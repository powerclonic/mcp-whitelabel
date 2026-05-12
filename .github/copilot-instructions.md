# Copilot Instructions for this Repository

## Current project state

This repository currently contains a product requirements document at `tasks/prd-servidor-mcp-governanca-ia.md` and is in planning/bootstrap phase. Treat that PRD as the source of truth for implementation direction until code/docs are added.

## Build, test, and lint commands

No executable build/test/lint commands are committed yet.

When adding the first runnable setup, keep commands centralized and consistent with the PRD constraints:
- Python project managed with `uv`
- Container workflow via Docker Compose
- Type/lint/test commands exposed in a predictable place (Makefile, `pyproject.toml` scripts, or documented command table in README)

Also add a documented **single-test** command pattern as soon as the test framework is introduced.

## High-level architecture (from PRD)

The intended system has two major product surfaces sharing a single governance knowledge base:

1. **Agent-facing MCP surface**
   - Natural-language Q&A about approved libraries, versions, and coding patterns
   - MCP tools for compliance checks on:
     - dependencies/libraries
     - code standards
     - infrastructure definitions
   - Responses must be traceable to source material/policy versions

2. **Maintainer-facing ingestion/management surface**
   - Ingest and manage technical knowledge from:
     - Markdown
     - PDF
     - Git repositories
     - Web/Confluence pages
   - Normalize content into chunks with metadata
   - Generate embeddings and store/retrieve via vector database

Cross-cutting architecture expectations:
- Python MCP HTTP runtime
- Clear module boundaries between MCP runtime, domain logic, and adapters/integrations
- Incremental ingestion and selective reindex support
- Docker Compose as default local deployment path
- Documentation maintained in README + MkDocs

## Key conventions to preserve

These conventions come from the existing PRD and should be treated as repository standards during implementation:

1. **Governance traceability is mandatory**
   - Agent answers should include supporting source/policy context (not opaque answers).

2. **Compliance outputs use normalized statuses**
   - Use consistent status values for checks: `compliant`, `warning`, `non_compliant`.

3. **No silent fallback when evidence is missing**
   - If policy evidence is unavailable, return an explicit “insufficient evidence / not found” style result.

4. **Metadata-first ingestion**
   - Persist source metadata (origin, version/reference, timestamps) with indexed content to support audits and reproducibility.

5. **Dependency/tooling constraints**
   - `uv` is the package/environment manager standard.
   - Docker Compose is the baseline runtime/deployment path.
   - Documentation is a required deliverable (README + MkDocs).

6. **Library/framework choices should be doc-validated**
   - Decisions involving external libs/frameworks should be verified against up-to-date documentation (per PRD: Context7-backed lookup).
