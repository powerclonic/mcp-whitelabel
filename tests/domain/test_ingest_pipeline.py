from unittest.mock import MagicMock

from src.vector.chunking import Chunk


def _make_chunk(content: str = "test content") -> Chunk:
    return Chunk(
        chunk_id=Chunk.make_id(content),
        content=content,
        metadata={"origin": "test.md", "source_type": "markdown", "version_ref": "v1"},
    )


class TestIngestPipeline:
    def test_ingest_new_chunks(self) -> None:
        from src.domain.ingest_pipeline import IngestPipeline

        mock_qdrant = MagicMock()
        mock_qdrant.chunk_exists.return_value = False
        mock_embedding = MagicMock()
        mock_embedding.embed.return_value = [[0.1] * 3]

        pipeline = IngestPipeline(qdrant=mock_qdrant, embedding=mock_embedding, collection="test")
        chunk = _make_chunk()
        result = pipeline.run([chunk], incremental=True)

        assert result.ingested == 1
        assert result.skipped == 0
        assert result.errors == []
        mock_qdrant.upsert_chunks.assert_called_once()

    def test_skip_existing_chunks(self) -> None:
        from src.domain.ingest_pipeline import IngestPipeline

        mock_qdrant = MagicMock()
        mock_qdrant.chunk_exists.return_value = True
        mock_embedding = MagicMock()

        pipeline = IngestPipeline(qdrant=mock_qdrant, embedding=mock_embedding, collection="test")
        chunk = _make_chunk()
        result = pipeline.run([chunk], incremental=True)

        assert result.ingested == 0
        assert result.skipped == 1
        mock_embedding.embed.assert_not_called()

    def test_non_incremental_ignores_exists(self) -> None:
        from src.domain.ingest_pipeline import IngestPipeline

        mock_qdrant = MagicMock()
        mock_embedding = MagicMock()
        mock_embedding.embed.return_value = [[0.1] * 3]

        pipeline = IngestPipeline(qdrant=mock_qdrant, embedding=mock_embedding, collection="test")
        chunk = _make_chunk()
        result = pipeline.run([chunk], incremental=False)

        assert result.ingested == 1
        mock_qdrant.chunk_exists.assert_not_called()

    def test_embedding_error_captured(self) -> None:
        from src.domain.ingest_pipeline import IngestPipeline
        from src.vector.embedding_client import EmbeddingError

        mock_qdrant = MagicMock()
        mock_qdrant.chunk_exists.return_value = False
        mock_embedding = MagicMock()
        mock_embedding.embed.side_effect = EmbeddingError("service down")

        pipeline = IngestPipeline(qdrant=mock_qdrant, embedding=mock_embedding, collection="test")
        chunk = _make_chunk()
        result = pipeline.run([chunk], incremental=True)

        assert result.ingested == 0
        assert len(result.errors) == 1
        assert "embedding failed" in result.errors[0]

    def test_upsert_error_captured(self) -> None:
        from src.domain.ingest_pipeline import IngestPipeline

        mock_qdrant = MagicMock()
        mock_qdrant.chunk_exists.return_value = False
        mock_qdrant.upsert_chunks.side_effect = RuntimeError("qdrant down")
        mock_embedding = MagicMock()
        mock_embedding.embed.return_value = [[0.1] * 3]

        pipeline = IngestPipeline(qdrant=mock_qdrant, embedding=mock_embedding, collection="test")
        chunk = _make_chunk()
        result = pipeline.run([chunk], incremental=True)

        assert result.ingested == 0
        assert len(result.errors) == 1
        assert "upsert failed" in result.errors[0]

    def test_empty_chunks_returns_zero(self) -> None:
        from src.domain.ingest_pipeline import IngestPipeline

        mock_qdrant = MagicMock()
        mock_embedding = MagicMock()

        pipeline = IngestPipeline(qdrant=mock_qdrant, embedding=mock_embedding, collection="test")
        result = pipeline.run([], incremental=True)

        assert result.ingested == 0
        assert result.skipped == 0
        assert result.errors == []
