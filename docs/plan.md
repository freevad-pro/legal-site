# Дорожная карта проекта Legal_site

Документ фиксирует крупные этапы развития системы — от уже зафиксированной документации до production-деплоя. Опирается на [docs/idea.md](idea.md), [docs/vision.md](vision.md) и [docs/adr/0001-laws-reference-structure.md](adr/0001-laws-reference-structure.md). Конкретные подзадачи каждой итерации живут в `docs/tasks/iteration-NN-<slug>.md`.

## Организация работ

`plan.md` — верхнеуровневая карта: список итераций, их цели и критерии завершения. Мелкий backlog (конкретные шаги, файлы, команды) не дублируется здесь, а вынесен в отдельные tasklist'ы под каждую итерацию по принципу «один этап — один tasklist». `plan.md` ссылается на tasklist'ы, но не повторяет их содержимое — при изменениях правится только tasklist, верхний уровень остаётся стабильным.

## Ключевые особенности плана

1. **Корпус законов — фундамент, всё остальное — обвязка.** Справочник законов как контент собран отдельной первой итерацией и является единственным источником правды о праве. Движок, API, UI и LLM-проверки опираются на готовый корпус и не дублируют знание о законах в коде.
2. **End-to-end на детерминированной логике, LLM — позже.** К итерации 6 продукт уже работает целиком (CLI → API → Frontend → PDF) на одних детерминированных правилах. LLM добавляется в итерации 7 как улучшение покрытия с ~65% до ~90–95%, поверх стабильной базы.
3. **Каждый этап — измеримый инкремент.** У каждой итерации есть проверяемое DoD и точка демонстрации (что-то «работает» по итогам). Деплой откладывается до полного завершения функционала — на VPS поднимается уже готовый продукт.

## Рабочий процесс

- Перед стартом итерации — создаём `docs/tasks/iteration-NN-<slug>.md`, статус в обзорной таблице меняем `📋 → 🚧`.
- По завершении всех пунктов DoD — статус `🚧 → ✅`, короткая демонстрация (`make`-команда, curl или скриншот).
- План живой: если DoD оказался лишним или неполным — правим `plan.md` в момент обнаружения, не накапливаем долг.

## Старт новой сессии

Чтобы продолжить работу в новом чате — достаточно этого файла как точки входа:

1. Прочитать `docs/plan.md` целиком (этот файл). Найти в обзорной таблице итерацию со статусом 🚧 или следующую 📋 после последней ✅.
2. Открыть `docs/tasks/iteration-NN-<slug>.md` соответствующей итерации.
3. Прочитать разделы из `docs/vision.md`, указанные в поле «**Стартовый контекст**» в карточке этой итерации (не весь vision — только нужные).
4. Глянуть `git status` и содержимое `app/` / `frontend/` для актуального состояния кода (план описывает «что должно быть», код — «что уже есть»).

### Шаблон стартового промпта — короткий

> Продолжаем Legal_site по `docs/plan.md`.
> Найди текущую итерацию (🚧 или следующую 📋 после ✅), прочитай её карточку, «Стартовый контекст» и tasklist. Глянь `git status`. Доложи: где остановились, что осталось по DoD, какой первый шаг предлагаешь.

### Шаблон стартового промпта — подробный (для холодного старта)

> Продолжаем реализацию проекта Legal_site по дорожной карте.
>
> Что сделать перед ответом:
> 1. Прочитай `docs/plan.md` целиком.
> 2. Найди в обзорной таблице итерацию со статусом 🚧. Если её нет — следующую 📋 после последней ✅.
> 3. Прочитай её карточку (Цель, DoD, Стартовый контекст, Полезный результат).
> 4. Прочитай разделы из `docs/vision.md`, перечисленные в «Стартовый контекст».
> 5. Открой `docs/tasks/iteration-NN-<slug>.md`. Если файла нет — пометь, что его надо создать перед стартом работ.
> 6. Проверь `git status` и содержимое `app/` / `frontend/` — что уже сделано в коде.
>
> Доложи:
> - Какая итерация текущая и её цель одной строкой.
> - Что уже выполнено по DoD (отметь зелёным/красным).
> - Какие зазоры: нужен ли tasklist, есть ли несоответствие `plan.md` и кода.
> - Какой первый шаг предлагаешь.
>
> Дальше работаем по обычному ритуалу: 📋→🚧 при старте, 🚧→✅ при завершении, демонстрация в конце.

## Легенда статусов

📋 Planned — запланирован
🚧 In Progress — в работе
✅ Done — завершён

---

## Обзор итераций

| Итерация | Название | Цель | Статус | Tasklist |
|----------|----------|------|--------|----------|
| 0 | Фундамент документации | Зафиксированы идея, видение, ADR, схема корпуса, эталонный 152-ФЗ | ✅ Done | — |
| 1 | Корпус MVP — 15 актов + 2 обзора | Полный валидированный справочник законов, 100 нарушений | ✅ Done | — |
| 2 | Каркас приложения и инструментарий | Рабочая разработческая среда: FastAPI отвечает, `make` команды работают | ✅ Done | [iteration-02-skeleton.md](tasks/iteration-02-skeleton.md) |
| 3 | Детерминированный движок (CLI-MVP) | На любой URL получаем JSON Finding'ов по детерминированным правилам | ✅ Done | [iteration-03-deterministic-engine.md](tasks/iteration-03-deterministic-engine.md) |
| 4 | API, аутентификация, отчёт PDF | End-to-end через curl: SSE прогресс + PDF-отчёт + Basic Auth | ✅ Done | [iteration-04-api.md](tasks/iteration-04-api.md) |
| 5 | Выбор и согласование дизайна UI | Утверждены стиль, палитра, мокапы 3 экранов; пользователь подтвердил | ✅ Done | [iteration-05-design.md](tasks/iteration-05-design.md) |
| 5а | Auth refactor: форма входа и разделение free/LLM | API на cookie-сессиях; `POST /scans` принимает `with_llm`, без сессии для `with_llm=true` — 401 | ✅ Done | [iteration-05a-auth-refactor.md](tasks/iteration-05a-auth-refactor.md) |
| 6 | Frontend MVP | Полный пользовательский сценарий через UI работает локально | ✅ Done | [iteration-06-frontend.md](tasks/iteration-06-frontend.md) |
| 6б | Контекстный гейтинг и инверсная логика детекции | Убрать ложные срабатывания через `applicability`-теги, поле `prohibited_keywords` и фильтрацию заглушек в отчёте | ✅ Done | [iteration-06b-detection-fixes.md](tasks/iteration-06b-detection-fixes.md) |
| 6в | Многостраничный обход сайта | Scanner обходит ключевые внутренние страницы (контакты, политика, обратная связь, регистрация), engine агрегирует findings со всех страниц; Finding содержит `page_url` | 📋 Planned | [iteration-06c-multipage-scan.md](tasks/iteration-06c-multipage-scan.md) |
| 7 | Гибридное LLM-покрытие | Покрытие нарушений ~90–95% за счёт семантических check-функций | 📋 Planned | [iteration-07-llm.md](tasks/iteration-07-llm.md) |
| 8 | Production-деплой на Beget VPS | Приложение поднято на VPS под HTTPS | 📋 Planned | [iteration-08-deploy.md](tasks/iteration-08-deploy.md) |

