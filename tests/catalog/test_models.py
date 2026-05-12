import pytest
from datetime import date
from pydantic import ValidationError

from src.catalog.models import (
    ComplianceStatus,
    LibraryEntry,
    LibraryStatus,
    StandardEntry,
)
from src.catalog.repository import InMemoryCatalogRepository


class TestLibraryEntry:
    def test_approved_status(self) -> None:
        entry = LibraryEntry(
            name="requests",
            version="2.31.0",
            status=LibraryStatus.approved,
            reason="Standard HTTP client",
            effective_date=date(2024, 1, 1),
            updated_by="admin",
        )
        assert entry.status == LibraryStatus.approved

    def test_restricted_status(self) -> None:
        entry = LibraryEntry(
            name="legacy-lib",
            version="1.0.0",
            status=LibraryStatus.restricted,
            reason="Deprecated API",
            effective_date=date(2024, 1, 1),
            updated_by="admin",
        )
        assert entry.status == LibraryStatus.restricted

    def test_forbidden_status(self) -> None:
        entry = LibraryEntry(
            name="vuln-pkg",
            version="0.1.0",
            status=LibraryStatus.forbidden,
            reason="Known CVE",
            effective_date=date(2024, 1, 1),
            updated_by="security",
        )
        assert entry.status == LibraryStatus.forbidden

    def test_invalid_status_raises(self) -> None:
        with pytest.raises(ValidationError):
            LibraryEntry(
                name="x",
                version="1.0",
                status="unknown",  # type: ignore[arg-type]
                reason="",
                effective_date=date(2024, 1, 1),
                updated_by="admin",
            )


class TestStandardEntry:
    def test_creation(self) -> None:
        entry = StandardEntry(
            id="STD-001",
            domain="security",
            title="No hardcoded secrets",
            description="Secrets must be injected via env vars",
            policy_version="1.0",
            effective_date=date(2024, 1, 1),
            updated_by="admin",
        )
        assert entry.id == "STD-001"
        assert entry.domain == "security"


class TestInMemoryCatalogRepository:
    def _make_library(self, name: str = "requests", version: str = "2.31.0") -> LibraryEntry:
        return LibraryEntry(
            name=name,
            version=version,
            status=LibraryStatus.approved,
            reason="OK",
            effective_date=date(2024, 1, 1),
            updated_by="admin",
        )

    def _make_standard(self, id: str = "STD-001") -> StandardEntry:
        return StandardEntry(
            id=id,
            domain="security",
            title="Test Standard",
            description="Desc",
            policy_version="1.0",
            effective_date=date(2024, 1, 1),
            updated_by="admin",
        )

    def test_get_known_library(self) -> None:
        entry = self._make_library()
        repo = InMemoryCatalogRepository(libraries=[entry])
        result = repo.get_library("requests", "2.31.0")
        assert result is not None
        assert result.status == LibraryStatus.approved

    def test_get_unknown_library_returns_none(self) -> None:
        repo = InMemoryCatalogRepository()
        assert repo.get_library("nonexistent", "9.9.9") is None

    def test_get_known_standard(self) -> None:
        entry = self._make_standard()
        repo = InMemoryCatalogRepository(standards=[entry])
        result = repo.get_standard("STD-001")
        assert result is not None
        assert result.domain == "security"

    def test_get_unknown_standard_returns_none(self) -> None:
        repo = InMemoryCatalogRepository()
        assert repo.get_standard("STD-999") is None


class TestComplianceStatus:
    def test_all_values(self) -> None:
        assert ComplianceStatus.compliant == "compliant"
        assert ComplianceStatus.warning == "warning"
        assert ComplianceStatus.non_compliant == "non_compliant"
