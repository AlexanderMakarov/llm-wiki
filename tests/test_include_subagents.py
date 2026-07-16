"""Tests for the ``filters.include_subagents`` mode (#30).

Every ``Agent`` tool fan-out writes its own transcript, ingested as a
standalone raw session (``is_subagent: true``). In a real vault these are
the majority (59% of raw sessions) and synthesizing them individually is
mostly wasted tokens — the parent session already captured each subagent's
final report. ``include_subagents`` lets the user choose:

    all      — sync AND synthesize subagents like any other session.
    only-raw — sync into raw/ but SKIP in synthesize/queue backlog (DEFAULT).
    off      — don't convert subagent transcripts at all.
"""

from __future__ import annotations

import json
from pathlib import Path

from llmwiki import convert as c
from llmwiki._frontmatter import is_subagent
from llmwiki.convert import DEFAULT_CONFIG
from llmwiki.synth.pipeline import resolve_include_subagents


# ─── unit: is_subagent frontmatter helper ────────────────────────────────


def test_is_subagent_true_for_bool():
    assert is_subagent({"is_subagent": True}, Path("x.md")) is True


def test_is_subagent_true_for_string_true():
    assert is_subagent({"is_subagent": "true"}, Path("x.md")) is True


def test_is_subagent_false_for_string_false():
    assert is_subagent({"is_subagent": "false"}, Path("x.md")) is False


def test_is_subagent_falls_back_to_filename_when_field_absent():
    # Pre-#406 raw files have no is_subagent field; the renderer renames
    # sub-agent slugs to `<slug>-subagent-<id>`.
    assert is_subagent({}, Path("2026-04-16-proj-demo-subagent-ab12.md")) is True
    assert is_subagent({}, Path("2026-04-16-proj-demo.md")) is False


# ─── unit: resolve_include_subagents ─────────────────────────────────────


def test_mode_default_is_only_raw():
    assert resolve_include_subagents({}) == "only-raw"
    assert resolve_include_subagents(None) == "only-raw"


def test_mode_reads_config_value():
    assert resolve_include_subagents({"filters": {"include_subagents": "all"}}) == "all"
    assert resolve_include_subagents({"filters": {"include_subagents": "off"}}) == "off"


def test_mode_normalizes_case_and_whitespace():
    assert resolve_include_subagents({"filters": {"include_subagents": " ALL "}}) == "all"


def test_mode_invalid_falls_back_to_default():
    # A typo must not crash sync/synthesize — fall back to the shipped default.
    assert resolve_include_subagents({"filters": {"include_subagents": "bogus"}}) == "only-raw"


def test_default_config_ships_only_raw():
    assert DEFAULT_CONFIG["filters"]["include_subagents"] == "only-raw"


# ─── integration: convert_all honors "off" ───────────────────────────────


def _write_session(path: Path, *, session_id: str = "sess-1", slug: str = "demo",
                   timestamp: str = "2026-04-16T10:00:00Z") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({
            "type": "user", "sessionId": session_id, "slug": slug,
            "timestamp": timestamp, "cwd": "/home/user/proj",
            "entrypoint": "cli", "promptSource": "typed", "gitBranch": "main",
            "message": {"role": "user", "content": "hi"},
        }) + "\n"
        + json.dumps({
            "type": "assistant", "sessionId": session_id,
            "timestamp": "2026-04-16T10:00:01Z",
            "message": {"role": "assistant", "content": "hello"},
        }) + "\n",
        encoding="utf-8",
    )


def _seed(tmp_path: Path):
    home = tmp_path / "home"
    home.mkdir()
    proj = home / ".claude" / "projects" / "my-proj"
    out_dir = tmp_path / "repo" / "raw" / "sessions"
    state = tmp_path / "state.json"
    return home, proj, out_dir, state


