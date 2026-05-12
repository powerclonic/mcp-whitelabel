from abc import ABC, abstractmethod
from typing import Optional

from src.catalog.models import LibraryEntry, StandardEntry


class CatalogRepository(ABC):
    @abstractmethod
    def get_library(self, name: str, version: str) -> Optional[LibraryEntry]:
        """Return the catalog entry for a library+version, or None if unknown."""

    @abstractmethod
    def get_standard(self, id: str) -> Optional[StandardEntry]:
        """Return the standard entry by ID, or None if unknown."""


class InMemoryCatalogRepository(CatalogRepository):
    """Simple in-memory catalog for testing and bootstrapping."""

    def __init__(
        self,
        libraries: list[LibraryEntry] | None = None,
        standards: list[StandardEntry] | None = None,
    ) -> None:
        self._libraries: dict[tuple[str, str], LibraryEntry] = {
            (e.name, e.version): e for e in (libraries or [])
        }
        self._standards: dict[str, StandardEntry] = {
            e.id: e for e in (standards or [])
        }

    def get_library(self, name: str, version: str) -> Optional[LibraryEntry]:
        return self._libraries.get((name, version))

    def get_standard(self, id: str) -> Optional[StandardEntry]:
        return self._standards.get(id)
