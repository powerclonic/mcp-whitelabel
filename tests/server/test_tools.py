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


# ---------------------------------------------------------------------------
# search_governance
# ---------------------------------------------------------------------------

class TestSearchGovernance:
    def _call(self, mock_qdrant: MagicMock, mock_embed: MagicMock, query: str = "security policy", domain: str | None = None) -> dict[str, Any]:
        from src.server.tools import search_governance
        return search_governance(query, domain, mock_qdrant, mock_embed)

    def test_returns_results_when_hits_found(self) -> None:
        mock_qdrant = MagicMock()
        mock_qdrant.search.return_value = [_hit()]
        mock_embed = MagicMock()
        mock_embed.embed.return_value = [[0.1] * 3]

        result = self._call(mock_qdrant, mock_embed)

        assert result["found"] is True
        assert len(result["results"]) == 1
        assert len(result["cited_chunks"]) == 1
        assert result["cited_chunks"][0]["chunk_id"] == "c1"

    def test_returns_insufficient_evidence_when_no_hits(self) -> None:
        mock_qdrant = MagicMock()
        mock_qdrant.search.return_value = []
        mock_embed = MagicMock()
        mock_embed.embed.return_value = [[0.1] * 3]

        result = self._call(mock_qdrant, mock_embed)

        assert result["found"] is False
        assert result["status"] == "warning"
        assert "insufficient evidence" in result["justification"]

    def test_returns_insufficient_evidence_on_embed_error(self) -> None:
        from src.vector.embedding_client import EmbeddingError
        mock_qdrant = MagicMock()
        mock_embed = MagicMock()
        mock_embed.embed.side_effect = EmbeddingError("down")

        result = self._call(mock_qdrant, mock_embed)

        assert result["found"] is False

    def test_low_score_hits_filtered_out(self) -> None:
        mock_qdrant = MagicMock()
        mock_qdrant.search.return_value = [_hit(score=0.2)]  # below MIN_SCORE
        mock_embed = MagicMock()
        mock_embed.embed.return_value = [[0.1] * 3]

        result = self._call(mock_qdrant, mock_embed)

        assert result["found"] is False


# ---------------------------------------------------------------------------
# check_library_compliance
# ---------------------------------------------------------------------------

class TestCheckLibraryCompliance:
    def _call(
        self,
        mock_qdrant: MagicMock,
        mock_embed: MagicMock,
        mock_catalog: MagicMock,
        name: str = "requests",
        version: str = "2.31.0",
    ) -> dict[str, Any]:
        from src.server.tools import check_library_compliance
        return check_library_compliance(name, version, mock_qdrant, mock_embed, mock_catalog)

    def test_catalog_approved_returns_compliant(self) -> None:
        mock_catalog = MagicMock()
        mock_catalog.get_library.return_value = _make_entry(LibraryStatus.approved)

        result = self._call(MagicMock(), MagicMock(), mock_catalog)

        assert result["status"] == "compliant"
        assert result["found"] is True
        assert result["cited_chunks"][0]["origin"] == "catalog"

    def test_catalog_forbidden_returns_non_compliant(self) -> None:
        mock_catalog = MagicMock()
        mock_catalog.get_library.return_value = _make_entry(LibraryStatus.forbidden)

        result = self._call(MagicMock(), MagicMock(), mock_catalog)

        assert result["status"] == "non_compliant"

    def test_catalog_restricted_returns_warning(self) -> None:
        mock_catalog = MagicMock()
        mock_catalog.get_library.return_value = _make_entry(LibraryStatus.restricted)

        result = self._call(MagicMock(), MagicMock(), mock_catalog)

        assert result["status"] == "warning"

    def test_unknown_library_no_vector_hits_returns_warning_not_found(self) -> None:
        mock_catalog = MagicMock()
        mock_catalog.get_library.return_value = None
        mock_qdrant = MagicMock()
        mock_qdrant.search.return_value = []
        mock_embed = MagicMock()
        mock_embed.embed.return_value = [[0.1] * 3]

        result = self._call(mock_qdrant, mock_embed, mock_catalog)

        assert result["found"] is False
        assert result["status"] == "warning"

    def test_unknown_library_with_vector_hits_returns_warning_found(self) -> None:
        mock_catalog = MagicMock()
        mock_catalog.get_library.return_value = None
        mock_qdrant = MagicMock()
        mock_qdrant.search.return_value = [_hit()]
        mock_embed = MagicMock()
        mock_embed.embed.return_value = [[0.1] * 3]

        result = self._call(mock_qdrant, mock_embed, mock_catalog)

        assert result["found"] is True
        assert result["status"] == "warning"
        assert len(result["cited_chunks"]) == 1


