"""Tests for RstAdapter — file path and URL ingestion."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.adapters.rst_adapter import RstAdapter

SIMPLE_RST = """\
Introduction
============

This is the first paragraph of the introduction.
It spans multiple lines.

Style Guide
-----------

Use four spaces for indentation.
Never mix tabs and spaces.
"""

EXPECTED_HEADING = "Introduction"


@pytest.fixture()
def adapter(tmp_path: Path) -> RstAdapter:
    inst = RstAdapter()
    # Patch _ensure_pandoc to avoid downloading pandoc in CI
    inst._pandoc_ready = True
    return inst


def _mock_convert(adapter: RstAdapter, rst: str) -> str:
    """Run convert() with pandoc mocked to a simple RST→MD transform."""
    with patch("pypandoc.convert_text") as mock_ct:
        # Return a minimal but structurally valid Markdown
        mock_ct.return_value = (
            "# Introduction\n\n"
            "This is the first paragraph of the introduction.\n"
            "It spans multiple lines.\n\n"
            "## Style Guide\n\n"
            "Use four spaces for indentation.\n"
            "Never mix tabs and spaces.\n"
        )
        return adapter.convert(rst)


# ---------------------------------------------------------------------------
# convert()
# ---------------------------------------------------------------------------

def test_convert_calls_pypandoc(adapter: RstAdapter) -> None:
    with patch("pypandoc.convert_text", return_value="# Hello\n\nWorld\n") as mock_ct:
        result = adapter.convert("Hello\n=====\n\nWorld\n")
    mock_ct.assert_called_once_with("Hello\n=====\n\nWorld\n", "md", format="rst")
    assert result == "# Hello\n\nWorld\n"


def test_convert_passes_pandoc_path() -> None:
    inst = RstAdapter(pandoc_path="/usr/local/bin/pandoc")
    inst._pandoc_ready = True
    with patch("pypandoc.convert_text", return_value="# X\n") as mock_ct:
        inst.convert("X\n=\n")
    mock_ct.assert_called_once_with("X\n=\n", "md", format="rst", pandoc_path="/usr/local/bin/pandoc")


# ---------------------------------------------------------------------------
# ingest() — local file
# ---------------------------------------------------------------------------

def test_ingest_file(adapter: RstAdapter, tmp_path: Path) -> None:
    rst_file = tmp_path / "guide.rst"
    rst_file.write_text(SIMPLE_RST, encoding="utf-8")

    with patch.object(adapter, "convert", return_value=(
        "# Introduction\n\nFirst paragraph.\n\n## Style Guide\n\nUse four spaces.\n"
    )):
        chunks = adapter.ingest(rst_file, metadata={
            "source_type": "standard",
            "domain": "engineering",
            "version_ref": "v1",
            "timestamp": "2024-01-01",
        })

    assert len(chunks) >= 1
    origins = {c.metadata["origin"] for c in chunks}
    assert str(rst_file) in origins
    domains = {c.metadata["domain"] for c in chunks}
    assert "engineering" in domains


def test_ingest_file_sets_origin_from_metadata(adapter: RstAdapter, tmp_path: Path) -> None:
    rst_file = tmp_path / "pep.rst"
    rst_file.write_text("Title\n=====\n\nText.\n", encoding="utf-8")

    with patch.object(adapter, "convert", return_value="# Title\n\nText.\n"):
        chunks = adapter.ingest(rst_file, metadata={
            "origin": "custom-origin",
            "source_type": "standard",
            "domain": "engineering",
            "version_ref": "v1",
            "timestamp": "2024-01-01",
        })

    assert all(c.metadata["origin"] == "custom-origin" for c in chunks)


# ---------------------------------------------------------------------------
# ingest() — URL
# ---------------------------------------------------------------------------

def test_ingest_url(adapter: RstAdapter) -> None:
    fake_rst = "PEP 8\n=====\n\nStyle guide for Python code.\n"
    fake_md = "# PEP 8\n\nStyle guide for Python code.\n"

    mock_response = MagicMock()
    mock_response.text = fake_rst
    mock_response.raise_for_status = MagicMock()

    url = "https://raw.githubusercontent.com/python/peps/refs/heads/main/peps/pep-0008.rst"

    with patch("httpx.get", return_value=mock_response) as mock_get, \
         patch.object(adapter, "convert", return_value=fake_md):
        chunks = adapter.ingest(url, metadata={
            "source_type": "standard",
            "domain": "engineering",
            "version_ref": "pep-0008",
            "timestamp": "2001-07-05",
        })

    mock_get.assert_called_once_with(url, timeout=30, follow_redirects=True)
    assert len(chunks) >= 1
    assert all(c.metadata["origin"] == url for c in chunks)
    assert all(c.metadata["domain"] == "engineering" for c in chunks)


def test_ingest_url_raises_on_http_error(adapter: RstAdapter) -> None:
    import httpx as _httpx

    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = _httpx.HTTPStatusError(
        "404", request=MagicMock(), response=MagicMock()
    )

    with patch("httpx.get", return_value=mock_response):
        with pytest.raises(_httpx.HTTPStatusError):
            adapter.ingest("https://example.com/missing.rst", metadata={
                "source_type": "standard", "domain": "engineering",
                "version_ref": "v1", "timestamp": "2024-01-01",
            })


# ---------------------------------------------------------------------------
# _ensure_pandoc — auto-download path
# ---------------------------------------------------------------------------

def test_ensure_pandoc_downloads_if_missing() -> None:
    inst = RstAdapter()
    with patch("pypandoc.get_pandoc_version", side_effect=OSError("not found")), \
         patch("pypandoc.pandoc_download.download_pandoc") as mock_dl:
        inst._ensure_pandoc()
    mock_dl.assert_called_once()
    assert inst._pandoc_ready is True


def test_ensure_pandoc_skips_if_ready() -> None:
    inst = RstAdapter()
    inst._pandoc_ready = True
    with patch("pypandoc.get_pandoc_version") as mock_ver:
        inst._ensure_pandoc()
    mock_ver.assert_not_called()
