"""Tests for config.json / sessions_config vault defaults."""

from __future__ import annotations

import json
from pathlib import Path


def test_load_default_vault_path_from_user_config(tmp_path: Path, monkeypatch):
    clone = tmp_path / "clone"
    clone.mkdir()
    (clone / "examples").mkdir()
    (clone / "examples" / "sessions_config.json").write_text(
        json.dumps({"vault": {"default_path": ""}}), encoding="utf-8",
    )
    (clone / "config.json").write_text(
        json.dumps({"vault": {"default_path": str(tmp_path / "my-vault")}}),
        encoding="utf-8",
    )
    import llmwiki.config_schedule as cs

    monkeypatch.setattr(cs, "_CLONE_ROOT", clone)
    monkeypatch.setattr(cs, "_SESSIONS_CONFIG", clone / "examples" / "sessions_config.json")
    monkeypatch.setattr(cs, "_USER_CONFIG", clone / "config.json")

    assert cs.load_default_vault_path() == (tmp_path / "my-vault").resolve()
