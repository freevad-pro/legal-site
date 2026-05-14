"""Фоновый воркер скана: оборачивает `run_scan` в семафор + таймаут.

Семафор приобретается **до** `wait_for(timeout)` — иначе ожидание в очереди
съело бы таймаут у самой работы. Финальное событие и `close_subscribers()`
публикуются во всех ветках, чтобы SSE-клиенты гарантированно завершили стрим.
"""

from __future__ import annotations

import asyncio
import logging
from collections import Counter
from datetime import UTC, datetime

from app.config import settings
from app.corpus.models import CorpusBundle
from app.engine import ScanResult, run_scan
from app.events import ScanEvent
from app.logging_config import scan_id_var
from app.scan_state import ScanState

logger = logging.getLogger(__name__)


def _summary(result: ScanResult) -> dict[str, int]:
    counts: Counter[str] = Counter(f.status for f in result.findings)
    return {
        "failed": counts.get("fail", 0),
        "passed": counts.get("pass", 0),
        "inconclusive": counts.get("inconclusive", 0),
    }


async def run_scan_job(
    state: ScanState,
    bundle: CorpusBundle,
    semaphore: asyncio.Semaphore,
) -> None:
    scan_id_var.set(str(state.scan_id))
    async with semaphore:
        state.status = "running"
        state.publish(ScanEvent(type="scanner_started", payload={"url": state.url}))

        try:
            result: ScanResult = await asyncio.wait_for(
                run_scan(state.url, bundle, on_event=state.publish),
                timeout=settings.scan_timeout_seconds,
            )
        except TimeoutError:
            logger.warning("scan timed out after %ss", settings.scan_timeout_seconds)
            state.status = "timeout"
            state.error = f"Scan exceeded timeout of {settings.scan_timeout_seconds}s"
            state.finished_at = datetime.now(UTC)
            state.publish(ScanEvent(type="done", payload={"reason": "timeout"}))
        except Exception as exc:  # noqa: BLE001 - воркер не должен падать
            logger.exception("scan failed: %s", exc)
            state.status = "failed"
            state.error = str(exc)
            state.finished_at = datetime.now(UTC)
            state.publish(ScanEvent(type="error", payload={"message": str(exc)}))
        else:
            state.result = result
            state.finished_at = datetime.now(UTC)
            if result.error is not None:
                state.status = "failed"
                state.error = result.error
                state.publish(
                    ScanEvent(
                        type="done",
                        payload={"summary": _summary(result), "error": result.error},
                    )
                )
            else:
                state.status = "done"
                state.publish(ScanEvent(type="done", payload={"summary": _summary(result)}))
        finally:
            state.close_subscribers()
