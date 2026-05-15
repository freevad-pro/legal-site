"""Тесты `ScanContext.applies`, `detect_context` и 7 приватных детекторов.

Каждый детектор — на минимальной HTML-фикстуре inline (positive + negative).
Сборная интеграция через `detect_context` проверяется отдельно.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.context import (
    ScanContext,
    _detect_ad_content,
    _detect_child_audience,
    _detect_ecommerce,
    _detect_has_signing,
    _detect_media_18plus,
    _detect_payments,
    _detect_ugc,
    _parse,
    _plain_text,
    detect_context,
)
from app.corpus.models import (
    ContextTag,
    Detection,
    PageSignal,
    Penalty,
    Violation,
)
from app.scanner import NetworkEntry, PageArtifacts


def _artifacts(
    *,
    html: str = "<html><body></body></html>",
    network_log: tuple[NetworkEntry, ...] = (),
) -> PageArtifacts:
    now = datetime.now(UTC)
    return PageArtifacts(
        url="https://example.test/",
        status=200,
        html=html,
        headers={},
        cookies=(),
        network_log=network_log,
        scan_started_at=now,
        scan_finished_at=now,
    )


def _violation(applicability: tuple[ContextTag, ...] = ()) -> Violation:
    return Violation(
        id="v-1",
        article="ст. 1",
        title="t",
        severity="low",
        description="d",
        detection=Detection(
            page_signals=(PageSignal(type="t", description="d", html_patterns=("div",)),)
        ),
        penalties=(
            Penalty(subject="organization", coap_article="ст. 1", amount_min=1000, amount_max=2000),
        ),
        recommendation="fix",
        applicability=applicability,
    )


# ---------------------------------------------------------------------------
# ScanContext.applies
# ---------------------------------------------------------------------------


def test_scan_context_applies_empty_applicability_always_true() -> None:
    ctx = ScanContext(active_tags=frozenset())
    assert ctx.applies(_violation()) is True


def test_scan_context_applies_when_tags_are_subset() -> None:
    ctx = ScanContext(active_tags=frozenset({"payments", "ecommerce"}))
    assert ctx.applies(_violation(("payments",))) is True


def test_scan_context_applies_false_when_tag_missing() -> None:
    ctx = ScanContext(active_tags=frozenset({"ecommerce"}))
    assert ctx.applies(_violation(("payments",))) is False


def test_scan_context_applies_requires_all_tags_and() -> None:
    """AND-семантика: нужны ВСЕ теги из applicability, не хотя бы один."""
    ctx = ScanContext(active_tags=frozenset({"payments"}))
    # has_signing отсутствует → False, даже если payments активен
    assert ctx.applies(_violation(("payments", "has_signing"))) is False


# ---------------------------------------------------------------------------
# _detect_payments
# ---------------------------------------------------------------------------


def test_detect_payments_iframe_yookassa() -> None:
    soup = _parse('<html><body><iframe src="https://yookassa.ru/widget/123"></iframe></body></html>')
    assert _detect_payments(soup, _artifacts()) is True


def test_detect_payments_card_input() -> None:
    soup = _parse('<html><body><input name="cardNumber"></body></html>')
    assert _detect_payments(soup, _artifacts()) is True


def test_detect_payments_checkout_link() -> None:
    soup = _parse('<html><body><a href="/checkout">Оформить</a></body></html>')
    assert _detect_payments(soup, _artifacts()) is True


def test_detect_payments_network_log_with_provider() -> None:
    soup = _parse("<html><body></body></html>")
    network = (
        NetworkEntry(
            url="https://cloudpayments.ru/api/init",
            method="GET",
            resource_type="xhr",
        ),
    )
    assert _detect_payments(soup, _artifacts(network_log=network)) is True


def test_detect_payments_negative_youtube_iframe() -> None:
    soup = _parse(
        '<html><body><iframe src="https://youtube.com/embed/abc"></iframe></body></html>'
    )
    assert _detect_payments(soup, _artifacts()) is False


def test_detect_payments_negative_checkout_rules_link() -> None:
    """Regression: substring `/checkout` сматчил справочную страницу
    `/checkout-rules`. После word-boundary в `_PAYMENT_HREF_RE` —
    только полные сегменты пути активируют payments. См. ревью захода 1."""
    soup = _parse('<html><body><a href="/help/checkout-rules">Правила</a></body></html>')
    assert _detect_payments(soup, _artifacts()) is False


def test_detect_payments_negative_paypal_link() -> None:
    """`/pay` substring'ом сматчил бы `/paypal`-страницы. Word-boundary
    отделяет `pay/`/`payment(s)?` от `paypal` как сегмента."""
    soup = _parse('<html><body><a href="/about/paypal-policy">PayPal</a></body></html>')
    assert _detect_payments(soup, _artifacts()) is False


def test_detect_payments_payment_segment_still_matches() -> None:
    """`/payment` и `/payments` — валидные сегменты, должны активировать."""
    soup = _parse('<html><body><a href="/order/payment">Оплатить</a></body></html>')
    assert _detect_payments(soup, _artifacts()) is True


# ---------------------------------------------------------------------------
# _detect_ecommerce
# ---------------------------------------------------------------------------


def test_detect_ecommerce_cart_and_price_together() -> None:
    """AND-логика: корзина-селектор + цена — интернет-магазин."""
    soup = _parse(
        '<html><body><div class="cart-summary"></div><span>1 990 ₽</span></body></html>'
    )
    assert _detect_ecommerce(soup, _plain_text(soup)) is True


def test_detect_ecommerce_cart_and_buy_together() -> None:
    soup = _parse(
        '<html><body><div class="cart"></div><button>Купить</button></body></html>'
    )
    assert _detect_ecommerce(soup, _plain_text(soup)) is True


def test_detect_ecommerce_buy_and_price_together() -> None:
    """Лендинг продукта без корзины: «купить за 990 ₽» — тоже e-commerce."""
    soup = _parse(
        "<html><body><button>Купить</button><span>990 рублей</span></body></html>"
    )
    assert _detect_ecommerce(soup, _plain_text(soup)) is True


def test_detect_ecommerce_negative_price_only() -> None:
    """Regression: цена в рублях в редакционной статье («playstation 5 за
    7 000 рублей с ozon» в фиде habr.com) одна не активирует тег. См. КТ-2
    итерации 6б, заход 4."""
    soup = _parse("<html><body><p>PlayStation 5 за 7 000 рублей с Ozon</p></body></html>")
    assert _detect_ecommerce(soup, _plain_text(soup)) is False


def test_detect_ecommerce_negative_cart_only() -> None:
    """Только корзинная иконка в шапке без buy/price — недостаточно
    (placeholder без товаров)."""
    soup = _parse('<html><body><a class="cart-icon" href="/cart"></a></body></html>')
    assert _detect_ecommerce(soup, _plain_text(soup)) is False


def test_detect_ecommerce_negative_buy_only() -> None:
    """«Купить курс» без цены — недостаточно, лендинг без коммерческой
    инфраструктуры."""
    soup = _parse("<html><body><button>Купить курс</button></body></html>")
    assert _detect_ecommerce(soup, _plain_text(soup)) is False


def test_detect_ecommerce_negative_simple_blog() -> None:
    soup = _parse("<html><body><p>Статья про космос</p></body></html>")
    assert _detect_ecommerce(soup, _plain_text(soup)) is False


def test_detect_ecommerce_negative_rubrika_not_a_price() -> None:
    """Regression: `\\d[\\d\\s]{0,8}\\s*руб\\.?` без word-boundary справа сматчит
    «5 рубрик», «1 рубикон» и т. п. — false positive `ecommerce` на медиа-сайтах
    с числами рядом со словом-рубрикатором. См. ревью захода 1."""
    soup = _parse("<html><body><p>Прочитайте 5 рубрик нашего журнала</p></body></html>")
    assert _detect_ecommerce(soup, _plain_text(soup)) is False


# ---------------------------------------------------------------------------
# _detect_ad_content
# ---------------------------------------------------------------------------


def test_detect_ad_content_bad_inside_banner_block() -> None:
    """Ключ внутри блока с классом-индикатором рекламы → True."""
    soup = _parse(
        '<html><body><aside class="ad-banner">'
        "наш бад поможет от всех болезней"
        "</aside></body></html>"
    )
    assert _detect_ad_content(soup, _plain_text(soup)) is True


def test_detect_ad_content_credit_inside_promo_block() -> None:
    soup = _parse(
        '<html><body><div class="promo-block">кредит до 5 млн без справок</div></body></html>'
    )
    assert _detect_ad_content(soup, _plain_text(soup)) is True


def test_detect_ad_content_negative_keyword_in_article() -> None:
    """Regression: «как llm помогает разрабатывать лекарства» в редакционной
    статье на habr.com активировал ad_content по plain-text. Контекстный
    детектор требует ключ внутри `[class*=ad|promo|banner|reklama|sponsor i]`."""
    soup = _parse(
        "<html><body><article>как llm помогает разрабатывать лекарства</article></body></html>"
    )
    assert _detect_ad_content(soup, _plain_text(soup)) is False


def test_detect_ad_content_negative_slogan_with_keyword() -> None:
    """Regression: «знания — лучшая инвестиция» (слоган habr) — не реклама
    инвестиций, не должен активировать тег."""
    soup = _parse(
        "<html><body><header><h1>знания — лучшая инвестиция</h1></header></body></html>"
    )
    assert _detect_ad_content(soup, _plain_text(soup)) is False


def test_detect_ad_content_negative_substring_ad_in_unrelated_class() -> None:
    """Regression: `[class*="ad" i]` без word-boundary сматчил `tm-header`
    (через подстроку «ad» в «h-ead-er») на habr.com → ad_content активировался
    по слогану «знания — лучшая инвестиция» в шапке. После word-boundary
    `~="ad"` / `*="ad-"` / `*="-ad"` — `tm-header` уже не контейнер.
    См. КТ-2 итерации 6б, заход 4."""
    soup = _parse(
        '<html><body><header class="tm-header">'
        "знания — лучшая инвестиция"
        "</header></body></html>"
    )
    assert _detect_ad_content(soup, _plain_text(soup)) is False


def test_detect_ad_content_negative_empty_ad_placeholder() -> None:
    """Пустой плейсхолдер рекламного блока без контента → False."""
    soup = _parse('<html><body><aside class="header-ad-slot"></aside></body></html>')
    assert _detect_ad_content(soup, _plain_text(soup)) is False


def test_detect_ad_content_negative_neutral_text() -> None:
    soup = _parse("<html><body><p>обычная новость про погоду</p></body></html>")
    assert _detect_ad_content(soup, _plain_text(soup)) is False


# ---------------------------------------------------------------------------
# _detect_ugc
# ---------------------------------------------------------------------------


def test_detect_ugc_textarea_present() -> None:
    soup = _parse("<html><body><form><textarea></textarea></form></body></html>")
    assert _detect_ugc(soup, _plain_text(soup)) is True


def test_detect_ugc_comment_class() -> None:
    soup = _parse('<html><body><div class="comments-list"></div></body></html>')
    assert _detect_ugc(soup, _plain_text(soup)) is True


def test_detect_ugc_negative_landing() -> None:
    soup = _parse("<html><body><h1>Заголовок</h1></body></html>")
    assert _detect_ugc(soup, _plain_text(soup)) is False


# ---------------------------------------------------------------------------
# _detect_media_18plus
# ---------------------------------------------------------------------------


def test_detect_media_18plus_alcohol_text() -> None:
    soup = _parse("<html><body><p>Купить алкоголь онлайн</p></body></html>")
    assert _detect_media_18plus(soup, _plain_text(soup)) is True


def test_detect_media_18plus_age_gate_selector() -> None:
    soup = _parse('<html><body><div class="age-gate-modal"></div></body></html>')
    assert _detect_media_18plus(soup, _plain_text(soup)) is True


def test_detect_media_18plus_negative_general_news() -> None:
    soup = _parse("<html><body><p>Новости спорта</p></body></html>")
    assert _detect_media_18plus(soup, _plain_text(soup)) is False


# ---------------------------------------------------------------------------
# _detect_child_audience
# ---------------------------------------------------------------------------


def test_detect_child_audience_six_plus_marking() -> None:
    assert _detect_child_audience("статья 6+ для всей семьи") is True


def test_detect_child_audience_twelve_plus_marking() -> None:
    assert _detect_child_audience("маркировка 12+ внизу страницы") is True


def test_detect_child_audience_negative_18_plus_only() -> None:
    assert _detect_child_audience("только 18+") is False


def test_detect_child_audience_negative_no_marking() -> None:
    assert _detect_child_audience("обычный текст без маркировки") is False


# ---------------------------------------------------------------------------
# _detect_has_signing
# ---------------------------------------------------------------------------


def test_detect_has_signing_checkbox_with_agree_name() -> None:
    soup = _parse(
        """
        <html><body>
          <form>
            <input type="email" name="email">
            <input type="checkbox" name="agree">
            <button type="submit">Отправить</button>
          </form>
        </body></html>
        """
    )
    assert _detect_has_signing(soup) is True


def test_detect_has_signing_checkbox_inside_label_with_consent_text() -> None:
    soup = _parse(
        """
        <html><body>
          <form>
            <input type="email" name="email">
            <label>
              <input type="checkbox" name="terms">
              Я согласен с условиями
            </label>
            <button type="submit">Зарегистрироваться</button>
          </form>
        </body></html>
        """
    )
    assert _detect_has_signing(soup) is True


def test_detect_has_signing_negative_plain_contact_form() -> None:
    """Простая форма «свяжитесь с нами» без чекбокса согласия — не активирует
    тег. Иначе has_signing срабатывал бы на любом сайте с формой обратной
    связи (см. open question 5)."""
    soup = _parse(
        """
        <html><body>
          <form>
            <input type="text" name="message">
            <button type="submit">Отправить</button>
          </form>
        </body></html>
        """
    )
    assert _detect_has_signing(soup) is False


def test_detect_has_signing_negative_checkbox_without_submit() -> None:
    soup = _parse(
        '<html><body><form><input type="checkbox" name="agree"></form></body></html>'
    )
    assert _detect_has_signing(soup) is False


# ---------------------------------------------------------------------------
# detect_context — интеграция
# ---------------------------------------------------------------------------


def test_detect_context_empty_html_no_tags() -> None:
    ctx = detect_context(_artifacts(html="<html><body></body></html>"))
    assert ctx.active_tags == frozenset()


def test_detect_context_ecommerce_with_payments() -> None:
    html = """
    <html><body>
      <div class="cart">Корзина</div>
      <iframe src="https://yookassa.ru/widget"></iframe>
      <span>1 990 ₽</span>
    </body></html>
    """
    ctx = detect_context(_artifacts(html=html))
    assert "ecommerce" in ctx.active_tags
    assert "payments" in ctx.active_tags


def test_detect_context_blog_with_comments() -> None:
    html = """
    <html><body>
      <article>Текст статьи</article>
      <div class="comments-list">
        <textarea name="reply"></textarea>
      </div>
    </body></html>
    """
    ctx = detect_context(_artifacts(html=html))
    assert "ugc" in ctx.active_tags
    assert "payments" not in ctx.active_tags
    assert "ecommerce" not in ctx.active_tags


def test_detect_context_returns_frozen_model() -> None:
    ctx = detect_context(_artifacts())
    with pytest.raises(ValueError, match="frozen"):
        ctx.active_tags = frozenset({"payments"})  # type: ignore[misc]
