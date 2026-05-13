# Git Adapter

Ingests text files from a Git repository by branch and glob pattern.

## Usage

```python
from src.adapters.git_adapter import GitAdapter

adapter = GitAdapter()
chunks = adapter.ingest(
    repo_path="/path/to/repo",
    branch="main",
    glob_pattern="**/*.md",
    metadata={"origin": "my-repo", "domain": "engineering"},
)
```

## Behaviour

- Uses `gitpython` to traverse blobs matching `glob_pattern` on `branch`.
- Supports `**/*` glob patterns via `PurePosixPath.match`.
- Skips binary files; decodes text as UTF-8 (ignores errors).
- Each blob becomes a separate set of chunks with `metadata.source = <blob_path>`.
