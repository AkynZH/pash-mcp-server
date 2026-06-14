# -*- coding: utf-8 -*-
"""
Felix Gateway Runtime v2.0 — Продуктовый слой управления демонами Qwen.
Интегрирует QwenDaemonManager для автоматического управления жизненным циклом,
портами и рабочими пространствами (workspace).
"""
import asyncio
import json
import logging
import httpx
import os
import shutil
import socket
import subprocess
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional, Dict, Any
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Felix Gateway Runtime")


class QwenDaemonManager:
    """Управляет жизненным циклом демонов qwen serve для разных рабочих пространств."""
    
    def __init__(self):
        # registry: workspace -> {"port": int, "process": subprocess.Popen, "host": str}
        self.registry: Dict[str, Dict[str, Any]] = {}
        self._default_workspace = os.environ.get("FELIX_WORKSPACE", os.getcwd())

    def find_free_port(self) -> int:
        """Находит свободный порт в диапазоне 8769-8799."""
        for port in range(8769, 8800):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.bind(("127.0.0.1", port))
                    return port
                except OSError:
                    continue
        raise RuntimeError("Не удалось найти свободный порт для qwen serve")

    def is_process_alive(self, process: subprocess.Popen) -> bool:
        """Проверяет, жив ли процесс демона."""
        return process.poll() is None

    async def ensure_daemon(self, workspace: str) -> Dict[str, Any]:
        """
        Гарантирует наличие живого демона qwen serve для указанного workspace.
        Если демон занят другим workspace или мертв — запускает новый на свободном порту.
        """
        workspace = os.path.abspath(workspace)
        
        # 1. Проверяем существующую запись
        existing = self.registry.get(workspace)
        if existing and self.is_process_alive(existing["process"]):
            logger.info(f"[DaemonManager] Демон для {workspace} уже активен на порту {existing['port']}")
            return existing

        # 2. Очищаем мертвые записи для этого workspace
        if existing and not self.is_process_alive(existing["process"]):
            logger.warning(f"[DaemonManager] Демон для {workspace} мертв. Перезапуск...")
            if "log_file" in existing and not existing["log_file"].closed:
                existing["log_file"].close()
            del self.registry[workspace]

        # 3. Ищем свободный порт и запускаем новый демон
        port = self.find_free_port()
        logger.info(f"[DaemonManager] Запуск qwen serve для {workspace} на порту {port}")
        
        try:
            # Запускаем qwen serve в фоновом режиме
            # Открываем файл для логов и НЕ закрываем его, чтобы Popen мог в него писать
            log_file_path = Path(workspace) / f"qwen_daemon_{port}.log"
            log_file = open(log_file_path, "a", encoding="utf-8")
            log_file.write(f"\n--- Starting daemon at {port} for {workspace} at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
            log_file.flush()
            
            # Находим полный путь к qwen (учитывая .cmd на Windows)
            qwen_executable = shutil.which("qwen") or shutil.which("qwen.cmd") or "qwen"

            process = subprocess.Popen(
                [
                    qwen_executable, "serve", "--http-bridge", 
                    "--port", str(port), 
                    "--workspace", workspace
                ],
                cwd=workspace,
                env=os.environ,
                stdout=subprocess.DEVNULL,
                stderr=log_file, # Передаем открытый файл
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )

            # Даем демону 3 секунды на подъем (иногда требуется больше на Windows)
            await asyncio.sleep(3)
            
            # Проверяем, жив ли процесс
            if not self.is_process_alive(process):
                logger.error(f"[DaemonManager] Демон для {workspace} упал сразу после запуска. См. {log_file_path}")
                log_file.close()
                raise RuntimeError(f"Qwen daemon crashed on startup. Check {log_file_path}")
            
            daemon_info = {
                "host": "127.0.0.1",
                "port": port,
                "workspace": workspace,
                "process": process,
                "log_file": log_file # Сохраняем ссылку на файл
            }
            self.registry[workspace] = daemon_info
            return daemon_info
            
        except Exception as e:
            logger.error(f"[DaemonManager] Ошибка запуска демона: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to start qwen serve: {str(e)}")

    def get_status(self, workspace: Optional[str] = None) -> Dict[str, Any]:
        """Возвращает честный статус демонов."""
        if workspace:
            info = self.registry.get(workspace)
            if not info:
                return {"status": "not_found", "workspace": workspace}
            return {
                "status": "connected" if self.is_process_alive(info["process"]) else "dead",
                "workspace": info["workspace"],
                "host": info["host"],
                "port": info["port"]
            }
        
        # Статус всех демонов
        return {
            "active_daemons": [
                {
                    "workspace": w,
                    "status": "connected" if self.is_process_alive(d["process"]) else "dead",
                    "port": d["port"]
                }
                for w, d in self.registry.items()
            ]
        }

daemon_manager = QwenDaemonManager()

# Разрешаем CORS для доступа из браузера (включая file:// и localhost)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Очереди событий для стриминга
qwen_events_queue: asyncio.Queue = asyncio.Queue()
felix_events_queue: asyncio.Queue = asyncio.Queue()

# Состояние сессии Qwen (Odysseus Bridge state)
qwen_session_state = {
    "session_id": None,
    "workspace_cwd": None,
    "last_event_id": None,
    "is_polling": False
}

# Раздача статики из папки static
STATIC_DIR = Path(__file__).parent.parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

@app.get("/", response_class=HTMLResponse)
async def root():
    """Отдает основной файл UI."""
    return FileResponse(STATIC_DIR / "index.html")

async def _generate_sse(queue: asyncio.Queue, name: str):
    """Генератор событий для SSE."""
    async def event_generator():
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=15.0)
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"
            except asyncio.CancelledError:
                logger.info(f"[{name}] SSE соединение разорвано клиентом.")
                break
            except Exception as e:
                logger.error(f"[{name}] Ошибка в генераторе SSE: {e}")
                yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
                break
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/api/qwen_stream")
async def qwen_stream(request: Request):
    """SSE эндпоинт для событий Qwen Code (реальный поток или очередь)."""
    return await _generate_sse(qwen_events_queue, "QwenStream")

