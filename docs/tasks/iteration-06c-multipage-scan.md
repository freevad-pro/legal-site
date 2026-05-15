# Итерация 6c — Многостраничный обход сайта при сканировании

> Документ-план к итерации между 6б (Контекстный гейтинг, ✅) и 7 (LLM, 📋).

## Контекст

Сейчас сканер забирает **одну страницу** — ту, которую дал пользователь
(`app.scanner.collect(url)` → один `PageArtifacts`). Это даёт неполное
покрытие:

- **152-ФЗ «Сбор ПДн без согласия»** — пропускаем формы на `/feedback/`,
  `/contacts/`, `/auth/`, `/register/`, `/order/`. На habr.com форма с
  правильным чекбоксом согласия живёт на `/ru/feedback/`, мы её не
  видим, и проверка даёт inconclusive «не удалось обнаружить форму».
- **149-ФЗ «Нет сведений о владельце»** — пропускаем `/contacts` или
  `/о-компании` с ОГРН/ИНН/адресом. На habr эти сведения на
  `company.habr.com/ru/#contact`, мы их не находим, даём fail на главной.
- **38-ФЗ «Реклама на иностранном»** — пропускаем рекламу на внутренних
  страницах разделов.
- **436-ФЗ «Возрастная маркировка»** — пропускаем разметку на странице
  статьи (главная может не иметь, отдельная публикация — должна иметь).
- **152-ФЗ «Политика не соответствует требованиям»** — частично работает
  через `_find_policy_url` + httpx, то есть **одна** дополнительная
  страница (политика) уже подгружается, но через отдельный механизм,
  параллельный scanner. Это устаревшая костыль-схема, которую сразу
  стоит унифицировать.

В итоге пользователь видит inconclusive / fail, которые после ручной
проверки оказываются спорными — реальная информация есть на сайте, но
не на той странице, которую мы сканировали.

---

## Решения пользователя

Зафиксированы перед стартом проектирования (через `AskUserQuestion`):

1. **Источник URL'ов:** эвристика по ссылкам с главной + опционально
   `/sitemap.xml`. Не пытаемся обходить весь сайт — только ключевые
   страницы, релевантные текущему корпусу нарушений (контакты,
   обратная связь, политика, согласие, регистрация / вход, тарифы /
   корзина, о компании). Лимит 5-10 страниц.

2. **Семантика агрегации:** per-violation. По умолчанию «fail хоть
   на одной странице → fail» (consent отсутствует хоть где-то —
   нарушение). Для site-wide характеристик (TLS, HTTP-заголовки) —
   только главная.

3. **Finding:** добавить поле `page_url` — где именно найдено. UI
   показывает «Найдено на странице X» в карточке.

---

## Архитектурные решения

### Р1. ScanArtifacts как контейнер

Вводим новый тип:

```python
class ScanArtifacts(BaseModel):
    main: PageArtifacts            # обязательно — главная
    pages: tuple[PageArtifacts, ...] = ()  # дополнительные страницы
    cookies: tuple[Cookie, ...] = ()       # сессионные cookies (общие)
    network_log: tuple[NetworkEntry, ...] = ()  # network main-страницы
```

`PageArtifacts` остаётся как есть (URL, HTML, headers, status). Cookies
и network_log переезжают на уровень `ScanArtifacts` — это сессионное
свойство, не per-page.

Engine принимает `ScanArtifacts`. Для check-функций, которые работают
per-page (DOM-based), вводим итерацию по `scan.main + scan.pages`.
Для site-wide функций (`cookie_set_before_consent`, `indexof_check`,
TLS) — используем только `scan.main` / `scan.cookies`.

### Р2. Выбор страниц для обхода

Алгоритм `_discover_pages(main: PageArtifacts) -> list[str]`:

1. Парсим DOM главной.
2. Ищем `<a href>` по списку ключевых слов в тексте/href:
   - `контакт`, `contact`
   - `о нас`, `о компании`, `about`
   - `политика`, `privacy`, `конфиденциальн`
   - `согласие`
   - `обратная связь`, `feedback`, `поддержка`, `support`
   - `регистрация`, `register`, `sign up`, `signup`, `вход`, `войти`,
     `login`, `signin`
   - `корзина`, `cart`, `оформить`, `checkout`, `тариф`, `подписка`
   - `условия`, `пользовательское соглашение`, `terms`
   - `оферта`, `offer`
3. Дедупликация по абсолютному URL.
4. Фильтр: только же-origin (тот же host, что и main). Исключаем
   внешние ссылки (facebook, instagram и т. п.).
