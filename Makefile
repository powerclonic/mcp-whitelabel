.PHONY: install dev test lint typecheck build docs new-ingestion seed

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

## Ingestion helpers
## Usage: make new-ingestion NAME=ingest_container_policy [ADAPTER=pdf] [DOMAIN=compliance]
new-ingestion:
	@test -n "$(NAME)" || (echo "Usage: make new-ingestion NAME=<script_name>"; exit 1)
	uv run python scripts/new_ingestion.py $(NAME) \
		$(if $(ADAPTER),--adapter $(ADAPTER)) \
		$(if $(DOMAIN),--domain $(DOMAIN))

## Run an ingestion script inside the server container (recommended for consistency).
## Usage: make ingest SCRIPT=scripts/ingestion/seed_all.py [FORCE=1]
## Usage: make ingest SCRIPT=scripts/ingestion/ingest_my_policy.py
ingest:
	@test -n "$(SCRIPT)" || (echo "Usage: make ingest SCRIPT=scripts/ingestion/<name>.py"; exit 1)
	docker compose run --rm \
		-v "$(PWD)/scripts:/app/scripts:ro" \
		-v "$(PWD)/policies:/app/policies:ro" \
		server uv run python $(SCRIPT) $(if $(FORCE),--force)

## Run the full seed script inside the container (first-time bootstrap)
## Usage: make seed [FORCE=1]
seed:
	docker compose run --rm \
		-v "$(PWD)/scripts:/app/scripts:ro" \
		server uv run python scripts/ingestion/seed_all.py $(if $(FORCE),--force)
