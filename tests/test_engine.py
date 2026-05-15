"""Тесты engine на fake scanner через monkeypatch."""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from app import engine, scanner
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
from app.engine import Finding
from app.events import ScanEvent
from app.scanner import PageArtifacts, ScanError


def _violation(
    vid: str,
    *,
    page_signals: tuple[PageSignal, ...] = (),
    site_signals: tuple[SiteSignal, ...] = (),
    severity: str = "low",
) -> Violation:
    return Violation(
        id=vid,
        article="ст. 1",
        title=f"Тест {vid}",
        severity=severity,  # type: ignore[arg-type]
        description="x",
        detection=Detection(page_signals=page_signals, site_signals=site_signals),
        penalties=(
            Penalty(subject="organization", coap_article="ст. 1", amount_min=1000, amount_max=2000),
        ),
        recommendation="fix",
    )


def _law(law_id: str, violations: tuple[Violation, ...]) -> Law:
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
        violations=violations,
    )


def _artifacts(html: str = "<html></html>") -> PageArtifacts:
    now = datetime.now(UTC)
    return PageArtifacts(
        url="https://example.test/",
        status=200,
        html=html,
        headers={},
        cookies=(),
        network_log=(),
        scan_started_at=now,
        scan_finished_at=now,
    )


@pytest.fixture
def patched_scanner(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    state: dict[str, object] = {"calls": 0, "artifacts": _artifacts(), "exc": None}

    async def fake_collect(url: str, timeout: int, user_agent: str) -> PageArtifacts:
        state["calls"] = int(state["calls"]) + 1  # type: ignore[arg-type]
        if state["exc"] is not None:
            raise state["exc"]  # type: ignore[misc]
        return state["artifacts"]  # type: ignore[return-value]

    monkeypatch.setattr(scanner, "collect", fake_collect)
    return state


def test_run_scan_produces_finding_per_violation(patched_scanner: dict[str, object]) -> None:
    triggered = _violation(
        "v-fail",
        page_signals=(
            PageSignal(
                type="trigger",
                description="x",
                html_patterns=('input[type="email"]',),
            ),
        ),
    )
    safe = _violation(
        "v-pass",
        page_signals=(
            PageSignal(
                type="other",
                description="x",
                html_patterns=('input[type="tel"]',),
            ),
        ),
    )
    bundle = CorpusBundle(laws=(_law("law-1", (triggered, safe)),))
    patched_scanner["artifacts"] = _artifacts(html='<form><input type="email"></form>')

    result = asyncio.run(engine.run_scan("https://example.test/", bundle))
    assert result.error is None
    statuses = {f.violation_id: f.status for f in result.findings}
    assert statuses == {"v-fail": "fail", "v-pass": "pass"}


def test_run_scan_aggregates_signals_or(patched_scanner: dict[str, object]) -> None:
    signals = (
        PageSignal(type="trigger", description="x", html_patterns=('input[type="email"]',)),
        PageSignal(type="other", description="x", html_patterns=('input[type="tel"]',)),
    )
    bundle = CorpusBundle(laws=(_law("law-1", (_violation("v-or", page_signals=signals),)),))
    patched_scanner["artifacts"] = _artifacts(html='<form><input type="email"></form>')

    result = asyncio.run(engine.run_scan("https://example.test/", bundle))
    assert {f.status for f in result.findings} == {"fail"}


def test_run_scan_returns_error_on_scan_error(
    patched_scanner: dict[str, object],
) -> None:
    bundle = CorpusBundle(
        laws=(
            _law(
                "law-1",
                (
                    _violation(
                        "v-x",
                        page_signals=(
                            PageSignal(type="t", description="x", html_patterns=("div",)),
                        ),
                    ),
                ),
            ),
        )
    )
    patched_scanner["exc"] = ScanError("DNS failed")

    result = asyncio.run(engine.run_scan("https://nope.test/", bundle))
    assert result.findings == ()
    assert result.error is not None and "DNS failed" in result.error


def test_run_scan_emits_progress_events(patched_scanner: dict[str, object]) -> None:
    v1 = _violation(
        "v-1",
        page_signals=(
            PageSignal(type="t", description="x", html_patterns=('input[type="email"]',)),
        ),
    )
    v2 = _violation(
        "v-2",
        page_signals=(
            PageSignal(type="t", description="x", html_patterns=("nonexistent-tag",)),
        ),
    )
    bundle = CorpusBundle(laws=(_law("law-1", (v1, v2)),))
    patched_scanner["artifacts"] = _artifacts(html='<input type="email">')

    events: list[ScanEvent] = []
    result = asyncio.run(
        engine.run_scan("https://example.test/", bundle, on_event=events.append)
    )

    assert result.error is None
    assert [e.type for e in events] == [
        "scanner_done",
        "violation_evaluated",
        "violation_evaluated",
    ]
    assert events[1].payload["violation_id"] == "v-1"
    assert events[1].payload["status"] == "fail"
    assert events[2].payload["violation_id"] == "v-2"


def test_run_scan_emits_error_event_on_scanner_failure(
    patched_scanner: dict[str, object],
) -> None:
    bundle = CorpusBundle(
        laws=(
            _law(
                "law-1",
                (
                    _violation(
                        "v-x",
                        page_signals=(
                            PageSignal(type="t", description="x", html_patterns=("div",)),
                        ),
                    ),
                ),
            ),
        )
    )
    patched_scanner["exc"] = ScanError("DNS failed")
    events: list[ScanEvent] = []

    result = asyncio.run(
        engine.run_scan("https://nope.test/", bundle, on_event=events.append)
    )

    assert result.error is not None
    assert [e.type for e in events] == ["error"]
    assert events[0].payload["message"] == "DNS failed"


def test_run_scan_copies_violation_fields_to_finding(patched_scanner: dict[str, object]) -> None:
    triggered = _violation(
        "v-x",
        page_signals=(
            PageSignal(type="t", description="x", html_patterns=('input[type="email"]',)),
        ),
        severity="high",
    )
    bundle = CorpusBundle(laws=(_law("law-1", (triggered,)),))
    patched_scanner["artifacts"] = _artifacts(html='<input type="email">')

    result = asyncio.run(engine.run_scan("https://example.test/", bundle))
    finding = result.findings[0]
    assert finding.law_id == "law-1"
    assert finding.severity == "high"
    assert finding.recommendation == "fix"
    assert finding.penalties[0].amount_min == 1000


# ---------------------------------------------------------------------------
# Итерация 6б: скрытие заглушек (см. ADR-0003)
# ---------------------------------------------------------------------------


def test_run_scan_filters_out_all_stubs_violation(patched_scanner: dict[str, object]) -> None:
    """Нарушение, у которого все sub-signals — заглушки (`_not_implemented`),
    не попадает в findings и не эмитит `violation_evaluated`."""
    stubs_only = _violation(
        "v-all-stubs",
        site_signals=(
            SiteSignal(type="t", description="x", check="rkn_registry_lookup"),
            SiteSignal(type="t", description="x", check="tls_audit"),
        ),
    )
    real_pass = _violation(
        "v-real-pass",
        page_signals=(
            PageSignal(type="t", description="x", html_patterns=("nonexistent-tag",)),
        ),
    )
    bundle = CorpusBundle(laws=(_law("law-1", (stubs_only, real_pass)),))

    events: list[ScanEvent] = []
    result = asyncio.run(
        engine.run_scan("https://example.test/", bundle, on_event=events.append)
    )

    found_ids = {f.violation_id for f in result.findings}
    assert "v-all-stubs" not in found_ids
    assert "v-real-pass" in found_ids
    emitted_violations = [
        e.payload["violation_id"]
        for e in events
        if e.type == "violation_evaluated"
    ]
    assert "v-all-stubs" not in emitted_violations


def test_run_scan_filters_out_context_dependent_violation(
    patched_scanner: dict[str, object],
) -> None:
    """ADR-0003 Q4: нарушение с единственным сигналом «required_keywords +
    required_absent без html_patterns» возвращает inconclusive(context_dependent)
    из evaluate и должно скрываться так же, как заглушки."""
    text_trigger = _violation(
        "v-text-trigger",
        page_signals=(
            PageSignal(
                type="bad-no-disclaimer",
                description="x",
                required_keywords=("БАД",),
                required_absent=("не лекарство",),
            ),
        ),
    )
    bundle = CorpusBundle(laws=(_law("law-1", (text_trigger,)),))
    patched_scanner["artifacts"] = _artifacts(html="<html><body>БАД на нашем сайте</body></html>")

    events: list[ScanEvent] = []
    result = asyncio.run(
        engine.run_scan("https://example.test/", bundle, on_event=events.append)
    )
    assert result.findings == ()
    assert all(e.type != "violation_evaluated" for e in events)


def test_run_scan_filters_out_combine_only_violation(patched_scanner: dict[str, object]) -> None:
    """Нарушение с combine-сигналом без реальных проверок отфильтровывается
    так же, как чистая заглушка — combine помечен check_not_implemented."""
    combine_only = _violation(
        "v-combine",
        site_signals=(
            SiteSignal(
                type="t",
                description="x",
                combine=["a", "b"],  # type: ignore[call-arg]
            ),
        ),
    )
    bundle = CorpusBundle(laws=(_law("law-1", (combine_only,)),))

    events: list[ScanEvent] = []
    result = asyncio.run(
        engine.run_scan("https://example.test/", bundle, on_event=events.append)
    )

    assert result.findings == ()
    assert all(e.type != "violation_evaluated" for e in events)


def test_run_scan_keeps_violation_with_real_fail_among_stubs(
    patched_scanner: dict[str, object],
) -> None:
    """Mixed: один реальный fail + несколько заглушек → finding есть, status=fail,
    evidence от реального fail."""
    mixed = _violation(
        "v-mixed-fail",
        page_signals=(
            PageSignal(type="real", description="x", html_patterns=('input[type="email"]',)),
        ),
        site_signals=(SiteSignal(type="stub", description="x", check="rkn_registry_lookup"),),
    )
    bundle = CorpusBundle(laws=(_law("law-1", (mixed,)),))
    patched_scanner["artifacts"] = _artifacts(html='<form><input type="email"></form>')

    result = asyncio.run(engine.run_scan("https://example.test/", bundle))
    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.status == "fail"
    assert finding.inconclusive_reason is None


def test_run_scan_keeps_real_inconclusive_among_stubs(
    patched_scanner: dict[str, object],
) -> None:
    """Mixed: реальный inconclusive (evidence_missing) + stub → finding есть,
    status=inconclusive, reason=evidence_missing (real приоритетнее stub)."""
    # `link_near_form_to_privacy` без PD-форм даёт inconclusive (real, не stub).
    mixed = _violation(
        "v-mixed-inc",
        site_signals=(
            SiteSignal(type="real-inc", description="x", check="link_near_form_to_privacy"),
            SiteSignal(type="stub", description="x", check="tls_audit"),
        ),
    )
    bundle = CorpusBundle(laws=(_law("law-1", (mixed,)),))
    patched_scanner["artifacts"] = _artifacts(html="<html><body><p>no forms</p></body></html>")

    result = asyncio.run(engine.run_scan("https://example.test/", bundle))
    # `link_near_form_to_privacy` возвращает inconclusive без reason —
    # это «real» inconclusive в смысле aggregate_or (reason != check_not_implemented).
    # Stub `tls_audit` имеет reason=check_not_implemented и должен быть подавлен.
    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.status == "inconclusive"
    assert finding.inconclusive_reason != "check_not_implemented"


def test_run_scan_keeps_all_pass_violation(patched_scanner: dict[str, object]) -> None:
    """Все sub-signals pass → finding есть, status=pass, reason=None."""
    all_pass = _violation(
        "v-pass",
        page_signals=(
            PageSignal(type="t", description="x", html_patterns=("nonexistent-tag",)),
        ),
    )
    bundle = CorpusBundle(laws=(_law("law-1", (all_pass,)),))

    result = asyncio.run(engine.run_scan("https://example.test/", bundle))
    assert len(result.findings) == 1
    assert result.findings[0].status == "pass"
    assert result.findings[0].inconclusive_reason is None


# ---------------------------------------------------------------------------
# Контекстный гейтинг через applicability (этап 5)
# ---------------------------------------------------------------------------


def test_run_scan_filters_out_violation_when_context_does_not_apply(
    patched_scanner: dict[str, object],
) -> None:
    """Нарушение с applicability=[payments] на странице без iframe платежей /
    card-input / checkout-ссылок отфильтровывается до оценки сигналов."""
    payments_only = Violation(
        id="v-payments",
        article="ст. 1",
        title="Только для платёжных",
        severity="high",
        description="x",
        detection=Detection(
            page_signals=(
                PageSignal(type="t", description="x", html_patterns=('input[type="email"]',)),
            )
        ),
        penalties=(
            Penalty(subject="organization", coap_article="ст. 1", amount_min=1000, amount_max=2000),
        ),
        recommendation="fix",
        applicability=("payments",),
    )
    bundle = CorpusBundle(laws=(_law("law-1", (payments_only,)),))
    # HTML с email-полем (сигнал бы сработал!), но без признаков платежей.
    patched_scanner["artifacts"] = _artifacts(html='<form><input type="email"></form>')

    events: list[ScanEvent] = []
    result = asyncio.run(
        engine.run_scan("https://example.test/", bundle, on_event=events.append)
    )
    assert result.findings == ()
    assert all(e.type != "violation_evaluated" for e in events)


def test_run_scan_evaluates_violation_when_context_applies(
    patched_scanner: dict[str, object],
) -> None:
    """То же нарушение, но на странице с iframe yookassa → context.applies = True,
    сигналы оцениваются → finding появляется."""
    payments_only = Violation(
        id="v-payments",
        article="ст. 1",
        title="Только для платёжных",
        severity="high",
        description="x",
        detection=Detection(
            page_signals=(
                PageSignal(type="t", description="x", html_patterns=('input[type="email"]',)),
            )
        ),
        penalties=(
            Penalty(subject="organization", coap_article="ст. 1", amount_min=1000, amount_max=2000),
        ),
        recommendation="fix",
        applicability=("payments",),
    )
    bundle = CorpusBundle(laws=(_law("law-1", (payments_only,)),))
    patched_scanner["artifacts"] = _artifacts(
        html=(
            '<html><body>'
            '<iframe src="https://yookassa.ru/widget/123"></iframe>'
            '<form><input type="email"></form>'
            "</body></html>"
        )
    )

    result = asyncio.run(engine.run_scan("https://example.test/", bundle))
    assert len(result.findings) == 1
    assert result.findings[0].violation_id == "v-payments"
    assert result.findings[0].status == "fail"


def test_run_scan_empty_applicability_always_evaluated(
    patched_scanner: dict[str, object],
) -> None:
    """Нарушение без applicability оценивается всегда, даже на пустой странице."""
    universal = _violation(
        "v-universal",
        page_signals=(
            PageSignal(type="t", description="x", html_patterns=("nonexistent-tag",)),
        ),
    )
    assert universal.applicability == ()
    bundle = CorpusBundle(laws=(_law("law-1", (universal,)),))

    result = asyncio.run(engine.run_scan("https://example.test/", bundle))
    assert len(result.findings) == 1
    assert result.findings[0].status == "pass"


# ---------------------------------------------------------------------------
# Finding-валидатор inconclusive_reason (симметричный к CheckResult)
# ---------------------------------------------------------------------------


def test_finding_validator_rejects_reason_with_fail_status() -> None:
    """Симметрично CheckResult: `inconclusive_reason` допустим только при
    `status='inconclusive'`. Защищает от программного создания невалидных
    Finding'ов в обход `_violation_to_finding`."""
    with pytest.raises(ValidationError) as exc_info:
        Finding(
            violation_id="v-1",
            law_id="law-1",
            title="t",
            article="ст. 1",
            severity="low",
            status="fail",
            recommendation="fix",
            inconclusive_reason="check_not_implemented",
        )
    assert "only valid for inconclusive" in str(exc_info.value)


def test_finding_validator_accepts_reason_with_inconclusive_status() -> None:
    f = Finding(
        violation_id="v-1",
        law_id="law-1",
        title="t",
        article="ст. 1",
        severity="low",
        status="inconclusive",
        recommendation="fix",
        inconclusive_reason="evidence_missing",
    )
    assert f.inconclusive_reason == "evidence_missing"


def test_finding_validator_accepts_pass_without_reason() -> None:
    f = Finding(
        violation_id="v-1",
        law_id="law-1",
        title="t",
        article="ст. 1",
        severity="low",
        status="pass",
        recommendation="fix",
    )
    assert f.inconclusive_reason is None
