"""MCP tool registration.

All four governance tools are registered onto the FastMCP instance here
via register_tools(mcp).  Dependencies (Qdrant, Embedding, Catalog) are
injected at call time through module-level factories that can be replaced
in tests.
"""
from __future__ import annotations

import re
from typing import Any

from fastmcp import FastMCP

from src.catalog.models import LibraryStatus
from src.catalog.repository import InMemoryCatalogRepository
from src.config.settings import settings
from src.vector.embedding_client import EmbeddingClient, EmbeddingError
from src.vector.qdrant_client import QdrantAdapter

MIN_SCORE: float = 0.5

# Module-level singletons — replaceable in tests via monkey-patching.
_qdrant: QdrantAdapter | None = None
_embedding: EmbeddingClient | None = None
_catalog: InMemoryCatalogRepository | None = None


def _get_qdrant() -> QdrantAdapter:
    global _qdrant
    if _qdrant is None:
        _qdrant = QdrantAdapter()
    return _qdrant


def _get_embedding() -> EmbeddingClient:
    global _embedding
    if _embedding is None:
        _embedding = EmbeddingClient()
    return _embedding


def _get_catalog() -> InMemoryCatalogRepository:
    global _catalog
    if _catalog is None:
        _catalog = InMemoryCatalogRepository()
    return _catalog


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _normalize_cited_chunks(hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "chunk_id": h.get("chunk_id", ""),
            "origin": h.get("origin", ""),
            "policy_version": h.get("policy_version") or h.get("version_ref", ""),
        }
        for h in hits
        if h.get("score", 0.0) >= MIN_SCORE
    ]


def _insufficient_evidence() -> dict[str, Any]:
    return {
        "found": False,
        "status": "warning",
        "justification": "insufficient evidence",
        "cited_chunks": [],
    }


def _embed_safe(texts: list[str], embedding: EmbeddingClient) -> list[list[float]] | None:
    try:
        return embedding.embed(texts)
    except EmbeddingError:
        return None


# ---------------------------------------------------------------------------
# Standalone tool implementations (testable without FastMCP runtime)
# ---------------------------------------------------------------------------

def search_governance(
    query: str,
    domain: str | None,
    qdrant: QdrantAdapter,
    embedding: EmbeddingClient,
) -> dict[str, Any]:
    vectors = _embed_safe([query], embedding)
    if vectors is None:
        return {**_insufficient_evidence(), "results": []}

    filters = {"domain": domain} if domain else None
    hits = qdrant.search(settings.qdrant_collection, vectors[0], filters=filters, top_k=5)
    above_threshold = [h for h in hits if h.get("score", 0.0) >= MIN_SCORE]

    if not above_threshold:
        return {**_insufficient_evidence(), "results": []}

    cited = _normalize_cited_chunks(above_threshold)
    return {
        "found": True,
        "results": [
            {
                "content": h.get("content", ""),
                "score": h.get("score", 0.0),
                "chunk_id": h.get("chunk_id", ""),
                "origin": h.get("origin", ""),
                "policy_version": h.get("policy_version") or h.get("version_ref", ""),
            }
            for h in above_threshold
        ],
        "cited_chunks": cited,
    }


def check_library_compliance(
    name: str,
    version: str,
    qdrant: QdrantAdapter,
    embedding: EmbeddingClient,
    catalog: InMemoryCatalogRepository,
) -> dict[str, Any]:
    entry = catalog.get_library(name, version)

    if entry is not None:
        catalog_citation = {
            "chunk_id": f"catalog:{name}:{version}",
            "origin": "catalog",
            "policy_version": str(entry.effective_date),
        }
        status_map = {
            LibraryStatus.approved: "compliant",
            LibraryStatus.restricted: "warning",
            LibraryStatus.forbidden: "non_compliant",
        }
        return {
            "found": True,
            "status": status_map[entry.status],
            "justification": entry.reason,
            "cited_chunks": [catalog_citation],
        }

    vectors = _embed_safe([f"{name} {version}"], embedding)
    if vectors is None:
        return _insufficient_evidence()

    hits = qdrant.search(settings.qdrant_collection, vectors[0], filters=None, top_k=5)
    relevant = [h for h in hits if h.get("score", 0.0) >= MIN_SCORE]
    if not relevant:
        return _insufficient_evidence()

    cited = _normalize_cited_chunks(relevant)
    return {
        "found": True,
        "status": "warning",
        "justification": (
            f"Library {name}=={version} not in approved catalog; "
            "policy evidence found — manual review recommended."
        ),
        "cited_chunks": cited,
    }


