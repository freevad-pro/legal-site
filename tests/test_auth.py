from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.auth import router as auth_router
from app.auth import hash_password, purge_expired_sessions, verify_password
from app.config import settings
from app.db import (
    delete_expired_sessions,
    get_user_password_hash,
    init_db,
    insert_session,
    select_session,
    upsert_user_and_revoke_sessions,
)


@pytest.fixture
def temp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    db_path = tmp_path / "users.sqlite"
    init_db(db_path)
    monkeypatch.setattr(settings, "database_path", db_path)
    # TestClient ходит на http://testserver — Secure cookie через http не пройдёт.
    monkeypatch.setattr(settings, "session_cookie_secure", False)
    yield db_path


@pytest.fixture
def app_with_auth() -> FastAPI:
    app = FastAPI()
    app.include_router(auth_router)
    return app


def _login(client: TestClient, login: str, password: str) -> dict[str, str]:
    resp = client.post(
        "/api/v1/auth/login", json={"login": login, "password": password}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert isinstance(body, dict)
    return body


def test_init_db_creates_users_and_sessions_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "users.sqlite"
    init_db(db_path)
    assert db_path.exists()
    # повторный init — без падения
    init_db(db_path)
    assert get_user_password_hash(db_path, "missing") is None
    # таблица sessions создана — select по несуществующему ключу не падает
    assert select_session(db_path, "missing-session-id") is None


def test_hash_and_verify_roundtrip() -> None:
    hashed = hash_password("s3cret")
    assert verify_password("s3cret", hashed) is True
    assert verify_password("wrong", hashed) is False


def test_verify_password_handles_garbage_hash() -> None:
    assert verify_password("any", "not-a-bcrypt-hash") is False


def test_login_sets_cookie_and_me_returns_login(
    temp_db: Path, app_with_auth: FastAPI
) -> None:
    upsert_user_and_revoke_sessions(temp_db, "demo", hash_password("s3cret"))
    with TestClient(app_with_auth) as client:
        body = _login(client, "demo", "s3cret")
        assert body == {"login": "demo"}
        assert settings.session_cookie_name in client.cookies

        me = client.get("/api/v1/auth/me")
        assert me.status_code == 200
        assert me.json() == {"login": "demo"}


def test_login_wrong_password_returns_401_no_cookie(
    temp_db: Path, app_with_auth: FastAPI
) -> None:
    upsert_user_and_revoke_sessions(temp_db, "demo", hash_password("s3cret"))
    with TestClient(app_with_auth) as client:
        resp = client.post(
            "/api/v1/auth/login",
            json={"login": "demo", "password": "WRONG"},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Неверный логин или пароль"
        assert settings.session_cookie_name not in client.cookies


def test_login_unknown_user_returns_same_401(
    temp_db: Path, app_with_auth: FastAPI
) -> None:
    with TestClient(app_with_auth) as client:
        resp = client.post(
            "/api/v1/auth/login",
            json={"login": "ghost", "password": "x"},
        )
        assert resp.status_code == 401
        # Анти-enumeration: формулировка та же, что при неверном пароле.
        assert resp.json()["detail"] == "Неверный логин или пароль"


def test_me_without_cookie_returns_anonymous(
    temp_db: Path, app_with_auth: FastAPI
) -> None:
    with TestClient(app_with_auth) as client:
        resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 200
    assert resp.json() == {"login": None}


def test_logout_clears_session_and_cookie(
    temp_db: Path, app_with_auth: FastAPI
) -> None:
    upsert_user_and_revoke_sessions(temp_db, "demo", hash_password("s3cret"))
    with TestClient(app_with_auth) as client:
        _login(client, "demo", "s3cret")
        session_id = client.cookies.get(settings.session_cookie_name)
        assert session_id is not None
        assert select_session(temp_db, session_id) is not None

        resp = client.post("/api/v1/auth/logout")
        assert resp.status_code == 204
        assert resp.content == b""

        assert select_session(temp_db, session_id) is None
        me = client.get("/api/v1/auth/me")
        assert me.json() == {"login": None}


def test_logout_without_cookie_returns_204(
    temp_db: Path, app_with_auth: FastAPI
) -> None:
    """logout идемпотентен — без cookie тоже 204."""

    with TestClient(app_with_auth) as client:
        resp = client.post("/api/v1/auth/logout")
    assert resp.status_code == 204
    assert resp.content == b""


def test_expired_session_treated_as_anonymous(
    temp_db: Path, app_with_auth: FastAPI
) -> None:
    upsert_user_and_revoke_sessions(temp_db, "demo", hash_password("s3cret"))
    now = datetime.now(UTC)
    past = now - timedelta(days=1)
    insert_session(
        temp_db,
        session_id="expired-id",
        user_login="demo",
        created_at=past - timedelta(days=30),
        expires_at=past,
        last_seen_at=past,
    )

    with TestClient(app_with_auth) as client:
        client.cookies.set(settings.session_cookie_name, "expired-id")
        resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 200
    assert resp.json() == {"login": None}

    # Истёкшая запись физически остаётся до lazy purge — проверим это.
    assert select_session(temp_db, "expired-id") is not None
    removed = delete_expired_sessions(temp_db, datetime.now(UTC))
    assert removed == 1
    assert select_session(temp_db, "expired-id") is None


async def test_purge_expired_sessions_helper(temp_db: Path) -> None:
    upsert_user_and_revoke_sessions(temp_db, "demo", hash_password("s3cret"))
    past = datetime.now(UTC) - timedelta(days=1)
    insert_session(
        temp_db,
        session_id="exp",
        user_login="demo",
        created_at=past,
        expires_at=past,
        last_seen_at=past,
    )
    removed = await purge_expired_sessions()
    assert removed == 1
    assert select_session(temp_db, "exp") is None


def test_login_purges_expired_sessions(
    temp_db: Path, app_with_auth: FastAPI
) -> None:
    upsert_user_and_revoke_sessions(temp_db, "demo", hash_password("s3cret"))
    past = datetime.now(UTC) - timedelta(days=1)
    insert_session(
        temp_db,
        session_id="stale",
        user_login="demo",
        created_at=past,
        expires_at=past,
        last_seen_at=past,
    )
    with TestClient(app_with_auth) as client:
        _login(client, "demo", "s3cret")
    # login триггерит purge_expired_sessions() — старая запись исчезла.
    assert select_session(temp_db, "stale") is None


def test_rolling_ttl_extends_session(
    temp_db: Path, app_with_auth: FastAPI
) -> None:
    upsert_user_and_revoke_sessions(temp_db, "demo", hash_password("s3cret"))
    with TestClient(app_with_auth) as client:
        _login(client, "demo", "s3cret")
        session_id = client.cookies.get(settings.session_cookie_name)
        assert session_id is not None
        row_before = select_session(temp_db, session_id)
        assert row_before is not None
        expires_before = datetime.fromisoformat(row_before["expires_at"])
        last_seen_before = datetime.fromisoformat(row_before["last_seen_at"])

        client.get("/api/v1/auth/me")

        row_after = select_session(temp_db, session_id)
        assert row_after is not None
        expires_after = datetime.fromisoformat(row_after["expires_at"])
        last_seen_after = datetime.fromisoformat(row_after["last_seen_at"])
        # Rolling TTL — оба поля сдвинулись вперёд (или хотя бы не назад).
        assert last_seen_after >= last_seen_before
        assert expires_after >= expires_before


def test_upsert_user_and_revoke_sessions_drops_old_sessions(
    temp_db: Path,
) -> None:
    upsert_user_and_revoke_sessions(temp_db, "demo", hash_password("old"))
    now = datetime.now(UTC)
    insert_session(
        temp_db,
        session_id="live",
        user_login="demo",
        created_at=now,
        expires_at=now + timedelta(days=30),
        last_seen_at=now,
    )
    assert select_session(temp_db, "live") is not None

    new_hash = hash_password("new")
    revoked = upsert_user_and_revoke_sessions(temp_db, "demo", new_hash)

    assert revoked == 1
    assert select_session(temp_db, "live") is None
    assert get_user_password_hash(temp_db, "demo") == new_hash


def test_upsert_user_and_revoke_sessions_new_user_returns_zero(
    temp_db: Path,
) -> None:
    revoked = upsert_user_and_revoke_sessions(
        temp_db, "fresh", hash_password("x")
    )
    assert revoked == 0
    assert get_user_password_hash(temp_db, "fresh") is not None
