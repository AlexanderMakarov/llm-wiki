"""Acceptance tests for #182 configurable adapters."""

from __future__ import annotations

from pathlib import Path

from llmwiki.adapters import REGISTRY, discover_all
from llmwiki.adapters.settings import adapter_store_present, select_sync_adapters
from llmwiki.adapters.status import adapter_status


def test_merged_config_enables_openclaw_vault_inbox(tmp_path: Path):
    discover_all()
    inbox = tmp_path / ".openclaw-sessions-inbox" / "main"
    inbox.mkdir(parents=True)
    (inbox / "sess.jsonl").write_text('{"type":"session"}\n', encoding="utf-8")
    cfg = {
        "vault": {"default_path": str(tmp_path)},
        "adapters": {
            "openclaw": {
                "enabled": True,
                "roots": [str(tmp_path / ".openclaw-sessions-inbox")],
            }
        },
    }
    names = [c.name for c in select_sync_adapters(cfg, None)]
    assert "openclaw" in names
    assert adapter_store_present(REGISTRY["openclaw"], cfg) is True


def test_cursor_ide_explicit_enabled_not_active_on_bare_sync(tmp_path: Path):
    discover_all()
    root = tmp_path / "workspaceStorage"
    root.mkdir(parents=True)
    cfg = {"adapters": {"cursor_ide": {"enabled": True, "roots": [str(root)]}}}
    selected = {c.name for c in select_sync_adapters(cfg, None)}
    enabled, active = adapter_status(
        "cursor_ide", REGISTRY["cursor_ide"], cfg, selected_names=selected
    )
    assert enabled == "explicit"
    assert active == "no"
    assert adapter_store_present(REGISTRY["cursor_ide"], cfg) is True