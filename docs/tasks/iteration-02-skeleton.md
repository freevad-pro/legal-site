# Итерация 2 — Каркас приложения и инструментарий

> Tasklist для [docs/plan.md](../plan.md), карточка итерации 2 («Каркас приложения и инструментарий»).
> Статусы: 📋 → 🚧 → ✅. По завершении итерации этот файл остаётся как исторический след.

## Контракт DoD (из `plan.md`)

- [x] `pyproject.toml` + `uv.lock`, виртуальное окружение через `uv`
- [x] `app/main.py` с FastAPI и эндпоинтом `GET /health` → `{"status": "ok"}`
- [x] `Makefile` с целями: `install`, `dev`, `lint`, `fmt`, `test`, `corpus`
- [x] `make corpus` запускает `tools/rebuild_index.py`, зелёный на текущем корпусе
- [x] `ruff` + `mypy` сконфигурированы (mypy строгий для `app/` и `tools/`)
- [x] `pytest` со скелетом `tests/` и хотя бы одним работающим тестом
- [x] `.env.example`, `.gitignore`, корневой `README.md`

## Ключевые решения

- **git init** — да, плюс первый локальный коммит. Без push.
- **Зависимости** — минимум на итерацию 2 (KISS): `fastapi`, `uvicorn[standard]`, `pydantic`, `pydantic-settings`, `pyyaml`; dev — `ruff`, `mypy`, `pytest`, `httpx`, `types-PyYAML`.
- **mypy** — `strict = true` сразу для `app/` И `tools/`.
- **Первый тест** — `TestClient` → `GET /health`.
- **Точка конфигурации** — всё в `pyproject.toml` (без отдельных `ruff.toml`/`mypy.ini`/`pytest.ini`).

## Пошаговый план

1. **Очистка**: удалить пустой `adr/` в корне (содержимое в [docs/adr/](../adr/)).
2. **Git**: `git init -b main`, положить `.gitignore`.
3. **Tasklist + статус**: создать этот файл, статус итерации 2 в `plan.md` поменять `📋 → 🚧`.
4. **Python окружение**: `.python-version` (`3.12`), `pyproject.toml` (deps + ruff/mypy/pytest секциями), `uv sync` → `uv.lock` + `.venv/`.
5. **Скелет `app/`**: `__init__.py`, `config.py` (Pydantic Settings — `log_level`, `corpus_path`), `api/__init__.py`, `api/health.py` (`GET /health`), `main.py` (регистрация роута + `logging.basicConfig`).
6. **Тесты**: `tests/__init__.py`, `tests/conftest.py` (фикстура `client` через `TestClient`), `tests/test_health.py`.
7. **Makefile**: цели `install`, `dev`, `lint`, `fmt`, `test`, `corpus`.
8. **Аннотации `tools/`**: прокинуть типы под `mypy --strict`. Если объём правок неожиданно большой — fallback-override (см. ниже).
9. **Документация**: `.env.example` (`LOG_LEVEL`, `CORPUS_PATH`), корневой `README.md` (как поднять локально).
10. **Verification**: пройти все семь пунктов чек-листа ниже.
11. **Закрытие**: статус итерации 2 в `plan.md` `🚧 → ✅`, отметка демо.
12. **Первый коммит**: `chore: scaffold app, tooling and dev environment (iteration 2)`.

## Fallback: если mypy strict на `tools/` тяжелее ожидаемого

При >30 замечаниях или необходимости ломать форму кода ради типов — даём `tools/` локальный override в `pyproject.toml`:

```toml
[[tool.mypy.overrides]]
module = ["tools.*"]
disallow_any_explicit = false
disallow_untyped_calls = false
```

— mypy всё ещё жёстко проверяет, но без полного strict. Возврат к полному strict для `tools/` — отдельной задачей, фиксируется в «открытое».

## Verification (демо)

```bash
make install
uv run python -c "import fastapi, pydantic_settings, yaml, pytest"
make corpus
make lint
make test
make dev      # в другом терминале:
curl http://127.0.0.1:8000/health    # → {"status":"ok"}
```

Семь пунктов зелёные — итерация закрывается.

## Демо (по факту)

Прогон 2026-05-14 на Windows (GNU Make 4.4.1, uv 0.8.13, Python 3.12):

```
make install   → uv sync, 35 пакетов
smoke import   → fastapi, pydantic_settings, yaml, pytest — OK
make corpus    → index.yml: 15 законов, 3 обзора, 100 нарушений, integrity OK
make lint      → ruff All checks passed + mypy Success (7 source files)
make test      → 1 passed in 0.03s
make dev       → Uvicorn running on 127.0.0.1:8000
curl /health   → {"status":"ok"}
```

Все 7 пунктов зелёные.

## Открытое

- (нет)
