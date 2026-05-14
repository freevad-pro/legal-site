# Итерация 3 — Детерминированный движок (CLI-MVP)

> Tasklist для [docs/plan.md](../plan.md), карточка итерации 3.
> Статусы: 📋 → 🚧 → ✅. По завершении остаётся как исторический след.

## Контракт DoD (из `plan.md`)

- [x] `app/corpus/models.py` — Pydantic v2 модели по [schema.md](../laws/schema.md)
- [x] `app/corpus/loader.py` — парсит корпус, валидирует, отдаёт иммутабельный `CorpusBundle`
- [x] `app/scanner.py` — Playwright собирает артефакты страницы (DOM, cookies, headers, network)
- [x] `app/checks.py` — реестр check-функций + базовые реализации для `page_signals` и `site_signals`
- [x] `app/engine.py` — оркестратор: scanner → проход по `violations` → список `Finding`
- [x] CLI: `uv run python -m app.scan <url>` печатает JSON с Finding'ами в stdout
- [x] Тесты: парсер корпуса и реестр check-функций (НЕ FastAPI, НЕ Playwright)
- [x] На эталонном 152-ФЗ детектируются 8 из 9 нарушений (9-е — `inconclusive` по плану)

## Ключевые решения

- **Pydantic v2, frozen-модели.** `PageSignal`/`SiteSignal` — `extra="allow"`: разные типы сигналов имеют разные доп. поля (`expected_status`, `min_chars`, `keywords`, `combine`, ...). Доступ к ним через `signal.model_extra`.
- **Корпус читается из `.md` через `python-frontmatter`** (не из сгенерированного `index.yml`). `tools/rebuild_index.py` остаётся как валидатор/индексатор.
- **`CorpusBundle.model_validator(mode="after")`** закрывает дыру в `rebuild_index.py`: глобальная уникальность `violation.id` + резолв `related[]` / `references_in_common[]`.
- **Scanner = только главная страница.** Вторичные страницы (политика) скачиваются через `httpx.Client` внутри check-функций. Playwright не нужен для статической HTML-выборки.
- **Check-функции — синхронные.** Engine async только из-за scanner (один `await`). HTTP внутри check `to_thread` не оборачиваем — в итерации 3 параллельности нет.
- **Универсальные обработчики** для сигналов без `check`: `html_patterns`, `required_absent`, `required_keywords`, `required_headers`, `required_protocol`. Объединяются OR.
- **`required_absent` со скоупом:** если все `html_patterns` — контейнерные теги (`footer|header|main|body|nav|article|section|aside`), `required_absent` ищется внутри найденных контейнеров. Иначе — по всему документу.
- **`required_keywords` источник — всегда plain-text главной** (итерация 3). Поиск в политике — отдельная check-функция (`text_length_threshold`, `date_in_document`).
- **7 именных check-функций реализуем:** `link_near_form_to_privacy`, `lookup_pages_by_keywords`, `http_status_check`, `text_length_threshold`, `date_in_document`, `cookie_set_before_consent`, `indexof_check`. Общий helper `_find_policy_url`.
- **11 заглушек** (`_not_implemented` → `inconclusive`): `rkn_registry_lookup`, `form_action_geo`, `ip_geolocation`, `api_endpoint_scan`, `internal_documents_audit`, `tls_audit`, `traffic_threshold`, `blocklist_status`, `product_card_audit`, `notification_mechanism_audit`, `prohibited_content_dictionary_match`.
- **`combine`-сигналы** → `inconclusive` с пометкой (реализация — итерация 6+).
- **OR-агрегация** сигналов внутри violation: `fail` если хоть один `fail`, `pass` если все `pass`, иначе `inconclusive`.
- **CLI сам конфигурит logging в stderr** (не наследует от `app/main.py`).

## Пошаговый план (по коммитам)

