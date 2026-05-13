# PDF Adapter

Ingests `.pdf` files using `pdfminer.six`.

## Usage

```python
from src.adapters.pdf_adapter import PDFAdapter

adapter = PDFAdapter()
chunks = adapter.ingest(
    path="docs/standard.pdf",
    metadata={"origin": "standard.pdf", "domain": "compliance"},
)
```

## Behaviour

- Extracts raw text via `pdfminer`; applies `chunk_text` with `chunk_max_size` and `chunk_overlap` from settings.
- Each chunk has `metadata.source_type = "pdf"`.