---

## Итерации

### Итерация 0: Фундамент документации

**Цель:** зафиксировать продуктовое и техническое видение до начала разработки, чтобы дальнейшая работа шла против согласованного контракта.

**Критерии завершения (DoD):**
- [docs/idea.md](idea.md) — продуктовая идея и сценарии MVP
- [docs/research.md](research.md) — техническое исследование и выбор стека
- [docs/vision.md](vision.md) — техническое видение (10 разделов, деплой отложен на итерацию 8)
- [docs/adr/0001-laws-reference-structure.md](adr/0001-laws-reference-structure.md) — структура справочника
- [docs/laws/schema.md](laws/schema.md) — формальная схема корпуса
- [docs/laws/152-fz-personal-data.md](laws/152-fz-personal-data.md) — эталонный закон, задаёт стандарт для остальных
- `docs/plan.md` (этот файл) — дорожная карта

**Связь с tasklist:** —

**Полезный результат:** новый разработчик (или будущий ты) понимает, что и зачем строим, не задавая лишних вопросов.

**Артефакты:** все файлы в `docs/`, перечисленные в DoD.

---

### Итерация 1: Корпус MVP — 15 актов + 2 обзора

**Цель:** собрать справочник законов, начатый эталонным 152-ФЗ, до полного набора MVP по [ADR-0001](adr/0001-laws-reference-structure.md) — он становится фундаментом, к которому привязан весь остальной код.

**Критерии завершения (DoD):**
- ✅ Собраны все 15 актов из ADR-0001 + 2 сводных обзора (`koap-overview.md`, `cookies-in-russia.md`) + бонусный `data-coverage-limitations.md`
- ✅ Каждый файл соответствует [docs/laws/schema.md](laws/schema.md): обязательные поля, ≥ 1 нарушение с `detection`, источники из приоритетного списка
- ✅ Все YAML валидны, все кросс-ссылки `related` / `references_in_common` резолвятся
- ✅ Итого 100 уникальных нарушений
- ✅ `tools/rebuild_index.py` сгенерировал [docs/laws/index.yml](laws/index.yml) и подтвердил целостность
- ✅ [docs/laws/README.md](laws/README.md) с таблицами актов и счётчиком нарушений

**Связь с tasklist:** —

**Полезный результат:** база знаний для движка готова. Любой нарушенный пункт законодательства имеет машиночитаемое описание и человеко-читаемый раздел.

**Артефакты:** `docs/laws/*.md` (15 актов), `docs/laws/common/*.md` (3 обзора), `docs/laws/index.yml`, `docs/laws/README.md`, `tools/rebuild_index.py`, `tools/show_verification_notes.py`.

**Открытое:** все файлы помечены `verified: partial` с открытыми TODO в `verification_notes` — финальная сверка отдельных нумераций частей статей КоАП и сумм штрафов с pravo.gov.ru отложена. Это типичная ситуация для v1; перевод в `verified: full` идёт по мере готовности первоисточников и не блокирует движок.

---

### Итерация 2: Каркас приложения и инструментарий

**Цель:** поднять разработческую среду — FastAPI запускается, линтеры и тесты работают, `make`-команды на месте, готовые скрипты корпуса завёрнуты в стандартные цели.

**Стартовый контекст:** [vision.md](vision.md) — разделы «Технологии», «Структура репозитория», «Сборка и запуск», «Конфигурация и секреты», «Логирование», «Принципы разработки»; готовый `tools/rebuild_index.py` из итерации 1 (как точка интеграции для `make corpus`).

**Критерии завершения (DoD):**
- ✅ `pyproject.toml` + `uv.lock`, виртуальное окружение через `uv`
- ✅ `app/main.py` с FastAPI и эндпоинтом `GET /health` → `{"status": "ok"}`
- ✅ `Makefile` с целями: `install`, `dev`, `lint`, `fmt`, `test`, `corpus`
- ✅ `make corpus` запускает `python tools/rebuild_index.py` (пересборка `index.yml` + проверка целостности кросс-ссылок); зелёный на текущем корпусе (15 законов, 3 обзора, 100 нарушений)
- ✅ `ruff` + `mypy` сконфигурированы (mypy строгий для `app/` и `tools/`, всё в `pyproject.toml`)
- ✅ `pytest` со скелетом `tests/` и одним работающим тестом (`tests/test_health.py` через `TestClient`)
- ✅ `.env.example`, `.gitignore`, корневой `README.md` с инструкцией «как поднять локально»

**Связь с tasklist:** [tasks/iteration-02-skeleton.md](tasks/iteration-02-skeleton.md)

**Полезный результат:** `make install && make dev` поднимает локальный сервер; `make lint && make test && make corpus` — всё зелёное.

**Артефакты:** `pyproject.toml`, `Makefile`, `app/main.py`, `app/config.py`, `.env.example`, корневой `README.md`.

---

### Итерация 3: Детерминированный движок (CLI-MVP)

**Цель:** научиться сканировать произвольный URL и применять детерминированные правила из корпуса — пока без API и фронта, через CLI.

**Стартовый контекст:** [vision.md](vision.md) — разделы «Принципы разработки», «Архитектура», «Модель данных / состояние»; [laws/schema.md](laws/schema.md) (поля `detection.page_signals` / `site_signals`, описание `check`-функций); [laws/152-fz-personal-data.md](laws/152-fz-personal-data.md) для разработки и тестирования первых проверок.

