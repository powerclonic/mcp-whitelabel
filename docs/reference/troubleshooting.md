# Troubleshooting

## Server fails to start: "No module named 'src'"

Ensure you installed with `uv sync` and are running via `make dev` or `uv run`:

```bash
uv sync
make dev
```

## OIDC token rejected: "Failed to fetch JWKS"

- Verify `OIDC_ISSUER` in `.env` points to a reachable OIDC provider.
- Check network connectivity from the server container to the issuer.
- The JWKS endpoint is `<issuer>/.well-known/jwks.json`.

## Vector search returns no results

1. Confirm ingestion ran successfully: check `PipelineResult.ingested > 0`.
2. Verify Qdrant is running: `curl http://localhost:6333/healthz`.
3. Confirm the embedding service is reachable: `curl http://localhost:8001/embed`.
4. Check the collection exists: `curl http://localhost:6333/collections/governance`.

## Typecheck failures after adding code

Run:

```bash
make typecheck
```

Ensure all new functions have type annotations.  See `mypy.ini` / `pyproject.toml` for mypy config.

## Tests failing after dependency update

```bash
uv sync
make test
```

Never use `pip install` — always use `uv add <package>` to add new dependencies.
