"""Tests for MCP tool functions (search_governance, check_*_compliance)."""
from __future__ import annotations

from datetime import date
from typing import Any
from unittest.mock import MagicMock

from src.catalog.models import LibraryEntry, LibraryStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hit(score: float = 0.9, chunk_id: str = "c1", origin: str = "policy.md") -> dict[str, Any]:
    return {"score": score, "chunk_id": chunk_id, "origin": origin, "content": "policy text", "version_ref": "v1"}


def _make_entry(status: LibraryStatus = LibraryStatus.approved) -> LibraryEntry:
    return LibraryEntry(
        name="requests",
        version="2.31.0",
        status=status,
        reason="Approved for use",
        effective_date=date(2024, 1, 1),
        updated_by="admin",
    )


def _mock_pipeline(hits: list[dict[str, Any]] | None = None) -> MagicMock:
    """Build a MagicMock that quacks like RetrievalPipeline."""
    pipeline = MagicMock()
    pipeline.retrieve.return_value = hits if hits is not None else []
    return pipeline


# ---------------------------------------------------------------------------
# search_governance
# ---------------------------------------------------------------------------

class TestSearchGovernance:
    def _call(
        self,
        mock_pipeline: MagicMock,
        query: str = "security policy",
        domain: str | None = None,
    ) -> dict[str, Any]:
        from src.server.tools import search_governance
        return search_governance(query, domain, mock_pipeline)

    def test_returns_results_when_hits_found(self) -> None:
        result = self._call(_mock_pipeline([_hit()]))

        assert result["found"] is True
        assert len(result["results"]) == 1
        assert len(result["cited_chunks"]) == 1
        assert result["cited_chunks"][0]["chunk_id"] == "c1"

    def test_returns_insufficient_evidence_when_no_hits(self) -> None:
        result = self._call(_mock_pipeline([]))

        assert result["found"] is False
        assert result["status"] == "warning"
        assert "insufficient evidence" in result["justification"]

    def test_domain_filter_passed_to_pipeline(self) -> None:
        pipeline = _mock_pipeline([_hit()])
        self._call(pipeline, domain="security")

        call_kwargs = pipeline.retrieve.call_args
        assert call_kwargs.kwargs.get("filters") == {"domain": "security"}

    def test_no_domain_passes_none_filter(self) -> None:
        pipeline = _mock_pipeline([_hit()])
        self._call(pipeline, domain=None)

        call_kwargs = pipeline.retrieve.call_args
        assert call_kwargs.kwargs.get("filters") is None


# ---------------------------------------------------------------------------
# check_library_compliance
# ---------------------------------------------------------------------------

class TestCheckLibraryCompliance:
    def _call(
        self,
        mock_pipeline: MagicMock,
        mock_catalog: MagicMock,
        name: str = "requests",
        version: str = "2.31.0",
    ) -> dict[str, Any]:
        from src.server.tools import check_library_compliance
        return check_library_compliance(name, version, mock_pipeline, mock_catalog)

    def test_catalog_approved_returns_compliant(self) -> None:
        mock_catalog = MagicMock()
        mock_catalog.get_library.return_value = _make_entry(LibraryStatus.approved)

        result = self._call(_mock_pipeline(), mock_catalog)

        assert result["status"] == "compliant"
        assert result["found"] is True
        assert result["cited_chunks"][0]["origin"] == "catalog"

    def test_catalog_forbidden_returns_non_compliant(self) -> None:
        mock_catalog = MagicMock()
        mock_catalog.get_library.return_value = _make_entry(LibraryStatus.forbidden)

        result = self._call(_mock_pipeline(), mock_catalog)

        assert result["status"] == "non_compliant"

    def test_catalog_restricted_returns_warning(self) -> None:
        mock_catalog = MagicMock()
        mock_catalog.get_library.return_value = _make_entry(LibraryStatus.restricted)

        result = self._call(_mock_pipeline(), mock_catalog)

        assert result["status"] == "warning"

    def test_unknown_library_no_vector_hits_returns_warning_not_found(self) -> None:
        mock_catalog = MagicMock()
        mock_catalog.get_library.return_value = None

        result = self._call(_mock_pipeline([]), mock_catalog)

        assert result["found"] is False
        assert result["status"] == "warning"

    def test_unknown_library_with_vector_hits_returns_warning_found(self) -> None:
        mock_catalog = MagicMock()
        mock_catalog.get_library.return_value = None

        result = self._call(_mock_pipeline([_hit()]), mock_catalog)

        assert result["found"] is True
        assert result["status"] == "warning"
        assert len(result["cited_chunks"]) == 1


# ---------------------------------------------------------------------------
# check_code_compliance
# ---------------------------------------------------------------------------

class TestCheckCodeCompliance:
    def _call(
        self,
        mock_pipeline: MagicMock,
        snippet: str = "import os; os.system('rm -rf')",
    ) -> dict[str, Any]:
        from src.server.tools import check_code_compliance
        return check_code_compliance(snippet, None, mock_pipeline)

    def test_with_hits_returns_warning_with_citations(self) -> None:
        result = self._call(_mock_pipeline([_hit()]))

        assert result["found"] is True
        assert result["status"] == "warning"
        assert len(result["cited_chunks"]) >= 1

    def test_no_evidence_returns_insufficient(self) -> None:
        result = self._call(_mock_pipeline([]))

        assert result["found"] is False


# ---------------------------------------------------------------------------
# check_infra_compliance
# ---------------------------------------------------------------------------

class TestCheckInfraCompliance:
    def _call(
        self,
        mock_pipeline: MagicMock,
        definition: str = "",
        type: str | None = None,
    ) -> dict[str, Any]:
        from src.server.tools import check_infra_compliance
        return check_infra_compliance(definition, type, mock_pipeline)

    def test_latest_tag_returns_non_compliant(self) -> None:
        dockerfile = "FROM python:latest\nRUN pip install flask"
        result = self._call(_mock_pipeline([]), dockerfile, "dockerfile")

        assert result["status"] == "non_compliant"
        assert "Unpinned base image" in result["justification"]

    def test_privileged_port_non_compliant(self) -> None:
        dockerfile = "FROM python:3.12\nEXPOSE 80"
        result = self._call(_mock_pipeline([]), dockerfile, "dockerfile")

        assert result["status"] == "non_compliant"
        assert "Privileged port" in result["justification"]

    def test_valid_dockerfile_with_no_evidence_returns_insufficient(self) -> None:
        dockerfile = "FROM python:3.12-slim\nCOPY . /app"
        result = self._call(_mock_pipeline([]), dockerfile, "dockerfile")

        assert result["found"] is False

    def test_hardcoded_secret_non_compliant(self) -> None:
        definition = "ENV SECRET_KEY=super_secret_value_1234"
        result = self._call(_mock_pipeline([]), definition)

        assert result["status"] == "non_compliant"

    def test_clean_infra_with_vector_evidence_returns_warning(self) -> None:
        definition = "FROM python:3.12-slim\nCOPY . /app"
        result = self._call(_mock_pipeline([_hit()]), definition, "dockerfile")

        assert result["found"] is True
        assert result["status"] == "warning"
