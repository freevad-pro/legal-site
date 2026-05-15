"""Изолированные тесты валидаторов Pydantic-моделей корпуса."""

from datetime import date

import pytest
from pydantic import ValidationError

from app.corpus.models import (
    CorpusBundle,
    Detection,
    Law,
    PageSignal,
    Penalty,
    SiteSignal,
    Source,
    Violation,
)


def _make_violation(vid: str = "test-violation") -> Violation:
    return Violation(
        id=vid,
        article="ст. 1",
        title="Title",
        severity="low",
        description="desc",
        detection=Detection(
            page_signals=(PageSignal(type="t", description="d", html_patterns=("div",)),)
        ),
        penalties=(
            Penalty(
                subject="organization",
                coap_article="ст. 1",
                amount_min=1000,
                amount_max=2000,
            ),
        ),
        recommendation="fix",
    )


def _make_law(law_id: str = "test-law", violations: tuple[Violation, ...] | None = None) -> Law:
    return Law(
        id=law_id,
        title="t",
        short_title="t",
        type="federal_law",
        number="1",
        adopted_date=date(2020, 1, 1),
        in_force_since=date(2020, 2, 1),
        last_amended=date(2024, 6, 1),
        status="in_force",
        category="privacy",
        icon="lock",
        short_description="Тестовый",
        official_sources=(Source(title="s", url="https://example.com/"),),
        applies_to=("all_websites",),
        verified_at=date(2025, 12, 1),
        verified_by="test",
        verified="full",
        violations=violations or (_make_violation(),),
    )


def test_penalty_amount_max_must_be_ge_amount_min() -> None:
    with pytest.raises(ValidationError):
        Penalty(subject="organization", coap_article="ст. 1", amount_min=5000, amount_max=1000)


def test_penalty_allows_no_amounts() -> None:
    p = Penalty(subject="organization", coap_article="ст. 1")
    assert p.amount_min is None and p.amount_max is None


def test_detection_requires_at_least_one_signal() -> None:
    with pytest.raises(ValidationError):
        Detection()


def test_violation_id_must_be_kebab_case() -> None:
    with pytest.raises(ValidationError):
        _make_violation(vid="Bad_ID")


def test_law_applies_to_all_websites_is_exclusive() -> None:
    with pytest.raises(ValidationError):
        Law(
            id="x",
            title="t",
            short_title="t",
            type="federal_law",
            number="1",
            adopted_date=date(2020, 1, 1),
            in_force_since=date(2020, 2, 1),
            last_amended=date(2024, 6, 1),
            status="in_force",
            official_sources=(Source(title="s", url="https://example.com/"),),
            applies_to=("all_websites", "ecommerce"),
            verified_at=date(2025, 12, 1),
            verified_by="test",
            verified="full",
            violations=(_make_violation(),),
        )


def test_law_verified_partial_requires_notes() -> None:
    with pytest.raises(ValidationError):
        Law(
            id="x",
            title="t",
            short_title="t",
            type="federal_law",
            number="1",
            adopted_date=date(2020, 1, 1),
            in_force_since=date(2020, 2, 1),
            last_amended=date(2024, 6, 1),
            status="in_force",
            official_sources=(Source(title="s", url="https://example.com/"),),
            applies_to=("all_websites",),
            verified_at=date(2025, 12, 1),
            verified_by="test",
            verified="partial",
            violations=(_make_violation(),),
        )


def test_law_official_sources_must_have_at_least_one() -> None:
    with pytest.raises(ValidationError):
        Law(
            id="x",
            title="t",
            short_title="t",
            type="federal_law",
            number="1",
            adopted_date=date(2020, 1, 1),
            in_force_since=date(2020, 2, 1),
            last_amended=date(2024, 6, 1),
            status="in_force",
            category="privacy",
            icon="lock",
            short_description="Тестовый",
            official_sources=(),
            applies_to=("all_websites",),
            verified_at=date(2025, 12, 1),
            verified_by="test",
            verified="full",
            violations=(_make_violation(),),
        )


def test_page_signal_allows_extra_fields() -> None:
    sig = PageSignal(type="t", description="d", expected_status=200, min_chars=1500)  # type: ignore[call-arg]
    assert sig.model_extra == {"expected_status": 200, "min_chars": 1500}


