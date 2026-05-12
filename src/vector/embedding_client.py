from typing import Any

import httpx

from src.config.settings import settings


class EmbeddingError(Exception):
    """Raised when the embedding service returns a non-200 response."""


class EmbeddingClient:
    def __init__(
        self,
        url: str | None = None,
        model: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._url = url or settings.embedding_url
        self._model = model or settings.embedding_model
        self._timeout = timeout

    @property
    def model(self) -> str:
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Call the self-hosted embedding endpoint and return embedding vectors."""
        try:
            response = httpx.post(
                self._url,
                json={"inputs": texts, "model": self._model},
                timeout=self._timeout,
            )
        except httpx.RequestError as exc:
            raise EmbeddingError(f"Connection error: {exc}") from exc

        if response.status_code != 200:
            raise EmbeddingError(
                f"Embedding service returned HTTP {response.status_code}: {response.text}"
            )
        data = response.json()
        # Support both {"embeddings": [...]} and plain list responses
        if isinstance(data, list):
            return data  # type: ignore[return-value]
        return data["embeddings"]  # type: ignore[return-value]

    def embed_with_metadata(
        self, texts: list[str], extra_metadata: dict[str, Any] | None = None
    ) -> tuple[list[list[float]], dict[str, Any]]:
        """Embed texts and return vectors alongside model metadata."""
        vectors = self.embed(texts)
        metadata: dict[str, Any] = {"embedding_model": self._model}
        if extra_metadata:
            metadata.update(extra_metadata)
        return vectors, metadata
