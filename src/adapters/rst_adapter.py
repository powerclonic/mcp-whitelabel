from pathlib import Path
from typing import Any

import httpx
import pypandoc

from src.vector.chunking import Chunk, chunk_markdown


DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


class RstAdapter:
    """Ingest reStructuredText from a local file or a remote URL.

    The RST source is converted to Markdown via pandoc, then chunked by
    heading hierarchy (same strategy as MarkdownAdapter).

    Pandoc is downloaded automatically on first use if not found in PATH.
    Pass ``pandoc_path`` to point at an existing binary and skip the download.

    Examples::

        adapter = RstAdapter()

        # From a local file
        chunks = adapter.ingest("docs/pep-0008.rst", metadata={...})

        # From a raw URL
        chunks = adapter.ingest(
            "https://raw.githubusercontent.com/python/peps/refs/heads/main/peps/pep-0008.rst",
            metadata={...},
        )
    """

    def __init__(self, pandoc_path: str | None = None) -> None:
        self._pandoc_path = pandoc_path
        self._pandoc_ready = False

    def _ensure_pandoc(self) -> None:
        if self._pandoc_ready:
            return
        try:
            pypandoc.get_pandoc_version()
        except OSError:
            from pypandoc.pandoc_download import download_pandoc  # type: ignore[import]
            download_pandoc()
        self._pandoc_ready = True

    def _fetch(self, source: str | Path) -> tuple[str, str]:
        """Return (rst_text, resolved_origin)."""
        raw = str(source)
        if raw.startswith("http://") or raw.startswith("https://"):
            response = httpx.get(
                raw,
                timeout=30,
                follow_redirects=True,
                headers={"User-Agent": DEFAULT_USER_AGENT},
            )
            response.raise_for_status()
            return response.text, raw
        text = Path(raw).read_text(encoding="utf-8")
        return text, raw

    def convert(self, rst_source: str) -> str:
        """Convert an RST string to Markdown and return it."""
        self._ensure_pandoc()
        kwargs: dict[str, Any] = {}
        if self._pandoc_path:
            kwargs["pandoc_path"] = self._pandoc_path
        return pypandoc.convert_text(  # type: ignore[no-any-return]
            rst_source, "md", format="rst", **kwargs
        )

    def ingest(self, path_or_url: str | Path, metadata: dict[str, Any]) -> list[Chunk]:
        """Fetch or read RST, convert to Markdown, and return chunks.

        Args:
            path_or_url: Local file path or ``https://`` URL to raw RST.
            metadata: Chunk metadata (origin, source_type, domain, …).
        """
        rst_text, origin = self._fetch(path_or_url)
        md_text = self.convert(rst_text)

        base_meta: dict[str, Any] = {
            "origin": metadata.get("origin", origin),
            "source_type": metadata.get("source_type", "standard"),
            "version_ref": metadata.get("version_ref", ""),
            "timestamp": metadata.get("timestamp", ""),
            "domain": metadata.get("domain", ""),
            **{k: v for k, v in metadata.items()
               if k not in ("origin", "source_type", "version_ref", "timestamp", "domain")},
        }
        return chunk_markdown(md_text, base_meta)
