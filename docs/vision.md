# Техническое видение проекта Legal_site

Документ описывает технические решения для веб-приложения по проверке сайтов на соответствие законодательству РФ. Опирается на [docs/idea.md](idea.md), [docs/research.md](research.md) и [docs/adr/0001-laws-reference-structure.md](adr/0001-laws-reference-structure.md).

## Технологии

### Backend
- **Python 3.12+**
- **FastAPI** — HTTP API + SSE для прогресса сканирования
- **Playwright (Python)** — headless-обход страниц проверяемого сайта
- **python-frontmatter** + **Pydantic v2** — парсинг и валидация корпуса законов из `docs/laws/`
- **WeasyPrint** + **Jinja2** — генерация PDF-отчёта
- **SQLite** (через стандартный `sqlite3`) — кэш LLM-ответов и таблица пользователей
- **httpx** — HTTP-клиент к GigaChat
- **passlib[bcrypt]** — хэширование паролей

### Frontend
- **Next.js 15** (App Router) + **TypeScript**, экспорт в статику (`output: 'export'`) — кладётся рядом с бэком, без отдельного Node-рантайма
- **Tailwind CSS**
- Нативный `EventSource` для приёма SSE — без отдельной либы

### LLM
- **GigaChat API** (платный тариф) — primary
- **YandexGPT** — фоллбек через тот же интерфейс `LLMProvider`

### Аутентификация
- **HTTP Basic Auth** через встроенный `HTTPBasic` FastAPI — браузер сам показывает нативное окно ввода
- Пользователи в SQLite: `users(login TEXT PRIMARY KEY, password_hash TEXT)`, пароли — bcrypt
- Регистрации нет. Создание пользователя — CLI: `uv run python tools/create_user.py <login>` (пароль запрашивается интерактивно, в БД попадает только хэш)
- Защищены все эндпоинты, кроме `/health`
- В MVP — 1–2 пользователя, заводятся вручную владельцем

### Управление зависимостями и окружением
- **Backend:** `uv` — единый инструмент для виртуального окружения и зависимостей. `pyproject.toml` + `uv.lock`, виртуальное окружение `.venv/` в корне
- **Frontend:** `pnpm` — `package.json` + `pnpm-lock.yaml`

### Сборка
- **Backend:** `uv sync` → зависимости; `uv run uvicorn app.main:app` → запуск. Отдельного шага сборки нет
- **Frontend:** `pnpm build` с `output: 'export'` → статический бандл в `frontend/out/`. FastAPI отдаёт его как статику через `StaticFiles`. Одно приложение, одна точка входа
- **Корпус:** `uv run python tools/rebuild_index.py` пересобирает `docs/laws/index.yml` и одновременно валидирует целостность кросс-ссылок (`related`, `references_in_common`)

### Docker
- **Один Dockerfile**, multi-stage:
  1. Стадия `frontend-build` — Node-образ, `pnpm install && pnpm build`
  2. Стадия `runtime` — `mcr.microsoft.com/playwright/python:v1.49.0-noble` (Chromium и системные библиотеки уже стоят), `uv sync`, копируем код + собранный фронт
- **Без docker-compose** — один контейнер, нечего оркестрировать
- **Без registry** — на VPS делаем `git pull && docker build && docker run`
- **SQLite — volume на хост** (`/var/lib/legal_site/db.sqlite`), чтобы пользователи и кэш переживали пересборку контейнера
- **Локальная разработка — без Docker.** `uv run` напрямую, Playwright ставится локально один раз. Docker — только для прода

### Хостинг
- **Beget VPS**, тариф 1 vCPU / 2 ГБ RAM / 15 ГБ NVMe — **510 ₽/мес**. RAM хватает на Chromium без swap-трюков, диск с запасом ~7–8 ГБ под Docker-образ Playwright и обновления
- **HTTPS** — Let's Encrypt через `certbot` на хосте перед контейнером
- **Домен** — технический поддомен от Beget на этапе разработки; свой домен опционально (~200 ₽/год у любого регистратора)
- **Паттерн «развернул-попользовался-удалил»** работает: удаляем VPS — биллинг прекращается; при необходимости — `git clone && docker build && docker run` за ~30 минут. Гранулярность месячная (не почасовая, как у Timeweb Cloud), но это сильно дешевле при удержании дольше пары дней

### Качество кода
- **ruff** — линтер и форматтер для Python (заменяет flake8 + black + isort)
- **mypy** — статическая типизация для `app/` и `tools/`, не для тестов
- **pytest** — unit-тесты движка проверки и парсера корпуса

### Чего сознательно НЕТ
- Celery / ARQ / Redis — один процесс FastAPI с async-задачами
- Postgres — только локальный SQLite
- Регистрация пользователей, OAuth, JWT, восстановление пароля — Basic Auth + ручное создание
- docker-compose, отдельные контейнеры на nginx/БД, приватный registry
- Раздельный деплой фронта и бэка — всё на одной VPS под одним доменом
- Локальный Saiga / Ollama как LLM-фоллбек — только облачные GigaChat/YandexGPT

## Принципы разработки

