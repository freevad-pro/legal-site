"""Контекстный гейтинг сканирования. См. ADR-0003.

`detect_context(artifacts)` смотрит на DOM/cookies/network-лог и определяет
набор активных `ContextTag`'ов (онлайн-оплата, e-commerce, рекламный контент,
UGC, 18+, детская аудитория, формы подписания). Engine использует этот контекст
в `_evaluate_violation`: нарушение с непустым `applicability` оценивается только
если его теги — подмножество активных.

Парсинг HTML и plain-text вычисляются **один раз** в `detect_context`, затем
переиспользуются всеми приватными детекторами — иначе на одной странице
soup создавался бы 7 раз.

Пустой `applicability = ()` (по умолчанию) → `applies()` всегда True. Это
сохраняет совместимость со старым корпусом, в котором поле ещё не размечено
(размечается в этапе 6 итерации 6б).
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup, Tag
from pydantic import BaseModel, ConfigDict
from soupsieve.util import SelectorSyntaxError

from app.corpus.models import ContextTag, Violation
from app.scanner import PageArtifacts


class ScanContext(BaseModel):
    """Активные контекст-теги, выявленные `detect_context` для одного скана."""

    model_config = ConfigDict(frozen=True)

    active_tags: frozenset[ContextTag] = frozenset()

    def applies(self, violation: Violation) -> bool:
        """Применимо ли нарушение в текущем контексте.

        Пустой `applicability` = «применимо всегда».
        Иначе требуется, чтобы все теги из applicability присутствовали в active.
        """
        if not violation.applicability:
            return True
        return set(violation.applicability).issubset(self.active_tags)


# ---------------------------------------------------------------------------
# Хелперы парсинга
# ---------------------------------------------------------------------------


def _parse(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def _plain_text(soup: BeautifulSoup) -> str:
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return " ".join(soup.get_text(separator=" ", strip=True).split()).lower()


def _safe_select(node: BeautifulSoup | Tag, selector: str) -> list[Tag]:
    try:
        return [t for t in node.select(selector) if isinstance(t, Tag)]
    except SelectorSyntaxError:
        return []


def _any_match(text: str, keywords: tuple[str, ...]) -> bool:
    return any(kw in text for kw in keywords)


# ---------------------------------------------------------------------------
# Платежи: iframe платёжного шлюза / поля карт / checkout-ссылки / network
# ---------------------------------------------------------------------------

_PAYMENT_PROVIDER_HOSTS: tuple[str, ...] = (
    "yookassa.ru",
    "yoomoney.ru",
    "cloudpayments.ru",
    "tinkoff.ru/widget",
    "qiwi.com",
    "robokassa.ru",
    "sberbank.ru/sberpay",
    "sbp.nspk.ru",
    "stripe.com",
    "checkout.paypal.com",
)

_PAYMENT_CARD_SELECTORS: tuple[str, ...] = (
    'input[name*="card" i]',
    'input[name*="pan" i]',
    'input[autocomplete="cc-number"]',
    'input[autocomplete="cc-csc"]',
    'input[name*="cvv" i]',
    'input[name*="cvc" i]',
)

# Сегменты пути в `<a href>`, указывающие на онлайн-оплату. Требуем
# границу сегмента — `/checkout-rules` или `/payments-history` НЕ должны
# активировать `payments` (это справочные страницы магазинов, не сама оплата).
_PAYMENT_HREF_RE = re.compile(
    r"(?:^|/)(?:checkout|cart/checkout|pay(?:ment)?s?|order/pay|oplata)(?:/|$|\?|#)",
    re.IGNORECASE,
)


def _detect_payments(
    soup: BeautifulSoup, artifacts: PageArtifacts
) -> bool:
    iframes = _safe_select(soup, "iframe[src]")
    for frame in iframes:
        src = str(frame.get("src", "")).lower()
        if any(host in src for host in _PAYMENT_PROVIDER_HOSTS):
            return True

    if any(_safe_select(soup, sel) for sel in _PAYMENT_CARD_SELECTORS):
        return True

    for anchor in soup.find_all("a", href=True):
        if not isinstance(anchor, Tag):
            continue
        href = str(anchor.get("href", "")).lower()
        if _PAYMENT_HREF_RE.search(href):
            return True

    for entry in artifacts.network_log:
        url_lc = entry.url.lower()
        if any(host in url_lc for host in _PAYMENT_PROVIDER_HOSTS):
            return True

    return False


# ---------------------------------------------------------------------------
# E-commerce: корзина / ценники / кнопка «Купить»
# ---------------------------------------------------------------------------

_ECOMMERCE_CART_SELECTORS: tuple[str, ...] = (
    '[class*="cart" i]',
    '[id*="cart" i]',
    '[class*="basket" i]',
    '[id*="basket" i]',
    '[class*="korzin" i]',
    'a[href*="/cart" i]',
    'a[href*="/korzin" i]',
)

_ECOMMERCE_BUY_KEYWORDS: tuple[str, ...] = (
    "в корзину",
    "купить",
    "оформить заказ",
    "добавить в корзину",
    "buy now",
    "add to cart",
)

# Цена в рублях. Word-boundary слева у `руб` + lookahead «не русская буква»
# справа — без них regex сматчит «5 рубрик», «1 рубикон» и т. п., давая
# ложный `ecommerce`-тег на медиа-сайтах с заголовками-рубрикаторами.
_PRICE_RUB_RE = re.compile(
    r"\d[\d\s]{0,8}\s*(?:₽|\bруб(?:\.|лей|ля|ль)?(?![а-яё])|\brub\b)",
    re.IGNORECASE,
)


def _detect_ecommerce(soup: BeautifulSoup, text: str) -> bool:
    """AND-логика: требуется минимум два независимых признака магазина, причём
    хотя бы один — «магазинный» (корзина-селектор или buy-keyword), не просто
    цена. Иначе медиа-сайты с упоминанием цены в редакционных статьях
    («playstation 5 за 7 000 рублей с ozon» в фиде habr.com) ложно
    активируют тег `ecommerce` → 18 e-commerce-нарушений (pp-2463 / 2300-1 /
    gk-rf-offer) попадают в отчёт. См. ADR-0003 «Калибровка детекторов»."""

    has_cart = any(_safe_select(soup, sel) for sel in _ECOMMERCE_CART_SELECTORS)
    has_buy = _any_match(text, _ECOMMERCE_BUY_KEYWORDS)
    has_price = bool(_PRICE_RUB_RE.search(text))

    if has_cart and (has_buy or has_price):
        return True
    return bool(has_buy and has_price)


# ---------------------------------------------------------------------------
# Рекламный контент регулируемых категорий: БАД / кредиты / страховка /
# инвестиции / VPN / казино / лекарства
# ---------------------------------------------------------------------------

# Подстроки регулируемых товаров — общие для ad_content и media_18plus.
# Вынесены в отдельную константу: оба тега «активны при наличии хотя бы одного
# упоминания», и без выноса любая правка одного списка рисковала рассинхроном.
_REGULATED_GOODS_KEYWORDS: tuple[str, ...] = (
    "табак",
    "сигарет",
    "вейп",
    "алкогол",
    "пиво",
    "вино",
    "казино",
    "букмекер",
    # «ставк» удалён 2026-05-15: слишком частый ложный триггер в IT-/новостном
    # контексте («ставки рефинансирования», «зарплатные ставки», «ставки в
    # технологиях»). Сайты казино/букмекеров и так активируют тег через «казино»
    # / «букмекер», поэтому потеря «ставк» не ослабляет реальную детекцию.
)

_AD_CONTENT_KEYWORDS: tuple[str, ...] = _REGULATED_GOODS_KEYWORDS + (
    "бад",
    "биологически активная",
    "лекарств",
    "кредит",
    "займ",
    "микрозайм",
    "ипотек",
    "страхов",
    "инвестиц",
    "брокер",
    "форекс",
    "vpn",
)

# Контейнеры, типичные для рекламных блоков (баннеры, спонсорские карточки,
# нативная реклама). Подстроку "ad" нельзя использовать напрямую — `[class*="ad"]`
# сматчит `tm-header` через `h-ead-er`, `dropdown`, `gradient`, `download` и т. д.
# Поэтому для «ad» требуем word-boundary: либо отдельный класс `ad`/`ads`,
# либо префикс/суффикс с разделителем `ad-` / `-ad` / `ad_` / `_ad`. Для
# `reklama` / `sponsor` / `promo` / `banner` подстрока безопасна — они длиннее
# и не встраиваются в распространённые «декоративные» классы.
_AD_CONTAINER_SELECTORS: tuple[str, ...] = (
    # Класс целиком — "ad" / "ads"
    '[class~="ad" i]',
    '[class~="ads" i]',
    # Префикс / суффикс с разделителем
    '[class*="ad-" i]',
    '[class*="-ad" i]',
    '[class*="ad_" i]',
    '[class*="_ad" i]',
    # Корни длиннее 3 символов — подстрока безопасна
    '[class*="reklama" i]',
    '[class*="sponsor" i]',
    '[class*="promo" i]',
    '[class*="banner" i]',
    # id с теми же оговорками
    '[id~="ad" i]',
    '[id~="ads" i]',
    '[id*="ad-" i]',
    '[id*="-ad" i]',
    '[id*="reklama" i]',
    '[id*="sponsor" i]',
    '[id*="banner" i]',
    '[id*="promo" i]',
)


def _detect_ad_content(soup: BeautifulSoup, text: str) -> bool:
    """Тег активен, только если регулируемый ключ встречается ВНУТРИ
    предполагаемого рекламного блока. Без этой контекстной привязки любое
    упоминание «лекарств» в IT-новости или «инвестиция» в слогане сайта
    («знания — лучшая инвестиция» на habr) даёт false positive.
    Известное ограничение «контент ≠ реклама» по детерминированной логике
    закрывается LLM в итерации 7, но контекстная фильтрация по блокам уже
    отсекает значительную часть шума."""

    del text  # signature симметрична другим детекторам, plain-text не нужен
    for sel in _AD_CONTAINER_SELECTORS:
        for element in _safe_select(soup, sel):
            block_text = " ".join(element.get_text(separator=" ", strip=True).split()).lower()
            if not block_text:
                continue
            if _any_match(block_text, _AD_CONTENT_KEYWORDS):
                return True
    return False


# ---------------------------------------------------------------------------
# UGC: формы комментариев / форумы
# ---------------------------------------------------------------------------

_UGC_SELECTORS: tuple[str, ...] = (
    '[class*="comment" i]',
    '[id*="comment" i]',
    '[class*="forum" i]',
    '[id*="forum" i]',
    '[class*="reply" i]',
    "textarea",
)

_UGC_KEYWORDS: tuple[str, ...] = (
    "комментар",
    "обсужден",
    "ответить",
    "написать сообщен",
    "оставить отзыв",
    "форум",
)


def _detect_ugc(soup: BeautifulSoup, text: str) -> bool:
    if any(_safe_select(soup, sel) for sel in _UGC_SELECTORS):
        return True
    return _any_match(text, _UGC_KEYWORDS)


# ---------------------------------------------------------------------------
# 18+: алкоголь / табак / казино / ставки / age-gate
# ---------------------------------------------------------------------------

_MEDIA_18PLUS_KEYWORDS: tuple[str, ...] = _REGULATED_GOODS_KEYWORDS + (
    "эротик",
    "18+",
)


def _detect_media_18plus(soup: BeautifulSoup, text: str) -> bool:
    if _any_match(text, _MEDIA_18PLUS_KEYWORDS):
        return True
    return bool(
        _safe_select(soup, '[class*="age-gate" i]')
        or _safe_select(soup, '[id*="age-gate" i]')
    )


# ---------------------------------------------------------------------------
# Детская аудитория: маркировка 0+ / 6+ / 12+
# ---------------------------------------------------------------------------

_CHILD_AGE_MARKING_RE = re.compile(r"(?<!\d)(?:0|6|12)\+(?!\d)")


def _detect_child_audience(text: str) -> bool:
    return bool(_CHILD_AGE_MARKING_RE.search(text))


# ---------------------------------------------------------------------------
# Подписание / акцепт оферты: middle-ground детектор (см. open question 5)
# Чекбокс с label/name/id/value на согласие + наличие submit в той же форме.
# ---------------------------------------------------------------------------

_CONSENT_HINTS: tuple[str, ...] = (
    "agree",
    "terms",
    "consent",
    "oferta",
    "accept",
    "согла",
    "подтвержд",
    "принима",
)


def _checkbox_signals_consent(checkbox: Tag) -> bool:
    for attr in ("name", "id", "value"):
        val = checkbox.get(attr)
        if isinstance(val, str) and any(hint in val.lower() for hint in _CONSENT_HINTS):
            return True

    # Связанный <label for="cb_id"> внутри той же формы.
    cb_id = checkbox.get("id")
    parent_forms = checkbox.find_parents("form")
    if isinstance(cb_id, str) and cb_id and parent_forms:
        form = parent_forms[0]
        for label in _safe_select(form, f'label[for="{cb_id}"]'):
            label_text = label.get_text(separator=" ", strip=True).lower()
            if any(hint in label_text for hint in _CONSENT_HINTS):
                return True

    # Inline-label: checkbox внутри <label>...</label>.
    parent_label = checkbox.find_parent("label")
    if isinstance(parent_label, Tag):
        text = parent_label.get_text(separator=" ", strip=True).lower()
        if any(hint in text for hint in _CONSENT_HINTS):
            return True

    return False


def _detect_has_signing(soup: BeautifulSoup) -> bool:
    for form in soup.find_all("form"):
        if not isinstance(form, Tag):
            continue
        submit = (
            _safe_select(form, 'button[type="submit"]')
            or _safe_select(form, 'input[type="submit"]')
            or _safe_select(form, "button:not([type])")
        )
        if not submit:
            continue
        for cb in _safe_select(form, 'input[type="checkbox"]'):
            if _checkbox_signals_consent(cb):
                return True
    return False


# ---------------------------------------------------------------------------
# Точка входа
# ---------------------------------------------------------------------------


def detect_context(artifacts: PageArtifacts) -> ScanContext:
    """Детерминированно определить активные `ContextTag`'и для артефактов скана.

    Парсит HTML один раз, plain-text один раз — переиспользует во всех 7
    детекторах. Возвращает иммутабельный `ScanContext`.
    """

    soup = _parse(artifacts.html)
    text = _plain_text(soup)

    active: set[ContextTag] = set()
    if _detect_payments(soup, artifacts):
        active.add("payments")
    if _detect_ecommerce(soup, text):
        active.add("ecommerce")
    if _detect_ad_content(soup, text):
        active.add("ad_content")
    if _detect_ugc(soup, text):
        active.add("ugc")
    if _detect_media_18plus(soup, text):
        active.add("media_18plus")
    if _detect_child_audience(text):
        active.add("child_audience")
    if _detect_has_signing(soup):
        active.add("has_signing")

    return ScanContext(active_tags=frozenset(active))
