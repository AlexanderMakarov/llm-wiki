"""Tests for ``filters.exclude_empty`` (#188).

Content-free transcripts (zero user messages and zero tool calls) are skipped
at ingest like ``exclude_headless``, persisted in sync state, and excluded
from synthesis / ``--estimate`` when already in ``raw/``.
"""

from __future__ import annotations

import json
from builtins import classmethod
from pathlib import Path

from llmwiki import convert as c
from llmwiki._frontmatter import is_empty_session
from llmwiki.adapters.claude_code import ClaudeCodeAdapter
from llmwiki.convert import DEFAULT_CONFIG, count_tool_calls, count_user_messages
from llmwiki.convert import is_empty_session as is_empty_records
from llmwiki.synth.estimate import synthesize_estimate_report
from llmwiki.synth.pipeline import DEFAULT_EXCLUDE_EMPTY, resolve_exclude_empty


def test_empty_session_unit_both_zero():
    records = [{"type": "assistant", "message": {"role": "assistant", "content": "x"}}]
    assert count_user_messages(records) == 0
    assert count_tool_calls(records) == 0
    assert is_empty_records(records) is True


def test_empty_session_false_with_user_message():
    records = [
        {
            "type": "user",
            "message": {"role": "user", "content": "hi"},
        }
    ]
    assert is_empty_records(records) is False


def test_empty_session_false_with_tool_call_only():
    records = [
        {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [{"type": "tool_use", "name": "Read", "input": {}}],
            },
        }
    ]
    assert count_user_messages(records) == 0
    assert count_tool_calls(records) == 1
    assert is_empty_records(records) is False


def test_is_empty_session_frontmatter():
    assert is_empty_session({"user_messages": 0, "tool_calls": 0}) is True
    assert is_empty_session({"user_messages": 1, "tool_calls": 0}) is False
    assert is_empty_session({"user_messages": 0, "tool_calls": 2}) is False
    assert is_empty_session({}) is False


def test_exclude_empty_defaults_to_on():
    assert DEFAULT_EXCLUDE_EMPTY is True
    assert DEFAULT_CONFIG["filters"]["exclude_empty"] is True
    assert resolve_exclude_empty({}) is True
    assert resolve_exclude_empty({"filters": {"exclude_empty": False}}) is False


def _write_session(path: Path, *, extra_lines: str = "", **kwargs) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    base = {
        "type": "user",
        "sessionId": kwargs.get("session_id", "sess-1"),
        "slug": kwargs.get("slug", "demo"),
        "timestamp": kwargs.get("timestamp", "2026-04-16T10:00:00Z"),
        "cwd": kwargs.get("cwd", "/home/user/proj"),
        "entrypoint": kwargs.get("entrypoint", "cli"),
        "promptSource": kwargs.get("prompt_source", "typed"),
        "gitBranch": "main",
    }
    if "user_content" in kwargs:
        base["message"] = {"role": "user", "content": kwargs["user_content"]}
    else:
        base["message"] = {"role": "user", "content": "hi"}
    path.write_text(json.dumps(base) + "\n" + extra_lines, encoding="utf-8")


