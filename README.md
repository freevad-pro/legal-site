# Legal_site

Веб-приложение для проверки сайтов на соответствие законодательству РФ.

Подробности — в [docs/idea.md](docs/idea.md), [docs/vision.md](docs/vision.md), [docs/plan.md](docs/plan.md).

**Текущее состояние:** каркас (итерация 2 из 8). Поднят FastAPI с `GET /health`, разработческая среда работает. Реальный сканер сайтов и UI — в следующих итерациях.

## Как поднять локально

Требуется:
- [uv](https://docs.astral.sh/uv/) — управляет Python и зависимостями (Python 3.12 поставит сам по `.python-version`).
- GNU Make — на Linux/macOS уже есть; на Windows — через WSL или `choco install make`.

```bash
# 1. Скопировать пример конфигурации (секретов в .env пока нет, можно оставить как есть).
#    POSIX:        cp .env.example .env
#    PowerShell:   Copy-Item .env.example .env

# 2. Установить зависимости и собрать индекс корпуса (sanity-check, что всё на месте).
make install
make corpus

# 3. Прогнать линтер и тесты — должно быть зелёное.
make lint
make test

# 4. Запустить dev-сервер. Команда блокирует терминал —
#    проверочный curl делаем во втором.
make dev
#   → второй терминал:
curl http://127.0.0.1:8000/health
#   → {"status":"ok"}
```

## Команды

| Команда | Что делает |
|---|---|
| `make install` | Установить зависимости (`uv sync`) |
| `make dev` | Запустить FastAPI с автоперезагрузкой на `127.0.0.1:8000` |
| `make lint` | Прогнать `ruff check` + `mypy` (strict для `app/` и `tools/`) |
| `make fmt` | Отформатировать (`ruff format`) и автопочинить замечания (`ruff --fix`) |
| `make test` | Запустить `pytest` |
| `make corpus` | Пересобрать [docs/laws/index.yml](docs/laws/index.yml) + проверить целостность кросс-ссылок |

## Структура

```
app/        — FastAPI приложение (точка входа: app.main:app)
tools/      — CLI-утилиты для работы с корпусом законов
docs/       — документация (vision, plan, ADR) и корпус законов (docs/laws/)
tests/      — pytest
```

## Дальше

Следующие итерации см. в [docs/plan.md](docs/plan.md). Для каждой итерации в работе или запланированной — отдельный tasklist в [docs/tasks/](docs/tasks/).
