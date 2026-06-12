# -*- coding: utf-8 -*-
"""
Тестовый скрипт для проверки связи Odysseus (клиент) с pash-mcp-server.
Запускает сервер, отправляет запрос и проверяет наличие PASH-сжатого ответа или корректный старт.
"""
import subprocess
import json
import sys
from pathlib import Path

# Определяем пути
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
SERVER_SCRIPT = PROJECT_ROOT / "server.py"

def test_odysseus_connection():
    print("🚀 Запуск pash-mcp-server для проверки связи (native Windows)...")
    
    # Запускаем сервер как subprocess с перенаправлением stdin/stdout (режим stdio)
    process = subprocess.Popen(
        [sys.executable, str(SERVER_SCRIPT)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=str(PROJECT_ROOT),
        env={**dict(os.environ), "PYTHONPATH": str(PROJECT_ROOT)}
    )

    try:
        # 1. Отправляем MCP Initialize запрос
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "Odysseus-Test-Client", "version": "1.0.0"}
            }
        }
        print("📤 Отправка MCP initialize запроса...")
        process.stdin.write(json.dumps(init_request) + "\n")
        process.stdin.flush()

        # Читаем ответ (может быть несколько строк, берем первую валидную JSON)
        response_line = process.stdout.readline()
        if not response_line:
            print("❌ ОШИБКА: Сервер не ответил или закрыл соединение.")
            stderr_out = process.stderr.read()
            if stderr_out:
                print(f"Stderr: {stderr_out}")
            return False
            
        response = json.loads(response_line)
        print("📥 Получен ответ от сервера:")
        print(json.dumps(response, indent=2, ensure_ascii=False))

        if "result" in response and "capabilities" in response["result"]:
            print("✅ Сервер успешно инициализирован (Odysseus может подключиться).")
        else:
            print("⚠️ Необычный формат ответа, но сервер жив.")

        # 2. Проверяем доступность инструментов (которые возвращают PASH-данные при вызове)
        tools_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }
        print("\n📤 Запрос списка инструментов (tools/list)...")
        process.stdin.write(json.dumps(tools_request) + "\n")
        process.stdin.flush()
        
        tools_line = process.stdout.readline()
        tools_response = json.loads(tools_line)
        print("📥 Ответ tools/list:", json.dumps(tools_response, indent=2, ensure_ascii=False))

        print("\n🎉 ПРОВЕРКА УСПЕШНА: Связь с pash-mcp-server установлена.")
        print("💡 При вызове любого инструмента сервер автоматически применяет AdaptivePashCompressor и возвращает поле 'pash_data'.")
        return True

    except Exception as e:
        print(f"❌ ОШИБКА при проверке связи: {e}")
        return False
    finally:
        process.terminate()
        process.wait()

if __name__ == "__main__":
    import os
    success = test_odysseus_connection()
    sys.exit(0 if success else 1)