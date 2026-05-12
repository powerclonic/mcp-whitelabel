import fnmatch
from pathlib import Path, PurePosixPath
from typing import Any

import git
from git.objects.blob import Blob as GitBlob

from src.vector.chunking import Chunk, chunk_text


class GitAdapter:
    """Ingest documentation files from a Git repository at a given ref."""

    def ingest(
        self,
        repo_path: str | Path,
        ref: str,
        glob_pattern: str,
        metadata: dict[str, Any],
    ) -> list[Chunk]:
        repo = git.Repo(str(repo_path))
        commit = repo.commit(ref)
        resolved_sha = commit.hexsha

        chunks: list[Chunk] = []
        for item in commit.tree.traverse():
            if not isinstance(item, GitBlob):
                continue
            blob_path = item.path
            if not PurePosixPath("/" + str(blob_path)).match(glob_pattern):
                continue

            content = item.data_stream.read().decode("utf-8", errors="replace")
            file_meta: dict[str, Any] = {
                "origin": str(blob_path),
                "source_type": "git",
                "version_ref": resolved_sha,
                "timestamp": metadata.get("timestamp", ""),
                "domain": metadata.get("domain", ""),
                **{k: v for k, v in metadata.items() if k not in ("version_ref", "timestamp", "domain")},
            }

            if str(blob_path).endswith(".md"):
                from src.vector.chunking import chunk_markdown
                chunks.extend(chunk_markdown(content, file_meta))
            else:
                chunks.extend(chunk_text(content, file_meta))

        return chunks
