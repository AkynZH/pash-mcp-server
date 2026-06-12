# -*- coding: utf-8 -*-
"""
Простой JSON-RPC сервер для демо-бенчмарков (без FastMCP, чтобы обойти требование initialize).
Читает stdin, отвечает на tools/call.
"""
import sys
import json

def get_demo_github_repo():
    items = [
        {
            "name": f"repo_{i}", 
            "full_name": f"org/repo_{i}", 
            "description": "A demo repository for testing PASH compression", 
            "url": f"https://github.com/org/repo_{i}", 
            "stars": 1000+i, 
            "forks": 100+i, 
            "language": "Python", 
            "topics": ["demo", "test", "pash", "compression", "benchmark"]
        } for i in range(100)
    ]
    return {"status": "success", "data": {"items": items, "total_count": 100}}

def get_demo_filesystem_search():
    items = [
        {
            "path": f"/src/module_{i}.py", 
            "query": "TODO", 
            "row_count": 5, 
            "matches": [f"Line {j}: TODO: fix this bug" for j in range(5)]
        } for i in range(100)
    ]
    return {"status": "success", "results": items}

def get_demo_web_scraping():
    # Возвращаем список абзацев, чтобы продемонстрировать PASH-сжатие однородных массивов
    paragraphs = [
        {
            "id": i,
            "type": "paragraph",
            "text": "Это тестовая веб-статья с повторяющимся контентом для проверки эффективного PASH-сжатия однородных массивов."
        } for i in range(200)
    ]
    return {
        "status": "success",
        "title": "Demo Article on Web Scraping",
        "url": "https://example.com/article",
        "summary": "Test",
        "content": paragraphs
    }

def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            if request.get("method") == "tools/call":
                tool_name = request["params"]["name"]
                request_id = request.get("id", 1)
                with open("debug_demo.log", "a") as f:
                    f.write(f"Received tool call for: '{tool_name}' (len={len(tool_name)})\n")
                
                if tool_name == "demo_github_repo":
                    result = get_demo_github_repo()
                elif tool_name == "demo_filesystem_search":
                    result = get_demo_filesystem_search()
                elif tool_name == "demo_web_scraping":
                    result = get_demo_web_scraping()
                else:
                    result = {"error": f"Unknown tool: {tool_name}"}
                
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]}
                }
                print(json.dumps(response, ensure_ascii=False), flush=True)
            elif request.get("method") == "initialize":
                # Отвечаем на initialize, чтобы быть совместимыми
                response = {
                    "jsonrpc": "2.0",
                    "id": request.get("id", 1),
                    "result": {"protocolVersion": "2024-11-05", "capabilities": {}, "serverInfo": {"name": "Demo", "version": "1.0.0"}}
                }
                print(json.dumps(response, ensure_ascii=False), flush=True)
        except Exception as e:
            error_resp = {"jsonrpc": "2.0", "id": request.get("id", 1), "error": {"message": str(e)}}
            print(json.dumps(error_resp, ensure_ascii=False), flush=True)

if __name__ == "__main__":
    main()