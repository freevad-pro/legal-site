# Legal_site

Веб-приложение для проверки сайтов на соответствие законодательству РФ.

Подробности — в [docs/idea.md](docs/idea.md), [docs/vision.md](docs/vision.md), [docs/plan.md](docs/plan.md).

**Текущее состояние:** детерминированный движок (итерация 3 из 8). Сканер на Playwright + проверка по корпусу законов через CLI: `python -m app.scan <url>` → JSON с `Finding`'ами. На эталонном 152-ФЗ детектируются 8 из 9 нарушений. UI и HTTP-API — в следующих итерациях.

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

# 3. Установить Chromium для Playwright (один раз).
uv run playwright install chromium

# 4. Прогнать линтер и тесты — должно быть зелёное.
make lint
make test

# 5. Запустить dev-сервер. Команда блокирует терминал —
#    проверочный curl делаем во втором.
make dev
#   → второй терминал:
curl http://127.0.0.1:8000/health
#   → {"status":"ok"}
```

## CLI: сканирование сайта

```bash
# Из корня репозитория. URL можно без схемы — добавится https://.
uv run python -m app.scan example.ru > scan.json
# либо через Makefile:
make scan URL=example.ru
```

JSON `ScanResult` пишется в stdout, логи (в т.ч. WARNING на нереализованные
check-функции) — в stderr. Exit-code 0 — успешный скан (даже если findings
полно). 1 — невалидный URL / битый корпус. Сетевая ошибка scanner'а
фиксируется в поле `error` и выводится с кодом 0.

Для smoke-демо на синтетической «плохой» странице:

```powershell
# PowerShell
$srv = Start-Process -PassThru uv -ArgumentList `
  'run','python','-m','http.server','8765','--directory','tests/fixtures/html'
uv run python -m app.scan http://localhost:8765/bad-site.html > scan-demo.json
Stop-Process -Id $srv.Id
```

В выводе ожидаем 100 findings (по числу нарушений корпуса), из них минимум 5
со `status: "fail"` для `law_id: "152-fz"` (цель — 8).

## Команды

| Команда | Что делает |
|---|---|
| `make install` | Установить зависимости (`uv sync`) |
| `make dev` | Запустить FastAPI с автоперезагрузкой на `127.0.0.1:8000` |
| `make lint` | Прогнать `ruff check` + `mypy` (strict для `app/` и `tools/`) |
| `make fmt` | Отформатировать (`ruff format`) и автопочинить замечания (`ruff --fix`) |
| `make test` | Запустить `pytest` |
| `make corpus` | Пересобрать [docs/laws/index.yml](docs/laws/index.yml) + проверить целостность кросс-ссылок |
| `make scan URL=<url>` | Просканировать URL и напечатать JSON `ScanResult` в stdout |

## Структура

```
app/        — FastAPI приложение (точка входа: app.main:app)
tools/      — CLI-утилиты для работы с корпусом законов
docs/       — документация (vision, plan, ADR) и корпус законов (docs/laws/)
tests/      — pytest
```

## Дальше

Следующие итерации см. в [docs/plan.md](docs/plan.md). Для каждой итерации в работе или запланированной — отдельный tasklist в [docs/tasks/](docs/tasks/).
