"""cmd_sync must hard-stop on a newer-schema / corrupt vault state (#29).

Guards the "downgrade silently duplicates raw/" incident at the CLI
border: before spending time converting, sync inspects the vault state
file and aborts (exit 2, convert_all never called) unless the user
passes --force-resync.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from llmwiki.state_store import SCHEMA_VERSION


@pytest.fixture(autouse=True)
def _no_personal_vault_config(monkeypatch):
    import llmwiki.config_schedule as config_schedule_mod

    monkeypatch.setattr(config_schedule_mod, "load_default_vault_path", lambda: None)


def _make_args(**overrides):
    base = {
        "vault": None,
        "allow_overwrite": False,
        "adapter": None,
        "since": None,
        "project": None,
        "include_current": False,
        "force": False,
        "force_resync": False,
        "auto_build": False,
        "auto_lint": False,
        "status": False,
        "recent": 0,
    }
    base.update(overrides)
    return argparse.Namespace(**base)


def _write_newer_schema_state(vault: Path) -> None:
    state = {"meta": {"schema_version": SCHEMA_VERSION + 1}, "sync": {"files": {"x": "y"}}}
    (vault / "llmwiki-state.json").write_text(json.dumps(state), encoding="utf-8")


def test_sync_aborts_on_newer_schema_vault(tmp_path: Path, capsys):
    from llmwiki.cli import cmd_sync

    vault = tmp_path / "vault"
    vault.mkdir()
    _write_newer_schema_state(vault)

    called = {"convert": False}

    def _fake(**kwargs):
        called["convert"] = True
        return 0

    with patch("llmwiki.convert.convert_all", side_effect=_fake):
        rc = cmd_sync(_make_args(vault=vault))

    assert rc == 2
    assert called["convert"] is False
    err = capsys.readouterr().err
    assert "force-resync" in err


def test_force_resync_bypasses_and_converts(tmp_path: Path):
    from llmwiki.cli import cmd_sync

    vault = tmp_path / "vault"
    vault.mkdir()
    _write_newer_schema_state(vault)

    captured: dict = {}

    def _fake(**kwargs):
        captured.update(kwargs)
        return 0

    with patch("llmwiki.convert.convert_all", side_effect=_fake):
        rc = cmd_sync(_make_args(vault=vault, force_resync=True))

    assert rc == 0
    # --force-resync implies a full reconvert.
    assert captured.get("force") is True
