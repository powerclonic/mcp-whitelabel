# Copilot Instructions for this Repository

## Current project state

Bootstrap phase. The project scaffold exists (`pyproject.toml`, `main.py`, `.python-version`) but no application code has been written yet. The PRD at `tasks/prd-servidor-mcp-governanca-ia.md` is the source of truth for all implementation decisions. The Ralph execution plan lives at `ralph/prd.json` in the sibling repo and tracks story-level progress.

## Commit discipline — semantic and atomic commits

**Every commit must be semantic and atomic. This is non-negotiable.**

### Format

```
<type>(<scope>): <short imperative summary>

[optional body: what changed and why, not how]

[optional footer: breaking changes, closes #issue]
```

### Types

| Type | When to use |
|------|-------------|
| `feat` | New feature or MCP tool |
| `fix` | Bug fix |
| `chore` | Tooling, deps, config (no production logic change) |
| `refactor` | Restructuring without behavior change |
| `test` | Adding or updating tests |
| `docs` | Documentation only |
| `ci` | CI/CD pipeline changes |
| `perf` | Performance improvement |

### Scopes (derived from module boundaries)

`server` · `ingestion` · `vector` · `catalog` · `tools` · `auth` · `adapters` · `config` · `docker` · `docs`

### Atomic commit rules

- **One logical change per commit.** If you can describe it with "and", split it.
- Each commit must leave the codebase in a working, type-checking state.
- Schema/migration changes get their own commit before the logic that uses them.
- Tests for a feature ship in the **same** commit as the feature (or as an immediately following commit if size demands it).
- Never bundle unrelated files in one commit just because they were touched together.

### Examples of good commits

```
feat(server): add FastMCP HTTP server with /health endpoint
chore(docker): add Dockerfile and docker-compose.yml for server and Qdrant
feat(vector): add Qdrant client adapter with upsert and hybrid search
feat(adapters): implement MarkdownAdapter preserving section hierarchy
feat(tools): add search_governance MCP tool with cited chunks response
feat(auth): add OIDC JWT validation middleware
test(auth): add unit tests for scope enforcement per MCP tool
docs: add MkDocs site with architecture and ingestion guides
```

### Pre-commit hygiene checklist

Before staging anything, verify:

1. **Is this file tracked intentionally?** — Run `git status` and question every new file. If it is generated, secret, OS-specific, IDE-specific, or a local volume, it belongs in `.gitignore`, not in the commit.
2. **Secrets check** — Never commit `.env`, `*.pem`, `*.key`, tokens, or passwords. Use `.env.example` with placeholder values for documentation.
3. **`.gitignore` up to date?** — When a new tool, service, or build output is introduced, update `.gitignore` in the **same commit** as the tooling change.
4. **`uv.lock` is always tracked** — It ensures reproducible builds. Never add it to `.gitignore`.
5. **Volume/data directories are never tracked** — `data/`, `qdrant_storage/`, `docker/volumes/` and similar runtime-generated paths must be in `.gitignore`.

### Examples of bad commits (do not do these)

```
wip                          # not semantic
fix stuff                    # not descriptive
feat: add all compliance tools and auth and docker  # not atomic
```

## Build, test, and lint commands

No runnable commands exist yet. When the first setup is added:

- All commands must be centralized — Makefile targets or `pyproject.toml` `[tool.scripts]` section.
- Expose these targets consistently: `make install`, `make dev`, `make test`, `make lint`, `make typecheck`, `make build`.
- Add a **single-test** pattern immediately: `make test TEST=path/to/test_file.py::test_name`.
- CI must run `typecheck` and `test` as separate, independent steps.

## Tech stack (closed decisions from PRD)

| Concern | Decision |
|---------|----------|
| Language / runtime | Python 3.12+ |
| MCP framework | FastMCP (HTTP transport) |
| Package manager | `uv` — only `uv`; never `pip install` directly |
| Vector database | Qdrant |
| Embedding model | Self-hosted BGE-M3 (or equivalent), dedicated container |
| Local infra | Docker Compose |
| Auth | OIDC Client Credentials + JWT |
| Authorization | RBAC by scope per MCP tool |
| Documentation | README + MkDocs (required deliverables) |
| Confluence ingestion | Export + ingest (no live crawler) |

## Module boundaries

Keep these boundaries clean — cross-boundary calls must go through defined interfaces:

```
src/
  server/       # FastMCP app, routing, middleware (auth, error handling)
  domain/       # Business logic: catalog, compliance rules, Q&A orchestration
  adapters/     # Source adapters: Markdown, PDF, Git, Web, Confluence
  vector/       # Qdrant client, embedding client, chunking strategies
  catalog/      # Library/version/standards data models and persistence
  config/       # Settings, env var loading (pydantic-settings)
```

## High-level architecture

Two product surfaces sharing one governance knowledge base:

1. **Agent-facing MCP surface**
   - `search_governance(query, domain?)` — natural language Q&A with cited sources
   - `check_library_compliance(name, version)` — validates against approved catalog
   - `check_code_compliance(snippet, domain?)` — evaluates against indexed standards
   - `check_infra_compliance(definition, type?)` — validates infra against policies
   - All responses must include evidence (chunk IDs, policy version, effective date)

2. **Maintainer-facing ingestion surface**
   - Adapters: Markdown, PDF, Git, Web, Confluence export
   - Unified `IngestPipeline`: adapt → chunk → embed → upsert to Qdrant
   - Incremental mode: skip chunks with matching content hash
   - Errors are logged per item; pipeline continues for remaining items

## Key conventions — never break these

1. **Governance traceability is mandatory**
   - Every agent answer must include `cited_chunks` with `chunk_id`, `origin`, `policy_version`.

2. **No silent fallback**
   - Missing evidence → return `{found: false, message: "insufficient evidence"}`. Never hallucinate policy.

3. **Compliance statuses are normalized**
   - Always one of: `compliant` | `warning` | `non_compliant`. No other values.

4. **Metadata-first ingestion**
   - Every chunk carries: `origin`, `source_type`, `version_ref`, `timestamp`, `domain`.

5. **`uv` only**
   - Never add dependencies with plain `pip`. Always `uv add <package>`.

6. **Validate lib/framework choices with docs**
   - Before committing to any external library, verify against current documentation (Context7 or official docs). Training-data knowledge of APIs is not sufficient.
