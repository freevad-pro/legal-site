"""Тесты реестра check-функций и универсальных обработчиков.

Реальные HTTP-запросы не делаются — фикстуры собираются вручную, либо
именные check-функции, опирающиеся на httpx, мокаются через monkeypatch
в соответствующих тестах этапа 3.
"""

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from app.checks import (
    REGISTRY,
    CheckResult,
    _check_pattern_with_escape,
    _find_policy_url,
    _not_implemented,
    aggregate_or,
    cookie_set_before_consent,
    date_in_document,
    evaluate,
    http_status_check,
    indexof_check,
    link_near_form_to_privacy,
    lookup_pages_by_keywords,
    text_length_threshold,
)
from app.corpus.models import PageSignal, SiteSignal
from app.scanner import Cookie, NetworkEntry, PageArtifacts

HTML_FIXTURES = Path(__file__).parent / "fixtures" / "html"


def _artifacts(
    *,
    url: str = "https://example.test/",
    html: str = "<html><body></body></html>",
    status: int = 200,
    headers: dict[str, str] | None = None,
    cookies: tuple[Cookie, ...] = (),
    network_log: tuple[NetworkEntry, ...] = (),
) -> PageArtifacts:
    now = datetime.now(UTC)
    return PageArtifacts(
        url=url,
        status=status,
        html=html,
        headers=headers or {},
        cookies=cookies,
        network_log=network_log,
        scan_started_at=now,
        scan_finished_at=now,
    )


def _load_fixture(name: str) -> str:
    return (HTML_FIXTURES / name).read_text(encoding="utf-8")


# ----- _check_html_patterns / required_absent ----- #


def test_evaluate_html_patterns_matches_pd_form() -> None:
    signal = PageSignal(
        type="form_with_email",
        description="Форма с email",
        html_patterns=('input[type="email"]',),
    )
    artifacts = _artifacts(html=_load_fixture("site-with-pd-form-no-checkbox.html"))
    result = evaluate(signal, artifacts)
    assert result.status == "fail"
    assert "input" in (result.evidence or "")


def test_evaluate_html_patterns_no_match_returns_pass() -> None:
    signal = PageSignal(
        type="form_with_email",
        description="Форма с email",
        html_patterns=('input[type="tel"]',),
    )
    artifacts = _artifacts(html="<html><body><p>no forms</p></body></html>")
    assert evaluate(signal, artifacts).status == "pass"


def test_evaluate_required_absent_document_scope_fail() -> None:
    signal = PageSignal(
        type="form_without_consent_checkbox",
        description="Форма с PD-полем без чекбокса согласия",
        html_patterns=('input[type="email"]',),
        required_absent=('input[type="checkbox"][name*="consent" i]',),
    )
    artifacts = _artifacts(html=_load_fixture("site-with-pd-form-no-checkbox.html"))
    result = evaluate(signal, artifacts)
    assert result.status == "fail"


def test_evaluate_required_absent_document_scope_pass_when_checkbox_present() -> None:
    html = """
        <html><body>
          <form><input type="email" name="email">
            <input type="checkbox" name="consent">
          </form>
        </body></html>
    """
    signal = PageSignal(
        type="form_without_consent_checkbox",
        description="Форма с PD-полем без чекбокса согласия",
        html_patterns=('input[type="email"]',),
        required_absent=('input[type="checkbox"][name*="consent" i]',),
    )
    assert evaluate(signal, _artifacts(html=html)).status == "pass"


def test_evaluate_required_absent_container_scope_fail() -> None:
    """`html_patterns=['footer']` + `required_absent=['a[href*="privacy" i]']`
    срабатывает, если в `<footer>` нет ссылки на политику."""
    signal = PageSignal(
        type="missing_policy_link_in_footer",
        description="В подвале нет ссылки на политику",
        html_patterns=("footer",),
        required_absent=('a[href*="privacy" i]', 'a[href*="policy" i]'),
    )
    artifacts = _artifacts(html=_load_fixture("site-without-policy-link.html"))
    assert evaluate(signal, artifacts).status == "fail"


