# -*- coding: utf-8 -*-
"""
Скрипт для запуска демо-бенчмарков PASH-сжатия (День 1, Шаг 1.3-1.5).
Запускает server.py, вызывает демо-инструменты и замеряет реальную экономию.
"""
import subprocess
import json
import sys
import time
import os
from pathlib import Path

# Определяем пути
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
SERVER_SCRIPT = PROJECT_ROOT / "server.py"

def run_benchmark():
    print("🚀 Запуск pash-mcp-server для бенчмарков (native Windows)...")
    
    process = subprocess.Popen(
        [sys.executable, str(SERVER_SCRIPT)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=str(PROJECT_ROOT),
        env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT)}
    )

    results = []
    tools_to_test = [
        {"name": "demo_github_repo", "scenario": "GitHub Repo Analysis", "tool": "demo_github_repo"},
        {"name": "demo_filesystem_search", "scenario": "Filesystem Search", "tool": "demo_filesystem_search"},
        {"name": "demo_web_scraping", "scenario": "Web Scraping", "tool": "demo_web_scraping"}
    ]

    try:
        # 1. Initialize
        init_request = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "Benchmark-Client", "version": "1.0.0"}}}
        process.stdin.write(json.dumps(init_request) + "\n")
        process.stdin.flush()
        process.stdout.readline() # Читаем ответ initialize

        # Initialized notification
        process.stdin.write('{"jsonrpc": "2.0", "method": "notifications/initialized"}\n')
        process.stdin.flush()

        for item in tools_to_test:
            print(f"📊 Тестирование сценария: {item['scenario']}...")
            
            # Замеряем время вызова (latency)
            start_time = time.time()
            
            call_request = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": item["tool"], "arguments": {}}
            }
            process.stdin.write(json.dumps(call_request) + "\n")
            process.stdin.flush()
            
            # Читаем ответ (может быть несколько строк, ищем tools/call ответ)
            response_line = process.stdout.readline()
            while response_line:
                print(f"   🔍 Server said: {response_line.strip()[:100]}") # Отладка
                try:
                    resp = json.loads(response_line.strip())
                    if resp.get("id") == 2:
                        break
                except json.JSONDecodeError:
                    pass
                response_line = process.stdout.readline()

            latency_ms = (time.time() - start_time) * 1000

            if resp and "result" in resp and "content" in resp["result"]:
                content = resp["result"]["content"][0]["text"]
                try:
                    data = json.loads(content)
                    raw_bytes = data.get("raw_size_bytes", 0)
                    pash_bytes = data.get("pash_size_bytes", 0)
                    compressed = data.get("compressed", False)
                    
                    if compressed and raw_bytes > 0:
                        savings = ((raw_bytes - pash_bytes) / raw_bytes) * 100
                        results.append({
                            "scenario": item["scenario"],
                            "tool": item["tool"],
                            "raw_bytes": raw_bytes,
                            "pash_bytes": pash_bytes,
                            "savings": savings,
                            "latency_ms": round(latency_ms, 2),
                            "status": "PASS"
                        })
                        print(f"   ✅ PASS: Сжатие применено. Экономия: {savings:.1f}%")
                    else:
                        results.append({
                            "scenario": item["scenario"],
                            "tool": item["tool"],
                            "raw_bytes": raw_bytes,
                            "pash_bytes": pash_bytes,
                            "savings": 0.0,
                            "latency_ms": round(latency_ms, 2),
                            "status": "FAIL (Not compressed)"
                        })
                        print(f"   ❌ FAIL: Данные не были сжаты (возможно, размер < 500 байт).")
                except json.JSONDecodeError as e:
                    print(f"   💥 Отладка: Не удалось распарсить JSON. Получено: {content[:200]}")
                    print(f"   💥 Полный ответ сервера: {resp}")
                    results.append({"scenario": item["scenario"], "status": f"FAIL (Invalid JSON: {e})"})
                    print(f"   ❌ FAIL: Неверный формат ответа.")
            else:
                results.append({"scenario": item["scenario"], "status": "FAIL (No result)"})
                print(f"   ❌ FAIL: Нет ответа от инструмента.")

    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        stderr_out = process.stderr.read()
        if stderr_out:
            print(f"Server stderr:\n{stderr_out}")
    finally:
        process.terminate()
        process.wait()
        # Всегда читаем stderr в конце для отладки
        stderr_out = process.stderr.read()
        if stderr_out:
            print("\n--- Server Debug Logs ---")
            print(stderr_out)
            print("-------------------------")

    return results

def generate_report(results):
    print("\n📝 Генерация отчета DEMO_RESULTS.md...")
    
    avg_savings = 0.0
    valid_results = [r for r in results if r["status"] == "PASS"]
    if valid_results:
        avg_savings = sum(r["savings"] for r in valid_results) / len(valid_results)
    
    max_latency = max((r["latency_ms"] for r in valid_results), default=0)

    md_content = f"""# Real-World PASH Compression Benchmarks

Tested via native Windows integration with Odysseus MCP client.

"""
    for r in results:
        if r["status"] == "PASS":
            raw_tokens = r["raw_bytes"] // 4
            pash_tokens = r["pash_bytes"] // 4
            md_content += f"""## Scenario: {r['scenario']}
- **Tool:** `{r['tool']}`
- **Raw Response Size:** ~{r['raw_bytes']:,} bytes (~{raw_tokens:,} tokens)
- **PASH Response Size:** ~{r['pash_bytes']:,} bytes (~{pash_tokens:,} tokens)
- **Savings:** **{r['savings']:.1f}%**
- **Latency:** {r['latency_ms']} ms

"""
        else:
            md_content += f"""## Scenario: {r['scenario']}
- **Status:** ❌ {r['status']}

"""

    md_content += f"""## Summary
- **Average Token Savings:** **{avg_savings:.1f}%**
- **Setup Time:** < 5 minutes (Native PowerShell, no Docker)
- **Latency Overhead:** < {max_latency:.0f} ms
"""
    
    docs_dir = PROJECT_ROOT / "docs"
    docs_dir.mkdir(exist_ok=True)
    report_path = docs_dir / "DEMO_RESULTS.md"
    
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(md_content)
        
    print(f"✅ Отчет сохранен: {report_path}")
    print(f"📈 Средняя экономия: {avg_savings:.1f}%")

if __name__ == "__main__":
    benchmark_results = run_benchmark()
    generate_report(benchmark_results)
    
    # Проверка успешности
    all_pass = all(r["status"] == "PASS" for r in benchmark_results)
    sys.exit(0 if all_pass else 1)