5. Лимит: 10 страниц максимум (по приоритету первых ключей).

Опционально (если успеем): `/sitemap.xml` — если ссылок из шага 2 < 5,
дёргаем `<main_url>/sitemap.xml`, парсим, добавляем URL по ключевым
словам в path (`*/contacts*`, `*/privacy*`, `*/feedback*`).

### Р3. Per-page evaluation в engine

`evaluate_violation`:

1. Текущая логика остаётся — `_evaluate_signal(signal, artifacts)` для
   одного `PageArtifacts`.
2. Новый wrapper `_evaluate_signal_across_pages(signal, scan)`:
   - Site-wide checks (по списку имён): передаём `scan.main`.
   - DOM-based checks: вызываем `_evaluate_signal(signal, page)` для
     каждой страницы из `scan.main + scan.pages`. Берём best result:
     fail > real-inconclusive > stub-inconclusive > pass. Сохраняем
     URL страницы, на которой получили best result.

`Finding` получает поле `page_url: str | None` — URL, на котором
найдено. None — если site-wide.

### Р4. Замена `_find_policy_url` + httpx-fetch на честный обход

Сейчас `text_length_threshold` / `date_in_document` / `http_status_check`
сами лезут в httpx за политикой. Это:
- Дублирует scanner-логику (нет playwright-рендера, нет cookies).
- Странная архитектура: одна страница через playwright, другая через
  httpx без рендера.

После 6c: эти чеки **читают политику из `scan.pages`** (страница уже
загружена общим механизмом). Если политика не загружена — inconclusive
с reason `evidence_missing` (не дёргаем сами).

### Р5. Cookies и network_log

Cookie state — общий для всей сессии (Playwright `BrowserContext`
сохраняет cookies между `page.goto()`). Поэтому одна `scan.cookies` для
всего скана: первый visit устанавливает cookies, последующие — уже с
ними. Это семантически правильно: «при обычном просмотре сайта
выставляются эти cookies до согласия».

Network log тоже общий (все запросы за время скана).

---

## Этапы

### Этап 1. Модели (~0.5 дня)

- `app/scanner.py`:
  - Новый `ScanArtifacts(BaseModel)` рядом с `PageArtifacts`.
  - `collect_scan(url, timeout, user_agent) -> ScanArtifacts`:
    - 1 playwright `BrowserContext`, переиспользуется.
    - Goto main, собрать main `PageArtifacts`.
    - `_discover_pages(main)` → список доп. URL.
    - Для каждого: goto, собрать `PageArtifacts` (без cookies/network —
      они общие).
    - Aggregate cookies + network_log по всему контексту.
  - Старый `collect()` сохраняем как deprecated-обёртку: возвращает
    `ScanArtifacts` с main и пустым `pages` для совместимости.

- `app/engine.py`:
  - `Finding`: добавить `page_url: str | None = None`.
  - `run_scan(scan: ScanArtifacts)` (была `run_scan(artifacts)`).
  - `_evaluate_violation(violation, scan)` принимает scan.

### Этап 2. Дискавери страниц (~0.5 дня)

- `app/discover.py` (новый модуль) — `discover_pages(main) -> list[str]`:
  - Извлечение `<a href>` по ключевым словам (RU+EN).
  - Фильтр same-origin (`urllib.parse.urlparse`).
  - Дедуп, лимит, приоритезация.
- Юнит-тесты `tests/test_discover.py` на фикстурах:
  - habr-like-blog: должен найти `/feedback/`, `/contacts/`,
    `/info/confidential/`.
  - e-commerce-like: должен найти `/checkout/`, `/cart/`, `/account/`,
    `/privacy/`.
  - lonely-landing (без ссылок): пустой список.

### Этап 3. Per-page evaluation (~0.5 дня)

- `app/engine.py`:
  - Список site-wide check-имён: `_SITE_WIDE_CHECKS = {
    "cookie_set_before_consent", "indexof_check", "tls_audit",
    "http_security_audit", "rkn_registry_lookup",
    "parked_domain_detection", ...}`.
  - `_evaluate_signal_across_pages(signal, scan)`:
    - Если `signal.check in _SITE_WIDE_CHECKS` → запустить только на
      `scan.main`.
    - Иначе → запустить на каждой странице, выбрать best (через
      приоритет fail > real-incon > stub > pass).
    - Вернуть `(CheckResult, page_url)`.
  - В `_evaluate_violation` использовать новый wrapper, передать
    `page_url` в Finding.

