"""CLI: `python -m app.scan <url>` → JSON со списком `Finding`'ов в stdout.

Логи (включая WARNING на неизвестные check-функции) идут в stderr.
Exit-code 0 — успешный скан (даже если findings полно). Exit-code 1 —
невалидный URL / битый корпус / неперехваченное исключение. Сетевая ошибка
scanner'а фиксируется в `ScanResult.error` и выводится в JSON с кодом 0.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from app.config import settings
from app.corpus.loader import CorpusLoadError, load_corpus
from app.engine import run_scan
from app.url import normalize_url


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.scan",
        description="Сканирует URL на соответствие законодательству РФ и печатает JSON-отчёт.",
    )
    parser.add_argument("url", help="URL для сканирования (схему можно опустить)")
    parser.add_argument(
        "--corpus-path",
        type=Path,
        default=settings.corpus_path,
        help="Путь к каталогу с корпусом законов (по умолчанию: docs/laws)",
    )
    return parser


async def _amain(url: str, corpus_path: Path) -> int:
    try:
        normalized = normalize_url(url)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    try:
        bundle = load_corpus(corpus_path)
    except CorpusLoadError as exc:
        print(f"error: failed to load corpus: {exc}", file=sys.stderr)
        return 1

    result = await run_scan(normalized, bundle)
    print(result.model_dump_json(indent=2))
    return 0


def main() -> int:
    args = _build_parser().parse_args()
    logging.basicConfig(
        level=settings.log_level,
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    # На Windows консоль по умолчанию cp1251 — стандартные символы (≥, ≤, …)
    # из JSON-вывода не закодируются. Принудительно переключаем stdout/stderr в UTF-8.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    return asyncio.run(_amain(args.url, args.corpus_path))


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
