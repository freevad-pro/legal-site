# Итерация 6 — Frontend MVP

> Tasklist для [docs/plan.md](../plan.md), карточка итерации 6.
> Статусы: 📋 → 🚧 → ✅. Один финальный коммит на всю итерацию (по [feedback_one_commit_per_iteration]).

## Контракт DoD (из `plan.md`)

- [ ] Скелет `frontend/`: Next.js 15 + Tailwind, `output: 'export'` в `next.config.mjs`, `pnpm build` собирается в `frontend/out/`
- [ ] Реализация соответствует утверждённым мокапам и палитре из `docs/design.md`
- [ ] Главная: инпут URL + кнопка «Проверить», лёгкая клиентская валидация
- [ ] Тоггл «Расширенный анализ»: disabled со ссылкой «Войти» для анона; активный (off по умолчанию) для авторизованного. Значение уходит в `POST /api/v1/scans {with_llm}`
- [ ] Страница `/login`: форма с inline-ошибкой, успех — редирект на `/`, сервер ставит cookie
- [ ] В шапке: «Войти» для анона, `<login>` + «Выйти» для авторизованного. Состояние — через `GET /api/v1/auth/me` (всегда 200, `login: null | str`); logout дёргает `POST /api/v1/auth/logout`
- [ ] Прогресс: `EventSource` подключается к SSE, отрисовывает текущий шаг, счётчик нарушений по severity
- [ ] Страница результата: список Finding'ов, **все карточки раскрыты по умолчанию**, кнопки «Свернуть все» / «Раскрыть все», индивидуальный toggle
- [ ] Если скан без LLM — виден блок «Расширенный анализ доступен после входа» (даже при 0 inconclusive)
- [ ] Кнопка «Скачать PDF» дёргает `/report.pdf`, имя файла `legal-audit-<host>-<date>.pdf`
- [ ] Обработка: 401 на `with_llm=true` без сессии (мягкое предложение войти), недоступный сайт, таймаут, `inconclusive` (отдельная секция)
- [ ] Сборка `pnpm build` → `frontend/out/` отдаётся FastAPI через `StaticFiles`
- [ ] Локальная dev-разработка работает в двух терминалах (`make dev` + `make dev-frontend`)

## Предусловия (унаследованы из 5 и 5а, см. [docs/design.md §15](../design.md))

- [ ] **ADR-0002** — расширение схемы корпуса полями `short_description`, `icon`, `category` (на уровне `Law`) и опциональным `evidence_template` (на уровне `violations[]`)
- [ ] Решение по категоризации шагов прогресса — **вариант B** зафиксирован: бэк не трогаем, фронт группирует `violation_evaluated` по `category` закона
- [x] Итерация 5а закрыта (cookie-сессии, `with_llm`, `/auth/me`)

## Ключевые решения

- **SSE-контракт — вариант B.** Бэк не публикует step-события. Фронт читает `category` каждого закона из bundled JSON (генерируется на этапе сборки фронта из `docs/laws/index.yml`) и сам группирует `violation_evaluated` в шаги прогресса. Контракт SSE остаётся стабильным.
- **Дедупликация SSE — обязательна.** Бэк ([app/api/scan.py:145-177](../../app/api/scan.py)) не поддерживает `Last-Event-ID`; при reconnect EventSource снова отдаёт весь буфер истории. В `useScanStream` храним `Set<violation_id>`, повторный `violation_evaluated` с тем же id — игнорируем. На терминальном событии (`done`/`error`) явно вызываем `EventSource.close()`.
- **Кнопка «Прервать» исключена из MVP.** На бэке нет cancel; имитация дезориентирует (скан добегает до 300-сек таймаута и держит семафор). Зафиксировано как известное ограничение MVP.
- **6 карточек категорий на главной — хардкод-массив** в `CategoriesGrid.tsx`, не из корпуса (в MVP-корпусе нет `category: cookies`, но карточка нужна для витрины). **Шаги прогресса — динамические** по реально присутствующим в корпусе категориям (в MVP — 5: privacy, advertising, consumer, info, copyright).
- **`with_llm` в `ScanSummary`.** Чтобы блок «Расширенный анализ доступен после входа» работал и при открытии скана по прямой ссылке (без localStorage), `with_llm` пробрасывается из `ScanState` в Pydantic-ответ `GET /scans/{id}`. Маленькая правка бэка внутри этой итерации.
- **`evidence_template` — опциональный.** Проставляем для 6 показательных нарушений, чтобы продемонстрировать каждый из 6 шаблонов мини-превью. Для остальных 94 нарушений UI рендерит `GenericEvidence` (mono-цитата `evidence` + severity-чип) — простой fallback, без потери информации.
- **API-база — через `NEXT_PUBLIC_API_BASE`.** Пустая строка в production (один origin) → относительные URL; `http://localhost:8000` в dev (`frontend/.env.development`). `rewrites` в `next.config.mjs` не используем — несовместимы с `output: 'export'` в production.
- **CORS для dev.** В `app/main.py` добавить `CORSMiddleware` с `allow_origins=["http://localhost:3000"]` и `allow_credentials=True` (только когда `settings.session_cookie_secure=False`, т. е. в dev). Production это не задевает — фронт и API на одном origin.
- **Один маршрут `/scan?id=<uuid>`** вместо динамического `/scan/[id]`. На static export `[id]` без `generateStaticParams` не работает; query-параметр обходит ограничение без серверного рендера.
- **shadcn-компоненты в MVP:** `button`, `input`, `label`, `badge`, `separator`, `dialog`, `tooltip`. `alert-dialog` и `toast` не нужны (кнопки «Прервать» нет).
- **Темплейты мини-превью — 6 хардкод-React-компонентов** в `frontend/src/components/evidence/`, +`GenericEvidence` как fallback. Без рантайм-загрузки и template engine — самое простое решение для MVP.

