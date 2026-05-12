import os
import subprocess
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


class TestMarkdownAdapter:
    def test_ingest_produces_chunks(self) -> None:
        from src.adapters.markdown_adapter import MarkdownAdapter

        adapter = MarkdownAdapter()
        chunks = adapter.ingest(FIXTURES / "sample.md", {"version_ref": "v1.0", "domain": "security"})
        assert len(chunks) > 0

    def test_metadata_completeness(self) -> None:
        from src.adapters.markdown_adapter import MarkdownAdapter

        adapter = MarkdownAdapter()
        chunks = adapter.ingest(FIXTURES / "sample.md", {"version_ref": "abc123", "domain": "security"})
        for c in chunks:
            assert c.metadata["source_type"] == "markdown"
            assert c.metadata["origin"] == str(FIXTURES / "sample.md")
            assert c.metadata["version_ref"] == "abc123"

    def test_heading_path_in_chunks(self) -> None:
        from src.adapters.markdown_adapter import MarkdownAdapter

        adapter = MarkdownAdapter()
        chunks = adapter.ingest(FIXTURES / "sample.md", {})
        paths = [c.metadata.get("heading_path", []) for c in chunks]
        assert any(len(p) > 0 for p in paths)


class TestWebAdapter:
    def test_ingest_local_html(self) -> None:
        from src.adapters.web_adapter import WebAdapter

        adapter = WebAdapter()
        chunks = adapter.ingest(FIXTURES / "sample.html", {"domain": "governance"})
        assert len(chunks) > 0
        full_text = " ".join(c.content for c in chunks)
        assert "Governance" in full_text

    def test_nav_and_footer_stripped(self) -> None:
        from src.adapters.web_adapter import WebAdapter

        adapter = WebAdapter()
        chunks = adapter.ingest(FIXTURES / "sample.html", {})
        full_text = " ".join(c.content for c in chunks)
        assert "Navigation bar" not in full_text
        assert "Footer content" not in full_text

    def test_source_type_default_web(self) -> None:
        from src.adapters.web_adapter import WebAdapter

        adapter = WebAdapter()
        chunks = adapter.ingest(FIXTURES / "sample.html", {})
        assert all(c.metadata["source_type"] == "web" for c in chunks)

    def test_source_type_confluence_export(self) -> None:
        from src.adapters.web_adapter import WebAdapter

        adapter = WebAdapter()
        chunks = adapter.ingest(FIXTURES / "sample.html", {"source_type": "confluence_export"})
        assert all(c.metadata["source_type"] == "confluence_export" for c in chunks)


class TestGitAdapter:
    @pytest.fixture
    def git_repo(self, tmp_path: Path) -> Path:
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        subprocess.run(["git", "init", str(repo_path)], check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=str(repo_path),
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=str(repo_path),
            check=True,
            capture_output=True,
        )
        md_file = repo_path / "README.md"
        md_file.write_text("# Test Repo\n\nThis is a test document.\n")
        txt_file = repo_path / "notes.txt"
        txt_file.write_text("Some plain text notes.")
        subprocess.run(["git", "add", "."], cwd=str(repo_path), check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=str(repo_path),
            check=True,
            capture_output=True,
        )
        return repo_path

    def test_ingest_markdown_files(self, git_repo: Path) -> None:
        from src.adapters.git_adapter import GitAdapter

        adapter = GitAdapter()
        chunks = adapter.ingest(git_repo, "HEAD", "*.md", {"domain": "docs"})
        assert len(chunks) > 0

    def test_version_ref_is_sha(self, git_repo: Path) -> None:
        from src.adapters.git_adapter import GitAdapter

        adapter = GitAdapter()
        chunks = adapter.ingest(git_repo, "HEAD", "**/*", {"domain": "docs"})
        assert len(chunks) > 0
        for c in chunks:
            assert len(c.metadata["version_ref"]) == 40

    def test_ingest_all_files(self, git_repo: Path) -> None:
        from src.adapters.git_adapter import GitAdapter

        adapter = GitAdapter()
        chunks = adapter.ingest(git_repo, "HEAD", "*", {"domain": "docs"})
        sources = {c.metadata["origin"] for c in chunks}
        assert "README.md" in sources or any("README" in s for s in sources)
