"""Оркестратор: scanner → checks → список `Finding`.

В итерации 3 движок берёт **все** violations из корпуса (без категоризации
сайта) и для каждой агрегирует свои сигналы через OR. Категоризация
(`CorpusBundle.for_categories`) — итерация 5+.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Literal

from playwright.async_api import Error as PlaywrightError
from pydantic import BaseModel, ConfigDict

from app import scanner
from app.checks import CheckResult, aggregate_or, evaluate
from app.config import settings
from app.corpus.models import CorpusBundle, Penalty, Violation
from app.scanner import PageArtifacts, ScanError
from app.types import Status

logger = logging.getLogger(__name__)


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
    )


def _evaluate_violation(law_id: str, violation: Violation, artifacts: PageArtifacts) -> Finding:
    sub_results: list[CheckResult] = [
        evaluate(s, artifacts) for s in violation.detection.page_signals
    ]
    sub_results.extend(evaluate(s, artifacts) for s in violation.detection.site_signals)
    aggregated = aggregate_or(sub_results)
    return _violation_to_finding(law_id, violation, aggregated)


async def run_scan(url: str, bundle: CorpusBundle) -> ScanResult:
    """Запустить сканирование одного URL.

    Возвращает `ScanResult` с findings по всем violations корпуса. Если scanner
    упал на сборе артефактов (DNS, timeout, отсутствие ответа) — возвращается
    `ScanResult(error=str(e), findings=())`.
    """

    started_at = datetime.now(UTC)
    try:
        artifacts = await scanner.collect(
            url, timeout=settings.scan_timeout_seconds, user_agent=settings.user_agent
        )
    except (ScanError, PlaywrightError) as exc:
        logger.error("scanner failed for %s: %s", url, exc)
        return ScanResult(
            url=url,
            started_at=started_at,
            finished_at=datetime.now(UTC),
            findings=(),
            error=str(exc),
        )

    findings: list[Finding] = []
    for law_id, violation in bundle.all_violations():
        findings.append(_evaluate_violation(law_id, violation, artifacts))

    return ScanResult(
        url=artifacts.url,
        started_at=started_at,
        finished_at=datetime.now(UTC),
        findings=tuple(findings),
    )