# ---------------------------------------------------------------------------
# check_code_compliance
# ---------------------------------------------------------------------------

class TestCheckCodeCompliance:
    def _call(
        self,
        mock_qdrant: MagicMock,
        mock_embed: MagicMock,
        snippet: str = "import os; os.system('rm -rf')",
    ) -> dict[str, Any]:
        from src.server.tools import check_code_compliance
        return check_code_compliance(snippet, None, mock_qdrant, mock_embed)

    def test_with_hits_returns_warning_with_citations(self) -> None:
        mock_qdrant = MagicMock()
        mock_qdrant.search.return_value = [_hit()]
        mock_embed = MagicMock()
        mock_embed.embed.return_value = [[0.1] * 3]

        result = self._call(mock_qdrant, mock_embed)

        assert result["found"] is True
        assert result["status"] == "warning"
        assert len(result["cited_chunks"]) >= 1

    def test_no_evidence_returns_insufficient(self) -> None:
        mock_qdrant = MagicMock()
        mock_qdrant.search.return_value = []
        mock_embed = MagicMock()
        mock_embed.embed.return_value = [[0.1] * 3]

        result = self._call(mock_qdrant, mock_embed)

        assert result["found"] is False


# ---------------------------------------------------------------------------
# check_infra_compliance
# ---------------------------------------------------------------------------

class TestCheckInfraCompliance:
    def _call(
        self,
        mock_qdrant: MagicMock,
        mock_embed: MagicMock,
        definition: str = "",
        type: str | None = None,
    ) -> dict[str, Any]:
        from src.server.tools import check_infra_compliance
        return check_infra_compliance(definition, type, mock_qdrant, mock_embed)

    def test_latest_tag_returns_non_compliant(self) -> None:
        dockerfile = "FROM python:latest\nRUN pip install flask"
        mock_embed = MagicMock()
        mock_embed.embed.return_value = [[0.1] * 3]
        mock_qdrant = MagicMock()
        mock_qdrant.search.return_value = []

        result = self._call(mock_qdrant, mock_embed, dockerfile, "dockerfile")

        assert result["status"] == "non_compliant"
        assert "Unpinned base image" in result["justification"]

    def test_privileged_port_non_compliant(self) -> None:
        dockerfile = "FROM python:3.12\nEXPOSE 80"
        mock_embed = MagicMock()
        mock_embed.embed.return_value = [[0.1] * 3]
        mock_qdrant = MagicMock()
        mock_qdrant.search.return_value = []

        result = self._call(mock_qdrant, mock_embed, dockerfile, "dockerfile")

        assert result["status"] == "non_compliant"
        assert "Privileged port" in result["justification"]

    def test_valid_dockerfile_with_no_evidence_returns_insufficient(self) -> None:
        dockerfile = "FROM python:3.12-slim\nCOPY . /app"
        mock_embed = MagicMock()
        mock_embed.embed.return_value = [[0.1] * 3]
        mock_qdrant = MagicMock()
        mock_qdrant.search.return_value = []

        result = self._call(mock_qdrant, mock_embed, dockerfile, "dockerfile")

        assert result["found"] is False

    def test_hardcoded_secret_non_compliant(self) -> None:
        definition = "ENV SECRET_KEY=super_secret_value_1234"
        mock_embed = MagicMock()
        mock_embed.embed.return_value = [[0.1] * 3]
        mock_qdrant = MagicMock()
        mock_qdrant.search.return_value = []

        result = self._call(mock_qdrant, mock_embed, definition)

        assert result["status"] == "non_compliant"

    def test_clean_infra_with_vector_evidence_returns_warning(self) -> None:
        definition = "FROM python:3.12-slim\nCOPY . /app"
        mock_embed = MagicMock()
        mock_embed.embed.return_value = [[0.1] * 3]
        mock_qdrant = MagicMock()
        mock_qdrant.search.return_value = [_hit()]

        result = self._call(mock_qdrant, mock_embed, definition, "dockerfile")

        assert result["found"] is True
        assert result["status"] == "warning"
