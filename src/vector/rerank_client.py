import logging
from typing import Any

import httpx

from src.config.settings import settings

logger = logging.getLogger(__name__)


class RerankClient:
    """HTTP client for a TEI cross-encoder reranker (e.g. BAAI/bge-reranker-v2-m3).

    Calls ``POST /rerank`` and returns document indices sorted by relevance score
    (most relevant first). Returns ``None`` on any network or HTTP error so the
    caller can fall back to the original candidate order.

    TEI ``/rerank`` response format (tolerantly parsed)::

        [{"index": 0, "score": 0.98}, {"index": 1, "score": 0.42}, ...]

        OR (legacy / alternative formats):
        {"scores": [0.98, 0.42, ...]}   → indices derived from position
        [0.98, 0.42, ...]               → indices derived from position
    """

    def __init__(
        self,
        url: str | None = None,
        model: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._url = url or settings.reranker_url
        self._model = model or settings.reranker_model
        self._timeout = timeout

    def rerank(self, query: str, texts: list[str]) -> list[int] | None:
        """Return candidate indices sorted by reranker score (best first).

        Args:
            query: The search query.
            texts: Candidate document texts in original order.

        Returns:
            Sorted list of original indices (most relevant first), or ``None``
            if the reranker service is unavailable so the caller can fall back.
        """
        if not texts:
            return []

        payload: dict[str, Any] = {
            "query": query,
            "texts": texts,
            "return_text": False,
        }
        try:
            response = httpx.post(self._url, json=payload, timeout=self._timeout)
        except httpx.RequestError as exc:
            logger.warning("Reranker unavailable (%s) — using original candidate order", exc)
            return None

        if response.status_code != 200:
            logger.warning(
                "Reranker returned HTTP %d — using original candidate order",
                response.status_code,
            )
            return None

        return self._parse_response(response.json(), len(texts))

    @staticmethod
    def _parse_response(data: Any, n: int) -> list[int]:
        """Tolerantly parse TEI rerank response into sorted indices."""
        if isinstance(data, list):
            if data and isinstance(data[0], dict):
                # [{"index": 0, "score": 0.98}, ...]
                scored = sorted(data, key=lambda x: float(x.get("score", 0.0)), reverse=True)
                return [int(item["index"]) for item in scored]
            # [0.98, 0.42, ...] — raw scores, position = original index
            scores: list[float] = [float(s) for s in data]
            return sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)

        if isinstance(data, dict):
            raw = data.get("scores") or data.get("results") or []
            if raw and isinstance(raw[0], dict):
                scored_items = sorted(raw, key=lambda x: float(x.get("score", 0.0)), reverse=True)
                return [int(item["index"]) for item in scored_items]
            score_list: list[float] = [float(s) for s in raw]
            return sorted(range(len(score_list)), key=lambda i: score_list[i], reverse=True)

        # Unrecognised format — return identity order
        return list(range(n))
