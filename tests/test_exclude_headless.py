"""Tests for the headless / temp-cwd ingest filters (#8).

llmwiki used to ingest headless ``claude -p`` / Agent-SDK sessions the
same as interactive ones, which both pollutes the wiki and — when the
synthesizer itself shells out to ``claude -p`` — creates a feedback loop
(synthesis runs get logged as new sessions, re-synthesized, ad infinitum).
Interactive sessions run from a throwaway temp cwd (e2e runs, scratch
worktrees) are similarly junk. Both are filtered at ingest, default-on,
toggleable via ``sessions_config.json``::

    { "filters": { "exclude_headless": true, "exclude_temp_cwd": true } }
"""

from __future__ import annotations

import json
from pathlib import Path

from llmwiki import convert as c
from llmwiki.convert import (
    DEFAULT_CONFIG,
    is_headless_session,
    is_temp_cwd_session,
)


# ─── unit: is_headless_session ───────────────────────────────────────────


def test_headless_true_for_sdk_cli_entrypoint():
    records = [{"type": "user", "entrypoint": "sdk-cli", "promptSource": "sdk"}]
    assert is_headless_session(records) is True


def test_headless_true_for_sdk_py_entrypoint_alone():
    # The Python SDK reports entrypoint=sdk-py. Even if promptSource were
    # absent on every record, the entrypoint prefix must flag it headless.
    records = [{"type": "user", "entrypoint": "sdk-py"}]
    assert is_headless_session(records) is True


def test_headless_true_for_sdk_prompt_source():
    # Only promptSource flags it; entrypoint absent.
    records = [{"type": "user", "promptSource": "sdk"}]
    assert is_headless_session(records) is True


def test_headless_true_if_any_record_is_headless():
    records = [
        {"type": "user", "entrypoint": "cli", "promptSource": "typed"},
        {"type": "user", "entrypoint": "sdk-cli", "promptSource": "sdk"},
    ]
    assert is_headless_session(records) is True


def test_headless_false_for_interactive_session():
    records = [
        {"type": "user", "entrypoint": "cli", "promptSource": "typed"},
        {"type": "assistant", "entrypoint": "cli", "promptSource": "queued"},
    ]
    assert is_headless_session(records) is False


def test_headless_false_when_fields_absent():
    records = [{"type": "user", "message": {"content": "hi"}}]
    assert is_headless_session(records) is False


# ─── unit: is_temp_cwd_session ───────────────────────────────────────────


def test_temp_cwd_true_for_tmp_exact():
    assert is_temp_cwd_session([{"cwd": "/tmp"}]) is True


def test_temp_cwd_true_for_tmp_prefix():
    assert is_temp_cwd_session([{"cwd": "/tmp/awos-e2e-1234"}]) is True


def test_temp_cwd_true_for_var_folders():
    assert is_temp_cwd_session([{"cwd": "/var/folders/xy/abc/T/scratch"}]) is True


def test_temp_cwd_true_for_private_var_folders():
    assert is_temp_cwd_session([{"cwd": "/private/var/folders/xy/T/x"}]) is True


def test_temp_cwd_false_for_real_project():
    assert is_temp_cwd_session([{"cwd": "/home/user/code/my-proj"}]) is False


def test_temp_cwd_false_when_cwd_absent():
    assert is_temp_cwd_session([{"type": "user"}]) is False


# ─── config defaults ─────────────────────────────────────────────────────


def test_filters_default_on():
    assert DEFAULT_CONFIG["filters"]["exclude_headless"] is True
    assert DEFAULT_CONFIG["filters"]["exclude_temp_cwd"] is True


# ─── integration: convert_all ────────────────────────────────────────────


def _write_session(path: Path, *, cwd: str = "/home/user/proj",
                   entrypoint: str = "cli", prompt_source: str = "typed") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({
            "type": "user",
            "sessionId": "sess-1",
            "slug": "demo",
            "timestamp": "2026-04-16T10:00:00Z",
            "cwd": cwd,
            "entrypoint": entrypoint,
            "promptSource": prompt_source,
            "gitBranch": "main",
            "message": {"role": "user", "content": "hi"},
        }) + "\n"
        + json.dumps({
            "type": "assistant",
            "sessionId": "sess-1",
            "timestamp": "2026-04-16T10:00:01Z",
            "entrypoint": entrypoint,
            "message": {"role": "assistant", "content": "hello"},
        }) + "\n",
        encoding="utf-8",
    )


