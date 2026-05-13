import hashlib
import re
from dataclasses import dataclass, field
from typing import Any

from src.config.settings import settings

# Conservative sentence boundary detector.
#
# Splits on end-of-sentence punctuation (.!?) followed by whitespace and an
# uppercase letter (or opening bracket), which covers the vast majority of
# English and Portuguese sentence endings while avoiding false positives on
# abbreviations like "e.g. something" or decimal numbers like "v2.0 adds".
#
# Two lookbehind alternatives handle optional closing quotes:
#   (?<=[.!?]["'])  — sentence ends with punctuation + closing quote (e.g. `."`)
#   (?<=[.!?])      — sentence ends with bare punctuation
# Using two fixed-width alternatives instead of a variable-width `["\']?`
# ensures the closing quote stays attached to the preceding sentence.
#
# The lookahead `[A-ZÀ-ÖØ-Ý\(\"\[]` covers ASCII uppercase AND Latin-1
# supplement uppercase letters (including all Portuguese accented capitals:
# À Á Â Ã Ç É Ê Í Ó Ô Õ Ú), so sentence starts with e.g. "Última análise."
# are detected correctly.
_SENTENCE_END_RE = re.compile(
    r'(?:(?<=[.!?]["\'])|(?<=[.!?]))\s+(?=[A-ZÀ-ÖØ-Ý\(\"\[])'
)


@dataclass
class Chunk:
    chunk_id: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def make_id(content: str) -> str:
        return hashlib.sha256(content.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _split_paragraphs(text: str) -> list[str]:
    """Split text into paragraphs separated by one or more blank lines."""
    return [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]


def _split_sentences(text: str) -> list[str]:
    """Split a paragraph into individual sentences.

    Uses a conservative boundary that only triggers when sentence-ending
    punctuation is followed by whitespace and an uppercase letter.  This
    avoids splitting on common abbreviations (``e.g.``, ``i.e.``, ``vs.``)
    and decimal numbers.
    """
    parts = _SENTENCE_END_RE.split(text)
    return [p.strip() for p in parts if p.strip()]


def _char_split(text: str, max_size: int, overlap: int) -> list[str]:
    """Hard character split — last resort for tokens that individually exceed *max_size*.

    ``overlap`` is clamped to ``max_size - 1`` so the sliding window always
    advances by at least one character, preventing an infinite loop when the
    caller passes ``overlap >= max_size``.
    """
    overlap = max(0, min(overlap, max_size - 1))
    parts: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_size, len(text))
        parts.append(text[start:end])
        if end >= len(text):
            break
        start = end - overlap
    return parts


def _overlap_seed(buffer: list[str], overlap: int) -> list[str]:
    """Return the tail of *buffer* whose total joined length fits within *overlap* chars."""
    if overlap <= 0:
        return []
    seed: list[str] = []
    seed_chars = 0
    for unit in reversed(buffer):
        # +1 for the space separator added by " ".join when seed is non-empty
        needed = len(unit) + (1 if seed else 0)
        if seed_chars + needed > overlap:
            break
        seed.insert(0, unit)
        seed_chars += needed
    return seed


