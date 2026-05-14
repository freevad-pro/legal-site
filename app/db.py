"""SQLite-хранилище: пользователи, сессии и (в итерации 7+) кэш LLM.

WAL включается при инициализации, чтобы читатели не блокировали писателей.

Все timestamp-поля в таблице `sessions` — `TEXT` с ISO-8601 (UTC, aware).
Не используем `CURRENT_TIMESTAMP` SQLite: он теряет tzinfo, а весь код
оперирует `datetime.now(UTC)` с aware-datetime.

Foreign keys в SQLite по умолчанию выключены и мы их не включаем —
консистентность `sessions.user_login -> users.login` обеспечивается на
уровне приложения (сессии создаются только после успешного `verify_password`).

Функции — синхронные (stdlib `sqlite3`). Async-границы (FastAPI handlers,
воркеры) оборачивают вызовы в `asyncio.to_thread`.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    login         TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS sessions (
    session_id    TEXT PRIMARY KEY,
    user_login    TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    expires_at    TEXT NOT NULL,
    last_seen_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at);
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


def upsert_user_and_revoke_sessions(
    path: Path, login: str, password_hash: str
) -> int:
    """Атомарно: upsert пользователя + удалить все его сессии.

    Гарантирует, что смена пароля немедленно инвалидирует ранее выданные
    session_id (типичный отклик на «возможно, скомпрометирован»).

    Возвращает число удалённых сессий (0 для нового пользователя).
    """

    with _connect(path) as conn:
        conn.execute(
            "INSERT INTO users (login, password_hash) VALUES (?, ?) "
            "ON CONFLICT(login) DO UPDATE SET password_hash = excluded.password_hash",
            (login, password_hash),
        )
        cursor = conn.execute(
            "DELETE FROM sessions WHERE user_login = ?", (login,)
        )
        revoked = cursor.rowcount
        conn.commit()
    return revoked


def insert_session(
    path: Path,
    session_id: str,
    user_login: str,
    created_at: datetime,
    expires_at: datetime,
    last_seen_at: datetime,
) -> None:
    with _connect(path) as conn:
        conn.execute(
            "INSERT INTO sessions "
            "(session_id, user_login, created_at, expires_at, last_seen_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                session_id,
                user_login,
                created_at.isoformat(),
                expires_at.isoformat(),
                last_seen_at.isoformat(),
            ),
        )
        conn.commit()


def select_session(path: Path, session_id: str) -> sqlite3.Row | None:
    with _connect(path) as conn:
        row: sqlite3.Row | None = conn.execute(
            "SELECT session_id, user_login, created_at, expires_at, last_seen_at "
            "FROM sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
    return row


def update_session_seen(
    path: Path,
    session_id: str,
    last_seen_at: datetime,
    expires_at: datetime,
) -> None:
    with _connect(path) as conn:
        conn.execute(
            "UPDATE sessions SET last_seen_at = ?, expires_at = ? "
            "WHERE session_id = ?",
            (last_seen_at.isoformat(), expires_at.isoformat(), session_id),
        )
        conn.commit()


def delete_session_by_id(path: Path, session_id: str) -> int:
    with _connect(path) as conn:
        cursor = conn.execute(
            "DELETE FROM sessions WHERE session_id = ?", (session_id,)
        )
        conn.commit()
        return cursor.rowcount


def delete_expired_sessions(path: Path, now: datetime) -> int:
    with _connect(path) as conn:
        cursor = conn.execute(
            "DELETE FROM sessions WHERE expires_at < ?", (now.isoformat(),)
        )
        conn.commit()
        return cursor.rowcount
