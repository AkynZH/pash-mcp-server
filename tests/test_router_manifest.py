# -*- coding: utf-8 -*-
import pytest
import sys
import os
import json
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.router import scan_manifests, launch_mcp_server

def test_scan_manifests_reads_valid_json():
    """Проверка, что сканер корректно находит и парсит manifest.json."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Создаем фейковый manifest.json
        manifest_path = Path(tmpdir) / "mcp_server" / "manifest.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        
        test_data = {
            "name": "test_server",
            "command": ["python", "server.py"],
            "tools": [{"name": "test_tool"}]
        }
        
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(test_data, f)
            
        manifests = scan_manifests(Path(tmpdir))
        
        assert len(manifests) == 1
        assert manifests[0]["name"] == "test_server"
        assert manifests[0]["_source_path"] == str(manifest_path)


def test_scan_manifests_ignores_invalid_json():
    """Проверка, что сканер не падает на битых JSON-файлах."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manifest_path = Path(tmpdir) / "manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            f.write("{ invalid json }")
            
        manifests = scan_manifests(Path(tmpdir))
        assert len(manifests) == 0


def test_launch_mcp_server_handles_missing_command():
    """Проверка, что запуск возвращает None при отсутствии команды."""
    manifest = {"name": "broken_server"}
    process = launch_mcp_server(manifest)
    assert process is None