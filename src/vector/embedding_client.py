from typing import Any

import httpx

from src.config.settings import settings


class EmbeddingError(Exception):
    """Raised when the embedding service returns a non-200 response."""


class EmbeddingClient:
    def __init__(
        self,
        url: str | None = None,
        sparse_url: str | None = None,
        model: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._url = url or settings.embedding_url
        self._sparse_url = sparse_url or settings.embedding_sparse_url
        self._model = model or settings.embedding_model
        self._timeout = timeout

    @property
    def model(self) -> str:
        return self._model

    def embed(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        """Call the self-hosted embedding endpoint and return dense embedding vectors.

        Splits large inputs into batches of ``batch_size`` to respect server limits.
        """
        if not texts:
            return []

        results: list[list[float]] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            try:
                response = httpx.post(
                    self._url,
                    json={"inputs": batch, "model": self._model},
                    timeout=self._timeout,
                )
            except httpx.RequestError as exc:
                raise EmbeddingError(f"Connection error: {exc}") from exc

            if response.status_code != 200:
                raise EmbeddingError(
                    f"Embedding service returned HTTP {response.status_code}: {response.text}"
                )
            data = response.json()
            batch_vectors: list[list[float]] = data if isinstance(data, list) else data["embeddings"]
            results.extend(batch_vectors)

        return results

    def embed_sparse(
        self, texts: list[str], batch_size: int = 32
    ) -> list[list[dict[str, Any]]] | None:
        """Return sparse token-weight representations from TEI ``/embed_sparse``.

        Each document is represented as a list of ``{"index": int, "value": float}``
        dicts. Returns ``None`` on any error so callers can gracefully fall back to
        dense-only retrieval.
        """
        if not texts:
            return []

        results: list[list[dict[str, Any]]] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            try:
                response = httpx.post(
                    self._sparse_url,
                    json={"inputs": batch, "model": self._model},
                    timeout=self._timeout,
                )
            except httpx.RequestError:
                return None

            if response.status_code != 200:
                return None

            data = response.json()
            batch_sparse: list[list[dict[str, Any]]] = (
                data if isinstance(data, list) else data.get("embeddings", data)
            )
            results.extend(batch_sparse)

        return results

    def embed_with_metadata(
        self, texts: list[str], extra_metadata: dict[str, Any] | None = None
    ) -> tuple[list[list[float]], dict[str, Any]]:
        """Embed texts and return vectors alongside model metadata."""
        vectors = self.embed(texts)
        metadata: dict[str, Any] = {"embedding_model": self._model}
        if extra_metadata:
            metadata.update(extra_metadata)
        return vectors, metadata