## Заполнение 15 YAML-файлов корпуса (для ADR-0002)

| Файл | `category` | `icon` (Lucide) | `short_description` |
|------|-----------|-----------------|---------------------|
| 152-fz-personal-data.md | privacy | `lock` | О персональных данных |
| 242-fz-data-localization.md | privacy | `database` | Локализация данных в РФ |
| pp-1119-pdn-protection.md | privacy | `shield-check` | Уровни защищённости ПДн |
| 38-fz-advertising.md | advertising | `megaphone` | О рекламе |
| ord-ad-marking.md | advertising | `tag` | Маркировка интернет-рекламы |
| 2300-1-consumer-protection.md | consumer | `users` | Защита прав потребителей |
| pp-2463-sale-rules.md | consumer | `shopping-cart` | Правила продажи товаров |
| gk-rf-offer.md | consumer | `scroll` | Публичная оферта (ГК РФ) |
| 54-fz-cash-registers.md | consumer | `receipt` | Контрольно-кассовая техника |
| 161-fz-payment-system.md | consumer | `credit-card` | Национальная платёжная система |
| 53-fz-state-language.md | info | `languages` | Государственный язык |
| 149-fz-information.md | info | `file-text` | Об информации и ИТ |
| 436-fz-children-protection.md | info | `shield` | Защита детей от вредной информации |
| 63-fz-electronic-signature.md | info | `pen-tool` | Об электронной подписи |
| gk-rf-part-iv-copyright.md | copyright | `copyright` | Интеллектуальная собственность (ГК РФ) |

Распределение: privacy 3 / advertising 2 / consumer 5 / info 4 / copyright 1 = 15 законов, 5 категорий.

**`evidence_template` для 6 показательных нарушений** (точные `violation_id` сверяем в момент работы — если кандидат отсутствует, берём семантически ближайший в том же законе и фиксируем выбор в коммит-сообщении):

| Кандидат `violation_id` | `evidence_template` |
|-------------------------|---------------------|
| 152-fz-no-privacy-policy | `footer_no_policy` |
| 152-fz-no-consent-form | `form_no_consent` |
| 152-fz-cookies-before-consent (или ближайшее cookie-нарушение) | `cookies_before_consent` |
| 2300-1-*-no-requisites (контакты/реквизиты продавца) | `contacts_no_requisites` |
| ord-ad-marking-no-erid | `banner_no_marking` |
| 152-fz-dnt-ignored (или ближайшее DNT/cookie) | `dnt_ignored` |

## Пошаговый план

> Этапы идут последовательно. После 2 — `make corpus && make lint && make test` должны быть зелёные. После 9 — финальный коммит.

1. **Tasklist и статус.** Создать этот файл (уже сделано), перевести строку итерации 6 в [plan.md](../plan.md) в `🚧`.

