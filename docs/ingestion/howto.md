# How-To: Ingest Governance Content

Practical examples for the most common ingestion scenarios.  Each example
assumes the services are running (`docker compose up -d`).

## Setup shared across examples

```python
from src.vector.qdrant_client import QdrantAdapter
from src.vector.embedding_client import EmbeddingClient
from src.domain.ingest_pipeline import IngestPipeline
from src.config.settings import settings

qdrant    = QdrantAdapter(host=settings.qdrant_host, port=settings.qdrant_port,
                          collection=settings.qdrant_collection)
embedding = EmbeddingClient(url=settings.embedding_url)
pipeline  = IngestPipeline(qdrant=qdrant, embedding=embedding)
```

---

## 1 — Security policy (Markdown file)

```python
from src.adapters.markdown_adapter import MarkdownAdapter

chunks = MarkdownAdapter().ingest(
    path="policies/security/container-hardening.md",
    metadata={
        "origin":       "policies/security/container-hardening.md",
        "source_type":  "policy",
        "domain":       "security",
        "version_ref":  "v2.1.0",
        "timestamp":    "2024-06-01",
    },
)
result = pipeline.run(chunks, incremental=True)
print(result)  # PipelineResult(ingested=18, skipped=0, errors=[])
```

**When to use `incremental=False`**: if you edited an existing policy and want
to force-replace every chunk even if the content hash hasn't changed.

```python
result = pipeline.run(chunks, incremental=False)
```

---

## 2 — ISO / regulatory standard (PDF)

```python
from src.adapters.pdf_adapter import PdfAdapter

chunks = PdfAdapter().ingest(
    path="standards/iso27001-annex-a.pdf",
    metadata={
        "origin":       "iso27001-annex-a.pdf",
        "source_type":  "standard",
        "domain":       "compliance",
        "version_ref":  "ISO 27001:2022",
        "timestamp":    "2022-10-25",
    },
)
result = pipeline.run(chunks)
print(result)
```

---

## 3 — All Markdown policies in a Git repository

Useful for ingesting a whole governance repo in one shot.

```python
from src.adapters.git_adapter import GitAdapter

chunks = GitAdapter().ingest(
    repo_path="/repos/governance",
    branch="main",
    glob_pattern="**/*.md",          # all Markdown files, any depth
    metadata={
        "origin":      "governance-repo",
        "source_type": "policy",
        "domain":      "engineering",
        "version_ref": "main",
        "timestamp":   "2024-12-01",
    },
)
result = pipeline.run(chunks)
print(f"ingested={result.ingested}  skipped={result.skipped}  errors={len(result.errors)}")
```

To ingest only ADRs (Architecture Decision Records):

```python
chunks = GitAdapter().ingest(
    repo_path="/repos/platform",
    branch="main",
    glob_pattern="docs/adr/*.md",
    metadata={"origin": "platform-repo", "domain": "architecture"},
)
pipeline.run(chunks)
```

---

## 4 — Public web policy page

```python
from src.adapters.web_adapter import WebAdapter

chunks = WebAdapter().ingest(
    url="https://company.intranet/security/data-classification-policy",
    metadata={
        "origin":      "company.intranet/security/data-classification-policy",
        "source_type": "policy",
        "domain":      "data-governance",
        "version_ref": "2024-Q4",
        "timestamp":   "2024-11-15",
    },
)
pipeline.run(chunks)
```

---

## 5 — Approved library catalog

The catalog drives `check_library_compliance`.  Populate it at server startup
or via a management script:

```python
from datetime import date
from src.catalog.models import LibraryEntry, LibraryStatus
from src.catalog.repository import InMemoryCatalogRepository

catalog = InMemoryCatalogRepository(
    libraries=[
        # ✅ approved versions
        LibraryEntry(
            name="requests", version="2.31.0",
            status=LibraryStatus.approved,
            reason="Stable, no known CVEs.",
            effective_date=date(2024, 1, 15),
            updated_by="platform-team",
        ),
        LibraryEntry(
            name="pydantic", version="2.7.4",
            status=LibraryStatus.approved,
            reason="V2 stable; V1 is forbidden (see below).",
            effective_date=date(2024, 3, 1),
            updated_by="platform-team",
        ),
        LibraryEntry(
            name="fastapi", version="0.111.0",
            status=LibraryStatus.approved,
            reason="Current LTS-equivalent release.",
            effective_date=date(2024, 5, 10),
            updated_by="platform-team",
        ),
        # ⚠️ restricted — allowed with justification
        LibraryEntry(
            name="paramiko", version="3.4.0",
            status=LibraryStatus.restricted,
            reason="Permitted only for jump-host tooling; requires security review.",
            effective_date=date(2024, 2, 1),
            updated_by="security-team",
        ),
        # ❌ forbidden
        LibraryEntry(
            name="pydantic", version="1.10.21",
            status=LibraryStatus.forbidden,
            reason="Pydantic V1 is EOL and contains known deserialization issues.",
            effective_date=date(2024, 3, 1),
            updated_by="platform-team",
        ),
        LibraryEntry(
            name="PyYAML", version="5.4.1",
            status=LibraryStatus.forbidden,
            reason="CVE-2020-14343: unsafe YAML loader. Upgrade to >=6.0.",
            effective_date=date(2023, 8, 1),
            updated_by="security-team",
        ),
    ]
)
```

Pass `catalog` to `register_tools(mcp, catalog=catalog)` (or inject it via
the server factory) so `check_library_compliance` uses the real catalog.

---

## 6 — Confluence export (Markdown)

Export your Confluence space as a ZIP of Markdown files, then ingest the
whole directory:

```python
import os
from pathlib import Path
from src.adapters.markdown_adapter import MarkdownAdapter

adapter = MarkdownAdapter()
all_chunks = []

for md_file in Path("confluence-export/security-space").rglob("*.md"):
    all_chunks.extend(
        adapter.ingest(
            path=str(md_file),
            metadata={
                "origin":      f"confluence/security-space/{md_file.name}",
                "source_type": "policy",
                "domain":      "security",
                "version_ref": "2024-export",
                "timestamp":   "2024-11-01",
            },
        )
    )

result = pipeline.run(all_chunks, incremental=True)
print(result)
```

---

## 7 — Handling errors

The pipeline never aborts on a single bad chunk — it records errors and
continues.  Always check `result.errors` after a large ingestion:

```python
result = pipeline.run(chunks)

if result.errors:
    print(f"⚠  {len(result.errors)} error(s) during ingestion:")
    for err in result.errors:
        print(f"   • {err}")

print(f"✓  ingested={result.ingested}  skipped={result.skipped}")
```

---

## 8 — Full startup ingestion script

A single script to seed the knowledge base from scratch:

```python
#!/usr/bin/env python3
"""Seed the governance knowledge base from all local policy sources."""
from pathlib import Path
from src.adapters.markdown_adapter import MarkdownAdapter
from src.adapters.pdf_adapter import PdfAdapter
from src.adapters.git_adapter import GitAdapter
from src.vector.qdrant_client import QdrantAdapter
from src.vector.embedding_client import EmbeddingClient
from src.domain.ingest_pipeline import IngestPipeline
from src.config.settings import settings

qdrant    = QdrantAdapter(host=settings.qdrant_host, port=settings.qdrant_port,
                          collection=settings.qdrant_collection)
embedding = EmbeddingClient(url=settings.embedding_url)
pipeline  = IngestPipeline(qdrant=qdrant, embedding=embedding)

sources = [
    # Markdown policies directory
    *[
        (MarkdownAdapter(), dict(
            path=str(f),
            metadata={"origin": str(f), "source_type": "policy", "domain": "security"},
        ))
        for f in Path("policies").rglob("*.md")
    ],
    # Regulatory PDFs
    *[
        (PdfAdapter(), dict(
            path=str(f),
            metadata={"origin": str(f), "source_type": "standard", "domain": "compliance"},
        ))
        for f in Path("standards").rglob("*.pdf")
    ],
    # Engineering standards in the platform Git repo
    (GitAdapter(), dict(
        repo_path="/repos/platform",
        branch="main",
        glob_pattern="docs/standards/**/*.md",
        metadata={"origin": "platform-repo", "source_type": "standard", "domain": "engineering"},
    )),
]

total_ingested = total_skipped = total_errors = 0
for adapter, kwargs in sources:
    chunks = adapter.ingest(**kwargs)
    result = pipeline.run(chunks, incremental=True)
    total_ingested += result.ingested
    total_skipped  += result.skipped
    total_errors   += len(result.errors)
    for err in result.errors:
        print(f"ERROR: {err}")

print(f"\nDone — ingested={total_ingested}  skipped={total_skipped}  errors={total_errors}")
```