def test_evaluate_required_absent_container_scope_pass() -> None:
    signal = PageSignal(
        type="missing_policy_link_in_footer",
        description="В подвале нет ссылки на политику",
        html_patterns=("footer",),
        required_absent=('a[href*="privacy" i]',),
    )
    artifacts = _artifacts(html=_load_fixture("site-with-policy-link.html"))
    assert evaluate(signal, artifacts).status == "pass"


def test_evaluate_required_absent_container_scope_inconclusive_when_no_container() -> None:
    signal = PageSignal(
        type="missing_policy_link_in_footer",
        description="В подвале нет ссылки на политику",
        html_patterns=("footer",),
        required_absent=('a[href*="privacy" i]',),
    )
    artifacts = _artifacts(html="<html><body><p>no footer</p></body></html>")
    assert evaluate(signal, artifacts).status == "inconclusive"


# ----- required_keywords / required_headers / required_protocol ----- #


def test_evaluate_required_keywords_missing() -> None:
    signal = PageSignal(
        type="policy_missing_required_sections",
        description="Нет ключевых разделов",
        required_keywords=("согласие", "обработка"),
    )
    artifacts = _artifacts(html="<html><body><p>Только согласие тут.</p></body></html>")
    result = evaluate(signal, artifacts)
    assert result.status == "fail"
    assert "обработка" in (result.explanation or "")


def test_evaluate_required_keywords_all_present() -> None:
    signal = PageSignal(
        type="policy_keywords_check",
        description="Ключевые слова",
        required_keywords=("Согласие", "обработка"),
    )
    artifacts = _artifacts(
        html="<html><body>Тут и Согласие, и Обработка персональных данных.</body></html>"
    )
    assert evaluate(signal, artifacts).status == "pass"


def test_evaluate_required_keywords_skips_script_and_style() -> None:
    signal = PageSignal(
        type="kw",
        description="kw",
        required_keywords=("hidden",),
    )
    html = "<html><body><script>hidden</script><p>visible</p></body></html>"
    assert evaluate(signal, _artifacts(html=html)).status == "fail"


def test_evaluate_required_headers_missing_case_insensitive() -> None:
    signal = PageSignal(
        type="weak_headers",
        description="Нет security headers",
        required_headers=("Strict-Transport-Security",),
    )
    artifacts = _artifacts(headers={"content-type": "text/html"})
    assert evaluate(signal, artifacts).status == "fail"


def test_evaluate_required_headers_present_case_insensitive() -> None:
    signal = PageSignal(
        type="weak_headers",
        description="security headers",
        required_headers=("Strict-Transport-Security",),
    )
    artifacts = _artifacts(headers={"strict-transport-security": "max-age=31536000"})
    assert evaluate(signal, artifacts).status == "pass"


def test_evaluate_required_protocol_fail_on_http() -> None:
    signal = PageSignal(
        type="missing_https",
        description="Сбор ПДн по HTTP",
        required_protocol="https",
    )
    artifacts = _artifacts(url="http://example.test/", headers={})
    assert evaluate(signal, artifacts).status == "fail"


def test_evaluate_required_protocol_pass_on_https() -> None:
    signal = PageSignal(
        type="missing_https",
        description="Сбор ПДн по HTTPS",
        required_protocol="https",
    )
    artifacts = _artifacts(url="https://example.test/", headers={})
    assert evaluate(signal, artifacts).status == "pass"


# ----- агрегация и обработка типов сигналов ----- #


def test_evaluate_signal_without_detectors_returns_inconclusive() -> None:
    signal = PageSignal(type="empty", description="no fields")
    assert evaluate(signal, _artifacts()).status == "inconclusive"


def test_pattern_with_escape_trigger_no_escape_fails() -> None:
    """Триггер html_patterns сработал, эскейпа required_absent нет → fail."""
    html = """
        <html><body>
          <form><input type="email"></form>
        </body></html>
    """
    result = _check_pattern_with_escape(
        html_patterns=('input[type="email"]',),
        required_absent=('input[type="checkbox"][name*="consent" i]',),
        artifacts=_artifacts(html=html),
    )
    assert result.status == "fail"


