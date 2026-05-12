from dataclasses import dataclass, field
from typing import Any

from src.vector.chunking import Chunk
from src.vector.embedding_client import EmbeddingClient, EmbeddingError
from src.vector.qdrant_client import QdrantAdapter
from src.config.settings import settings


@dataclass
class PipelineResult:
    ingested: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)


class IngestPipeline:
    """Orchestrates: adapt → chunk → embed → upsert."""

    def __init__(
        self,
        qdrant: QdrantAdapter | None = None,
        embedding: EmbeddingClient | None = None,
        collection: str | None = None,
    ) -> None:
        self._qdrant = qdrant or QdrantAdapter()
        self._embedding = embedding or EmbeddingClient()
        self._collection = collection or settings.qdrant_collection

    def run(
        self,
        chunks: list[Chunk],
        incremental: bool = True,
    ) -> PipelineResult:
        """Embed and upsert chunks, optionally skipping already-stored ones.

        Args:
            chunks: Pre-chunked content from an adapter.
            incremental: When True, skip chunks whose chunk_id already exists.

        Returns:
            PipelineResult with ingested, skipped, and error counts.
        """
        result = PipelineResult()
        to_ingest: list[Chunk] = []

        for chunk in chunks:
            if incremental and self._qdrant.chunk_exists(self._collection, chunk.chunk_id):
                result.skipped += 1
            else:
                to_ingest.append(chunk)

        if not to_ingest:
            return result

        texts = [c.content for c in to_ingest]
        try:
            vectors: list[list[float]] = self._embedding.embed(texts)
        except EmbeddingError as exc:
            result.errors.append(f"embedding failed: {exc}")
            return result

        for chunk, vector in zip(to_ingest, vectors):
            try:
                self._qdrant.upsert_chunks(self._collection, [chunk], [vector])
                result.ingested += 1
            except Exception as exc:  # noqa: BLE001
                result.errors.append(f"upsert failed for {chunk.chunk_id}: {exc}")

        return result
