"""HTTP-API аутентификации: login / logout / me.

`POST /login` — `{login, password}` → 200 + HttpOnly cookie с session_id.
`POST /logout` — 204 + cookie удалена.
`GET /me` — 200 всегда: `{login: str | null}` (null для анонимного).

Единая формулировка ошибки login защищает от user-enumeration: «нет такого
логина» и «неверный пароль» отдают одинаковый 401-detail, а dummy-hash в
сценарии «нет логина» уравнивает timing.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field

from app.auth import (
    create_session,
    delete_session,
    get_optional_user,
    purge_expired_sessions,
    verify_password,
)
from app.config import settings
from app.db import get_user_password_hash

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth")

# Заведомо невалидный bcrypt-хэш правильной длины. Нужен только чтобы
# `verify_password` для несуществующего пользователя выполнил bcrypt-сверку
# и потратил столько же времени, сколько для существующего, — отсюда
# constant-time-семантика без раскрытия факта существования логина.
_DUMMY_HASH = "$2b$12$" + "." * 53


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Длины ограничиваем, чтобы тривиальный DoS большой строкой не уходил в bcrypt.
    login: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class UserInfo(BaseModel):
    login: str | None


@router.post("/login", response_model=UserInfo)
async def login(payload: LoginRequest, response: Response) -> UserInfo:
    hashed = await asyncio.to_thread(
        get_user_password_hash, settings.database_path, payload.login
    )
    candidate = hashed if hashed is not None else _DUMMY_HASH
    password_ok = verify_password(payload.password, candidate)

    if hashed is None or not password_ok:
        logger.warning("failed login attempt")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль",
        )

    await purge_expired_sessions()
    session_id = await create_session(payload.login)
    response.set_cookie(
        key=settings.session_cookie_name,
        value=session_id,
        max_age=settings.session_ttl_days * 86400,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )
    logger.info("login ok: %s", payload.login)
    return UserInfo(login=payload.login)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    user: Annotated[str | None, Depends(get_optional_user)],
) -> None:
    """Идемпотентный logout: всегда 204.

    Без валидной cookie тоже отдаём 204, чтобы фронт мог дёргать /logout
    «на всякий случай» без обработки 401 как успешного исхода. Истёкшая
    сессия в БД (если cookie ещё на клиенте) будет подобрана фоновой
    чисткой; cookie на клиенте мы всё равно явно удаляем заголовком.
    """

    session_id = request.cookies.get(settings.session_cookie_name)
    if session_id is not None:
        await delete_session(session_id)
    # delete_cookie должна передать тот же набор атрибутов, что set_cookie:
    # строгие реализации не сматчат cookie без совпадения secure/samesite.
    response.delete_cookie(
        key=settings.session_cookie_name,
        path="/",
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
    )
    if user is not None:
        logger.info("logout ok: %s", user)
    return None


@router.get("/me", response_model=UserInfo)
async def me(
    user: Annotated[str | None, Depends(get_optional_user)],
) -> UserInfo:
    return UserInfo(login=user)