1. **`feat(corpus): pydantic models, loader and integrity checks`** — `app/corpus/{__init__,models,loader}.py`. 9 классов (`Source`, `Penalty`, `PageSignal`, `SiteSignal`, `Detection`, `Violation`, `ReviewLogEntry`, `Law`, `CorpusBundle`). Фикстуры `tests/fixtures/laws/{good,bad_*}/`. Тесты: `test_corpus_models.py`, `test_corpus_loader.py`, `test_corpus_loader_real.py` (sanity на боевом корпусе). Deps: `python-frontmatter`.
2. **`feat(checks): registry and universal pattern detectors`** — `app/checks.py` с `CheckResult`, REGISTRY (пока только заглушки), 5 универсальных обработчиков, `aggregate_or`, `_find_policy_url`. Фикстуры `tests/fixtures/html/*.html`. Deps: `beautifulsoup4`, `soupsieve`, `types-beautifulsoup4` (dev), поднять `httpx` в основные.
3. **`feat(checks): named functions for 152-fz coverage`** — реализация 7 именных check-функций + `_fetch_text`. Тесты с моками httpx через `monkeypatch`.
4. **`feat(scanner): playwright page collector`** — `app/scanner.py` (`PageArtifacts`, `Cookie`, `NetworkEntry`, `collect`, `ScanError`). Новые поля `app/config.py`: `scan_timeout_seconds`, `user_agent`. Sync `.env.example`. README про `playwright install chromium`. Deps: `playwright`.
5. **`feat(engine,cli): orchestrator, ScanResult, app.scan command`** — `app/engine.py` (Finding, ScanResult, run_scan, OR-агрегация). `app/scan.py` (CLI, `normalize_url`, logging в stderr). `Makefile` цель `scan`. `test_engine.py`. README раздел «CLI».
6. **`chore(plan): close iteration 3`** — статус 🚧→✅, заполнить «Демо (по факту)», `verification` снапшот.

Каждый коммит — самодостаточный, `make lint && make test` зелёное. Сообщения коммитов согласовываются с пользователем до `git commit`.

## Fallback

- **Whitelist контейнеров для `required_absent`-скоупа хрупкий.** Если `html_patterns=['footer.cls']` — наш голый-тег-whitelist не сработает. Расширяем эвристикой: «контейнер» = селектор, первый токен которого совпадает с whitelist'ом. Если и это сломается — все сигналы → `inconclusive` (зафиксировать в «Открытое»).
- **`_find_policy_url` не нашёл политику** → три зависимых check (`http_status_check`, `text_length_threshold`, `date_in_document`) возвращают `inconclusive` — это нормальное поведение.
- **mypy strict для `app/checks.py`** с `Callable` и `model_extra: dict[str, Any]` может требовать локальный override (`disallow_any_explicit = false` только для `app.checks`). Сначала пробуем `TypeAlias` + `Protocol`.
- **Демо < 5 fail на 152-ФЗ** — итерацию не закрываем; проверяем (1) фикстуру `bad-site.html`, (2) Content-Type локального сервера, (3) скоуп `required_absent`.

## Verification (демо)

```bash
make install
uv run playwright install chromium
make corpus          # sanity: 15 законов, 100 нарушений, integrity OK
make lint            # ruff + mypy (strict)
make test            # все тесты зелёные

# Локальное демо на синтетической фикстуре:
# PowerShell:
$srv = Start-Process -PassThru uv -ArgumentList 'run','python','-m','http.server','8765','--directory','tests/fixtures/html'
make scan URL=http://localhost:8765/bad-site.html | tee scan-demo.json
Stop-Process -Id $srv.Id
# bash/zsh:
#   uv run python -m http.server 8765 --directory tests/fixtures/html &
#   make scan URL=http://localhost:8765/bad-site.html | tee scan-demo.json
#   kill %1
```

**Контрольные точки в `scan-demo.json`:**
- `findings` ровно 100 элементов.
- Минимум 5 (цель — 8) findings со `status: "fail"` имеют `law_id: "152-fz"`.
- Все 152-fz findings — `fail` или `inconclusive` (не `pass`).
- `error: null`.