def test_pattern_with_escape_trigger_with_escape_passes() -> None:
    """Триггер сработал, эскейп тоже → pass (рядом нашёлся нужный элемент)."""
    html = """
        <html><body>
          <form>
            <input type="email">
            <input type="checkbox" name="consent">
          </form>
        </body></html>
    """
    result = _check_pattern_with_escape(
        html_patterns=('input[type="email"]',),
        required_absent=('input[type="checkbox"][name*="consent" i]',),
        artifacts=_artifacts(html=html),
    )
    assert result.status == "pass"


def test_pattern_with_escape_no_trigger_passes() -> None:
    """Триггер html_patterns не сработал → pass (повода для проверки нет)."""
    result = _check_pattern_with_escape(
        html_patterns=('input[type="email"]',),
        required_absent=('input[type="checkbox"][name*="consent" i]',),
        artifacts=_artifacts(html="<html><body><p>no forms</p></body></html>"),
    )
    assert result.status == "pass"


def test_aggregate_or_priority() -> None:
    assert (
        aggregate_or(
            [
                CheckResult(status="pass"),
                CheckResult(status="inconclusive"),
                CheckResult(status="fail", explanation="bad"),
            ]
        ).status
        == "fail"
    )

    assert (
        aggregate_or(
            [
                CheckResult(status="pass"),
                CheckResult(status="inconclusive", explanation="why"),
            ]
        ).status
        == "inconclusive"
    )

    assert aggregate_or([CheckResult(status="pass"), CheckResult(status="pass")]).status == "pass"


# ----- combine, неизвестный check, реестр ----- #


def test_combine_signal_returns_inconclusive() -> None:
    signal = SiteSignal(
        type="combo",
        description="combo signal",
        combine=["a", "b"],  # type: ignore[call-arg]
    )
    result = evaluate(signal, _artifacts())
    assert result.status == "inconclusive"
    assert "combine" in (result.explanation or "")


def test_unknown_check_returns_inconclusive() -> None:
    signal = SiteSignal(
        type="x",
        description="x",
        check="never_registered_check",
    )
    result = evaluate(signal, _artifacts())
    assert result.status == "inconclusive"
    assert "unknown check" in (result.explanation or "")


def test_registry_contains_expected_names() -> None:
    expected = {
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
        "link_near_form_to_privacy",
        "lookup_pages_by_keywords",
        "http_status_check",
        "text_length_threshold",
        "date_in_document",
        "cookie_set_before_consent",
        "indexof_check",
    }
    assert expected.issubset(REGISTRY.keys())


def test_stub_returns_inconclusive() -> None:
    signal = SiteSignal(type="x", description="x", check="rkn_registry_lookup")
    result = _not_implemented(signal, _artifacts())
    assert result.status == "inconclusive"
    assert "rkn_registry_lookup" in (result.explanation or "")


# ----- _find_policy_url ----- #


def test_find_policy_url_returns_absolute_url() -> None:
    artifacts = _artifacts(
        url="https://example.test/index",
        html=_load_fixture("site-with-policy-link.html"),
    )
    assert _find_policy_url(artifacts) == "https://example.test/privacy"


def test_find_policy_url_returns_none_when_no_link() -> None:
    artifacts = _artifacts(html=_load_fixture("site-without-policy-link.html"))
    assert _find_policy_url(artifacts) is None


def test_find_policy_url_handles_percent_encoded_href_without_visible_text() -> None:
    """Иконка-ссылка с русским href в percent-encoded виде должна находиться."""
    html = (
        '<html><body><a href="/%D0%BF%D0%BE%D0%BB%D0%B8%D1%82%D0%B8%D0%BA%D0%B0">'
        '<img src="icon.png"></a></body></html>'
    )
    artifacts = _artifacts(url="https://example.test/", html=html)
    result = _find_policy_url(artifacts)
    assert result is not None
    assert "%D0%BF" in result or "политика" in result


# ---------------------------------------------------------------------------
# Именные check-функции (этап 3)
# ---------------------------------------------------------------------------


