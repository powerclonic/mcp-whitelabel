import logging
from typing import Any

from src.config.settings import settings
from src.vector.embedding_client import EmbeddingClient, EmbeddingError
from src.vector.qdrant_client import QdrantAdapter
from src.vector.rerank_client import RerankClient

logger = logging.getLogger(__name__)


class RetrievalPipeline:
    """Orchestrates two-stage semantic retrieval.

    Stage 1 — **Candidate retrieval**: embeds the query (dense + optional sparse),
    runs hybrid search in Qdrant using RRF fusion, and returns *candidate_k* hits.

    Stage 2 — **Reranking**: if a :class:`RerankClient` is supplied, passes the
    candidate texts to the cross-encoder and reorders them by relevance score,
    returning only the best *top_n* results.

    Every step degrades gracefully:
    - Sparse embedding failure → falls back to dense-only retrieval.
    - Reranker failure → returns candidates in original Qdrant order (top_n).
    - Dense embedding failure → returns an empty list.
    """

    def __init__(
        self,
        qdrant: QdrantAdapter,
        embedding_client: EmbeddingClient,
        rerank_client: RerankClient | None = None,
        candidate_k: int | None = None,
        top_n: int | None = None,
    ) -> None:
        self._qdrant = qdrant
        self._embedding = embedding_client
        self._reranker = rerank_client
        self._candidate_k = candidate_k or settings.rerank_candidate_k
        self._top_n = top_n or settings.rerank_top_n

    def retrieve(
        self,
        query: str,
        collection: str,
        filters: dict[str, Any] | None = None,
        candidate_k: int | None = None,
        top_n: int | None = None,
    ) -> list[dict[str, Any]]:
        """Run the two-stage retrieval and return ranked hits.

        Args:
            query: Natural language query string.
            collection: Qdrant collection name.
            filters: Optional metadata equality filters forwarded to Qdrant.
            candidate_k: Override number of Qdrant candidates (default from settings).
            top_n: Override final result count (default from settings).

        Returns:
            List of hit dicts, each containing at minimum ``content``, ``score``,
            ``chunk_id``, ``origin``, and ``version_ref``. Empty list on failure.
        """
        _candidate_k = candidate_k or self._candidate_k
        _top_n = top_n or self._top_n

        # --- Stage 1a: dense embedding -----------------------------------
        try:
            dense_vectors = self._embedding.embed([query])
        except EmbeddingError as exc:
            logger.warning("Dense embedding failed: %s", exc)
            return []
        dense_vector = dense_vectors[0]

        # --- Stage 1b: sparse embedding (optional) -----------------------
        sparse_vector: list[dict[str, Any]] | None = None
        if settings.sparse_search_enabled:
            sparse_result = self._embedding.embed_sparse([query])
            if sparse_result:
                sparse_vector = sparse_result[0]
            else:
                logger.debug("Sparse embedding unavailable — using dense-only retrieval")

        # --- Stage 1c: Qdrant search (hybrid or dense-only) --------------
        candidates = self._qdrant.search(
            collection=collection,
            vector=dense_vector,
            sparse_vector=sparse_vector,
            filters=filters,
            top_k=_candidate_k,
        )

        if not candidates:
            return []

        # --- Stage 2: reranking ------------------------------------------
        if self._reranker is not None:
            texts = [hit.get("content", "") for hit in candidates]
            ranked_indices = self._reranker.rerank(query, texts)

            if ranked_indices is not None:
                candidates = [candidates[i] for i in ranked_indices[:_top_n]]
            else:
                candidates = candidates[:_top_n]
        else:
            candidates = candidates[:_top_n]

        return candidates
