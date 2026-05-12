from pathlib import Path
from typing import Any

from src.vector.chunking import Chunk, chunk_markdown


class MarkdownAdapter:
    """Ingest a Markdown file and return chunks with heading hierarchy metadata."""

    def ingest(self, path: str | Path, metadata: dict[str, Any]) -> list[Chunk]:
        text = Path(path).read_text(encoding="utf-8")
        base_meta: dict[str, Any] = {
            "origin": str(path),
            "source_type": "markdown",
            "version_ref": metadata.get("version_ref", ""),
            "timestamp": metadata.get("timestamp", ""),
            "domain": metadata.get("domain", ""),
            **{k: v for k, v in metadata.items() if k not in ("version_ref", "timestamp", "domain")},
        }
        return chunk_markdown(text, base_meta)