class _FakeHttpResponse:
    def __init__(
        self,
        status_code: int = 200,
        text: str = "",
        *,
        content: bytes | None = None,
        encoding: str | None = "utf-8",
    ) -> None:
        self.status_code = status_code
        self.text = text
        self.content = content if content is not None else text.encode("utf-8")
        self.encoding = encoding


class _FakeHttpxClient:
    """Простой подменщик httpx.Client; принимает таблицу url→response."""

    instances: list["_FakeHttpxClient"] = []

    def __init__(self, *_: object, **__: object) -> None:
        self.calls: list[str] = []
        type(self).instances.append(self)

    def __enter__(self) -> "_FakeHttpxClient":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def get(self, url: str) -> _FakeHttpResponse:
        self.calls.append(url)
        return _FAKE_HTTP_RESPONSES.get(url, _FakeHttpResponse(status_code=404, text=""))


_FAKE_HTTP_RESPONSES: dict[str, _FakeHttpResponse] = {}


@pytest.fixture(autouse=False)
def fake_httpx(monkeypatch: pytest.MonkeyPatch) -> type[_FakeHttpxClient]:
    import app.checks as checks_mod

    _FAKE_HTTP_RESPONSES.clear()
    _FakeHttpxClient.instances = []
    monkeypatch.setattr(checks_mod.httpx, "Client", _FakeHttpxClient)
    return _FakeHttpxClient


# ----- link_near_form_to_privacy ----- #


def test_link_near_form_to_privacy_passes_when_link_inside_form() -> None:
    html = """
    <html><body>
      <form>
        <input type="email">
        <a href="/privacy">Политика конфиденциальности</a>
      </form>
    </body></html>
    """
    signal = SiteSignal(
        type="consent_link_missing",
        description="x",
        check="link_near_form_to_privacy",
        keywords=["согласие на обработку"],  # type: ignore[call-arg]
    )
    assert link_near_form_to_privacy(signal, _artifacts(html=html)).status == "pass"


def test_link_near_form_to_privacy_fails_when_no_link_nearby() -> None:
    html = """
    <html><body>
      <main>
        <form><input type="email"></form>
      </main>
      <footer>Совсем другая ссылка</footer>
    </body></html>
    """
    signal = SiteSignal(type="x", description="x", check="link_near_form_to_privacy")
    assert link_near_form_to_privacy(signal, _artifacts(html=html)).status == "fail"


def test_link_near_form_to_privacy_inconclusive_if_no_pd_form() -> None:
    html = "<html><body><form><input type='hidden'></form></body></html>"
    signal = SiteSignal(type="x", description="x", check="link_near_form_to_privacy")
    assert link_near_form_to_privacy(signal, _artifacts(html=html)).status == "inconclusive"


# ----- lookup_pages_by_keywords ----- #


def test_lookup_pages_by_keywords_pass_returns_absolute_url() -> None:
    signal = SiteSignal(
        type="privacy_policy_page_missing",
        description="x",
        check="lookup_pages_by_keywords",
        keywords=["политика конфиденциальности"],  # type: ignore[call-arg]
    )
    artifacts = _artifacts(
        url="https://example.test/",
        html=_load_fixture("site-with-policy-link.html"),
    )
    result = lookup_pages_by_keywords(signal, artifacts)
    assert result.status == "pass"
    assert result.evidence == "https://example.test/privacy"


def test_lookup_pages_by_keywords_fail_when_no_match() -> None:
    signal = SiteSignal(
        type="x",
        description="x",
        check="lookup_pages_by_keywords",
        keywords=["zzz-unmatched"],  # type: ignore[call-arg]
    )
    artifacts = _artifacts(html=_load_fixture("site-with-policy-link.html"))
    assert lookup_pages_by_keywords(signal, artifacts).status == "fail"


# ----- http_status_check ----- #


def test_http_status_check_pass(fake_httpx: type[_FakeHttpxClient]) -> None:
    _FAKE_HTTP_RESPONSES["https://example.test/privacy"] = _FakeHttpResponse(200, "ok")
    signal = PageSignal(
        type="policy_url_returns_404",
        description="x",
        check="http_status_check",
        expected_status=200,  # type: ignore[call-arg]
    )
    artifacts = _artifacts(
        url="https://example.test/", html=_load_fixture("site-with-policy-link.html")
    )
    result = http_status_check(signal, artifacts)
    assert result.status == "pass"


