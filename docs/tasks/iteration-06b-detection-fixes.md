# Итерация 6б — Контекстный гейтинг и инверсная логика детекции

> Документ-план к итерации между 6 (Frontend MVP, ✅) и 7 (LLM, 📋). По итогам разбора прогона по `https://habr.com/ru/feed/` (73 нарушения, большинство ложные).

> **Итерация закрыта 2026-05-15.** Итог по `habr.com/ru/feed/`: total findings 100 → 32, fail 71 → 23 (-68%). Все 4 исходные жалобы ушли, 0 утечек гейтинга, 0 заглушек в отчёте. Метрика «fail ≤ 10» формально не достигнута, но качественный состав остатка — реальные срабатывания (политика ПДн / госязык / маркировка / UGC-реестр) + 7 known issue `gk-rf-part-iv` (отложено в итерацию 7). Подробности — в [docs/adr/0003-context-gating-and-inverse-keywords.md](../adr/0003-context-gating-and-inverse-keywords.md), История изменений ADR, заход 4.

> **Что не достигнуто и переносится дальше** (см. также «Открытое после 6б» в [docs/plan.md](../plan.md) карточка итерации 7):
>
> 1. **Метрика «fail ≤ 10» на habr.com.** По факту 23 fail (16 без `gk-rf-part-iv`). Дальнейшее снижение упирается в проблемы, для которых детерминированный движок недостаточен:
>    - Гиперширокие селекторы в `gk-rf-part-iv` (`img[src^="https://"]`, `title`, `link[href*="fonts"]`) дают 7 fails на любом сайте. Точечная ревизия селекторов или замена на LLM-проверки — итерация 7. Закрытие селекторов вручную потребует или удалить часть нарушений (потеря охвата), или ввести семантику «есть ли указание лицензии на изображение», что выходит за CSS-уровень.
>    - 16 «честных» fails (152-фз политика, 242-фз GA, 53-фз госязык, 149-фз UGC-реестр и owner-info, pp-1119, 436-фз без age-marking) — корректны для habr как медиа-сайта без чёткой политики ПДн. Снизить их можно только либо переразметкой корпуса (с риском пропустить реальные случаи на других сайтах), либо реализацией LLM-проверок, которые умеют отличать «политика есть, но неполная» от «политики нет совсем».
> 2. **False positives «контент ≠ реклама» для `ad_content`.** На прогоне по habr тег `ad_content` не активировался после захода 4, но это случайность данной страницы (на главной habr не оказалось рекламного блока с регулируемым ключом). На сайтах с реальными нативными рекламными блоками БАД/кредитов через семантически «правильные» классы (`tm-marketing-block`, `tm-banner-ads`) тег сработает корректно, но статья «обзор VPN-сервисов» в блоке `[class*="promo"]` всё ещё даст ложный fail. Закрывается только LLM (промпт «реклама с коммерческим призывом или редакционный контент с упоминанием?»).
> 3. **Калибровка `_detect_ecommerce` на лендингах.** AND-логика «корзина + (купить ИЛИ цена)» ИЛИ «купить + цена» правильно режет медиа-сайты, но может пропустить лендинг продукта без цены («Купить курс» без явной суммы — payments/has_signing дадут охват, но e-commerce-нарушения pp-2463 / 2300-1 окажутся вне выдачи). Точная калибровка — отдельный шаг при появлении статистики.
> 4. **Q4 из контрольной точки 1: текстовый триггер + эскейп.** 6 sub-signals в 38-ФЗ сейчас возвращают `inconclusive_reason="context_dependent"` и скрыты engine'ом. Пересмотр после реализации LLM в итерации 7: либо free-fallback `_check_keyword_trigger_with_escape`, либо тишина в free-режиме (см. карточку итерации 7 в plan.md).

## Контекст

Прогон детерминированного сканера по habr.com выдал отчёт с грубыми ложными срабатываниями:

1. **«Несвоевременное уведомление РКН об инциденте с ПДн»** детектируется по `missing keywords ['ответственный за обработку', 'DPO']` — но отсутствие слова «DPO» в тексте главной никак не доказывает несвоевременное уведомление об инциденте.
2. **«Утечка ПДн вследствие нарушения мер защиты»** детектируется по `missing response headers: ['Content-Security-Policy']` — CSP это профилактическая мера от XSS, а не доказательство утечки.
3. **«Приём платежей по картам без эквайринга»** срабатывает по `no matching link found in DOM` (ключи «эквайер», «платёжный агент» не найдены) — но habr вообще не принимает платежей.
4. **«Реклама запрещённых товаров»** срабатывает по `missing keywords ['купить табак', 'купить сигареты', 'купить оружие', 'VPN купить', ...]` — логика инверсна: должно срабатывать на **присутствие** ключей, а не отсутствие.

Три корневые причины:

- **Нет контекстного гейтинга.** Все 100 нарушений проверяются на любом сайте, без учёта «есть ли на сайте оплата / e-commerce / реклама БАД / 18+ контент / UGC». Поле `applies_to` есть на уровне закона ([app/corpus/models.py:151](../../app/corpus/models.py)), но движок его игнорирует.
- **Инверсная семантика `required_keywords` для запрещёнки.** Универсальный `_check_required_keywords` ([app/checks.py:201-210](../../app/checks.py)) возвращает `fail` если **хотя бы одно** ключевое слово отсутствует. Это правильно для «политика должна содержать слова "сроки обработки"», но в корпусе тем же полем описаны «запрещённые ключи»: `38-fz-prohibited-goods.prohibited_keywords_in_content` ([docs/laws/38-fz-advertising.md:290-305](../laws/38-fz-advertising.md)) использует `required_keywords` для слов, которых на сайте быть **не должно**.
- **Семантически случайные привязки detection.** Sub-сигнал `dpo_contact_missing` приклеен к нарушению «несвоевременное уведомление об инциденте» ([docs/laws/152-fz-personal-data.md:485-489](../laws/152-fz-personal-data.md)). Sub-сигнал `weak_security_headers` с CSP приклеен к «утечке» ([docs/laws/152-fz-personal-data.md:544-548](../laws/152-fz-personal-data.md)). Связь натянутая — это разные нарушения с другим смыслом.

Плюс в отчёте 21 «Не определено» от 11 не реализованных в итерации 3 заглушек (`rkn_registry_lookup`, `tls_version_scan`, `ip_geolocation`, `form_action_geo` и т. п.). Они засоряют отчёт пустыми карточками.

Цель итерации — закрыть детерминированный слой до уровня «отчёт можно показать пользователю без оговорок про шум», до подключения LLM (итерация 7).

---

## Решения пользователя

Зафиксированы перед стартом проектирования:

1. **Масштаб:** правки в корпусе + схеме + движке. (Не «только корпус», не полный ADR-0003.)
2. **Оформление:** отдельная итерация 6б, перед итерацией 7. Tasklist `docs/tasks/iteration-06b-detection-fixes.md`.
3. **Заглушки `unknown check`:** скрыть из MVP-отчёта.

---

## Режим выполнения и контрольные точки

Итерация выполняется в **3 захода** с двумя обязательными контрольными точками. Каждый заход = отдельная сессия (чтобы контекст не разрастался). На контрольных точках агент **останавливается и докладывает пользователю**, не идёт дальше автоматически.

### Перед стартом итерации (один раз, в любом заходе перед этапом 1)

Обязательные подготовительные шаги:

1. **Снять baseline сканирования habr.com** — иначе на этапе 7 не с чем будет сравнивать «было/стало»:
   ```powershell
   uv run python -m app.scan "https://habr.com/ru/feed/" > scan-habr-before.json
   ```
   Файл `scan-habr-before.json` сохранить вне `git` (например, в `temp/` — он уже в `.gitignore`).

2. **Создать рабочую ветку:**
   ```powershell
   git checkout -b iteration-06b-detection-fixes
   ```
   Все правки итерации делаются в этой ветке; коммит — один финальный после закрытия (см. memory: «один коммит на итерацию»).

