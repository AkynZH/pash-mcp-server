# -*- coding: utf-8 -*-
"""
Главная точка входа standalone MCP-сервера (Phoenix Architecture).
Инициализирует FastMCP, загружает манифесты и динамически регистрирует инструменты с PASH-сжатием.
"""
import json
import logging
import sys
from pathlib import Path

# Добавляем корень проекта в sys.path для корректных импортов
sys.path.insert(0, str(Path(__file__).resolve().parent))

from mcp.server.fastmcp import FastMCP

from src.config import ServerConfig
from src.router import scan_manifests, launch_mcp_server, proxy_call
from src.compressor import AdaptivePashCompressor

# Инициализация логирования
config = ServerConfig()
logging.basicConfig(
    level=getattr(logging, config.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# Инициализация компонентов
mcp = FastMCP("Felix Standalone MCP")
compressor = AdaptivePashCompressor(min_size_threshold=config.pash_min_threshold)

# Хранилище запущенных процессов: { manifest_name: subprocess.Popen }
active_processes = {}


def get_or_start_process(manifest: dict):
    """Возвращает запущенный процесс или запускает новый."""
    name = manifest.get("name", "unknown")
    if name not in active_processes:
        process = launch_mcp_server(manifest)
        if process:
            active_processes[name] = process
        else:
            raise RuntimeError(f"Не удалось запустить MCP-сервер: {name}")
    return active_processes[name]


def create_tool_wrapper(manifest_name: str, tool_def: dict):
    """
    Фабрика функций для динамической регистрации инструментов в FastMCP.
    """
    tool_name = tool_def.get("name", "unknown_tool")
    tool_desc = tool_def.get("description", "No description provided.")

    # Проверяем, есть ли входные параметры
    input_schema = tool_def.get("inputSchema", {})
    properties = input_schema.get("properties", {})

    if properties:
        # Если есть параметры, используем **kwargs (упрощенно)
        def tool_wrapper(**kwargs):
            return _execute_tool(manifest_name, tool_name, kwargs)
    else:
        # Если параметров нет, создаем функцию без аргументов, чтобы FastMCP не требовал kwargs
        def tool_wrapper():
            return _execute_tool(manifest_name, tool_name, {})

    # Настраиваем метаданные функции для FastMCP
    tool_wrapper.__name__ = tool_name
    tool_wrapper.__doc__ = tool_desc

    return tool_wrapper


def _execute_tool(manifest_name: str, tool_name: str, kwargs: dict):
    """Реальная логика выполнения инструмента."""
    try:
        # Находим манифест по имени
        target_manifest = next(
            (m for m in registered_manifests if m.get("name") == manifest_name),
            None
        )
        if not target_manifest:
            return {"error": f"Манифест {manifest_name} не найден"}

        process = get_or_start_process(target_manifest)
        raw_result = proxy_call(process, tool_name, kwargs)

        # Применяем PASH-сжатие
        compressed_result = compressor.compress(raw_result)

        # Честные замеры размеров для демо-бенчмарков
        raw_str = json.dumps(raw_result, ensure_ascii=False) if not isinstance(raw_result, str) else raw_result
        pash_str = json.dumps(compressed_result["pash"], ensure_ascii=False) if not isinstance(compressed_result["pash"], str) else str(compressed_result["pash"])

        return {
            "raw_size_bytes": len(raw_str.encode('utf-8')),
            "pash_size_bytes": len(pash_str.encode('utf-8')),
            "pash_data": compressed_result["pash"],
            "raw_hash": compressed_result["raw_hash"],
            "compressed": compressed_result["compressed"]
        }
    except Exception as e:
        logger.error(f"Ошибка при выполнении инструмента {tool_name}: {e}")
        return {"error": str(e)}


# Глобальная переменная для хранения просканированных манифестов
registered_manifests = []


@mcp.tool()
def list_available_tools() -> list:
    """Возвращает список всех доступных инструментов из загруженных манифестов."""
    tools_list = []
    for manifest in registered_manifests:
        manifest_name = manifest.get("name", "unknown")
        for tool in manifest.get("tools", []):
            tools_list.append({
                "server": manifest_name,
                "name": tool.get("name"),
                "description": tool.get("description", "No description")
            })
    return tools_list


def setup_dynamic_tools():
    """Сканирует директорию и регистрирует все найденные инструменты."""
    global registered_manifests
    engines_dir = config.resolve_engines_dir()
    logger.info(f"Сканирование MCP-движков в: {engines_dir}")
    
    registered_manifests = scan_manifests(engines_dir)
    logger.info(f"Найдено {len(registered_manifests)} манифестов.")
    
    for manifest in registered_manifests:
        manifest_name = manifest.get("name", "unknown")
        tools = manifest.get("tools", [])
        
        for tool_def in tools:
            try:
                wrapper_func = create_tool_wrapper(manifest_name, tool_def)
                # Динамическая регистрация в FastMCP
                mcp.tool()(wrapper_func)
                logger.info(f"Зарегистрирован инструмент: {tool_def.get('name')} из {manifest_name}")
            except Exception as e:
                logger.error(f"Ошибка регистрации инструмента {tool_def.get('name')}: {e}")


if __name__ == "__main__":
    logger.info("Запуск Felix Standalone MCP Server (Phoenix Architecture)...")
    setup_dynamic_tools()
    logger.info("Сервер готов к работе в режиме stdio.")
    mcp.run(transport="stdio")