## Демо (по факту)

Прогон 2026-05-14 на Windows (Python 3.12.11, uv 0.8.13, Playwright 1.59.0,
Chromium 147.0.7727.15):

```
make install                                      → uv sync, 40 пакетов
uv run playwright install chromium                → Chrome v1217, FFmpeg, headless-shell
make corpus                                       → 15 законов, 100 нарушений, integrity OK
make lint                                         → ruff All checks passed + mypy 14 source files OK
make test                                         → 71 passed in 0.5s

# Локальное демо на синтетической «плохой» фикстуре:
Start-Process uv ... http.server 8765 --directory tests/fixtures/html
uv run python -m app.scan http://localhost:8765/bad-site.html > scan-demo.json
EXIT=0
```

Контрольные точки `scan-demo.json` (через `python -c`):
- `findings`: **100** (по числу нарушений в корпусе) ✓
- `error`: `None` ✓
- 152-fz: **8 fail + 1 inconclusive** ✓ (целевое значение растянутого DoD)
- inconclusive — `152-fz-no-rkn-notification` (нет API РКН и ОГРН на входе)
- Глобально по корпусу: 71 fail, 25 inconclusive, 4 pass

Все 8 пунктов DoD зелёные, цели достигнуты.

## Открытое (в добавление к плану)

- **`amount_max: 0` как маркер «штраф без верхней границы»** — антипаттерн
  в корпусе (16 вхождений). В рамках итерации 3 поправлены только 5
  ломающих случаев (`amount_min > 0, amount_max: 0` → `amount_max: null`
  в `54-fz-cash-registers.md` и `161-fz-payment-system.md`). Остальные 11
  (`amount_min: 0, amount_max: 0` в `gk-rf-part-iv-copyright.md`,
  `63-fz-electronic-signature.md`, `242-fz-data-localization.md`,
  `54-fz-cash-registers.md`, `161-fz-payment-system.md`) — также семантически
  неидеальны, но формально проходят валидацию. Отдельная подзадача
  по гигиене корпуса.

- **Невалидные CSS-селекторы в корпусе** (`:contains("кириллица")` —
  deprecated синтаксис; `text:…` без экранирования двоеточия). В engine
  они теперь обрабатываются `_safe_select` через WARNING + пустой матч,
  но сами селекторы в корпусе стоит привести к актуальному
  `:-soup-contains` или иной форме. Затрагивает:
  `2300-1-consumer-protection.md`, `161-fz-payment-system.md`,
  `gk-rf-part-iv-copyright.md`, `pp-2463-sale-rules.md`,
  `38-fz-advertising.md`. Отдельная подзадача.

- **`review_log` с не-структурным элементом** в `63-fz-electronic-signature.md`
  поправлен — meta-комментарий перенесён в `verification_notes`. Аналогичные
  случаи в других файлах не обнаружены, но при следующем расширении корпуса
  стоит проверить.

## Открытое (по плану итерации, без изменений)

- **Многостраничный обход через Playwright** — итерация 4.
- **Авто-категоризация сайтов** (ecommerce/landing/blog) и `CorpusBundle.for_categories()` — итерация 5+.
- **`combine`-сигналы** → `inconclusive`. Реализация композиции — итерации 6–7.
- **`required_keywords` source = политика** — итерация 6+ (поле `source` в schema).
- **11 check-функций как заглушки** (`rkn_registry_lookup`, `form_action_geo`, `ip_geolocation`, `api_endpoint_scan`, `internal_documents_audit`, `tls_audit`, `traffic_threshold`, `blocklist_status`, `product_card_audit`, `notification_mechanism_audit`, `prohibited_content_dictionary_match`) — итерации 6–7.
- **Скриншоты для evidence в PDF** — итерация 4.
- **Семантические LLM-проверки** — итерация 7.