@app.get("/api/agent_stream")
async def agent_stream(request: Request):
    """SSE эндпоинт для событий ядра Felix."""
    return await _generate_sse(felix_events_queue, "AgentStream")

@app.post("/api/qwen/connect")
async def connect_qwen(payload: dict = {}):
    """
    Продуктовый эндпоинт: инициализирует сессию с qwen serve.
    Фронтенд не передает cwd/host/port. Бэкенд сам определяет рабочее пространство
    и гарантирует наличие живого демона.
    """
    # Если workspace не передан, используем дефолтный из окружения или текущую директорию
    raw_cwd = payload.get("cwd")
    workspace_cwd = raw_cwd or daemon_manager._default_workspace
    workspace_cwd = os.path.abspath(workspace_cwd)
    
    # ЯВНАЯ ОТЛАДКА
    print(f"!!! DEBUG: raw_cwd={repr(raw_cwd)}, default={repr(daemon_manager._default_workspace)}, final={repr(workspace_cwd)}")

    # 1. Гарантируем наличие живого демона для этого workspace
    try:
        daemon_info = await daemon_manager.ensure_daemon(workspace_cwd)
    except HTTPException:
        raise
    
    host = daemon_info["host"]
    port = daemon_info["port"]
    base_url = f"http://{host}:{port}"

    # Если уже есть активная сессия для этого воркспейса, возвращаем её
    if qwen_session_state["is_polling"] and qwen_session_state["workspace_cwd"] == workspace_cwd:
        return {
            "status": "ok", 
            "message": "Уже подключено", 
            "session_id": qwen_session_state["session_id"],
            "workspace": workspace_cwd,
            "port": port
        }

    # 2. Создание сессии
    # Используем прямые слеши для совместимости с парсерами, ожидающими POSIX-пути даже на Windows
    safe_workspace_cwd = workspace_cwd.replace("\\", "/")
    req_payload = {"cwd": safe_workspace_cwd}
    logger.info(f"[Gateway] Отправка запроса на создание сессии в {base_url}/session: {req_payload}")
    try:
        async with httpx.AsyncClient(trust_env=False) as client:
            response = await client.post(
                f"{base_url}/session",
                json=req_payload,
                timeout=10.0 # Увеличиваем таймаут для первого запуска демона
            )
            
            # Обработка workspace_mismatch, если демон все же оказался привязан к другому
            if response.status_code == 400 and "workspace_mismatch" in response.text:
                logger.warning(f"[DaemonManager] workspace_mismatch на порту {port}. Перезапуск...")
                # В реальном сценарии здесь мы бы убили процесс и запустили новый, 
                # но ensure_daemon уже должен был это предотвратить.
                raise HTTPException(status_code=400, detail=response.text)
                
            response.raise_for_status()
            result = response.json()

            qwen_session_state["session_id"] = result.get("sessionId")
            qwen_session_state["workspace_cwd"] = workspace_cwd
            qwen_session_state["qwen_host"] = host
            qwen_session_state["qwen_port"] = port
            qwen_session_state["is_polling"] = True
            
            logger.info(f"[Gateway] Сессия qwen создана: {qwen_session_state['session_id']} на порту {port}")

            # 3. Запуск фонового опроса событий
            asyncio.create_task(_poll_qwen_sse(base_url))

            return {
                "status": "ok", 
                "message": "Сессия создана, опрос запущен", 
                "session_id": qwen_session_state["session_id"],
                "workspace": workspace_cwd,
                "port": port
            }
    except httpx.HTTPStatusError as e:
        logger.error(f"[Gateway] HTTP Error creating session: {e.response.text}")
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        logger.error(f"[Gateway] Ошибка создания сессии: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/qwen/status")
async def qwen_status():
    """Возвращает честное состояние Gateway и демонов Qwen."""
    current_workspace = qwen_session_state.get("workspace_cwd")
    daemon_status = daemon_manager.get_status(current_workspace) if current_workspace else daemon_manager.get_status()
    
    return {
        "gateway_status": "healthy",
        "active_session": {
            "session_id": qwen_session_state["session_id"],
            "workspace": qwen_session_state["workspace_cwd"],
            "host": qwen_session_state.get("qwen_host"),
            "port": qwen_session_state.get("qwen_port"),
            "is_polling": qwen_session_state["is_polling"]
        } if qwen_session_state["is_polling"] else None,
        "daemons": daemon_status
    }

