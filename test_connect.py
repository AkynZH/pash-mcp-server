import subprocess
import time
import requests
import os
import sys

# 1. Хирургическая очистка портов (без убийства родительского python.exe)
print("Очистка портов 8770, 8765, 8769...")
subprocess.run([sys.executable, "clean_ports.py"], cwd="D:\\Felix\\projects\\felix-mcp-standalone", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)

# 2. Запуск сервера
print("Запуск uvicorn...")
with open("uvicorn_debug.log", "w", encoding="utf-8") as log_file:
    server_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "src.sse_server:app", "--host", "127.0.0.1", "--port", "8770"],
        cwd="D:\\Felix\\projects\\felix-mcp-standalone",
        stdout=log_file,
        stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NO_WINDOW
    )
time.sleep(4)

# 3. Тест запроса
print("Отправка запроса /api/qwen/connect с пустым payload...")
try:
    r = requests.post("http://127.0.0.1:8770/api/qwen/connect", json={}, timeout=15, proxies={"http": None, "https": None})
    print(f"Status: {r.status_code}")
    print(f"Response: {r.text}")

    if r.status_code != 200:
        workspace = "D:\\Felix\\projects\\felix-mcp-standalone"
        log_file = os.path.join(workspace, "qwen_daemon_8769.log")
        if os.path.exists(log_file):
            print(f"\n--- Лог демона ({log_file}) ---")
            with open(log_file, "r", encoding="utf-8", errors="replace") as f:
                print(f.read()[-1000:])
        else:
            print(f"Лог-файл {log_file} не найден.")

except Exception as e:
    print(f"Ошибка запроса: {e}")
finally:
    server_proc.terminate()
    # Снова хирургическая очистка
    subprocess.run([sys.executable, "clean_ports.py"], cwd="D:\\Felix\\projects\\felix-mcp-standalone", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    print("\n--- Логи uvicorn ---")
    if os.path.exists("uvicorn_debug.log"):
        with open("uvicorn_debug.log", "r", encoding="utf-8", errors="replace") as f:
            print(f.read()[-1500:])
    else:
        print("Лог uvicorn не найден.")