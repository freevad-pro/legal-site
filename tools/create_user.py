"""CLI: создать или обновить пароль пользователя.

Запуск: `uv run python -m tools.create_user <login>` или `make user LOGIN=<login>`.
Пароль вводится интерактивно через `getpass` (не виден в shell-history).
"""

from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

from app.auth import hash_password
from app.config import settings
from app.db import get_user_password_hash, init_db, upsert_user


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tools.create_user",
        description="Создаёт пользователя или обновляет ему пароль.",
    )
    parser.add_argument("login", help="Логин пользователя")
    parser.add_argument(
        "--database-path",
        type=Path,
        default=settings.database_path,
        help=f"Путь к SQLite-файлу (по умолчанию: {settings.database_path})",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    db_path: Path = args.database_path
    login: str = args.login

    init_db(db_path)

    existed = get_user_password_hash(db_path, login) is not None
    action = "обновляем пароль" if existed else "создаём пользователя"
    print(f"{action}: {login}", file=sys.stderr)

    password = getpass.getpass("Пароль: ")
    confirm = getpass.getpass("Повторите пароль: ")
    if password != confirm:
        print("error: пароли не совпадают", file=sys.stderr)
        return 1
    if not password:
        print("error: пустой пароль", file=sys.stderr)
        return 1

    upsert_user(db_path, login, hash_password(password))
    print(f"ok: пользователь {login!r} {'обновлён' if existed else 'создан'}", file=sys.stderr)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
