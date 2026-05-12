from pathlib import Path
from typing import Any

import httpx
from bs4 import BeautifulSoup

from src.vector.chunking import Chunk, chunk_text


class WebAdapter:
    """Ingest a local HTML file or fetch a URL and return text chunks."""

    def ingest(self, path_or_url: str | Path, metadata: dict[str, Any]) -> list[Chunk]:
        raw = str(path_or_url)
        if raw.startswith("http://") or raw.startswith("https://"):
            html = httpx.get(raw, timeout=30).text
            origin = raw
        else:
            html = Path(raw).read_text(encoding="utf-8")
            origin = str(raw)

        soup = BeautifulSoup(html, "lxml")
        for tag in soup(["script", "style", "nav", "footer", "head"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)

        source_type = metadata.get("source_type", "web")
        base_meta: dict[str, Any] = {
            "origin": origin,
            "source_type": source_type,
            "version_ref": metadata.get("version_ref", ""),
            "timestamp": metadata.get("timestamp", ""),
            "domain": metadata.get("domain", ""),
            **{k: v for k, v in metadata.items() if k not in ("source_type", "version_ref", "timestamp", "domain")},
        }
        return chunk_text(text, base_meta)
