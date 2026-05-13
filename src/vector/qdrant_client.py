from typing import Any, Sequence

from qdrant_client import QdrantClient as _QdrantClient
from qdrant_client.http import models as qm

from src.config.settings import settings
from src.vector.chunking import Chunk

_DENSE_VECTOR = "dense"
_SPARSE_VECTOR = "sparse"


def _to_sparse_vector(token_weights: list[dict[str, Any]]) -> qm.SparseVector:
    """Convert TEI sparse output (list of {index, value} dicts) to Qdrant SparseVector."""
    indices = [int(t["index"]) for t in token_weights]
    values = [float(t["value"]) for t in token_weights]
    return qm.SparseVector(indices=indices, values=values)


class QdrantAdapter:
    """Thin wrapper around qdrant-client providing upsert and hybrid search.

    Supports two collection schemas:
    - *hybrid*: named vectors ``dense`` (float) + ``sparse`` (sparse), using RRF
      fusion for retrieval. Created for new collections when
      ``sparse_search_enabled=True``.
    - *legacy*: single unnamed dense vector. Used for existing collections that
      pre-date the hybrid schema, and as a fallback when sparse vectors are
      unavailable.

    Schema is detected automatically per collection on first access and cached.
    """

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        vector_size: int | None = None,
        sparse_enabled: bool | None = None,
    ) -> None:
        self._host = host or settings.qdrant_host
        self._port = port or settings.qdrant_port
        self._vector_size = vector_size or settings.qdrant_vector_size
        self._sparse_enabled = (
            sparse_enabled if sparse_enabled is not None else settings.sparse_search_enabled
        )
        self._client = _QdrantClient(host=self._host, port=self._port)
        # Cache: collection_name -> "hybrid" | "legacy"
        self._schema_cache: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Schema helpers
    # ------------------------------------------------------------------

    def _collection_schema(self, collection: str) -> str:
        """Return ``"hybrid"`` or ``"legacy"`` for an existing collection."""
        if collection in self._schema_cache:
            return self._schema_cache[collection]
        try:
            info = self._client.get_collection(collection)
            named = info.config.params.vectors
            schema = "hybrid" if isinstance(named, dict) and _DENSE_VECTOR in named else "legacy"
        except Exception:  # noqa: BLE001
            schema = "legacy"
        self._schema_cache[collection] = schema
        return schema

    def _ensure_collection(self, collection: str) -> None:
        existing = {c.name for c in self._client.get_collections().collections}
        if collection in existing:
            return

        if self._sparse_enabled:
            self._client.create_collection(
                collection_name=collection,
                vectors_config={
                    _DENSE_VECTOR: qm.VectorParams(
                        size=self._vector_size,
                        distance=qm.Distance.COSINE,
                    )
                },
                sparse_vectors_config={
                    _SPARSE_VECTOR: qm.SparseVectorParams(),
                },
            )
            self._schema_cache[collection] = "hybrid"
        else:
            self._client.create_collection(
                collection_name=collection,
                vectors_config=qm.VectorParams(
                    size=self._vector_size,
                    distance=qm.Distance.COSINE,
                ),
            )
            self._schema_cache[collection] = "legacy"

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def upsert_chunks(
        self,
        collection: str,
        chunks: list[Chunk],
        vectors: list[list[float]],
        sparse_vectors: list[list[dict[str, Any]]] | None = None,
    ) -> None:
        """Upsert chunks with their embedding vectors into the collection.

        When the collection schema is *hybrid*, always uses named vector format.
        If *sparse_vectors* is also provided, includes the sparse vector; otherwise
        stores only the ``dense`` named vector. Falls back to the legacy
        single-vector format only for *legacy* collections.
        """
        self._ensure_collection(collection)
        schema = self._collection_schema(collection)
        use_hybrid = schema == "hybrid" and sparse_vectors is not None

        points: list[qm.PointStruct] = []
        for idx, (chunk, dense_vec) in enumerate(zip(chunks, vectors)):
            payload = {
                "chunk_id": chunk.chunk_id,
                "content": chunk.content,
                "origin": chunk.metadata.get("origin", ""),
                "source_type": chunk.metadata.get("source_type", ""),
                "version_ref": chunk.metadata.get("version_ref", ""),
                "timestamp": chunk.metadata.get("timestamp", ""),
                "domain": chunk.metadata.get("domain", ""),
                **chunk.metadata,
            }

            if use_hybrid and sparse_vectors is not None:
                vector: Any = {
                    _DENSE_VECTOR: dense_vec,
                    _SPARSE_VECTOR: _to_sparse_vector(sparse_vectors[idx]),
                }
            elif schema == "hybrid":
                # Collection has named vectors; omit sparse when unavailable
                vector = {_DENSE_VECTOR: dense_vec}
            else:
                vector = dense_vec

            points.append(
                qm.PointStruct(
                    id=abs(hash(chunk.chunk_id)) % (2**63),
                    vector=vector,
                    payload=payload,
                )
            )

        self._client.upsert(collection_name=collection, points=points)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def search(
        self,
        collection: str,
        vector: list[float],
        sparse_vector: list[dict[str, Any]] | None = None,
        filters: dict[str, Any] | None = None,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Search for similar chunks and return their payloads.

        Uses hybrid (dense+sparse) RRF fusion when *sparse_vector* is provided and
        the collection has the hybrid schema. Falls back to dense-only cosine search
        otherwise.
        """
        self._ensure_collection(collection)
        schema = self._collection_schema(collection)
        use_hybrid = schema == "hybrid" and sparse_vector is not None

        query_filter: qm.Filter | None = None
        if filters:
            conditions: Sequence[qm.FieldCondition] = [
                qm.FieldCondition(key=k, match=qm.MatchValue(value=v))
                for k, v in filters.items()
            ]
            query_filter = qm.Filter(must=list(conditions))

        if use_hybrid:
            results = self._client.query_points(
                collection_name=collection,
                prefetch=[
                    qm.Prefetch(
                        query=vector,
                        using=_DENSE_VECTOR,
                        limit=top_k,
                        filter=query_filter,
                    ),
                    qm.Prefetch(
                        query=_to_sparse_vector(sparse_vector),  # type: ignore[arg-type]
                        using=_SPARSE_VECTOR,
                        limit=top_k,
                        filter=query_filter,
                    ),
                ],
                query=qm.FusionQuery(fusion=qm.Fusion.RRF),
                limit=top_k,
            )
        elif schema == "hybrid":
            # Hybrid collection but no sparse query — search dense vector by name
            results = self._client.query_points(
                collection_name=collection,
                query=vector,
                using=_DENSE_VECTOR,
                query_filter=query_filter,
                limit=top_k,
            )
        else:
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
