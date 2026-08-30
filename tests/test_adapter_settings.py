"""Tests for adapter config resolution and sync selection (#182)."""

from __future__ import annotations

from pathlib import Path

import pytest

from llmwiki.adapters import REGISTRY, discover_all
from llmwiki.adapters.settings import (
    adapter_block,
    adapter_enabled_flag,
    adapter_store_present,
    select_sync_adapters,
)


def test_adapter_block_merges_top_level_and_adapters_section():
    cfg = {
        "openclaw": {"enabled": False},
        "adapters": {"openclaw": {"enabled": True, "roots": ["/tmp/oc"]}},
    }
    block = adapter_block(cfg, "openclaw")
    assert block["enabled"] is True
    assert block["roots"] == ["/tmp/oc"]


def test_adapter_enabled_flag_respects_false():
    cfg = {"adapters": {"claude_code": {"enabled": False}}}
    assert adapter_enabled_flag(cfg, "claude_code") is False


def test_select_sync_skips_disabled_ai_adapter():
    discover_all()
    cfg = {"adapters": {"claude_code": {"enabled": False}}}
    names = [c.name for c in select_sync_adapters(cfg, None)]
    assert "claude_code" not in names


def test_select_sync_includes_openclaw_when_store_present(tmp_path: Path):
    discover_all()
    store = tmp_path / "openclaw-agents"
    store.mkdir(parents=True)
    cfg = {"adapters": {"openclaw": {"roots": [str(store)]}}}
    names = [c.name for c in select_sync_adapters(cfg, None)]
    assert "openclaw" in names


def test_select_sync_obsidian_requires_explicit_enable(tmp_path: Path):
    discover_all()
    vault = tmp_path / "vault"
    vault.mkdir(parents=True)
    (vault / "note.md").write_text("x" * 60, encoding="utf-8")
    names = [c.name for c in select_sync_adapters({}, None)]
    assert "obsidian" not in names
    names_on = [c.name for c in select_sync_adapters(
        {"adapters": {"obsidian": {"enabled": True, "vault_paths": [str(vault)]}}},
        None,
    )]
    assert "obsidian" in names_on


def test_select_sync_explicit_adapter_override():
    discover_all()
    names = [c.name for c in select_sync_adapters({}, ["cursor_cli"])]
    assert names == ["cursor_cli"]


def test_select_sync_unknown_adapter_raises():
    with pytest.raises(ValueError, match="unknown adapter"):
        select_sync_adapters({}, ["not-a-real-adapter"])


def test_select_sync_includes_cursor_ide_when_enabled(tmp_path: Path):
    """#192 R9: enabled Cursor IDE is on bare sync; alias cursor still works."""
    discover_all()
    db = tmp_path / "state.vscdb"
    db.write_bytes(b"")
    # Legacy adapters.cursor key still configures cursor_ide.
    cfg = {
        "adapters": {
            "cursor": {
                "enabled": True,
                "roots": [str(tmp_path)],
                "global_db": str(db),
            }
        }
    }
    names = [c.name for c in select_sync_adapters(cfg, None)]
    assert "cursor_ide" in names
    names_explicit = [c.name for c in select_sync_adapters(cfg, ["cursor"])]
    assert names_explicit == ["cursor_ide"]
    names_canon = [c.name for c in select_sync_adapters(cfg, ["cursor_ide"])]
    assert names_canon == ["cursor_ide"]


def test_adapter_store_present_openclaw_custom_root(tmp_path: Path):
    discover_all()
    root = tmp_path / "inbox"
    root.mkdir(parents=True)
    cfg = {"adapters": {"openclaw": {"roots": [str(root)]}}}
    assert adapter_store_present(REGISTRY["openclaw"], cfg) is True


def test_adapter_store_present_chatgpt_without_enable(tmp_path: Path):
    discover_all()
    export_dir = tmp_path / "export"
    export_dir.mkdir(parents=True)
    (export_dir / "conversations.json").write_text("[]", encoding="utf-8")
    cfg = {"adapters": {"chatgpt": {"enabled": False, "export_dirs": [str(export_dir)]}}}
    assert adapter_store_present(REGISTRY["chatgpt"], cfg) is True
    names = [c.name for c in select_sync_adapters(cfg, None)]
    assert "chatgpt" not in names
