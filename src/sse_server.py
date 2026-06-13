# -*- coding: utf-8 -*-
"""
SSE Server v1.0 — Сервер для трансляции событий в 4-зонный UI.
Принимает события от ядра Felix и проксирует события Qwen Code (через имитацию или реальный Odysseus Bridge).
Использует FastAPI и StreamingResponse для zero-dependency SSE (в рамках возможностей stdlib/asyncio).
"""
import asyncio
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения (запуск/остановка демо-генераторов)."""
    logger.info("Запуск демо-генераторов событий. Для реальных данных отключите _simulate_* в lifespan.")
    task1 = asyncio.create_task(_simulate_qwen_events())
    task2 = asyncio.create_task(_simulate_felix_events())
    yield
    logger.info("Остановка демо-генераторов событий.")
    task1.cancel()
    task2.cancel()

app = FastAPI(title="Felix SSE Proxy", lifespan=lifespan)

# Очереди событий для стриминга
qwen_events_queue: asyncio.Queue = asyncio.Queue()
felix_events_queue: asyncio.Queue = asyncio.Queue()

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
                # Ждем событие с таймаутом, чтобы отправлять keepalive
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
    """SSE эндпоинт для событий Qwen Code."""
    return await _generate_sse(qwen_events_queue, "QwenStream")

@app.get("/api/agent_stream")
async def agent_stream(request: Request):
    """SSE эндпоинт для событий ядра Felix."""
    return await _generate_sse(felix_events_queue, "AgentStream")

@app.post("/api/push_qwen")
async def push_qwen_event(event: dict):
    """Внешний эндпоинт для добавления события Qwen в очередь."""
    await qwen_events_queue.put(event)
    return {"status": "ok", "message": "Qwen event queued"}

@app.post("/api/push_felix")
async def push_felix_event(event: dict):
    """Внешний эндпоинт для добавления события Felix в очередь."""
    await felix_events_queue.put(event)
    return {"status": "ok", "message": "Felix event queued"}

@app.get("/api/health")
async def health():
    """Проверка здоровья сервера."""
    return {"status": "healthy", "qwen_queue_size": qwen_events_queue.qsize(), "felix_queue_size": felix_events_queue.qsize()}

# ==========================================
# Демо-генераторы (для тестирования UI без реального ядра)
# ==========================================
import random

async def _simulate_qwen_events():
    """Имитация потока событий от Qwen Code."""
    states = ["thinking", "tool_call", "tool_result", "message"]
    tools = ["read_file", "run_shell_command", "grep_search"]
    while True:
        await asyncio.sleep(random.uniform(1.5, 3.5))
        state = random.choice(states)
        event = {
            "timestamp": asyncio.get_event_loop().time(),
            "type": "qwen_event",
            "status": state,
            "data": f"Qwen processing: {random.choice(tools)} on dummy_file.py" if state != "message" else "Qwen: Task completed successfully."
        }
        await qwen_events_queue.put(event)

async def _simulate_felix_events():
    """Имитация потока событий от ядра Felix (CognitiveLoop)."""
    phases = ["plan", "compress", "execute", "judge", "retry", "done"]
    while True:
        await asyncio.sleep(random.uniform(2.0, 4.0))
        phase = random.choice(phases)
        event = {
            "timestamp": asyncio.get_event_loop().time(),
            "type": "felix_event",
            "phase": phase,
            "data": f"Felix CognitiveLoop: Phase '{phase}' completed. PASH compression active."
        }
        await felix_events_queue.put(event)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8770)