**Критерии завершения (DoD):**
- `app/corpus/models.py` — Pydantic-модели по схеме `docs/laws/`
- `app/corpus/loader.py` — парсит корпус, валидирует, отдаёт иммутабельный `CorpusBundle`
- `app/scanner.py` — Playwright собирает артефакты страницы (DOM, cookies, headers, network)
- `app/checks.py` — реестр check-функций (`{name → callable}`) + базовые реализации для `page_signals` и `site_signals`
- `app/engine.py` — оркестратор: scanner → проход по `violations` → список `Finding`
- CLI: `uv run python -m app.scan <url>` печатает JSON с Finding'ами в stdout
- `tests/`: покрытие парсера корпуса и реестра check-функций (не на FastAPI и не на Playwright-сценариях)
- На эталонном 152-ФЗ детектируются хотя бы 3–5 типовых нарушений

**Связь с tasklist:** [tasks/iteration-03-deterministic-engine.md](tasks/iteration-03-deterministic-engine.md)

**Полезный результат:** появилась нижняя сущность всей системы — «дай URL, получи JSON Finding'ов». Дальше всё (API, UI, LLM) — обвязка вокруг неё.

**Артефакты:** `app/corpus/`, `app/scanner.py`, `app/checks.py`, `app/engine.py`, тесты в `tests/`.

---

### Итерация 4: API, аутентификация, отчёт PDF

**Цель:** обернуть движок в HTTP-API, добавить аутентификацию, SSE-прогресс и PDF-отчёт — так, чтобы полный сценарий проходил через `curl` без участия фронта.

**Стартовый контекст:** [vision.md](vision.md) — разделы «Архитектура» (жизненный цикл скана, SSE, семафор), «Модель данных / состояние», «Сценарии работы пользователя» (нормализация URL, нестандартные ситуации), «Конфигурация и секреты», «Логирование».

**Критерии завершения (DoD):**
- `POST /api/v1/scans` создаёт скан, возвращает `scan_id`
- `GET /api/v1/scans/{id}` отдаёт текущий статус + `ScanResult` по завершении
- `GET /api/v1/scans/{id}/events` — SSE с буфером истории и live-потоком
- `GET /api/v1/scans/{id}/report.pdf` — lazy-рендер WeasyPrint через `asyncio.to_thread`
- HTTP Basic Auth защищает всё, кроме `/health`; пароли — bcrypt в SQLite
- `tools/create_user.py` — CLI для создания/обновления пользователей
- SQLite в режиме WAL, схема `users` (таблица `llm_cache` появится в итерации 7 — её рано создавать)
- `asyncio.Semaphore(1)` ограничивает одновременные сканы
- `asyncio.wait_for(timeout=300)` — общий таймаут скана
- TTL для `ScanState` в памяти (1 час, очистка при обращении)
- Нормализация URL по правилам из vision (без схемы → `https://`, `http://` оставляем, валидация netloc)
- End-to-end сценарий через `curl`: создать скан → получить SSE-события → скачать PDF

**Связь с tasklist:** [tasks/iteration-04-api.md](tasks/iteration-04-api.md)

**Полезный результат:** бэкенд готов и стабилен — есть контракт, под который пишется фронт.

**Артефакты:** `app/api/`, `app/auth.py`, `app/db.py`, `app/report/`, `tools/create_user.py`, `prompts/` (структура; промпты появятся в итерации 7).

> *Basic Auth итерации 4 был временным MVP-решением: он закрыл вопрос аутентификации одним приёмом и позволил сосредоточиться на API, SSE и PDF. Продуктовая модель «бесплатно всем / LLM — только владельцу» требует формы входа на сайте и условного доступа на уровне эндпоинта — это сделано в итерации 5а.*

---

### Итерация 5: Выбор и согласование дизайна UI

**Цель:** зафиксировать визуальный язык продукта (стиль, палитра, типографика, мокапы ключевых экранов) и **получить явное согласование пользователя** до начала кодинга фронта.

**⚡ Параллельность:** может вестись **параллельно с итерацией 4** (API). Дизайн не зависит от готового бэка — нужны только сценарии из `idea.md` и vision.

**Стартовый контекст:** [idea.md](idea.md) (целевая аудитория, сценарии MVP); [vision.md](vision.md) — раздел «Сценарии работы пользователя» (что должно быть на каждом экране, поведение карточек), «Технологии» → Frontend (Tailwind как ограничение/инструмент).

**Критерии завершения (DoD):**
- Зафиксированы стиль и тональность (деловой/доверительный vs дружелюбный) с 2–3 референсами (URL аналогичных продуктов или скриншоты)
- Решено: чистый Tailwind или + надстройка (`shadcn/ui`, Radix, Headless UI), аргументация одной строкой
- Цветовая палитра (основной фон, акцент, severity-цвета для нарушений: `low` / `medium` / `high` / `critical`); типографика (1 шрифт основного текста + 1 моноширинный для evidence-цитат)
- Текстовые/ASCII-мокапы 3 ключевых экранов: главная (форма ввода URL + кнопка запуска), прогресс (текущий шаг + счётчик нарушений), результат (список карточек Finding + кнопка PDF)
- Решение по адаптивности: только desktop / desktop + tablet / mobile-first — одной строкой с аргументацией
- Все решения собраны в `docs/design.md` (или `docs/adr/0002-ui-design.md`, если решений много и они архитектурно значимы)
- **Пользователь явно согласовал** документ — без этого итерация не закрывается

**Связь с tasklist:** [tasks/iteration-05-design.md](tasks/iteration-05-design.md)

**Полезный результат:** итерация 6 (Frontend) пишется по утверждённым мокапам и палитре, а не «как получится». Явная точка согласования перед инвестицией в код — меньше переделок.

**Артефакты:** `docs/design.md` (или `docs/adr/0002-ui-design.md`), при необходимости — папка `docs/design/` с референс-скриншотами.

---

### Итерация 5а: Auth refactor — форма входа и разделение free/LLM

**Цель:** перевести API с Basic Auth на форму входа + cookie-сессию; разделить `POST /api/v1/scans` на бесплатную ветку (детерминированные правила, без auth) и ветку с расширенным анализом (`with_llm=true`, требует валидной сессии). После закрытия итерации фронт пишется уже под целевую модель доступа без переходных решений.

**Стартовый контекст:** [vision.md](vision.md) — разделы «Аутентификация и доступ», «Модель данных / состояние» (таблицы `users`, `sessions`), «Работа с LLM → Доступ к LLM-проверкам», «Сценарии работы пользователя» (Первое посещение, Нестандартные ситуации), «Конфигурация и секреты»; закрытая [iteration-04-api.md](tasks/iteration-04-api.md) как точка старта по коду.

