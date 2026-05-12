.PHONY: install dev test lint typecheck build docs

install:
	uv sync

dev:
	uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload

test:
	uv run pytest tests/ -v

test-one:
	uv run pytest $(TEST) -v

lint:
	uv run ruff check src/ tests/
	uv run ruff format --check src/ tests/

typecheck:
	uv run mypy src/ --ignore-missing-imports

build:
	docker build -t mcp-governance-server .

docs:
	uv run mkdocs serve
