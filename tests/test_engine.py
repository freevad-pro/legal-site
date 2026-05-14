"""Тесты engine на fake scanner через monkeypatch."""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime

import pytest

from app import engine, scanner
from app.corpus.models import (
    CorpusBundle,
    Detection,
    Law,
    PageSignal,
    Penalty,
    Source,
    Violation,
)
from app.events import ScanEvent
from app.scanner import PageArtifacts, ScanError


def _violation(
    vid: str,
    *,
    page_signals: tuple[PageSignal, ...] = (),
    severity: str = "low",
) -> Violation:
    return Violation(
        id=vid,
        article="ст. 1",
        title=f"Тест {vid}",
        severity=severity,  # type: ignore[arg-type]
        description="x",
        detection=Detection(page_signals=page_signals),
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
