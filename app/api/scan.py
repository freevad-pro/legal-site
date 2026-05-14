"""HTTP-API сканов: POST/GET/SSE.

`POST /scans` принимает `with_llm: bool` — анонимный пользователь может
запросить только бесплатные детерминированные проверки (`with_llm=false`);
расширенный анализ (`with_llm=true`) требует валидной cookie-сессии.

`GET /scans/{id}`, `/events`, `/report.pdf` — публичные (UUIDv4 — достаточная
защита для MVP). `/health` живёт в `app/api/health.py`.
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
from datetime import UTC, datetime
from typing import Annotated, Any
from urllib.parse import urlparse
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.api.scan_worker import run_scan_job
from app.auth import get_optional_user
from app.corpus.models import CorpusBundle
from app.engine import ScanResult
from app.events import ScanEvent
from app.report.renderer import render_pdf
from app.scan_state import ScanRegistry, ScanState
from app.url import normalize_url

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1")


class CreateScanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str = Field(..., description="URL для сканирования")
    with_llm: bool = Field(
        default=False,
        description="Расширенный анализ (LLM); требует валидной сессии",
    )

    @field_validator("url")
    @classmethod
    def _normalize(cls, raw: str) -> str:
        return normalize_url(raw)


class CreateScanResponse(BaseModel):
    scan_id: UUID


class ScanSummary(BaseModel):
    scan_id: UUID
    url: str
    status: str
    with_llm: bool
    started_at: datetime
    finished_at: datetime | None
    error: str | None
    result: ScanResult | None


def _registry(request: Request) -> ScanRegistry:
    return request.app.state.scan_registry  # type: ignore[no-any-return]


def _bundle(request: Request) -> CorpusBundle:
    return request.app.state.corpus  # type: ignore[no-any-return]


def _semaphore(request: Request) -> asyncio.Semaphore:
    return request.app.state.scan_semaphore  # type: ignore[no-any-return]


def _background_tasks(request: Request) -> set[asyncio.Task[None]]:
    return request.app.state.background_tasks  # type: ignore[no-any-return]


def _get_state_or_404(registry: ScanRegistry, scan_id: UUID) -> ScanState:
    state = registry.get(scan_id)
    if state is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="scan not found")
    return state


@router.post(
    "/scans",
    response_model=CreateScanResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_scan(
    payload: CreateScanRequest,
    registry: Annotated[ScanRegistry, Depends(_registry)],
    bundle: Annotated[CorpusBundle, Depends(_bundle)],
    semaphore: Annotated[asyncio.Semaphore, Depends(_semaphore)],
    tasks: Annotated[set[asyncio.Task[None]], Depends(_background_tasks)],
    user: Annotated[str | None, Depends(get_optional_user)] = None,
) -> CreateScanResponse:
    if payload.with_llm and user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Расширенный анализ доступен только после входа",
        )
    state = registry.create(payload.url, with_llm=payload.with_llm)
    task = asyncio.create_task(run_scan_job(state, bundle, semaphore))
    # Держим сильную ссылку, иначе Python GC может прибрать таску до завершения.
    tasks.add(task)
    task.add_done_callback(tasks.discard)
    logger.info("scan created for %s (with_llm=%s)", state.url, state.with_llm)
    return CreateScanResponse(scan_id=state.scan_id)


@router.get("/scans/{scan_id}", response_model=ScanSummary)
async def get_scan(
    scan_id: UUID,
    registry: Annotated[ScanRegistry, Depends(_registry)],
) -> ScanSummary:
    state = _get_state_or_404(registry, scan_id)
    return ScanSummary(
        scan_id=state.scan_id,
        url=state.url,
        status=state.status,
        with_llm=state.with_llm,
        started_at=state.started_at,
        finished_at=state.finished_at,
        error=state.error,
        result=state.result if isinstance(state.result, ScanResult) else None,
    )


def _event_to_sse(event: ScanEvent) -> bytes:
    payload: dict[str, Any] = {
        "timestamp": event.timestamp.isoformat(),
        "payload": event.payload,
    }
    data = json.dumps(payload, ensure_ascii=False)
    return f"event: {event.type}\ndata: {data}\n\n".encode()


async def _sse_stream(state: ScanState) -> Any:
    # Сначала — буфер истории. Считаем, сколько отдали, чтобы потом добрать
    # «хвост», если воркер завершился пока мы готовили подписку.
    snapshot = list(state.events)
    for event in snapshot:
        yield _event_to_sse(event)
    delivered = len(snapshot)

    # Если уже терминальный — закрываем стрим, не подписываясь.
    if state.is_terminal():
        return

    queue: asyncio.Queue[ScanEvent | None] = asyncio.Queue()
    state.queues.append(queue)
    try:
        # Повторная проверка после подписки: воркер мог завершиться между
        # первой is_terminal() и append, его sentinel в нашу очередь не дошёл.
        # Сами добираем то, что появилось в events между snapshot и append.
        if state.is_terminal():
            for event in state.events[delivered:]:
                yield _event_to_sse(event)
            return

        while True:
            item = await queue.get()
            if item is None:
                return
            yield _event_to_sse(item)
            if item.type in {"done", "error"}:
                return
    finally:
        if queue in state.queues:
            state.queues.remove(queue)


@router.get("/scans/{scan_id}/events")
async def get_scan_events(
    scan_id: UUID,
    registry: Annotated[ScanRegistry, Depends(_registry)],
) -> StreamingResponse:
    state = _get_state_or_404(registry, scan_id)
    return StreamingResponse(_sse_stream(state), media_type="text/event-stream")


@router.get("/scans/{scan_id}/report.pdf")
async def get_scan_report(
    scan_id: UUID,
    registry: Annotated[ScanRegistry, Depends(_registry)],
) -> StreamingResponse:
    state = _get_state_or_404(registry, scan_id)
    if state.status != "done" or not isinstance(state.result, ScanResult):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"PDF available only when scan is done (current: {state.status})",
        )

    pdf_bytes = await render_pdf(state.result)

    host = urlparse(state.url).hostname or "unknown"
    date_label = (state.finished_at or datetime.now(UTC)).strftime("%Y-%m-%d")
    filename = f"legal-audit-{host}-{date_label}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(pdf_bytes)),
        },
    )
