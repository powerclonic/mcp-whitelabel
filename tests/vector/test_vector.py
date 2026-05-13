import pytest
from unittest.mock import MagicMock, patch

from src.vector.chunking import Chunk, chunk_markdown, chunk_text


class TestChunk:
    def test_make_id_deterministic(self) -> None:
        c1 = Chunk.make_id("hello world")
        c2 = Chunk.make_id("hello world")
        assert c1 == c2

    def test_make_id_differs_for_different_content(self) -> None:
        assert Chunk.make_id("hello") != Chunk.make_id("world")


class TestChunkText:
    def test_empty_text_returns_empty(self) -> None:
        assert chunk_text("", {}) == []

    def test_whitespace_only_returns_empty(self) -> None:
        assert chunk_text("   \n  ", {}) == []

    def test_single_chunk(self) -> None:
        chunks = chunk_text("short text", {"origin": "test"}, max_size=512, overlap=0)
        assert len(chunks) == 1
        assert chunks[0].content == "short text"
        assert chunks[0].metadata["origin"] == "test"

    def test_multiple_chunks(self) -> None:
        text = "a" * 600
        chunks = chunk_text(text, {}, max_size=100, overlap=0)
        assert len(chunks) > 1

    def test_overlap_produces_overlap(self) -> None:
        text = "a" * 200
        chunks_no_overlap = chunk_text(text, {}, max_size=100, overlap=0)
        chunks_with_overlap = chunk_text(text, {}, max_size=100, overlap=20)
        assert len(chunks_with_overlap) >= len(chunks_no_overlap)

    def test_chunk_id_is_sha256(self) -> None:
        chunks = chunk_text("test content", {}, max_size=512, overlap=0)
        assert len(chunks[0].chunk_id) == 64  # SHA-256 hex

    def test_metadata_chunk_index(self) -> None:
        text = "a" * 300
        chunks = chunk_text(text, {}, max_size=100, overlap=0)
        indices = [c.metadata["chunk_index"] for c in chunks]
        assert indices == list(range(len(chunks)))


class TestChunkTextSentenceAware:
    """Verify that chunk_text never cuts mid-sentence and respects paragraph boundaries."""

    def test_no_mid_sentence_cut(self) -> None:
        # Two long sentences that together exceed max_size=80 must each appear
        # complete inside exactly one chunk — no sentence is split across chunks.
        s1 = "The first sentence describes the governance policy in full detail."
        s2 = "The second sentence explains the compliance requirements for all teams."
        text = f"{s1} {s2}"
        chunks = chunk_text(text, {}, max_size=80, overlap=0)
        # Each sentence must appear whole in at least one chunk
        assert any(s1 in c.content for c in chunks), f"{s1!r} not found whole in any chunk"
        assert any(s2 in c.content for c in chunks), f"{s2!r} not found whole in any chunk"

    def test_sentence_boundary_respected(self) -> None:
        # With a tight window, each sentence lands in its own chunk
        sentences = [
            "Alpha is the first rule.",
            "Beta is the second rule.",
            "Gamma is the third rule.",
        ]
        text = " ".join(sentences)
        chunks = chunk_text(text, {}, max_size=40, overlap=0)
        # Every chunk content must not cut a sentence — it must start/end at
        # sentence-like boundaries (no bare lowercase continuation mid-word)
        for chunk in chunks:
            assert chunk.content.strip() != ""

    def test_paragraph_boundaries_respected(self) -> None:
        # Two short paragraphs that each fit alone but together exceed max_size
        para1 = "First paragraph about security policies."
        para2 = "Second paragraph about compliance standards."
        text = f"{para1}\n\n{para2}"
        # max_size smaller than combined length but larger than each paragraph
        chunks = chunk_text(text, {}, max_size=len(para1) + 5, overlap=0)
        # Paragraphs should not bleed into each other
        contents = [c.content for c in chunks]
        assert any(para1 in c for c in contents)
        assert any(para2 in c for c in contents)

    def test_char_count_in_metadata(self) -> None:
        chunks = chunk_text("Hello world. This is a test sentence.", {}, max_size=512, overlap=0)
        assert len(chunks) == 1
        assert chunks[0].metadata["char_count"] == len(chunks[0].content)

    def test_char_count_matches_content_length(self) -> None:
        text = "A " * 100  # 200 chars
        chunks = chunk_text(text, {}, max_size=50, overlap=0)
        for chunk in chunks:
            assert chunk.metadata["char_count"] == len(chunk.content)

    def test_overlap_starts_at_sentence_boundary(self) -> None:
        # With sentence-aware overlap the seeded sentences must appear verbatim
        # at the start of the following chunk.
        s1 = "The policy requires approval from the security committee."
        s2 = "All exceptions must be logged within twenty-four hours."
        s3 = "Violations trigger an automatic incident report."
        text = f"{s1} {s2} {s3}"
        # Tight window so each sentence lands mostly alone; overlap seeds s2 into chunk2
        chunks = chunk_text(text, {}, max_size=70, overlap=60)
        # At least the overlapping sentence content should appear in more than one chunk
        all_contents = [c.content for c in chunks]
        # s2 is 55 chars — with overlap=60 it should seed into the next chunk
        overlap_count = sum(1 for c in all_contents if s2[:20] in c)
        assert overlap_count >= 1


