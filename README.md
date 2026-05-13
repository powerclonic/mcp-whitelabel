# MCP Governance Server

An internal [Model Context Protocol (MCP)](https://modelcontextprotocol.io) HTTP server that gives AI agents governed access to your organization's policies, standards, and approved library catalog.

## Features

- **Q&A with citations** — `search_governance` returns answers grounded in indexed policy documents
- **Library compliance** — `check_library_compliance` validates a library version against an approved catalog
- **Code compliance** — `check_code_compliance` evaluates code snippets against indexed standards
- **Infra compliance** — `check_infra_compliance` validates Dockerfiles / Compose / Terraform against policies
- **Multi-source ingestion** — Markdown, PDF, Git, Web adapters
- **OIDC authentication** — RS256 JWT validation with JWKS caching
- **RBAC** — `query:read` / `compliance:read` scope enforcement per tool

## Quick Start

### Prerequisites

- [uv](https://docs.astral.sh/uv/) ≥ 0.4
- [Docker](https://docs.docker.com/) + Docker Compose

### 1. Clone and install dependencies

```bash
git clone <repo-url> mcp-governance-server
cd mcp-governance-server
uv sync
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env — set OIDC_ISSUER, OIDC_AUDIENCE, and service URLs
```

### 3. Start the stack

```bash
docker compose up -d
```

This starts:

| Service | URL |
|---|---|
| MCP governance server | `http://localhost:8000` |
| Qdrant vector database | `http://localhost:6333` |
| Embedding service (BGE-M3) | `http://localhost:8001` |

### 4. Verify health

```bash
curl http://localhost:8000/health
# {"status": "ok"}
```

### 5. Run tests

```bash
make test
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `HOST` | `0.0.0.0` | Server bind address |
| `PORT` | `8000` | Server port |
| `QDRANT_HOST` | `localhost` | Qdrant hostname |
| `QDRANT_PORT` | `6333` | Qdrant port |
| `QDRANT_COLLECTION` | `governance` | Qdrant collection name |
| `QDRANT_VECTOR_SIZE` | `1024` | Embedding dimension (must match model) |
| `EMBEDDING_URL` | `http://localhost:8001/embed` | Embedding service URL |
| `EMBEDDING_MODEL` | `BAAI/bge-m3` | Model identifier |
| `CHUNK_MAX_SIZE` | `512` | Maximum tokens per chunk |
| `CHUNK_OVERLAP` | `64` | Token overlap between chunks |
| `OIDC_ISSUER` | `https://auth.example.com` | OIDC provider issuer URL |
| `OIDC_AUDIENCE` | `mcp-governance` | Expected JWT audience |
| `JWKS_CACHE_TTL_SECONDS` | `3600` | How long to cache JWKS keys |

See `.env.example` for a fully annotated reference.

## Development

```bash
make install      # install all deps
make dev          # start server with hot reload
make test         # run test suite
make lint         # ruff check + format check
make typecheck    # mypy
make build        # docker build
make docs         # mkdocs serve (local docs site)
```

## Documentation

Full MkDocs documentation covers architecture, ingestion guides, MCP tool reference, retention policy, and troubleshooting.

```bash
make docs
# → http://127.0.0.1:8000
```

- [Architecture Overview](docs/architecture/overview.md)
- [Ingestion Guide](docs/ingestion/overview.md)
- [MCP Tool Reference](docs/tools/reference.md)
- [Retention Policy & Snapshots](docs/operations/retention.md)
- [Troubleshooting](docs/reference/troubleshooting.md)
