.PHONY: dev test lint migrate seed up down

dev:
	uv run fastapi dev src/api.py

test:
	uv run pytest -q

lint:
	uv run ruff check src tests

migrate:
	uv run alembic upgrade head

seed:
	uv run python -m src.seed && uv run python -m src.seed_reviews

up:
	docker compose up --build

down:
	docker compose down