2. **Предусловия — ADR-0002, расширение корпуса, точечная правка бэка.**
   - `docs/adr/0002-corpus-ui-fields.md` — обоснование 4 новых полей, enum категорий, перечень шаблонов превью, фиксация варианта B SSE.
   - `docs/laws/schema.md` — секции про новые поля, валидация длины `short_description ≤ 60`.
   - `app/corpus/models.py` — добавить `LawCategory` (StrEnum), поля `Law.category`, `Law.icon`, `Law.short_description`, `Violation.evidence_template: str | None = None`.
   - `tools/rebuild_index.py` — выписать новые поля в `docs/laws/index.yml`. Дополнительно — `categories: {category: violations_count}` для prebuild фронта.
   - Заполнить 15 YAML-файлов по таблице выше; проставить `evidence_template` для 6 нарушений.
   - `app/api/scan.py` — в `ScanSummary` добавить `with_llm: bool`, заполнять из `state.with_llm`.
   - `tests/test_api_scans.py` — проверка наличия `with_llm` в GET ответе.
   - Прогнать `make corpus && make lint && make test` — зелёные.

3. **Скелет `frontend/`.**
   - `pnpm` инициализация: `package.json`, `pnpm-lock.yaml`, `tsconfig.json`, `next.config.mjs` (`output: 'export'`, `images.unoptimized: true`), `tailwind.config.ts`, `postcss.config.mjs`, `.gitignore`.
   - Зависимости: `next@15`, `react@19`, `react-dom@19`, `typescript@5`, `tailwindcss@3`, `tailwindcss-animate`, `lucide-react`, `clsx`, `tailwind-merge`, `class-variance-authority` (для shadcn).
   - shadcn init и установка: `button`, `input`, `label`, `badge`, `separator`, `dialog`, `tooltip` — одной пачкой через `pnpm dlx shadcn@latest add`.
   - Шрифты — Onest + JetBrains Mono через `next/font/google` в `src/app/layout.tsx`.
   - Tailwind tokens (по `docs/design.md` §5–6): base/severity/favicon палитра, типографическая шкала. shadcn theme tokens (`--primary`, `--background`, …) маппятся на бренд-токены.
   - `frontend/scripts/build-corpus.mjs` — читает `docs/laws/index.yml`, пишет `frontend/src/data/laws.generated.ts` и `frontend/src/data/categories.generated.ts`. Подключён к `prebuild` скрипту в `package.json`.
   - `src/lib/api.ts` — обёртки `login`, `logout`, `me`, `createScan`, `getScan`, `subscribeEvents`, `reportPdfUrl` с `credentials: 'include'`. База — `NEXT_PUBLIC_API_BASE ?? ''`.
   - `src/lib/types.ts` — TS-зеркало `ScanSummary`, `ScanResult`, `Finding`, `Penalty`, `LawCategory`.
   - `frontend/.env.development` — `NEXT_PUBLIC_API_BASE=http://localhost:8000`.

4. **Auth UI.**
   - `src/lib/auth-context.tsx` — клиентский `AuthProvider`: на mount вызывает `/auth/me`, отдаёт `{login, refresh, logout}`. Подключается в `src/app/layout.tsx` через `'use client'`-обёртку.
   - `src/components/Header.tsx` — sticky-шапка, лого, кнопка «Войти» (анон) или `<login>` + «Выйти» (авторизованный). Logout вызывает `api.logout()` → `refresh()`.
   - `src/app/login/page.tsx` — карточка по центру (420×auto), поля login/password, inline-ошибка под формой при 401, успех → `router.push('/')`.

5. **Главная (Фаза 1).**
   - `src/app/page.tsx` — Hero (h1 + abstract) + зелёная CTA-карточка.
   - `src/components/ScanForm.tsx` — клиентская валидация (непустой URL, базовая проверка `^[a-zA-Z0-9-]+\.[a-zA-Z]{2,}` ИЛИ `^https?://`), POST `/scans` с `with_llm` из тоггла → `router.push('/scan?id=<uuid>&phase=progress')`.
   - `src/components/LlmToggle.tsx` — для анона: disabled + ссылка «Войти»; для авторизованного: активный, off по умолчанию.
   - `src/components/CategoriesGrid.tsx` — 6 серых карточек: privacy/cookies/advertising/consumer/info/copyright. Иконки и подписи — хардкод-массив, hover-эффекты по design.md §9.
   - `src/components/LawsMarquee.tsx` — карусель из `laws.generated.ts` (бесконечная, дублируется, pause on hover, hover на карточке → иконка зелёная).