def test_page_signal_keywords_are_mutually_exclusive() -> None:
    with pytest.raises(ValidationError) as exc_info:
        PageSignal(
            type="t",
            description="d",
            required_keywords=("обязательно",),
            prohibited_keywords=("запрещено",),
        )
    assert "mutually exclusive" in str(exc_info.value)


def test_site_signal_keywords_are_mutually_exclusive() -> None:
    with pytest.raises(ValidationError) as exc_info:
        SiteSignal(
            type="t",
            description="d",
            required_keywords=("обязательно",),
            prohibited_keywords=("запрещено",),
        )
    assert "mutually exclusive" in str(exc_info.value)


def test_page_signal_only_prohibited_keywords_is_valid() -> None:
    sig = PageSignal(type="t", description="d", prohibited_keywords=("купить табак",))
    assert sig.prohibited_keywords == ("купить табак",)
    assert sig.required_keywords == ()


def test_violation_applicability_accepts_known_tags() -> None:
    sig = PageSignal(type="t", description="d", html_patterns=("div",))
    v = Violation(
        id="v-1",
        article="ст. 1",
        title="t",
        severity="low",
        description="d",
        detection=Detection(page_signals=(sig,)),
        recommendation="fix",
        applicability=("payments", "has_signing"),
    )
    assert v.applicability == ("payments", "has_signing")


def test_violation_applicability_rejects_unknown_tag() -> None:
    sig = PageSignal(type="t", description="d", html_patterns=("div",))
    with pytest.raises(ValidationError):
        Violation(
            id="v-1",
            article="ст. 1",
            title="t",
            severity="low",
            description="d",
            detection=Detection(page_signals=(sig,)),
            recommendation="fix",
            applicability=("not_a_real_tag",),  # type: ignore[arg-type]
        )


def test_violation_applicability_defaults_to_empty_tuple() -> None:
    v = _make_violation()
    assert v.applicability == ()


def test_corpus_bundle_indexes_built() -> None:
    law = _make_law("law-1", (_make_violation("v-1"), _make_violation("v-2")))
    bundle = CorpusBundle(laws=(law,))
    assert bundle.total_violations == 2
    assert bundle.find_law("law-1") is law
    found = bundle.find_violation("v-1")
    assert found is not None
    assert found[0] == "law-1"
    assert bundle.find_violation("missing") is None
    assert len(bundle.all_violations()) == 2


def test_corpus_bundle_detects_duplicate_violation_id() -> None:
    law_a = _make_law("law-a", (_make_violation("dup-v"),))
    law_b = _make_law("law-b", (_make_violation("dup-v"),))
    with pytest.raises(ValidationError) as exc_info:
        CorpusBundle(laws=(law_a, law_b))
    assert "duplicate violation id" in str(exc_info.value)


def test_corpus_bundle_detects_missing_related() -> None:
    law = Law(
        id="law-1",
        title="t",
        short_title="t",
        type="federal_law",
        number="1",
        adopted_date=date(2020, 1, 1),
        in_force_since=date(2020, 2, 1),
        last_amended=date(2024, 6, 1),
        status="in_force",
        category="privacy",
        icon="lock",
        short_description="Тестовый",
        official_sources=(Source(title="s", url="https://example.com/"),),
        applies_to=("all_websites",),
        related=("missing-law",),
        verified_at=date(2025, 12, 1),
        verified_by="test",
        verified="full",
        violations=(_make_violation(),),
    )
    with pytest.raises(ValidationError) as exc_info:
        CorpusBundle(laws=(law,))
    assert "related" in str(exc_info.value)


def test_corpus_bundle_detects_missing_common_reference() -> None:
    law = Law(
        id="law-1",
        title="t",
        short_title="t",
        type="federal_law",
        number="1",
        adopted_date=date(2020, 1, 1),
        in_force_since=date(2020, 2, 1),
        last_amended=date(2024, 6, 1),
        status="in_force",
        category="privacy",
        icon="lock",
        short_description="Тестовый",
        official_sources=(Source(title="s", url="https://example.com/"),),
        applies_to=("all_websites",),
        references_in_common=("missing-common",),
        verified_at=date(2025, 12, 1),
        verified_by="test",
        verified="full",
        violations=(_make_violation(),),
    )
    with pytest.raises(ValidationError) as exc_info:
        CorpusBundle(laws=(law,), common_ids=frozenset())
    assert "references_in_common" in str(exc_info.value)
