"""Seed the governance knowledge base from all local policy sources.

Usage:
    uv run python scripts/ingestion/seed_all.py [--force]

Options:
    --force   Re-ingest all chunks even if already present (incremental=False)

Edit the SOURCES list below to match your repository layout.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.adapters.git_adapter import GitAdapter  # noqa: E402
from src.adapters.markdown_adapter import MarkdownAdapter  # noqa: E402
from src.adapters.pdf_adapter import PDFAdapter  # noqa: E402
from src.config.settings import settings  # noqa: E402
from src.domain.ingest_pipeline import IngestPipeline  # noqa: E402
from src.vector.embedding_client import EmbeddingClient  # noqa: E402
from src.vector.qdrant_client import QdrantAdapter  # noqa: E402

qdrant    = QdrantAdapter(host=settings.qdrant_host, port=settings.qdrant_port)
embedding = EmbeddingClient(url=settings.embedding_url)
pipeline  = IngestPipeline(qdrant=qdrant, embedding=embedding)

# ---------------------------------------------------------------------------
# Edit SOURCES to match your layout.
# Each entry: (adapter_instance, kwargs_for_ingest)
# ---------------------------------------------------------------------------
md_policy_dir   = Path("policies")
pdf_standard_dir = Path("standards")
git_repo_path   = Path("/repos/platform")

SOURCES: list[tuple] = []

# Markdown policies
if md_policy_dir.exists():
    adapter = MarkdownAdapter()
    for md_file in md_policy_dir.rglob("*.md"):
        SOURCES.append((adapter, dict(
            path=str(md_file),
            metadata={
                "origin":      str(md_file),
                "source_type": "policy",
                "domain":      "security",
                "version_ref": "latest",
                "timestamp":   "2024-01-01",
            },
        )))

# PDF standards
if pdf_standard_dir.exists():
    adapter = PDFAdapter()
    for pdf_file in pdf_standard_dir.rglob("*.pdf"):
        SOURCES.append((adapter, dict(
            path=str(pdf_file),
            metadata={
                "origin":      str(pdf_file),
                "source_type": "standard",
                "domain":      "compliance",
                "version_ref": "latest",
                "timestamp":   "2024-01-01",
            },
        )))

# Git repo standards
if git_repo_path.exists():
    SOURCES.append((GitAdapter(), dict(
        repo_path=str(git_repo_path),
        branch="main",
        glob_pattern="docs/standards/**/*.md",
        metadata={
            "origin":      "platform-repo",
            "source_type": "standard",
            "domain":      "engineering",
            "version_ref": "main",
            "timestamp":   "2024-01-01",
        },
    )))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true",
                        help="Force re-ingest all chunks (incremental=False)")
    args = parser.parse_args()
    incremental = not args.force

    if not SOURCES:
        print("No sources found — edit SOURCES in this script to match your layout.")
        sys.exit(0)

    total_ingested = total_skipped = total_errors = 0

    for adapter, kwargs in SOURCES:
        origin = kwargs.get("metadata", {}).get("origin", "?")
        print(f"  → {origin}", end=" ", flush=True)
        chunks = adapter.ingest(**kwargs)
        result = pipeline.run(chunks, incremental=incremental)
        total_ingested += result.ingested
        total_skipped  += result.skipped
        total_errors   += len(result.errors)
        print(f"ingested={result.ingested} skipped={result.skipped} errors={len(result.errors)}")
        for err in result.errors:
            print(f"    ⚠  {err}")

    print(f"\n✓  Total — ingested={total_ingested}  skipped={total_skipped}  errors={total_errors}")
    if total_errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
