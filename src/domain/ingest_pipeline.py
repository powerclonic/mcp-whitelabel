import logging
from dataclasses import dataclass, field
from typing import Any

from src.config.settings import settings
from src.vector.chunking import Chunk
from src.vector.embedding_client import EmbeddingClient, EmbeddingError
from src.vector.qdrant_client import QdrantAdapter

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    ingested: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)


class IngestPipeline:
    """Orchestrates: adapt → chunk → embed → upsert.

    When ``settings.sparse_search_enabled`` is True, also embeds sparse
    token-weight vectors (via TEI ``/embed_sparse``) and stores them alongside
    dense vectors so that hybrid retrieval can leverage both. Sparse embedding
    failures are non-fatal: a warning is logged and ingestion continues with
    dense-only vectors.

    Note: existing collections ingested without sparse vectors require
    re-ingestion (pass ``incremental=False``) to gain hybrid search benefits.
    """

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
            dense_vectors: list[list[float]] = self._embedding.embed(texts)
        except EmbeddingError as exc:
            result.errors.append(f"embedding failed: {exc}")
            return result

        sparse_vectors: list[list[dict[str, Any]]] | None = None
        if settings.sparse_search_enabled:
            sparse_result = self._embedding.embed_sparse(texts)
            if sparse_result is not None:
                sparse_vectors = sparse_result
            else:
                logger.warning(
                    "Sparse embedding unavailable for batch of %d chunks — ingesting dense-only",
                    len(to_ingest),
                )

        for idx, (chunk, dense_vec) in enumerate(zip(to_ingest, dense_vectors)):
            sparse_batch = [sparse_vectors[idx]] if sparse_vectors is not None else None
            try:
                self._qdrant.upsert_chunks(
                    self._collection,
                    [chunk],
                    [dense_vec],
                    sparse_vectors=sparse_batch,
                )
                result.ingested += 1
            except Exception as exc:  # noqa: BLE001
                result.errors.append(f"upsert failed for {chunk.chunk_id}: {exc}")

        return result