def _patch(monkeypatch, home):
    from llmwiki.adapters.claude_code import ClaudeCodeAdapter
    store = home / ".claude" / "projects"
    monkeypatch.setattr(ClaudeCodeAdapter, "session_store_path", store, raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setattr(c, "REPO_ROOT", home.parent / "repo")


def _write_config(tmp_path: Path, filters: dict) -> Path:
    cfg = tmp_path / "sessions_config.json"
    cfg.write_text(json.dumps({"filters": filters}), encoding="utf-8")
    return cfg


def test_off_mode_drops_subagent_keeps_parent(tmp_path, monkeypatch):
    home, proj, out_dir, state = _seed(tmp_path)
    _write_session(proj / "parent.jsonl", session_id="parent", slug="coord")
    _write_session(
        proj / "parent" / "subagents" / "agent-ab12.jsonl",
        session_id="agent-ab12", slug="fanout",
    )
    _patch(monkeypatch, home)
    cfg = _write_config(tmp_path, {"include_subagents": "off"})
    c.discover_adapters()
    c.convert_all(adapters=["claude_code"], out_dir=out_dir, state_file=state,
                  config_file=cfg, include_current=True)
    written = sorted(p.name for p in out_dir.rglob("*.md"))
    assert len(written) == 1
    assert all("subagent" not in n for n in written)


def test_default_only_raw_keeps_subagent_in_raw(tmp_path, monkeypatch):
    # only-raw (the shipped default) still converts the subagent into raw/.
    home, proj, out_dir, state = _seed(tmp_path)
    _write_session(proj / "parent.jsonl", session_id="parent", slug="coord")
    _write_session(
        proj / "parent" / "subagents" / "agent-ab12.jsonl",
        session_id="agent-ab12", slug="fanout",
    )
    _patch(monkeypatch, home)
    c.discover_adapters()
    c.convert_all(adapters=["claude_code"], out_dir=out_dir, state_file=state,
                  config_file=tmp_path / "nonexistent.json", include_current=True)
    assert len(sorted(out_dir.rglob("*.md"))) == 2


def test_off_mode_persists_mtime_for_short_circuit(tmp_path, monkeypatch):
    # A dropped subagent must record its mtime so a no-op re-sync short-
    # circuits at the mtime check instead of re-parsing it every run.
    home, proj, out_dir, state = _seed(tmp_path)
    sub = proj / "parent" / "subagents" / "agent-ab12.jsonl"
    _write_session(sub, session_id="agent-ab12", slug="fanout")
    _patch(monkeypatch, home)
    cfg = _write_config(tmp_path, {"include_subagents": "off"})
    c.discover_adapters()
    c.convert_all(adapters=["claude_code"], out_dir=out_dir, state_file=state,
                  config_file=cfg, include_current=True)
    saved_files = json.loads(state.read_text())["sync"]["files"]
    assert any("agent-ab12" in k for k in saved_files)


def test_off_mode_does_not_delete_existing_raw(tmp_path, monkeypatch):
    # Requirement 2 (#30): switching to "off" only affects future syncs — a
    # subagent raw file already on disk (from a prior only-raw sync) is left
    # untouched, not deleted.
    home, proj, out_dir, state = _seed(tmp_path)
    _write_session(
        proj / "parent" / "subagents" / "agent-ab12.jsonl",
        session_id="agent-ab12", slug="fanout",
    )
    existing = out_dir / "my-proj" / "2026-04-16-my-proj-fanout-subagent-ab12.md"
    existing.parent.mkdir(parents=True, exist_ok=True)
    existing.write_text("pre-existing raw subagent page\n", encoding="utf-8")
    _patch(monkeypatch, home)
    cfg = _write_config(tmp_path, {"include_subagents": "off"})
    c.discover_adapters()
    c.convert_all(adapters=["claude_code"], out_dir=out_dir, state_file=state,
                  config_file=cfg, include_current=True)
    assert existing.exists()


def test_off_mode_summary_reports_subagent_breakdown(tmp_path, monkeypatch, capsys):
    home, proj, out_dir, state = _seed(tmp_path)
    _write_session(
        proj / "parent" / "subagents" / "agent-ab12.jsonl",
        session_id="agent-ab12", slug="fanout",
    )
    _patch(monkeypatch, home)
    cfg = _write_config(tmp_path, {"include_subagents": "off"})
    c.discover_adapters()
    c.convert_all(adapters=["claude_code"], out_dir=out_dir, state_file=state,
                  config_file=cfg, include_current=True)
    out = capsys.readouterr().out
    assert "subagent" in out.lower()


# ─── unit: synthesize_estimate_report honors only-raw ────────────────────


class _P:
    """Cheap Path-ish object for injecting raw_sessions without touching disk."""

    def __init__(self, rel: str):
        self._rel = rel
        self.name = rel.split("/")[-1]
        self.stem = self.name.rsplit(".", 1)[0]

    def __str__(self) -> str:
        return self._rel

    def relative_to(self, other):
        return self


def _mixed_sessions():
    # One normal coordinator session + one subagent fan-out, nothing synthed.
    return [
        (_P("proj/2026-04-16-coord.md"), {"project": "proj"}, "body " * 200),
        (_P("proj/2026-04-16-coord-subagent-ab12.md"),
         {"project": "proj", "is_subagent": True}, "body " * 200),
    ]


def test_estimate_only_raw_excludes_subagent_from_backlog():
    from llmwiki.synth.estimate import synthesize_estimate_report
    rpt = synthesize_estimate_report(
        raw_sessions=_mixed_sessions(),
        state_keys=set(),
        synthesized_source_keys=set(),
        include_subagents="only-raw",
    )
    assert rpt["new_sessions"] == 1
    rels = [it["rel"] for it in rpt["unsynth_items"]]
    assert all("subagent" not in r for r in rels)


def test_estimate_all_includes_subagent_in_backlog():
    from llmwiki.synth.estimate import synthesize_estimate_report
    rpt = synthesize_estimate_report(
        raw_sessions=_mixed_sessions(),
        state_keys=set(),
        synthesized_source_keys=set(),
        include_subagents="all",
    )
    assert rpt["new_sessions"] == 2


def test_estimate_defaults_to_only_raw():
    from llmwiki.synth.estimate import synthesize_estimate_report
    rpt = synthesize_estimate_report(
        raw_sessions=_mixed_sessions(),
        state_keys=set(),
        synthesized_source_keys=set(),
    )
    assert rpt["new_sessions"] == 1


# ─── integration: synthesize_new_sessions honors only-raw (incl. --force) ─


_COORD = """---
title: "Session: coord"
type: source
source_file: raw/sessions/proj/2026-04-16-coord.md
slug: coord
project: proj
is_subagent: false
---

# coord

## Summary
Coordinator session with [[pytest]].
"""

_SUBAGENT = """---
title: "Session: fanout"
type: source
source_file: raw/sessions/proj/2026-04-16-coord-subagent-ab12.md
slug: coord-subagent-ab12
project: proj
is_subagent: true
---

# fanout

## Summary
Subagent fan-out with [[pytest]].
"""


def _seed_raw_pair(tmp_path: Path) -> tuple[Path, Path]:
    raw = tmp_path / "raw" / "sessions" / "proj"
    raw.mkdir(parents=True)
    (raw / "2026-04-16-coord.md").write_text(_COORD, encoding="utf-8")
    (raw / "2026-04-16-coord-subagent-ab12.md").write_text(_SUBAGENT, encoding="utf-8")
    return tmp_path / "raw" / "sessions", tmp_path / "wiki" / "sources"


def _synth_written(wiki_sources: Path) -> list[str]:
    return sorted(p.name for p in wiki_sources.rglob("*.md"))


def test_synthesize_only_raw_skips_subagent(tmp_path: Path):
    from llmwiki.synth.base import DummySynthesizer
    from llmwiki.synth.pipeline import synthesize_new_sessions
    raw, wiki_sources = _seed_raw_pair(tmp_path)
    state = tmp_path / "state.json"
    summary = synthesize_new_sessions(
        backend=DummySynthesizer(), raw_dir=raw, wiki_sources_dir=wiki_sources,
        state_file=state, include_docs=False, include_subagents="only-raw",
    )
    written = _synth_written(wiki_sources)
    assert summary["synthesized"] == 1
    assert all("subagent" not in n for n in written)


def test_synthesize_only_raw_skips_subagent_even_with_force(tmp_path: Path):
    # --force means "redo synthesis", not "override the include_subagents
    # policy" — subagents stay out until the user switches to "all".
    from llmwiki.synth.base import DummySynthesizer
    from llmwiki.synth.pipeline import synthesize_new_sessions
    raw, wiki_sources = _seed_raw_pair(tmp_path)
    state = tmp_path / "state.json"
    summary = synthesize_new_sessions(
        backend=DummySynthesizer(), raw_dir=raw, wiki_sources_dir=wiki_sources,
        state_file=state, include_docs=False, force=True,
        include_subagents="only-raw",
    )
    written = _synth_written(wiki_sources)
    assert all("subagent" not in n for n in written)
    assert summary["synthesized"] == 1


def test_synthesize_all_includes_subagent(tmp_path: Path):
    from llmwiki.synth.base import DummySynthesizer
    from llmwiki.synth.pipeline import synthesize_new_sessions
    raw, wiki_sources = _seed_raw_pair(tmp_path)
    state = tmp_path / "state.json"
    summary = synthesize_new_sessions(
        backend=DummySynthesizer(), raw_dir=raw, wiki_sources_dir=wiki_sources,
        state_file=state, include_docs=False, include_subagents="all",
    )
    assert summary["synthesized"] == 2


# ─── unsynth_total backlog (queue status) honors the mode ────────────────
#
# The CHANGELOG promises `queue status`'s unsynth_total (sourced from
# refresh_synth_pending -> synth.pending_total) doesn't count skipped subagents
# as permanently-pending. Exercise that persisted count directly.


def test_refresh_pending_only_raw_excludes_subagent(tmp_path: Path):
    from llmwiki.synth.pipeline import refresh_synth_pending
    raw, wiki_sources = _seed_raw_pair(tmp_path)
    state = tmp_path / "state.json"
    result = refresh_synth_pending(
        raw_dir=raw, docs_dir=tmp_path / "raw" / "docs",
        wiki_sources_dir=wiki_sources, state_file=state,
        include_subagents="only-raw",
    )
    assert result["pending_total"] == 1
    rels = [it["rel"] for it in result["pending"]]
    assert all("subagent" not in r for r in rels)
    # And it is persisted to state so `queue status` reads the same number.
    persisted = json.loads(state.read_text())["synth"]
    assert persisted["pending_total"] == 1


def test_refresh_pending_all_counts_subagent(tmp_path: Path):
    from llmwiki.synth.pipeline import refresh_synth_pending
    raw, wiki_sources = _seed_raw_pair(tmp_path)
    state = tmp_path / "state.json"
    result = refresh_synth_pending(
        raw_dir=raw, docs_dir=tmp_path / "raw" / "docs",
        wiki_sources_dir=wiki_sources, state_file=state,
        include_subagents="all",
    )
    assert result["pending_total"] == 2
