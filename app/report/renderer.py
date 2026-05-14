"""Рендер PDF-отчёта по `ScanResult`.

Жёсткое правило: основной body использует bundled-шрифт `ReportSans`
без fallback на системные `sans-serif`. На минималистичных Linux-образах
системных кириллических шрифтов может не быть — лучше шрифт «не подцепился»
и WeasyPrint крикнул в логах, чем тихо рендерить квадратики.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.engine import Finding, ScanResult

_TEMPLATES_DIR = Path(__file__).parent / "templates"

_env = Environment(
    loader=FileSystemLoader(_TEMPLATES_DIR),
    autoescape=select_autoescape(["html", "j2"]),
)


def _section_buckets(result: ScanResult) -> list[tuple[str, str, list[Finding]]]:
    fail = [f for f in result.findings if f.status == "fail"]
    inconclusive = [f for f in result.findings if f.status == "inconclusive"]
    # `pass` отчёт не показывает, чтобы не раздувать PDF
    fail.sort(
        key=lambda f: {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(f.severity, 4)
    )
    return [
        ("Нарушения", "fail", fail),
        ("Проверки без однозначного вердикта", "inconclusive", inconclusive),
    ]


def _render_sync(result: ScanResult) -> bytes:
    # Импорт weasyprint ленивый: на Windows без GTK runtime он падает с OSError
    # ещё на module-level. Делаем так, чтобы можно было импортировать renderer
    # и проверять HTML-шаблон даже без работающего WeasyPrint.
    from weasyprint import HTML

    template = _env.get_template("report.html.j2")
    counts = {
        "fail": sum(1 for f in result.findings if f.status == "fail"),
        "pass_": sum(1 for f in result.findings if f.status == "pass"),
        "inconclusive": sum(1 for f in result.findings if f.status == "inconclusive"),
    }
    html_str = template.render(
        result=result,
        counts=counts,
        sections=_section_buckets(result),
    )
    return HTML(string=html_str, base_url=str(_TEMPLATES_DIR)).write_pdf()  # type: ignore[no-any-return]


async def render_pdf(result: ScanResult) -> bytes:
    return await asyncio.to_thread(_render_sync, result)