**Критерии завершения (DoD):**
- Таблица `sessions` создаётся в `app/db.py` (`CREATE TABLE IF NOT EXISTS`, индекс по `expires_at`).
- `app/auth.py` переписан без `HTTPBasic`. Появляются: `create_session(login) -> session_id`, `delete_session(session_id)`, `get_user_by_session(session_id) -> str | None` (обновляет `last_seen_at`), `purge_expired_sessions()`, Depends `get_optional_user` для FastAPI.
- Новый `app/api/auth.py`: `POST /api/v1/auth/login` (200 + cookie), `POST /api/v1/auth/logout` (идемпотентный 204), `GET /api/v1/auth/me` (всегда 200 + `login: str | null`). Pydantic-модели `LoginRequest` (с min/max-length), `UserInfo`. На неверном пароле в login — 401 с единой формулировкой (без enumeration). В `app/main.py` — фоновая таска `_purge_sessions_loop` (раз в час).
- `app/api/scan.py`: убрана глобальная `dependencies=[Depends(get_current_user)]` на роутере; `POST /scans` принимает `{url: str, with_llm: bool = False}`; если `with_llm=true` без валидной сессии — 401. `GET /scans/{id}`, `/events`, `/report.pdf` публичны (UUID — достаточная защита для MVP).
- `ScanState` дополнен полем `with_llm: bool` (immutable, фиксируется при создании); `run_scan` принимает флаг keyword-only аргументом. В итерации 5а engine просто принимает и сохраняет флаг — семантических check-функций ещё нет, фильтровать нечего. Механизм отбора LLM-check'ов вводится в итерации 7.
- `app/config.py`: `BASIC_AUTH_REALM` удалён; добавлены `session_cookie_name`, `session_ttl_days`, `session_cookie_secure`. `.env.example` синхронизирован.
- `tools/create_user.py` вызывает `upsert_user_and_revoke_sessions` — смена пароля одной транзакцией гасит все активные сессии пользователя.
- `tests/test_auth.py` переписан: login → cookie → /me → logout, ошибка пароля, ошибка с истёкшей сессией, очистка истёкших сессий при login.
- `tests/test_api_scans.py` обновлён: анонимный POST /scans → 202 и работает, POST /scans с `with_llm=true` без cookie → 401, с cookie → 202; GET /scans/{id}, /events, /report.pdf публичны.
- End-to-end через `curl`:
  1. Анонимный POST `/scans` → SSE → PDF.
  2. `POST /auth/login` → cookie → `POST /scans {with_llm: true}` → SSE → PDF.
  3. `POST /auth/logout` → следующий `POST /scans {with_llm: true}` → 401.

**Связь с tasklist:** [tasks/iteration-05a-auth-refactor.md](tasks/iteration-05a-auth-refactor.md)

**Полезный результат:** API соответствует продуктовой модели «бесплатно всем / LLM-только-владельцу». Фронт итерации 6 пишется сразу под форму входа + тоггл `with_llm`, без переходного Basic Auth.

**Артефакты:** обновлённые `app/auth.py`, `app/db.py` (+`upsert_user_and_revoke_sessions`), `app/api/scan.py`, `app/scan_state.py`, `app/api/scan_worker.py`, `app/engine.py`, `app/config.py`, `app/main.py`, `tools/create_user.py`; новый `app/api/auth.py`; обновлённые `.env.example`, `tests/test_auth.py`, `tests/test_api_scans.py`, `tests/test_scan_worker.py`.

---

### Итерация 6: Frontend MVP

**Цель:** реализовать пользовательский UI поверх готового API по утверждённому в итерации 5 дизайну — полный сценарий «ввёл URL → увидел прогресс → получил отчёт → скачал PDF» работает в браузере.

**Стартовый контекст:** утверждённый [docs/design.md](design.md) и живой прототип [docs/design/preview.html](design/preview.html) из итерации 5; [vision.md](vision.md) — разделы «Сценарии работы пользователя» (поведение раскрытых карточек, нормализация URL, нестандартные ситуации), «Структура репозитория» (раскладка `frontend/`), «Технологии» → Frontend (Next.js + Tailwind, static export).

**Предусловия (унаследованы из итерации 5 — см. [docs/design.md § 15](design.md), и из итерации 5а):**

Перед стартом вёрстки фронта необходимо закрыть **три задачи**, без которых UI будет работать на хардкоде или на устаревшем контракте API:

- **ADR-0002 — расширение схемы корпуса** ([docs/laws/schema.md](laws/schema.md) + 15 YAML-файлов корпуса + пересборка `docs/laws/index.yml`):
  - На уровне закона: `short_description`, `icon` (Lucide-имя), `category` (одна из `privacy` / `cookies` / `advertising` / `consumer` / `info` / `copyright`).
  - На уровне `violations[]`: `evidence_template` — имя шаблона мини-превью.
- **`CorpusBundle.for_categories` — категоризация для шагов прогресса.** Решить: бэк публикует `step`-события (правка [app/engine.py](../app/engine.py) и [app/events.py](../app/events.py)) или UI группирует `violation_evaluated` на лету по полю `category`. От этого зависит контракт SSE-стрима.
- **Итерация 5а закрыта** — API использует cookie-сессии, `POST /scans` принимает `with_llm`, есть `GET /api/v1/auth/me`. Без этого фронту нечего вызывать для авторизованной ветки.

Эти три пункта должны быть первыми в tasklist'е итерации 6.