def check_code_compliance(
    snippet: str,
    domain: str | None,
    qdrant: QdrantAdapter,
    embedding: EmbeddingClient,
) -> dict[str, Any]:
    vectors = _embed_safe([snippet], embedding)
    if vectors is None:
        return _insufficient_evidence()

    filters = {"domain": domain} if domain else None
    hits = qdrant.search(settings.qdrant_collection, vectors[0], filters=filters, top_k=5)
    relevant = [h for h in hits if h.get("score", 0.0) >= MIN_SCORE]
    if not relevant:
        return _insufficient_evidence()

    cited = _normalize_cited_chunks(relevant)
    return {
        "found": True,
        "status": "warning",
        "justification": (
            "Relevant policy evidence found. Human review required to "
            "determine compliance status against the cited standards."
        ),
        "cited_chunks": cited,
    }


def check_infra_compliance(
    definition: str,
    type: str | None,
    qdrant: QdrantAdapter,
    embedding: EmbeddingClient,
) -> dict[str, Any]:
    violations = _detect_infra_violations(definition, type)

    vectors = _embed_safe([definition], embedding)
    hits: list[dict[str, Any]] = []
    if vectors is not None:
        hits = qdrant.search(settings.qdrant_collection, vectors[0], filters=None, top_k=5)
    relevant = [h for h in hits if h.get("score", 0.0) >= MIN_SCORE]

    if violations:
        cited = _normalize_cited_chunks(relevant)
        return {
            "found": True,
            "status": "non_compliant",
            "justification": "; ".join(violations),
            "cited_chunks": cited,
        }

    if not relevant:
        return _insufficient_evidence()

    cited = _normalize_cited_chunks(relevant)
    return {
        "found": True,
        "status": "warning",
        "justification": (
            "No deterministic violations detected. "
            "Policy evidence found — human review recommended."
        ),
        "cited_chunks": cited,
    }


def _detect_infra_violations(definition: str, type: str | None) -> list[str]:
    violations: list[str] = []
    hint = (type or "").lower()

    is_dockerfile = hint == "dockerfile" or bool(re.search(r"^FROM\s", definition, re.MULTILINE))
    if is_dockerfile:
        if re.search(r"^FROM\s+\S+:latest\b", definition, re.MULTILINE | re.IGNORECASE):
            violations.append("Unpinned base image: 'latest' tag is not reproducible")
        # Unpinned: no `:tag` and no `@digest`
        for from_match in re.finditer(r"^FROM\s+(\S+)", definition, re.MULTILINE):
            image = from_match.group(1)
            if ":" not in image and "@" not in image:
                violations.append("Unpinned base image: no tag or digest specified")
        for port_match in re.finditer(r"^EXPOSE\s+(\d+)", definition, re.MULTILINE):
            port = int(port_match.group(1))
            if port < 1024:
                violations.append(f"Privileged port exposed: {port}")

    secret_patterns = [
        (r"(?i)(password|secret|token|api_key)\s*=\s*['\"]?\S{8,}", "Possible hardcoded secret"),
        (r"(?i)env\s+\w*(password|secret|token|key)\w*=[^${\s]\S+", "ENV directive with hardcoded secret"),
    ]
    for pattern, message in secret_patterns:
        if re.search(pattern, definition):
            violations.append(message)

    return violations


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------

def register_tools(mcp: FastMCP) -> None:
    """Register all governance MCP tools onto *mcp*."""

    @mcp.tool()
    def search_governance_tool(
        query: str,
        domain: str | None = None,
    ) -> dict[str, Any]:
        """Natural-language governance Q&A with cited sources.

        Required scope: query:read
        """
        return search_governance(query, domain, _get_qdrant(), _get_embedding())

    @mcp.tool()
    def check_library_compliance_tool(
        name: str,
        version: str,
    ) -> dict[str, Any]:
        """Check if a library version is approved for use.

        Catalog takes precedence over vector search.
        Required scope: compliance:read
        """
        return check_library_compliance(name, version, _get_qdrant(), _get_embedding(), _get_catalog())

    @mcp.tool()
    def check_code_compliance_tool(
        snippet: str,
        domain: str | None = None,
    ) -> dict[str, Any]:
        """Check a code snippet against indexed coding standards.

        Only cites retrieved evidence — never invents rules.
        Required scope: compliance:read
        """
        return check_code_compliance(snippet, domain, _get_qdrant(), _get_embedding())

    @mcp.tool()
    def check_infra_compliance_tool(
        definition: str,
        type: str | None = None,
    ) -> dict[str, Any]:
        """Check an infrastructure definition against indexed policies.

        Detects common violations (unpinned base images, exposed ports,
        hardcoded secrets) and cross-references with retrieved evidence.
        Required scope: compliance:read
        """
        return check_infra_compliance(definition, type, _get_qdrant(), _get_embedding())

