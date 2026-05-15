# Legal_site

Веб-приложение для проверки сайтов на соответствие законодательству РФ.

Подробности — в [docs/idea.md](docs/idea.md), [docs/vision.md](docs/vision.md), [docs/plan.md](docs/plan.md).

**Текущее состояние:** закрыты итерации 0–5а — корпус законов, детерминированный движок, HTTP-API + SSE + PDF, дизайн UI, cookie-сессии. В работе — итерация 6 (Frontend MVP). Дальше — 7 (LLM), 8 (Deploy). Подробности — [docs/plan.md](docs/plan.md).

## Доступ

- **Бесплатно, без входа:** базовая проверка с детерминированными правилами корпуса. Доступна любому посетителю на любой URL, ограничений на количество запусков нет.
- **Расширенный анализ (после входа):** семантические проверки через автоматический анализ текста (читаемость политики, корректность согласия, dark pattern в баннере и т. п.) — для авторизованного владельца. Аккаунт создаётся локально командой `make user LOGIN=<имя>`, дальше вход — формой на сайте.

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

# 6. (опционально) Создать пользователя для расширенного анализа.
#    Нужен только если планируется тестировать LLM-проверки локально.
make user LOGIN=demo
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
| `make build-frontend` | Собрать фронт (Next.js → `frontend/out/`); FastAPI отдаст его как StaticFiles при следующем `make dev` |
| `make dev-frontend` | Поднять dev-сервер фронта на `localhost:3000` (с hot-reload, ходит на API через `NEXT_PUBLIC_API_BASE=http://localhost:8000`) |

## Frontend — локальная разработка

Фронт лежит в [frontend/](frontend) (Next.js 15 + Tailwind, статический экспорт). В **production** он собран в `frontend/out/` и отдаётся FastAPI как `StaticFiles` под `/` — один порт `8000`, без CORS:

```bash
make build-frontend   # один раз — собрать статику
make dev              # FastAPI + статика на :8000
```

В **dev**-режиме фронт работает на отдельном порту `:3000` через `pnpm dev` с hot-reload. Cookie-сессии работают через CORS — для `http://localhost:3000` он включён автоматически, когда `SESSION_COOKIE_SECURE=false`:

```bash
# Терминал 1: бэк
make dev

# Терминал 2: фронт
make dev-frontend
# → http://localhost:3000
```

`pnpm` ставится один раз: `npm install -g pnpm@9.15.4` (на Node 20.x). На Node 22+ — последний pnpm подходит.

## PDF-отчёт: системные зависимости

PDF собирается WeasyPrint, которому нужны системные библиотеки **GTK / Pango / Cairo**.

**Linux / Docker (production):**

```bash
apt-get install -y libpango-1.0-0 libpangoft2-1.0-0
```

После этого PDF работает «из коробки» — обычно ставится в Dockerfile один раз.

**Windows (локальная разработка):**

Без GTK runtime endpoint `/report.pdf` будет возвращать `503` (UI покажет понятный диалог со ссылкой). Чтобы PDF заработал локально:

1. Скачать установщик: <https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases/latest> (~30&nbsp;МБ).
2. В мастере установки отметить «Set up PATH environment variable to include GTK+».
3. Перезапустить терминал и `make dev`.

Если PDF локально не нужен — можно работать без GTK; кнопка «PDF» подскажет, что и как поставить.

## Структура

```
app/        — FastAPI приложение (точка входа: app.main:app)
frontend/   — Next.js 15 + Tailwind (UI); собирается в frontend/out/
tools/      — CLI-утилиты для работы с корпусом законов
docs/       — документация (vision, plan, ADR) и корпус законов (docs/laws/)
tests/      — pytest
```

## Дальше

Следующие итерации см. в [docs/plan.md](docs/plan.md). Для каждой итерации в работе или запланированной — отдельный tasklist в [docs/tasks/](docs/tasks/).
