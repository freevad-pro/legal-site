"""Тесты API сканов через мок-engine.

Поднимаем минимальный FastAPI с `scan_router` и lifespan-подобным state'ом,
подсовываем фейковый `run_scan`, который публикует контролируемую
последовательность событий.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.scan import router as scan_router
from app.auth import hash_password
from app.config import settings
from app.corpus.models import CorpusBundle
from app.db import init_db, upsert_user
from app.engine import Finding, ScanResult
from app.events import ScanEvent
from app.scan_state import ScanRegistry


@pytest.fixture
def temp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db_path = tmp_path / "users.sqlite"
    init_db(db_path)
    monkeypatch.setattr(settings, "database_path", db_path)
    upsert_user(db_path, "demo", hash_password("s3cret"))
    return db_path


@pytest.fixture
def api_app(temp_db: Path) -> FastAPI:
    app = FastAPI()
    app.include_router(scan_router)
    app.state.corpus = CorpusBundle(laws=())
    app.state.scan_registry = ScanRegistry(ttl=timedelta(hours=1))
    app.state.scan_semaphore = asyncio.Semaphore(1)
    app.state.background_tasks = set()
    return app


def _install_fake_run_scan(
    monkeypatch: pytest.MonkeyPatch,
    events: list[ScanEvent],
    result: ScanResult | None = None,
    delay: float = 0.0,
) -> None:
    async def fake_run_scan(
        url: str,
        bundle: CorpusBundle,
        *,
        on_event: Callable[[ScanEvent], None] | None = None,
    ) -> ScanResult:
        for event in events:
            if on_event is not None:
                on_event(event)
            if delay:
                await asyncio.sleep(delay)
        if result is not None:
            return result
        now = datetime.now(UTC)
        return ScanResult(url=url, started_at=now, finished_at=now, findings=())

    # Worker импортирует run_scan по имени — патчим в его namespace.
    monkeypatch.setattr("app.api.scan_worker.run_scan", fake_run_scan)


def _wait_for_status(
    client: TestClient, scan_id: str, status: str, timeout: float = 5.0
) -> dict[str, Any]:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        resp = client.get(f"/api/v1/scans/{scan_id}", auth=("demo", "s3cret"))
        assert resp.status_code == 200
        body = resp.json()
        if body["status"] == status:
            return body
        time.sleep(0.05)
    raise AssertionError(f"scan {scan_id} did not reach {status} in {timeout}s")


def test_post_requires_auth(api_app: FastAPI) -> None:
    with TestClient(api_app) as client:
        resp = client.post("/api/v1/scans", json={"url": "example.ru"})
    assert resp.status_code == 401
    assert resp.headers["WWW-Authenticate"] == 'Basic realm="Legal_site"'


def test_post_rejects_invalid_url(api_app: FastAPI) -> None:
    with TestClient(api_app) as client:
        resp = client.post(
            "/api/v1/scans",
            json={"url": "example"},
            auth=("demo", "s3cret"),
        )
    assert resp.status_code == 422


def test_post_creates_scan_and_get_returns_summary(
    api_app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    events = [
        ScanEvent(type="scanner_done", payload={"url": "https://example.ru"}),
        ScanEvent(
            type="violation_evaluated",
            payload={"violation_id": "v-1", "status": "fail", "severity": "low"},
        ),
    ]
    _install_fake_run_scan(monkeypatch, events)

    with TestClient(api_app) as client:
        post = client.post(
            "/api/v1/scans",
            json={"url": "example.ru"},
            auth=("demo", "s3cret"),
        )
        assert post.status_code == 202
        scan_id = post.json()["scan_id"]

        body = _wait_for_status(client, scan_id, "done")
        assert body["url"] == "https://example.ru"
        assert body["result"] is not None
        assert body["error"] is None


def test_get_unknown_scan_returns_404(api_app: FastAPI) -> None:
    with TestClient(api_app) as client:
        resp = client.get(
            "/api/v1/scans/00000000-0000-0000-0000-000000000000",
            auth=("demo", "s3cret"),
        )
    assert resp.status_code == 404


def _parse_sse(body: str) -> list[tuple[str, dict[str, Any]]]:
    events: list[tuple[str, dict[str, Any]]] = []
    event_type = None
    for line in body.splitlines():
        if line.startswith("event: "):
            event_type = line[len("event: ") :]
        elif line.startswith("data: ") and event_type is not None:
            events.append((event_type, json.loads(line[len("data: ") :])))
            event_type = None
    return events


def test_sse_replays_buffer_after_done(
    api_app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    events = [
        ScanEvent(type="scanner_done", payload={"url": "https://example.ru"}),
        ScanEvent(
            type="violation_evaluated",
            payload={"violation_id": "v-1", "status": "pass", "severity": "low"},
        ),
    ]
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
    result = ScanResult(
        url="https://example.ru",
        started_at=now,
        finished_at=now,
        findings=findings,
    )
    _install_fake_run_scan(monkeypatch, events, result=result)

    with TestClient(api_app) as client:
        post = client.post(
            "/api/v1/scans",
            json={"url": "example.ru"},
            auth=("demo", "s3cret"),
        )
        scan_id = post.json()["scan_id"]
        _wait_for_status(client, scan_id, "done")

        # подписка после завершения — отдаёт буфер и закрывается
        sse_resp = client.get(
            f"/api/v1/scans/{scan_id}/events",
            auth=("demo", "s3cret"),
        )
    assert sse_resp.status_code == 200
    types = [t for t, _ in _parse_sse(sse_resp.text)]
    assert types[0] == "scanner_started"
    assert "scanner_done" in types
    assert "violation_evaluated" in types
    assert types[-1] == "done"


def test_sse_requires_auth(api_app: FastAPI) -> None:
    with TestClient(api_app) as client:
        resp = client.get("/api/v1/scans/00000000-0000-0000-0000-000000000000/events")
    assert resp.status_code == 401