6. **Прогресс-страница (Фаза 2).**
   - `src/app/scan/page.tsx` (Suspense + client component) с `useSearchParams()`. Фазы переключаются по `phase` query-param + по `status` из `getScan`.
   - `src/hooks/useScanStream.ts`:
     - Подписка на `/scans/{id}/events` через нативный `EventSource`.
     - `Set<violation_id>` для дедупликации.
     - На `done` / `error` → `eventSource.close()`, выставить флаг завершения.
     - Состояние: `{seenIds, severityCounts, lastViolationTitle, status, errorMessage}`.
   - `src/components/Progress/*.tsx` — pulsing dot, favicon-кружок (цвет по `hashHost(host) % 9`), заголовок шага, прогресс-бар 8px с диагональной анимацией, live-flash, 4 плитки severity, список шагов (динамический набор по `categories.generated.ts` и пришедшим событиям).
   - На `done` → `router.replace('/scan?id=...&phase=result')`. На `error` → красное Failed-состояние.

7. **Страница результата (Фаза 3).**
   - Та же `src/app/scan/page.tsx`, ветка по `phase=result` или `status === 'done'`.
   - `getScan(id)` → `ScanSummary` (с `with_llm`, `result`, `error`).
   - Sticky-шапка отчёта (top 64px, blur): favicon, домен, № аудита (`generateAuditNumber(scan_id, started_at)`), кнопки «Новая» / «PDF».
   - Severity-сводка 4×1 (critical/high/medium/low — считаем по `findings`).
   - `src/components/FindingCard.tsx` — все раскрыты по умолчанию, severity-стрип слева, чип, статья, chevron-toggle.
   - `src/components/ResultsToolbar.tsx` — счётчик + «Раскрыть все» / «Свернуть все».
   - `src/components/evidence/*.tsx`:
     - `FooterNoPolicy`, `FormNoConsent`, `CookiesBeforeConsent`, `ContactsNoRequisites`, `BannerNoMarking`, `DntIgnored` — статичные React-компоненты по дизайну прототипа.
     - `GenericEvidence` — fallback (mono-цитата `finding.evidence` + severity-чип).
     - `<EvidencePreview template={...} finding={...} />` — диспетчер по `template`.
   - Секция «Требуют ручной проверки» — отдельный список для `findings` с `status === 'inconclusive'`.
   - Блок «Расширенный анализ доступен после входа» — показывается при `summary.with_llm === false` (и при наличии inconclusive, и без них).
   - Финальный зелёный CTA-блок: «Скачать PDF» (тёмная кнопка) + «Проверить другой» (outline → /).

8. **Интеграция в FastAPI.**
   - `app/main.py`:
     - `CORSMiddleware`: `allow_origins=["http://localhost:3000"]` под флагом `not settings.session_cookie_secure` (т. е. только в dev). `allow_credentials=True`.
     - `StaticFiles` на корень — **после** регистрации `/api/*`, `/health`. Используем `html=True` для fallback на `index.html`. Каталог `frontend/out` — если его нет (фронт не собран), приложение не должно падать: монтаж в try/except с warning-логом.
   - `Makefile`:
     - `build-frontend`: `cd frontend && pnpm install && pnpm build`.
     - `dev-frontend`: `cd frontend && pnpm dev`.
   - `README.md` — новый раздел «Frontend — локальная разработка»: два терминала (`make dev` на 8000, `make dev-frontend` на 3000), production-сборка `make build-frontend`.

9. **End-to-end и закрытие.**
   - Локально пройти сценарии в браузере:
     1. Анонимный: главная → ввод URL → прогресс → результат → PDF; на результате виден блок «Расширенный анализ доступен после входа».
     2. Login → главная → тоггл on → прогресс → результат (блок отсутствует) → PDF.
     3. Logout → попытка `with_llm=true` → мягкое предложение войти.
     4. Failed (несуществующий хост) — красное состояние.
     5. Empty (0 нарушений) — success-карточка.
     6. **Reconnect:** в DevTools заглушить SSE-соединение, дождаться переподключения — счётчики не задваиваются.
     7. **Прямая ссылка:** открыть `/scan?id=<uuid>` после `done` в новой вкладке — блок «доступен после входа» рендерится корректно по `with_llm`.
   - `make corpus && make lint && make test && make build-frontend` — всё зелёное.
   - Согласовать с пользователем черновик commit-сообщения, сделать один коммит на всю итерацию.
   - Перевод статуса в [plan.md](../plan.md) `🚧 → ✅`.

