"""HTTP Basic Auth поверх таблицы `users`.

Пароли хранятся как bcrypt-хэши. Проверка идёт через `bcrypt.checkpw`
с `secrets.compare_digest`-семантикой (bcrypt сам делает constant-time).
"""

from __future__ import annotations

import asyncio
from typing import Annotated

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from app.config import settings
from app.db import get_user_password_hash

_security = HTTPBasic(auto_error=False)


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": f'Basic realm="{settings.basic_auth_realm}"'},
    )


async def get_current_user(
    creds: Annotated[HTTPBasicCredentials | None, Depends(_security)],
) -> str:
    if creds is None:
        raise _unauthorized()

    hashed = await asyncio.to_thread(
        get_user_password_hash, settings.database_path, creds.username
    )
    # Сверяем даже при отсутствующем пользователе — constant-time, чтобы
    # не дать различать «нет такого логина» и «неверный пароль» по таймингу.
    dummy_hash = "$2b$12$" + "." * 53
    candidate = hashed if hashed is not None else dummy_hash
    password_ok = verify_password(creds.password, candidate)

    if hashed is None or not password_ok:
        raise _unauthorized()

    return creds.username