def test_http_status_check_fail_on_404(fake_httpx: type[_FakeHttpxClient]) -> None:
    _FAKE_HTTP_RESPONSES["https://example.test/privacy"] = _FakeHttpResponse(404, "")
    signal = PageSignal(
        type="policy_url_returns_404",
        description="x",
        check="http_status_check",
        expected_status=200,  # type: ignore[call-arg]
    )
    artifacts = _artifacts(
        url="https://example.test/", html=_load_fixture("site-with-policy-link.html")
    )
    result = http_status_check(signal, artifacts)
    assert result.status == "fail"
    assert "404" in (result.explanation or "")


def test_http_status_check_inconclusive_when_no_policy_url() -> None:
    signal = PageSignal(type="x", description="x", check="http_status_check")
    artifacts = _artifacts(html=_load_fixture("site-without-policy-link.html"))
    assert http_status_check(signal, artifacts).status == "inconclusive"


# ----- text_length_threshold ----- #


def test_text_length_threshold_pass(fake_httpx: type[_FakeHttpxClient]) -> None:
    long_text = "a" * 2000
    _FAKE_HTTP_RESPONSES["https://example.test/privacy"] = _FakeHttpResponse(
        200, f"<html><body>{long_text}</body></html>"
    )
    signal = PageSignal(
        type="policy_too_short",
        description="x",
        check="text_length_threshold",
        min_chars=1500,  # type: ignore[call-arg]
    )
    artifacts = _artifacts(
        url="https://example.test/", html=_load_fixture("site-with-policy-link.html")
    )
    assert text_length_threshold(signal, artifacts).status == "pass"


def test_text_length_threshold_fail(fake_httpx: type[_FakeHttpxClient]) -> None:
    _FAKE_HTTP_RESPONSES["https://example.test/privacy"] = _FakeHttpResponse(
        200, "<html><body>short</body></html>"
    )
    signal = PageSignal(
        type="x",
        description="x",
        check="text_length_threshold",
        min_chars=1500,  # type: ignore[call-arg]
    )
    artifacts = _artifacts(
        url="https://example.test/", html=_load_fixture("site-with-policy-link.html")
    )
    assert text_length_threshold(signal, artifacts).status == "fail"


# ----- date_in_document ----- #


def test_date_in_document_fail_when_no_date(fake_httpx: type[_FakeHttpxClient]) -> None:
    _FAKE_HTTP_RESPONSES["https://example.test/privacy"] = _FakeHttpResponse(
        200, "<html><body>Без даты</body></html>"
    )
    signal = SiteSignal(type="policy_outdated", description="x", check="date_in_document")
    artifacts = _artifacts(
        url="https://example.test/", html=_load_fixture("site-with-policy-link.html")
    )
    result = date_in_document(signal, artifacts)
    assert result.status == "fail"
    assert "no document date" in (result.explanation or "")


def test_date_in_document_fail_when_date_too_old(fake_httpx: type[_FakeHttpxClient]) -> None:
    _FAKE_HTTP_RESPONSES["https://example.test/privacy"] = _FakeHttpResponse(
        200, "<html><body>Последняя редакция 01.01.2010</body></html>"
    )
    signal = SiteSignal(type="x", description="x", check="date_in_document")
    artifacts = _artifacts(
        url="https://example.test/", html=_load_fixture("site-with-policy-link.html")
    )
    assert date_in_document(signal, artifacts).status == "fail"


def test_date_in_document_pass_with_iso_date(fake_httpx: type[_FakeHttpxClient]) -> None:
    today_year = date.today().year
    _FAKE_HTTP_RESPONSES["https://example.test/privacy"] = _FakeHttpResponse(
        200, f"<html><body>Redacted {today_year}-03-15</body></html>"
    )
    signal = SiteSignal(type="x", description="x", check="date_in_document")
    artifacts = _artifacts(
        url="https://example.test/", html=_load_fixture("site-with-policy-link.html")
    )
    assert date_in_document(signal, artifacts).status == "pass"


