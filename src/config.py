# -*- coding: utf-8 -*-
"""
Конфигурация сервера.
Использует pydantic-settings для загрузки переменных окружения.
"""
import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class ServerConfig(BaseSettings):
    """Конфигурация standalone MCP сервера."""
    mcp_engines_dir: Path = Path("./mcp_engines")
    log_level: str = "INFO"
    pash_min_threshold: int = 500

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    def resolve_engines_dir(self) -> Path:
        """Возвращает абсолютный путь к директории MCP-движков."""
        if self.mcp_engines_dir.is_absolute():
            return self.mcp_engines_dir
        return Path(__file__).resolve().parent.parent / self.mcp_engines_dir