# На Windows требует GNU Make: либо WSL, либо `choco install make`.

.PHONY: install dev lint fmt test corpus scan user

install:
	uv sync

dev:
	uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

lint:
	uv run ruff check .
	uv run mypy

fmt:
	uv run ruff format .
	uv run ruff check --fix .

test:
	uv run pytest -q

corpus:
	uv run python tools/rebuild_index.py

scan:
	uv run python -m app.scan $(URL)

user:
	uv run python -m tools.create_user $(LOGIN)