1. **KISS — операционный фильтр.** Перед каждой абстракцией/слоем/новым файлом спрашиваем: «нужно сейчас или может пригодиться?». Если «может пригодиться» — не добавляем.
2. **Корпус законов — единственный источник правды о праве.** Никаких знаний о законах, статьях, штрафах в коде Python. Только парсинг `docs/laws/`. Бизнес-логика «есть ли в политике X» — это check-функция в реестре, а не `if` в движке.
3. **Сначала детерминированный сигнал, LLM — только если иначе нельзя.** Для каждого нарушения сначала пытаемся закрыть `page_signals`/`site_signals`. LLM — только для семантики, которую сигналом физически не описать.
4. **Явная неопределённость лучше тихого «pass».** Любая невозможность проверить (LLM-ответ невалидный JSON, страница не загрузилась, превышен бюджет токенов, таймаут) → статус `inconclusive` в отчёте. Никогда не «pass по умолчанию».
5. **Ошибки — наверх, не глушим.** Никаких широких `try: ... except: pass`. Ловим только конкретные исключения там, где знаем что делать. Всё остальное — в логи + 500 пользователю.
6. **Минимум persistence.** В памяти: загруженный корпус, состояние текущего скана. На диске (SQLite): только кэш LLM-ответов и таблица users. Результаты проверок не сохраняются — это явное решение из идеи.
7. **Тесты — на движок и парсер, не на всё подряд.** pytest покрывает: парсер корпуса, реестр check-функций, нормализацию контента для LLM-кэша. НЕ покрывает: FastAPI-ручки, вёрстку отчёта, Playwright-сценарии.
8. **Type hints везде, mypy строгий.** Особенно для моделей корпуса, интерфейса `LLMProvider` и результатов проверок. На тестах — не настаиваем.

## Структура репозитория

```
Legal_site/
├── .gitignore
├── .env.example                   # пример конфигурации (без секретов)
├── pyproject.toml                 # uv-managed Python deps
├── uv.lock
├── README.md
├── Makefile                       # частые команды: install, dev, lint, test, corpus, docker-*
├── Dockerfile                     # multi-stage: frontend build + runtime
├── .dockerignore
│
├── app/                           # Python backend
│   ├── __init__.py
│   ├── main.py                    # FastAPI entry, регистрация роутов, монтаж статики
│   ├── config.py                  # Pydantic Settings — переменные окружения
│   ├── db.py                      # SQLite: init, схема (users, llm_cache)
│   ├── auth.py                    # HTTPBasic + bcrypt
│   ├── api/
│   │   ├── __init__.py
│   │   ├── scan.py                # POST /scan, GET /scan/{id}/events (SSE), GET /scan/{id}/report.pdf
│   │   └── health.py              # GET /health
│   ├── corpus/
│   │   ├── __init__.py
│   │   ├── models.py              # Pydantic-модели схемы docs/laws/
│   │   └── loader.py              # парсинг и валидация корпуса
│   ├── scanner.py                 # Playwright: сбор артефактов сайта (DOM, cookies, headers, network)
│   ├── checks.py                  # реализации check-функций + реестр {name → callable}
│   ├── engine.py                  # оркестратор: scanner → проход по сигналам → нормализованный результат
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── base.py                # интерфейс LLMProvider + StructuredAnswer
│   │   ├── gigachat.py
│   │   ├── yandex.py
│   │   └── cache.py               # SQLite-кэш по sha256(prompt+content)
│   └── report/
│       ├── __init__.py
│       ├── renderer.py            # WeasyPrint + Jinja2
│       └── templates/
│           └── report.html.j2
│
├── tools/                         # CLI-утилиты
│   ├── create_user.py             # создать/обновить пользователя
│   ├── rebuild_index.py           # пересобрать docs/laws/index.yml + проверить целостность
│   └── show_verification_notes.py # вывести открытые TODO из verification_notes по корпусу
│
├── prompts/                       # LLM-промпты, версионируются с кодом
│   └── *.md                       # каждый — отдельный файл с frontmatter
│
├── tests/                         # pytest, плоская структура
│   ├── conftest.py
│   ├── test_corpus_loader.py
│   ├── test_checks.py
│   └── test_engine.py
│
├── frontend/                      # Next.js + Tailwind
│   ├── package.json
│   ├── pnpm-lock.yaml
│   ├── next.config.mjs            # output: 'export'
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   └── src/
│       ├── app/
│       │   ├── layout.tsx
│       │   ├── page.tsx           # главная: инпут URL + анимация + результат
│       │   └── globals.css
│       └── components/
│           ├── ScanForm.tsx
│           ├── ScanProgress.tsx
│           └── ScanResult.tsx
│
└── docs/                          # документация и корпус
    ├── idea.md
    ├── vision.md
    ├── research.md
    ├── adr/
    │   ├── README.md
    │   └── 0001-laws-reference-structure.md
    └── laws/
        ├── README.md
        ├── schema.md
        ├── index.yml              # генерируется tools/rebuild_index.py
        ├── 152-fz-personal-data.md
        ├── ...
        └── common/
            ├── koap-overview.md
            └── cookies-in-russia.md
```

### Ключевые решения по структуре

