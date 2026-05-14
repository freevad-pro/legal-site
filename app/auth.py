"""Аутентификация по cookie-сессии.

Пароли хранятся как bcrypt-хэши (см. `verify_password`).
Сессии — server-side: 256-бит `session_id` в SQLite + HttpOnly Secure cookie.
TTL rolling — каждое чтение валидной сессии сдвигает `expires_at`.

Async-обёртки над `app.db.*` через `asyncio.to_thread` — SQLite stdlib
синхронный, мы не блокируем event loop.
"""

from __future__ import annotations

import asyncio
import logging
import secrets
from datetime import UTC, datetime, timedelta

import bcrypt
from fastapi import Request

from app.config import settings
from app.db import (
    delete_expired_sessions,
    delete_session_by_id,
    insert_session,
    select_session,
    update_session_seen,
)

logger = logging.getLogger(__name__)


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def _ttl() -> timedelta:
    return timedelta(days=settings.session_ttl_days)


async def create_session(login: str) -> str:
    """Создать новую сессию и вернуть session_id (для записи в cookie)."""

    session_id = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    expires_at = now + _ttl()
    await asyncio.to_thread(
        insert_session,
        settings.database_path,
        session_id,
        login,
        now,
        expires_at,
        now,
    )
    return session_id


async def delete_session(session_id: str) -> int:
    """Удалить сессию (logout). Возвращает число удалённых строк."""

    return await asyncio.to_thread(
        delete_session_by_id, settings.database_path, session_id
    )


async def get_user_by_session(session_id: str) -> str | None:
    """Вернуть login по session_id или None.

    На валидной сессии — обновляет `last_seen_at`/`expires_at` (rolling TTL).
    Истёкшие сессии трактуются как `None` (физическая чистка — ленивая,
    через `purge_expired_sessions` при login).
    """

    row = await asyncio.to_thread(
        select_session, settings.database_path, session_id
    )
    if row is None:
        return None
    expires_at = datetime.fromisoformat(row["expires_at"])
    now = datetime.now(UTC)
    if expires_at < now:
        return None

    new_expires = now + _ttl()
    await asyncio.to_thread(
        update_session_seen,
        settings.database_path,
        session_id,
        now,
        new_expires,
    )
    login: str = row["user_login"]
    return login


async def purge_expired_sessions() -> int:
    """Удалить истёкшие сессии. Возвращает число удалённых строк."""

    now = datetime.now(UTC)
    removed = await asyncio.to_thread(
        delete_expired_sessions, settings.database_path, now
    )
    if removed > 0:
        logger.info("purged %d expired session(s)", removed)
    return removed


async def get_optional_user(request: Request) -> str | None:
    """Depends-фабрика: вернуть login по cookie или None для анонимного."""

    session_id = request.cookies.get(settings.session_cookie_name)
    if not session_id:
        return None
    return await get_user_by_session(session_id)
