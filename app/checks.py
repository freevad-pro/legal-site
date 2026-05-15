"""Реестр check-функций и универсальные обработчики сигналов.

Контракт:

- `CheckFunction = Callable[[PageSignal | SiteSignal, PageArtifacts], CheckResult]`
- Все check-функции **синхронные**. Engine — async (нужен `await scanner.collect`),
  но проход по сигналам — sync; HTTP внутри check (httpx.Client) не блокирует
  loop надолго (≤10 сек на запрос).
- Если у сигнала задано `signal.check`, движок вызывает `REGISTRY[name]`.
  Если имени нет в реестре или функция — `_not_implemented`, возвращается
  `inconclusive`.
- Если `signal.check` пуст, движок собирает универсальные суб-результаты по
  каждому заданному полю (`html_patterns`, `required_absent`, …) и агрегирует
  их через OR (`fail` если хоть один fail; `pass` если все pass; иначе
  `inconclusive`).
- Доступ к extra-полям сигналов — через `signal.model_extra`.

Семантика пары `html_patterns` + `required_absent`:

- `html_patterns` без `required_absent` — «нашли подозрительный элемент → fail».
- `required_absent` без `html_patterns` — «обязательный элемент → должен присутствовать
  где-то в документе, иначе fail» (это документ-скоуп).
- `html_patterns` + `required_absent` — **триггер + эскейп**:
  - Если триггер `html_patterns` ничего не нашёл — `pass` (повод для проверки не возник).
  - Если все `html_patterns` — голые контейнерные теги (`footer|header|main|body|
    nav|article|section|aside`) — собираем все найденные контейнеры. Если **хоть
    у одного** есть `required_absent` элемент → `pass` (например, в корневом
    `<footer>` сайта есть ссылка на политику — nested-`<footer>`'ы карточек
    статей её отсутствие не валит). Если ни у одного нет → `fail` с evidence
    первого контейнера. Логика «хоть один с эскейпом → pass» нужна для сайтов
    с nested-структурой (Vue/React SPA): множественные `<footer class="tm-block__footer">`
    внутри карточек контента — типичный паттерн, и `<footer>` сайта — лишь один из них.
  - Иначе (document-scope): триггер сработал; если в документе есть хоть один
    `required_absent` элемент → `pass` («рядом есть нужный элемент»), иначе → `fail`.

Семантика `required_keywords` в итерации 3 — поиск в **plain-text главной**.
Источник = политика будет реализован в итерации 6+ (через расширение схемы).
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Iterable
from datetime import date
from urllib.parse import unquote, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup, Tag
from pydantic import BaseModel, ConfigDict, model_validator
from soupsieve.util import SelectorSyntaxError

from app.corpus.models import PageSignal, SiteSignal
from app.scanner import PageArtifacts
from app.types import InconclusiveReason, Status

logger = logging.getLogger(__name__)

Signal = PageSignal | SiteSignal

_CONTAINER_TAGS = frozenset(
    {"footer", "header", "main", "body", "nav", "article", "section", "aside"}
)

_POLICY_URL_KEYWORDS = (
    "политика",
    "конфиденциальн",
    "персональн",
    "обработк",
    "privacy",
    "policy",
    "personal",
    "pdn",
)


class CheckResult(BaseModel):
    """Результат проверки одного сигнала."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: Status
    evidence: str | None = None
    explanation: str | None = None
    inconclusive_reason: InconclusiveReason | None = None

    @model_validator(mode="after")
    def _reason_only_when_inconclusive(self) -> CheckResult:
        if self.inconclusive_reason is not None and self.status != "inconclusive":
            raise ValueError(
                f"inconclusive_reason is set ({self.inconclusive_reason!r}) "
                f"but status is {self.status!r}; reason is only valid for inconclusive"
            )
        return self


CheckFunction = Callable[[Signal, PageArtifacts], CheckResult]


def _truncate(value: str, limit: int = 200) -> str:
    value = " ".join(value.split())
    if len(value) <= limit:
        return value
    return value[: limit - 1] + "…"


