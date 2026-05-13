# Architecture Overview

## System Components

```
┌─────────────────────────────────────────────────────────────┐
│  Agent / LLM client                                         │
│                                                             │
│  MCP tool calls (HTTP transport)                            │
└───────────────────────────┬─────────────────────────────────┘
                            │ Bearer token (OIDC)
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  mcp-governance-server  (FastMCP + Starlette)               │
│                                                             │
│  ┌──────────────┐  ┌────────────────────────────────────┐  │
│  │  /health     │  │  MCP tools (registered on FastMCP)  │  │
│  └──────────────┘  │  - search_governance                 │  │
│                    │  - check_library_compliance          │  │
│  ┌──────────────┐  │  - check_code_compliance            │  │
│  │  Auth layer  │  │  - check_infra_compliance           │  │
│  │  OIDC JWT    │  └────────────────────────────────────┘  │
│  │  + RBAC      │                                          │
│  └──────────────┘                                          │
└───────────────────────────┬─────────────────────────────────┘
                            │
               ┌────────────┴────────────┐
               ▼                         ▼
  ┌─────────────────────┐    ┌─────────────────────────┐
  │  Qdrant             │    │  Embedding service      │
  │  (vector store)     │    │  BGE-M3 (HTTP API)      │
  └─────────────────────┘    └─────────────────────────┘
```

## Module Map

| Module | Responsibility |
|---|---|
| `src/server/` | FastMCP app, routing, middleware |
| `src/domain/` | IngestPipeline business logic |
| `src/adapters/` | Source adapters (Markdown, PDF, Git, Web, Confluence) |
| `src/vector/` | Qdrant client, EmbeddingClient, chunking strategies |
| `src/catalog/` | Library/standard models and repository |
| `src/config/` | Settings (pydantic-settings, `.env`) |
| `src/auth/` | OIDC JWT validation, RBAC scope enforcement |

## Data Flow — Ingestion

```
Source (file / URL / Git repo)
  └─ Adapter.ingest()          → List[Chunk]
       └─ IngestPipeline.run()
            ├─ EmbeddingClient.embed()    → vectors
            ├─ QdrantAdapter.upsert()     → stored points
            └─ PipelineResult(ingested, skipped, errors)
```

## Data Flow — MCP Tool Call

```
Agent calls tool (e.g. search_governance)
  ├─ OIDC JWT validated by JWKSCache
  ├─ Scope checked (e.g. query:read)
  ├─ EmbeddingClient.embed([query])    → query vector
  ├─ QdrantAdapter.search()            → top-k chunks
  └─ Response: {found, answer, cited_chunks}
```

## Key Design Decisions

- **No hallucination policy**: tools return `{found: false, status: "warning", justification: "insufficient evidence"}` when evidence is below the 0.5 score threshold.
- **Governance traceability**: every answer includes `cited_chunks` with `chunk_id`, `origin`, `policy_version`.
- **Incremental ingestion**: chunks with matching `content_hash` are skipped; pipeline continues on per-item errors.
- **RBAC scopes**: `query:read` for search; `compliance:read` for all compliance tools.
