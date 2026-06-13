# -*- coding: utf-8 -*-
"""
SSE Server v1.1 — Сервер для трансляции событий в 4-зонный UI.
Интегрирует реальную логику Odysseus Bridge (zero-dependency urllib) для проксирования 
настоящих событий от qwen serve, а не демо-генераторов.
"""
import asyncio
import json
import logging
import urllib.request
import urllib.error
import httpx
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Felix SSE Proxy")

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
async def connect_qwen(payload: dict):
    """
    Инициирует сессию с qwen serve и запускает фоновый опрос событий (Odysseus Bridge logic).
    Использует zero-dependency urllib с явными таймаутами (fail-fast).
    """
    workspace_cwd = payload.get("cwd", ".")
    qwen_host = payload.get("host", "127.0.0.1")
    qwen_port = payload.get("port", 8769)
    base_url = f"http://{qwen_host}:{qwen_port}"

    if qwen_session_state["is_polling"]:
        return {"status": "ok", "message": "Уже подключено", "session_id": qwen_session_state["session_id"]}

    # 1. Создание сессии (OdysseusBridge.create_qwen_session)
    req_payload = json.dumps({"cwd": workspace_cwd}).encode('utf-8')
    req = urllib.request.Request(
        f"{base_url}/session",
        data=req_payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            result = json.loads(response.read().decode('utf-8'))
            qwen_session_state["session_id"] = result.get("sessionId")
            qwen_session_state["workspace_cwd"] = workspace_cwd
            qwen_session_state["is_polling"] = True
            logger.info(f"[OdysseusBridge] Сессия qwen создана: {qwen_session_state['session_id']}")
            
            # 2. Запуск фонового опроса событий
            asyncio.create_task(_poll_qwen_sse(base_url))
            
            return {"status": "ok", "message": "Сессия создана, опрос запущен", "session_id": qwen_session_state["session_id"]}
    except urllib.error.HTTPError as e:
        logger.error(f"[OdysseusBridge] HTTP Error creating session: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"[OdysseusBridge] Ошибка создания сессии: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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
            async with httpx.AsyncClient(timeout=httpx.Timeout(None)) as client:
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
    """Отправка задачи в qwen serve через активную сессию Odysseus Bridge."""
    task = payload.get("task") or payload.get("message") or payload.get("prompt", "")
    if not task:
        raise HTTPException(status_code=400, detail="Task/message is required")

    session_id = qwen_session_state.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="Qwen session not initialized. Call /api/qwen/connect first.")

    qwen_host = "127.0.0.1"
    qwen_port = 8769
    base_url = f"http://{qwen_host}:{qwen_port}"

    # Формат ACP для отправки промпта: массив блоков контента
    req_payload = {
        "prompt": [{"type": "text", "text": str(task)}]
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{base_url}/session/{session_id}/prompt",
                json=req_payload,
                timeout=10.0
            )
            response.raise_for_status()
            result = response.json()
            logger.info(f"[OdysseusBridge] Промпт отправлен в сессию {session_id}, promptId: {result.get('promptId')}")
            return {"status": "ok", "message": "Task sent to Qwen", "prompt_id": result.get("promptId")}
    except httpx.HTTPStatusError as e:
        logger.error(f"[OdysseusBridge] HTTP Error sending prompt: {e.response.text}")
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        logger.error(f"[OdysseusBridge] Ошибка отправки промпта: {e}")
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