- **`app/` — плоская насколько возможно.** Подкаталоги только там, где есть >2 связанных файлов (`api/`, `corpus/`, `llm/`, `report/`). `scanner.py`, `checks.py`, `engine.py` — один файл каждый, пока не разрастутся.
- **`prompts/` — на верхнем уровне.** Промпты — это данные продукта, не утилитарный код. Заметнее и удобнее править.
- **`tests/` — плоская.** Имена `test_<что_тестируется>.py`. Зеркалить структуру `app/` для 10–20 тестовых файлов — лишняя церемония.
- **`tools/` отделено от `app/`.** Это CLI-скрипты, а не часть веб-приложения. Запускаются вручную или через `make`.
- **`frontend/out/` (артефакт сборки) — в `.gitignore`.** В прод собирается через Docker, локально — `pnpm build` или `make build`.
- **Makefile в корне.** Конкретные цели и команды — в разделе «Сборка и запуск». На Windows требует WSL или `choco install make`.

## Архитектура

### Общий вид

```
   Browser (HTTP Basic over HTTPS)
   ── Next.js static (frontend/out)
   ── EventSource → SSE
        │
        ▼
┌─────────────────────────────────────────────────────────┐
│  FastAPI (один процесс, один контейнер)                 │
│                                                         │
│   StaticFiles ──► frontend/out                          │
│   /api/v1/scan                  ◄── создание скана      │
│   /api/v1/scan/{id}             ◄── статус + результат  │
│   /api/v1/scan/{id}/events      ◄── SSE-прогресс        │
│   /api/v1/scan/{id}/report.pdf  ◄── lazy PDF            │
│                                                         │
│   ┌─────────────────────────────────────────────────┐   │
│   │  Engine                                         │   │
│   │   asyncio.Semaphore(1) ──► не больше 1 скана    │   │
│   │   asyncio.wait_for(..., timeout=300)            │   │
│   │                                                 │   │
│   │   ├─ Scanner (Playwright, fresh browser/scan)   │   │
│   │   ├─ Checks registry (детерм. + LLM)            │   │
│   │   └─ Report (WeasyPrint via to_thread, lazy)    │   │
│   └─────────────────────────────────────────────────┘   │
│                                                         │
│   LLMProvider ──► GigaChat / YandexGPT (http)           │
│                       ▲                                 │
│                       │ кэш                             │
│                       ▼                                 │
│              SQLite WAL (volume на хосте)               │
│              ├─ users                                   │
│              └─ llm_cache                               │
└─────────────────────────────────────────────────────────┘
   ▲
   │ HTTP(S)
   ▼
Целевой сайт (Playwright открывает в headless Chromium)
```

### Жизненный цикл скана

1. `POST /api/v1/scan {url}` → создаётся `ScanState`, async-таска ждёт семафор; клиенту возвращается `scan_id`.
2. Фронт открывает `GET /api/v1/scan/{id}/events` (SSE). Сначала отдаётся буфер уже накопленных событий из `ScanState.events`, потом — live-стрим из `asyncio.Queue`. EventSource при автореконнекте получает всё с начала.
3. Engine получает семафор → `scanner.collect()` (свежий Chromium через `async with playwright.chromium.launch()`) → проход по `violations` корпуса → каждый шаг публикуется в SSE и копится в `ScanState.events`.
4. Семантические check-функции дёргают `LLMProvider.ask(...)` через SQLite-кэш (см. раздел «Работа с LLM»).
5. По завершении (или по таймауту `asyncio.wait_for(..., timeout=300)`) `ScanResult` кладётся в `ScanState`, семафор отпускается, в SSE летит `done`. Незавершённые из-за таймаута проверки помечаются `inconclusive`.
6. Фронт делает `GET /api/v1/scan/{id}/report.pdf` → PDF рендерится **в этот момент** через `asyncio.to_thread(WeasyPrint…)` и стримится в ответ. Не скачали — байты не висят в памяти.
7. `ScanState` живёт 1 час после последнего обращения, потом TTL-очистка.

### Где живёт состояние

| Что | Где | Жизненный цикл |
|---|---|---|
| Корпус законов | В памяти процесса | Загружается один раз при старте; для обновления — `docker restart` |
| `scan_id → ScanState` (активные сканы) | В памяти процесса | TTL 1 час, при рестарте теряется (явный KISS-компромисс) |
| `users`, `llm_cache` | SQLite на volume хоста, режим **WAL** | Переживает пересборку контейнера |

### Точки расширения

- **`LLMProvider`** — интерфейс `ask(prompt, content) → StructuredAnswer`. Реализации `GigaChatProvider`, `YandexGPTProvider`. Выбор через env `LLM_PROVIDER`. Кэш — обёртка над любым провайдером.
- **Реестр check-функций** — словарь `{name → callable}` в `app/checks.py`. Добавление проверки = новая функция + одна строка в реестре. Без плагинов и динамических импортов.
- **Маппинг «тип сигнала → шаг прогресса в UI»** — один словарь, читается engine'ом при пуше SSE-события.

### Решения для устойчивости и производительности