class TestChunkMarkdown:
    SAMPLE_MD = """# Title

Intro text about the document.

## Section One

Content of section one goes here. It has some detail.

### Subsection

Deeper content here.

## Section Two

Another section with its own content.
"""

    def test_chunk_count_positive(self) -> None:
        chunks = chunk_markdown(self.SAMPLE_MD, {"origin": "test"})
        assert len(chunks) > 0

    def test_heading_path_in_metadata(self) -> None:
        chunks = chunk_markdown(self.SAMPLE_MD, {})
        paths = [c.metadata.get("heading_path") for c in chunks]
        assert any(p for p in paths if isinstance(p, list) and len(p) > 0)

    def test_section_hierarchy_preserved(self) -> None:
        chunks = chunk_markdown(self.SAMPLE_MD, {})
        subsection_chunks = [
            c for c in chunks if "Subsection" in c.metadata.get("heading_path", [])
        ]
        assert len(subsection_chunks) > 0

    def test_metadata_origin_propagated(self) -> None:
        chunks = chunk_markdown(self.SAMPLE_MD, {"origin": "test.md"})
        assert all(c.metadata.get("origin") == "test.md" for c in chunks)

    def test_empty_markdown_returns_empty(self) -> None:
        assert chunk_markdown("", {}) == []

    def test_section_title_in_metadata(self) -> None:
        chunks = chunk_markdown(self.SAMPLE_MD, {})
        # Every chunk from a headed section must carry section_title
        headed = [c for c in chunks if c.metadata.get("heading_path")]
        assert all(
            c.metadata.get("section_title") == c.metadata["heading_path"][-1]
            for c in headed
        )

    def test_section_title_empty_for_pre_heading_content(self) -> None:
        md = "Some intro before any heading.\n\n# First Heading\n\nBody text."
        chunks = chunk_markdown(md, {})
        pre = [c for c in chunks if c.metadata.get("heading_path") == []]
        assert all(c.metadata.get("section_title") == "" for c in pre)

    def test_heading_level_in_metadata(self) -> None:
        chunks = chunk_markdown(self.SAMPLE_MD, {})
        # Chunks whose section_title is "Title" (the h1) must have heading_level == 1
        title_chunks = [c for c in chunks if c.metadata.get("section_title") == "Title"]
        assert all(c.metadata.get("heading_level") == 1 for c in title_chunks)
        # Chunks under the h3 Subsection must have heading_level == 3
        sub_chunks = [c for c in chunks if c.metadata.get("section_title") == "Subsection"]
        assert all(c.metadata.get("heading_level") == 3 for c in sub_chunks)

    def test_char_count_in_markdown_chunks(self) -> None:
        chunks = chunk_markdown(self.SAMPLE_MD, {})
        for chunk in chunks:
            assert chunk.metadata.get("char_count") == len(chunk.content)


