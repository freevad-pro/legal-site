# Итерация 5а — Auth refactor: форма входа и разделение free/LLM

> Tasklist для [docs/plan.md](../plan.md), карточка итерации 5а.
> Статусы: 📋 → 🚧 → ✅ (закрыта 2026-05-14). По завершении остаётся как исторический след.

## Контракт DoD (из `plan.md`)

- [x] Таблица `sessions` создаётся в `app/db.py` (`CREATE TABLE IF NOT EXISTS`, индекс по `expires_at`)
- [x] `app/auth.py` переписан без `HTTPBasic`. Появляются: `create_session(login) -> session_id`, `delete_session(session_id)`, `get_user_by_session(session_id) -> str | None` (обновляет `last_seen_at`), Depends `get_optional_user` для FastAPI
- [x] Новый `app/api/auth.py`: `POST /api/v1/auth/login`, `POST /api/v1/auth/logout`, `GET /api/v1/auth/me`. Pydantic-модели `LoginRequest`, `UserInfo` (`login: str | None`). `/auth/me` всегда отдаёт 200; `null` означает анонимного посетителя. На неверном пароле в `/login` — 401 с единой формулировкой (без enumeration)
- [x] `app/api/scan.py`: убрана глобальная `dependencies=[Depends(get_current_user)]` на роутере; `POST /scans` принимает `{url: str, with_llm: bool = False}`; если `with_llm=true` без валидной сессии — 401
- [x] `GET /scans/{id}`, `/events`, `/report.pdf` остаются публичными (UUID — достаточная защита для MVP)
- [x] `ScanState` дополнен полем `with_llm: bool` (immutable, фиксируется при создании). Engine принимает флаг keyword-only (фильтрация семантических check-функций — задача итерации 7, в которой появятся сами функции)
- [x] `app/config.py`: `BASIC_AUTH_REALM` удалён; добавлены `session_cookie_name`, `session_ttl_days`, `session_cookie_secure` (default `False` для dev-простоты). `.env.example` синхронизирован
- [x] `tools/create_user.py` — вызывает `upsert_user_and_revoke_sessions` (одна транзакция UPSERT users + DELETE sessions), чтобы смена пароля гарантированно инвалидировала все старые сессии. Печатает в stderr количество отозванных сессий (только при `> 0`)
- [x] `tests/test_auth.py` переписан: login → cookie → /me → logout, ошибка пароля, ошибка с истёкшей сессией, очистка истёкших сессий, rolling TTL, revoke при upsert
- [x] `tests/test_api_scans.py` обновлён: анонимный POST /scans → 202 и работает, POST /scans с `with_llm=true` без cookie → 401, с cookie → 202; GET /scans/{id}, /events публичны
- [x] End-to-end через `curl`:
  1. Анонимный POST `/scans` → SSE → PDF
  2. `POST /auth/login` → cookie → `POST /scans {with_llm: true}` → SSE → PDF
  3. `POST /auth/logout` → следующий `POST /scans {with_llm: true}` → 401

## Ключевые решения