- **`asyncio.Semaphore(1)`** ограничивает одновременные сканы — на 2 ГБ RAM два Chromium'а одновременно дадут OOM.
- **`asyncio.to_thread(...)`** для WeasyPrint — рендер PDF не блокирует event loop.
- **SSE с буфером истории** — клиент при подключении или реконнекте никогда не пропускает события.
- **Общий таймаут скана 5 мин** — защита от зависшего Playwright или LLM.
- **SQLite WAL** — параллельные чтения кэша с одновременной записью не блокируют друг друга.
- **Свежий Browser на каждый скан** — нет утечек состояния, проще отлаживать. Накладные расходы ~1 сек на старт — приемлемо.

### Чего в архитектуре НЕТ

- Очереди задач (RQ/Celery/ARQ) — одна `asyncio.Task` в том же процессе.
- Message bus — события прогресса идут прямо в `asyncio.Queue` конкретного скана.
- Фоновых воркеров и крон-задач — TTL скан-стейта реализован на проверке времени при обращении, без отдельного потока.
- WebSocket — SSE проще, односторонний канал нам подходит.
- Сохранение результатов проверок — явное решение из идеи, не сохраняем.

## Модель данных / состояние

### Корпус (только чтение)

Pydantic-модели в `app/corpus/models.py` — 1-в-1 со схемой из [docs/laws/schema.md](laws/schema.md). Основные типы:

```
Law
 ├─ id, title, short_title, type, number
 ├─ adopted_date, in_force_since, last_amended
 ├─ status, regulators, applies_to, related, tags
 ├─ verified_at, verified_by, verified
 ├─ official_sources: list[Source]
 └─ violations: list[Violation]

Violation
 ├─ id, article, title, severity, description, recommendation, references
 ├─ detection: Detection
 │    ├─ page_signals: list[PageSignal]
 │    └─ site_signals: list[SiteSignal]
 └─ penalties: list[Penalty]
```

Корпус **иммутабелен в рантайме** — загружается в `CorpusBundle` на старте, дальше только читается.

### Состояние скана (в памяти)

```
ScanState
 ├─ scan_id: UUID
 ├─ url: str
 ├─ status: "pending" | "running" | "done" | "failed" | "timeout"
 ├─ started_at, finished_at, last_accessed_at
 ├─ events: list[ScanEvent]       # буфер для SSE replay
 ├─ event_queue: asyncio.Queue    # live-канал для подключённых SSE-клиентов
 ├─ result: ScanResult | None     # заполняется по завершении
 └─ error: str | None             # если status == "failed"
```

`last_accessed_at` обновляется при каждом обращении к `scan_id`. Через 1 час без обращений — TTL-очистка при следующем обращении к реестру, отдельный поток не нужен.

### События прогресса (SSE)

```
ScanEvent
 ├─ timestamp
 ├─ type: "step" | "violation_found" | "done" | "error"
 └─ payload: dict
    # step:             { step_name: str, progress: 0.0..1.0 }
    # violation_found:  { violation_id, severity, title }
    # done:             { summary: {failed, passed, inconclusive} }
    # error:            { message: str }
```

### Результат проверки

```
ScanResult
 ├─ scan_id, url, started_at, finished_at
 ├─ summary: { total_checks, failed, passed, inconclusive }
 └─ findings: list[Finding]

Finding
 ├─ violation_id, law_id, title, article, severity
 ├─ status: "fail" | "pass" | "inconclusive"
 ├─ evidence: str | None        # цитата из DOM / URL страницы / CSS-селектор
 ├─ explanation: str | None     # объяснение от check-функции или LLM
 ├─ recommendation: str         # из корпуса (как исправить)
 └─ penalties: list[PenaltyInfo] # из корпуса (для PDF-отчёта)
```

`Finding` — единственный формат вывода для UI и PDF. Текстовые поля (`title`, `recommendation`, `penalties`) уже пришли из корпуса как готовый текст — никакого допроцессинга.

### Persistent-состояние (SQLite, режим WAL)

```sql
CREATE TABLE users (
    login          TEXT PRIMARY KEY,
    password_hash  TEXT NOT NULL,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE llm_cache (
    cache_key      TEXT PRIMARY KEY,   -- sha256(prompt_id + normalized_content_hash + model + prompt_version)
    prompt_id      TEXT NOT NULL,
    model          TEXT NOT NULL,
    answer_json    TEXT NOT NULL,      -- сериализованный StructuredAnswer
    tokens_used    INTEGER,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_llm_cache_created ON llm_cache(created_at);
```

Структура простейшая — никаких FK, никаких сложных индексов. Запросы только по `PRIMARY KEY`.

### Что НЕ хранится

- **Результаты сканов** — только в памяти `ScanState`, после TTL уходят. Прямое требование из идеи.
- **PDF-отчёты** — генерируются на лету при `GET /report.pdf` через `asyncio.to_thread(WeasyPrint…)`, в памяти не висят.
- **Сырые артефакты Playwright** (DOM, network log) — нужны только во время прохода engine, после завершения скана не сохраняются (только то, что попало в `Finding.evidence`).
- **Промпты и ответы LLM как пары** — в кэше лежит только нормализованный `StructuredAnswer`, не сам промпт и не исходный текст.
- **История пользовательских действий** — никаких логов «кто что проверял».

## Работа с LLM

### Интерфейс провайдера

```
async LLMProvider.ask(prompt_id, content, budget_tokens) → StructuredAnswer

StructuredAnswer
 ├─ verdict: "pass" | "fail" | "unclear"
 ├─ evidence: str            # цитата из content
 ├─ explanation: str         # короткое объяснение для отчёта
 └─ tokens_used: int         # реальный расход; 0 для попаданий в кэш
```