def _seed(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    home = tmp_path / "home"
    home.mkdir()
    proj = home / ".claude" / "projects" / "my-proj"
    out_dir = tmp_path / "repo" / "raw" / "sessions"
    state = tmp_path / "state.json"
    return home, proj, out_dir, state


def _patch(monkeypatch, home, state):
    from llmwiki.adapters.claude_code import ClaudeCodeAdapter
    store = home / ".claude" / "projects"
    monkeypatch.setattr(ClaudeCodeAdapter, "session_store_path", store, raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setattr(c, "DEFAULT_STATE_FILE", state)
    monkeypatch.setattr(c, "REPO_ROOT", home.parent / "repo")


def _write_config(tmp_path: Path, filters: dict) -> Path:
    cfg = tmp_path / "sessions_config.json"
    cfg.write_text(json.dumps({"filters": filters}), encoding="utf-8")
    return cfg


def test_convert_all_skips_headless_by_default(tmp_path, monkeypatch):
    home, proj, out_dir, state = _seed(tmp_path)
    _write_session(proj / "headless.jsonl", entrypoint="sdk-cli", prompt_source="sdk")
    _patch(monkeypatch, home, state)
    c.discover_adapters()
    c.convert_all(adapters=["claude_code"], out_dir=out_dir, state_file=state,
                  config_file=tmp_path / "nonexistent.json", include_current=True)
    assert sorted(out_dir.rglob("*.md")) == []


def test_convert_all_skips_temp_cwd_by_default(tmp_path, monkeypatch):
    home, proj, out_dir, state = _seed(tmp_path)
    _write_session(proj / "scratch.jsonl", cwd="/tmp/awos-e2e-99")
    _patch(monkeypatch, home, state)
    c.discover_adapters()
    c.convert_all(adapters=["claude_code"], out_dir=out_dir, state_file=state,
                  config_file=tmp_path / "nonexistent.json", include_current=True)
    assert sorted(out_dir.rglob("*.md")) == []


def test_convert_all_keeps_interactive_real_project(tmp_path, monkeypatch):
    home, proj, out_dir, state = _seed(tmp_path)
    _write_session(proj / "good.jsonl")  # cli / typed / /home/user/proj
    _patch(monkeypatch, home, state)
    c.discover_adapters()
    c.convert_all(adapters=["claude_code"], out_dir=out_dir, state_file=state,
                  config_file=tmp_path / "nonexistent.json", include_current=True)
    assert len(sorted(out_dir.rglob("*.md"))) == 1


def test_exclude_headless_can_be_disabled(tmp_path, monkeypatch):
    home, proj, out_dir, state = _seed(tmp_path)
    _write_session(proj / "headless.jsonl", entrypoint="sdk-cli", prompt_source="sdk")
    _patch(monkeypatch, home, state)
    cfg = _write_config(tmp_path, {"exclude_headless": False})
    c.discover_adapters()
    c.convert_all(adapters=["claude_code"], out_dir=out_dir, state_file=state,
                  config_file=cfg, include_current=True)
    assert len(sorted(out_dir.rglob("*.md"))) == 1


def test_exclude_temp_cwd_can_be_disabled(tmp_path, monkeypatch):
    home, proj, out_dir, state = _seed(tmp_path)
    _write_session(proj / "scratch.jsonl", cwd="/tmp/awos-e2e-99")
    _patch(monkeypatch, home, state)
    cfg = _write_config(tmp_path, {"exclude_temp_cwd": False})
    c.discover_adapters()
    c.convert_all(adapters=["claude_code"], out_dir=out_dir, state_file=state,
                  config_file=cfg, include_current=True)
    assert len(sorted(out_dir.rglob("*.md"))) == 1


def test_summary_reports_exclusion_breakdown(tmp_path, monkeypatch, capsys):
    # A silent 94%-corpus drop is the review's dominant complaint: the
    # summary must break out headless vs temp-cwd so the drop is visible.
    home, proj, out_dir, state = _seed(tmp_path)
    _write_session(proj / "headless.jsonl", entrypoint="sdk-cli", prompt_source="sdk")
    _write_session(proj / "scratch.jsonl", cwd="/tmp/awos-e2e-99")
    _write_session(proj / "good.jsonl")
    _patch(monkeypatch, home, state)
    c.discover_adapters()
    c.convert_all(adapters=["claude_code"], out_dir=out_dir, state_file=state,
                  config_file=tmp_path / "nonexistent.json", include_current=True)
    out = capsys.readouterr().out
    assert "1 headless" in out
    assert "1 temp-cwd" in out


def test_summary_omits_breakdown_when_nothing_excluded(tmp_path, monkeypatch, capsys):
    home, proj, out_dir, state = _seed(tmp_path)
    _write_session(proj / "good.jsonl")
    _patch(monkeypatch, home, state)
    c.discover_adapters()
    c.convert_all(adapters=["claude_code"], out_dir=out_dir, state_file=state,
                  config_file=tmp_path / "nonexistent.json", include_current=True)
    assert "filtered breakdown" not in capsys.readouterr().out
