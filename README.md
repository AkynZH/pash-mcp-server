# Felix Standalone MCP Server

**Standalone MCP Server with PASH Compression (Phoenix Architecture)**

Этот проект представляет собой минимальный, production-ready Model Context Protocol (MCP) сервер, извлеченный из экосистемы Felix. Он разработан для предоставления внешних инструментов (Cursor, Claude Desktop и др.) с максимальной экономией токенов благодаря встроенному PASH-сжатию.

## Особенности (Phoenix Architecture)
- **Чистое ядро**: Никаких скрытых зависимостей от монолитной кодовой базы Феликса.
- **Динамическая регистрация**: Автоматическое сканирование директории `mcp_engines` и загрузка инструментов из `manifest.json`.
- **PASH Compression**: Интеллектуальное сжатие тяжелых JSON-ответов (экономия >80% токенов) с прозрачным возвратом хэша.
- **Zero-config запуск**: Работает через `stdio` с конфигурацией через `.env`.

## Установка

```bash
git clone https://github.com/AkynZH/felix-mcp-standalone.git
cd felix-mcp-standalone
pip install -e .
```

## Конфигурация

Скопируйте `.env.example` в `.env` и настройте пути:

```env
MCP_ENGINES_DIR=./mcp_engines
LOG_LEVEL=INFO
PASH_MIN_THRESHOLD=500
```

Создайте директорию `mcp_engines` и поместите в неё подпапки с `manifest.json` и исполняемыми файлами ваших MCP-серверов.

## Запуск

```bash
python server.py
```

Сервер запустится в режиме `stdio` и будет готов к подключению через совместимые клиенты (например, Claude Desktop).

## Структура проекта
```
felix-mcp-standalone/
├── server.py                  # Точка входа (FastMCP)
├── src/
│   ├── config.py              # Pydantic-конфигурация
│   ├── router.py              # Сканер и JSON-RPC прокси
│   └── compressor.py          # Ядро PASH-сжатия
├── config/
│   └── manifest.example.json  # Пример манифеста
└── tests/                     # Изолированные тесты
```

## Лицензия
MIT License (c) 2026 AkynZH