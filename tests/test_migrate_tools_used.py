"""Migration: expand CallMcpTool frontmatter from origin session stores."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from llmwiki import convert as c
from llmwiki.adapters.claude_code import ClaudeCodeAdapter

REPO = Path(__file__).resolve().parents[1]


def _load_migrator():
    script = REPO / "scripts" / "migrate_tools_used_mcp.py"
    spec = importlib.util.spec_from_file_location(
        "migrate_tools_used_mcp", script
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write_jsonl_with_call_mcp(path: Path, *, session_id: str = "sess-expand") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "type": "user",
            "sessionId": session_id,
            "slug": "expand-demo",
            "timestamp": "2026-07-01T10:00:00Z",
            "cwd": "/home/user/proj",
            "message": {"role": "user", "content": "query wiki"},
        },
        {
            "type": "assistant",
            "sessionId": session_id,
            "timestamp": "2026-07-01T10:00:01Z",
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "name": "CallMcpTool",
                        "input": {
                            "server": "llmwiki",
                            "toolName": "wiki_query",
                        },
                    }
                ],
            },
        },
    ]
    path.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )


OLD_SESSION_MD = """---
title: "Session: expand-demo — 2026-07-01"
type: source
tags: [claude-code, session-transcript]
date: 2026-07-01
sessionId: sess-expand
slug: expand-demo
project: demo
tools_used: [CallMcpTool, Read]
tool_counts: {"CallMcpTool": 1, "Read": 1}
is_subagent: false
---

# Session

Body unchanged.
"""


def _seed_vault(tmp_path: Path):
    home = tmp_path / "home"
    home.mkdir()
    store = home / ".claude" / "projects" / "demo"
    vault = tmp_path / "vault"
    sessions = vault / "raw" / "sessions"
    sessions.mkdir(parents=True)
    state = vault / "llmwiki-state.json"
    return home, store, vault, sessions, state


def _patch_home(monkeypatch, home: Path):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setattr(
        ClaudeCodeAdapter, "session_store_path", home / ".claude" / "projects", raising=False
    )
    c.discover_adapters()


def test_migrate_expands_tools_used_from_origin(tmp_path: Path, monkeypatch):
    mod = _load_migrator()
    home, store, vault, sessions, state = _seed_vault(tmp_path)
    jsonl = store / "sess-expand.jsonl"
    _write_jsonl_with_call_mcp(jsonl)
    state.write_text(
        json.dumps(
            {
                "sync": {
                    "files": {
                        "claude_code::.claude/projects/demo/sess-expand.jsonl": "2026-07-01T10:00:00Z"
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    target = sessions / "2026-07-01T10-00-demo-expand-demo.md"
    target.write_text(OLD_SESSION_MD, encoding="utf-8")
    _patch_home(monkeypatch, home)

    report = mod.run_migration(vault=vault, dry_run=False)
    assert report["scanned"] == 1
    assert report["rewritten"] == 1
    assert report["skipped_missing_origin"] == 0
    updated = target.read_text(encoding="utf-8")
    assert "mcp__llmwiki__wiki_query" in updated
    assert "tools_used: [CallMcpTool, mcp__llmwiki__wiki_query]" in updated
    assert '"CallMcpTool": 1' in updated
    assert '"mcp__llmwiki__wiki_query": 1' in updated
    assert "Read" not in updated.split("---", 2)[1]
    assert "Body unchanged." in updated


def test_migrate_missing_origin_leaves_file_unchanged(tmp_path: Path, monkeypatch):
    mod = _load_migrator()
    home, _store, vault, sessions, state = _seed_vault(tmp_path)
    state.write_text(json.dumps({"sync": {"files": {}}}), encoding="utf-8")
    target = sessions / "2026-07-01T10-00-demo-expand-demo.md"
    target.write_text(OLD_SESSION_MD, encoding="utf-8")
    _patch_home(monkeypatch, home)

    report = mod.run_migration(vault=vault, dry_run=False)
    assert report["scanned"] == 1
    assert report["rewritten"] == 0
    assert report["skipped_missing_origin"] == 1
    assert target.read_text(encoding="utf-8") == OLD_SESSION_MD


def test_migrate_dry_run_writes_nothing(tmp_path: Path, monkeypatch):
    mod = _load_migrator()
    home, store, vault, sessions, state = _seed_vault(tmp_path)
    _write_jsonl_with_call_mcp(store / "sess-expand.jsonl")
    state.write_text(
        json.dumps(
            {
                "sync": {
                    "files": {
                        "claude_code::.claude/projects/demo/sess-expand.jsonl": "2026-07-01T10:00:00Z"
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    target = sessions / "2026-07-01T10-00-demo-expand-demo.md"
    target.write_text(OLD_SESSION_MD, encoding="utf-8")
    _patch_home(monkeypatch, home)

    report = mod.run_migration(vault=vault, dry_run=True)
    assert report["rewritten"] == 1
    assert report["dry_run"] is True
    assert target.read_text(encoding="utf-8") == OLD_SESSION_MD


def test_migrate_noop_without_call_mcp_tool(tmp_path: Path):
    mod = _load_migrator()
    vault = tmp_path / "vault"
    sessions = vault / "raw" / "sessions"
    sessions.mkdir(parents=True)
    (vault / "llmwiki-state.json").write_text("{}", encoding="utf-8")
    plain = """---
sessionId: plain
tags: [claude-code, session-transcript]
tools_used: [Read, Bash]
tool_counts: {"Read": 1, "Bash": 1}
---

body
"""
    target = sessions / "plain.md"
    target.write_text(plain, encoding="utf-8")

    report = mod.run_migration(vault=vault, dry_run=False)
    assert report["unchanged"] == 1
    assert report["skipped_missing_origin"] == 0
    assert target.read_text(encoding="utf-8") == plain
