# Markdown Adapter

Ingests `.md` files, preserving section hierarchy in chunk metadata.

## Usage

```python
from src.adapters.markdown_adapter import MarkdownAdapter

adapter = MarkdownAdapter()
chunks = adapter.ingest(
    path="docs/policy.md",
    metadata={
        "origin": "docs/policy.md",
        "domain": "security",
        "version_ref": "v1.2.0",
    },
)
```

## Behaviour

- Splits on `##`/`###` headings; each section becomes one or more chunks.
- Chunk `metadata` includes `heading_path` (e.g., `"Overview > Authentication"`).
- Each chunk carries the provided `metadata` dict merged with heading and source info.
