"""Tests for automation install renderers + status + hook merge."""

from __future__ import annotations

import json
from pathlib import Path

from llmwiki.automation_install import (
    HOOK_MARKER,
    merge_claude_session_start_hook,
    merge_cursor_session_start_hook,
    profile_command,
    render_systemd_timer,
    run_install,
)
from llmwiki.automation_status import load_status


def test_profile_command_b_uses_synth_not_synthesize(tmp_path: Path):
    """Profile B must call ``synth`` (sources + harvest), not deprecated ``synthesize``."""
    cmd = profile_command("B", "python3", tmp_path)
    assert "llmwiki synth &&" in cmd
    assert "synthesize" not in cmd
    assert "sync --no-auto-build" in cmd
    assert "llmwiki build" in cmd


def test_profile_command_c_is_all_pipeline(tmp_path: Path):
    cmd = profile_command("C", "python3", tmp_path)
    assert "all --with-sync --with-synth --skip-graph" in cmd
    assert "synthesize" not in cmd


def test_systemd_timer_persistent_and_time():
    text = render_systemd_timer(hour=8, minute=0)
    assert "Persistent=true" in text
    assert "08:00:00" in text


def test_hook_merge_idempotent():
    settings: dict = {"hooks": {}}
    cmd = "python3 -m llmwiki sync"
    once = merge_claude_session_start_hook(settings, cmd, install=True)
    twice = merge_claude_session_start_hook(once, cmd, install=True)
    blob = json.dumps(twice)
    assert blob.count(HOOK_MARKER) == 1
    removed = merge_claude_session_start_hook(twice, cmd, install=False)
    assert HOOK_MARKER not in json.dumps(removed)


def test_cursor_hook_merge_idempotent():
    hooks = {"version": 1, "hooks": {}}
    cmd = "python3 -m llmwiki sync"
    once = merge_cursor_session_start_hook(hooks, cmd, install=True)
    twice = merge_cursor_session_start_hook(once, cmd, install=True)
    assert json.dumps(twice).count(HOOK_MARKER) == 1


def test_run_install_writes_status_and_units(tmp_path: Path):
    vault = tmp_path / "vault"
    vault.mkdir()
    units = tmp_path / "units"
    status = run_install({
        "profile": "A",
        "hour": 8,
        "minute": 0,
        "working_dir": tmp_path,
        "python_bin": "python3",
        "vault_root": vault,
        "write_units_dir": units,
        "force_platform": "linux",
        "synth_backend": "dummy",
    })
    assert status["profile"] == "A"
    loaded = load_status(vault)
    assert loaded is not None
    assert loaded["hour"] == 8
    assert (units / "llmwiki-maintain.timer").is_file()
    assert (units / "llmwiki-maintain.sh").is_file()
    assert "no-op" in (loaded.get("note") or "")
