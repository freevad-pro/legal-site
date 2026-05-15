"""Тесты PDF-рендера.

На Windows WeasyPrint требует GTK3-runtime. Если он не установлен —
импорт `weasyprint` падает с OSError при загрузке нативных библиотек.
Тогда тест помечается как `skip`, а не `fail` (в Docker/Linux это
безусловно проходит).
"""

from __future__ import annotations

import asyncio
import importlib.util
from datetime import UTC, datetime

import pytest

from app.engine import Finding, ScanResult


def _weasyprint_available() -> bool:
    if importlib.util.find_spec("weasyprint") is None:
        return False
    try:
        import weasyprint  # noqa: F401

        return True
    except OSError:
        return False


_skip_no_weasyprint = pytest.mark.skipif(
    not _weasyprint_available(),
    reason="WeasyPrint native deps (Pango/GTK) недоступны в этом окружении",
)


def _sample_result() -> ScanResult:
    now = datetime.now(UTC)
    findings = (
        Finding(
            violation_id="152-fz-no-policy",
            law_id="152-fz",
            title="Отсутствует политика обработки персональных данных",
            article="ч. 2 ст. 18.1 152-ФЗ",
            severity="high",
            status="fail",
            evidence="На странице не найдена ссылка на политику.",
            explanation="Оператор обязан опубликовать политику в свободном доступе.",
            recommendation="Опубликовать политику и поставить ссылку в футере.",
        ),
        Finding(
            violation_id="152-fz-no-consent",
            law_id="152-fz",
            title="Форма без согласия на обработку ПДн",
            article="ст. 9 152-ФЗ",
            severity="critical",
            status="fail",
            recommendation="Добавить чекбокс согласия рядом с кнопкой отправки.",
        ),
    )
    return ScanResult(
        url="https://example.ru",
        started_at=now,
        finished_at=now,
        findings=findings,
    )


@_skip_no_weasyprint
def test_render_pdf_produces_pdf_bytes() -> None:
    from app.report.renderer import render_pdf

    pdf = asyncio.run(render_pdf(_sample_result()))
    assert pdf[:5] == b"%PDF-"
    assert len(pdf) > 1000


@_skip_no_weasyprint
def test_render_pdf_embeds_dejavu_font() -> None:
    import re
    import zlib

    from app.report.renderer import render_pdf

    pdf = asyncio.run(render_pdf(_sample_result()))
    # WeasyPrint в PDF 1.7 пакует объекты в Object Streams + FlateDecode —
    # имена шрифтов оказываются не в plain-text, а в zlib-сжатых блоках.
    # Распаковываем все streams и собираем содержимое для поиска.
    decoded_blobs: list[bytes] = []
    for match in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", pdf, flags=re.DOTALL):
        try:
            decoded_blobs.append(zlib.decompress(match.group(1)))
        except zlib.error:
            continue
    decoded = b"".join(decoded_blobs)

    # (1) В PDF встроен реальный TTF-стрим (FontFile2 — TrueType font descriptor key).
    assert b"FontFile2" in decoded, "no TTF font embedded — bundled @font-face не подключился"
    # (2) Шрифт встроен под нашим CSS-именем ReportSans (оригинальное «DejaVu»
    # WeasyPrint затирает при subset'инге, поэтому имя файла в PDF не ищем).
    assert b"ReportSans" in decoded, (
        "bundled ReportSans (DejaVu) не embed'нут — кириллица сломается"
    )


def test_render_pdf_contains_cyrillic_title() -> None:
    """Проверяем, что в HTML-этапе кириллица не превращается в `?`.

    Прямой поиск кириллических байтов в потоке PDF ненадёжен (текст хранится
    в виде индексов глифов), но HTML-этап мы можем дёрнуть напрямую через
    Jinja-окружение и проверить, что подстановка корректна.
    """

    from app.report.renderer import _env

    template = _env.get_template("report.html.j2")
    html = template.render(
        result=_sample_result(),
        counts={"fail": 2, "pass_": 0, "inconclusive": 0},
        sections=[
            ("Нарушения", "fail", list(_sample_result().findings)),
            ("Проверки без однозначного вердикта", "inconclusive", []),
        ],
    )
    assert "Отсутствует политика обработки персональных данных" in html
    assert "ст. 9 152-ФЗ" in html