Реализации: `GigaChatProvider` (primary), `YandexGPTProvider`. Выбор — через env `LLM_PROVIDER=gigachat | yandex`. Никакого автофоллбека между провайдерами — переключение ручное.

`CachedLLMProvider` — декоратор над любым провайдером, читает/пишет SQLite-кэш до делегирования вызова реальному провайдеру. При попадании в кэш возвращает `tokens_used=0`, чтобы не тратить бюджет.

### Промпты как данные

`prompts/<prompt_id>.md` — простой Markdown-шаблон с плейсхолдером `{content}`. Без frontmatter — имя файла = `prompt_id`, версионирование через git (любое изменение файла → новый хэш промпта → новый ключ кэша).

Подстановка контента — `prompt_text.replace("{content}", content)`, **не** `.format()`. В реальных политиках встречаются фигурные скобки (`{`/`}`) — `.format()` упадёт с `KeyError`.

Пример `prompts/policy_discloses_purposes.md`:

```markdown
Ты — юрист по 152-ФЗ. На входе — текст политики конфиденциальности.

Ответь строго JSON:
{
  "verdict": "pass" | "fail" | "unclear",
  "evidence": "цитата из текста, обосновывающая вердикт (1-2 предложения)",
  "explanation": "коротко: что нашёл / чего не хватает"
}

verdict="pass" — в тексте явно перечислены конкретные цели обработки ПДн.
verdict="fail" — целей нет или они слишком общие («улучшение сервиса» не считается).
verdict="unclear" — текст оборван или не похож на политику.

Текст политики:
---
{content}
---
```

### Извлечение текста из страницы

Подача в LLM «текста политики» — это работа check-функции, не провайдера. Подход KISS:

- Берём DOM-артефакт нужной страницы от `scanner` (Playwright уже вернул HTML).
- Через BeautifulSoup: `<main>` или `<article>` если есть, иначе `<body>` минус `<nav>` / `<footer>` / `<script>` / `<style>`.
- `.get_text(separator="\n", strip=True)` → плоский текст.

Никаких Readability/trafilatura-либ в MVP. Простой парсер закрывает 90% случаев.

### Что подаётся в LLM

| Семантическая проверка | Что подаём в LLM |
|---|---|
| Политика раскрывает цели обработки | Текст страницы политики |
| Текст согласия корректный | Содержимое `<label>` чекбокса + связанный документ |
| Cookie-banner без dark pattern | DOM-фрагмент банера + текст кнопок |
| Является ли блок рекламой | Текст блока + 1–2 соседних элемента контекста |

### Ключ кэша

```
cache_key = sha256(prompt_text + normalized_content + model)
```

- `prompt_text` — весь текст файла промпта. Поменяли промпт → новый ключ.
- `normalized_content` — текст после нормализации (см. ниже).
- `model` — конкретная версия модели (`GigaChat-Pro`, `GigaChat-Max`, ...).

### Нормализация контента перед хэшированием

- `strip()` + схлопывание множественных пробелов и пустых строк
- удаление заведомо динамического: «Последнее обновление: …», «© 2026», `nonce`/`csrf` из data-атрибутов
- унификация переводов строк (`\r\n` → `\n`)

Регистр и пунктуация не трогаются — содержательно.

### Бюджет токенов

- **Per-scan budget: 50 000 токенов.** Передаётся в `ask()` и уменьшается после каждого вызова.
- **Проверка ДО вызова.** Если `remaining_budget < ESTIMATED_MIN_COST` (запас ~1000 токенов) → возвращаем `inconclusive("исчерпан бюджет")`, **провайдера не дёргаем**. Иначе уйдём в минус из-за округлений.
- **Cache hit стоит 0 токенов.** Кэшированные ответы бесплатные, бюджет на них не тратится.
- Глобального лимита нет — 1–2 пользователя, аккаунты создаются вручную, фрод нерелевантен.

### Особенности GigaChat (учитываем в `GigaChatProvider`)

1. **Bearer-токен живёт ~30 минут.** Провайдер хранит токен + `expires_at` в памяти, обновляет проактивно (за ~1 мин до истечения). Не «истёк → 401 → паника», не обновление на каждом запросе.
2. **Контент-модерация.** Иногда отказывается отвечать на юр/мед темы — это HTTP 200 с защитным ответом, не ошибка. Распознаём по характерному паттерну ответа → возвращаем `inconclusive` с пометкой «провайдер отказался отвечать».

### Обработка ошибок

| Ситуация | Что делаем |
|---|---|
| LLM вернул невалидный JSON | Одна попытка ретрая с уточнением «верни строго JSON». Не сработало → `inconclusive` |
| `verdict == "unclear"` | `inconclusive` с пояснением от LLM |
| HTTP 5xx / таймаут провайдера | **Один автоматический ретрай** через httpx-транспорт. Не помог → `inconclusive`, логируем |
| HTTP 4xx (кроме 429) | Сразу `inconclusive` — наш баг, ретраи не помогут |
| HTTP 429 (rate limit) | Ретрай с задержкой по `Retry-After` (если есть) — один раз, потом `inconclusive` |
| Контент-модерация (отказ отвечать) | `inconclusive` с пометкой |
| Превышен бюджет | `inconclusive` с пометкой, провайдер не дёргается |

