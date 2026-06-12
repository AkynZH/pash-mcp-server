# -*- coding: utf-8 -*-
"""
Cognitive Loop (Plan-Reflect) — превращает MCP-сервер в автономного агента.
~150 строк чистого Python + asyncio + pydantic. Без LangGraph/CrewAI.
Троица: Alpha (Архитектор) = openai/gpt-5.5, Judge (Судья) = anthropic/claude-sonnet-4.6
"""
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import List, Optional, Literal
from pydantic import BaseModel

class Step(BaseModel):
    tool: str
    args: dict
    description: str

class PlanResponse(BaseModel):
    steps: List[Step]

class ReflectResponse(BaseModel):
    status: Literal["FINISH", "ITERATE"]
    reason: str
    final_answer: Optional[str] = None

async def call_llm(prompt: str, schema: type[BaseModel], model: str) -> BaseModel:
    """Zero-dependency HTTP call to LLM with Pydantic validation and retry."""
    if os.environ.get("MOCK_LLM"):
        return schema.model_validate_json(os.environ["MOCK_LLM"])
    
    url = "https://openrouter.ai/api/v1/chat/completions"
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1
    }).encode('utf-8')
    
    req = __import__('urllib.request').Request(url, data=payload, headers={
        "Authorization": f"Bearer {os.environ.get('OPENROUTER_API_KEY', 'sk-or-dummy')}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost",
        "X-Title": "Felix Cognitive Loop"
    })
    
    for attempt in range(2):
        try:
            with __import__('urllib.request').urlopen(req, timeout=15) as resp:
                text = json.loads(resp.read().decode('utf-8', errors='replace'))['choices'][0]['message']['content']
                if "```json" in text:
                    text = text.split("```json")[1].split("```")[0].strip()
                return schema.model_validate_json(text)
        except Exception:
            await asyncio.sleep(1)
    raise RuntimeError("LLM JSON validation failed after 2 retries")

async def run_cognitive_loop(task: str, max_iterations: int = 3) -> dict:
    """Основной когнитивный цикл: Plan -> Execute -> Reflect."""
    # Alpha (Архитектор) планирует
    plan_prompt = f"Task: {task}. Break into executable steps using available tools. JSON schema: {PlanResponse.model_json_schema()}"
    plan = await call_llm(plan_prompt, PlanResponse, model=os.environ.get("ARCHITECT_MODEL", "openai/gpt-5.5"))
    
    history = []
    for iteration in range(max_iterations):
        step_results = []
        for step in plan.steps:
            # Вызов реального MCP-сервера через subprocess (std-io)
            server_path = Path(__file__).parent.parent / "server.py"
            proc = await asyncio.create_subprocess_exec(
                sys.executable, str(server_path),
                stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                env={**os.environ, "PYTHONPATH": str(Path(__file__).parent.parent)}
            )
            
            # Корректная инициализация MCP-сессии
            init_req = {"jsonrpc": "2.0", "id": 1, "method": "initialize", 
                        "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "Felix-Cognitive", "version": "1.0"}}}
            proc.stdin.write((json.dumps(init_req) + "\n").encode('utf-8'))
            await proc.stdin.drain()
            await proc.stdout.readline() # Читаем ответ initialize
            
            init_done = {"jsonrpc": "2.0", "method": "notifications/initialized"}
            proc.stdin.write((json.dumps(init_done) + "\n").encode('utf-8'))
            await proc.stdin.drain()
            
            # Вызов инструмента
            req = {"jsonrpc": "2.0", "id": 2, "method": "tools/call", 
                   "params": {"name": step.tool, "arguments": step.args}}
            proc.stdin.write((json.dumps(req) + "\n").encode('utf-8'))
            await proc.stdin.drain()
            
            out = await asyncio.wait_for(proc.stdout.readline(), timeout=15.0)
            res = json.loads(out.decode('utf-8', errors='replace')).get("result", {})
            proc.terminate()
            
            raw_size = res.get("raw_size_bytes", len(json.dumps(res).encode('utf-8')))
            pash_size = res.get("pash_size_bytes", raw_size)
            step_results.append({
                "tool": step.tool, 
                "raw_bytes": raw_size, 
                "pash_bytes": pash_size, 
                "data": res.get("pash_data", res)
            })
        
        history.append({"iteration": iteration + 1, "steps": step_results})
        total_pash = sum(s["pash_bytes"] for s in step_results)
        
        # Judge (Судья) оценивает
        reflect_prompt = f"Task: {task}. History: {json.dumps(history, ensure_ascii=False)}. Decide FINISH or ITERATE. Schema: {ReflectResponse.model_json_schema()}"
        reflection = await call_llm(reflect_prompt, ReflectResponse, model=os.environ.get("JUDGE_MODEL", "anthropic/claude-sonnet-4.6"))
        
        if reflection.status == "FINISH":
            return {
                "status": "SUCCESS", 
                "iterations": iteration + 1, 
                "answer": reflection.final_answer,
                "total_pash_bytes": total_pash, 
                "history": history
            }
            
    return {"status": "MAX_ITERATIONS", "iterations": max_iterations, "answer": "Task incomplete", "history": history}