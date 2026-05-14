import pytest

from app.url import normalize_url


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("example.ru", "https://example.ru"),
        ("www.example.ru", "https://www.example.ru"),
        ("https://example.ru", "https://example.ru"),
        ("http://example.ru", "http://example.ru"),
        ("example.ru:8080", "https://example.ru:8080"),
        ("localhost", "https://localhost"),
        ("localhost:8000", "https://localhost:8000"),
        ("https://example.ru/path?q=1", "https://example.ru/path?q=1"),
        ("  example.ru  ", "https://example.ru"),
    ],
)
def test_normalize_url_valid(raw: str, expected: str) -> None:
    assert normalize_url(raw) == expected


@pytest.mark.parametrize("raw", ["", "   ", "\t\n"])
def test_normalize_url_empty(raw: str) -> None:
    with pytest.raises(ValueError, match="empty input"):
        normalize_url(raw)


@pytest.mark.parametrize("raw", ["example", "https://"])
def test_normalize_url_invalid_host(raw: str) -> None:
    with pytest.raises(ValueError, match="invalid URL"):
        normalize_url(raw)
