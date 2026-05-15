"""Оркестратор: scanner → checks → список `Finding`.

В итерации 3 движок берёт **все** violations из корпуса (без категоризации
сайта) и для каждой агрегирует свои сигналы через OR. Категоризация
(`CorpusBundle.for_categories`) — итерация 5+.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Literal

from playwright.async_api import Error as PlaywrightError
from pydantic import BaseModel, ConfigDict

from app import scanner
from app.checks import CheckResult, aggregate_or, evaluate
from app.config import settings
from app.corpus.models import CorpusBundle, Penalty, Violation
from app.events import ScanEvent
from app.scanner import PageArtifacts, ScanError
from app.types import Status

EventSink = Callable[[ScanEvent], None]

logger = logging.getLogger(__name__)

# Порядок прохождения категорий в SSE-стриме. Должен совпадать с CATEGORY_ORDER
# на фронте (frontend/src/hooks/useScanStream.ts), иначе шаги прогресса будут
# заполняться вразнобой.
_CATEGORY_ORDER: tuple[str, ...] = (
    "privacy",
    "cookies",
    "advertising",
    "consumer",
    "info",
    "copyright",
)


def _violations_in_category_order(
    bundle: CorpusBundle,
) -> list[tuple[str, Violation]]:
    law_category = {law.id: law.category for law in bundle.laws}

    def order_key(item: tuple[str, Violation]) -> int:
        law_id, _ = item
        category = law_category.get(law_id)
        try:
            return _CATEGORY_ORDER.index(category) if category else len(_CATEGORY_ORDER)
        except ValueError:
            return len(_CATEGORY_ORDER)

    return sorted(bundle.all_violations(), key=order_key)


class Finding(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    violation_id: str
    law_id: str
    title: str
    article: str
    severity: Literal["low", "medium", "high", "critical"]
    status: Status
    evidence: str | None = None
    explanation: str | None = None
    recommendation: str
    penalties: tuple[Penalty, ...] = ()
    evidence_template: str | None = None


class ScanResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    url: str
    started_at: datetime
    finished_at: datetime
    findings: tuple[Finding, ...] = ()
    error: str | None = None


def _violation_to_finding(law_id: str, violation: Violation, aggregated: CheckResult) -> Finding:
    return Finding(
        violation_id=violation.id,
        law_id=law_id,
        title=violation.title,
        article=violation.article,
        severity=violation.severity,
        status=aggregated.status,
        evidence=aggregated.evidence,
        explanation=aggregated.explanation,
        recommendation=violation.recommendation,
        penalties=violation.penalties,
        evidence_template=violation.evidence_template,
    )


def _evaluate_violation(law_id: str, violation: Violation, artifacts: PageArtifacts) -> Finding:
    sub_results: list[CheckResult] = [
        evaluate(s, artifacts) for s in violation.detection.page_signals
    ]
    sub_results.extend(evaluate(s, artifacts) for s in violation.detection.site_signals)
    aggregated = aggregate_or(sub_results)
    return _violation_to_finding(law_id, violation, aggregated)


async def run_scan(
    url: str,
    bundle: CorpusBundle,
    *,
    on_event: EventSink | None = None,
    with_llm: bool = False,
) -> ScanResult:
    """Запустить сканирование одного URL.

    Возвращает `ScanResult` с findings по всем violations корпуса. Если scanner
    упал на сборе артефактов (DNS, timeout, отсутствие ответа) — возвращается
    `ScanResult(error=str(e), findings=())`.

    `on_event` — опциональный sync-коллбэк для публикации прогресса
    (`scanner_done`, `violation_evaluated`, `error`). CLI его не передаёт.

    `with_llm` — флаг расширенного анализа. В итерации 5а только принимается
    и не используется: реальный механизм отбора LLM-check'ов появится в
    итерации 7 вместе с `app/llm/`.
    """

    del with_llm  # будет использовано в итерации 7

    def _emit(event: ScanEvent) -> None:
        if on_event is not None:
            on_event(event)

    started_at = datetime.now(UTC)
    try:
        artifacts = await scanner.collect(
            url,
            timeout=settings.playwright_timeout_seconds,
            user_agent=settings.user_agent,
        )
    except (ScanError, PlaywrightError) as exc:
        logger.error("scanner failed for %s: %s", url, exc)
        _emit(ScanEvent(type="error", payload={"message": str(exc)}))
        return ScanResult(
            url=url,
            started_at=started_at,
            finished_at=datetime.now(UTC),
            findings=(),
            error=str(exc),
        )

    _emit(ScanEvent(type="scanner_done", payload={"url": artifacts.url}))

    findings: list[Finding] = []
    for law_id, violation in _violations_in_category_order(bundle):
        finding = _evaluate_violation(law_id, violation, artifacts)
        findings.append(finding)
        _emit(
            ScanEvent(
                type="violation_evaluated",
                payload={
                    "violation_id": finding.violation_id,
                    "law_id": finding.law_id,
                    "title": finding.title,
                    "status": finding.status,
                    "severity": finding.severity,
                },
            )
        )
        # Передаём control event-loop'у, чтобы SSE-task успел отдать накопленные
        # события клиенту — иначе все violation_evaluated приходят пачкой в конце.
        await asyncio.sleep(0)

    return ScanResult(
        url=artifacts.url,
        started_at=started_at,
        finished_at=datetime.now(UTC),
        findings=tuple(findings),
    )
