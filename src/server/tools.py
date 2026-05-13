"""MCP tool registration.

All four governance tools are registered onto the FastMCP instance here
via register_tools(mcp).  Dependencies (RetrievalPipeline, Catalog) are
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
from src.vector.embedding_client import EmbeddingClient
from src.vector.qdrant_client import QdrantAdapter
from src.vector.rerank_client import RerankClient
from src.vector.retrieval_pipeline import RetrievalPipeline

MIN_SCORE: float = 0.5

# Module-level singletons — replaceable in tests via monkey-patching.
_pipeline: RetrievalPipeline | None = None
_catalog: InMemoryCatalogRepository | None = None


def _get_pipeline() -> RetrievalPipeline:
    global _pipeline
    if _pipeline is None:
        reranker = RerankClient() if settings.reranker_enabled else None
        _pipeline = RetrievalPipeline(
            qdrant=QdrantAdapter(),
            embedding_client=EmbeddingClient(),
            rerank_client=reranker,
        )
    return _pipeline


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
    ]


def _insufficient_evidence() -> dict[str, Any]:
    return {
        "found": False,
        "status": "warning",
        "justification": "insufficient evidence",
        "cited_chunks": [],
    }


# ---------------------------------------------------------------------------
# Standalone tool implementations (testable without FastMCP runtime)
# ---------------------------------------------------------------------------

def search_governance(
    query: str,
    domain: str | None,
    pipeline: RetrievalPipeline,
) -> dict[str, Any]:
    filters = {"domain": domain} if domain else None
    hits = pipeline.retrieve(query, settings.qdrant_collection, filters=filters)

    if not hits:
        return {**_insufficient_evidence(), "results": []}

    cited = _normalize_cited_chunks(hits)
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
            for h in hits
        ],
        "cited_chunks": cited,
    }


def check_library_compliance(
    name: str,
    version: str,
    pipeline: RetrievalPipeline,
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

    hits = pipeline.retrieve(f"{name} {version}", settings.qdrant_collection)
    if not hits:
        return _insufficient_evidence()

    cited = _normalize_cited_chunks(hits)
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
    pipeline: RetrievalPipeline,
) -> dict[str, Any]:
    filters = {"domain": domain} if domain else None
    hits = pipeline.retrieve(snippet, settings.qdrant_collection, filters=filters)
    if not hits:
        return _insufficient_evidence()

    cited = _normalize_cited_chunks(hits)
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
    pipeline: RetrievalPipeline,
) -> dict[str, Any]:
    violations = _detect_infra_violations(definition, type)

    hits = pipeline.retrieve(definition, settings.qdrant_collection)

    if violations:
        cited = _normalize_cited_chunks(hits)
        return {
            "found": True,
            "status": "non_compliant",
            "justification": "; ".join(violations),
            "cited_chunks": cited,
        }

    if not hits:
        return _insufficient_evidence()

    cited = _normalize_cited_chunks(hits)
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
        return search_governance(query, domain, _get_pipeline())

    @mcp.tool()
    def check_library_compliance_tool(
        name: str,
        version: str,
    ) -> dict[str, Any]:
        """Check if a library version is approved for use.

        Catalog takes precedence over vector search.
        Required scope: compliance:read
        """
        return check_library_compliance(name, version, _get_pipeline(), _get_catalog())

    @mcp.tool()
    def check_code_compliance_tool(
        snippet: str,
        domain: str | None = None,
    ) -> dict[str, Any]:
        """Check a code snippet against indexed coding standards.

        Only cites retrieved evidence — never invents rules.
        Required scope: compliance:read
        """
        return check_code_compliance(snippet, domain, _get_pipeline())

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
        return check_infra_compliance(definition, type, _get_pipeline())