3. **Прочитать tasklist целиком** (этот файл), а также: [docs/plan.md](../plan.md) (карточка итерации 6б), [docs/laws/schema.md](../laws/schema.md), [app/checks.py](../../app/checks.py), [app/engine.py](../../app/engine.py), [app/corpus/models.py](../../app/corpus/models.py).

### Заход 1 — Инфраструктура (этапы 1–5)

**Что делает агент в автопилоте:** этапы 1, 2, 3, 4, 5 без вопросов пользователю. Все DoD проверяются `make lint && make test` после каждого этапа.

**На что обратить внимание:**

- **Этап 4 — breaking change.** Существующие тесты `tests/test_engine.py` могут начать падать, потому что `_evaluate_violation` теперь `Finding | None` и часть findings исчезает из результата (stubs скрыты). Адаптировать ассерты `len(result.findings) == N` под новое поведение — это часть этапа 4, не повод останавливаться. Если же при адаптации обнаруживается, что какой-то тест проверял именно поведение stubs как inconclusive (а не как «не должно быть») — остановиться и доложить.
- **Этап 5 — после интеграции `ScanContext`.** Корпус ещё НЕ размечен `applicability`-тегами — все нарушения по-прежнему применяются ко всем сайтам (пустой `applicability = ()` → `context.applies()` всегда `True`). Поведение сканера на habr.com **не должно радикально измениться** относительно baseline: уйдут только 2 sub-signals из этапа 3 + скрытые заглушки. Если число fail после захода 1 упало с 73 до, скажем, 30 — что-то пошло не так с гейтингом (не должен ещё работать), остановиться и проверить.

**Финиш захода 1 (контролируется агентом перед выходом из сессии):**
- [ ] `make corpus && make lint && make test` зелёные.
- [ ] Все этапы 1–5 закрыты по DoD.
- [ ] Документация-чекпоинт: `docs/plan.md` (статус 🚧), `docs/adr/0003-...md` (создан), `docs/laws/schema.md` (новые поля описаны).
- [ ] Код-чекпоинт: `app/context.py` существует и работает; `app/engine.py` фильтрует stubs и неприменимые.
- [ ] Корпус НЕ тронут (кроме удаления 2 sub-signals в этапе 3).

Доложить пользователю: «Заход 1 закрыт, готов к контрольной точке 1 — обсудить open questions».

### 🛑 Контрольная точка 1 — Open questions перед этапом 6

**Агент НЕ начинает этап 6 автоматически.** Он останавливается и просит пользователя ответить на 6 open questions из секции «Открытые вопросы» этого tasklist'а:

1. Граница `[ad_content]`-тега для 13 нарушений 38-ФЗ (все или только БАД/кредиты/запрещёнка).
2. Объём `[ugc]` в 149-ФЗ — какие нарушения помечать.
3. Объём `[has_signing]` для 63-ФЗ (предложение «все 7» — подтверждать или сузить).
4. «Текстовый триггер + эскейп» — вариант (а) реализовать новый обработчик, (б) переделать на html_patterns, (в) пометить как known issue.
5. Граница детектора `_detect_has_signing` (узкий / широкий / middle ground).
6. Тег `has_pd_form` — вводить ли (предложение: не вводить в 6б).

**Формат остановки:** агент в финальном сообщении перечисляет все 6 вопросов с дефолтным предложением из плана и просит подтвердить или скорректировать каждый. После ответов пользователя — заход 2.

### Заход 2 — Миграция корпуса (этап 6)

**Что делает агент в автопилоте:** этап 6 целиком по решённым open questions. Все 8 батчей последовательно.

