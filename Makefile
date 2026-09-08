SHELL := /bin/bash

.PHONY: setup db-up db-down backend frontend lint format test check

setup:
	@test -f .env || cp .env.example .env
	@test -f frontend/.env || cp frontend/.env.example frontend/.env
	cd backend && uv sync
	cd frontend && npm install

db-up:
	docker compose up -d postgres

db-down:
	docker compose down

backend:
	cd backend && uv run uvicorn --app-dir src app.main:app --reload --host 0.0.0.0 --port 8000

frontend:
	cd frontend && npm run dev -- --host 0.0.0.0

lint:
	cd backend && uv run ruff check .
	cd frontend && npm run lint

format:
	cd backend && uv run ruff format .

test:
	cd backend && uv run pytest
	cd frontend && npm run test

check:
	cd backend && uv run ruff check .
	cd backend && uv run ruff format --check .
	cd backend && uv run pytest
	cd frontend && npm run lint
	cd frontend && npm run test
	cd frontend && npm run build
	openspec validate --all --strict
