"""Tests for config.json / sessions_config vault defaults."""

from __future__ import annotations

import json
from pathlib import Path
import llmwiki.config_schedule as cs



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

    monkeypatch.setattr(cs, "_CLONE_ROOT", clone)
    monkeypatch.setattr(cs, "_SESSIONS_CONFIG", clone / "examples" / "sessions_config.json")
    monkeypatch.setattr(cs, "_USER_CONFIG", clone / "config.json")

    def _real_load_default_vault_path() -> Path | None:
        vault = cs._load_sessions_config().get("vault", {})
        if not isinstance(vault, dict):
            return None
        raw = str(vault.get("default_path", "")).strip()
        if not raw:
            return None
        return Path(raw).expanduser()

    monkeypatch.setattr(cs, "load_default_vault_path", _real_load_default_vault_path)

    assert cs.load_default_vault_path() == (tmp_path / "my-vault").resolve()
