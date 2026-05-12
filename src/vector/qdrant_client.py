from typing import Any, Sequence

from qdrant_client import QdrantClient as _QdrantClient
from qdrant_client.http import models as qm

from src.config.settings import settings
from src.vector.chunking import Chunk


class QdrantAdapter:
    """Thin wrapper around qdrant-client providing upsert and hybrid search."""

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        vector_size: int | None = None,
    ) -> None:
        self._host = host or settings.qdrant_host
        self._port = port or settings.qdrant_port
        self._vector_size = vector_size or settings.qdrant_vector_size
        self._client = _QdrantClient(host=self._host, port=self._port)

    def _ensure_collection(self, collection: str) -> None:
        existing = {c.name for c in self._client.get_collections().collections}
        if collection not in existing:
            self._client.create_collection(
                collection_name=collection,
                vectors_config=qm.VectorParams(
                    size=self._vector_size,
                    distance=qm.Distance.COSINE,
                ),
            )

    def upsert_chunks(self, collection: str, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        """Upsert chunks with their embedding vectors into the collection."""
        self._ensure_collection(collection)
        points = [
            qm.PointStruct(
                id=abs(hash(chunk.chunk_id)) % (2**63),
                vector=vector,
                payload={
                    "chunk_id": chunk.chunk_id,
                    "content": chunk.content,
                    "origin": chunk.metadata.get("origin", ""),
                    "source_type": chunk.metadata.get("source_type", ""),
                    "version_ref": chunk.metadata.get("version_ref", ""),
                    "timestamp": chunk.metadata.get("timestamp", ""),
                    "domain": chunk.metadata.get("domain", ""),
                    **chunk.metadata,
                },
            )
            for chunk, vector in zip(chunks, vectors)
        ]
        self._client.upsert(collection_name=collection, points=points)

    def search(
        self,
        collection: str,
        vector: list[float],
        filters: dict[str, Any] | None = None,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Search for similar chunks and return their payloads."""
        self._ensure_collection(collection)
        query_filter = None
        if filters:
            conditions: Sequence[qm.FieldCondition] = [
                qm.FieldCondition(key=k, match=qm.MatchValue(value=v))
                for k, v in filters.items()
            ]
            query_filter = qm.Filter(must=list(conditions))

        results = self._client.query_points(
            collection_name=collection,
            query=vector,
            query_filter=query_filter,
            limit=top_k,
        )
        return [
            {"score": r.score, **(r.payload or {})}
            for r in results.points
        ]

    def chunk_exists(self, collection: str, chunk_id: str) -> bool:
        """Check if a chunk with the given chunk_id already exists."""
        self._ensure_collection(collection)
        results = self._client.scroll(
            collection_name=collection,
            scroll_filter=qm.Filter(
                must=[qm.FieldCondition(key="chunk_id", match=qm.MatchValue(value=chunk_id))]
            ),
            limit=1,
        )
        return len(results[0]) > 0
