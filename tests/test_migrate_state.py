"""Tests for one-time unified state migration."""

from __future__ import annotations

import json
from pathlib import Path

from llmwiki.migrate_state import run_migration


def test_migrate_legacy_dotfiles(tmp_path: Path):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / ".llmwiki-state.json").write_text(
        json.dumps({"raw/a.md": 1.0, "_meta": {"last_sync": "t"}}),
        encoding="utf-8",
    )
    (vault / ".llmwiki-queue.json").write_text(
        json.dumps(["raw/pending.md"]),
        encoding="utf-8",
    )
    target = vault / "llmwiki-state.json"
    report = run_migration(target)
    assert report["migrated"]
    state = json.loads(target.read_text(encoding="utf-8"))
    assert state["sync"]["files"]["raw/a.md"] == 1.0
    assert state["queue"]["legacy_pending_paths"] == ["raw/pending.md"]
