"""Whole-feature acceptance tests for #180: exclude_headless across adapters.

# @layer: integration
# @spec: 175-exclude-headless-adapters
# @regression

Slice tests (``test_exclude_headless*.py``, ``test_cursor_cli_exclude_headless.py``,
``test_adapter_exclude_headless_slice3.py``, ``test_adapter_is_headless_contract.py``,
``test_docs_adapter_currency.py``) cover per-adapter rules and docs currency. This
file verifies the feature **as a whole** against functional-spec.md R1–R6.

AC coverage matrix:

    R1.1 interactive kept on sync              -> test_mixed_sync_keeps_interactive_claude_and_cursor
    R1.2 automated skipped on sync             -> test_mixed_sync_skips_headless_claude_and_cursor
    R1.2 automated omitted from estimate       -> test_estimate_omits_marked_headless_from_both_adapters
    R1.3 filter off includes automated         -> test_filter_off_sync_includes_headless_from_both_adapters
    R1.4 legacy unmarked stays eligible        -> test_legacy_unmarked_cursor_raw_stays_in_estimate_backlog
    R2.1 Cursor CLI auto-review skipped        -> covered by test_cursor_cli_exclude_headless.py
    R2.2 IDE ingest not claimed fixed          -> test_support_map_distinguishes_cursor_cli_from_ide
    R3.1 OpenClaw interactive collected        -> test_openclaw_convert_keeps_session_under_default_filter
    R3.2 dreaming N/A at store layer           -> test_openclaw_never_classified_headless (unit in slice3)
    R4   Obsidian/ChatGPT N/A in docs          -> test_support_map_marks_non_applicable_sources
    R4   scaffold N/A in docs                  -> test_support_map_marks_scaffold_sources
    R5   aggregate headless sync summary       -> test_mixed_sync_reports_aggregate_headless_count_only
    R6   support map + per-source automated    -> test_support_map_section_covers_working_sources
    R6   docs currency                         -> covered by test_docs_adapter_currency.py
    R6   synth skips cursor headless in raw    -> test_synthesize_skips_cursor_headless_already_in_raw

Contract (every adapter defines ``is_headless_session``):
    covered by test_adapter_is_headless_contract.py
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from llmwiki import convert as c
from llmwiki.adapters.claude_code import ClaudeCodeAdapter
from llmwiki.adapters.contrib.openclaw import OpenClawAdapter
from llmwiki.synth.base import DummySynthesizer
from llmwiki.synth.estimate import synthesize_estimate_report
from llmwiki.synth.pipeline import synthesize_new_sessions
from tests.conftest import REPO_ROOT
from tests.test_cursor_cli_exclude_headless import (
    _make_cursor_store,
    _patch_cursor,
    _seed_cursor,
)

_SUPPORT_MAP = REPO_ROOT / "docs" / "multi-agent-setup.md"


# ─── helpers ─────────────────────────────────────────────────────────────


def _write_claude_session(
    path: Path,
    *,
    entrypoint: str = "cli",
    prompt_source: str = "typed",
    session_id: str = "sess-1",
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "type": "user",
                "sessionId": session_id,
                "slug": session_id,
                "timestamp": "2026-04-16T10:00:00Z",
                "cwd": "/home/user/proj",
                "entrypoint": entrypoint,
                "promptSource": prompt_source,
                "message": {"role": "user", "content": "hi"},
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _seed_claude(tmp_path: Path) -> tuple[Path, Path]:
    home = tmp_path / "home"
    proj = home / ".claude" / "projects" / "my-proj"
    proj.mkdir(parents=True)
    return home, proj


def _patch_claude(monkeypatch, home: Path) -> None:
    store = home / ".claude" / "projects"
    monkeypatch.setattr(ClaudeCodeAdapter, "session_store_path", store, raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setattr(c, "REPO_ROOT", home.parent / "repo")


def _write_config(tmp_path: Path, body: dict) -> Path:
    cfg = tmp_path / "sessions_config.json"
    cfg.write_text(json.dumps(body), encoding="utf-8")
    return cfg


def _openclaw_session_jsonl(content_hint: str = "ordinary chat") -> str:
    return (
        json.dumps({"type": "session", "id": "s1", "cwd": "/vault"})
        + "\n"
        + json.dumps(
            {
                "type": "message",
                "id": "m1",
                "timestamp": "2026-04-16T10:00:00Z",
                "message": {
                    "role": "user",
                    "content": [{"type": "text", "text": content_hint}],
                },
            }
        )
        + "\n"
    )


class _FakePath:
    def __init__(self, rel: str):
        self._rel = rel
        self.name = rel.split("/")[-1]
        self.stem = self.name.removesuffix(".md")

    def __str__(self) -> str:
        return self._rel

    def relative_to(self, other):
        return self


# ─── R1 + R5: mixed-adapter sync policy ───────────────────────────────────


def test_mixed_sync_keeps_interactive_claude_and_cursor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """@spec: 175-exclude-headless-adapters — R1 interactive sessions stay eligible."""
    # @regression
    home, proj = _seed_claude(tmp_path)
    chats, out_dir, state = _seed_cursor(tmp_path)
    _write_claude_session(proj / "good.jsonl")
    _make_cursor_store(chats / "store.db", store_meta={"approvalMode": "unrestricted"})
    _patch_claude(monkeypatch, home)
    _patch_cursor(monkeypatch, home)
    c.discover_adapters()
    c.convert_all(
        adapters=["claude_code", "cursor_cli"],
        out_dir=out_dir,
        state_file=state,
        config_file=tmp_path / "missing.json",
        include_current=True,
    )
    files = sorted(out_dir.rglob("*.md"))
    assert len(files) == 2
    bodies = "\n".join(p.read_text(encoding="utf-8") for p in files)
    assert "is_headless: false" in bodies


def test_mixed_sync_skips_headless_claude_and_cursor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """@spec: 175-exclude-headless-adapters — R1 automated launches skipped on sync."""
    # @regression
    home, proj = _seed_claude(tmp_path)
    chats, out_dir, state = _seed_cursor(tmp_path)
    _write_claude_session(
        proj / "sdk.jsonl",
        entrypoint="sdk-cli",
        prompt_source="sdk",
        session_id="sdk",
    )
    _make_cursor_store(chats / "store.db", store_meta={"approvalMode": "auto-review"})
    _patch_claude(monkeypatch, home)
    _patch_cursor(monkeypatch, home)
    c.discover_adapters()
    c.convert_all(
        adapters=["claude_code", "cursor_cli"],
        out_dir=out_dir,
        state_file=state,
        config_file=tmp_path / "missing.json",
        include_current=True,
    )
    assert sorted(out_dir.rglob("*.md")) == []


def test_mixed_sync_reports_aggregate_headless_count_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """@spec: 175-exclude-headless-adapters — R5 one aggregate headless count, no per-agent line."""
    # @regression
    home, proj = _seed_claude(tmp_path)
    chats, out_dir, state = _seed_cursor(tmp_path)
    _write_claude_session(
        proj / "sdk.jsonl",
        entrypoint="sdk-cli",
        prompt_source="sdk",
        session_id="sdk",
    )
    _make_cursor_store(
        chats / "store.db",
        store_meta={"subagentInfo": {"typeName": "generalPurpose"}},
    )
    _patch_claude(monkeypatch, home)
    _patch_cursor(monkeypatch, home)
    c.discover_adapters()
    c.convert_all(
        adapters=["claude_code", "cursor_cli"],
        out_dir=out_dir,
        state_file=state,
        config_file=tmp_path / "missing.json",
        include_current=True,
    )
    out = capsys.readouterr().out
    assert "2 headless" in out
    assert "cursor_cli" not in out.split("filtered breakdown")[-1]
    assert "claude_code" not in out.split("filtered breakdown")[-1]


def test_filter_off_sync_includes_headless_from_both_adapters(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """@spec: 175-exclude-headless-adapters — R1 filter off includes automated launches."""
    # @regression
    home, proj = _seed_claude(tmp_path)
    chats, out_dir, state = _seed_cursor(tmp_path)
    _write_claude_session(
        proj / "sdk.jsonl",
        entrypoint="sdk-cli",
        prompt_source="sdk",
        session_id="sdk",
    )
    _make_cursor_store(chats / "store.db", store_meta={"approvalMode": "auto-review"})
    _patch_claude(monkeypatch, home)
    _patch_cursor(monkeypatch, home)
    cfg = _write_config(tmp_path, {"filters": {"exclude_headless": False}})
    c.discover_adapters()
    c.convert_all(
        adapters=["claude_code", "cursor_cli"],
        out_dir=out_dir,
        state_file=state,
        config_file=cfg,
        include_current=True,
    )
    files = sorted(out_dir.rglob("*.md"))
    assert len(files) == 2
    bodies = "\n".join(p.read_text(encoding="utf-8") for p in files)
    assert bodies.count("is_headless: true") == 2


# ─── R1: estimate + synth share the same policy ──────────────────────────


def test_estimate_omits_marked_headless_from_both_adapters() -> None:
    """@spec: 175-exclude-headless-adapters — R1 estimate excludes automated sessions."""
    # @regression
    raw_sessions = [
        (
            _FakePath("proj/interactive-claude.md"),
            {"project": "proj", "is_headless": False},
            "body " * 200,
        ),
        (
            _FakePath("proj/headless-claude.md"),
            {
                "project": "proj",
                "is_headless": True,
                "entrypoint": "sdk-cli",
                "promptSource": "sdk",
            },
            "body " * 200,
        ),
        (
            _FakePath("proj/interactive-cursor.md"),
            {"project": "proj", "is_headless": False, "approvalMode": "unrestricted"},
            "body " * 200,
        ),
        (
            _FakePath("proj/headless-cursor.md"),
            {
                "project": "proj",
                "is_headless": True,
                "approvalMode": "auto-review",
            },
            "body " * 200,
        ),
    ]
    rpt = synthesize_estimate_report(
        raw_sessions=raw_sessions,
        state_keys=set(),
        exclude_headless=True,
    )
    assert rpt["new_sessions"] == 2
    assert rpt["excluded_headless"] == 2
    rels = {it["rel"] for it in rpt["unsynth_items"]}
    assert "interactive-claude" in next(r for r in rels if "interactive-claude" in r)
    assert "interactive-cursor" in next(r for r in rels if "interactive-cursor" in r)
    assert all("headless" not in rel for rel in rels)


def test_legacy_unmarked_cursor_raw_stays_in_estimate_backlog() -> None:
    """@spec: 175-exclude-headless-adapters — R1 legacy raw without markers stays eligible."""
    # @regression
    raw_sessions = [
        (
            _FakePath("proj/legacy-cursor.md"),
            {"project": "proj", "approvalMode": "auto-review"},
            "body " * 200,
        ),
    ]
    rpt = synthesize_estimate_report(
        raw_sessions=raw_sessions,
        state_keys=set(),
        exclude_headless=True,
    )
    assert rpt["new_sessions"] == 1
    assert rpt["excluded_headless"] == 0


_CURSOR_HEADLESS_RAW = """---
title: "Session: cursor auto"
type: source
date: 2026-04-16
source_file: raw/sessions/cursor-ws/2026-04-16-auto.md
slug: auto
project: cursor-ws
is_subagent: false
is_headless: true
approvalMode: auto-review
---

