"""Нормализация пользовательского URL.

Переехало из `app/scan.py` в отдельный модуль, чтобы CLI и API использовали
одну реализацию. Правила нормализации зафиксированы в vision (раздел
«Сценарии работы пользователя»).
"""

from __future__ import annotations

from urllib.parse import urlparse


def normalize_url(raw: str) -> str:
    """Нормализовать пользовательский URL по правилам vision.

    - strip пробелов;
    - если нет схемы → префиксуем `https://`;
    - валидируем `netloc` (непустой, содержит точку или `localhost`);
    - http→https автоматически не апгрейдим (отсутствие HTTPS — повод для нарушения).
    """

    raw = (raw or "").strip()
    if not raw:
        raise ValueError("invalid URL: empty input")

    parsed = urlparse(raw)
    # RFC 3986 разрешает алфавитно-цифровую схему с `.` (urlparse трактует
    # "example.ru:8080" как scheme="example.ru", netloc="", path="8080").
    # Для пользовательского ввода ограничиваемся http/https — иначе считаем,
    # что схема не указана, и префиксуем https://.
    if parsed.scheme not in {"http", "https"}:
        parsed = urlparse(f"https://{raw}")

    netloc = parsed.netloc
    if not netloc:
        raise ValueError(f"invalid URL: empty host in {raw!r}")
    host = netloc.split(":", 1)[0]
    if "." not in host and host != "localhost":
        raise ValueError(f"invalid URL: host {host!r} does not look like an address")
    return parsed.geturl()
