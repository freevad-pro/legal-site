from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.auth import get_current_user, hash_password, verify_password
from app.config import settings
from app.db import get_user_password_hash, init_db, upsert_user


@pytest.fixture
def temp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    db_path = tmp_path / "users.sqlite"
    init_db(db_path)
    monkeypatch.setattr(settings, "database_path", db_path)
    yield db_path


@pytest.fixture
def app_with_auth() -> FastAPI:
    app = FastAPI()

    @app.get("/protected")
    def protected(login: str = Depends(get_current_user)) -> dict[str, str]:
        return {"login": login}

    return app


def test_init_db_creates_users_table(tmp_path: Path) -> None:
    db_path = tmp_path / "users.sqlite"
    init_db(db_path)
    assert db_path.exists()
    # повторный init — без падения
    init_db(db_path)
    assert get_user_password_hash(db_path, "missing") is None


def test_upsert_user_inserts_and_updates(temp_db: Path) -> None:
    upsert_user(temp_db, "demo", "hash-1")
    assert get_user_password_hash(temp_db, "demo") == "hash-1"
    upsert_user(temp_db, "demo", "hash-2")
    assert get_user_password_hash(temp_db, "demo") == "hash-2"


def test_hash_and_verify_roundtrip() -> None:
    hashed = hash_password("s3cret")
    assert verify_password("s3cret", hashed) is True
    assert verify_password("wrong", hashed) is False


def test_verify_password_handles_garbage_hash() -> None:
    assert verify_password("any", "not-a-bcrypt-hash") is False


def test_protected_endpoint_happy_path(
    temp_db: Path, app_with_auth: FastAPI
) -> None:
    upsert_user(temp_db, "demo", hash_password("s3cret"))
    with TestClient(app_with_auth) as client:
        resp = client.get("/protected", auth=("demo", "s3cret"))
    assert resp.status_code == 200
    assert resp.json() == {"login": "demo"}


def test_protected_endpoint_wrong_password(
    temp_db: Path, app_with_auth: FastAPI
) -> None:
    upsert_user(temp_db, "demo", hash_password("s3cret"))
    with TestClient(app_with_auth) as client:
        resp = client.get("/protected", auth=("demo", "WRONG"))
    assert resp.status_code == 401
    assert resp.headers["WWW-Authenticate"] == 'Basic realm="Legal_site"'


def test_protected_endpoint_unknown_user(
    temp_db: Path, app_with_auth: FastAPI
) -> None:
    with TestClient(app_with_auth) as client:
        resp = client.get("/protected", auth=("ghost", "x"))
    assert resp.status_code == 401
    assert resp.headers["WWW-Authenticate"] == 'Basic realm="Legal_site"'


def test_protected_endpoint_no_credentials(
    temp_db: Path, app_with_auth: FastAPI
) -> None:
    with TestClient(app_with_auth) as client:
        resp = client.get("/protected")
    assert resp.status_code == 401
    assert resp.headers["WWW-Authenticate"] == 'Basic realm="Legal_site"'