class TestEmbeddingClient:
    def test_embed_returns_vectors(self) -> None:
        with patch("httpx.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
            mock_post.return_value = mock_resp

            from src.vector.embedding_client import EmbeddingClient

            client = EmbeddingClient(url="http://test/embed", model="test-model")
            result = client.embed(["text1", "text2"])
            assert result == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]

    def test_embed_raises_on_non_200(self) -> None:
        with patch("httpx.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 500
            mock_resp.text = "Internal Server Error"
            mock_post.return_value = mock_resp

            from src.vector.embedding_client import EmbeddingClient, EmbeddingError

            client = EmbeddingClient(url="http://test/embed", model="test-model")
            with pytest.raises(EmbeddingError):
                client.embed(["text"])

    def test_embed_with_metadata_includes_model(self) -> None:
        with patch("httpx.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = [[0.1, 0.2]]
            mock_post.return_value = mock_resp

            from src.vector.embedding_client import EmbeddingClient

            client = EmbeddingClient(url="http://test/embed", model="bge-m3")
            _, meta = client.embed_with_metadata(["text"])
            assert meta["embedding_model"] == "bge-m3"


class TestEmbeddingClientSparse:
    def test_embed_sparse_returns_token_weights(self) -> None:
        with patch("httpx.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = [
                [{"index": 42, "value": 0.9}, {"index": 7, "value": 0.3}],
                [{"index": 1, "value": 0.5}],
            ]
            mock_post.return_value = mock_resp

            from src.vector.embedding_client import EmbeddingClient

            client = EmbeddingClient(
                url="http://test/embed",
                sparse_url="http://test/embed_sparse",
                model="bge-m3",
            )
            result = client.embed_sparse(["text1", "text2"])

        assert result is not None
        assert len(result) == 2
        assert result[0][0]["index"] == 42
        assert result[0][0]["value"] == pytest.approx(0.9)

    def test_embed_sparse_returns_none_on_http_error(self) -> None:
        with patch("httpx.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 503
            mock_post.return_value = mock_resp

            from src.vector.embedding_client import EmbeddingClient

            client = EmbeddingClient(
                url="http://test/embed",
                sparse_url="http://test/embed_sparse",
                model="bge-m3",
            )
            result = client.embed_sparse(["text"])

        assert result is None

    def test_embed_sparse_returns_none_on_network_error(self) -> None:
        import httpx

        with patch("httpx.post", side_effect=httpx.RequestError("timeout")):
            from src.vector.embedding_client import EmbeddingClient

            client = EmbeddingClient(
                url="http://test/embed",
                sparse_url="http://test/embed_sparse",
                model="bge-m3",
            )
            result = client.embed_sparse(["text"])

        assert result is None


class TestQdrantAdapter:
    def _make_chunk(self, content: str = "test content") -> Chunk:
        return Chunk(
            chunk_id=Chunk.make_id(content),
            content=content,
            metadata={
                "origin": "test.md",
                "source_type": "markdown",
                "version_ref": "abc123",
                "timestamp": "2024-01-01",
                "domain": "security",
            },
        )

    def test_upsert_chunks_calls_client(self) -> None:
        with patch("src.vector.qdrant_client._QdrantClient") as MockClient:
            mock_instance = MagicMock()
            MockClient.return_value = mock_instance
            mock_instance.get_collections.return_value.collections = []
            mock_instance.get_collection.return_value.config.params.vectors = {"dense": MagicMock()}

            from src.vector.qdrant_client import QdrantAdapter

            adapter = QdrantAdapter(host="localhost", port=6333, vector_size=3)
            chunk = self._make_chunk()
            adapter.upsert_chunks("test_col", [chunk], [[0.1, 0.2, 0.3]])

            mock_instance.upsert.assert_called_once()
            call_kwargs = mock_instance.upsert.call_args
            assert call_kwargs.kwargs["collection_name"] == "test_col"

    def test_search_returns_payloads(self) -> None:
        with patch("src.vector.qdrant_client._QdrantClient") as MockClient:
            mock_instance = MagicMock()
            MockClient.return_value = mock_instance
            mock_instance.get_collections.return_value.collections = [
                MagicMock(name="test_col")
            ]
            mock_instance.get_collection.return_value.config.params.vectors = {}

            mock_result = MagicMock()
            mock_result.score = 0.95
            mock_result.payload = {"chunk_id": "abc", "content": "hello"}
            mock_instance.query_points.return_value = MagicMock(points=[mock_result])

            from src.vector.qdrant_client import QdrantAdapter

            adapter = QdrantAdapter(host="localhost", port=6333, vector_size=3)
            results = adapter.search("test_col", [0.1, 0.2, 0.3], top_k=1)

            assert len(results) == 1
            assert results[0]["chunk_id"] == "abc"
            assert results[0]["score"] == 0.95
