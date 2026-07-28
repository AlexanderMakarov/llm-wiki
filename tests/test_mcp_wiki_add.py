"""Tests for the `wiki_add` MCP write tool (#37 A3).

`wiki_add` is the only write-ish MCP tool other than `wiki_sync` — a
thin wrapper around `add_sources` (the same conversion/write path the
`llmwiki add` CLI uses) so MCP-only agents have a supported way to
land a new document without shelling out. It must resolve the vault
the same way every other MCP tool does (the patched `REPO_ROOT`
module global), never the repo's own `wiki/`.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from llmwiki.mcp.server import TOOL_IMPLS, TOOLS, tool_wiki_add


def _result_text(result: dict) -> str:
    return result["content"][0]["text"]


def _result_json(result: dict):
    return json.loads(_result_text(result))


# ─── Registration ──────────────────────────────────────────────────


def test_wiki_add_registered_in_tools_and_impls():
    names = {t["name"] for t in TOOLS}
    assert "wiki_add" in names
    assert TOOL_IMPLS["wiki_add"] is tool_wiki_add


# ─── Input validation ──────────────────────────────────────────────


def test_wiki_add_requires_a_source():
    result = tool_wiki_add({})
    assert result["isError"] is True
    assert "exactly one of" in _result_text(result)


def test_wiki_add_rejects_two_sources_at_once():
    result = tool_wiki_add({"url": "https://example.com/x", "content": "hello"})
    assert result["isError"] is True
    assert "exactly one of" in _result_text(result)


def test_wiki_add_rejects_all_three_sources_at_once():
    result = tool_wiki_add({
        "url": "https://example.com/x",
        "path": "/tmp/whatever.md",
        "content": "hello",
    })
    assert result["isError"] is True
    assert "exactly one of" in _result_text(result)


# ─── content route (no network needed) ─────────────────────────────


def test_wiki_add_content_lands_raw_doc_under_resolved_vault(tmp_path: Path):
    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_add({
            "content": "# My Note\n\nSome durable knowledge worth keeping.\n",
        })
    assert result["isError"] is False, _result_text(result)
    payload = _result_json(result)
    assert len(payload["written"]) == 1
    rel = payload["written"][0]
    assert rel.startswith("raw/docs/")
    written_path = tmp_path / rel
    assert written_path.exists()
    assert "My Note" in written_path.read_text(encoding="utf-8")
    assert "Some durable knowledge worth keeping." in written_path.read_text(encoding="utf-8")


def test_wiki_add_content_does_not_touch_repo_wiki(tmp_path: Path):
    """The vault resolved for this call is tmp_path — nothing should be
    written under tmp_path/wiki/, and REPO_ROOT being patched away for
    the duration of the call means the real project's wiki/ can't be
    touched either."""
    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_add({"content": "# Another Note\n\nBody text.\n"})
    assert result["isError"] is False, _result_text(result)
    assert not (tmp_path / "wiki").exists()


def test_wiki_add_content_honors_title_and_project(tmp_path: Path):
    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_add({
            "content": "Just a body, no heading.\n",
            "title": "Custom Title",
            "project": "my-project",
        })
    assert result["isError"] is False, _result_text(result)
    payload = _result_json(result)
    rel = payload["written"][0]
    assert rel.startswith("raw/docs/my-project/")
    text = (tmp_path / rel).read_text(encoding="utf-8")
    assert "Custom Title" in text


# ─── path route ─────────────────────────────────────────────────────


def test_wiki_add_path_lands_raw_doc(tmp_path: Path):
    vault = tmp_path / "vault"
    vault.mkdir()
    src_dir = tmp_path / "outside"
    src_dir.mkdir()
    src_file = src_dir / "source.md"
    src_file.write_text("# Source Doc\n\nContent from a file.\n", encoding="utf-8")

    with patch("llmwiki.mcp.server.REPO_ROOT", vault):
        result = tool_wiki_add({"path": str(src_file)})
    assert result["isError"] is False, _result_text(result)
    payload = _result_json(result)
    rel = payload["written"][0]
    assert rel.startswith("raw/docs/")
    assert (vault / rel).exists()
    assert not (tmp_path / "wiki").exists()


def test_wiki_add_missing_path_reports_error(tmp_path: Path):
    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_add({"path": str(tmp_path / "does-not-exist.md")})
    assert result["isError"] is True
