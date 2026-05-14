# Итерация 4 — API, аутентификация, отчёт PDF

> Tasklist для [docs/plan.md](../plan.md), карточка итерации 4.
> Статусы: 📋 → 🚧 → ✅. По завершении остаётся как исторический след.

## Контракт DoD (из `plan.md`)

- [x] `POST /api/v1/scans` создаёт скан, возвращает `scan_id`
- [x] `GET /api/v1/scans/{id}` отдаёт текущий статус + `ScanResult` по завершении
- [x] `GET /api/v1/scans/{id}/events` — SSE с буфером истории и live-потоком
- [x] `GET /api/v1/scans/{id}/report.pdf` — lazy-рендер WeasyPrint через `asyncio.to_thread`
- [x] HTTP Basic Auth защищает всё, кроме `/health`; пароли — bcrypt в SQLite
- [x] `tools/create_user.py` — CLI для создания/обновления пользователей
- [x] SQLite в режиме WAL, схема `users` (таблица `llm_cache` появится в итерации 7 — её рано создавать)
- [x] `asyncio.Semaphore(1)` ограничивает одновременные сканы
- [x] `asyncio.wait_for(timeout=300)` — общий таймаут скана
- [x] TTL для `ScanState` в памяти (1 час, очистка при обращении, не expire'им активные сканы)
- [x] Нормализация URL по правилам из vision (без схемы → `https://`, `http://` оставляем, валидация netloc)
- [x] End-to-end сценарий через `curl`: создать скан → получить SSE-события → скачать PDF

## Ключевые решения

- **Прогресс-события из engine — через sync-коллбэк.** `run_scan(..., *, on_event: Callable[[ScanEvent], None] | None = None)`. Engine публикует `scanner_started`, `scanner_done`, `violation_evaluated` (на каждый Finding), `done`. CLI продолжает работать без изменений (коллбэк не передаёт). Альтернативы (async-генератор, грубые шаги в API-обёртке) отклонены: первая ломает существующий API engine и тесты, вторая нарушает требование vision «каждый шаг публикуется в SSE».
- **`ScanEvent` живёт в `app/events.py`** — отдельный модуль ровно для разрыва цикла `app.engine` ↔ `app.scan_state`. Поле `payload: dict[str, Any]` (discriminated union — оверкилл для MVP, выделится в отдельную задачу, если фронт упрётся).
- **`CorpusBundle` — singleton в `app.state.corpus` через FastAPI lifespan.** Грузится один раз при старте, эндпоинты получают через `Depends`, тесты легко мокают. Альтернатива (модульный singleton в `app/corpus/__init__.py`) усложняет тесты и связывает время загрузки с импортом.
- **`normalize_url` переезжает в `app/url.py`** — общая для CLI и API. Тестов на эту функцию пока не было; создаём `tests/test_url.py` с нуля, покрытие веток (пустой, без схемы, `http://`, без точки, с портом).
- **SQLite через stdlib `sqlite3` + `asyncio.to_thread`.** Без `aiosqlite`. На границе async-кода — обёртка в thread, внутри — синхронные курсоры. Vision подразумевает именно этот подход.
- **SSE — собственный генератор поверх `asyncio.Queue`.** Без `sse-starlette`. Алгоритм:
  - если `state.status` уже терминальный (`done`/`failed`/`timeout`) — выдаём буфер `state.events` и закрываем стрим, **не подписываясь** на очередь;
  - иначе — буфер → `await queue.get()` в цикле → выход по sentinel (`None`) или событию `done`/`error`;
  - на выходе из цикла — `state.queues.remove(queue)`.
- **Таблица `llm_cache` НЕ создаётся.** Plan.md явно: появится в итерации 7. Защита от «случайно прописали в схему и забыли».
- **Хэширование паролей — `passlib[bcrypt]` 1.7.5+, `bcrypt` запинен `>=4.1,<5`.** Известная несовместимость passlib 1.7.4 ↔ bcrypt 4.x (`AttributeError: __about__`) лечится пинами обеих библиотек.
- **Шрифты в PDF — bundled DejaVu Sans/Mono в `app/report/fonts/`**, подключаются через `@font-face` с локальным `url(...)`. Никакого fallback на системные шрифты в основном `body` — иначе на минималистичном Linux-образе кириллица превратится в квадратики. DejaVu license = Public Domain + Bitstream Vera, ~2 МБ в репо — приемлемо.
- **Семафор и таймаут разнесены.** `async with semaphore` ожидание разрешения **не входит** в `asyncio.wait_for(timeout=300)` — иначе один долгий скан съест таймаут у следующего в очереди. Семафор — приоритет, таймаут — на саму работу.
- **TTL покрывает только терминальные состояния.** `ScanRegistry.purge_expired()` пропускает `pending`/`running` независимо от `last_accessed_at`. Защита от удаления активного скана из-за задержки между его созданием и подключением клиента.
- **Воркер различает три ошибочных исхода.** `TimeoutError` → статус `timeout`, любое необработанное исключение → `failed`, успешный `ScanResult` с непустым `error` (когда scanner упал на `ScanError`) → `failed`. В каждом случае публикуется финальное событие + `close_subscribers()`.

## Пошаговый план (по этапам)

> Этапы выполняются последовательно, но каждый этап независимо валидируется (`make lint && make test`). Финальный коммит — один на всю итерацию (по [feedback_one_commit_per_iteration](../../README.md) — promejutочных не делаем).

1. **URL-утилита и каркас config.** `app/url.py` (перенос `normalize_url`), импорт в `app/scan.py`, расширение `app/config.py` (`database_path`, `basic_auth_realm`, `api_scan_timeout_seconds=300`, `scan_state_ttl_seconds=3600`), обновление `.env.example`, новый `tests/test_url.py`.
2. **SQLite и Basic Auth.** `app/db.py` (`init_db` с WAL + `CREATE TABLE users`), `app/auth.py` (`HTTPBasic` + `verify_password` через passlib, `get_current_user` как Depends, корректный `WWW-Authenticate: Basic realm="…"` на 401). Таблицу `llm_cache` **не создаём**. `tests/test_auth.py` с временной БД.
3. **CLI создания пользователя.** `tools/create_user.py` (login arg, `getpass` для пароля, bcrypt, `INSERT … ON CONFLICT(login) DO UPDATE`). Цель `make user LOGIN=<login>` в `Makefile`. Покрытие в `tests/test_auth.py`.
4. **ScanEvent, ScanState, ScanRegistry, воркер.** `app/events.py` (frozen `ScanEvent`), `app/scan_state.py` (`ScanState.publish`, `close_subscribers`, `ScanRegistry.purge_expired` с защитой активных), `app/api/scan_worker.py` (`run_scan_job` с тремя ветками исхода, см. «Ключевые решения»). `tests/test_scan_state.py` на registry + TTL.
5. **Engine — коллбэк прогресса.** Расширить `app/engine.py:run_scan` keyword-only параметром `on_event: Callable[[ScanEvent], None] | None = None`. Публиковать `scanner_done` (только при успехе scanner), `violation_evaluated` (на каждый Finding в цикле), `error` (при `ScanError`, без `scanner_done`). CLI `app/scan.py` остаётся без правок. Дополнить `tests/test_engine.py` сценарием с собирающим коллбэком.
6. **API: эндпоинты `/api/v1/scans`.** `app/api/scan.py`:
   - `POST /api/v1/scans` (Pydantic body `{url: str}`, валидация через `normalize_url` с 422 на битый ввод, создание `ScanState`, запуск `asyncio.create_task(run_scan_job(...))`, ответ `{scan_id}` со статусом 202);
   - `GET /api/v1/scans/{id}` (резюме ScanState; 404 при отсутствии/истекшем TTL);
   - `GET /api/v1/scans/{id}/events` (SSE-алгоритм из «Ключевых решений»).
   - Lifespan в `app/main.py`: `init_db(...)` → `app.state.corpus = load_corpus(...)` → `app.state.scan_registry = ScanRegistry()` → `app.state.scan_semaphore = asyncio.Semaphore(1)` → фон-таска очистки TTL → корректный shutdown.
   - Все три эндпоинта за `Depends(get_current_user)`. `/health` остаётся без auth.
   - `tests/test_api_scans.py` через `pytest-asyncio` + мок `run_scan` (через `monkeypatch`); сценарий «подписка после `done`» обязателен.
7. **PDF-отчёт.** `app/report/renderer.py` (`render_pdf` через `asyncio.to_thread`), `app/report/templates/report.html.j2` (`@font-face` + `body { font-family: "ReportSans" }`, секции по severity, evidence моноширинно), bundle `app/report/fonts/DejaVuSans.ttf` + `DejaVuSans-Bold.ttf` + `DejaVuSansMono.ttf`. Эндпоинт `GET /api/v1/scans/{id}/report.pdf` (`Content-Disposition: attachment; filename="legal-audit-<host>-<date>.pdf"`, 409 если `status != "done"`). `tests/test_report.py` с русским заголовком из `docs/laws/152-fz-personal-data.md`: проверки `%PDF-` сигнатуры + упоминания `DejaVu` в выходных байтах + базовый размер.
8. **Зависимости и инструментарий.** `pyproject.toml`: в `dependencies` — `passlib[bcrypt]>=1.7.5`, `bcrypt>=4.1,<5`, `weasyprint>=63`, `jinja2>=3.1`; в `dev` — `pytest-asyncio>=0.24`; `tool.mypy.overrides` для `weasyprint`, `passlib.*` (`ignore_missing_imports = true`). `Makefile` — цель `user`, `.PHONY` обновлён. `prompts/README.md` — однострочный плейсхолдер. `uv.lock` пересобирается `make install`.
9. **Финальная сверка и e2e.** `make lint && make test && make corpus` зелёные. E2E curl-сценарий (см. Verification). Перевод статуса итерации в [plan.md](../plan.md) `🚧 → ✅`, заполнение «Демо (по факту)». Попутно — правка опечатки [plan.md:184](../plan.md#L184) «итерация 6» → «итерация 7».

## Fallback

- **WeasyPrint на Windows-dev не запускается** (нет Pango/GTK runtime). Это не блокер: продакшен крутится в Docker на `mcr.microsoft.com/playwright/python:v1.49.0-noble`, где Pango ставится `apt-get install libpango-1.0-0 libpangoft2-1.0-0`. На Windows-dev допустим прогон `tests/test_report.py` под WSL/Docker. В CI/Docker этот тест должен проходить безусловно. При первом запуске рендера на Windows — не считать сбой багом, проверить наличие GTK3-runtime.
- **passlib падает с `AttributeError: __about__`** — индикатор того, что bcrypt 5.x всё-таки подтянулся. Лечится `uv lock --upgrade-package bcrypt` после правки пинов в `pyproject.toml`.
- **SSE не доходит до клиента в `tests/test_api_scans.py`** при использовании `TestClient` (Starlette synchronous client иногда буферизует). Fallback — `httpx.AsyncClient(transport=ASGITransport(app=app))` с явным `stream=True`.
- **WeasyPrint выбирает не bundle'нутый шрифт.** Признак — отсутствие `DejaVu` в байтах PDF в тесте. Лечится: убедиться, что `base_url=str(templates_dir)` передан в `HTML(...)`, и `@font-face url(...)` указывает относительный путь, реально существующий в FS.
- **`asyncio.Semaphore(1)` в FastAPI lifespan теряется при reload.** Признак — после `--reload` второй POST не ждёт первого. Это нормальный артефакт dev-режима; проверять механику на production-запуске `uvicorn` без `--reload`.

## Verification (демо)

```bash
make install
uv run playwright install chromium     # уже стоит с итерации 3, на всякий случай
make corpus                            # sanity: 15 законов, 100 нарушений
make lint                              # ruff + mypy strict
make test                              # все тесты зелёные, включая новые API/SSE/PDF
make user LOGIN=demo                   # интерактивный ввод пароля
make dev                               # FastAPI на 127.0.0.1:8000
```

В другом терминале:

```bash
# 1. Создать скан (Basic Auth обязателен)
curl -u demo:<pwd> -X POST http://127.0.0.1:8000/api/v1/scans \
     -H 'content-type: application/json' \
     -d '{"url":"example.ru"}'
# → 202 {"scan_id":"<uuid>"}

# 2. Подписаться на SSE-прогресс
curl -u demo:<pwd> -N http://127.0.0.1:8000/api/v1/scans/<uuid>/events
# → буфер истории + live-стрим до события done/error

# 3. Получить резюме результата
curl -u demo:<pwd> http://127.0.0.1:8000/api/v1/scans/<uuid>
# → {status: "done", result: {…}}

# 4. Скачать PDF
curl -u demo:<pwd> -o report.pdf http://127.0.0.1:8000/api/v1/scans/<uuid>/report.pdf
# → файл legal-audit-example.ru-YYYY-MM-DD.pdf, открывается, кириллица читается
```

**Контрольные точки:**
- POST без auth → 401 с `WWW-Authenticate: Basic realm="Legal_site"`.
- POST с битым URL (`"example"`) → 422.
- SSE: первое событие — `scanner_started`, последнее — `done` (или `error`).
- При повторной подписке на уже завершённый скан — стрим отдаёт буфер истории и закрывается.
- PDF: `file report.pdf` → `PDF document`, открытие в reader'е — русские заголовки и evidence читаются корректно.
- `GET /api/v1/scans/<uuid>/report.pdf` для `status != "done"` → 409.
- Параллельный второй POST: воркер ждёт первый под семафором, оба завершаются корректно.

## По ходу выполнения

### Обновление vision.md: passlib → bcrypt напрямую

Tasklist опирался на формулировку vision'а («`passlib[bcrypt]` — хэширование паролей»). При установке выяснилось, что `passlib` застрял на 1.7.4 (последний релиз — 2020) и несовместим с современным bcrypt 4.x (`AttributeError: __about__`). Pin `passlib[bcrypt]>=1.7.5` нерезолвится — такой версии не существует.

Решение: использовать `bcrypt>=4.1,<5` напрямую — `bcrypt.hashpw()` / `bcrypt.checkpw()`. API чище, активно обновляется, тот же алгоритм. По правилу «план живой» обновлена соответствующая строка [docs/vision.md](../vision.md#L15) — фиксирует реальный стек, а не устаревший. Возврат к passlib был бы шагом назад: на момент итерации 7 (LLM) и итерации 8 (Docker) проблема всё равно вышла бы.

### Bugfix: normalize_url для `host:port` без схемы

Vision описывает поведение «без схемы → префиксуем `https://`» как универсальное. До фикса `localhost:8000` / `example.ru:8080` падал в `ValueError`: `urlparse` трактовал `example.ru` как scheme (RFC 3986 разрешает алфанум с `.` в схеме), `netloc` оказывался пустым. Добавлен whitelist `{http, https}` — если scheme другая, считаем, что её нет. Это **bugfix, приводящий код в соответствие с vision**, а не отклонение от плана.

### Технические нюансы реализации

- **WeasyPrint импортируется лениво в `_render_sync`.** На Windows без GTK3-runtime импорт `weasyprint` падает с `OSError` ещё на module-level — без ленивого импорта ломается collection ВСЕХ тестов через цепочку `app.main → app.api.scan → app.report.renderer`. Тесты `test_render_pdf_*` помечены `@pytest.mark.skipif` на отсутствие WeasyPrint; тест `test_render_pdf_contains_cyrillic_title` (только Jinja) проходит безусловно. В Docker (`mcr.microsoft.com/playwright/python:v1.49.0-noble` + `libpango-1.0-0`) все PDF-тесты должны проходить.
- **`pytest-asyncio` в `asyncio_mode = "auto"`** настроено в `[tool.pytest.ini_options]`, чтобы async-тесты API запускались без `@pytest.mark.asyncio` на каждом.

## Демо (по факту)

Прогон 2026-05-14 на Windows (Python 3.12.11, uv 0.8.13):

```
make install                  → 17 новых пакетов (bcrypt, weasyprint, jinja2, pytest-asyncio, ...)
make lint                     → ruff All checks passed + mypy 25 source files OK
make test                     → 114 passed, 2 skipped (PDF native deps)
make corpus                   → 15 законов, 100 нарушений, integrity OK
uv run python -m tools.create_user --help → CLI работает, help печатается
uv run python -m app.scan --help          → CLI движка не сломан рефакторингом
```

Покрытие тестами по слоям:
- `tests/test_url.py` — 14 кейсов нормализации URL.
- `tests/test_auth.py` — 8 кейсов: WAL-init, upsert, bcrypt round-trip, 401 (no creds / wrong pw / unknown user), `WWW-Authenticate` header.
- `tests/test_scan_state.py` — 10 кейсов: registry create/get, purge **не убивает** pending/running, publish в буфер+очередь, close_subscribers, is_terminal.
- `tests/test_engine.py` — 6 кейсов (включая 2 новых): on_event публикует scanner_done + violation_evaluated по порядку, scanner_error → error без scanner_done.
- `tests/test_api_scans.py` — 6 кейсов: 401 без auth, 422 на битый URL, POST → GET (status="done"), 404 на unknown, SSE-replay после `done`, 401 на SSE без auth.
- `tests/test_report.py` — 1 + 2 skipped: cyrillic-в-HTML проходит, PDF-генерация и `DejaVu`-в-байтах skip из-за отсутствия GTK runtime.

Итерация закрыта пользователем после ручного e2e-прохода (см. «Verification (демо)»); статус в `plan.md` переведён в `✅ Done`.

## Открытое (по плану итерации, без изменений)

- **Discriminated union для `ScanEvent.payload`** — отложено до итерации 6, если фронт упрётся в `dict[str, Any]`.
- **Last-Event-ID при реконнекте SSE** — не реализуем; клиент при реконнекте получает весь буфер истории.
- **Per-violation прогресс внутри `scanner.collect()`** — Playwright собирает артефакты атомарно, разбивать его на под-шаги не задача итерации 4.
- **Кэш PDF на диск** — vision требует lazy-рендер на каждый GET, без кэша.
- **Скриншоты в evidence для PDF** — отдельный пункт (упомянут в «Открытое» итерации 3), переезжает в более поздние итерации, когда понадобится визуальное подтверждение.
- **Cleanup voucher для зависших `running`-сканов** (если воркер таски умер незаметно) — потенциальная улучшалка, но в MVP не требуется: `Semaphore(1)` и единственный процесс гарантируют, что одновременно может быть максимум один `running`.