`inconclusive` ≠ `pass`. Пользователь должен видеть, что проверка не дала чёткого ответа.

### Логирование LLM-вызовов

Логируем только **метаданные**, не содержимое:

```
prompt_id, model, tokens_used, verdict, latency_ms, cache_hit, retry_count
```

Не логируем: текст промпта, контент, ответ LLM, evidence. Иначе логи распухнут и могут содержать PII с проверяемых сайтов.

### Чего НЕТ

- Стриминга токенов — ждём полный ответ.
- Multi-turn диалога — каждый промпт self-contained.
- Function calling / tool use — структура ответа задана промптом, валидируется Pydantic.
- Автофоллбека между провайдерами — только ручное переключение через env.
- Адаптивного бюджета — фиксированный `budget_tokens` на скан.
- Readability/trafilatura/иных тяжёлых либ для извлечения текста — простой BeautifulSoup.

## Сценарии работы пользователя

### 1. Первый вход

1. Открывает URL приложения в браузере.
2. Браузер показывает нативное окно HTTP Basic Auth.
3. Вводит логин/пароль (созданные владельцем заранее через `make user`).
4. Видит главную страницу с одним инпутом для URL и кнопкой «Проверить».
5. Дальше браузер кэширует Basic-credentials до закрытия вкладки/окна.

### 2. Основной сценарий — проверка сайта (happy path)

1. Вводит URL в свободной форме — приложение нормализует (см. ниже), нажимает «Проверить».
2. Фронт делает `POST /api/v1/scan` → получает `scan_id`, сразу открывает `GET /api/v1/scan/{id}/events` (SSE).
3. На экране — анимация прогресса. По мере событий обновляется текущий шаг:
   - «Загружаем главную страницу…»
   - «Ищем политику конфиденциальности…»
   - «Проверяем формы сбора ПДн…»
   - «Анализируем cookie и трекеры…»
   - «Проверяем рекламные блоки…»
   - …
4. Параллельно копится счётчик найденных нарушений по уровням severity.
5. SSE присылает `done`. Фронт делает `GET /api/v1/scan/{id}` → получает полный `ScanResult`.
6. Видит **сводку** (всего нарушений, по severity, сколько `inconclusive`) и **список Finding'ов — все карточки раскрыты по умолчанию**. Каждая карточка содержит: статью закона, описание, evidence (цитата/селектор), штрафы, рекомендацию. Над списком — кнопка «Свернуть все» / «Раскрыть все», у каждой карточки — индивидуальная сворачивалка.
7. Кнопка «Скачать PDF» → `GET /api/v1/scan/{id}/report.pdf` → PDF рендерится на лету и скачивается с именем вида `legal-audit-example.ru-2026-05-13.pdf`.

### Нормализация URL (на бэке, Pydantic-валидатор)

1. `strip()` ведущих/хвостовых пробелов.
2. Если нет схемы (`example.ru`, `www.example.ru`) → подставляем `https://`.
3. `http://...` оставляем как есть — не апгрейдим автоматически. Отсутствие HTTPS всплывёт в отчёте как нарушение.
4. `www` не трогаем — оставляем как ввёл. Не подбираем вариант с/без `www`.
5. Валидация через `urllib.parse.urlparse` + проверка `netloc` (есть точка, допустимые символы). Невалид → 422 от FastAPI с понятным сообщением.

| Ввёл | Уйдёт в scanner |
|---|---|
| `example.ru` | `https://example.ru` |
| `www.example.ru` | `https://www.example.ru` |
| `example.ru/cart` | `https://example.ru/cart` |
| `http://example.ru` | `http://example.ru` |
| `  https://example.ru  ` | `https://example.ru` |
| `example` (без точки) | 422 «не похоже на адрес сайта» |

На фронте — лёгкая прескрин-валидация только на пустоту/явный мусор. Основная валидация — на бэке.

### 3. Параллельный второй скан

1. Фронт получает `scan_id` мгновенно, но в SSE — событие `step` со статусом «Ждём завершения предыдущего скана…» (семафор).
2. Когда первый скан закончился — второй начинает обычный поток событий.
3. Пользователь это видит явно, не считает, что приложение зависло.

### 4. Закрытие вкладки во время скана

1. Скан продолжает работать на сервере (async-таска не зависит от соединения).
2. SSE-соединение закрывается, события копятся в `ScanState.events`.
3. Пользователь возвращается в течение часа — `GET /api/v1/scan/{id}/events` снова отдаст накопленный буфер + live-стрим, если скан ещё идёт.

### 5. Нестандартные ситуации

