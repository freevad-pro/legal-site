"""Unit-тесты воркера сканов: три ветки исхода + sentinel в очередях."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.api.scan_worker import run_scan_job
from app.config import settings
from app.corpus.models import CorpusBundle
from app.engine import Finding, ScanResult
from app.events import ScanEvent
from app.scan_state import ScanState


@pytest.fixture
def empty_bundle() -> CorpusBundle:
    return CorpusBundle(laws=())


@pytest.fixture
def state() -> ScanState:
    return ScanState(scan_id=uuid4(), url="https://example.ru")


@pytest.fixture
def semaphore() -> asyncio.Semaphore:
    return asyncio.Semaphore(1)


@pytest.fixture
def subscriber(state: ScanState) -> asyncio.Queue[ScanEvent | None]:
    queue: asyncio.Queue[ScanEvent | None] = asyncio.Queue()
    state.queues.append(queue)
    return queue


def _install_run_scan(
    monkeypatch: pytest.MonkeyPatch,
    impl: Callable[..., object],
) -> None:
    monkeypatch.setattr("app.api.scan_worker.run_scan", impl)


def _drain(queue: asyncio.Queue[ScanEvent | None]) -> list[ScanEvent | None]:
    items: list[ScanEvent | None] = []
    while not queue.empty():
        items.append(queue.get_nowait())
    return items


async def test_run_scan_job_done_success(
    state: ScanState,
    empty_bundle: CorpusBundle,
    semaphore: asyncio.Semaphore,
    subscriber: asyncio.Queue[ScanEvent | None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    findings = (
        Finding(
            violation_id="v-1",
            law_id="law-1",
            title="t",
            article="a",
            severity="low",
            status="pass",
            recommendation="ok",
        ),
    )
    now = datetime.now(UTC)
    result = ScanResult(url=state.url, started_at=now, finished_at=now, findings=findings)

    async def fake_run_scan(
        url: str,
        bundle: CorpusBundle,
        *,
        on_event: object,
        with_llm: bool = False,
    ) -> ScanResult:
        return result

    _install_run_scan(monkeypatch, fake_run_scan)
    await run_scan_job(state, empty_bundle, semaphore)

    assert state.status == "done"
    assert state.error is None
    assert state.result is result
    assert state.finished_at is not None
    drained = _drain(subscriber)
    events = [e for e in drained if e is not None]
    assert events[0].type == "scanner_started"
    assert events[-1].type == "done"
    assert events[-1].payload["summary"] == {"failed": 0, "passed": 1, "inconclusive": 0}
    assert drained[-1] is None  # sentinel закрывает стрим SSE-клиента


async def test_run_scan_job_failed_when_scanner_returned_error(
    state: ScanState,
    empty_bundle: CorpusBundle,
    semaphore: asyncio.Semaphore,
    subscriber: asyncio.Queue[ScanEvent | None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime.now(UTC)
    result_with_error = ScanResult(
        url=state.url,
        started_at=now,
        finished_at=now,
        findings=(),
        error="DNS resolution failed",
    )

    async def fake_run_scan(
        url: str,
        bundle: CorpusBundle,
        *,
        on_event: object,
        with_llm: bool = False,
    ) -> ScanResult:
        return result_with_error

    _install_run_scan(monkeypatch, fake_run_scan)
    await run_scan_job(state, empty_bundle, semaphore)

    assert state.status == "failed"
    assert state.error == "DNS resolution failed"
    assert state.result is result_with_error
    events = [e for e in _drain(subscriber) if e is not None]
    assert events[-1].type == "done"
    assert events[-1].payload["error"] == "DNS resolution failed"


async def test_run_scan_job_timeout(
    state: ScanState,
    empty_bundle: CorpusBundle,
    semaphore: asyncio.Semaphore,
    subscriber: asyncio.Queue[ScanEvent | None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "scan_timeout_seconds", 0)

    async def fake_run_scan(
        url: str,
        bundle: CorpusBundle,
        *,
        on_event: object,
        with_llm: bool = False,
    ) -> ScanResult:
        await asyncio.sleep(10)
        raise AssertionError("should not reach")

    _install_run_scan(monkeypatch, fake_run_scan)
    await run_scan_job(state, empty_bundle, semaphore)

    assert state.status == "timeout"
    assert state.error is not None and "timeout" in state.error.lower()
    assert state.result is None
    events = [e for e in _drain(subscriber) if e is not None]
    assert events[-1].type == "done"
    assert events[-1].payload["reason"] == "timeout"


async def test_run_scan_job_failed_on_unhandled_exception(
    state: ScanState,
    empty_bundle: CorpusBundle,
    semaphore: asyncio.Semaphore,
    subscriber: asyncio.Queue[ScanEvent | None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_run_scan(
        url: str,
        bundle: CorpusBundle,
        *,
        on_event: object,
        with_llm: bool = False,
    ) -> ScanResult:
        raise RuntimeError("boom")

    _install_run_scan(monkeypatch, fake_run_scan)
    await run_scan_job(state, empty_bundle, semaphore)

    assert state.status == "failed"
    assert state.error == "boom"
    assert state.result is None
    events = [e for e in _drain(subscriber) if e is not None]
    assert events[-1].type == "error"
    assert events[-1].payload["message"] == "boom"


async def test_run_scan_job_always_closes_subscribers(
    empty_bundle: CorpusBundle,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_run_scan(
        url: str,
        bundle: CorpusBundle,
        *,
        on_event: object,
        with_llm: bool = False,
    ) -> ScanResult:
        raise RuntimeError("boom")

    _install_run_scan(monkeypatch, fake_run_scan)

    state = ScanState(scan_id=uuid4(), url="https://example.ru")
    queue: asyncio.Queue[ScanEvent | None] = asyncio.Queue()
    state.queues.append(queue)

    await run_scan_job(state, empty_bundle, asyncio.Semaphore(1))

    items: list[ScanEvent | None] = []
    while not queue.empty():
        items.append(queue.get_nowait())
    assert items[-1] is None
