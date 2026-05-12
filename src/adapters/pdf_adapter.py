from pathlib import Path
from typing import Any

import pypdf

from src.vector.chunking import Chunk, chunk_text


class PDFAdapter:
    """Ingest a PDF file page by page and return text chunks."""

    def ingest(self, path: str | Path, metadata: dict[str, Any]) -> list[Chunk]:
        reader = pypdf.PdfReader(str(path))
        chunks: list[Chunk] = []
        for page_num, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            if not text.strip():
                continue
            page_meta: dict[str, Any] = {
                "origin": str(path),
                "source_type": "pdf",
                "version_ref": metadata.get("version_ref", ""),
                "timestamp": metadata.get("timestamp", ""),
                "domain": metadata.get("domain", ""),
                "page_number": page_num,
                **{k: v for k, v in metadata.items() if k not in ("version_ref", "timestamp", "domain")},
            }
            chunks.extend(chunk_text(text, page_meta))
        return chunks
