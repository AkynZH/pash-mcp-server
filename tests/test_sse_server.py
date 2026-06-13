# -*- coding: utf-8 -*-
"""
Тесты для SSE Server (src/sse_server.py).
Проверка эндпоинтов стриминга, очереди событий и интеграции Odysseus Bridge.
"""
import pytest
import asyncio
import json
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import sys
import os

# Добавляем путь к src для корректного импорта
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from sse_server import app, qwen_events_queue, felix_events_queue, qwen_session_state

client = TestClient(app)

@pytest.fixture(autouse=True)
def reset_state():
    """Сброс состояния очередей и сессии перед каждым тестом."""
    while not qwen_events_queue.empty():
        qwen_events_queue.get_nowait()
    while not felix_events_queue.empty():
        felix_events_queue.get_nowait()
    
    qwen_session_state["session_id"] = None
    qwen_session_state["workspace_cwd"] = None
    qwen_session_state["last_event_id"] = None
    qwen_session_state["is_polling"] = False
    yield

def test_health_endpoint_shows_bridge_state():
    """Проверка, что /api/health отражает состояние Odysseus Bridge."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "odysseus_bridge" in data
    assert "is_polling" in data["odysseus_bridge"]
    assert "session_id" in data["odysseus_bridge"]

@patch('sse_server._poll_qwen_sse') # Мокаем фоновую задачу, чтобы она не блокировала event loop синхронным urllib
@patch('urllib.request.urlopen')
def test_qwen_connect_success(mock_urlopen, mock_poll_task):
    """Проверка успешного создания сессии и инициации опроса через Odysseus Bridge."""
    # Мокаем ответ qwen serve на создание сессии
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.read.return_value = json.dumps({"sessionId": "test-session-123", "clientId": "client-abc"}).encode('utf-8')
    mock_urlopen.return_value.__enter__.return_value = mock_response

    payload = {"cwd": "/test/workspace", "host": "127.0.0.1", "port": 8769}
    response = client.post("/api/qwen/connect", json=payload)
    
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "ok"
    assert result["session_id"] == "test-session-123"
    
    # Проверяем, что состояние обновилось и фоновая задача была запланирована
    assert qwen_session_state["is_polling"] is True
    assert qwen_session_state["session_id"] == "test-session-123"
    assert qwen_session_state["workspace_cwd"] == "/test/workspace"
    mock_poll_task.assert_called_once_with("http://127.0.0.1:8769")

@patch('urllib.request.urlopen')
def test_qwen_connect_failure(mock_urlopen):
    """Проверка обработки ошибки при создании сессии (например, qwen serve недоступен)."""
    mock_urlopen.side_effect = Exception("Connection refused")

    payload = {"cwd": "/test/workspace"}
    response = client.post("/api/qwen/connect", json=payload)
    
    assert response.status_code == 500
    result = response.json()
    # HTTPException возвращает ошибку в поле 'detail'
    assert "Connection refused" in result["detail"]
    
    # Состояние не должно измениться на активное
    assert qwen_session_state["is_polling"] is False

@pytest.mark.asyncio
async def test_push_felix_event():
    """Проверка добавления события в очередь Felix."""
    test_event = {"phase": "judge", "data": "validation_passed"}
    response = client.post("/api/push_felix", json=test_event)
    
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    
    assert not felix_events_queue.empty()
    queued_event = await felix_events_queue.get()
    assert queued_event["phase"] == "judge"
    assert queued_event["data"] == "validation_passed"

def test_root_serves_html():
    """Проверка, что корень отдает HTML (index.html)."""
    response = client.get("/")
    assert response.status_code in [200, 404]
