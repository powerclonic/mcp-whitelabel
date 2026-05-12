import hashlib
import re
from dataclasses import dataclass, field
from typing import Any

from src.config.settings import settings


@dataclass
class Chunk:
    chunk_id: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def make_id(content: str) -> str:
        return hashlib.sha256(content.encode()).hexdigest()


def chunk_text(
    text: str,
    metadata: dict[str, Any],
    max_size: int | None = None,
    overlap: int | None = None,
) -> list[Chunk]:
    max_size = max_size if max_size is not None else settings.chunk_max_size
    overlap = overlap if overlap is not None else settings.chunk_overlap
    text = text.strip()
    if not text:
        return []

    chunks: list[Chunk] = []
    start = 0
    while start < len(text):
        end = start + max_size
        content = text[start:end].strip()
        if content:
            chunks.append(
                Chunk(
                    chunk_id=Chunk.make_id(content),
                    content=content,
                    metadata={**metadata, "chunk_index": len(chunks)},
                )
            )
        start = end - overlap if end < len(text) else len(text)
    return chunks


def chunk_markdown(
    text: str,
    metadata: dict[str, Any],
    max_size: int | None = None,
    overlap: int | None = None,
) -> list[Chunk]:
    """Split Markdown text into chunks, preserving section heading hierarchy in metadata."""
    max_size = max_size if max_size is not None else settings.chunk_max_size
    overlap = overlap if overlap is not None else settings.chunk_overlap

    heading_re = re.compile(r"^(#{1,6})\s+(.+)", re.MULTILINE)

    sections: list[tuple[list[str], str]] = []  # (heading_path, body)
    heading_stack: list[str] = []
    last_pos = 0

    for match in heading_re.finditer(text):
        body = text[last_pos : match.start()].strip()
        if body:
            sections.append((list(heading_stack), body))
        level = len(match.group(1))
        heading_stack = heading_stack[: level - 1] + [match.group(2).strip()]
        last_pos = match.end()

    tail = text[last_pos:].strip()
    if tail:
        sections.append((list(heading_stack), tail))

    chunks: list[Chunk] = []
    for heading_path, body in sections:
        section_meta = {**metadata, "heading_path": heading_path}
        for chunk in chunk_text(body, section_meta, max_size, overlap):
            chunk.metadata["heading_path"] = heading_path
            chunks.append(chunk)
    return chunks