- **Cookie:** имя из `settings.session_cookie_name`, `httponly=True`, `secure=settings.session_cookie_secure`, `samesite="lax"`, `path="/"`. `max_age` = `SESSION_TTL_DAYS * 86400`. SameSite=Lax совместима с переходом по ссылке `/login` и не открывает CSRF на POST/scans (мы и так требуем `application/json` body, а простой form-POST не пройдёт).
- **session_id:** `secrets.token_urlsafe(32)` — 256 бит энтропии. Хранится в БД как есть; cookie тоже содержит plain session_id (это нормально для server-side сессий, ценность утечки cookie такая же, как утечки сессии).
- **Rolling TTL:** при каждом успешном чтении сессии через `get_user_by_session` обновляются `last_seen_at` и `expires_at = now() + SESSION_TTL_DAYS`. Так пользователь, активный раз в неделю, не разлогинивается через 30 дней календарной давности первого входа.
- **Очистка истёкших сессий:** ленивая внутри `login` плюс фоновая таска `_purge_sessions_loop` в `app/main.py` (раз в час, по образцу `_purge_loop` для scan registry). Без фоновой чистки БД росла бы у долго не входящего пользователя — это дешёвая страховка, инфраструктура lifespan-задач уже есть.
- **Rate-limit на login:** отложен. Для MVP с 1–2 пользователями и без публичной регистрации защищаться от brute-force нерелевантно. Если когда-то понадобится — отдельный ADR, точка вставки понятна.
- **Все SQLite-операции через `asyncio.to_thread`** — стиль уже устоялся в итерации 4 для `users`. Никакого `aiosqlite`.
- **`ScanState.with_llm`** — immutable-поле, проставляется в `POST /scans`, доезжает до `run_scan(..., with_llm=...)`. В итерации 5а engine только принимает флаг и нигде не использует — семантических check-функций ещё нет, фильтровать нечего. Решение «как именно engine отбирает LLM-check'и» откладываем на итерацию 7: там вводится `app/llm/` и ADR на расширение схемы корпуса (см. карточку 7 в `plan.md`), и тогда же логично решить — атрибут на функцию, отдельный реестр, поле в YAML или что-то ещё. Здесь, в 5а, мы только фиксируем контракт API и контракт engine, чтобы 7 включилась без правки API.
- **`logout` удаляет одну сессию** (ту, что в cookie), а не «все сессии этого пользователя». Если пользователь хочет «выйти везде» — это будущая фича; в MVP не нужно, у нас не более 1–2 одновременных сессий.
- **`tools/create_user.py` гасит все сессии пользователя при upsert'е.** Смена пароля — это типичный отклик на «возможно, скомпрометирован»; оставлять прежние session_id валидными до конца их TTL противоречит самой причине смены. Поэтому upsert по `users` атомарно сопровождается `DELETE FROM sessions WHERE user_login = ?`. Для нового пользователя это no-op.
- **Ошибка на login — единая формулировка** «Неверный логин или пароль» и для несуществующего логина, и для неверного пароля. В логе на `WARNING` — только факт «failed login attempt» без логина в открытом виде, чтобы не давать enumeration через логи.
- **Единственный Depends `get_optional_user`:** возвращает `str | None`. Без cookie или с истёкшей — `None`, никакого 401. Используется в `POST /scans` (чтобы решить, разрешать `with_llm=true` или вернуть 401 явно), в `GET /auth/me` (200 + `{login: None}` для анонимного) и в `POST /auth/logout` (логирование). Отдельной `require_user`-фабрики нет — единственным «требовательным» местом был logout, но он сделан идемпотентным.
- **`logout` идемпотентен:** всегда возвращает 204. Без cookie тоже 204 — фронту не нужно различать «уже разлогинен» и «успешно разлогинились». `delete_cookie` ставится с тем же набором атрибутов (`httponly`, `secure`, `samesite=lax`, `path=/`), что и `set_cookie` — иначе строгие реализации браузеров не сматчат cookie на удаление.
- **Удаление BASIC_AUTH_REALM:** убирается из `Settings`, из `.env.example`; в `tests/conftest.py` ничего не зависело. Если найдётся импорт — удаляется заодно.

## Пошаговый план (по этапам)

> Этапы выполняются последовательно, каждый валидируется `make lint && make test`. Финальный коммит — один на всю итерацию (по [feedback_one_commit_per_iteration](../../README.md)).

1. **Схема БД и конфиг.**
   - `app/db.py`: добавить `CREATE TABLE IF NOT EXISTS sessions(...)` + `CREATE INDEX IF NOT EXISTS idx_sessions_expires`. Утилиты `insert_session`, `select_session`, `update_session_seen`, `delete_session_by_id`, `delete_expired_sessions` — все синхронные, обёртываются в `to_thread` на уровне `auth.py`.
   - `app/config.py`: убрать `basic_auth_realm`; добавить `session_cookie_name: str = "legal_site_session"`, `session_ttl_days: int = 30`, `session_cookie_secure: bool = True`.
   - `.env.example`: убрать `BASIC_AUTH_REALM`, добавить три новых.

2. **`app/auth.py` — переписать.**
   - Удалить `HTTPBasic`, `HTTPBasicCredentials`, `get_current_user`.
   - Добавить `create_session(login) -> session_id`, `delete_session(session_id)`, `get_user_by_session(session_id) -> str | None` (внутри — обновление `last_seen_at`, `expires_at`).
   - Добавить `purge_expired_sessions()` — точечный `DELETE FROM sessions WHERE expires_at < ?`.
   - Depends-фабрика: `get_optional_user(request: Request) -> str | None` (читает cookie, валидирует). Отдельный `require_user` не нужен — единственное место, где он напрашивался (`/auth/logout`), сделано идемпотентным.
   - `verify_password` / `hash_password` оставить как есть (используются в `tools/create_user.py` и в новом `/auth/login`).

