"""Sanity-тест на реальном корпусе `docs/laws/`.

Проверяет, что весь боевой корпус загружается без ошибок и счётчики соответствуют
ожидаемым (15 законов, 100 нарушений). Если файл не пройдёт валидацию — тест упадёт.
"""

from pathlib import Path

from app.corpus.loader import load_corpus

ROOT = Path(__file__).resolve().parent.parent
REAL_CORPUS = ROOT / "docs" / "laws"


def test_real_corpus_loads_with_expected_counters() -> None:
    bundle = load_corpus(REAL_CORPUS)
    assert len(bundle.laws) == 15
    assert bundle.total_violations == 100


def test_real_corpus_152_fz_present() -> None:
    bundle = load_corpus(REAL_CORPUS)
    law = bundle.find_law("152-fz")
    assert law is not None
    assert law.short_title == "152-ФЗ"
    assert len(law.violations) == 9


def test_real_corpus_152_fz_no_consent_form_exists() -> None:
    bundle = load_corpus(REAL_CORPUS)
    found = bundle.find_violation("152-fz-no-consent-form")
    assert found is not None
    law_id, violation = found
    assert law_id == "152-fz"
    assert violation.severity == "high"


def test_real_corpus_incident_notification_has_single_sub_signal() -> None:
    """После итерации 6б: `152-fz-incident-notification-missed` сохраняет только
    `incident_response_procedure_missing`; sub-signal `dpo_contact_missing`
    удалён как семантически нерелевантный (см. ADR-0003)."""
    bundle = load_corpus(REAL_CORPUS)
    found = bundle.find_violation("152-fz-incident-notification-missed")
    assert found is not None
    _, violation = found
    assert len(violation.detection.page_signals) == 0
    assert len(violation.detection.site_signals) == 1
    assert violation.detection.site_signals[0].type == "incident_response_procedure_missing"


def test_real_corpus_data_breach_no_weak_headers_sub_signal() -> None:
    """После итерации 6б: `152-fz-data-breach` теряет `weak_security_headers`
    (заголовки проверяются в pp-1119-secure-http-headers, см. ADR-0003)."""
    bundle = load_corpus(REAL_CORPUS)
    found = bundle.find_violation("152-fz-data-breach")
    assert found is not None
    _, violation = found
    page_signal_types = {s.type for s in violation.detection.page_signals}
    assert "weak_security_headers" not in page_signal_types
    assert "missing_https" in page_signal_types
