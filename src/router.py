# -*- coding: utf-8 -*-
"""
Упрощенный маршрутизатор MCP-серверов.
Сканирует директорию на наличие manifest.json, запускает процессы и проксирует JSON-RPC вызовы.
"""
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import logging

logger = logging.getLogger(__name__)


def scan_manifests(directory: Path) -> List[Dict[str, Any]]:
    """
    Рекурсивно сканирует директорию в поисках файлов manifest.json.
    Возвращает список распарсенных манифестов.
    """
    manifests = []
    if not directory.exists():
        logger.warning(f"Директория MCP-движков не найдена: {directory}")
        return manifests

    for manifest_path in directory.rglob("manifest.json"):
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
                manifest["_source_path"] = str(manifest_path)
                manifests.append(manifest)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Ошибка чтения {manifest_path}: {e}")
    return manifests


def launch_mcp_server(manifest: Dict[str, Any]) -> Optional[subprocess.Popen]:
    """
    Запускает MCP-сервер на основе описания в манифесте.
    Ожидает ключ 'command' со списком аргументов (например, ["node", "server.js"]).
    """
    command = manifest.get("command")
    if not command:
        logger.error(f"Отсутствует команда запуска в манифесте: {manifest.get('name', 'unknown')}")
        return None

    # Подготовка аргументов для Windows
    creation_flags = 0
    if sys.platform == "win32":
        try:
            import subprocess
            creation_flags = subprocess.CREATE_NO_WINDOW
        except AttributeError:
            pass

    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",  # Защита от сбоев декодирования на границах буфера
            creationflags=creation_flags,
            cwd=Path(manifest["_source_path"]).parent
        )
        logger.info(f"MCP-сервер '{manifest.get('name')}' запущен с PID {process.pid}")
        return process
    except Exception as e:
        logger.error(f"Не удалось запустить MCP-сервер '{manifest.get('name')}': {e}")
        return None


def proxy_call(process: subprocess.Popen, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Отправляет JSON-RPC запрос запущенному процессу и возвращает результат.
    """
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments
        }
    }
    
    try:
        # Отправляем запрос с разделителем новой строки, как требует стандарт JSON-RPC over stdio
        request_str = json.dumps(request, ensure_ascii=False) + "\n"
        process.stdin.write(request_str)
        process.stdin.flush()
        
        # Читаем ответ (первая строка)
        # В реальной реализации可能需要 читать до \n или обрабатывать потоки асинхронно.
        # Для упрощенной версии читаем одну строку.
        response_str = process.stdout.readline()
        if not response_str:
            # Проверяем, не упал ли процесс
            if process.poll() is not None:
                stderr = process.stderr.read()
                return {"error": f"Процесс завершился с кодом {process.poll()}. Stderr: {stderr}"}
            return {"error": "Пустой ответ от MCP-сервера"}
            
        response = json.loads(response_str)
        
        if "error" in response:
            return {"error": response["error"]}
            
        return response.get("result", {})
        
    except json.JSONDecodeError as e:
        return {"error": f"Неверный JSON в ответе: {e}"}
    except Exception as e:
        return {"error": f"Ошибка при проксировании вызова: {e}"}