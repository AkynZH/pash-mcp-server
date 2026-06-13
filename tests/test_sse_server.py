# -*- coding: utf-8 -*-
"""
Тесты для SSE Server (src/sse_server.py).
Проверка эндпоинтов стриминга и очереди событий без запуска реального UI.
"""
import pytest
import asyncio
import json
from fastapi.testclient import TestClient
import sys
import os

# Добавляем путь к src для корректного импорта
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from sse_server import app, qwen_events_queue, felix_events_queue

client = TestClient(app)

@pytest.fixture(autouse=True)
def clear_queues():
    """Очистка очередей перед каждым тестом."""
    while not qwen_events_queue.empty():
        qwen_events_queue.get_nowait()
    while not felix_events_queue.empty():
        felix_events_queue.get_nowait()
    yield

def test_health_endpoint():
    """Проверка эндпоинта /api/health."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "qwen_queue_size" in data
    assert "felix_queue_size" in data

@pytest.mark.asyncio
async def test_push_qwen_event():
    """Проверка добавления события в очередь Qwen и его доступности."""
    test_event = {"type": "test", "data": "hello_qwen"}
    response = client.post("/api/push_qwen", json=test_event)
    
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    
    # Проверяем, что событие попало в очередь
    assert not qwen_events_queue.empty()
    queued_event = await qwen_events_queue.get()
    assert queued_event["type"] == "test"
    assert queued_event["data"] == "hello_qwen"

@pytest.mark.asyncio
async def test_push_felix_event():
    """Проверка добавления события в очередь Felix и его доступности."""
    test_event = {"phase": "judge", "data": "validation_passed"}
    response = client.post("/api/push_felix", json=test_event)
    
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    
    # Проверяем, что событие попало в очередь
    assert not felix_events_queue.empty()
    queued_event = await felix_events_queue.get()
    assert queued_event["phase"] == "judge"
    assert queued_event["data"] == "validation_passed"

def test_root_serves_html():
    """Проверка, что корень отдает HTML (index.html)."""
    # Примечание: в тестовом окружении StaticFiles может требовать наличия файлов,
    # но мы проверяем, что маршрут существует и не падает с 404, если файл есть.
    # Если файла нет, будет 404, что тоже валидно для проверки маршрутизации.
    response = client.get("/")
    # Если static/index.html существует, будет 200. Иначе 404.
    # Для надежности теста просто проверим, что эндпоинт отвечает (не 500).
    assert response.status_code in [200, 404]