**Критерии завершения (DoD):**
- Скелет `frontend/`: Next.js 15 + Tailwind, `output: 'export'` в `next.config.mjs`, `pnpm build` собирается в `frontend/out/`
- Реализация соответствует утверждённым мокапам и палитре из `docs/design.md`
- Главная страница: инпут для URL + кнопка «Проверить», лёгкая клиентская валидация на пустоту/мусор
- Под CTA-карточкой — тоггл «Расширенный анализ»: disabled со ссылкой «Войти» для анонимного пользователя; активный (по умолчанию выкл.) для авторизованного. Значение тоггла уходит в `POST /api/v1/scans {with_llm}`
- Страница `/login` (Фаза 0 в `docs/design.md`): форма с inline-ошибкой, успех — редирект на `/`, сервер ставит cookie
- В шапке: кнопка «Войти» для анонимного, `<login>` + «Выйти» для авторизованного. Состояние определяется через `GET /api/v1/auth/me` при загрузке любой страницы (всегда 200; `login: null` → анонимная ветка, строка → авторизованная); logout дергает `POST /api/v1/auth/logout`
- Прогресс-страница: `EventSource` подключается к SSE, отрисовывает текущий шаг, счётчик найденных нарушений по severity
- Страница результата: список Finding'ов, **все карточки раскрыты по умолчанию**, кнопки «Свернуть все» / «Раскрыть все» сверху, индивидуальная сворачивалка у каждой карточки
- Если скан запущен без LLM — в результатах виден явный блок «Расширенный анализ доступен после входа» (даже при `inconclusive=0` от детерминированных проверок)
- Кнопка «Скачать PDF» дёргает `/report.pdf`, файл сохраняется с именем `legal-audit-<host>-<date>.pdf`
- Обработка нестандартных ситуаций: 401 на `with_llm=true` без сессии (мягкое предложение войти), недоступный сайт, таймаут, `inconclusive`-проверки (отображаются отдельной секцией)
- Сборка `pnpm build` → `frontend/out/` отдаётся FastAPI через `StaticFiles`
- Локальная dev-разработка работает в двух терминалах (`make dev` + `make dev-frontend` с проксированием `/api`)

**Связь с tasklist:** [tasks/iteration-06-frontend.md](tasks/iteration-06-frontend.md)

**Полезный результат:** есть рабочий продукт. На детерминированном движке покрытие ~65%, но end-to-end сценарий полностью пригоден для использования.

**Артефакты:** `frontend/src/app/`, `frontend/src/components/`, монтаж `StaticFiles` в `app/main.py`.

---

### Итерация 6б: Контекстный гейтинг и инверсная логика детекции

**Цель:** устранить системные ложные срабатывания детерминированного сканера, выявленные при прогоне по `https://habr.com/ru/feed/` (73 fail, большинство нерелевантны). Закрыть детерминированный слой до уровня «отчёт можно показать пользователю без оговорок про шум», до подключения LLM в итерации 7.

**Стартовый контекст:** [docs/tasks/iteration-06b-detection-fixes.md](tasks/iteration-06b-detection-fixes.md) — полный план с архитектурными решениями Р1–Р5, разбором 4 жалоб из исходного отчёта, mental-сценариями и known issues; [docs/laws/schema.md](laws/schema.md) (поля `applies_to`, формат detection); [app/checks.py](../app/checks.py), [app/engine.py](../app/engine.py), [app/corpus/models.py](../app/corpus/models.py).

**Корневые причины (из разбора прогона по habr.com):**

- Нет контекстного гейтинга — все 100 нарушений проверяются на любом сайте, включая нарушения о платежах, e-commerce, рекламе БАД на блог-сайтах.
- Инверсная семантика `required_keywords` для запрещённых ключей (`'купить табак'` срабатывает по их отсутствию — инверсия логики).
- Семантически случайные привязки sub-signals (CSP-заголовок → «утечка ПДн», ключевое слово «DPO» → «несвоевременное уведомление об инциденте»).
- 21 «Не определено» от 11 нереализованных заглушек, засоряющих отчёт.

**Критерии завершения (DoD):**

- В схему корпуса введено опциональное поле `applicability: tuple[ContextTag, ...]` на уровне Violation (закрытый словарь из 7 тегов: `ecommerce`, `payments`, `ad_content`, `ugc`, `media_18plus`, `child_audience`, `has_signing`). AND-семантика; пустой = «применимо всегда».
- В `PageSignal`/`SiteSignal` добавлено поле `prohibited_keywords` + универсальный обработчик `_check_prohibited_keywords` (fail при наличии ключа); Pydantic-валидатор запрещает совместное использование с `required_keywords`.
- В `CheckResult` и `Finding` добавлено поле `inconclusive_reason` (`check_not_implemented` / `context_dependent` / `evidence_missing`). `aggregate_or` различает stub-inconclusive и real-inconclusive с приоритетом real над stub.
- Новый модуль `app/context.py` с `ScanContext`, `detect_context` и 7 контекст-детекторами; парсинг HTML делается один раз и переиспользуется.
- `_evaluate_violation` возвращает `Finding | None`: `None` если нарушение не применимо к контексту ИЛИ если итог inconclusive + `check_not_implemented`. `run_scan` пропускает None из findings и SSE.
- В корпусе удалены 2 семантически нерелевантных sub-signals (`152-fz-incident-notification-missed.dpo_contact_missing`, `152-fz-data-breach.weak_security_headers`).
- 15 файлов корпуса размечены `applicability`-тегами по таблице из tasklist'а; инверсные `required_keywords` мигрированы на `prohibited_keywords` (3 случая в 38-ФЗ + 4 случая в 436-ФЗ).
- Новый ADR-0003 `docs/adr/0003-context-gating-and-inverse-keywords.md`.
- Regression-тест `tests/test_engine_regression.py` на фикстуре `habr-like-blog.html`: `failed_findings <= 10`, нет финдингов из 161-ФЗ/54-ФЗ/pp-2463, нет inconclusive с `check_not_implemented`.
- Ручной прогон по `https://habr.com/ru/feed/`: было 73 fail → стало ≤ 10 fail.

**Связь с tasklist:** [tasks/iteration-06b-detection-fixes.md](tasks/iteration-06b-detection-fixes.md)

**Полезный результат:** отчёт сканера перестаёт быть «шумной кучей» для нерелевантных сайтов — контекст определяет, какие нарушения применимы. Детерминированный слой становится контрактом, на который надёжно встраивается LLM в итерации 7.

**Артефакты:** новый `app/context.py`; правки `app/corpus/models.py`, `app/checks.py`, `app/engine.py`; 15 файлов `docs/laws/*.md` (разметка `applicability`, миграция инверсных ключей); `docs/laws/schema.md` (новые поля и словари); `docs/adr/0003-context-gating-and-inverse-keywords.md`; новые тесты `tests/test_context.py`, `tests/test_engine_regression.py` + 3 HTML-фикстуры; `frontend/src/lib/types.ts` (поле `inconclusive_reason` в TS-интерфейсе Finding).