3. **`app/api/auth.py` — новый модуль с тремя эндпоинтами.**
   - Pydantic: `class LoginRequest(BaseModel): login: str; password: str` и `class UserInfo(BaseModel): login: str | None`.
   - `POST /api/v1/auth/login {login, password}`: проверяет bcrypt-хэш через `get_user_password_hash` + `verify_password`. На успехе — `purge_expired_sessions()`, `create_session(login)`, `response.set_cookie(...)` с параметрами из `settings`. Возвращает `UserInfo(login=login)`. На любой ошибке (нет пользователя / неверный пароль) — `HTTPException(401, "Неверный логин или пароль")`.
   - `POST /api/v1/auth/logout` (status 204, без тела): `Depends(get_optional_user)`. Читает `session_id` из cookie — если есть, `delete_session(session_id)`. `response.delete_cookie(...)` с теми же `httponly`/`secure`/`samesite`/`path`, что и `set_cookie`. Логируем `INFO "logout ok: %s"` только если user не None — иначе тихий 204 (бесплатный анон-вызов в логи не пишем).
   - `GET /api/v1/auth/me`: `Depends(get_optional_user)` → всегда 200, возвращает `UserInfo(login=user)` (поле `None` для анонимного посетителя). Фронту проще: один и тот же контракт для обеих веток.
   - Регистрация роутера в `app/main.py`.

4. **`app/api/scan.py` — снять глобальный auth, добавить ветку `with_llm`.**
   - Удалить `dependencies=[Depends(get_current_user)]` с `APIRouter(prefix="/api/v1")`.
   - В Pydantic-теле для `POST /scans` добавить `with_llm: bool = False`.
   - В обработчике: `user = Depends(get_optional_user)`. Если `body.with_llm and user is None` — `HTTPException(401, "Расширенный анализ доступен только после входа")`.
   - Создание `ScanState`: передать `with_llm=body.with_llm`.
   - `GET /scans/{id}`, `/events`, `/report.pdf` — без Depends на auth.

