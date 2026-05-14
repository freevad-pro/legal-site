"""Парсер справочника законов из `docs/laws/*.md`.

Возвращает иммутабельный [CorpusBundle]. Fail-fast: первая же ошибка валидации
останавливает загрузку, никакого частичного парсинга.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import frontmatter
from pydantic import ValidationError

from app.corpus.models import CorpusBundle, Law

_SKIP_FILES = frozenset({"readme.md", "schema.md"})


class CorpusLoadError(Exception):
    """Ошибка загрузки или валидации корпуса."""


def _read_frontmatter(path: Path) -> dict[str, Any]:
    try:
        post = frontmatter.load(path)
    except Exception as exc:
        raise CorpusLoadError(f"{path}: failed to parse frontmatter: {exc}") from exc

    metadata = post.metadata
    if not isinstance(metadata, dict) or not metadata:
        raise CorpusLoadError(f"{path}: frontmatter is empty or not a mapping")
    return metadata


def _collect_common_ids(common_dir: Path) -> frozenset[str]:
    if not common_dir.exists():
        return frozenset()

    ids: set[str] = set()
    for path in sorted(common_dir.glob("*.md")):
        if path.name.lower() in _SKIP_FILES:
            continue
        metadata = _read_frontmatter(path)
        common_id = metadata.get("id")
        if not isinstance(common_id, str) or not common_id:
            raise CorpusLoadError(f"{path}: common document must declare a non-empty 'id'")
        if common_id in ids:
            raise CorpusLoadError(f"{path}: duplicate common id {common_id!r}")
        ids.add(common_id)
    return frozenset(ids)


def _parse_law(path: Path) -> Law:
    metadata = _read_frontmatter(path)
    try:
        return Law.model_validate(metadata)
    except ValidationError as exc:
        raise CorpusLoadError(f"{path}: {exc}") from exc


def load_corpus(path: Path) -> CorpusBundle:
    """Загрузить и валидировать корпус законов.

    Парсит все `*.md` в `path` (кроме README.md / schema.md) как самостоятельные акты
    и `path/common/*.md` — как ссылочные документы (полную модель не строим, нужны
    только id для резолва `references_in_common`).
    """

    if not path.exists() or not path.is_dir():
        raise CorpusLoadError(f"{path}: corpus directory does not exist")

    common_ids = _collect_common_ids(path / "common")

    laws: list[Law] = []
    for law_path in sorted(path.glob("*.md")):
        if law_path.name.lower() in _SKIP_FILES:
            continue
        laws.append(_parse_law(law_path))

    if not laws:
        raise CorpusLoadError(f"{path}: no law files found")

    try:
        return CorpusBundle.model_validate({"laws": tuple(laws), "common_ids": common_ids})
    except ValidationError as exc:
        raise CorpusLoadError(f"{path}: bundle validation failed: {exc}") from exc
