"""Tests for RetrievalPipeline (two-stage retrieval orchestrator)."""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest


def _hit(content: str = "policy text", score: float = 0.9) -> dict[str, Any]:
    return {"content": content, "score": score, "chunk_id": "c1", "origin": "doc.md"}


class TestRetrievalPipelineRetrieve:
    def _make_pipeline(
        self,
        dense: list[list[float]] | None = None,
        sparse: list[list[dict]] | None = None,
        search_hits: list[dict] | None = None,
        rerank_indices: list[int] | None = None,
        embed_error: bool = False,
        reranker_enabled: bool = True,
    ):
        from src.vector.retrieval_pipeline import RetrievalPipeline

        qdrant = MagicMock()
        qdrant.search.return_value = search_hits if search_hits is not None else [_hit()]

        embedding = MagicMock()
        if embed_error:
            from src.vector.embedding_client import EmbeddingError
            embedding.embed.side_effect = EmbeddingError("down")
        else:
            embedding.embed.return_value = dense or [[0.1, 0.2, 0.3]]
        embedding.embed_sparse.return_value = sparse  # None means failure

        reranker = None
        if reranker_enabled:
            reranker = MagicMock()
            reranker.rerank.return_value = rerank_indices  # None means fallback

        return RetrievalPipeline(
            qdrant=qdrant,
            embedding_client=embedding,
            rerank_client=reranker,
            candidate_k=10,
            top_n=3,
        ), qdrant, embedding, reranker

    def test_full_two_stage_returns_reranked_results(self) -> None:
        hits = [_hit("doc0"), _hit("doc1"), _hit("doc2"), _hit("doc3")]
        pipeline, _, _, reranker = self._make_pipeline(
            search_hits=hits,
            rerank_indices=[2, 0, 1],  # reranker picks 2, 0, 1 as top-3
        )

        with patch("src.vector.retrieval_pipeline.settings") as mock_settings:
            mock_settings.sparse_search_enabled = False
            results = pipeline.retrieve("query", "my_col")

        assert len(results) == 3
        assert results[0]["content"] == "doc2"
        assert results[1]["content"] == "doc0"
        assert results[2]["content"] == "doc1"

    def test_reranker_failure_falls_back_to_original_order(self) -> None:
        hits = [_hit("a"), _hit("b"), _hit("c")]
        pipeline, _, _, reranker = self._make_pipeline(
            search_hits=hits,
            rerank_indices=None,  # None → fallback
        )

        with patch("src.vector.retrieval_pipeline.settings") as mock_settings:
            mock_settings.sparse_search_enabled = False
            results = pipeline.retrieve("query", "my_col")

        assert len(results) == 3
        assert results[0]["content"] == "a"

    def test_sparse_failure_uses_dense_only(self) -> None:
        pipeline, qdrant, embedding, _ = self._make_pipeline(
            sparse=None,  # embed_sparse returns None
            reranker_enabled=False,
        )

        with patch("src.vector.retrieval_pipeline.settings") as mock_settings:
            mock_settings.sparse_search_enabled = True
            pipeline.retrieve("query", "my_col")

        call_kwargs = qdrant.search.call_args
        assert call_kwargs.kwargs.get("sparse_vector") is None

    def test_sparse_disabled_skips_embed_sparse_call(self) -> None:
        pipeline, qdrant, embedding, _ = self._make_pipeline(reranker_enabled=False)

        with patch("src.vector.retrieval_pipeline.settings") as mock_settings:
            mock_settings.sparse_search_enabled = False
            pipeline.retrieve("query", "my_col")

        embedding.embed_sparse.assert_not_called()

    def test_dense_embedding_error_returns_empty(self) -> None:
        pipeline, _, _, _ = self._make_pipeline(embed_error=True)

        with patch("src.vector.retrieval_pipeline.settings") as mock_settings:
            mock_settings.sparse_search_enabled = False
            results = pipeline.retrieve("query", "my_col")

        assert results == []

    def test_no_candidates_returns_empty(self) -> None:
        pipeline, _, _, _ = self._make_pipeline(search_hits=[])

        with patch("src.vector.retrieval_pipeline.settings") as mock_settings:
            mock_settings.sparse_search_enabled = False
            results = pipeline.retrieve("query", "my_col")

        assert results == []

    def test_top_n_respected_without_reranker(self) -> None:
        hits = [_hit(f"doc{i}") for i in range(10)]
        pipeline, _, _, _ = self._make_pipeline(
            search_hits=hits,
            reranker_enabled=False,
        )

        with patch("src.vector.retrieval_pipeline.settings") as mock_settings:
            mock_settings.sparse_search_enabled = False
            results = pipeline.retrieve("query", "my_col")

        assert len(results) == 3  # top_n=3 set in constructor

    def test_filters_passed_to_qdrant(self) -> None:
        pipeline, qdrant, _, _ = self._make_pipeline(reranker_enabled=False)

        with patch("src.vector.retrieval_pipeline.settings") as mock_settings:
            mock_settings.sparse_search_enabled = False
            pipeline.retrieve("query", "my_col", filters={"domain": "security"})

        call_kwargs = qdrant.search.call_args
        assert call_kwargs.kwargs.get("filters") == {"domain": "security"}