| Ситуация | Что пользователь видит |
|---|---|
| Невалидный URL (пустой / без точки в хосте / битый) | 422 с понятным сообщением, ещё до запуска скана |
| Сайт недоступен (DNS / 404 / timeout 30 сек на загрузку главной) | SSE-событие `error: "Сайт не отвечает или недоступен"`, скан помечается `failed`, кнопка «Попробовать снова» |
| Сайт блокирует ботов (403 Cloudflare и т.п.) | То же — `failed` с причиной «Сайт блокирует автоматические проверки» |
| LLM-провайдер сломался | Скан **не падает**. Семантические проверки получают `inconclusive`, детерминированные продолжают работать. В отчёте — раздел «Не удалось проверить семантически» |
| Превышен таймаут скана (5 мин) | SSE-событие `done` с пометкой `timeout`. Что успели проверить — в результате, остальное — `inconclusive` |
| Превышен токен-бюджет | Аналогично — оставшиеся семантические проверки `inconclusive` с пометкой «исчерпан токен-бюджет» |
| Ввёл неправильный пароль | Браузер 3 раза показывает Basic Auth prompt, потом — 401 страница от FastAPI |

### 6. Чего НЕТ в сценариях MVP

- Регистрации, восстановления пароля, смены пароля через UI (только через `make user`).
- Истории «мои предыдущие проверки» — результаты не сохраняются.
- Списка сохранённых сайтов / закладок.
- Уведомлений (email, push) о готовности скана — UI всегда в фокусе пользователя.
- Расшаривания результата по ссылке — каждый скан только для одного клиента.
- Сравнения двух сканов одного сайта.
- Автоподбора вариантов URL (`www`/`без www`, `http`/`https`).

## Конфигурация и секреты

### Единый источник — `app/config.py` на Pydantic Settings

Все настройки приложения — один класс `Settings(BaseSettings)`. Pydantic сам читает из env-переменных и из `.env` файла в корне. Типы проверяются на старте — кривое значение → процесс не запустится.

### Полный список env-переменных

| Переменная | Default | Назначение |
|---|---|---|
| `LLM_PROVIDER` | `gigachat` | `gigachat` или `yandex` |
| `GIGACHAT_AUTH_KEY` | — | Bearer-ключ авторизации GigaChat (формат «Basic …» из личного кабинета) |
| `GIGACHAT_MODEL` | `GigaChat` | Конкретная модель (`GigaChat`, `GigaChat-Pro`, `GigaChat-Max`) |
| `YANDEX_GPT_API_KEY` | — | API-ключ Yandex Cloud (если `LLM_PROVIDER=yandex`) |
| `YANDEX_GPT_FOLDER_ID` | — | Folder ID Yandex Cloud |
| `DATABASE_PATH` | `/data/db.sqlite` | Путь к SQLite-файлу (на хосте — volume) |
| `CORPUS_PATH` | `docs/laws` | Путь к каталогу с корпусом законов |
| `PROMPTS_PATH` | `prompts` | Путь к каталогу с LLM-промптами |
| `SCAN_TIMEOUT_SECONDS` | `300` | Общий таймаут одного скана |
| `LLM_BUDGET_TOKENS_PER_SCAN` | `50000` | Токен-бюджет на скан |
| `SCAN_STATE_TTL_SECONDS` | `3600` | TTL для `ScanState` в памяти |
| `LOG_LEVEL` | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `BASIC_AUTH_REALM` | `Legal_site` | Подпись в окне Basic Auth (для разных установок можно отличать) |

### Файл `.env.example` (в git)

Кладётся в корень репозитория, в git, без секретов:

```env
LLM_PROVIDER=gigachat
GIGACHAT_AUTH_KEY=replace_me
GIGACHAT_MODEL=GigaChat
# YANDEX_GPT_API_KEY=
# YANDEX_GPT_FOLDER_ID=

DATABASE_PATH=/data/db.sqlite
SCAN_TIMEOUT_SECONDS=300
LLM_BUDGET_TOKENS_PER_SCAN=50000
LOG_LEVEL=INFO
```

### Файл `.env` (НЕ в git)

В `.gitignore`. Локально для разработки — копия `.env.example` с реальными значениями. На VPS — создаётся вручную при первом деплое (например, в `~/legal_site/.env`), права `600`. Подхватывается `docker run --env-file=.env`.

### Секреты — что считается секретом и где живёт

| Секрет | Где живёт |
|---|---|
| `GIGACHAT_AUTH_KEY`, `YANDEX_GPT_*` | Только в `.env` на VPS (или передаются `docker run -e`). Не в коде, не в git |
| Пароли пользователей | bcrypt-хэши в SQLite, плейн-пароль не сохраняется нигде. Создание/смена — только через `make user` |
| Bearer-токен GigaChat (получаемый по `AUTH_KEY`) | Только в памяти процесса, обновляется по `expires_at` |

**Никогда не логируем:**
- Содержимое env-переменных
- Bearer-токен GigaChat
- Пароли (даже хэши на info-уровне)
- Содержимое промптов и LLM-контента (см. раздел «Работа с LLM»)

### Загрузка и проверка на старте

При старте FastAPI:
1. Загружается `.env` через Pydantic Settings.
2. Проверяется, что обязательные ключи присутствуют (для выбранного `LLM_PROVIDER` — соответствующие ключи).
3. Проверяется, что `DATABASE_PATH` доступен на запись.
4. Парсится корпус из `CORPUS_PATH` — иначе процесс не стартует. Битый корпус → fail-fast, не идём в прод с поломанной справочной базой.
5. Проверяется, что нужные промпты для check-функций существуют в `PROMPTS_PATH`.

