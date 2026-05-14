"""Тесты `load_corpus` на синтетических фикстурах в `tests/fixtures/laws/`."""

from pathlib import Path

import pytest

from app.corpus.loader import CorpusLoadError, load_corpus

FIXTURES = Path(__file__).parent / "fixtures" / "laws"


def test_loader_happy_path_loads_good_fixture() -> None:
    bundle = load_corpus(FIXTURES / "good")

    assert len(bundle.laws) == 2
    assert bundle.total_violations == 3
    assert bundle.find_law("test-fz-a") is not None
    assert bundle.find_law("test-fz-b") is not None

    found = bundle.find_violation("test-a-violation-html-patterns")
    assert found is not None
    law_id, violation = found
    assert law_id == "test-fz-a"
    assert violation.severity == "high"

    related = bundle.find_law("test-fz-b")
    assert related is not None and related.related == ("test-fz-a",)


def test_loader_rejects_duplicate_violation_id() -> None:
    with pytest.raises(CorpusLoadError) as exc_info:
        load_corpus(FIXTURES / "bad_duplicate_violation")
    assert "duplicate violation id" in str(exc_info.value)


def test_loader_rejects_unresolvable_related() -> None:
    with pytest.raises(CorpusLoadError) as exc_info:
        load_corpus(FIXTURES / "bad_related")
    assert "related" in str(exc_info.value)


def test_loader_rejects_invalid_yaml() -> None:
    with pytest.raises(CorpusLoadError):
        load_corpus(FIXTURES / "bad_yaml")


def test_loader_rejects_partial_without_notes() -> None:
    with pytest.raises(CorpusLoadError) as exc_info:
        load_corpus(FIXTURES / "bad_partial_without_notes")
    assert "verification_notes" in str(exc_info.value)


def test_loader_rejects_missing_directory(tmp_path: Path) -> None:
    with pytest.raises(CorpusLoadError):
        load_corpus(tmp_path / "does-not-exist")


def test_loader_rejects_empty_directory(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(CorpusLoadError) as exc_info:
        load_corpus(empty)
    assert "no law files" in str(exc_info.value)
