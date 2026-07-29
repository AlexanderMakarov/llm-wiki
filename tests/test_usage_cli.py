"""Tests for the ``llmwiki usage`` subcommand (#26).

The command folds the per-process telemetry logs into totals and surfaces
them next to the synthesis *cost* already persisted in state, so the
"is this wiki earning its spend?" question is answerable at a glance.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from llmwiki import cli, state_store, usage


@pytest.fixture(autouse=True)
def _no_default_vault(monkeypatch):
    """The dev checkout has a gitignored config pointing at a real Obsidian
    vault; neutralise it so `usage` reads the patched REPO_ROOT."""
    monkeypatch.setattr(
        "llmwiki.config_schedule.load_default_vault_path", lambda: None)


def _ns(**kw) -> argparse.Namespace:
    base = dict(vault=None, state_file=None, json=False, compact=False)
    base.update(kw)
    return argparse.Namespace(**base)


def _seed_records(root: Path) -> None:
    rec = usage.UsageRecorder(root, pid=1, started="2026-07-16T09:00:00Z")
    caller = dict(caller_project="sde-automation",
                  caller_source=usage.CALLER_CLIENT_ROOT)
    rec.record(tool="wiki_search", query="sync", hits=3, resp_bytes=100, duration_ms=5, **caller)
    rec.record(tool="wiki_search", query="nothing", hits=0, resp_bytes=40, duration_ms=5, **caller)
    rec.record(tool="wiki_query", query="what", hits=2, resp_bytes=200, duration_ms=9, **caller)


def test_usage_json_reports_consumption(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    _seed_records(tmp_path)
    state_file = tmp_path / "llmwiki-state.json"

    rc = cli.cmd_usage(_ns(json=True, state_file=state_file))
    assert rc == 0

    payload = json.loads(capsys.readouterr().out)
    cons = payload["consumption"]
    assert cons["total_calls"] == 3
    assert cons["total_resp_bytes"] == 340
    assert cons["per_tool"]["wiki_search"]["calls"] == 2
    assert cons["per_tool"]["wiki_search"]["zero_hits"] == 1
    assert cons["per_project"]["sde-automation"]["calls"] == 3
    # cost side present even when state has no estimate yet
    assert "cost" in payload
    assert payload["cost"]["full_force_usd"] == 0.0


def test_usage_json_surfaces_synth_cost(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    _seed_records(tmp_path)
    state_file = tmp_path / "llmwiki-state.json"
    state = state_store.default_state()
    state["synth"]["estimate"] = {"full_force_usd": 56.0, "incremental_usd": 1.2}
    state_store.write_state(state, state_file)

    cli.cmd_usage(_ns(json=True, state_file=state_file))
    payload = json.loads(capsys.readouterr().out)
    assert payload["cost"]["full_force_usd"] == 56.0
    assert payload["cost"]["incremental_usd"] == 1.2


def test_usage_human_output_lists_tools(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    _seed_records(tmp_path)
    state_file = tmp_path / "llmwiki-state.json"

    rc = cli.cmd_usage(_ns(state_file=state_file))
    assert rc == 0
    out = capsys.readouterr().out
    assert "wiki_search" in out
    assert "wiki_query" in out


def test_usage_report_labels_calls_with_no_identified_caller(
    tmp_path: Path, monkeypatch, capsys
):
    """#51: calls the server couldn't attribute print as unattributed, not
    under a project slug someone might mistake for a real caller."""
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    usage.UsageRecorder(tmp_path, pid=1, started="2026-07-16T09:00:00Z").record(
        tool="wiki_query", hits=1)

    assert cli.cmd_usage(_ns(state_file=tmp_path / "llmwiki-state.json")) == 0
    out = capsys.readouterr().out
    assert "unattributed" in out


def test_usage_compact_folds_old_logs(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    # A June (past-month) file that --compact should fold + delete. The
    # record ts — not the wall clock — is what marks it past-month.
    usage.UsageRecorder(tmp_path, pid=7, started="2026-06-01T09:00:00Z").record(
        tool="wiki_search", hits=1, resp_bytes=10, duration_ms=1,
        ts="2026-06-01T09:00:00Z")
    state_file = tmp_path / "llmwiki-state.json"

    cli.cmd_usage(_ns(json=True, compact=True, state_file=state_file))
    # Compaction moved the June data into the kept-forever rollup.
    assert (tmp_path / "usage" / "rollup.json").exists()
    assert usage.load_rollup(tmp_path)["total_calls"] == 1
