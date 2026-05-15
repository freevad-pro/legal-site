# На Windows требует GNU Make: либо WSL, либо `choco install make`.

.PHONY: install dev lint fmt test corpus scan user build-frontend dev-frontend

install:
	uv sync

dev:
	uv run watchfiles --filter python "uvicorn app.main:app --host 127.0.0.1 --port 8000" app

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

# Frontend (Next.js 15 + Tailwind, static export).
# Требует pnpm; см. README про установку через `npm install -g pnpm@9.15.4`.

build-frontend:
	cd frontend && pnpm install && pnpm build

dev-frontend:
	cd frontend && pnpm dev

lint-frontend:
	cd frontend && pnpm lint && pnpm typecheck