**Демо (прогон по `https://habr.com/ru/feed/`):** total findings 100 → 32, fail 71 → 23 (-68%). Из 23 оставшихся: 7 — known issue `gk-rf-part-iv` (гиперширокие селекторы, отложено в итерацию 7), 16 — реальные применимые проверки (политика ПДн, GA без локализации, госязык, UGC-реестр). Все 4 исходные жалобы пользователя (DPO, CSP, эквайринг, missing-keywords запрещёнки) ушли. Гейтинг 161-ФЗ / 54-ФЗ / pp-2463 / 63-ФЗ / `gk-rf-offer` — 0 утечек. Заглушки и `context_dependent` — 0 в отчёте. Метрика «≤ 10 fail» не достигнута, но качественный состав остатка — реальные срабатывания, не шум.

**Замечание после демо (2026-05-15):** ручной прогон выявил карточку «Названия товаров на иностранном без перевода» (53-ФЗ) с evidence `account.habr.com/info/confidential/?hl=ru_RU` и текстом «failed to fetch policy». Причина — sub-signal `catalog_titles_latin` в YAML 53-ФЗ был привязан к чеку `text_length_threshold`, который проверяет длину страницы политики, а не латиницу. Проведена ревизия всех `check:`-привязок в корпусе, найдено 9 mismatch'ей (включая `card_data_in_cookies_or_storage` через `cookie_set_before_consent`, `no_https_redirect` через `http_status_check`, `parked_domain` через `http_status_check` и др.). Внесены правки: 2 sub-signal'а переведены на новые детерминированные функции `latin_only_in_selectors` и `latin_to_cyrillic_ratio`, 5 — на честные заглушки (`cookies_pan_storage_audit`, `http_security_audit`, `parked_domain_detection`, `offer_acceptance_audit`), 2 — удалены целиком (`anglicisms_review_against_dictionaries`, `refund_terms_too_short`). См. раздел «История изменений» в ADR-0003.

**Дополнение (2026-05-15, дочистка):** при повторном прогоне всплыло, что (а) sub-signal `button_text_latin_only` в 53-ФЗ работает через универсальный `_check_html_patterns_only` («нашли button → fail»), из-за чего бургер-кнопки без текста и иконки-ссылки давали ложноположительный fail; (б) violation `gk-iv-pirated-software-fonts` (high) ловил Google Fonts через `link[href*="fonts" i]`, противореча собственному recommendation; (в) аналогичные гиперширокие селекторы — во всём `gk-rf-part-iv-copyright.md`. Закрыто двумя движениями: `button_text_latin_only` привязан к свежесозданному `latin_only_in_selectors` (пропускает пустые элементы и элементы с кириллицей); ревизия `gk-rf-part-iv` свела 10 sub-signal'ов из 5 violations к 5 честным заглушкам (`image_attribution_audit`, `text_provenance_audit`, `media_embed_license_audit`, `trademark_use_audit`, `font_license_audit`). LLM в итерации 7 реализует каждую как семантическую check-функцию.

