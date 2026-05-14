"""SQLite-хранилище: пользователи и (в итерации 7+) кэш LLM.

В итерации 4 — только таблица `users`. WAL включается при инициализации,
чтобы читатели не блокировали писателей и наоборот.

Функции — синхронные (stdlib `sqlite3`). Async-границы (FastAPI handlers,
воркеры) оборачивают вызовы в `asyncio.to_thread`.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    login         TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(path: Path) -> None:
    """Создать БД, включить WAL, применить схему."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(path) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(_SCHEMA)
        conn.commit()


def get_user_password_hash(path: Path, login: str) -> str | None:
    with _connect(path) as conn:
        row = conn.execute(
            "SELECT password_hash FROM users WHERE login = ?", (login,)
        ).fetchone()
    return row["password_hash"] if row is not None else None


def upsert_user(path: Path, login: str, password_hash: str) -> None:
    with _connect(path) as conn:
        conn.execute(
            "INSERT INTO users (login, password_hash) VALUES (?, ?) "
            "ON CONFLICT(login) DO UPDATE SET password_hash = excluded.password_hash",
            (login, password_hash),
        )
        conn.commit()