5. **`ScanState.with_llm` и engine.**
   - В `app/scan_state.py`: добавить `with_llm: bool` в dataclass; в `ScanRegistry.create_scan` — обязательным kwarg'ом.
   - В `app/scan_worker.py` / `app/engine.py`: пробросить `with_llm` в `run_scan(..., *, with_llm: bool)` — keyword-only, чтобы не сломать CLI и существующие тесты. В итерации 5а engine флаг **только принимает и сохраняет**, никакой логики «пропускать функции» не добавляет — семантических check-функций пока нет, фильтровать нечего. Реальный механизм отбора («что считать LLM-check'ом и как его опускать») вводится в итерации 7 вместе с ADR на расширение схемы корпуса и появлением `app/llm/`. Здесь мы только бронируем контракт API и контракт engine.

6. **`tools/create_user.py` — отзыв сессий.**
   - В функцию upsert'а пользователя добавить второй шаг: `DELETE FROM sessions WHERE user_login = ?` в той же транзакции, что и `INSERT … ON CONFLICT … DO UPDATE` по `users`.
   - Получить число удалённых строк через `cursor.rowcount` и при `> 0` напечатать в stderr: `«Сброшено активных сессий: N»` (для feedback'а владельца).
   - Покрыть тестом в `tests/test_auth.py`: создать пользователя, залогиниться, ещё раз вызвать `upsert_user` с новым паролем — старая сессия должна стать невалидной.

7. **Тесты.**
   - `tests/test_auth.py` — полностью переписать. Сценарии: login happy → cookie выставлена → /me 200 с правильным login; login wrong password → 401, cookie нет; /me без cookie → 200 `{"login": null}`; logout с cookie → 204 + cookie удалена + сессия пропала из БД; **logout без cookie → 204 (идемпотентно)**; истёкшая сессия → /me `{"login": null}`, запись чистится при login и фоновой purge.
   - `tests/test_api_scans.py` — обновить: POST анонимный → 202; POST `with_llm=true` без cookie → 401; POST `with_llm=true` с cookie → 202; GET /scans/{id}/events без cookie → стрим (200/SSE); GET /scans/{id}/report.pdf без cookie → 200 PDF. Старый сценарий «401 без auth» удалить.
   - В `tests/conftest.py` — фикстура `authed_client` (TestClient после login) и `anon_client`. Переопределить `settings.session_cookie_secure = False` для TestClient (http://testserver).

8. **Финальная сверка и e2e.**
   - `make lint && make test && make corpus` — зелёные.
   - E2E curl-сценарий из DoD выше.
   - Перевод статуса итерации в [plan.md](../plan.md) `🚧 → ✅`.

## Fallback

- **Cookie не ставится в `TestClient`** (Starlette валится по `secure=true` на http://testserver) → в `tests/conftest.py` явно установить `settings.session_cookie_secure = False` через `monkeypatch.setattr`. Использовать тот же финт, что в итерации 4 для `httpx.AsyncClient`.
- **SameSite=Lax ломает SSE** — теоретически EventSource на той же origin'е работать должен; если в проде разные субдомены — потребуется `SameSite=None; Secure` (отдельный ADR на момент деплоя). В dev/проде на одной origin'е — лака достаточно.
- **`delete_cookie` не удаляет cookie с другим `secure`-флагом** — Starlette при `delete_cookie` использует тот же набор атрибутов, что и при `set_cookie`. Проверить: в тесте после logout cookie должна исчезнуть из jar клиента.
- **bcrypt.checkpw с istёкшим хэшем (формат < 2y)** — bcrypt 4.x не понимает `$2$`; в `tools/create_user.py` уже используется `bcrypt.hashpw` с `$2b$`, проблема возможна только при импорте старых хэшей. Для MVP неактуально (никаких импортов нет).

## Verification (демо)

```bash
make install
make corpus
make lint
make test
make user LOGIN=demo  # интерактивно ввести пароль
make dev
```

В другом терминале:

```bash
# 1) Анонимный скан — должен работать без auth
curl -X POST http://127.0.0.1:8000/api/v1/scans \
     -H 'content-type: application/json' \
     -d '{"url":"example.ru"}'
# → 202 {"scan_id":"<uuid>"}

# 2) Попытка расширенного без cookie → 401
curl -X POST http://127.0.0.1:8000/api/v1/scans \
     -H 'content-type: application/json' \
     -d '{"url":"example.ru","with_llm":true}'
# → 401

# 3) Логин — ставит cookie в jar
curl -c jar.txt -X POST http://127.0.0.1:8000/api/v1/auth/login \
     -H 'content-type: application/json' \
     -d '{"login":"demo","password":"<pwd>"}'
# → 200 {"login":"demo"}, в jar.txt cookie legal_site_session

# 4) /me с cookie
curl -b jar.txt http://127.0.0.1:8000/api/v1/auth/me
# → 200 {"login":"demo"}

# 4а) /me без cookie — тот же 200, login=null
curl http://127.0.0.1:8000/api/v1/auth/me
# → 200 {"login":null}

# 5) Расширенный скан с cookie
curl -b jar.txt -X POST http://127.0.0.1:8000/api/v1/scans \
     -H 'content-type: application/json' \
     -d '{"url":"example.ru","with_llm":true}'
# → 202 {"scan_id":"<uuid>"}

# 6) SSE — публичный
curl -N http://127.0.0.1:8000/api/v1/scans/<uuid>/events
# → буфер истории + live до done/error

# 7) PDF — публичный
curl -o report.pdf http://127.0.0.1:8000/api/v1/scans/<uuid>/report.pdf
# → файл legal-audit-example.ru-YYYY-MM-DD.pdf

# 8) Logout
curl -b jar.txt -c jar.txt -X POST http://127.0.0.1:8000/api/v1/auth/logout
# → 204, в jar.txt cookie удалена

# 9) После logout — снова 401 на расширенном
curl -b jar.txt -X POST http://127.0.0.1:8000/api/v1/scans \
     -H 'content-type: application/json' \
     -d '{"url":"example.ru","with_llm":true}'
# → 401
```

**Контрольные точки:**
- POST /scans без auth и без `with_llm` — 202, скан стартует.
- POST /scans с `with_llm=true` и без cookie — 401, никакого `ScanState` не создаётся.
- POST /auth/login с неверным паролем — 401, cookie не ставится.
- /auth/me без cookie — 200 `{"login": null}`; с валидной — 200 `{"login": "<имя>"}`.
- /auth/logout удаляет именно эту сессию из БД; другие сессии того же пользователя (если есть) не трогаются.
- В БД таблица `sessions` существует, после logout — соответствующая строка удалена.
- `SESSION_COOKIE_SECURE=false` в `.env` локально не ломает регистрацию cookie на http://127.0.0.1.

## Открытое (вне MVP)

- **Rate-limit на login** — отдельный ADR, когда понадобится. Сейчас 1–2 пользователя, brute-force нерелевантен.
- **«Выйти на всех устройствах»** — будущая фича; пока `logout` удаляет только текущую сессию.
- **CSRF-токен для POST /auth/login** — пока не нужен (форма submit'ится через JSON-fetch той же origin'ы, SameSite=Lax). Если появится отдельный домен/мобильный клиент — отдельный ADR.
- **Audit-лог входов** — отдельная таблица `auth_events`, опционально; в MVP полагаемся на `INFO`-логи stdout.