def test_date_in_document_pass_with_russian_date(fake_httpx: type[_FakeHttpxClient]) -> None:
    today_year = date.today().year
    _FAKE_HTTP_RESPONSES["https://example.test/privacy"] = _FakeHttpResponse(
        200, f"<html><body>Последняя редакция 5 марта {today_year}</body></html>"
    )
    signal = SiteSignal(type="x", description="x", check="date_in_document")
    artifacts = _artifacts(
        url="https://example.test/", html=_load_fixture("site-with-policy-link.html")
    )
    assert date_in_document(signal, artifacts).status == "pass"


# ----- cookie_set_before_consent ----- #


def test_cookie_set_before_consent_fail_on_tracker() -> None:
    cookies = (
        Cookie(name="_ga", value="GA1", domain="example.test"),
        Cookie(name="session", value="abc", domain="example.test"),
    )
    signal = PageSignal(type="cookies_set_without_banner", description="x")
    artifacts = _artifacts(cookies=cookies)
    result = cookie_set_before_consent(signal, artifacts)
    assert result.status == "fail"
    assert "_ga" in (result.evidence or "")


def test_cookie_set_before_consent_fail_on_prefix() -> None:
    cookies = (Cookie(name="_ga_ABC123", value="x", domain="example.test"),)
    signal = SiteSignal(type="x", description="x", check="cookie_set_before_consent")
    assert cookie_set_before_consent(signal, _artifacts(cookies=cookies)).status == "fail"


def test_cookie_set_before_consent_pass_with_only_technical() -> None:
    cookies = (Cookie(name="session", value="x", domain="example.test", http_only=True),)
    signal = SiteSignal(type="x", description="x", check="cookie_set_before_consent")
    assert cookie_set_before_consent(signal, _artifacts(cookies=cookies)).status == "pass"


# ----- indexof_check ----- #


def test_indexof_check_fail_on_directory_listing(fake_httpx: type[_FakeHttpxClient]) -> None:
    _FAKE_HTTP_RESPONSES["https://example.test/uploads/"] = _FakeHttpResponse(
        200, "<html><h1>Index of /uploads</h1></html>"
    )
    signal = PageSignal(type="directory_listing_enabled", description="x", check="indexof_check")
    artifacts = _artifacts(url="https://example.test/")
    result = indexof_check(signal, artifacts)
    assert result.status == "fail"
    assert "uploads" in (result.evidence or "")


def test_indexof_check_pass_when_all_404(fake_httpx: type[_FakeHttpxClient]) -> None:
    # все ответы по дефолту 404 (см. _FakeHttpxClient.get)
    signal = PageSignal(type="x", description="x", check="indexof_check")
    artifacts = _artifacts(url="https://example.test/")
    assert indexof_check(signal, artifacts).status == "pass"


# ----- кириллица и кодировки в _fetch_text ----- #


def test_text_length_threshold_decodes_cp1251_without_http_charset(
    fake_httpx: type[_FakeHttpxClient],
) -> None:
    """Старый русский сайт: HTML декларирует windows-1251 в meta, но в HTTP
    Content-Type charset отсутствует. bs4 должен корректно декодировать."""
    russian_long = "Политика обработки персональных данных. " * 80  # > 1500 символов
    html_str = (
        '<html><head><meta http-equiv="Content-Type" '
        'content="text/html; charset=windows-1251"></head>'
        f"<body>{russian_long}</body></html>"
    )
    _FAKE_HTTP_RESPONSES["https://example.test/privacy"] = _FakeHttpResponse(
        200,
        text="",  # ловушка: response.text не используем — используем content
        content=html_str.encode("windows-1251"),
        encoding=None,
    )
    signal = PageSignal(
        type="policy_too_short",
        description="x",
        check="text_length_threshold",
        min_chars=1500,  # type: ignore[call-arg]
    )
    artifacts = _artifacts(
        url="https://example.test/", html=_load_fixture("site-with-policy-link.html")
    )
    assert text_length_threshold(signal, artifacts).status == "pass"
