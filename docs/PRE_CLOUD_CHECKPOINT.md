# PRE-CLOUD CHECKPOINT

## Подтверждённые коммиты
- 24bcf250707accc33f747c1ce6ffb454b8c2eec1
- 5069cff9d816ac4916ff316d3ea5c798e74a86e8

## Доказано локально
- `/api/qwen/connect` = 200
- qwen session created
- workspace correct
- `/api/push_qwen` = 200
- prompt enqueued
- no `taskkill /IM`
- safe `server_proc` terminate/kill (only own child process)

## ЕЩЁ НЕ доказано
- Qwen full response capture
- `/api/qwen_stream` stable response
- `FELIX_QWEN_OK` received
- UI live event rendering

## Следующий первый тест на облаке
- `run test_qwen_message.py refined version`

## Строгие запреты (STRICT BANS)
- no `taskkill /IM`
- no global `node`/`python`/`qwen`/`uvicorn` kill
- only surgical cleanup by port
- no `git add .`
- no `.env` commit

## Неотслеживаемые черновики (Untracked drafts)
- `brainstorm_intercept.py`
- `test_direct_sse.py`
- `test_e2e_sse.py`
- `test_qwen_message.py`

## Рекомендация
`test_qwen_message.py` пока считать diagnostic partial smoke test, не production test.