**Финиш захода 2:**
- [ ] `make corpus && make lint && make test` зелёные.
- [ ] Общее число нарушений = 100 (контроль того, что батчи не удалили violations).
- [ ] Все 15 файлов корпуса размечены `applicability` согласно решениям с контрольной точки 1.
- [ ] Инверсные `required_keywords` мигрированы на `prohibited_keywords` (3 в 38-ФЗ + 4 в 436-ФЗ + возможные ещё 1–3 после grep'а).
- [ ] Решение open question 4 («текстовый триггер+эскейп») применено единообразно.

Доложить пользователю: «Заход 2 закрыт, корпус размечен, готов к заходу 3 (regression + ручной прогон)».

### Заход 3 — Verification и закрытие (этапы 7–8)

**Что делает агент в автопилоте:** этап 7 (фикстуры, regression-тест, ручной прогон по habr) — без остановки. Этап 8 (закрытие) — **только после прохождения контрольной точки 2**.

### 🛑 Контрольная точка 2 — Метрика достигнута?

**После этапа 7** агент собирает данные и докладывает пользователю **до выполнения этапа 8**:

- Было fail: 73; стало fail: **X** (из `scan-habr-after.json`).
- Было total findings: 100; стало: **Y**.
- Findings с `inconclusive_reason="check_not_implemented"`: **должно быть 0**; по факту: **Z**.
- Качественный состав оставшихся `fail`: **сравнение со списком «Что должно ОСТАТЬСЯ» из секции «Верификация end-to-end»** — соответствует / нет, с перечнем отклонений.
- Качественный состав того, что **должно было исчезнуть** — все ли отфильтровались.

**Решение:**

- Если **X ≤ 10 И качественный состав совпадает** → агент идёт в этап 8 (закрытие итерации) без дополнительных вопросов.
- Если **X > 10 ИЛИ в `fail` остались нарушения из 161-фз/54-фз/pp-2463/63-фз** (то есть гейтинг не отработал) → агент **останавливается**, докладывает что не так, и предлагает варианты докрутки (например: «детектор `_detect_payments` срабатывает по ложному признаку — нужно сузить»; или «применимость 161-фз помечена не на всех 7 нарушениях»; или «нужно добавить ещё одну миграцию `required_keywords` → `prohibited_keywords`»).

### Этап 8 — Закрытие итерации (только после прохождения контрольной точки 2)

Стандартное закрытие: статус в `docs/plan.md` `🚧 → ✅`, демо-цифры, финализация ADR-0003.

**Финиш итерации:** агент останавливается ПЕРЕД `git commit` (см. memory: «перед `git commit` показывать черновик и ждать подтверждения», «один коммит на итерацию»). Готовит черновик commit-сообщения и просит пользователя подтвердить.

---

## Архитектурные решения

### Р1. Контекстный гейтинг через `applicability: tuple[ContextTag, ...]` на Violation

В `Violation` добавляется опциональное поле `applicability` со списком тегов контекста — закрытый словарь из **7 значений**:

- `ecommerce` — интернет-магазин (корзина, кнопка «Купить», ценники, оформление заказа).
- `payments` — приём онлайн-оплат (поля карт, iframe yookassa/cloudpayments/sber/tinkoff/robokassa, ссылки `/checkout`, `/pay`).
- `ad_content` — рекламный контент регулируемых категорий (БАД, кредиты/займы, страхование, инвестиции, фарма).
- `ugc` — пользовательский контент (комментарии, форум, переписка).
- `media_18plus` — категории 18+ (алкоголь, табак, азартные игры, эротика).
- `child_audience` — детская/семейная аудитория с возрастной маркировкой 0+/6+/12+.
- `has_signing` — есть формы акцепта оферты / подписания соглашений (чекбоксы «согласен», SMS-OTP, кнопки «Подписать»/«Зарегистрироваться» в авторизуемом сценарии). Гейтинг 63-ФЗ.

Семантика: нарушение применяется ⇔ `applicability ⊆ active_tags` (AND). Пустой `applicability` (по умолчанию) = «применимо всегда». Старый корпус остаётся валидным без правок — поле опциональное.

**Почему так, а не иначе:**

- Альтернатива «`prerequisite: true` на первом сигнале» — экономит схему, но прячет контекст в sub-signal; контекст один на нарушение, а не на сигнал; e-commerce упоминается в ≥ 12 разных нарушениях — дублировать sub-signals неудобно.
- Альтернатива «расширить existing `applies_to` на уровне закона» — слишком грубо. В одном законе (38-ФЗ) есть и универсальные нарушения (ОРД-маркировка любой рекламы), и контекстные (БАД, кредиты).
- Закрытый словарь из 7 тегов покрывает >95% реальных контекстов. Расширение — отдельным ADR в будущем.

### Р2. Поле `prohibited_keywords` отдельно от `required_keywords`

В `PageSignal` и `SiteSignal` добавляется `prohibited_keywords: tuple[str, ...] = ()`. Новый универсальный обработчик `_check_prohibited_keywords` — `fail` при наличии **любого** из ключей в plain-text главной; `pass` если ни одного нет; evidence = найденный ключ.

Pydantic-валидатор запрещает совместное использование `required_keywords` и `prohibited_keywords` на одном сигнале (семантика противоположная).

Через `html_patterns` с `:contains` делать **не будем**: bs4/soupsieve `:-soup-contains` ограниченно работает с кириллицей и расширяет хрупкую область CSS-селекторов.

**⚠️ Substring-matching как known limitation:** и `_check_required_keywords`, и `_check_prohibited_keywords` ищут подстроку в plain-text, без word-boundary. Ключ `'bet'` сматчится в слове `'between'`. При миграции корпуса на `prohibited_keywords` нужно учитывать это и предпочитать многословные ключи (`'купить табак'`, не `'табак'`). Точечный апгрейд до word-boundary — отдельная задача за пределами 6б.

### Р3. Удаление семантически нерелевантных sub-signals

- Удаляется `dpo_contact_missing` ([docs/laws/152-fz-personal-data.md:485-489](../laws/152-fz-personal-data.md)) из `152-fz-incident-notification-missed`. (Содержание политики DPO — отдельное нарушение, оно уже живёт в `152-fz-policy-incomplete`.)
- Удаляется `weak_security_headers` ([docs/laws/152-fz-personal-data.md:544-548](../laws/152-fz-personal-data.md)) из `152-fz-data-breach`. (Заголовки уже есть в `pp-1119-secure-http-headers` — там и должны быть.)

После правки оба нарушения продолжают существовать, но их детектирование становится более узким (без false-positive по DOM-текстовым сигналам).

Эти два случая — единственные «семантически случайные привязки» в строгом смысле (sub-signal не доказывает заявленное нарушение). Отдельный класс **«гиперширокие селекторы»** (`img[src^="https://"]`, `title`, `link[href*="fonts"]` в `gk-rf-part-iv-copyright`, `[class*="promo" i]` в `53-fz` для рекламы) — рассматривается отдельно в разделе «Не делаем» (требует точечной ревизии селекторов, отложено).

### Р4. ScanContext и фильтрация неприменимых

Новый модуль `app/context.py`:

- `ContextTag` (импорт из `app/corpus/models.py`). Циклического импорта нет: `models.py` не импортирует `context.py`.
- `ScanContext(BaseModel, frozen=True)` с `active_tags: frozenset[ContextTag]` и методом `applies(violation: Violation) -> bool`.
- `detect_context(artifacts: PageArtifacts) -> ScanContext` — единая точка входа, sync, детерминированная. **Парсит `artifacts.html` через `BeautifulSoup` один раз** и передаёт `soup` всем приватным детекторам, чтобы не парсить 6 раз подряд. То же применимо к `_plain_text(soup)` — вычисляется один раз, переиспользуется.
- 7 приватных детекторов (`_detect_payments`, `_detect_ecommerce`, `_detect_ad_content`, `_detect_ugc`, `_detect_media_18plus`, `_detect_child_audience`, `_detect_has_signing`) — все принимают `soup: BeautifulSoup` и/или `text: str`, без повторного парсинга. Используют `artifacts.cookies`, `artifacts.network_log` при необходимости (платежи).

`run_scan` ([app/engine.py:111](../../app/engine.py)) после `scanner.collect` вычисляет `ScanContext` и передаёт его в `_evaluate_violation`. `_evaluate_violation` возвращает `Finding | None`: `None` если `not context.applies(violation)` — finding не появляется в результате, SSE-событие `violation_evaluated` для него не публикуется.

**Не вводим четвёртый статус `not_applicable`.** Это сломало бы `Status` Literal, фронт, PDF, тесты — польза от показа «вам не применимо» не оправдывает шум. Отфильтрованные нарушения просто отсутствуют в результате; общее число findings становится короче — это нормально.

### Р5. Скрытие заглушек через `inconclusive_reason` + фильтрация в engine

Добавляется поле `inconclusive_reason: Literal["check_not_implemented", "context_dependent", "evidence_missing"] | None` в `CheckResult` ([app/checks.py:72-79](../../app/checks.py)) и `Finding` ([app/engine.py:60-73](../../app/engine.py)). Pydantic-валидатор: не-None только при `status="inconclusive"`.

- `_not_implemented` ([app/checks.py:296-301](../../app/checks.py)) проставляет `"check_not_implemented"`.
- Ветка «unknown check» в `evaluate` ([app/checks.py:719-727](../../app/checks.py)) тоже проставляет `"check_not_implemented"`. Это покрывает не только перечисленный `_STUBS` ([app/checks.py:671-683](../../app/checks.py)), но и любое имя check, отсутствующее в REGISTRY — в корпусе их встречается больше 11 (например, `erir_token_lookup`, `text_language_detection`, `profanity_filter`).
- **`aggregate_or` различает stub-inconclusive и real-inconclusive** ([app/checks.py:235-260](../../app/checks.py)):
  - Хоть один fail → итог fail (evidence/explanation от первого fail).
  - Иначе хоть один **реальный** inconclusive (с `inconclusive_reason ≠ check_not_implemented`) → итог inconclusive с причиной от **реального** (не stub).
  - Иначе если все inconclusive — заглушки → итог inconclusive с `check_not_implemented`.
  - Иначе все pass → итог pass.

  Это критично: без различия порядок sub_signals определяет, скрыть ли finding (нестабильность). С различием: stub-inconclusive «маскируется» реальным inconclusive, если он есть, и не маскируется иначе.
- **`combine`-сигналы тоже считаются stub.** Ветка обработки `combine` в `evaluate` ([app/checks.py:712-717](../../app/checks.py)) возвращает `inconclusive` с фиксированной фразой `"combine-signals not supported in iteration 3"`. Эту ветку правим: возвращать `inconclusive_reason="check_not_implemented"`. Иначе нарушение, в котором рядом стоят `combine` и реальный stub, останется в отчёте (combine «маскирует» stub) — это `152-fz-no-rkn-notification` (combine `[form_with_pd, not_in_rkn_registry]`) и `436-fz-prohibited-content` (combine `[adult_content_detected, no_age_verification]`).
- `_evaluate_violation` ([app/engine.py:102](../../app/engine.py)): если `aggregated.status == "inconclusive"` и `aggregated.inconclusive_reason == "check_not_implemented"` → возвращает `None`. Finding не появляется, SSE для него не публикуется. **⚠️ Контракт `_evaluate_violation` меняется с `Finding` на `Finding | None`** — это breaking change для тестов и любых callers. Этап 4 включает: правка аннотаций возвращаемого типа, обновление `run_scan` (skip None), правка тестов `test_engine.py` (которые ожидают, что для каждой violation в bundle есть Finding в результате — теперь не так).

Фильтрация делается в engine — фронт и PDF получают уже очищенный массив, без знания о списке заглушек. В итерации 7 при реализации этих check-функций они вернут реальный статус — фильтр перестанет срабатывать автоматически.

Поле `inconclusive_reason` в Finding пробрасывается во `frontend/src/lib/types.ts` для типобезопасности — на рендер UI сейчас не влияет.

---

## Изменения по слоям

### Схема — `docs/laws/schema.md`

- Раздел «Нарушения»: описание `applicability` (закрытый словарь, AND-семантика, пустой = универсально).
- Раздел «Требования к движку проверки»: развести `required_keywords` (обязательное наличие) и `prohibited_keywords` (запрет наличия), явный запрет совместного использования.
- Раздел «Словари допустимых значений»: добавить `ContextTag` с описанием каждого тега.
- ADR `docs/adr/0003-context-gating-and-inverse-keywords.md` (новый, короткий) — контекст / решение / последствия, явная фиксация решения «4-й статус `not_applicable` не вводим».

### Pydantic-модели — `app/corpus/models.py`

- `ContextTag = Literal[...]` рядом с `LawCategory`.
- `PageSignal` / `SiteSignal`: добавить `prohibited_keywords: tuple[str, ...] = ()`; `model_validator` запрещает одновременное непустое `required_keywords` и `prohibited_keywords`.
- `Violation`: добавить `applicability: tuple[ContextTag, ...] = ()`. Модель остаётся `extra="forbid"` (поле добавляется явно).

### Движок — `app/checks.py`, `app/engine.py`, `app/context.py`

- **`app/checks.py`:**
  - `CheckResult`: новое поле `inconclusive_reason` + валидатор «non-None ⇒ status=inconclusive».
  - `_check_prohibited_keywords` — новый универсальный обработчик.
  - В `evaluate`: добавить ветку обработки `prohibited_keywords`; ветки `_not_implemented` и unknown check проставляют `inconclusive_reason="check_not_implemented"`.
  - `aggregate_or`: пробрасывать причину от первого inconclusive.
- **`app/context.py`** (новый): `ContextTag` импорт, `ScanContext`, `detect_context`, 6 приватных детекторов.
- **`app/engine.py`:**
  - `run_scan`: после `scanner.collect` — `context = detect_context(artifacts)`; передача в `_evaluate_violation`.
  - `_evaluate_violation`: подпись становится `-> Finding | None`. Возвращает `None` если `not context.applies(violation)` или если итог = `inconclusive` + `check_not_implemented`.
  - В цикле `run_scan`: skip None; SSE не публикуется.
  - `Finding`: поле `inconclusive_reason`.

### Корпус — `docs/laws/*.md`

Полный батч-план (15 файлов) с разметкой `applicability` и инвертированными ключами:

| Файл | applicability на нарушения | Правки sub-signals |
|---|---|---|
| `161-fz-payment-system.md` (7 violations) | `[payments]` на все 7 | — |
| `54-fz-cash-registers.md` (~5) | `[payments]` на все | — |
| `pp-2463-sale-rules.md` (~7) | `[ecommerce]` на все | — |
| `2300-1-consumer-protection.md` (~9) | `[ecommerce]` на нарушения о продавце/возврате/доставке | — |
| `gk-rf-offer.md` (~5) | `[ecommerce]` или `[payments]` где о договоре оплаты | — |
| `38-fz-advertising.md` (13) | `[ad_content]` на БАД/лекарства/кредиты/запрещёнку; ОРД-маркировка пустой | `prohibited_keywords` вместо `required_keywords` в `38-fz-prohibited-goods.prohibited_keywords_in_content` (стр. 290-305), `38-fz-prohibited-goods.unregistered_medicine_ad` (306-312), `38-fz-bad-no-disclaimer.bad_therapeutic_claims` (389-396) |
| `436-fz-children-protection.md` (~6) | `[media_18plus]` для age-gate/алкоголь-табак; `lgbt-propaganda`/`prohibited-content` — `[]` (универсально); `wrong-age-marking` — `[media_18plus]` | **Дополнительные миграции `required_keywords` → `prohibited_keywords`:** `436-fz-lgbt-propaganda.lgbt_propaganda_keywords` (стр. 207-209, `['ЛГБТ', 'однополые отношения', 'смена пола', 'трансгендер']`); `436-fz-prohibited-content.suicide_promotion_keywords` (стр. 295-297, `['способы суицида', 'как покончить', 'selfharm']`); `436-fz-prohibited-content.drug_usage_instructions` (стр. 298-300, `['способ употребления', 'как приготовить', 'наркотик']`); `436-fz-wrong-age-marking.adult_keywords_under_low_age_marking` (стр. 117-119, `['эротика', 'ставки', 'казино', 'наркотики', 'алкоголь', 'табак']`) |
| `152-fz-personal-data.md` (~10) | `[]` (все универсальные) | удалить sub-signal `dpo_contact_missing` (485-489) и `weak_security_headers` (544-548) |
| `pp-1119-pdn-protection.md` | `[]` (универсально) | — |
| `242-fz-data-localization.md` | `[]` (универсально) | — |
| `149-fz-information.md` | `[]` на универсальные; `[ugc]` на нарушения о модерации UGC | — |
| `53-fz-state-language.md` | `[]` на универсальные (госязык — для любого сайта); `[ad_content]` на нарушения о рекламе на иностранном | — |
| `63-fz-electronic-signature.md` (~7) | **`[has_signing]` на все 7 нарушений** (закон применяется только при наличии форм акцепта/подписания) | — |
| `ord-ad-marking.md` | `[ad_content]` (применимо там, где есть рекламные посты) | — |
| `gk-rf-part-iv-copyright.md` (8) | `[]` на универсальные | — (но ⚠️ см. «Не делаем» — гиперширокие селекторы) |

Дополнительно: пройти все 49 случаев `required_keywords` по корпусу и проверить семантику. Те, что описывают «нечто, чего не должно быть» (купить табак, лечит, вылечит) — мигрировать на `prohibited_keywords`. Те, что описывают «обязательное содержание» (срок возврата, ОГРН, ИНН) — оставить как есть.

После правок: `make corpus` пересобирает `docs/laws/index.yml`, общее число нарушений остаётся **100** (мы убираем sub-signals и добавляем разметку, не удаляя сами violations).

### Frontend / PDF

- `frontend/src/lib/types.ts`: добавить `inconclusive_reason` в TS-интерфейс `Finding`.
- Рендер не меняется. Счётчики «Нарушений найдено» / «Не определено» автоматически становятся меньше — массив короче.

---

## Этапы и DoD

### Этап 1. Документация: схема + ADR

- В `docs/laws/schema.md`: разделы про `applicability`, `prohibited_keywords`, словарь `ContextTag`.
- ADR `docs/adr/0003-context-gating-and-inverse-keywords.md`.
- В `docs/plan.md` обзорная таблица: строка итерации 6б, статус `🚧 In Progress`.

**DoD:** документы согласованы, статус в таблице обновлён.

### Этап 2. Pydantic-модели + `_check_prohibited_keywords` + новый `aggregate_or`

- `app/corpus/models.py`: `ContextTag` (7 значений), `prohibited_keywords`, `applicability`, валидатор взаимной исключительности `required_keywords ⊕ prohibited_keywords`.
- `app/types.py` (или место для `InconclusiveReason`): новый Literal `InconclusiveReason = Literal["check_not_implemented", "context_dependent", "evidence_missing"]`.
- `app/checks.py`:
  - `CheckResult.inconclusive_reason: InconclusiveReason | None` + валидатор «non-None только при status=inconclusive».
  - Новый универсальный обработчик `_check_prohibited_keywords` (ищет в plain-text, fail при первом совпадении).
  - Расширение `evaluate`: ветка `if signal.prohibited_keywords`; ветки «unknown check», `_not_implemented`, `combine` проставляют `inconclusive_reason="check_not_implemented"`.
  - Новый `aggregate_or` с приоритетом real-inconclusive над stub-inconclusive.
- Тесты:
  - `tests/test_corpus_models.py`: валидация `applicability` (валидный список / неизвестный тег → ValidationError), валидация `required_keywords ⊕ prohibited_keywords` (одновременно → ValidationError).
  - `tests/test_checks.py`:
    - `_check_prohibited_keywords`: fail при наличии хоть одного ключа (evidence = ключ), pass если нет, корректный case-insensitive поиск.
    - Новый `aggregate_or`: real-fail побеждает (любой fail → fail с evidence от первого fail); real-inconclusive побеждает stub-inconclusive (даже если stub стоит первым в списке); all-stub-inconclusive → итог с `check_not_implemented`; all pass → pass.
    - Ветка «unknown check» проставляет `check_not_implemented`.
    - `combine`-ветка проставляет `check_not_implemented`.

**DoD:** `make lint && make test` зелёные; корпус продолжает валидироваться без правок (новые поля опциональные); существующие тесты `test_checks.py` адаптированы под расширенный `CheckResult`.

### Этап 3. Удаление семантически нерелевантных sub-signals

- В `152-fz-personal-data.md`: удалить `dpo_contact_missing` (485-489) и `weak_security_headers` (544-548).
- `make corpus` — общее число нарушений 100 (мы убрали sub-signals, не violations).
- Точечный тест в `tests/test_corpus_loader_real.py`: оба нарушения имеют ровно 1 sub-signal.

**DoD:** corpus reloads, тесты зелёные.

### Этап 4. Скрытие заглушек в engine (breaking change контракта)

- `app/engine.py`:
  - `Finding` получает поле `inconclusive_reason: InconclusiveReason | None`.
  - **Подпись `_evaluate_violation` меняется с `-> Finding` на `-> Finding | None`.** Если `aggregated.status == "inconclusive"` и `aggregated.inconclusive_reason == "check_not_implemented"` → return None.
  - В `run_scan`: цикл пропускает None из `_evaluate_violation` (не добавляем в findings, не публикуем SSE `violation_evaluated`).
  - `_violation_to_finding` пробрасывает `inconclusive_reason` от aggregated в Finding.
- **Проверка callers `_evaluate_violation`:** найти grep'ом все вызовы; помимо `run_scan` могут быть в тестах (`test_engine.py`) и в моках. Обновить ожидаемые типы.
- `frontend/src/lib/types.ts`: добавить `inconclusive_reason: 'check_not_implemented' | 'context_dependent' | 'evidence_missing' | null` в `Finding` для типобезопасности (рендер не меняется).
- Тесты (новые, в `tests/test_engine.py`):
  - all-stubs violation → finding отсутствует в findings; on_event ни разу не позвал `violation_evaluated` для этой violation.
  - all-combine violation → аналогично отфильтровано.
  - mixed (real fail + stub) → Finding есть, status=fail, evidence от реального fail.
  - mixed (real inconclusive `evidence_missing` + stub) → Finding есть, status=inconclusive, `inconclusive_reason="evidence_missing"` (приоритет real над stub).
  - all-pass violation → Finding есть, status=pass.
- **Тесты-регрессия:** все существующие тесты `test_engine.py`, ожидающие `len(result.findings) == N` для конкретного N, могут начать падать — теперь N меньше из-за фильтрации stubs. Этап 4 включает разовый аудит и адаптацию этих ассертов.

**DoD:** все тесты зелёные (включая адаптированные); `mypy --strict` проходит для `app/engine.py` с новым `Finding | None` контрактом; на синтетической фикстуре с большим числом заглушек итоговый отчёт не содержит «пустых» inconclusive-карточек.

### Этап 5. `app/context.py` + интеграция

- Создать модуль `app/context.py`:
  - `ContextTag` импортирован из `app/corpus/models.py` (определён там в этапе 2).
  - `ScanContext(BaseModel, frozen=True)` с `active_tags: frozenset[ContextTag]`, метод `applies(violation) -> bool`.
  - `detect_context(artifacts: PageArtifacts) -> ScanContext` — **парсит HTML через BeautifulSoup один раз**, вычисляет `plain_text` один раз, передаёт `soup` и `text` приватным детекторам.
  - 7 приватных детекторов (включая `_detect_has_signing`). Каждый принимает `soup` и/или `text` и/или `artifacts.cookies`/`network_log` (для `_detect_payments`). Возвращает `bool`.
- `app/engine.py`:
  - После `scanner.collect`: `context = detect_context(artifacts)`. SSE можно опубликовать `context_detected` события с активными тегами (опционально).
  - `_evaluate_violation` принимает третий параметр `context: ScanContext`. **Первая проверка** в функции: `if not context.applies(violation): return None`. Это раньше, чем оценка signals — экономит вычисления.
- `tests/test_context.py` (новый): unit-тест каждого из 7 детекторов на минимальной HTML-фикстуре. Например:
  - `_detect_payments(soup)` для HTML с `<iframe src="https://yookassa.ru/..."`> → True.
  - `_detect_payments(soup)` для HTML с `<iframe src="https://youtube.com/..."`> → False.
  - `_detect_has_signing(soup)` для HTML с `<input type="checkbox" name="agree">` + `<button type="submit">` → True.
  - И т. д. для каждого детектора.
- `tests/test_engine.py`: тест с `applicability=[payments]` на фикстуре без платежей → finding отсутствует; на фикстуре с iframe yookassa → finding есть. Тест с пустым `applicability=()` → finding всегда оценивается.

**DoD:** новые тесты зелёные; engine корректно сужает выдачу; `detect_context` выполняется за <50ms на типичной странице (опционально проверить).

### Этап 6. Миграция корпуса

Батчи (последовательно):

1. **Платежи и e-commerce:** `161-fz-payment-system.md`, `54-fz-cash-registers.md`, `pp-2463-sale-rules.md`, `2300-1-consumer-protection.md`, `gk-rf-offer.md`.
2. **Подписания:** `63-fz-electronic-signature.md` — `[has_signing]` на все 7 нарушений.
3. **Реклама и инверсные ключи:** `38-fz-advertising.md` (включая 3 миграции на `prohibited_keywords`: `prohibited_keywords_in_content`, `unregistered_medicine_ad`, `bad_therapeutic_claims`), `ord-ad-marking.md`.
4. **Контентные ограничения 436-ФЗ:** `436-fz-children-protection.md` — `[media_18plus]` на age-gate/алкоголь-табак; **дополнительные миграции `required_keywords` → `prohibited_keywords`** на 4 sub-signals в `lgbt-propaganda`, `prohibited-content` (2 sub-signals: суицид, наркотики), `wrong-age-marking`.
5. **UGC:** `149-fz-information.md` — `[ugc]` на нарушения о модерации пользовательских комментариев.
6. **Универсальные — контрольная проверка, что НЕ помечены:** `152-fz`, `pp-1119`, `242-fz`, `53-fz`, `gk-rf-part-iv-copyright.md`.
7. **Финальная зачистка инверсных `required_keywords`:** пройти grep'ом по всем 49 случаям, мигрировать оставшиеся (после батчей 3-4 их должно быть ≤ 5).
8. **Текстовые триггер+эскейп:** ревизия sub-signals с одновременным непустым `required_keywords` и `required_absent` (в `38-fz`: `superlative_without_proof`, `unverifiable_specific_claims`, `bad_product_card_no_disclaimer.required_keywords`, `credit_ad_no_psk`, `credit_ad_no_warning`, `excessive_foreign_words_in_ads`). Решение по каждому — переделать на `html_patterns + required_absent` через `_check_pattern_with_escape`, либо пометить как known issue (это open question 4).
9. **Чистка `app/context.py` после ревью захода 1** (Nit 2-3 из code-review). Когда корпус размечен `[ad_content]` и `[media_18plus]`, появится статистика какие ключи реально нужны:
   - `_AD_CONTENT_KEYWORDS` — убрать избыточный `"лекарственн"` (подстрока `"лекарств"`); заменить хрупкие `"вино "`, `"займ "` (trailing space ломается перед знаком препинания) на word-boundary через regex или явный `\b`.
   - Дубль `_AD_CONTENT_KEYWORDS` ⊂ `_MEDIA_18PLUS_KEYWORDS` (9 ключей пересекаются: `табак`, `сигарет`, `алкогол`, `вино `, `пиво`, `вейп`, `казино`, `ставк`, `букмекер`). Решить: вынести общий набор в отдельную константу `_REGULATED_GOODS_KEYWORDS` и переиспользовать, либо оставить с явным комментарием «пересечение намеренное». Без правки — риск рассинхрона при правках одного из списков.

**DoD:** `make corpus && make lint && make test` зелёные; общее число нарушений = 100.

### Этап 7. Regression-тест + ручной прогон по habr

- Фикстуры `tests/fixtures/html/`: `habr-like-blog.html`, `ecommerce-like.html`, `payments-page.html`.
- `tests/test_engine_regression.py`: на `habr-like-blog.html` через `load_corpus(Path("docs/laws"))` и `run_scan`:
  - `len(failed_findings) <= 10`;
  - ни одно из failed не относится к 161-фз / 54-фз / pp-2463;
  - в результате нет findings с `inconclusive_reason="check_not_implemented"`.
- Ручной прогон: `uv run python -m app.scan https://habr.com/ru/feed/ > scan-after.json`; сравнить с baseline.

**Целевые метрики:**
- `fail` упал с 73 до ≤ 10.
- Общее число findings сократилось с 100 до ~35-40.
- В findings нет ни одного объекта с `inconclusive_reason="check_not_implemented"`.

**DoD:** regression-тест зелёный, ручной прогон укладывается в метрики.

### Этап 8. Закрытие итерации

- Статус в `docs/plan.md`: `🚧 → ✅`.
- Демо: команда + краткие цифры (было 73 fail / стало X fail).
- Обновление ADR-0003 по итогам реализации (если нужно).

---

## Список файлов

### Создаются

- `docs/tasks/iteration-06b-detection-fixes.md` (этот файл — детальный tasklist)
- `docs/adr/0003-context-gating-and-inverse-keywords.md`
- `app/context.py`
- `tests/test_context.py`
- `tests/test_engine_regression.py`
- `tests/fixtures/html/habr-like-blog.html`
- `tests/fixtures/html/ecommerce-like.html`
- `tests/fixtures/html/payments-page.html`

### Правятся (код)

- [app/corpus/models.py](../../app/corpus/models.py) — ContextTag, applicability, prohibited_keywords, валидаторы.
- [app/checks.py](../../app/checks.py) — `_check_prohibited_keywords`, `inconclusive_reason`, `evaluate`, `aggregate_or`.
- [app/engine.py](../../app/engine.py) — Finding с inconclusive_reason, ScanContext в `_evaluate_violation`, фильтрация None.
- `app/types.py` — опционально вынести `InconclusiveReason`.
- `frontend/src/lib/types.ts` — добавить `inconclusive_reason` в TS-интерфейс Finding.

### Правятся (документация)

- [docs/laws/schema.md](../laws/schema.md) — разделы applicability / prohibited_keywords / ContextTag.
- [docs/plan.md](../plan.md) — таблица итераций, карточка итерации 6б.

### Правятся (корпус, 15 файлов)

Все файлы `docs/laws/*.md` (детальный батч-план см. таблицу в разделе «Корпус») + пересборка `docs/laws/index.yml` через `make corpus`.

---

## Верификация end-to-end

```powershell
# До правок (baseline на отдельной ветке):
uv run python -m app.scan "https://habr.com/ru/feed/" > scan-habr-before.json

# После всех правок:
uv run python -m app.scan "https://habr.com/ru/feed/" > scan-habr-after.json

# Сравнение в Python REPL:
# import json
# before = json.load(open('scan-habr-before.json'))
# after  = json.load(open('scan-habr-after.json'))
# fail_before = [f for f in before['findings'] if f['status'] == 'fail']
# fail_after  = [f for f in after['findings']  if f['status'] == 'fail']
# print(f"fail: {len(fail_before)} → {len(fail_after)}")
```

Целевые цифры: было 73 fail → стало ≤ 10 fail; total findings было 100 → стало 30-40; никаких inconclusive из заглушек.

**Ожидаемый качественный состав финального отчёта по habr.com** (для проверки «достигнута ли цель»):

Что должно ОСТАТЬСЯ (реальные применимые проверки, корректные fail / pass):

- **152-ФЗ:** Google Analytics / Tag Manager без локализации (`script[src*="googletagmanager.com"]` — корректный fail для habr). Cookies без согласия (yandexuid, _ga и т.п. — корректный fail). Политика ПДн / содержание политики — fail или pass в зависимости от состояния footer. Согласие у форм. Итого 4-6 finding'ов.
- **53-ФЗ:** госязык — fail если есть кнопки на иностранном без перевода (Sign Up → Регистрация). Итого 1-2.
- **149-ФЗ UGC:** регистрация ОРИ (habr подпадает под определение ОРИ — это реальный fail). Итого 1.
- **436-ФЗ no-age-marking:** на главной habr нет возрастной маркировки 16+ — корректный fail. Итого 1.
- **ord-ad-marking:** если на habr есть рекламные посты с erid — pass; без erid — fail. Итого 1-2.

Что должно ИСЧЕЗНУТЬ из отчёта (ложные срабатывания, устранённые планом):

- ❌ Все 7 нарушений 161-ФЗ (платежи) — отфильтрованы по `applicability=[payments]`.
- ❌ Все ~5 нарушений 54-ФЗ (чеки) — отфильтрованы по `[payments]`.
- ❌ ~15 нарушений pp-2463 / 2300-1 / gk-rf-offer (e-commerce) — отфильтрованы по `[ecommerce]`.
- ❌ Все 7 нарушений 63-ФЗ (ПЭП) — отфильтрованы по `[has_signing]`.
- ❌ `152-fz-incident-notification-missed` — после Р3 все sub-signals — stubs/combine → отфильтровано.
- ❌ `152-fz-data-breach` — после Р3 stubs преобладают, missing_https/directory_listing — pass → отфильтровано или pass.
- ❌ `436-fz-lgbt-propaganda`, `prohibited-content`, `wrong-age-marking` — после миграции на `prohibited_keywords` ключи в DOM скорее всего не находятся → pass.
- ❌ Заглушки (`unknown check`): rkn_registry_lookup, internal_documents_audit, age_gate_bypass_test, profanity_filter, traffic_threshold и т. п. — скрыты.

Что МОЖЕТ остаться как остаточный шум (известные ограничения, отмечены в «Не делаем»):

- ⚠️ 38-ФЗ БАД/кредит/запрещёнка — если в фиде habr статьи с упоминанием регулируемых товаров → `ad_content` активен → `prohibited_keywords` может сматчить «VPN купить» в обзоре или «лечит» в медицинской статье. Это known issue «контент ≠ реклама», закрывается LLM в итерации 7.
- ⚠️ Гиперширокие селекторы в `gk-rf-part-iv-copyright` — оставят 3-4 fail, known issue вне 6б.

**Критерий «цель достигнута»:** fail ≤ 10, отчёт можно показать без оговорок про «4 громких ложных срабатывания» из исходной жалобы.

```powershell
make corpus    # 15 законов, 100 нарушений, integrity OK
make lint      # ruff + mypy strict
make test      # +регрессионный + 6 контекст-детекторов + новый обработчик + валидаторы
```

---

## Не делаем в этой итерации

- **LLM-реализация заглушек** (rkn_registry_lookup, tls_audit, internal_documents_audit и др.) — итерация 7. Заглушки скрываем, но не реализуем.
- **Multipage-обход** (страница политики, контактов) — отдельная архитектурная задача.
- **Полная реализация `combine`-сигналов** (композиция через AND/OR/NOT) — итерация 7 параллельно с LLM. В 6б combine-ветка в `evaluate` помечается как `inconclusive_reason="check_not_implemented"` и фильтруется вместе с другими стабами (см. Р5).
- **Внешние API регуляторов** (РКН, ЕРИР, реестр ОФД) — итерация 7+.
- **Калибровка детекторов контекста на ложноположительные срабатывания** (блог с одним упоминанием БАД → весь сайт получает `ad_content`-тег). Известная проблема порога; в 6б — простой «хоть одно упоминание есть»; точная калибровка — отдельный шаг при появлении статистики по реальным сайтам.
- **UI-секция «Не применимо к вашему сайту»** — сознательно НЕ добавляем. Для MVP «короче и точнее» лучше «подробнее».
- **Новый универсальный обработчик `_check_keyword_trigger_with_escape`** (текстовый триггер + текстовый эскейп). Затрагивает нарушения `38-fz-misleading-superlative-claims` (если упомянуто «лучший» — должна быть ссылка на исследование), `credit_ad_no_psk` (если упомянут «кредит» — должна быть ПСК), `38-fz-bad-no-disclaimer.bad_product_card_no_disclaimer` (если упомянут «БАД» — должен быть дисклеймер). Сейчас в YAML эти сигналы имеют `required_keywords` + `required_absent` параллельно, и универсальный `evaluate` оценивает их как два независимых sub-results через OR — что даёт fail при отсутствии любого слова из required_keywords и отсутствии required_absent (ложно). Возможные решения: (а) реализовать новый обработчик; (б) переделать сигналы на `html_patterns` (контейнер `[class*="ad" i]` или `[class*="banner" i]`) + `required_absent` через существующий `_check_pattern_with_escape`; (в) явно пометить такие нарушения «требует LLM» через `inconclusive_reason="context_dependent"` (новый смысл — «детерминированно сейчас невозможно»). **Решение для 6б:** вариант (в) — помечать `applicability=[ad_content]` (уже сделано) и пройти эти сигналы вручную; если в YAML переделка на html_patterns не получится — оставить как known issue. Точная реализация — на старте этапа 6.
- **Гиперширокие селекторы в `gk-rf-part-iv-copyright.md`** (`img[src^="https://"]`, `title`, `link[href*="fonts"]`) и в `53-fz-state-language.md` (`.banner, .promo, .ad-block, [class*="promo" i]`). Эти селекторы сматчатся на любом сайте, давая fail. Точечная ревизия отложена: семантика «есть ли изображение без указания лицензии», «использует ли сайт чужой бренд в title», «есть ли иностранный текст в рекламном блоке» требует более тонкой логики, выходящей за рамки CSS-селекторов. Отмечается как known issue MVP; в 7-й итерации может быть закрыто LLM-проверкой.
- **False positives от `ad_content` на медиа-сайтах с упоминаниями БАД/кредитов в статьях.** Это фундаментальное ограничение детерминированной логики: статья «обзор VPN-сервисов» содержит фразу «VPN купить», что после миграции на `prohibited_keywords` даст fail по `38-fz-prohibited-goods` (реклама VPN запрещена), хотя статья — контент, а не реклама. То же для лекарств, БАД, кредитов в редакционных материалах. **Закрывается только LLM** в итерации 7 (промпт «это реклама с коммерческим призывом или редакционный контент с упоминанием?»). В 6б — known issue, явно отмечается в ADR-0003.
- **False positives от `prohibited_keywords` для контентных запретов 436-фз на медиа-сайтах** (`['ЛГБТ', 'наркотик', 'способы суицида']` могут встретиться в новостной статье или научной публикации, не являясь пропагандой). Та же проблема контекста — закрывается только LLM.

---

## Открытые вопросы (на старте итерации)

1. **Граница `ad_content`-тега.** Помечаем все 13 нарушений 38-ФЗ или только БАД/кредиты/запрещёнка? Текущее предложение: ОРД-маркировка `[]` (универсально — любой сайт может содержать рекламные посты с erid), БАД и подобное — `[ad_content]`.
2. **Объём `[ugc]` в 149-ФЗ.** Нарушения о реестре ОРИ — технические, не зависят от UGC. Только нарушения о модерации пользовательских комментариев получают `[ugc]`. Точный список — детализация на этапе 6.
3. **Объём `[has_signing]` для 63-ФЗ.** Все 7 нарушений помечаются `[has_signing]`. Точный детектор: наличие `input[type="checkbox"][name*="agree" i]`, `button[name*="sign" i]`, форм регистрации с подтверждением. На лендинге без формы регистрации — тег не активен → все 63-ФЗ нарушения отфильтровываются.
4. **«Текстовый триггер + эскейп» подход.** Финальное решение по нарушениям типа «superlative_without_proof» — переделать на html_patterns+required_absent (через `_check_pattern_with_escape`) или ввести новый обработчик. Решается в начале этапа 6.
5. **Граница детектора `_detect_has_signing`.** Узкий вариант (чекбоксы с явным именем `agree`/`oferta`/`accept` + кнопка `sign`/`register`) пропустит форму с `<input type="checkbox" name="terms">` + `<button>Оформить</button>`. Широкий вариант (любой submit рядом с чекбоксом) активирует тег почти на всех сайтах с формой обратной связи, включая habr. **Предложение:** middle ground — чекбокс с label/name/id/value, содержащим один из {`agree`, `terms`, `consent`, `oferta`, `accept`, `согла`, `подтвержд`, `принима`} + наличие submit-кнопки в той же форме. Калибруется на фикстурах в этапе 5.
6. **Стоит ли вводить ещё один тег `has_pd_form`** (есть форма со сбором ПДн) для более строгого гейтинга нарушений pp-1119 и 242-фз? Сейчас они помечены `[]` (универсально), и `pp-1119-no-https` срабатывает на любом сайте без HTTPS, даже если форм ПДн нет. **Решение:** в 6б оставить `[]` (более широкое срабатывание — это не false positive, HTTPS нужен везде); если в будущем потребуется — добавим тег.

---

## Решения с контрольной точки 1 (для захода 2)

Зафиксированы после обсуждения 6 open questions выше. Используются при разметке корпуса в этапе 6.

### Q1. Граница `[ad_content]` для 38-ФЗ — **Вариант B (расширенный)**

В корпусе 38-ФЗ ровно **7 нарушений** (в плане раньше упоминалось «13» — ошибка, считались sub-signals).

- `[ad_content]` (5): `38-fz-prohibited-goods`, `38-fz-bad-no-disclaimer`, `38-fz-financial-services-no-disclosure`, `38-fz-hidden-advertising`, `38-fz-minors-misuse`.
- `[]` универсально (2): `38-fz-misleading-claims`, `38-fz-foreign-words-untranslated`.

Логика: hidden-advertising и minors-misuse явно про рекламный контекст → гейт. Misleading-claims и foreign-words применимы к любому рекламному тексту, включая «лучший сервис» на лендинге продукта без регулируемых товаров → оставляем универсальными как баланс охвата vs шума.

### Q2. Объём `[ugc]` в 149-ФЗ — **Вариант B (UGC-прокси)**

В корпусе 149-ФЗ **8 нарушений**.

- `[ugc]` (2): `149-fz-ori-not-registered`, `149-fz-social-network-not-registered`.
- `[]` универсально (6): остальные (`no-owner-info`, `news-aggregator-not-registered`, `prohibited-info-distribution`, `copyright-infringement`, `in-pd-offenders-registry`, `missing-age-rating`).

Логика: формальное определение ОРИ и соцсети не требует UGC, но UI-индикатор UGC (textarea, комментарии, форум) — хороший практический прокси: на лендинге без форм эти нарушения вряд ли применимы.

### Q3. Объём `[has_signing]` для 63-ФЗ — **Вариант A (все 7)**

Все 7 нарушений 63-ФЗ помечаются `[has_signing]`. Концептуально каждое связано с процессом электронной подписи; без forms с consent-checkbox + submit закон не применим.

### Q4. «Текстовый триггер + эскейп» — **Вариант B (known issue + context_dependent)**

В заходе 2 в `app/checks.py`:
- В `evaluate` добавить ветку: «если у сигнала есть `required_keywords` И `required_absent`, но нет `html_patterns`» → вернуть `inconclusive` с `inconclusive_reason="context_dependent"`.
- В `app/engine.py:_evaluate_violation` добавить `context_dependent` к списку скрываемых причин (рядом с `check_not_implemented`).

YAML не трогаем — 6 затронутых sub-signals остаются как есть. После реализации LLM в итерации 7 они «оживут» через семантическую LLM-проверку.

**Записано в [docs/plan.md](../plan.md) карточка итерации 7 → раздел «Открытое после 6б»:** в итерации 7 пересмотреть, нужен ли отдельный free-fallback `_check_keyword_trigger_with_escape` (детерминированный сигнал с шумом «контент ≠ реклама») по статистике использования.

### Q5. Граница `_detect_has_signing` — **Middle ground (уже реализован в этапе 5)**

Подтверждено: чекбокс с консент-намёком (8 hints, включая русские `согла`, `подтвержд`, `принима`) + submit-кнопка в той же форме. Реализация в `app/context.py:262-321`, покрыто тестами.

### Q6. Тег `has_pd_form` — **Не вводить**

Закрытый словарь `ContextTag` остаётся из 7 значений. pp-1119 и 242-ФЗ остаются `applicability=[]` (универсально). HTTPS — общая техническая гигиена 2026 года, не требует гейтинга по наличию форм. Если статистика после деплоя покажет реальную потребность — отдельным ADR.

---

## Trace 4 жалоб пользователя через план

Проверка на конкретных нарушениях из отчёта `temp/legal-audit-habr.com-2026-05-14.pdf`.

### Жалоба 1: «Несвоевременное уведомление РКН об инциденте с ПДн»

- **Сейчас:** detection имеет 2 sub-signals — `incident_response_procedure_missing` (check: `internal_documents_audit` — заглушка) и `dpo_contact_missing` (`required_keywords ['ответственный за обработку', 'DPO']` — выдаёт fail на habr.com, т.к. слов нет в DOM). aggregate_or: fail + inconclusive = fail.
- **После плана:** `dpo_contact_missing` удалён (Р3). Остаётся `incident_response_procedure_missing` → stub inconclusive с reason=check_not_implemented. _evaluate_violation возвращает None. **Finding не появляется. ✅**

### Жалоба 2: «Утечка персональных данных вследствие нарушения мер защиты»

- **Сейчас:** 4 sub-signals — `missing_https` (pass для HTTPS-habr), `weak_security_headers` (fail по отсутствию CSP), `public_database_endpoint` (stub), `directory_listing_enabled` (pass). aggregate_or: pass + fail + inconclusive + pass = fail.
- **После плана:** `weak_security_headers` удалён (Р3). Остаются: `missing_https` (pass), `public_database_endpoint` (stub inconclusive, reason=check_not_implemented), `directory_listing_enabled` (pass). По уточнённой логике aggregate_or: нет fail, нет real-inconclusive, есть только stub-inconclusive → итог inconclusive с reason=check_not_implemented → _evaluate_violation возвращает None. **Finding не появляется. ✅**

### Жалоба 3: «Приём платежей по картам без лицензированного эквайринга»

- **Сейчас:** 2 sub-signals — `card_input_on_merchant_form` (pattern_with_escape; на habr нет card input → pass) и `no_payment_provider_disclosure` (lookup_pages_by_keywords ['эквайер'] → fail). aggregate_or: pass + fail = fail.
- **После плана:** `applicability=[payments]`. На habr.com `_detect_payments(artifacts)` возвращает False (нет card input, нет iframe yookassa/cloudpayments, нет ссылок `/checkout`). `context.applies(violation)` = False → _evaluate_violation возвращает None. **Finding не появляется. ✅**

### Жалоба 4: «Реклама запрещённых товаров: наркотики, табак, оружие...»

- **Сейчас:** 2 sub-signals — `prohibited_keywords_in_content` (`required_keywords ['купить табак', 'купить сигареты', ...]` → fail при отсутствии всех ключей) и `unregistered_medicine_ad` (`required_keywords ['лечит', 'вылечит', 'от всех болезней']`). На habr.com missing → fail.
- **После плана:** `applicability=[ad_content]`. Мигрировано на `prohibited_keywords` (правильная семантика: fail при наличии ключа).
  - **Сценарий А (habr без статей про регулируемые товары):** `_detect_ad_content(artifacts)` = False → нарушение отфильтровано. **Finding не появляется. ✅**
  - **Сценарий Б (habr со статьями про БАД/VPN/кредиты в фиде):** `_detect_ad_content` = True. Проверка идёт. Если в plain-text есть «купить VPN» или «лечит» (в редакционной статье) → `_check_prohibited_keywords` → fail. **Это остаточный false positive «статья ≠ реклама». ⚠️**
- **Жалоба пользователя** конкретно про «`missing keywords`» — это инверсная семантика, она полностью устранена миграцией на `prohibited_keywords`. **✅** Но новый класс false positive (контент с упоминанием регулируемых товаров) — known issue, явно отмечен в «Не делаем».

---

## Mental-сценарии для проверки плана

### Сценарий А: маленький лендинг продукта (без e-commerce и оплаты)

Одна страница, форма заявки `email+phone+name`, кнопка «Оставить заявку», без корзины, без цен, без упоминаний платежей.

- `ScanContext.active_tags = frozenset()` (ни один тег не активен; `has_signing` опционально, если есть чекбокс согласия).
- **Применимые:** 152-ФЗ (форма ПДн → политика, согласие, локализация), 53-ФЗ (госязык), 436-ФЗ (универсальные нарушения: возрастная маркировка, lgbt-propaganda через prohibited_keywords), gk-rf-part-iv (общие — но известны грубые селекторы), pp-1119 (HTTPS), 242-ФЗ.
- **Не применимые:** 161-ФЗ (нет payments), 54-ФЗ (нет payments), pp-2463 (нет ecommerce), 2300-1 (нет ecommerce), gk-rf-offer (нет ecommerce), 63-ФЗ (нет has_signing), 38-ФЗ БАД/кредит/запрещёнка (нет ad_content), 149-ФЗ UGC.
- Ожидаемое поведение: уровень шума резко меньше; finding'ов 15-25 (вместо 100), реальные fail — только связанные с ПДн / госязыком / возрастной маркировкой.

### Сценарий Б: интернет-магазин с эквайрингом через iframe yookassa

Каталог товаров, корзина, ссылки `/checkout`, оплата через iframe yookassa, политика, оферта, страница возврата.

- `ScanContext.active_tags = {ecommerce, payments, has_signing}`.
- **Применимые:** всё универсальное + 161-ФЗ + 54-ФЗ + pp-2463 + 2300-1 + gk-rf-offer + 63-ФЗ.
- `161-fz-no-licensed-acquiring.card_input_on_merchant_form`: `_check_pattern_with_escape` с card input + escape iframe yookassa. На сайте card input нет (используется iframe) → trigger не сработал → pass. `no_payment_provider_disclosure`: если на сайте упомянут «эквайер» или название провайдера → pass.
- Ожидаемое поведение: false positive по эквайрингу не появляется, если магазин правильно использует iframe.

### Сценарий В: госсайт (информационный, без UGC, без рекламы)

Статичные страницы с информацией о ведомстве, контакты, объявления.

- `ScanContext.active_tags = frozenset()`.
- **Применимые:** 152-ФЗ (минимум, если есть форма обратной связи), 53-ФЗ (госязык — особенно строго для гос), gk-rf-part-iv (общие).
- Не применимые: всё контекстное.

### Сценарий Г: медиа-портал (как habr)

Статьи, комментарии, рекламные посты с erid, без оплаты, без e-commerce.

- `ScanContext.active_tags = {ugc, ad_content?}`. Тег `ad_content` зависит от наличия упоминаний БАД/кредитов в текущей выборке статей фида.
- **Применимые:** 152-ФЗ, 53-ФЗ, 436-ФЗ (универсальные), ord-ad-marking (если есть рекламные посты), 149-ФЗ UGC.
- **Если `ad_content` активен:** срабатывают 38-ФЗ БАД/кредит/запрещёнка через `prohibited_keywords`. Часть из них — false positive «статья ≠ реклама» (см. жалоба 4 сценарий Б).
- Ожидаемое поведение для habr.com: с 73 fail снижение до 10-15 fail. Основные оставшиеся: 152-ФЗ (политика/cookies), 53-ФЗ (если применимо), ord-ad-marking, 149-ФЗ UGC, возможные «статья ≠ реклама» false positives.

### Сценарий Д: магазин БАД

Каталог БАД с описаниями, корзина, оплата.

- `ScanContext.active_tags = {ecommerce, payments, ad_content, has_signing}`.
- **Применимые:** всё + 38-ФЗ БАД (правильно).
- `38-fz-bad-no-disclaimer.bad_therapeutic_claims` (мигрировано на prohibited_keywords): fail если описание содержит «лечит/избавит» → корректное срабатывание.
- Это работает по назначению.

### Сценарий Е: букмекерская площадка 18+

Ставки, age-gate модал.

- `ScanContext.active_tags = {media_18plus, has_signing}`.
- **Применимые:** 436-ФЗ 18+, 38-ФЗ (контроль рекламы алкоголя/казино), 152-ФЗ.
- `436-fz-no-age-gate-for-18plus`: если age-gate реализован → pass; если нет → fail (корректно).
