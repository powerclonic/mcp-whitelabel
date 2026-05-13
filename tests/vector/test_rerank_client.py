"""Tests for RerankClient."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.vector.rerank_client import RerankClient


class TestRerankClientParse:
    """_parse_response is a pure function — test it directly."""

    def test_index_score_format(self) -> None:
        data = [{"index": 1, "score": 0.9}, {"index": 0, "score": 0.3}, {"index": 2, "score": 0.6}]
        result = RerankClient._parse_response(data, 3)
        assert result == [1, 2, 0]  # sorted by score desc

    def test_float_list_format(self) -> None:
        data = [0.3, 0.9, 0.6]
        result = RerankClient._parse_response(data, 3)
        assert result == [1, 2, 0]

    def test_dict_with_scores_key(self) -> None:
        data = {"scores": [0.3, 0.9, 0.6]}
        result = RerankClient._parse_response(data, 3)
        assert result == [1, 2, 0]

    def test_unknown_format_returns_identity(self) -> None:
        result = RerankClient._parse_response("bad", 3)
        assert result == [0, 1, 2]

    def test_empty_list_returns_empty(self) -> None:
        result = RerankClient._parse_response([], 0)
        assert result == []


class TestRerankClientHttp:
    def test_rerank_returns_sorted_indices_on_success(self) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [
            {"index": 1, "score": 0.95},
            {"index": 0, "score": 0.40},
        ]

        with patch("httpx.post", return_value=mock_resp):
            client = RerankClient(url="http://test/rerank", model="reranker")
            result = client.rerank("query", ["doc0", "doc1"])

        assert result == [1, 0]

    def test_rerank_returns_none_on_http_error(self) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 503

        with patch("httpx.post", return_value=mock_resp):
            client = RerankClient(url="http://test/rerank", model="reranker")
            result = client.rerank("query", ["doc"])

        assert result is None

    def test_rerank_returns_none_on_network_error(self) -> None:
        import httpx

        with patch("httpx.post", side_effect=httpx.RequestError("timeout")):
            client = RerankClient(url="http://test/rerank", model="reranker")
            result = client.rerank("query", ["doc"])

        assert result is None

    def test_rerank_empty_texts_returns_empty_list(self) -> None:
        with patch("httpx.post") as mock_post:
            client = RerankClient(url="http://test/rerank", model="reranker")
            result = client.rerank("query", [])

        mock_post.assert_not_called()
        assert result == []