def _parse(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def _safe_select(node: BeautifulSoup | Tag, selector: str) -> list[Tag]:
    """Безопасный `soup.select`: невалидный CSS-селектор → пустой результат.

    bs4/soupsieve кидает `SelectorSyntaxError` на неподдерживаемые конструкции
    (например, deprecated `:contains("кириллица")`). Не хотим, чтобы один
    дефектный селектор в корпусе валил весь скан — логируем WARNING и
    продолжаем.
    """

    try:
        return [t for t in node.select(selector) if isinstance(t, Tag)]
    except SelectorSyntaxError as exc:
        logger.warning("invalid CSS selector %r: %s", selector, exc)
        return []


def _plain_text(soup: BeautifulSoup) -> str:
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return " ".join(soup.get_text(separator=" ", strip=True).split())


def _is_container_selector(selector: str) -> bool:
    return selector.strip().lower() in _CONTAINER_TAGS


# ---------------------------------------------------------------------------
# Универсальные обработчики (не в REGISTRY)
# ---------------------------------------------------------------------------


def _check_html_patterns_only(patterns: Iterable[str], artifacts: PageArtifacts) -> CheckResult:
    """`html_patterns` без `required_absent`: «нашли подозрительный элемент → fail»."""
    soup = _parse(artifacts.html)
    for pattern in patterns:
        matches = _safe_select(soup, pattern)
        if matches:
            return CheckResult(
                status="fail",
                evidence=_truncate(str(matches[0])),
                explanation=f"selector matched: {pattern}",
            )
    return CheckResult(status="pass", explanation="no html_patterns matched")


def _check_required_absent_only(
    required_absent: tuple[str, ...], artifacts: PageArtifacts
) -> CheckResult:
    """`required_absent` без триггера: элемент обязан присутствовать в документе."""
    soup = _parse(artifacts.html)
    if any(_safe_select(soup, sel) for sel in required_absent):
        return CheckResult(
            status="pass",
            explanation="at least one required element present in document",
        )
    return CheckResult(
        status="fail",
        explanation=f"none of required elements found: {list(required_absent)}",
    )


def _check_pattern_with_escape(
    html_patterns: tuple[str, ...],
    required_absent: tuple[str, ...],
    artifacts: PageArtifacts,
) -> CheckResult:
    """Триггер + эскейп. См. docstring модуля."""
    soup = _parse(artifacts.html)

    scope_is_containers = all(_is_container_selector(p) for p in html_patterns)

    if scope_is_containers:
        containers: list[Tag] = []
        for pattern in html_patterns:
            containers.extend(_safe_select(soup, pattern))
        if not containers:
            return CheckResult(
                status="inconclusive",
                explanation=f"trigger containers not found: {list(html_patterns)}",
            )
        for container in containers:
            if any(_safe_select(container, sel) for sel in required_absent):
                return CheckResult(
                    status="pass",
                    explanation="at least one container has an escape element",
                )
        return CheckResult(
            status="fail",
            evidence=_truncate(str(containers[0])),
            explanation=(
                f"no container has any of the escape elements: {list(required_absent)}"
            ),
        )

    triggers: list[Tag] = []
    for pattern in html_patterns:
        triggers.extend(_safe_select(soup, pattern))
    if not triggers:
        return CheckResult(status="pass", explanation="trigger not matched")
    if any(_safe_select(soup, sel) for sel in required_absent):
        return CheckResult(status="pass", explanation="escape elements present in document")
    return CheckResult(
        status="fail",
        evidence=_truncate(str(triggers[0])),
        explanation=f"trigger matched without escape: {list(required_absent)}",
    )


def _check_required_keywords(keywords: Iterable[str], artifacts: PageArtifacts) -> CheckResult:
    soup = _parse(artifacts.html)
    text = _plain_text(soup).lower()
    missing = [kw for kw in keywords if kw.lower().strip() and kw.lower().strip() not in text]
    if missing:
        return CheckResult(
            status="fail",
            explanation=f"missing keywords in main page text: {missing}",
        )
    return CheckResult(status="pass", explanation="all keywords present in main page text")


def _check_prohibited_keywords(keywords: Iterable[str], artifacts: PageArtifacts) -> CheckResult:
    """Обратная семантика `_check_required_keywords`: fail при наличии ключа.

    Ищем подстроку в plain-text главной (без word-boundary — это known limitation,
    см. ADR-0003). При первом совпадении возвращаем `fail` с найденным ключом в
    evidence. Пустые ключи пропускаем.
    """

    soup = _parse(artifacts.html)
    text = _plain_text(soup).lower()
    for kw in keywords:
        normalized = kw.lower().strip()
        if not normalized:
            continue
        if normalized in text:
            return CheckResult(
                status="fail",
                evidence=kw,
                explanation=f"prohibited keyword found in main page text: {kw!r}",
            )
    return CheckResult(
        status="pass",
        explanation="no prohibited keywords found in main page text",
    )


def _check_pattern_contains_prohibited(
    html_patterns: tuple[str, ...],
    prohibited_keywords: tuple[str, ...],
    artifacts: PageArtifacts,
) -> CheckResult:
    """Контекстный prohibited: ищем ключи ВНУТРИ найденных html_patterns-элементов.

    Симметричен `_check_pattern_with_escape`, но «эскейп» текстовый и инверсный:
    мы ищем не отсутствие селектора, а присутствие подстроки внутри найденного
    блока. Семантика — «иностранное слово в рекламном блоке без перевода»
    (38-ФЗ, ст. 5 ч. 11): фраза «BUY NOW» внутри `<button>` или `.banner` → fail;
    та же фраза вне триггерных элементов (произвольный текст, `<script>`,
    атрибуты других тегов) → игнорируется.

    - html_patterns ничего не сматчил → pass (нет повода для проверки).
    - Триггер сработал, в каком-либо элементе встретился ключ → fail
      (evidence = ключ, explanation указывает на матчивший селектор).
    - Триггер сработал, ключей нет → pass.

    Без word-boundary (как и в `_check_prohibited_keywords`); предпочитайте
    многословные ключи вроде «BUY NOW», чтобы избегать ложных матчей.
    """

    soup = _parse(artifacts.html)
    normalized = [
        (raw, raw.lower().strip()) for raw in prohibited_keywords if raw.lower().strip()
    ]
    for pattern in html_patterns:
        for element in _safe_select(soup, pattern):
            element_text = " ".join(element.get_text(separator=" ", strip=True).split()).lower()
            if not element_text:
                continue
            for raw, kw in normalized:
                if kw in element_text:
                    return CheckResult(
                        status="fail",
                        evidence=raw,
                        explanation=(
                            f"prohibited keyword {raw!r} found inside element "
                            f"matched by selector {pattern!r}"
                        ),
                    )
    return CheckResult(
        status="pass",
        explanation="no prohibited keywords found inside trigger elements",
    )


def _check_required_headers(required: Iterable[str], artifacts: PageArtifacts) -> CheckResult:
    present = {key.lower() for key in artifacts.headers}
    missing = [h for h in required if h.lower() not in present]
    if missing:
        return CheckResult(
            status="fail",
            explanation=f"missing response headers: {missing}",
        )
    return CheckResult(status="pass", explanation="all required headers present")


def _check_required_protocol(scheme: str, artifacts: PageArtifacts) -> CheckResult:
    actual = urlparse(artifacts.url).scheme
    if actual.lower() != scheme.lower():
        return CheckResult(
            status="fail",
            evidence=artifacts.url,
            explanation=f"expected protocol {scheme!r}, got {actual!r}",
        )
    return CheckResult(status="pass", explanation=f"protocol matches {scheme!r}")


def aggregate_or(results: Iterable[CheckResult]) -> CheckResult:
    """Объединить несколько суб-результатов одного сигнала через OR.

    Приоритеты:
    1. Хоть один fail → итог fail (evidence/explanation от первого fail).
    2. Иначе хоть один **реальный** inconclusive (с `inconclusive_reason ≠
       check_not_implemented`) → итог inconclusive с reason от первого реального.
    3. Иначе если все inconclusive — заглушки (`check_not_implemented`) → итог
       inconclusive с reason=`check_not_implemented` (такой finding будет скрыт
       engine'ом, см. ADR-0003).
    4. Иначе все pass → итог pass.

    Без п. 2-3 порядок sub_signals в YAML определял бы, скрыт ли finding,
    что давало бы нестабильное поведение.
    """

    results = list(results)
    if not results:
        return CheckResult(
            status="inconclusive",
            explanation="no sub-results to aggregate",
            inconclusive_reason="evidence_missing",
        )

    fails = [r for r in results if r.status == "fail"]
    if fails:
        first = fails[0]
        return CheckResult(status="fail", evidence=first.evidence, explanation=first.explanation)

    inconclusives = [r for r in results if r.status == "inconclusive"]
    if inconclusives:
        real = [r for r in inconclusives if r.inconclusive_reason != "check_not_implemented"]
        chosen = real[0] if real else inconclusives[0]
        return CheckResult(
            status="inconclusive",
            evidence=chosen.evidence,
            explanation=chosen.explanation,
            inconclusive_reason=chosen.inconclusive_reason,
        )

    return CheckResult(status="pass", explanation="all sub-checks passed")


# ---------------------------------------------------------------------------
# Helper для check-функций, которым нужна страница политики (заглушки в этапе 2)
# ---------------------------------------------------------------------------


def _find_policy_url(artifacts: PageArtifacts) -> str | None:
    """Найти первую ссылку на главной, ведущую на страницу политики.

    Возвращает абсолютный URL или None. Используется именными check-функциями
    `text_length_threshold`, `date_in_document` и `http_status_check`.
    Поиск устойчив к percent-encoded href вида `/%D0%BF%D0%BE%D0%BB…` — мы
    разворачиваем их через `unquote` перед сравнением.
    """

    soup = _parse(artifacts.html)
    for anchor in soup.find_all("a"):
        if not isinstance(anchor, Tag):
            continue
        href = anchor.get("href")
        if not isinstance(href, str) or not href.strip():
            continue
        text_lc = anchor.get_text(separator=" ", strip=True).lower()
        href_lc = unquote(href).lower()
        if any(kw in text_lc or kw in href_lc for kw in _POLICY_URL_KEYWORDS):
            return urljoin(artifacts.url, href)
    return None


# ---------------------------------------------------------------------------
# Заглушка для не реализованных в итерации 3 check-функций
# ---------------------------------------------------------------------------


def _not_implemented(signal: Signal, artifacts: PageArtifacts) -> CheckResult:
    del artifacts
    name = signal.check or "<unknown>"
    return CheckResult(
        status="inconclusive",
        explanation=f"check {name!r} not implemented in iteration 3",
        inconclusive_reason="check_not_implemented",
    )


# ---------------------------------------------------------------------------
# Именные check-функции (реализуем 7 из 18; остальные — заглушки)
# ---------------------------------------------------------------------------

_PD_FIELD_SELECTORS: tuple[str, ...] = (
    'input[type="email"]',
    'input[type="tel"]',
    'input[name*="email" i]',
    'input[name*="phone" i]',
    'input[name*="tel" i]',
    'input[name*="name" i]',
    'input[name*="fio" i]',
    'textarea[name*="message" i]',
)

_PRIVACY_LINK_KEYWORDS: tuple[str, ...] = (
    "политика",
    "конфиденциальн",
    "обработк",
    "согласи",
    "персональн",
    "privacy",
    "policy",
    "personal",
)


def _is_pd_form(form: Tag) -> bool:
    return any(_safe_select(form, sel) for sel in _PD_FIELD_SELECTORS)


def link_near_form_to_privacy(signal: Signal, artifacts: PageArtifacts) -> CheckResult:
    """Возле PD-форм должна быть ссылка на политику/текст согласия.

    Алгоритм: ищем все `<form>`, отфильтровываем PD-формы (с email/tel/name/...).
    Для каждой PD-формы — ищем `<a>` внутри `<form>` или в её родителе с глубиной
    ≤ 2 по ключевым словам в тексте/href. Хоть одна форма без такой ссылки → fail.
    """

    soup = _parse(artifacts.html)
    forms = [f for f in soup.find_all("form") if isinstance(f, Tag) and _is_pd_form(f)]
    if not forms:
        return CheckResult(status="inconclusive", explanation="no PD forms found on page")

    extra_keywords = tuple((signal.model_extra or {}).get("keywords", ()))
    keywords = tuple(kw.lower() for kw in (*_PRIVACY_LINK_KEYWORDS, *extra_keywords))

    def _link_matches(anchor: Tag) -> bool:
        href = anchor.get("href")
        text = anchor.get_text(separator=" ", strip=True).lower()
        href_lc = href.lower() if isinstance(href, str) else ""
        return any(kw in text or kw in href_lc for kw in keywords)

    def _has_privacy_link(form: Tag) -> bool:
        anchors: list[Tag] = []
        anchors.extend(a for a in form.find_all("a") if isinstance(a, Tag))
        parent = form.parent
        depth = 0
        while isinstance(parent, Tag) and depth < 2:
            anchors.extend(a for a in parent.find_all("a") if isinstance(a, Tag))
            parent = parent.parent
            depth += 1
        return any(_link_matches(a) for a in anchors)

    for form in forms:
        if not _has_privacy_link(form):
            return CheckResult(
                status="fail",
                evidence=_truncate(str(form)),
                explanation="PD form has no privacy/consent link nearby",
            )
    return CheckResult(status="pass", explanation="every PD form has a privacy link nearby")


def lookup_pages_by_keywords(signal: Signal, artifacts: PageArtifacts) -> CheckResult:
    """В DOM главной должна быть `<a>`-ссылка по ключевым словам.

    Ключевые слова из `signal.model_extra["keywords"]` (если нет — берём
    дефолтный набор `_POLICY_URL_KEYWORDS`). Возвращает `pass` + evidence
    с найденным абсолютным URL; `fail` — если ни одна ссылка не подошла.
    """

    soup = _parse(artifacts.html)
    raw_keywords = (signal.model_extra or {}).get("keywords") or _POLICY_URL_KEYWORDS
    keywords = tuple(str(kw).strip().lower() for kw in raw_keywords if str(kw).strip())
    if not keywords:
        return CheckResult(status="inconclusive", explanation="no keywords provided")

    for anchor in soup.find_all("a"):
        if not isinstance(anchor, Tag):
            continue
        href = anchor.get("href")
        if not isinstance(href, str) or not href.strip():
            continue
        text_lc = anchor.get_text(separator=" ", strip=True).lower()
        href_lc = unquote(href).lower()
        if any(kw in text_lc or kw in href_lc for kw in keywords):
            return CheckResult(
                status="pass",
                evidence=urljoin(artifacts.url, href),
                explanation="matching link found in DOM",
            )
    return CheckResult(status="fail", explanation="no matching link found in DOM")


def http_status_check(signal: Signal, artifacts: PageArtifacts) -> CheckResult:
    """Проверка HTTP-статуса страницы политики (URL ищется через `_find_policy_url`)."""
    expected_raw = (signal.model_extra or {}).get("expected_status", 200)
    try:
        expected = int(expected_raw)
    except (TypeError, ValueError):
        return CheckResult(
            status="inconclusive",
            explanation=f"invalid expected_status: {expected_raw!r}",
        )

    url = _find_policy_url(artifacts)
    if url is None:
        return CheckResult(status="inconclusive", explanation="policy URL not found on page")

    try:
        with httpx.Client(timeout=10.0, follow_redirects=True) as client:
            response = client.get(url)
    except httpx.HTTPError as exc:
        return CheckResult(
            status="inconclusive",
            evidence=url,
            explanation=f"http error: {exc}",
        )

    if response.status_code == expected:
        return CheckResult(
            status="pass",
            evidence=url,
            explanation=f"status {response.status_code} matches expected {expected}",
        )
    return CheckResult(
        status="fail",
        evidence=url,
        explanation=f"expected status {expected}, got {response.status_code}",
    )


def _fetch_text(url: str) -> str | None:
    """Скачать страницу и вернуть plain-text.

    Используется именными check-функциями для страницы политики. Декодирование
    делегируется BeautifulSoup: на вход подаём `response.content` (bytes) — bs4
    через `UnicodeDammit` смотрит на BOM, `<meta charset>` и HTTP Content-Type,
    что закрывает старые русские сайты, отдающие cp1251 без `charset` в HTTP
    header.
    """

    try:
        with httpx.Client(timeout=10.0, follow_redirects=True) as client:
            response = client.get(url)
    except httpx.HTTPError:
        return None
    if response.status_code != 200:
        return None
    soup = BeautifulSoup(
        response.content,
        "html.parser",
        from_encoding=response.encoding,
    )
    return _plain_text(soup)


def text_length_threshold(signal: Signal, artifacts: PageArtifacts) -> CheckResult:
    """Текст страницы политики должен быть не короче `min_chars` (default 1500)."""
    min_chars_raw = (signal.model_extra or {}).get("min_chars", 1500)
    try:
        min_chars = int(min_chars_raw)
    except (TypeError, ValueError):
        return CheckResult(
            status="inconclusive",
            explanation=f"invalid min_chars: {min_chars_raw!r}",
        )

    url = _find_policy_url(artifacts)
    if url is None:
        return CheckResult(status="inconclusive", explanation="policy URL not found on page")
    text = _fetch_text(url)
    if text is None:
        return CheckResult(
            status="inconclusive",
            evidence=url,
            explanation="failed to fetch policy",
        )

    if len(text) < min_chars:
        return CheckResult(
            status="fail",
            evidence=url,
            explanation=f"policy text length {len(text)} < {min_chars}",
        )
    return CheckResult(
        status="pass",
        evidence=url,
        explanation=f"policy text length {len(text)} ≥ {min_chars}",
    )


_DATE_DDMMYYYY_RE = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b")
_DATE_ISO_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_RU_MONTHS = {
    "января": 1,
    "февраля": 2,
    "марта": 3,
    "апреля": 4,
    "мая": 5,
    "июня": 6,
    "июля": 7,
    "августа": 8,
    "сентября": 9,
    "октября": 10,
    "ноября": 11,
    "декабря": 12,
}
_DATE_RU_RE = re.compile(
    r"\b(\d{1,2})\s+(" + "|".join(_RU_MONTHS.keys()) + r")\s+(\d{4})\b",
    re.IGNORECASE,
)


def _extract_dates(text: str) -> list[date]:
    found: list[date] = []
    for match in _DATE_DDMMYYYY_RE.finditer(text):
        try:
            found.append(date(int(match.group(3)), int(match.group(2)), int(match.group(1))))
        except ValueError:
            continue
    for match in _DATE_ISO_RE.finditer(text):
        try:
            found.append(date(int(match.group(1)), int(match.group(2)), int(match.group(3))))
        except ValueError:
            continue
    for match in _DATE_RU_RE.finditer(text):
        try:
            month = _RU_MONTHS[match.group(2).lower()]
            found.append(date(int(match.group(3)), month, int(match.group(1))))
        except (ValueError, KeyError):
            continue
    return found


def date_in_document(signal: Signal, artifacts: PageArtifacts) -> CheckResult:
    """Дата редакции политики должна быть не старше 2 лет."""
    del signal  # параметры не используются — всё из текущего контекста
    url = _find_policy_url(artifacts)
    if url is None:
        return CheckResult(status="inconclusive", explanation="policy URL not found on page")
    text = _fetch_text(url)
    if text is None:
        return CheckResult(
            status="inconclusive",
            evidence=url,
            explanation="failed to fetch policy",
        )

    dates = _extract_dates(text)
    if not dates:
        return CheckResult(
            status="fail",
            evidence=url,
            explanation="no document date found in policy text",
        )

    latest = max(dates)
    cutoff = date.today().replace(year=date.today().year - 2)
    if latest < cutoff:
        return CheckResult(
            status="fail",
            evidence=url,
            explanation=f"latest date {latest.isoformat()} is older than 2 years",
        )
    return CheckResult(
        status="pass",
        evidence=url,
        explanation=f"latest date {latest.isoformat()} within 2 years",
    )


_TRACKER_COOKIES: frozenset[str] = frozenset(
    {
        "_ga",
        "_gid",
        "_gat",
        "_fbp",
        "_fbc",
        "_hjid",
        "_hjFirstSeen",
        "_hjAbsoluteSessionInProgress",
        "_ym_uid",
        "_ym_d",
        "_ym_isad",
        "_ym_visorc",
        "yandexuid",
        "yabs-sid",
        "yp",
        "MUID",
        "MR",
        "ANONCHK",
        "intercom-id",
        "intercom-session",
        "hubspotutk",
        "li_at",
        "li_sg_ts",
    }
)
_TRACKER_PREFIXES: tuple[str, ...] = ("_ga_", "_ym_", "_gcl_", "_uetsid", "_uetvid")


def _is_tracker_cookie(name: str) -> bool:
    return name in _TRACKER_COOKIES or any(name.startswith(p) for p in _TRACKER_PREFIXES)


def cookie_set_before_consent(signal: Signal, artifacts: PageArtifacts) -> CheckResult:
    """Tracker-cookie выставлены до взаимодействия с banner'ом → fail.

    Scanner делает «голый» `goto` без кликов, поэтому любые tracker-cookie из
    словаря в `artifacts.cookies` — это установленные до согласия cookie.
    """
    del signal
    trackers = [c.name for c in artifacts.cookies if _is_tracker_cookie(c.name)]
    if trackers:
        return CheckResult(
            status="fail",
            evidence=", ".join(trackers),
            explanation="tracker cookies set without user consent",
        )
    return CheckResult(status="pass", explanation="no tracker cookies set")


_INDEXOF_PATHS: tuple[str, ...] = (
    "/uploads/",
    "/files/",
    "/data/",
    "/backup/",
    "/_old/",
    "/private/",
)


def indexof_check(signal: Signal, artifacts: PageArtifacts) -> CheckResult:
    """Проверка directory listing по нескольким типичным путям."""
    del signal
    for path in _INDEXOF_PATHS:
        url = urljoin(artifacts.url, path)
        try:
            with httpx.Client(timeout=5.0, follow_redirects=True) as client:
                response = client.get(url)
        except httpx.HTTPError:
            continue
        if response.status_code == 200 and "Index of /" in response.text:
            return CheckResult(
                status="fail",
                evidence=url,
                explanation="directory listing enabled",
            )
    return CheckResult(status="pass", explanation="no directory listing exposed")


_CYRILLIC_RE = re.compile(r"[А-Яа-яЁё]")
_LATIN_RE = re.compile(r"[A-Za-z]")
_LATIN_RATIO_MIN_LETTERS = 200


def _element_visible_text(element: Tag) -> str:
    """Видимый текст элемента + `value` у `<input>` (там `get_text()` пуст).

    Для `<input type="submit" value="Купить">` визуальный текст кнопки лежит
    в атрибуте `value` — `get_text()` для `<input>` всегда возвращает пустую
    строку. Для остальных элементов читаем только `get_text()`. Atributs
    `aria-label` / `title` / `placeholder` намеренно не читаем: они служат
    accessibility (screen reader, tooltip, hint), а не основной видимой
    подписи; English-конвенция в этих атрибутах на иконках-кнопках широко
    распространена и не образует нарушения 53-ФЗ.
    """
    text = " ".join(element.get_text(separator=" ", strip=True).split())
    if text:
        return text
    if element.name == "input":
        value = element.get("value")
        if isinstance(value, str) and value.strip():
            return " ".join(value.split())
    return ""


def latin_only_in_selectors(signal: Signal, artifacts: PageArtifacts) -> CheckResult:
    """Элементы по `html_patterns` сигнала содержат латиницу без кириллицы → fail.

    Для каждого селектора собираем найденные элементы. Если хоть один содержит
    непустой видимый текст без кириллической буквы и с латиницей → `fail` с
    evidence (текст элемента, обрезанный до 200 символов). Если ни один такой не
    найден → `pass`.

    «Видимый текст» — `get_text()` или, если он пуст, первый непустой из
    атрибутов `value` / `aria-label` / `title` / `placeholder`. Это покрывает
    `<input type="submit" value="Купить">`, иконки-кнопки и
    `<button aria-label="...">` без визуального текста.

    Семантика: применяется к селекторам заголовков карточек товара / категорий
    (`.product-title`, `h1.product-name`, `.category-title`, …) и к кнопкам и
    элементам навигации (53-ФЗ `button_text_latin_only`). Помогает выявлять
    `iPhone 16`, `Smart TV`, `Buy now`, `Sign Up` без русского эквивалента.
    """

    html_patterns = getattr(signal, "html_patterns", ()) or ()
    if not html_patterns:
        return CheckResult(
            status="inconclusive",
            explanation="no html_patterns to inspect",
            inconclusive_reason="evidence_missing",
        )

    soup = _parse(artifacts.html)
    for pattern in html_patterns:
        for element in _safe_select(soup, pattern):
            text = _element_visible_text(element)
            if not text:
                continue
            if _CYRILLIC_RE.search(text):
                continue
            if not _LATIN_RE.search(text):
                continue
            return CheckResult(
                status="fail",
                evidence=_truncate(text),
                explanation=f"selector {pattern!r} matched element without cyrillic",
            )
    return CheckResult(
        status="pass",
        explanation="every matched element contains cyrillic letters",
    )


def latin_to_cyrillic_ratio(signal: Signal, artifacts: PageArtifacts) -> CheckResult:
    """Доля латиницы в plain-text страницы > threshold → fail (default 0.7).

    Считаем буквы кириллицы и латиницы в plain-text всей страницы (без `<script>`
    / `<style>` / `<noscript>`). Если их сумма < 200 — `inconclusive`
    (`evidence_missing`): мало текста для статистики. Иначе:
    `ratio = latin / (latin + cyrillic)`. Если `ratio > threshold` → `fail`.

    Параметр `threshold` берётся из `signal.model_extra["threshold"]`, default 0.7.
    """

    threshold_raw = (signal.model_extra or {}).get("threshold", 0.7)
    try:
        threshold = float(threshold_raw)
    except (TypeError, ValueError):
        return CheckResult(
            status="inconclusive",
            explanation=f"invalid threshold: {threshold_raw!r}",
        )

    soup = _parse(artifacts.html)
    text = _plain_text(soup)
    cyr_count = len(_CYRILLIC_RE.findall(text))
    lat_count = len(_LATIN_RE.findall(text))
    total = cyr_count + lat_count
    if total < _LATIN_RATIO_MIN_LETTERS:
        return CheckResult(
            status="inconclusive",
            explanation=f"too little text to assess: {total} letters",
            inconclusive_reason="evidence_missing",
        )

    ratio = lat_count / total
    if ratio > threshold:
        return CheckResult(
            status="fail",
            evidence=f"latin/(latin+cyr) = {ratio:.2f}",
            explanation=f"latin-cyrillic ratio {ratio:.2f} > threshold {threshold:.2f}",
        )
    return CheckResult(
        status="pass",
        explanation=f"latin-cyrillic ratio {ratio:.2f} ≤ threshold {threshold:.2f}",
    )


# ---------------------------------------------------------------------------
# Реестр
# ---------------------------------------------------------------------------

_STUBS: tuple[str, ...] = (
    "rkn_registry_lookup",
    "form_action_geo",
    "ip_geolocation",
    "api_endpoint_scan",
    "internal_documents_audit",
    "tls_audit",
    "traffic_threshold",
    "blocklist_status",
    "product_card_audit",
    "notification_mechanism_audit",
    "prohibited_content_dictionary_match",
    "cookies_pan_storage_audit",
    "http_security_audit",
    "parked_domain_detection",
    "offer_acceptance_audit",
    "image_attribution_audit",
    "text_provenance_audit",
    "media_embed_license_audit",
    "trademark_use_audit",
    "font_license_audit",
)

REGISTRY: dict[str, CheckFunction] = {
    **{name: _not_implemented for name in _STUBS},
    "link_near_form_to_privacy": link_near_form_to_privacy,
    "lookup_pages_by_keywords": lookup_pages_by_keywords,
    "http_status_check": http_status_check,
    "text_length_threshold": text_length_threshold,
    "date_in_document": date_in_document,
    "cookie_set_before_consent": cookie_set_before_consent,
    "indexof_check": indexof_check,
    "latin_only_in_selectors": latin_only_in_selectors,
    "latin_to_cyrillic_ratio": latin_to_cyrillic_ratio,
}


# ---------------------------------------------------------------------------
# Главная точка входа: оценить один сигнал
# ---------------------------------------------------------------------------


def evaluate(signal: Signal, artifacts: PageArtifacts) -> CheckResult:
    """Оценить один сигнал на собранных артефактах страницы.

    1. Если у сигнала задан `check`, делегируем в `REGISTRY[name]`. Неизвестное
       имя → `inconclusive` + WARNING лог.
    2. Иначе — собираем суб-результаты по универсальным полям и агрегируем OR.
    3. Если у сигнала есть `combine` (композиция нескольких сигналов) —
       возвращаем `inconclusive` (реализация — итерация 6+).
    """

    extra = signal.model_extra or {}
    if "combine" in extra:
        return CheckResult(
            status="inconclusive",
            explanation="combine-signals not supported in iteration 3",
            inconclusive_reason="check_not_implemented",
        )

    if signal.check:
        fn = REGISTRY.get(signal.check)
        if fn is None:
            logger.warning("unknown check name: %s (signal type=%s)", signal.check, signal.type)
            return CheckResult(
                status="inconclusive",
                explanation=f"unknown check {signal.check!r}",
                inconclusive_reason="check_not_implemented",
            )
        return fn(signal, artifacts)

    # Q4 (ADR-0003): «текстовый триггер + эскейп без html_patterns» — пара
    # required_keywords+required_absent описывает семантическую проверку
    # «если упомянуто X, должно быть Y» (БАД→дисклеймер, кредит→ПСК и т. п.).
    # Детерминированно через OR-агрегацию это даёт ложные fail; реальный сигнал
    # появится в итерации 7 через LLM. До тех пор — context_dependent (скрывается
    # в engine как и check_not_implemented).
    if (
        isinstance(signal, PageSignal)
        and signal.required_keywords
        and signal.required_absent
        and not signal.html_patterns
    ):
        return CheckResult(
            status="inconclusive",
            explanation="text-trigger+escape requires semantic check (deferred to LLM)",
            inconclusive_reason="context_dependent",
        )

    sub_results: list[CheckResult] = []

    # Контекстный prohibited (html_patterns + prohibited_keywords без required_absent)
    # обрабатывается одним sub-result, который покрывает оба поля: иначе обычная
    # OR-агрегация дала бы fail на любом сайте с триггерным селектором независимо
    # от наличия ключа (см. ADR-0003, итерация 6б заход 3).
    contextual_prohibited = (
        isinstance(signal, PageSignal)
        and signal.html_patterns
        and signal.prohibited_keywords
        and not signal.required_absent
    )

    if contextual_prohibited:
        assert isinstance(signal, PageSignal)
        sub_results.append(
            _check_pattern_contains_prohibited(
                signal.html_patterns, signal.prohibited_keywords, artifacts
            )
        )
    elif signal.required_keywords:
        sub_results.append(_check_required_keywords(signal.required_keywords, artifacts))
    elif signal.prohibited_keywords:
        sub_results.append(_check_prohibited_keywords(signal.prohibited_keywords, artifacts))

    if isinstance(signal, PageSignal):
        if not contextual_prohibited:
            if signal.html_patterns and signal.required_absent:
                sub_results.append(
                    _check_pattern_with_escape(
                        signal.html_patterns, signal.required_absent, artifacts
                    )
                )
            elif signal.html_patterns:
                sub_results.append(_check_html_patterns_only(signal.html_patterns, artifacts))
            elif signal.required_absent:
                sub_results.append(_check_required_absent_only(signal.required_absent, artifacts))
        if signal.required_headers:
            sub_results.append(_check_required_headers(signal.required_headers, artifacts))
        if signal.required_protocol:
            sub_results.append(_check_required_protocol(signal.required_protocol, artifacts))

    if not sub_results:
        return CheckResult(
            status="inconclusive",
            explanation="signal has no detectable fields",
        )
    return aggregate_or(sub_results)
