# Retention Policy and Snapshot Guide

## Active-Version Policy

The governance server maintains a single **active version** of each policy document and library catalog entry in the Qdrant collection.  When a document is re-ingested:

1. The ingestion pipeline computes a `content_hash` for each chunk.
2. Chunks whose `content_hash` already exists in the vector store are **skipped** (incremental mode).
3. Chunks with a new `content_hash` are upserted, overwriting the previous version's payload for that chunk ID.

This means the active collection always reflects the latest ingested version of each document.

## Periodic Snapshot Policy

To enable rollback and audit, the Qdrant collection must be snapshotted **at minimum once per week**, and additionally before any bulk re-ingestion that modifies existing policies.

| Snapshot event | Minimum frequency |
|---|---|
| Scheduled | Weekly (e.g., every Sunday 02:00 UTC) |
| Pre-ingestion | Before any `ingest_pipeline.run()` that targets existing chunks |
| Post-release | After each governance document release |

Snapshots are stored on the host volume mounted at `/qdrant_storage/snapshots/` (see `docker-compose.yml`).

## Snapshot Creation

```bash
# Create a named snapshot
curl -X POST \
  "http://localhost:6333/collections/governance/snapshots" \
  -H "Content-Type: application/json"
```

The response includes a `name` field (e.g., `governance-1-2024-01-15-120000.snapshot`).  Record this name for restore operations.

## Snapshot Restore Procedure

Follow these steps to restore a collection from a snapshot:

1. **Stop the governance server** to prevent writes during restore:

   ```bash
   docker compose stop server
   ```

2. **Identify the target snapshot** by listing available snapshots:

   ```bash
   curl http://localhost:6333/collections/governance/snapshots
   ```

3. **Delete the current collection** (destructive — ensure you have the snapshot):

   ```bash
   curl -X DELETE http://localhost:6333/collections/governance
   ```

4. **Recreate the collection** with the correct vector configuration:

   ```bash
   curl -X PUT http://localhost:6333/collections/governance \
     -H "Content-Type: application/json" \
     -d '{"vectors": {"size": 1024, "distance": "Cosine"}}'
   ```

5. **Restore the snapshot** by uploading the snapshot file:

   ```bash
   curl -X POST \
     "http://localhost:6333/collections/governance/snapshots/upload" \
     -H "Content-Type: multipart/form-data" \
     -F "snapshot=@/qdrant_storage/snapshots/<snapshot-name>.snapshot"
   ```

6. **Verify the restore** by checking collection info:

   ```bash
   curl http://localhost:6333/collections/governance
   ```

   Confirm `vectors_count` matches the pre-restore count.

7. **Restart the governance server**:

   ```bash
   docker compose start server
   ```

## Related

- [Architecture Overview](../architecture/overview.md)
- [Ingestion Guide](../ingestion/overview.md)
- README quick-start (root `README.md`)