async def _poll_qwen_sse(base_url: str):
    """
    Фоновая задача ИСТИННОГО асинхронного SSE-стриминга (Odysseus Bridge v1.2).
    Использует httpx с timeout=None для удержания единого долгоживущего соединения.
    Читает чанки по мере их поступления, исключая потерю событий между опросами.
    Поддерживает Last-Event-ID для корректного восстановления при обрыве соединения.
    """
    session_id = qwen_session_state["session_id"]
    url = f"{base_url}/session/{session_id}/events"
    
    logger.info(f"[OdysseusBridge] Запуск асинхронного SSE-стриминга: {url}")
    
    while qwen_session_state["is_polling"]:
        headers = {}
        if qwen_session_state["last_event_id"]:
            headers["Last-Event-ID"] = qwen_session_state["last_event_id"]
            
        try:
            # timeout=None держит соединение открытым indefinitely для истинного стриминга
            # trust_env=False отключает системный прокси для предотвращения перехвата localhost
            async with httpx.AsyncClient(timeout=httpx.Timeout(None), trust_env=False) as client:
                async with client.stream("GET", url, headers=headers) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not qwen_session_state["is_polling"]:
                            break
                        if line.startswith("data: "):
                            try:
                                event_data = json.loads(line[6:])
                                if isinstance(event_data, dict) and "id" in event_data:
                                    qwen_session_state["last_event_id"] = str(event_data["id"])
                                await qwen_events_queue.put(event_data)
                            except json.JSONDecodeError:
                                await qwen_events_queue.put({"raw_data": line[6:]})
                        elif line.startswith("id: "):
                            # Альтернативный источник ID события из заголовка SSE
                            qwen_session_state["last_event_id"] = line[4:].strip()
        except httpx.ReadTimeout:
            pass # Ожидается при некоторых конфигурациях, продолжаем цикл
        except httpx.ReadError as e:
            logger.warning(f"[OdysseusBridge] SSE соединение разорвано: {e}. Переподключение через 1с...")
            await asyncio.sleep(1) # Экспоненциальная задержка перед переподключением
        except Exception as e:
            logger.error(f"[OdysseusBridge] Критическая ошибка SSE-стриминга: {e}")
            await asyncio.sleep(1)
            
    logger.info("[OdysseusBridge] Асинхронный SSE-стриминг остановлен.")

@app.post("/api/push_felix")
async def push_felix_event(event: dict):
    """Внешний эндпоинт для добавления события Felix в очередь."""
    await felix_events_queue.put(event)
    return {"status": "ok", "message": "Felix event queued"}

@app.post("/api/push_qwen")
async def push_qwen_event(payload: dict):
    """Отправка задачи в qwen serve через активную сессию. Порт и хост берутся из состояния сессии."""
    task = payload.get("task") or payload.get("message") or payload.get("prompt", "")
    if not task:
        raise HTTPException(status_code=400, detail="Task/message is required")

    session_id = qwen_session_state.get("session_id")
    if not session_id or not qwen_session_state["is_polling"]:
        raise HTTPException(status_code=400, detail="Qwen session not initialized. Call /api/qwen/connect first.")

    # Берем актуальные хост и порт из состояния сессии, а не хардкодим
    qwen_host = qwen_session_state.get("qwen_host", "127.0.0.1")
    qwen_port = qwen_session_state.get("qwen_port", 8769)
    base_url = f"http://{qwen_host}:{qwen_port}"

    # Формат ACP для отправки промпта: массив блоков контента
    req_payload = {
        "prompt": [{"type": "text", "text": str(task)}]
    }

    try:
        async with httpx.AsyncClient(trust_env=False) as client:
            response = await client.post(
                f"{base_url}/session/{session_id}/prompt",
                json=req_payload,
                timeout=10.0
            )
            response.raise_for_status()
            result = response.json()
            logger.info(f"[Gateway] Промпт отправлен в сессию {session_id}, promptId: {result.get('promptId')}")
            return {"status": "ok", "message": "Task sent to Qwen", "prompt_id": result.get("promptId")}
    except httpx.HTTPStatusError as e:
        logger.error(f"[Gateway] HTTP Error sending prompt: {e.response.text}")
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        logger.error(f"[Gateway] Ошибка отправки промпта: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
async def health():
    """Проверка здоровья сервера и статуса моста."""
    return {
        "status": "healthy", 
        "qwen_queue_size": qwen_events_queue.qsize(), 
        "felix_queue_size": felix_events_queue.qsize(),
        "odysseus_bridge": {
            "is_polling": qwen_session_state["is_polling"],
            "session_id": qwen_session_state["session_id"]
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8770)
