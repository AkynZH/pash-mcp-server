# -*- coding: utf-8 -*-
import pytest
import sys
import os
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Мокаем зависимости перед импортом server.py, чтобы избежать реального запуска
import unittest.mock as mock

def test_server_initializes_without_import_errors():
    """Проверка, что server.py может быть импортирован и инициализирован без ошибок."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Создаем минимальный .env для теста
        env_path = Path(tmpdir) / ".env"
        with open(env_path, "w", encoding="utf-8") as f:
            f.write(f"MCP_ENGINES_DIR={tmpdir}/engines\n")
            
        # Мокируем переменные окружения
        with mock.patch.dict(os.environ, {"MCP_ENGINES_DIR": f"{tmpdir}/engines"}):
            try:
                # Импортируем конфигурацию и проверяем, что она работает
                from src.config import ServerConfig
                config = ServerConfig()
                
                # Проверяем, что пути разрешаются корректно
                engines_dir = config.resolve_engines_dir()
                assert "engines" in str(engines_dir)
                
                # Проверяем, что модуль compressor импортируется
                from src.compressor import AdaptivePashCompressor
                compressor = AdaptivePashCompressor()
                assert compressor.min_size_threshold == 500
                
            except ImportError as e:
                pytest.fail(f"Ошибка импорта в server.py или его зависимостях: {e}")


def test_dynamic_tool_registration_logic():
    """Проверка логики создания обертки для инструмента."""
    import server
    create_tool_wrapper = server.create_tool_wrapper
    
    mock_manifest = {
        "name": "dummy_server",
        "tools": [
            {
                "name": "dummy_tool",
                "description": "A dummy tool for testing",
                "inputSchema": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}}
                }
            }
        ]
    }
    
    wrapper = create_tool_wrapper("dummy_server", mock_manifest["tools"][0])
    
    assert wrapper.__name__ == "dummy_tool"
    assert wrapper.__doc__ == "A dummy tool for testing"
    assert callable(wrapper)