# Felix Standalone MCP Server

**Standalone MCP Server with PASH Compression (Phoenix Architecture)**

Этот проект представляет собой минимальный, production-ready Model Context Protocol (MCP) сервер, извлеченный из экосистемы Felix. Он разработан для предоставления внешних инструментов (Cursor, Claude Desktop и др.) с максимальной экономией токенов благодаря встроенному PASH-сжатию.

## Особенности (Phoenix Architecture)
- **Чистое ядро**: Никаких скрытых зависимостей от монолитной кодовой базы Феликса.
- **Динамическая регистрация**: Автоматическое сканирование директории `mcp_engines` и загрузка инструментов из `manifest.json`.
- **PASH Compression**: Интеллектуальное сжатие тяжелых JSON-ответов (экономия >80% токенов) с прозрачным возвратом хэша.
- **Zero-config запуск**: Работает через `stdio` с конфигурацией через `.env`.

## ⚠️ Безопасность и Runtime
Для разработчиков, вносящих изменения в серверную часть (`sse_server.py`, тесты): строго соблюдайте паттерн **[Surgical Process Cleanup by Port](docs/RUNTIME_SAFETY.md)**. Глобальное убийство процессов (`taskkill /IM`) категорически запрещено, так как оно обрывает агентскую сессию.

## Architecture Boundaries

**Felix MCP Standalone** is a self-contained product. It shares **principles, not code** with the internal Felix core (`C:\Users\53\Felix`).

- **Product Judge** (in `src/product_judge.py`) is an independent implementation of deterministic validation. It shares the principle of "structural validation before output" with the internal Mirror Forge Synthesis, but has zero shared code by design. This is intentional technical debt prevention.
- **Cognitive Loop and PASH compression** are implemented directly in this repository. They do not import from or depend on the internal Felix core. This ensures the product can be deployed, tested, and maintained independently.

**Why this matters:** When you install this package, you get a complete, autonomous system. No hidden dependencies on internal infrastructure.

## Установка

```bash
git clone https://github.com/AkynZH/pash-mcp-server.git
cd pash-mcp-server
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
pash-mcp-server/
├── server.py                  # Точка входа (FastMCP)
├── src/
│   ├── config.py              # Pydantic-конфигурация
│   ├── router.py              # Сканер и JSON-RPC прокси
│   └── compressor.py          # Ядро PASH-сжатия
├── config/
│   └── manifest.example.json  # Пример манифеста
└── tests/                     # Изолированные тесты
```

## Odysseus Integration Status

This repository serves as the cognitive core designed to be paired with an interface like Odysseus.
- ✅ **Completed & Shipped:** Cognitive Loop, PASH compression, Product Judge, and heuristic routing are fully implemented and tested.
- 🗺️ **Roadmap:** Native, one-click UI integration with the Odysseus agent (combining local reflexes with this cognitive core) is currently in active development. 

*We believe in shipping what works and clearly labeling what is being built.*

## Лицензия
MIT License (c) 2026 AkynZH