def _build_chunks(
    units: list[str],
    max_size: int,
    overlap: int,
    metadata: dict[str, Any],
    chunk_index_start: int = 0,
) -> list[Chunk]:
    """Greedily accumulate *units* (sentences / paragraphs) into :class:`Chunk` objects.

    Algorithm
    ---------
    * Units are appended to a running buffer until the next unit would push
      the buffer past *max_size* characters.
    * When the buffer is full it is emitted as a chunk and a new buffer is
      seeded with whole units from the tail of the previous buffer (up to
      *overlap* characters), so every chunk begins at a sentence boundary.
    * Units that individually exceed *max_size* are hard-split at character
      boundaries with :func:`_char_split` as a last resort (e.g. long code
      lines, tables, or pathological inputs like repeated characters).
    """
    chunks: list[Chunk] = []
    buffer: list[str] = []

    def _buffer_text() -> str:
        return " ".join(buffer)

    def _flush() -> None:
        content = _buffer_text().strip()
        if content:
            chunks.append(
                Chunk(
                    chunk_id=Chunk.make_id(content),
                    content=content,
                    metadata={
                        **metadata,
                        "chunk_index": chunk_index_start + len(chunks),
                        "char_count": len(content),
                    },
                )
            )

    for raw_unit in units:
        unit = raw_unit.strip()
        if not unit:
            continue

        unit_len = len(unit)

        # ── Unit is larger than the entire window → flush, then hard-split ──
        if unit_len > max_size:
            seed: list[str] = []
            if buffer:
                _flush()
                seed = _overlap_seed(buffer, overlap)
                buffer = []
            # Combine the overlap seed with the first hard-split fragment so it
            # is not emitted as a standalone micro-chunk.
            first_part = True
            for raw_part in _char_split(unit, max_size, overlap):
                part = raw_part.strip()
                if not part:
                    continue
                if first_part and seed:
                    buffer = seed + [part]
                    first_part = False
                else:
                    if buffer:
                        _flush()
                    buffer = [part]
                    first_part = False
            continue

        # ── Adding this unit would overflow the buffer → flush first ──
        sep = 1 if buffer else 0
        if buffer and len(_buffer_text()) + sep + unit_len > max_size:
            _flush()
            # Bound the seed so that seed_chars + sep + unit_len <= max_size,
            # preventing the buffer from exceeding max_size after appending unit.
            max_seed = max(0, max_size - unit_len - 1)
            buffer = _overlap_seed(buffer, min(overlap, max_seed))

        buffer.append(unit)

    if buffer:
        _flush()

    return chunks


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def chunk_text(
    text: str,
    metadata: dict[str, Any],
    max_size: int | None = None,
    overlap: int | None = None,
) -> list[Chunk]:
    """Paragraph- and sentence-aware text chunking.

    Splitting hierarchy (coarsest → finest):

    1. **Paragraphs** — blank-line-separated blocks are treated as independent
       units.  Short paragraphs that fit within *max_size* are kept whole.
    2. **Sentences** — paragraphs whose sentences are accumulated until the
       buffer reaches *max_size*.  The boundary detector avoids cutting on
       abbreviations or decimal numbers.
    3. **Characters** — sentences that individually exceed *max_size* are
       hard-split as a last resort (e.g. long code lines or tables).

    Overlap is sentence-aware: the new chunk is seeded with whole sentences
    from the tail of the previous chunk (up to *overlap* characters) so every
    chunk starts at a sentence boundary.

    Every :class:`Chunk` receives:

    * ``chunk_index`` — zero-based position within this call's result list.
    * ``char_count``  — character length of the chunk's content.
    """
    max_size = max_size if max_size is not None else settings.chunk_max_size
    overlap = overlap if overlap is not None else settings.chunk_overlap
    text = text.strip()
    if not text:
        return []

    units: list[str] = []
    for para in _split_paragraphs(text):
        sentences = _split_sentences(para)
        units.extend(sentences if sentences else [para])

    return _build_chunks(units, max_size, overlap, metadata)


def chunk_markdown(
    text: str,
    metadata: dict[str, Any],
    max_size: int | None = None,
    overlap: int | None = None,
) -> list[Chunk]:
    """Split Markdown into sentence-aware chunks preserving section hierarchy.

    Each ATX-heading section (``#`` … ``######``) is chunked independently
    using :func:`chunk_text`.  Every chunk receives the following metadata:

    * ``heading_path``  — full breadcrumb list from root to the section's own
      heading, e.g. ``["Architecture", "Storage", "Qdrant"]``.
    * ``section_title`` — the most specific heading (last element of
      ``heading_path``).  Empty string for content that precedes all headings.
    * ``heading_level`` — ATX depth (1–6) of the section.  ``0`` for content
      that precedes the first heading.
    * ``chunk_index``   — position within the section's own chunk list.
    * ``char_count``    — character length of the chunk's content.
    """
    max_size = max_size if max_size is not None else settings.chunk_max_size
    overlap = overlap if overlap is not None else settings.chunk_overlap

    heading_re = re.compile(r"^(#{1,6})\s+(.+)", re.MULTILINE)

    # Each entry: (heading_path, heading_level, body_text)
    sections: list[tuple[list[str], int, str]] = []
    heading_stack: list[str] = []
    last_level = 0
    last_pos = 0

    for match in heading_re.finditer(text):
        body = text[last_pos : match.start()].strip()
        if body:
            sections.append((list(heading_stack), last_level, body))
        level = len(match.group(1))
        heading_stack = heading_stack[: level - 1] + [match.group(2).strip()]
        last_level = level
        last_pos = match.end()

    tail = text[last_pos:].strip()
    if tail:
        sections.append((list(heading_stack), last_level, tail))

    chunks: list[Chunk] = []
    for heading_path, heading_level, body in sections:
        section_meta: dict[str, Any] = {
            **metadata,
            "heading_path": heading_path,
            "section_title": heading_path[-1] if heading_path else "",
            "heading_level": heading_level,
        }
        for chunk in chunk_text(body, section_meta, max_size, overlap):
            # Reinforce heading keys — chunk_text injects chunk_index / char_count
            # into metadata but must not clobber the heading fields.
            chunk.metadata["heading_path"] = heading_path
            chunk.metadata["section_title"] = heading_path[-1] if heading_path else ""
            chunk.metadata["heading_level"] = heading_level
            chunks.append(chunk)

    return chunks
