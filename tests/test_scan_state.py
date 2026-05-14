from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from app.events import ScanEvent
from app.scan_state import ScanRegistry, ScanState


def test_registry_creates_and_finds() -> None:
    reg = ScanRegistry(ttl=timedelta(hours=1))
    state = reg.create("https://example.ru")
    assert reg.get(state.scan_id) is state
    assert reg.get(state.scan_id) is not None  # touch не теряет state
    assert len(reg) == 1


def test_registry_purge_skips_active() -> None:
    reg = ScanRegistry(ttl=timedelta(seconds=0))  # всё «просрочено»
    state = reg.create("https://example.ru")
    state.last_accessed_at = datetime.now(UTC) - timedelta(hours=2)

    # pending — не удаляем
    assert reg.purge_expired() == 0
    assert len(reg) == 1

    # running — не удаляем
    state.status = "running"
    assert reg.purge_expired() == 0
    assert len(reg) == 1

    # done — удаляем
    state.status = "done"
    assert reg.purge_expired() == 1
    assert len(reg) == 0


def test_registry_purge_keeps_recently_accessed_done() -> None:
    reg = ScanRegistry(ttl=timedelta(hours=1))
    state = reg.create("https://example.ru")
    state.status = "done"
    # last_accessed_at ровно сейчас → не просрочен
    assert reg.purge_expired() == 0
    assert len(reg) == 1


def test_publish_writes_buffer_and_queue() -> None:
    state = ScanState(scan_id=__import__("uuid").uuid4(), url="https://example.ru")
    queue: asyncio.Queue[ScanEvent | None] = asyncio.Queue()
    state.queues.append(queue)

    event = ScanEvent(type="scanner_started", payload={"url": state.url})
    state.publish(event)

    assert state.events == [event]
    assert queue.get_nowait() is event


def test_close_subscribers_sends_sentinel() -> None:
    state = ScanState(scan_id=__import__("uuid").uuid4(), url="https://example.ru")
    queue: asyncio.Queue[ScanEvent | None] = asyncio.Queue()
    state.queues.append(queue)

    state.close_subscribers()
    assert queue.get_nowait() is None


@pytest.mark.parametrize(
    "status, expected_terminal",
    [
        ("pending", False),
        ("running", False),
        ("done", True),
        ("failed", True),
        ("timeout", True),
    ],
)
def test_is_terminal(status: str, expected_terminal: bool) -> None:
    state = ScanState(scan_id=__import__("uuid").uuid4(), url="https://example.ru")
    state.status = status  # type: ignore[assignment]
    assert state.is_terminal() is expected_terminal