# auto

Automated Cursor Agent CLI run.
"""

_CURSOR_INTERACTIVE_RAW = """---
title: "Session: cursor chat"
type: source
date: 2026-04-16
source_file: raw/sessions/cursor-ws/2026-04-16-chat.md
slug: chat
project: cursor-ws
is_subagent: false
is_headless: false
approvalMode: unrestricted
---

# chat

Interactive Cursor Agent CLI run.
"""


def test_synthesize_skips_cursor_headless_already_in_raw(tmp_path: Path) -> None:
    """@spec: 175-exclude-headless-adapters — R1 synth backlog honours cursor is_headless."""
    # @regression
    raw = tmp_path / "raw" / "sessions" / "cursor-ws"
    raw.mkdir(parents=True)
    (raw / "2026-04-16-auto.md").write_text(_CURSOR_HEADLESS_RAW, encoding="utf-8")
    (raw / "2026-04-16-chat.md").write_text(_CURSOR_INTERACTIVE_RAW, encoding="utf-8")
    wiki_sources = tmp_path / "wiki" / "sources"
    wiki_sources.mkdir(parents=True)
    summary = synthesize_new_sessions(
        backend=DummySynthesizer(),
        raw_dir=tmp_path / "raw" / "sessions",
        wiki_sources_dir=wiki_sources,
        state_file=tmp_path / "state.json",
        include_docs=False,
        exclude_headless=True,
    )
    assert summary["synthesized"] == 1
    written = sorted(p.name for p in wiki_sources.rglob("*.md"))
    assert written == ["2026-04-16-chat.md"]


# ─── R3: OpenClaw stays eligible ─────────────────────────────────────────


def test_openclaw_convert_keeps_session_under_default_filter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """@spec: 175-exclude-headless-adapters — R3 normal OpenClaw session collected."""
    # @regression
    home = tmp_path / "home"
    agents = home / ".openclaw" / "agents" / "main" / "sessions"
    agents.mkdir(parents=True)
    session = agents / "uuid-openclaw.jsonl"
    session.write_text(
        _openclaw_session_jsonl("dreaming is mentioned but store has no mode marker"),
        encoding="utf-8",
    )
    out_dir = tmp_path / "repo" / "raw" / "sessions"
    state = tmp_path / "state.json"
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setattr(c, "REPO_ROOT", tmp_path / "repo")
    cfg = _write_config(
        tmp_path,
        {"adapters": {"openclaw": {"roots": [str(home / ".openclaw" / "agents")]}}},
    )
    c.discover_adapters()
    c.convert_all(
        adapters=["openclaw"],
        out_dir=out_dir,
        state_file=state,
        config_file=cfg,
        include_current=True,
    )
    files = sorted(out_dir.rglob("*.md"))
    assert len(files) == 1
    text = files[0].read_text(encoding="utf-8")
    assert "is_headless: false" in text
    assert OpenClawAdapter().is_headless_session([]) is False


# ─── R2 / R4 / R6: docs support map ──────────────────────────────────────


@pytest.fixture(scope="module")
def support_map_text() -> str:
    return _SUPPORT_MAP.read_text(encoding="utf-8")


def test_support_map_section_covers_working_sources(support_map_text: str) -> None:
    """@spec: 175-exclude-headless-adapters — R6 dedicated support section."""
    # @regression
    assert "## Which agents are supported" in support_map_text
    for name in (
        "claude_code",
        "codex_cli",
        "cursor_cli",
        "openclaw",
        "opencode",
        "copilot_cli",
        "copilot_chat",
        "gemini_cli",
        "chatgpt",
        "obsidian",
    ):
        assert name in support_map_text, f"missing registry name {name!r}"


def test_support_map_distinguishes_cursor_cli_from_ide(support_map_text: str) -> None:
    """@spec: 175-exclude-headless-adapters — R2/R6 Cursor Agent CLI vs IDE (#2)."""
    # @regression
    assert "### Cursor Agent CLI vs Cursor IDE" in support_map_text
    assert "`cursor_cli`" in support_map_text
    assert "#2" in support_map_text
    assert "IDE" in support_map_text


def test_support_map_marks_non_applicable_sources(support_map_text: str) -> None:
    """@spec: 175-exclude-headless-adapters — R4 Obsidian + ChatGPT N/A."""
    # @regression
    assert "Not applicable" in support_map_text or "not applicable" in support_map_text.lower()
    assert "notes intake" in support_map_text.lower()
    assert "ChatGPT export" in support_map_text


def test_support_map_marks_scaffold_sources(support_map_text: str) -> None:
    """@spec: 175-exclude-headless-adapters — R4 Gemini CLI / Cursor IDE scaffold N/A."""
    # @regression
    assert "Scaffold" in support_map_text
    assert "N/A until launch detection" in support_map_text or "never classified headless" in support_map_text


def test_support_map_documents_openclaw_headless_rule(support_map_text: str) -> None:
    """@spec: 175-exclude-headless-adapters — R3/R6 OpenClaw interactive rule in support map."""
    # @regression
    assert "## What" in support_map_text and "automated" in support_map_text.lower()
    assert "OpenClaw" in support_map_text
    assert "not headless" in support_map_text.lower()


def test_support_map_documents_exclude_headless_default_and_toggle(
    support_map_text: str,
) -> None:
    """@spec: 175-exclude-headless-adapters — R6 default skip + how to turn off."""
    # @regression
    assert "exclude_headless" in support_map_text
    assert '"exclude_headless": false' in support_map_text or "exclude_headless`: false" in support_map_text