Любая ошибка → процесс падает с понятным сообщением, не пытается работать в полусломанном состоянии.

### Чего НЕТ

- Vault / AWS Secrets Manager / KMS — оверкилл для one-VPS установки.
- Конфигурация в YAML/TOML файлах — `.env` + Pydantic Settings достаточно.
- Hot-reload конфигурации — `docker restart` после правки `.env`.
- Profile'ов (`dev/staging/prod`) — одна установка, разные значения через разные `.env` на разных хостах.
- Динамической смены LLM-провайдера в рантайме — только через env + рестарт.
- Bootstrap-создания пользователей из env — только `make user` после первого старта.

## Логирование

- **Куда:** stdout/stderr, ничего в файлы внутри контейнера. На VPS читается через `docker logs legal_site --tail 200 -f`.
- **Чем:** стандартный `logging` из stdlib. Один кастомный форматтер, который добавляет `scan_id` из `contextvars` к каждому сообщению внутри скана.
- **Уровни:** `INFO` — старт/конец скана, найденные нарушения, создание пользователя; `WARNING` — ретраи, отказ модерации, попадание в таймаут отдельной check-функции, превышение бюджета; `ERROR` — Playwright-таймаут на главной, провайдер не отвечает после ретрая, неперехваченное исключение; `DEBUG` — выключено по умолчанию, включается через `LOG_LEVEL=DEBUG`.
- **Корреляция:** `contextvars` ставит `scan_id` при старте async-таски скана, форматтер вытаскивает его — `docker logs ... | grep scan_id=...` даёт полную трассировку одного скана.
- **Что не логируем:** содержимое env, Bearer-токены, пароли, промпты, LLM-контент и ответы, сырой DOM сайтов. Подробности — в разделах «Работа с LLM» и «Конфигурация и секреты».

## Сборка и запуск

Конкретные команды — в `Makefile`. Здесь — типовые сценарии работы.

### Первичная настройка локального окружения

```bash
git clone <repo>
cd Legal_site
cp .env.example .env
# отредактировать .env, прописать GIGACHAT_AUTH_KEY и т.п.

make install                # uv sync + pnpm install
playwright install chromium # один раз: Docker используется только для прода
make user                   # создать первого пользователя локально
```

### Повседневная разработка

В двух терминалах:

```bash
make dev           # FastAPI с автоперезагрузкой, порт 8000
make dev-frontend  # Next.js dev-сервер, порт 3000, проксирует /api на 8000
```

Фронт открывается на `http://localhost:3000`, изменения в `frontend/src/` подхватываются hot-reload'ом. Изменения в `app/` — uvicorn перезагружается сам.

### Перед коммитом

```bash
make lint  # ruff check + mypy
make fmt   # ruff format + ruff check --fix
make test  # pytest
```

### Обновление корпуса законов

После правок в `docs/laws/*.md`:

```bash
make corpus  # python tools/rebuild_index.py
```

Скрипт пересобирает `index.yml` из всех фронтматтеров и валидирует целостность кросс-ссылок (`related`, `references_in_common`). Падает на битом YAML, нарушенной целостности, дублях violation-id. Не пройдёт — не коммитим.

### Production-сборка

```bash
make docker-build  # docker build -t legal_site .
```

Multi-stage Dockerfile:
1. `frontend-build` — `node:20-alpine`, `pnpm install`, `pnpm build` → `frontend/out`
2. `runtime` — `mcr.microsoft.com/playwright/python:v1.49.0-noble`, `uv sync`, копируем `app/`, `tools/`, `prompts/`, `docs/`, собранный `frontend/out/`

На выходе один образ `legal_site:latest`, ~1,5–2 ГБ.

### Production-запуск

```bash
make docker-run
# docker run --rm -p 8000:8000 -v $(pwd)/data:/data --env-file=.env legal_site
```

Важное:
- `-v $(pwd)/data:/data` — SQLite живёт на хосте, переживает пересборку образа
- `--env-file=.env` — конфигурация и секреты (включая `GIGACHAT_AUTH_KEY`)
- Порт 8000 наружу — на хосте reverse-proxy (nginx) с `certbot` отдаёт HTTPS на 443

### Что запускается внутри контейнера

```
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
```

**Один воркер.** Не `--workers 4`. Состояние сканов держим в памяти процесса — несколько воркеров не смогут поделиться им без Redis. Для 1–2 пользователей одного воркера достаточно.

### Чего НЕТ

- Скриптов миграции БД (alembic / yoyo) — схема SQLite простая, `CREATE TABLE IF NOT EXISTS` при старте. Если структура радикально поменяется — пересоздадим БД, не катастрофа.
- Pre-commit hooks — `make lint && make test` дисциплинирует и так.
- Запуска через `supervisord` / `systemd` — Docker сам перезапустит контейнер при падении (`--restart unless-stopped`).
- Health-check сложнее `/health` возвращающего `{"status": "ok"}`.

## Деплой

Отложено. Опишем, когда дойдём до первого реального развёртывания на VPS — там нужны конкретные команды по nginx, certbot, systemd-юниту для `docker run` и скриптом обновления `git pull + docker build + docker run`. До этого момента «как деплоить» сводится к разделу «Production-запуск» выше.
