# -*- coding: utf-8 -*-
"""
Тест когнитивного цикла (Cyborg Test).
Сценарий: "Find TODOs in the project".
"""
import asyncio
import json
import os
import sys
from pathlib import Path

# Добавляем корень проекта в sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.cognitive_loop import run_cognitive_loop

async def test_cyborg():
    print("🚀 Запуск Cyborg Test: 'Find TODOs in the project'...")
    
    # Мокаем LLM для гарантированного прохождения теста без реальных API-вызовов
    # Alpha (Архитектор) планирует вызвать demo_filesystem_search
    mock_plan = json.dumps({
        "steps": [
            {"tool": "demo_filesystem_search", "args": {}, "description": "Search for TODOs"}
        ]
    })
    
    # Judge (Судья) завершает задачу после первой итерации
    mock_reflect = json.dumps({
        "status": "FINISH",
        "reason": "Found TODOs successfully",
        "final_answer": "Найдено 5 TODOs в файлах проекта. Задача выполнена."
    })
    
    # Устанавливаем моки через环境变量
    os.environ["MOCK_LLM"] = mock_plan # Это сработает только для первого вызова, но для простоты теста переопределим функцию
    
    # Переопределяем call_llm локально для теста, чтобы контролировать последовательность ответов
    import src.cognitive_loop as cl
    original_call_llm = cl.call_llm
    call_count = 0
    
    async def mock_call_llm(prompt: str, schema: type, model: str):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return schema.model_validate_json(mock_plan)
        else:
            return schema.model_validate_json(mock_reflect)
            
    cl.call_llm = mock_call_llm
    
    try:
        result = await run_cognitive_loop(task="Find TODOs in the project", max_iterations=3)
        
        print("\n--- ОТЧЕТ CYBORG TEST ---")
        print(f"Результат: ✅ PASS" if result["status"] == "SUCCESS" else f"Результат: ❌ FAIL")
        print(f"Количество итераций: {result['iterations']}")
        
        # Подсчет PASH-экономии
        total_raw = sum(s["raw_bytes"] for iter_data in result["history"] for s in iter_data["steps"])
        total_pash = sum(s["pash_bytes"] for iter_data in result["history"] for s in iter_data["steps"])
        savings = ((total_raw - total_pash) / total_raw * 100) if total_raw > 0 else 0
        
        print(f"Размер PASH-ответов, переданных в REFLECT: {total_pash} байт (Raw: {total_raw} байт, Экономия: {savings:.1f}%)")
        print(f"Итоговый ответ агента: {result['answer']}")
        
        assert result["status"] == "SUCCESS", "Agent did not finish successfully"
        assert result["iterations"] == 1, "Agent took more than 1 iteration for mocked simple task"
        print("✅ Все ассерты пройдены. Cyborg Test PASSED.")
        
    finally:
        cl.call_llm = original_call_llm
        if "MOCK_LLM" in os.environ:
            del os.environ["MOCK_LLM"]

if __name__ == "__main__":
    asyncio.run(test_cyborg())