### Этап 4. Унификация policy-fetch (~0.5 дня)

- `_find_policy_url` остаётся для поиска ссылки на политику.
- `_fetch_text(url)` → удалить.
- `text_length_threshold` / `date_in_document` / `http_status_check`:
  - Использовать `scan.pages` для поиска страницы политики (URL ==
    результат `_find_policy_url(scan.main)`).
  - Если страницы нет в `scan.pages` — inconclusive `evidence_missing`
    («политика не загружена в этом скане»).
- Корпус: `lookup_pages_by_keywords` (Site-wide check для поиска
  страницы политики) теперь возвращает абсолютный URL — engine
  гарантирует, что URL загружен.

### Этап 5. Frontend / API (~0.5 дня)

- `app/api/scan.py`: SSE-события уже структурированы — добавить
  `page_url` в Finding в JSON-сериализации.
- `frontend/src/lib/types.ts`: добавить `page_url?: string` в
  `Finding`-интерфейс.
- `frontend/src/app/scan/[id]/page.tsx` (или где рендерится карточка):
  показывать «Найдено на странице: <url>» в карточке findings.

### Этап 6. Прогон и регрессии (~0.5 дня)

- `make corpus && make lint && make test` — всё зелёное.
- Manual scan по habr:
  - До 6c: 152-fz no-consent → inconclusive («форма не найдена»);
    149-fz no-owner-info → fail.
  - После 6c: оба теперь должны корректно срабатывать (consent есть
    на `/feedback/` → pass; owner-info на `company.habr.com` → если
    same-origin фильтр пропускает поддомен, pass; иначе документируем).
- Юнит-тесты:
  - `tests/test_engine_multipage.py`: violation с page_signal даёт
    fail только если ВСЕ страницы fail (отрицательный случай); fail
    если хоть одна fail (положительный).
  - `tests/test_engine_multipage.py`: site-wide signal оценивается
    только на main.

### Этап 7. Документация и ADR (~0.5 дня)

- Новый `docs/adr/0004-multipage-scanning.md`:
  - Решения Р1-Р5 в формализованном виде.
  - Trade-off: одинокая страница (landing) → 1 страница; полноценный
    сайт → 5-10. Стоимость: время скана растёт линейно (5x для
    среднего сайта).
- Обновить `docs/vision.md` раздел «Архитектура» (жизненный цикл скана
  — теперь N страниц).
- Обновить README с описанием «что значит сейчас "скан сайта"».

---

## DoD

- `app/scanner.py` отдаёт `ScanArtifacts` с `main` + 0-10 дополнительных
  страниц.
- `app/discover.py` — модуль с эвристикой выбора URL'ов, юнит-тесты
  ≥ 6 кейсов.
- `app/engine.py` оценивает page_signals на всех страницах, site_signals
  — только на main. Finding содержит `page_url`.
- `text_length_threshold` / `date_in_document` / `http_status_check`
  читают политику из `scan.pages`, не дёргают httpx напрямую.
- `Finding` в API (JSON) и UI (TS-типы + карточка) показывают
  `page_url`.
- Прогон по habr.com: 152-fz no-consent даёт корректный pass (форма с
  чекбоксом на `/ru/feedback/`); 149-fz no-owner-info — корректный
  результат с учётом `company.habr.com` (после согласования: или
  pass, или документируем ограничение про поддомены).
- Все тесты зелёные (≥ 252 + новые).
- ADR-0004 написан.

---

## Открытые вопросы (закрыть на старте)

1. **Поддомены.** `company.habr.com` для основного домена `habr.com` —
   обходить или нет? Сейчас same-origin фильтр исключает. Решение: на
   старте делаем same-origin (тот же host). Поддомены — расширение в
   будущих итерациях через флаг `--include-subdomains`.

2. **Размер выборки.** 10 страниц — это разумный максимум для скана за
   ~30 секунд (1 страница ≈ 3s playwright). Если корпоративный сайт
   действительно нуждается в большем — итерация 7 / LLM.

3. **Lazy-load и SPA.** Страницы с client-rendering после `goto` могут
   не успеть отрендерить контент. Используем `wait_until="load"` +
   short `networkidle` (как сейчас в `collect`). Кейсы с тяжёлым SPA
   — ограничение, документируем.

4. **Cookies на разных страницах.** Если форма регистрации только на
   `/register/` устанавливает A/B-cookies, и они появятся в общем
   `scan.cookies` — это всё ещё «cookies до согласия», поэтому fair
   game для 152-fz cookies-without-disclosure.
