# Governance Update Guide

This guide explains how to update the governance knowledge base when policies, standards, or the library catalog change.

## Updating a Policy Document

1. Edit or replace the source document (e.g., `docs/policy.md`).
2. Run the ingestion pipeline for the updated file:

   ```python
   from src.domain.ingest_pipeline import IngestPipeline
   from src.adapters.markdown_adapter import MarkdownAdapter
   from src.vector.qdrant_client import QdrantAdapter
   from src.vector.embedding_client import EmbeddingClient
   from src.config.settings import settings

   qdrant = QdrantAdapter(host=settings.qdrant_host, port=settings.qdrant_port, collection=settings.qdrant_collection)
   embedding = EmbeddingClient(url=settings.embedding_url)
   pipeline = IngestPipeline(qdrant=qdrant, embedding=embedding)

   adapter = MarkdownAdapter()
   chunks = adapter.ingest(path="docs/policy.md", metadata={"origin": "policy.md", "version_ref": "v2.0.0"})
   result = pipeline.run(chunks, incremental=False)  # force-upsert changed content
   print(result)
   ```

3. Verify by running a `search_governance` query related to the changed policy.

## Updating the Library Catalog

The catalog is currently held in-memory (`InMemoryCatalogRepository`).  To persist catalog entries:

1. Extend `CatalogRepository` with a database-backed implementation.
2. Seed it from a YAML/JSON file at startup.

Until then, populate catalog entries via code or a startup script.

## Snapshotting Before Updates

Always create a Qdrant snapshot before bulk re-ingestion (see [Retention Policy](../operations/retention.md)).
