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
