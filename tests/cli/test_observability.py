"""Tests for the observability CLI bundle (G-01 · G-03).

* ``cmd_adapters``: status helper returns yes/no; CLI shows present +
  enabled yes/no (#192 R9); legacy active/auto/explicit labels gone;
  ``--wide`` still works.
* ``cmd_sync_status``: reads ``_meta`` + ``_counters`` from the state
  file, renders per-adapter table, surfaces quarantine counts, shows
  ``--recent`` activity from log.md.
* State migration keeps ``_meta`` / ``_counters`` intact.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from textwrap import dedent
from unittest.mock import patch

import llmwiki.cli as cli_mod
import llmwiki.sync.status as sync_status_mod
from llmwiki import quarantine as q
from llmwiki.cli import _adapter_status
from llmwiki.convert import _migrate_legacy_state


def _run_cli(*args, env=None):
    return subprocess.run(
        [sys.executable, "-m", "llmwiki", *args],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


# ─── G-01: _adapter_status + cmd_adapters ─────────────────────────────────


class _FakeAdapter:
    """Minimal adapter shim used by ``_adapter_status`` tests."""

    _available = True

    @classmethod
    def is_available(cls) -> bool:
        return cls._available


def _available_fake(is_avail: bool):
    klass = type(
        "Fake",
        (_FakeAdapter,),
        {"_available": is_avail},
    )
    return klass


def test_adapter_status_auto_default():
    """An available adapter with no config row must show enabled yes."""
    assert _adapter_status("x", _available_fake(True), config={}) == "yes"


def test_adapter_status_explicit_enable():
    """``enabled: true`` in config must show enabled yes when the adapter is present."""
    cfg = {"x": {"enabled": True}}
    assert _adapter_status("x", _available_fake(True), config=cfg) == "yes"


def test_adapter_status_explicit_off_blocks_fire():
    """``enabled: false`` must show enabled no even when the adapter is available."""
    cfg = {"x": {"enabled": False}}
    assert _adapter_status("x", _available_fake(True), config=cfg) == "no"


def test_adapter_status_unavailable_never_fires():
    """Unavailable adapters must never show enabled yes."""
    assert (
        _adapter_status(
            "x", _available_fake(False), config={"x": {"enabled": True}}
        )
        == "no"
    )


def test_adapter_status_invalid_config_entry_defaults_to_auto():
    """A malformed config row (string instead of dict) must not crash."""
    assert _adapter_status("x", _available_fake(True), config={"x": "yes"}) == "yes"


def test_adapters_cli_shows_new_columns():
    """``adapters`` table must use present/enabled columns and drop retired labels."""
    cp = _run_cli("adapters")
    assert cp.returncode == 0
    # #192 R9: name / present / enabled(yes|no) / description — no active column.
    for header in ("name", "present", "enabled", "description"):
        assert header in cp.stdout, (
            f"adapters table missing the {header!r} column header"
        )
    table_section = cp.stdout.split("Columns:")[0]
    assert "  active  " not in table_section, "retired 'active' column still rendered"
    assert "  configured  " not in table_section, "old 'configured' column header still rendered"
    assert "  will_fire  " not in table_section, "old 'will_fire' column header still rendered"
    assert "auto (default)" not in cp.stdout
    assert "explicit (enabled:true" not in cp.stdout
    assert "yes/no" in cp.stdout


def test_adapters_wide_flag_still_works():
    """``adapters --wide`` must print extended columns without the narrow hint."""
    cp = _run_cli("adapters", "--wide")
    assert cp.returncode == 0
    assert "Pass --wide" not in cp.stdout


SAMPLE_LOG = dedent(
    """\
    # Wiki Log

    ## [2026-04-19] synthesize | 3 sessions across 2 projects
    - Processed: 3
    - Errors: 0

    ## [2026-04-18] lint | auto-check
    - Processed: 714

    ## [2026-04-17] sync | nightly
    - Processed: 20
    """
)


# ─── G-03: cmd_sync_status ────────────────────────────────────────────────


def test_sync_status_empty_state(tmp_path, monkeypatch, capsys):
    state_file = tmp_path / "state.json"
    monkeypatch.setattr(cli_mod, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(sync_status_mod, "REPO_ROOT", tmp_path)
    args = _mk_sync_status_args(state_file=state_file)
    rc = cli_mod.cmd_sync_status(args)
    assert rc == 0
    out = capsys.readouterr().out
    assert "never" in out or "pre-upgrade" in out
    assert "No per-adapter counters" in out
    assert "Quarantined sources: 0" in out


def test_sync_status_renders_counters_table(tmp_path, monkeypatch, capsys):
    state_file = tmp_path / "state.json"
    state_file.write_text(
        json.dumps({
            "_meta": {"last_sync": "2026-04-20T04:00:00Z", "version": 1},
            "_counters": {
                "claude_code": {
                    "discovered": 471, "converted": 65, "unchanged": 0,
                    "live": 1, "filtered": 405, "ignored": 0, "errored": 0,
                },
                "codex_cli": {
                    "discovered": 1, "converted": 0, "unchanged": 0,
                    "live": 0, "filtered": 1, "ignored": 0, "errored": 0,
                },
            },
            "claude_code::.claude/projects/foo/a.jsonl": 1.0,
        }, indent=2),
        encoding="utf-8",
    )
    monkeypatch.setattr(cli_mod, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(sync_status_mod, "REPO_ROOT", tmp_path)
    rc = cli_mod.cmd_sync_status(_mk_sync_status_args(state_file=state_file))
    assert rc == 0
    out = capsys.readouterr().out
    assert "Last sync: 2026-04-20T04:00:00Z" in out
    assert "claude_code" in out
    assert "codex_cli" in out
    # Counters columns
    for header in ("discovered", "converted", "unchanged", "live", "filtered", "errored"):
        assert header in out


def test_sync_status_surfaces_quarantine(tmp_path, monkeypatch, capsys):
    state_file = tmp_path / "state.json"
    state_file.write_text(json.dumps({}), encoding="utf-8")
    q.add_entry("claude_code", "/tmp/bad.jsonl", "boom", path=state_file)

    monkeypatch.setattr(cli_mod, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(sync_status_mod, "REPO_ROOT", tmp_path)

    rc = cli_mod.cmd_sync_status(_mk_sync_status_args(state_file=state_file))
    assert rc == 0
    out = capsys.readouterr().out
    assert "Quarantined sources: 1" in out
    assert "claude_code:1" in out


def test_sync_status_with_recent_logs_events(tmp_path, monkeypatch, capsys):
    (tmp_path / "wiki").mkdir()
    (tmp_path / "wiki" / "log.md").write_text(SAMPLE_LOG, encoding="utf-8")
    state_file = tmp_path / "state.json"
    state_file.write_text(json.dumps({}), encoding="utf-8")
    monkeypatch.setattr(cli_mod, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(sync_status_mod, "REPO_ROOT", tmp_path)
    rc = cli_mod.cmd_sync_status(_mk_sync_status_args(recent=2, state_file=state_file))
    assert rc == 0
    out = capsys.readouterr().out
    assert "Recent activity" in out
    # SAMPLE_LOG only has one sync/synthesize pair (synthesize on 4-19, sync on 4-17)
    assert "2026-04-19" in out
    assert "2026-04-17" in out


def test_sync_status_corrupt_state_file_is_tolerated(tmp_path, monkeypatch, capsys):
    """Corrupt JSON in the state file must still yield a status report, not a crash."""
    state_file = tmp_path / "state.json"
    state_file.write_text("{ not json", encoding="utf-8")
    monkeypatch.setattr(cli_mod, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(sync_status_mod, "REPO_ROOT", tmp_path)
    rc = cli_mod.cmd_sync_status(_mk_sync_status_args(state_file=state_file))
    assert rc == 0
    out = capsys.readouterr().out
    assert "never" in out or "pre-upgrade" in out
    assert "No per-adapter counters" in out
    assert "Quarantined sources: 0" in out


def test_sync_status_flag_short_circuits_before_convert(tmp_path, monkeypatch, capsys):
    """``sync --status`` must report observability and never reach ``convert_all``."""
    state_file = tmp_path / "state.json"
    state_file.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(cli_mod, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(sync_status_mod, "REPO_ROOT", tmp_path)
    args = cli_mod.build_parser().parse_args(["sync", "--status", "--vault", str(tmp_path)])
    with patch("llmwiki.cli.convert_all") as convert:
        rc = cli_mod.cmd_sync(args)
    assert rc == 0
    convert.assert_not_called()
    out = capsys.readouterr().out
    assert "Last sync:" in out
    assert "Quarantined sources:" in out


def test_cli_sync_status_argv_exits_zero():
    """``python -m llmwiki sync --status`` must exit 0 and print the status banner."""
    cp = _run_cli("sync", "--status")
    assert "Traceback" not in cp.stderr
    assert cp.returncode == 0
    assert "Last sync:" in cp.stdout
    assert "Quarantined sources:" in cp.stdout


# ─── state migration preserves _meta / _counters ──────────────────────────


def test_migrate_preserves_underscore_prefixed_keys(tmp_path):
    """Legacy migration must keep ``_meta`` and ``_counters`` keys untouched."""
    legacy = {
        "_meta": {"last_sync": "2026-04-20T00:00:00Z"},
        "_counters": {"claude_code": {"discovered": 10}},
        "claude_code::.claude/projects/x/a.jsonl": 1.0,
    }
    migrated, count = _migrate_legacy_state(legacy, ["claude_code"])
    assert "_meta" in migrated
    assert migrated["_meta"]["last_sync"] == "2026-04-20T00:00:00Z"
    assert "_counters" in migrated
    assert migrated["_counters"]["claude_code"]["discovered"] == 10
    assert count == 0  # no legacy absolute paths in this fixture


def test_migrate_preserves_meta_through_legacy_path_rewrite(tmp_path, monkeypatch):
    """Rewriting legacy absolute paths must not drop ``_meta`` from the migrated state."""
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    legacy_abs = str(tmp_path / ".claude" / "projects" / "x" / "old.jsonl")
    legacy = {
        "_meta": {"last_sync": "2026-04-20T00:00:00Z"},
        legacy_abs: 1.0,
    }
    migrated, count = _migrate_legacy_state(legacy, ["claude_code"])
    assert count == 1
    assert "_meta" in migrated
    assert any(k.startswith("claude_code::") for k in migrated if not k.startswith("_"))


# ─── test helpers ─────────────────────────────────────────────────────────


def _mk_sync_status_args(*, recent=0, vault=None, state_file=None):
    class _A:
        pass
    a = _A()
    a.recent = recent
    a.vault = vault
    a.state_file = state_file
    return a