def _seed(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    home = tmp_path / "home"
    home.mkdir()
    proj = home / ".claude" / "projects" / "my-proj"
    out_dir = tmp_path / "repo" / "raw" / "sessions"
    state = tmp_path / "state.json"
    return home, proj, out_dir, state


def _patch(monkeypatch, home, state):
    store = home / ".claude" / "projects"
    monkeypatch.setattr(
        ClaudeCodeAdapter,
        "default_session_store_path",
        classmethod(lambda cls, s=store: s),
    )
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setattr(c, "REPO_ROOT", home.parent / "repo")


def _write_config(tmp_path: Path, filters: dict) -> Path:
    cfg = tmp_path / "sessions_config.json"
    cfg.write_text(json.dumps({"filters": filters}), encoding="utf-8")
    return cfg


def _write_empty_jsonl(proj: Path, name: str = "empty.jsonl") -> None:
    proj.mkdir(parents=True, exist_ok=True)
    (proj / name).write_text(
        json.dumps({
            "type": "assistant",
            "sessionId": "e1",
            "slug": "empty",
            "timestamp": "2026-04-16T10:00:00Z",
            "cwd": "/home/user/proj",
            "message": {"role": "assistant", "content": ""},
        }) + "\n",
        encoding="utf-8",
    )


def test_convert_all_skips_empty_by_default(tmp_path, monkeypatch):
    home, proj, out_dir, state = _seed(tmp_path)
    _write_empty_jsonl(proj)
    _patch(monkeypatch, home, state)
    c.discover_adapters()
    c.convert_all(
        adapters=["claude_code"],
        out_dir=out_dir,
        state_file=state,
        config_file=tmp_path / "nonexistent.json",
        include_current=True,
    )
    assert sorted(out_dir.rglob("*.md")) == []


def test_convert_all_keeps_user_message_only(tmp_path, monkeypatch):
    home, proj, out_dir, state = _seed(tmp_path)
    _write_session(proj / "question.jsonl")
    _patch(monkeypatch, home, state)
    c.discover_adapters()
    c.convert_all(
        adapters=["claude_code"],
        out_dir=out_dir,
        state_file=state,
        config_file=tmp_path / "nonexistent.json",
        include_current=True,
    )
    assert len(sorted(out_dir.rglob("*.md"))) == 1


def test_convert_all_keeps_tool_call_only(tmp_path, monkeypatch):
    home, proj, out_dir, state = _seed(tmp_path)
    proj.mkdir(parents=True, exist_ok=True)
    (proj / "tools.jsonl").write_text(
        json.dumps({
            "type": "assistant",
            "sessionId": "t1",
            "slug": "tools",
            "timestamp": "2026-04-16T10:00:00Z",
            "cwd": "/home/user/proj",
            "message": {
                "role": "assistant",
                "content": [{"type": "tool_use", "name": "Read", "input": {}}],
            },
        }) + "\n",
        encoding="utf-8",
    )
    _patch(monkeypatch, home, state)
    c.discover_adapters()
    c.convert_all(
        adapters=["claude_code"],
        out_dir=out_dir,
        state_file=state,
        config_file=tmp_path / "nonexistent.json",
        include_current=True,
    )
    assert len(sorted(out_dir.rglob("*.md"))) == 1


def test_exclude_empty_opt_out(tmp_path, monkeypatch):
    home, proj, out_dir, state = _seed(tmp_path)
    _write_empty_jsonl(proj)
    _patch(monkeypatch, home, state)
    cfg = _write_config(tmp_path, {"exclude_empty": False})
    c.discover_adapters()
    c.convert_all(
        adapters=["claude_code"],
        out_dir=out_dir,
        state_file=state,
        config_file=cfg,
        include_current=True,
    )
    assert len(sorted(out_dir.rglob("*.md"))) == 1


def test_summary_reports_empty_breakdown(tmp_path, monkeypatch, capsys):
    home, proj, out_dir, state = _seed(tmp_path)
    _write_empty_jsonl(proj)
    _write_session(proj / "good.jsonl")
    _patch(monkeypatch, home, state)
    c.discover_adapters()
    c.convert_all(
        adapters=["claude_code"],
        out_dir=out_dir,
        state_file=state,
        config_file=tmp_path / "nonexistent.json",
        include_current=True,
    )
    out = capsys.readouterr().out
    assert "1 empty" in out
    assert "exclude_empty" in out


def test_filtered_empty_persists_mtime(tmp_path, monkeypatch):
    home, proj, out_dir, state = _seed(tmp_path)
    _write_empty_jsonl(proj)
    _patch(monkeypatch, home, state)
    c.discover_adapters()
    c.convert_all(
        adapters=["claude_code"],
        out_dir=out_dir,
        state_file=state,
        config_file=tmp_path / "nonexistent.json",
        include_current=True,
    )
    saved = json.loads(state.read_text(encoding="utf-8"))
    assert saved.get("sync", {}).get("files")


class _P:
    def __init__(self, rel: str):
        self._rel = rel
        self.name = rel.split("/")[-1]

    def __str__(self) -> str:
        return self._rel

    def relative_to(self, other):
        return self


def test_estimate_excludes_empty_from_backlog():
    sessions = [
        (_P("proj/real.md"), {"project": "proj", "user_messages": 1, "tool_calls": 0}, "body " * 50),
        (_P("proj/empty.md"), {"project": "proj", "user_messages": 0, "tool_calls": 0}, "body " * 50),
    ]
    rpt = synthesize_estimate_report(raw_sessions=sessions, state_keys=set(), exclude_empty=True)
    assert rpt["new_sessions"] == 1
    assert rpt["excluded_empty"] == 1


def test_estimate_includes_empty_when_filter_disabled():
    sessions = [
        (_P("proj/real.md"), {"project": "proj", "user_messages": 1, "tool_calls": 0}, "body " * 50),
        (_P("proj/empty.md"), {"project": "proj", "user_messages": 0, "tool_calls": 0}, "body " * 50),
    ]
    rpt = synthesize_estimate_report(raw_sessions=sessions, state_keys=set(), exclude_empty=False)
    assert rpt["new_sessions"] == 2
    assert rpt["excluded_empty"] == 0
