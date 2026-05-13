# Ingestion Overview

The `IngestPipeline` provides a unified entry point for all source adapters.  Each adapter converts its source into `Chunk` objects; the pipeline embeds and upserts them into Qdrant.

## Running an Ingestion

```python
from src.domain.ingest_pipeline import IngestPipeline
from src.adapters.markdown_adapter import MarkdownAdapter
from src.vector.qdrant_client import QdrantAdapter
from src.vector.embedding_client import EmbeddingClient

qdrant = QdrantAdapter(host="localhost", port=6333, collection="governance")
embedding = EmbeddingClient(url="http://localhost:8001/embed")
pipeline = IngestPipeline(qdrant=qdrant, embedding=embedding)

adapter = MarkdownAdapter()
chunks = adapter.ingest(path="docs/policy.md", metadata={"origin": "policy.md", "domain": "security"})
result = pipeline.run(chunks, incremental=True)
print(result)  # PipelineResult(ingested=12, skipped=0, errors=[])
```

## Incremental Mode

When `incremental=True` (default), the pipeline checks existing chunk IDs in Qdrant before embedding.  Chunks whose `chunk_id` (SHA-256 of content) is already present are skipped.  This avoids redundant embedding calls for unchanged content.

## Adapters

| Adapter | Source | Key options |
|---|---|---|
| `MarkdownAdapter` | `.md` files | `metadata` dict |
| `PdfAdapter` | `.pdf` files | `metadata` dict |
| `GitAdapter` | Git repo | `branch`, `glob_pattern`, `metadata` |
| `WebAdapter` | URL | `metadata` |

## Guides

- [How-To: practical ingestion examples](howto.md) — security policies, PDFs, Git repos, Confluence exports, catalog setup, error handling
- [Markdown Adapter](markdown.md)
- [PDF Adapter](pdf.md)
- [Git Adapter](git.md)
- [Web Adapter](web.md)
