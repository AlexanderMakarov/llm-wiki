"""Tests for adapter config resolution and sync selection (#182)."""

from __future__ import annotations

from pathlib import Path

import pytest

from llmwiki.adapters import discover_all
from llmwiki.adapters.settings import (
    adapter_block,
    adapter_enabled_flag,
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
