# Web Adapter

Ingests a single web page by URL using `httpx` + `BeautifulSoup`.

## Usage

```python
from src.adapters.web_adapter import WebAdapter

adapter = WebAdapter()
chunks = adapter.ingest(
    url="https://example.com/policy",
    metadata={"origin": "example.com/policy", "domain": "legal"},
)
```

## Behaviour

- Fetches the URL with `httpx`; raises on non-2xx responses.
- Extracts visible text from `<body>` using `BeautifulSoup`.
- Applies `chunk_text` for uniform chunk sizing.