## Fallback

- **`pnpm` не установлен в системе** → инструкция `corepack enable && corepack prepare pnpm@latest --activate`. В Makefile использовать `pnpm` напрямую, без npm/yarn.
- **`cd frontend && pnpm install` падает на Windows из-за длинных путей** → инструкция `git config --system core.longpaths true` (один раз).
- **shadcn-init создаёт `src/lib/utils.ts` со своим `cn`** — оставляем как есть, импорты в компонентах ссылаются именно на него.
- **`output: 'export'` валит build из-за серверного компонента** → пометить все интерактивные страницы (`/login`, `/scan`, главная) как `'use client'`. Layout остаётся серверным, провайдеры — внутри клиентского wrapper'а.
- **CORS блокирует POST из dev-фронта** → в браузере DevTools → Network: смотрим, что preflight OPTIONS возвращает `Access-Control-Allow-Credentials: true` и `Access-Control-Allow-Origin: http://localhost:3000` (а не `*`).
- **`EventSource` не поддерживает headers / cookies cross-origin** — нативный EventSource всегда отправляет cookies на same-origin; для dev на `localhost:3000 → localhost:8000` нужен `EventSource(url, { withCredentials: true })`. Без этого SSE будет анонимным (для GET /events это OK — эндпоинт публичный по UUID).
- **Иконка Lucide отсутствует** → fallback на `circle`. Все имена в таблице YAML предварительно проверены, но если pin изменился — `getIcon(name) || Circle`.
- **`Last-Event-ID` reconnect задваивает счётчики** — решается дедупликацией по `violation_id` (см. ключевые решения). Если задваивается всё равно — проверить, что `Set` живёт в ref'е, а не пересоздаётся каждый рендер.
- **Static export не поддерживает `next/dynamic` с `ssr: false`** в роутах без явного `'use client'` — все интерактивные страницы целиком клиентские.
- **Скан был запущен в текущей вкладке и cookie-флаг `with_llm` потерялся при F5** → теперь не проблема: бэк отдаёт `with_llm` в `ScanSummary`, фронт читает оттуда.

## Verification (демо)

```bash
# Терминал 1: бэк
make install
make corpus
make lint && make test
make user LOGIN=demo  # для второго сценария
make dev

# Терминал 2: фронт (dev)
make dev-frontend
# открыть http://localhost:3000
```

Сценарии (вручную в браузере):

1. **Анонимный:** ввести `example.ru` → прогресс → результат → «Скачать PDF».
2. **Авторизованный:** «Войти» → demo/<пароль> → тоггл «Расширенный анализ» on → запустить скан → результат → PDF.
3. **Logout:** «Выйти» → попробовать тоггл — теперь disabled со ссылкой «Войти».
4. **Failed:** ввести `nonexistent.invalid` → красное «Сайт недоступен».
5. **Empty:** запустить на ресурсе без нарушений → success-карточка.
6. **Reconnect:** DevTools → Network → SSE-соединение → Block; снять блок — счётчики не задвоились.
7. **Прямая ссылка:** скопировать URL `/scan?id=<uuid>` после `done` в новую вкладку (анонимная сессия) — страница результата корректно показывает блок «Расширенный анализ доступен после входа».

**Production-сборка через FastAPI (один порт):**

```bash
make build-frontend
make dev
# http://localhost:8000/ — главная отдаётся из frontend/out/, API на /api/v1/* работает
```

## Открытое (вне MVP)

- **Кнопка «Прервать» с реальным cancel** — отдельная история; требует кооперативного отмены в `app/engine.py` (передача `CancellationToken`, проверки между шагами). Когда понадобится — отдельная итерация или вместе с очередью сканов.
- **`Last-Event-ID` на бэке** — позволит фронту не дедуплицировать вручную. Маленькая правка `_sse_stream`, но не критична для MVP.
- **Локализация UI / i18n** — пока всё на русском, тексты в JSX. Когда понадобится английский — отдельный ADR.
- **Темплейты мини-превью через схему корпуса** — сейчас 6 React-компонентов в `frontend/src/components/evidence/`. Если шаблонов станет много (> 15) и они будут зависеть от данных в YAML — переехать на data-driven рендер с конфигом в YAML.
- **Тесты фронта (Vitest / Playwright)** — в MVP проверяем вручную по сценариям выше. Когда фронт стабилизируется — добавлять компонентные тесты на ключевые состояния (loading/error/empty/inconclusive).
