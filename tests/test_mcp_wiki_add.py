"""Tests for the `wiki_add` MCP write tool (#37 A3 / #273).

`wiki_add` is a thin proxy onto shared ``run_add`` — same defaults as CLI
``llmwiki add`` (raw + site build; synthesize opt-in). It must resolve the
vault the same way every other MCP tool does (the patched `REPO_ROOT`
module global), never the operator live vault.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import llmwiki.add_pipeline as pipe
from llmwiki.add_pipeline import run_add
from llmwiki.mcp.server import TOOL_IMPLS, TOOLS, tool_wiki_add


def _result_text(result: dict) -> str:
    return result["content"][0]["text"]


def _result_json(result: dict):
    return json.loads(_result_text(result))


def _vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "raw" / "docs").mkdir(parents=True)
    (vault / "wiki").mkdir()
    return vault


def _schema_props() -> dict:
    tool = next(t for t in TOOLS if t["name"] == "wiki_add")
    return tool["inputSchema"]["properties"]


# ─── Registration ──────────────────────────────────────────────────


def test_wiki_add_registered_in_tools_and_impls():
    names = {t["name"] for t in TOOLS}
    assert "wiki_add" in names
    assert TOOL_IMPLS["wiki_add"] is tool_wiki_add


def test_wiki_add_schema_exposes_synthesize_and_no_build():
    props = _schema_props()
    assert props["synthesize"]["default"] is False
    assert props["no_build"]["default"] is False
    desc = next(t for t in TOOLS if t["name"] == "wiki_add")["description"]
    assert "Proxy for CLI" in desc or "proxy" in desc.lower()
    assert "synthesize" in desc.lower()
    assert "do not reconstruct" in desc.lower() or "unless the user asked" in desc


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


# ─── content route (piped; no network) ─────────────────────────────


def test_wiki_add_content_lands_raw_doc_under_resolved_vault(tmp_path: Path, monkeypatch):
    vault = _vault(tmp_path)
    monkeypatch.setattr(pipe, "build_site", lambda **kw: 0)
    with patch("llmwiki.mcp.server.REPO_ROOT", vault):
        result = tool_wiki_add({
            "content": "# My Note\n\nSome durable knowledge worth keeping.\n",
        })
    assert result["isError"] is False, _result_text(result)
    payload = _result_json(result)
    assert len(payload["written"]) == 1
    rel = payload["written"][0]
    assert rel.startswith("raw/docs/")
    written_path = vault / rel
    assert written_path.exists()
    text = written_path.read_text(encoding="utf-8")
    assert "My Note" in text
    assert "Some durable knowledge worth keeping." in text


def test_wiki_add_content_piped_provenance(tmp_path: Path, monkeypatch):
    """MCP content must record ``source: piped``, never a /tmp path (#273)."""
    vault = _vault(tmp_path)
    monkeypatch.setattr(pipe, "build_site", lambda **kw: 0)
    with patch("llmwiki.mcp.server.REPO_ROOT", vault):
        result = tool_wiki_add({
            "content": "# Piped MCP Doc\n\nhello from content\n",
            "no_build": True,
        })
    assert result["isError"] is False, _result_text(result)
    rel = _result_json(result)["written"][0]
    text = (vault / rel).read_text(encoding="utf-8")
    assert 'source: "piped"' in text or "source: piped" in text
    assert "/tmp/" not in text
    assert "wiki-add-content-" not in text


def test_wiki_add_content_parity_with_cli_text_add(tmp_path: Path, monkeypatch):
    """Same body via MCP content and CLI ``add -`` → same piped provenance."""
    monkeypatch.setattr(pipe, "build_site", lambda **kw: 0)
    body = "# Parity Doc\n\nshared body for mcp and cli\n"

    mcp_vault = _vault(tmp_path / "mcp")
    with patch("llmwiki.mcp.server.REPO_ROOT", mcp_vault):
        mcp_result = tool_wiki_add({"content": body, "no_build": True})
    assert mcp_result["isError"] is False, _result_text(mcp_result)
    mcp_text = (mcp_vault / _result_json(mcp_result)["written"][0]).read_text(
        encoding="utf-8"
    )

    cli_vault = _vault(tmp_path / "cli")
    cli_result = run_add(
        ["-"],
        cli_vault / "raw" / "docs",
        vault_root=cli_vault,
        build=False,
        stdin_text=body,
    )
    assert cli_result["exit_code"] == 0
    cli_text = cli_result["written"][0].read_text(encoding="utf-8")

    assert ('source: "piped"' in mcp_text) or ("source: piped" in mcp_text)
    assert ('source: "piped"' in cli_text) or ("source: piped" in cli_text)
    assert "shared body for mcp and cli" in mcp_text
    assert "shared body for mcp and cli" in cli_text


def test_wiki_add_default_builds_without_synth(tmp_path: Path, monkeypatch):
    vault = _vault(tmp_path)
    synth_called = {"n": 0}
    build_called = {"n": 0}
    monkeypatch.setattr(
        pipe,
        "synthesize_new_sessions",
        lambda **kw: (synth_called.__setitem__("n", synth_called["n"] + 1) or {
            "synthesized": 0, "skipped": 0, "errors": [],
        }),
    )
    monkeypatch.setattr(
        pipe,
        "build_site",
        lambda **kw: (build_called.__setitem__("n", build_called["n"] + 1) or 0),
    )
    with patch("llmwiki.mcp.server.REPO_ROOT", vault):
        result = tool_wiki_add({"content": "# Default Doc\n\nbody\n"})
    assert result["isError"] is False, _result_text(result)
    assert synth_called["n"] == 0
    assert build_called["n"] == 1
    sources = vault / "wiki" / "sources"
    assert not list(sources.rglob("*.md")) if sources.exists() else True


def test_wiki_add_no_build_skips_site_rebuild(tmp_path: Path, monkeypatch):
    vault = _vault(tmp_path)
    build_called = {"n": 0}
    monkeypatch.setattr(
        pipe,
        "build_site",
        lambda **kw: (build_called.__setitem__("n", build_called["n"] + 1) or 0),
    )
    with patch("llmwiki.mcp.server.REPO_ROOT", vault):
        result = tool_wiki_add({
            "content": "# No Build Doc\n\nbody\n",
            "no_build": True,
        })
    assert result["isError"] is False, _result_text(result)
    assert build_called["n"] == 0
    assert (vault / _result_json(result)["written"][0]).exists()


def test_wiki_add_synthesize_opt_in(tmp_path: Path, monkeypatch):
    vault = _vault(tmp_path)
    synth_called = {"n": 0}

    class _Ok:
        name = "dummy"

        def is_available(self):
            return True

    def _fake_synth(**kwargs):
        synth_called["n"] += 1
        return {
            "total_scanned": 1,
            "new_files": 1,
            "synthesized": 1,
            "skipped": 0,
            "errors": [],
            "backend": "dummy",
        }

    def _expected(raw_path, sources_dir):
        p = Path(sources_dir) / "docs" / "synth-opt-in.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("# Synth Opt In\n", encoding="utf-8")
        return p

    monkeypatch.setattr(pipe, "_load_sessions_config", lambda: {
        "synthesis": {"backend": "dummy"},
    })
    monkeypatch.setattr(pipe, "resolve_backend", lambda _cfg: _Ok())
    monkeypatch.setattr(pipe, "synthesize_new_sessions", _fake_synth)
    monkeypatch.setattr(pipe, "expected_source_page", _expected)
    monkeypatch.setattr(pipe, "build_site", lambda **kw: 0)

    with patch("llmwiki.mcp.server.REPO_ROOT", vault):
        result = tool_wiki_add({
            "content": "# Synth Opt In\n\nbody\n",
            "synthesize": True,
            "no_build": True,
        })
    assert result["isError"] is False, _result_text(result)
    assert synth_called["n"] == 1
    assert (vault / "wiki" / "sources" / "docs" / "synth-opt-in.md").exists()


def test_wiki_add_content_does_not_synthesize_wiki_sources(tmp_path: Path, monkeypatch):
    """Default add must not create wiki/sources pages (#273)."""
    vault = _vault(tmp_path)
    monkeypatch.setattr(pipe, "build_site", lambda **kw: 0)
    with patch("llmwiki.mcp.server.REPO_ROOT", vault):
        result = tool_wiki_add({"content": "# Another Note\n\nBody text.\n"})
    assert result["isError"] is False, _result_text(result)
    sources = vault / "wiki" / "sources"
    assert not list(sources.rglob("*.md")) if sources.exists() else True


def test_wiki_add_content_honors_title_and_project(tmp_path: Path, monkeypatch):
    vault = _vault(tmp_path)
    monkeypatch.setattr(pipe, "build_site", lambda **kw: 0)
    with patch("llmwiki.mcp.server.REPO_ROOT", vault):
        result = tool_wiki_add({
            "content": "Just a body, no heading.\n",
            "title": "Custom Title",
            "project": "my-project",
            "no_build": True,
        })
    assert result["isError"] is False, _result_text(result)
    payload = _result_json(result)
    rel = payload["written"][0]
    assert rel.startswith("raw/docs/my-project/")
    text = (vault / rel).read_text(encoding="utf-8")
    assert "Custom Title" in text


# ─── path route ─────────────────────────────────────────────────────


def test_wiki_add_path_lands_raw_doc(tmp_path: Path, monkeypatch):
    vault = _vault(tmp_path)
    monkeypatch.setattr(pipe, "build_site", lambda **kw: 0)
    src_dir = tmp_path / "outside"
    src_dir.mkdir()
    src_file = src_dir / "source.md"
    src_file.write_text("# Source Doc\n\nContent from a file.\n", encoding="utf-8")

    with patch("llmwiki.mcp.server.REPO_ROOT", vault):
        result = tool_wiki_add({"path": str(src_file), "no_build": True})
    assert result["isError"] is False, _result_text(result)
    payload = _result_json(result)
    rel = payload["written"][0]
    assert rel.startswith("raw/docs/")
    assert (vault / rel).exists()
    text = (vault / rel).read_text(encoding="utf-8")
    assert str(src_file) in text or "source.md" in text
    assert "/tmp/wiki-add-content-" not in text


def test_wiki_add_missing_path_reports_error(tmp_path: Path, monkeypatch):
    vault = _vault(tmp_path)
    monkeypatch.setattr(pipe, "build_site", lambda **kw: 0)
    with patch("llmwiki.mcp.server.REPO_ROOT", vault):
        result = tool_wiki_add({"path": str(tmp_path / "does-not-exist.md")})
    assert result["isError"] is True