**Аудит реального медиа-сайта + класс-фиксы (2026-05-15, заход 7):** полный прогон по русскоязычному медиа-сайту дал 22 fail. Каждый размечен после поштучного разбора: 7 обоснованных, 11 ложноположительных, 4 пограничных. Ложные сгруппированы в 4 системных класса; починка одного класса закрывает несколько карточек разом. **Класс A** (nested-container fail на первом нерелевантном footer/header'е): инвертирована логика `_check_pattern_with_escape` для container-scope («хоть один с эскейпом → pass»), плюс удалены 5 избыточных footer/header page_signal'ов из 4 violations (152-fz-no-privacy-policy, 149-fz-no-owner-info, 436-fz-no-age-marking ×2, gk-iv-no-copyright-notice) — site_signal lookup того же violation уже корректно проверяет «есть ли раздел где-то на сайте». **Класс B** (UGC-trigger как «доказательство» нерегистрации в реестре): удалены page_signals `user_messages_feature` / `forum_or_board_engine` из 149-fz-ori-not-registered — applicability `[ugc]` уже триггерит violation, реальная проверка реестра — через `rkn_registry_lookup` stub. **Класс C** (гиперширокий `.promo` без `check:`): `banner_text_latin_only` привязан к `latin_only_in_selectors`. **Класс D** (`required_keywords` в plain-text главной вместо политики): удалён `policy_missing_required_sections` из 152-fz-policy-incomplete (детерминированно покрывается через `policy_too_short` / `text_length_threshold`). Точечно: `no_protection_level_in_policy` и `no_threat_model_disclosure` (pp-1119) переключены на `internal_documents_audit` — это внутренние документы оператора. `no_user_rules_published` (149-fz-social-network-not-registered) — на тот же stub. 5 lookup-чеков `gk-rf-part-iv` переведены на ранее введённые stubs (`image_attribution_audit`, `text_provenance_audit`, `media_embed_license_audit`, `trademark_use_audit`). Из `_REGULATED_GOODS_KEYWORDS` удалён ключ `«ставк»` — он давал ложный media_18plus в IT-/новостном контексте (где «ставки рефинансирования» / «зарплатные ставки»); сайты казино/букмекеров активируются через «казино» / «букмекер». Итог повторного прогона: 22 → 15 fail (-32%); 10 ложных ушли; появилось 3 новых валидных срабатывания (английский consent banner в `<h1>`, кнопка `Learn more`, ratio латиницы 0.72 на странице с большим количеством IT-тегов и англоязычного consent-баннера) — это и есть подлинные несоответствия 53-ФЗ.

**Открытое:** на старте этапа 6 миграции корпуса решаются open questions 1–6 из tasklist'а (граница тегов `ad_content`/`ugc`/`has_signing`, подход к «текстовому триггер+эскейп» в 38-ФЗ, тонкая настройка детектора `_detect_has_signing`).

**Известные ограничения, остающиеся после итерации (закрываются только LLM в итерации 7):**

- На медиа-сайтах со статьями про регулируемые товары (БАД, VPN, кредиты) тег `ad_content` активируется → `prohibited_keywords` может дать false positive «статья ≠ реклама».
- Аналогичная проблема для контентных запретов 436-ФЗ (`'ЛГБТ'`, `'наркотик'`, `'способы суицида'` в новостной статье — не пропаганда).
- Семантические проверки авторского права (атрибуция изображений, плагиат текстов, лицензии медиа, использование ТЗ в meta/h1/логотипах, легальность шрифтов) сведены к 5 stub-семантикам — реализация в итерации 7.

---

### Итерация 6в: Многостраничный обход сайта при сканировании

**Цель:** scanner перестаёт ограничиваться одной страницей — обходит ключевые внутренние (контакты, политика, обратная связь, регистрация, корзина, о компании), и engine агрегирует findings по всему набору страниц. Каждый Finding получает поле `page_url` — на какой странице найдено.

**Стартовый контекст:** [docs/tasks/iteration-06c-multipage-scan.md](tasks/iteration-06c-multipage-scan.md) — детальный план с решениями Р1–Р5; [app/scanner.py](../app/scanner.py), [app/engine.py](../app/engine.py).

**Корневая причина:** при ручном прогоне по habr.com выяснилось, что детектор PD-форм даёт inconclusive (форма не найдена на главной), хотя форма с правильным чекбоксом согласия живёт на `/ru/feedback/`. Аналогично 149-ФЗ «нет сведений о владельце» — данные оператора на `company.habr.com/ru/#contact`, не на главной. Текущая архитектура сканирует только URL, который дали в input'е, и не обходит внутренние страницы — большинство проверок получают неполное покрытие. Старый костыль `_find_policy_url` + httpx-fetch для политики ПДн уже подгружает одну дополнительную страницу мимо общего scanner-механизма, что подтверждает: нужен честный multi-page обход вместо разрозненных хаков.

**Критерии завершения (DoD):**

- Введён `ScanArtifacts(main: PageArtifacts, pages: tuple[PageArtifacts, ...], cookies, network_log)`. Cookies и network_log — на уровне ScanArtifacts (общие для сессии), не per-page.
- `app/scanner.py` отдаёт `ScanArtifacts` с `main` + 0-10 дополнительных страниц, обнаруженных эвристикой по ссылкам с главной.
- Новый модуль `app/discover.py` с функцией `discover_pages(main) -> list[str]`: ищет ссылки по ключевым словам в тексте/href (`контакт`, `политика`, `обратная связь`, `регистрация`, `корзина`, `о компании` + EN-аналоги), фильтр same-origin, лимит 10. Юнит-тесты ≥ 6 кейсов в `tests/test_discover.py`.
- `app/engine.py` оценивает page-сигналы на всех страницах (`scan.main + scan.pages`); site-wide сигналы (`cookie_set_before_consent`, `indexof_check`, TLS-проверки) — только на `scan.main`. Список site-wide checks вынесен в константу `_SITE_WIDE_CHECKS`.
- `Finding` содержит поле `page_url: str | None` — URL страницы, на которой получен best result (или None для site-wide).
- Унифицирован policy-fetch: `text_length_threshold`, `date_in_document`, `http_status_check` читают политику из `scan.pages`, а не дёргают httpx напрямую. Если страница политики не загружена скан-обходом — inconclusive `evidence_missing`.
- `frontend/src/lib/types.ts` и UI-карточка показывают «Найдено на странице: <url>».
- Прогон по `https://habr.com/ru/`: 152-fz no-consent на `/ru/feedback/` даёт корректный pass (форма с правильным чекбоксом); 149-fz no-owner-info обрабатывает контактную страницу корректно (с учётом same-origin-фильтра по хосту).
- Юнит-тесты: `tests/test_engine_multipage.py` (per-page агрегация, site-wide vs page-wide), `tests/test_discover.py` (выбор страниц по эвристике), все существующие тесты остаются зелёными.
- Новый ADR-0004 `docs/adr/0004-multipage-scanning.md` (решения Р1-Р5).

**Связь с tasklist:** [tasks/iteration-06c-multipage-scan.md](tasks/iteration-06c-multipage-scan.md)

**Полезный результат:** карточки нарушений перестают быть кривыми из-за того, что мы видим только главную. Реальные нарушения локализованы по конкретным страницам (полезно для пользователя — он понимает, где править). Костыль с httpx-fetch'ем политики ушёл — архитектура честная.

**Артефакты:** новый `app/discover.py`; правки `app/scanner.py` (ScanArtifacts), `app/engine.py` (per-page + page_url в Finding), `app/checks.py` (унификация policy-fetch); правки `frontend/src/lib/types.ts` и карточек findings; `docs/adr/0004-multipage-scanning.md`; новые тесты `tests/test_discover.py`, `tests/test_engine_multipage.py`.

**Открытое (закрывается на старте этапа 1):**

1. Поддомены (`company.habr.com` для `habr.com`) — на старте same-origin (только основной хост); поддомены через флаг в будущих итерациях.
2. Размер выборки — лимит 10 страниц, перформанс ≈ 30s при ~3s на страницу через Playwright.
3. SPA с lazy-load — `wait_until="load"` + short `networkidle` (как сейчас в `collect`); тяжёлые SPA — известное ограничение.

---

### Итерация 7: Гибридное LLM-покрытие

**Цель:** довести покрытие нарушений до ~90–95% за счёт семантических check-функций через GigaChat (primary) и YandexGPT (фоллбек).

**Предусловие:** итерация 6б закрыта. Контекстный гейтинг, `prohibited_keywords` и `inconclusive_reason` уже введены и работают — LLM-проверки заменяют заглушки (`rkn_registry_lookup`, `tls_audit`, `internal_documents_audit` и др.), которые в 6б скрыты, и закрывают остаточные false positives «контент ≠ реклама» для медиа-сайтов с `ad_content`-контекстом. Без 6б LLM работала бы поверх шумного детерминированного слоя и не имела бы стабильной точки замены заглушек.

**Стартовый контекст:** [vision.md](vision.md) — раздел «Работа с LLM» целиком (интерфейс провайдера, промпты, нормализация контента, ключ кэша, бюджет токенов, особенности GigaChat, обработка ошибок); [laws/schema.md](laws/schema.md) — поле `check` в детекции, контракт `applicability` и `prohibited_keywords` из 6б (расширение под semantic-проверки потребует ADR); [docs/tasks/iteration-06b-detection-fixes.md](tasks/iteration-06b-detection-fixes.md) — раздел «Не делаем в этой итерации» с явным списком, что LLM должна закрыть.

**Критерии завершения (DoD):**
- Семантические check-функции вызываются движком **только если** `ScanState.with_llm == True` (контракт зафиксирован в итерации 5а). Без флага — пропускаются молча, в SSE/finding'и не публикуются.
- Принят ADR на расширение схемы корпуса под семантические check-функции (новый тип `check` или поле `semantic_check`) — обновляется `docs/laws/schema.md`
- `app/llm/base.py` — интерфейс `LLMProvider` + `StructuredAnswer`
- `app/llm/gigachat.py` — `GigaChatProvider` с OAuth по `expires_at`, ретраями 5xx/429, распознаванием контент-модерации
- `app/llm/yandex.py` — `YandexGPTProvider`
- Таблица `llm_cache` добавляется в схему SQLite (в итерации 4 её сознательно не создавали)
- `app/llm/cache.py` — `CachedLLMProvider` поверх SQLite (`cache_key = sha256(prompt_text + normalized_content + model)`), нормализация контента, cache hit = `tokens_used: 0`
- Бюджет токенов на скан (`LLM_BUDGET_TOKENS_PER_SCAN`, default 50 000), проверка ДО вызова, иначе `inconclusive`
- 2–3 реальные семантические check-функции: например, «политика раскрывает цели обработки», «текст согласия корректный», «cookie-banner без dark pattern»
- Соответствующие промпты в `prompts/<prompt_id>.md`
- `inconclusive`-статус отображается в UI отдельной секцией и присутствует в PDF-отчёте с пометкой причины
- Логирование LLM-вызовов: только метаданные (`prompt_id`, `model`, `tokens_used`, `verdict`, `latency_ms`, `cache_hit`)

**Связь с tasklist:** [tasks/iteration-07-llm.md](tasks/iteration-07-llm.md)

**Полезный результат:** реальное покрытие законодательных требований выросло до уровня, при котором отчёт можно показывать клиенту/руководству без оговорок «детектор не нашёл — но может быть».

**Артефакты:** `app/llm/`, `prompts/*.md`, новый ADR в `docs/adr/`, изменения в `docs/laws/schema.md` и затронутых файлах корпуса.

**Открытое после 6б:**

- **Гибрид free + with_llm для 6 sub-signals «текстовый триггер + эскейп» в 38-ФЗ.** В 6б (open question 4) выбран минимальный путь — детерминированный движок возвращает `inconclusive_reason="context_dependent"` и engine скрывает эти findings из отчёта в обоих режимах. После реализации LLM в итерации 7 пересмотреть: нужен ли отдельный fallback-обработчик `_check_keyword_trigger_with_escape` для free-режима (детерминированный сигнал с шумом «контент ≠ реклама»), или достаточно того, что with_llm-режим закрывает эти sub-signals семантически, а free-юзер получает по ним тишину. Решение принять по статистике использования free-режима и feedback'у пользователей. Sub-signals: `38-fz-misleading-claims.superlative_without_proof`, `38-fz-misleading-claims.unverifiable_specific_claims`, `38-fz-bad-no-disclaimer.bad_product_card_no_disclaimer`, `38-fz-financial-services-no-disclosure.credit_ad_no_psk`, `38-fz-financial-services-no-disclosure.credit_ad_no_warning`, `38-fz-foreign-words-untranslated.excessive_foreign_words_in_ads`.
- **Метрика «fail ≤ 10» на habr.com из 6б не достигнута (по факту 23, или 16 без `gk-rf-part-iv` known issue).** Дальнейшее снижение требует либо LLM-проверок (отличать «политика есть, но неполная» от «политики нет», закрывать гиперширокие селекторы в `gk-rf-part-iv` семантикой), либо точечной переразметки корпуса с риском потерять охват на других сайтах. Подробности — в [docs/tasks/iteration-06b-detection-fixes.md](tasks/iteration-06b-detection-fixes.md) (раздел «Что не достигнуто и переносится дальше», пункты 1–3). На старте итерации 7 решить: оставить ли остаточные «честные» fails как есть (объяснимое поведение детерминированного слоя) или закрывать через LLM.
- **Гиперширокие селекторы в `gk-rf-part-iv-copyright`** (`img[src^="https://"]`, `title`, `link[href*="fonts"]`) — 7 fails на любом сайте. В 6б отмечены как known issue в [docs/adr/0003-context-gating-and-inverse-keywords.md](adr/0003-context-gating-and-inverse-keywords.md). В итерации 7 заменить на семантические LLM-проверки («есть ли на изображениях указание лицензии», «использует ли сайт чужой бренд в title как ключевой») либо удалить нарушения с пометкой «недетектируемо без многостраничной семантики».

---

### Итерация 8: Production-деплой на Beget VPS

**Цель:** поднять приложение на Beget VPS (510 ₽/мес) под HTTPS, чтобы можно было пользоваться им из любой точки и при необходимости удалять/пересоздавать инфраструктуру.

**Стартовый контекст:** [vision.md](vision.md) — разделы «Хостинг», «Docker», «Сборка и запуск» (production-сборка/запуск), «Деплой» (текущая заглушка — её и предстоит заполнить), «Конфигурация и секреты» (как .env попадает на VPS).

**Критерии завершения (DoD):**
- Multi-stage `Dockerfile`: `frontend-build` (Node 20 alpine, `pnpm build`) → `runtime` (`mcr.microsoft.com/playwright/python:v1.49.0-noble`, `uv sync`, копирование `app/`, `tools/`, `prompts/`, `docs/`, `frontend/out/`)
- `.dockerignore` исключает `.venv`, `node_modules`, `frontend/.next`, кэш
- `make docker-build` собирает образ, `make docker-run` запускает с `--env-file=.env`, volume `/data`, портом 8000
- Инструкция по развёртыванию в `docs/deploy.md` (или соответствующем разделе): создание VPS на Beget, установка Docker, certbot для Let's Encrypt, nginx как reverse-proxy с HTTPS на 443
- Скрипт обновления: `git pull && docker build && docker run` (или ручная последовательность с пояснениями)
- `--restart unless-stopped` для Docker — контейнер сам поднимается после ребута/падения
- Проверочный чек-лист: HTTPS работает; форма входа работает, cookie ставится с `Secure`-флагом и переживает обновление страницы; анонимный скан без `with_llm` проходит end-to-end; авторизованный скан с `with_llm=true` тоже; PDF скачивается; перезапуск контейнера не теряет пользователей, активные сессии и LLM-кэш

**Связь с tasklist:** [tasks/iteration-08-deploy.md](tasks/iteration-08-deploy.md)

**Полезный результат:** приложение доступно по своему URL под HTTPS; паттерн «развернул — попользовался — удалил» работает.

**Артефакты:** `Dockerfile`, `.dockerignore`, обновлённый раздел «Деплой» в [docs/vision.md](vision.md) или отдельный `docs/deploy.md`.
