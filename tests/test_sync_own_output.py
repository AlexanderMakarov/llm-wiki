"""Sync must recognize its own prior outputs (ownership by sessionId).

The #339 disambiguation pass used ``state.get(key) != mtime`` as a proxy
for "the existing canonical file was written by someone else". That
proxy misfires whenever the state file is stale or missing: a resumed
session (same source, new mtime) and a lost/reset state file both look
like foreign collisions. Sync then duplicates the session into a
``--<hash>`` (double-slug) sibling — and once both names exist, the
#326 write guard rejects every later re-conversion of that source, so
it stays quarantined forever.

Ownership is now decided by comparing frontmatter ``sessionId`` values:
same id → the existing file is this source's own prior output and gets
updated in place; different id → the conservative collision path runs
exactly as before.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from llmwiki import convert as c
from llmwiki import quarantine
from llmwiki.adapters.claude_code import ClaudeCodeAdapter



def _write_jsonl(path: Path, session_id: str, iso_ts: str,
                 slug: str = "own-slug", extra_turns: int = 0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        json.dumps({
            "type": "user",
            "sessionId": session_id,
            "slug": slug,
            "timestamp": iso_ts,
            "cwd": "/home/user/my-proj",
            "gitBranch": "main",
            "message": {"role": "user", "content": "hi"},
        }),
        json.dumps({
            "type": "assistant",
            "sessionId": session_id,
            "timestamp": iso_ts,
            "message": {"role": "assistant", "content": "hello"},
        }),
    ]
    for i in range(extra_turns):
        rows.append(json.dumps({
            "type": "user",
            "sessionId": session_id,
            "timestamp": iso_ts,
            "cwd": "/home/user/my-proj",
            "message": {"role": "user", "content": f"more {i}"},
        }))
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Fake home + adapter store + isolated state/quarantine files."""
    home = tmp_path / "home"
    home.mkdir()
    store = home / ".claude" / "projects"
    proj = store / "my-proj"
    out_dir = tmp_path / "repo" / "raw" / "sessions"
    state = tmp_path / "state.json"

    monkeypatch.setattr(
        ClaudeCodeAdapter, "session_store_path", store, raising=False,
    )
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setattr(c, "REPO_ROOT", home.parent / "repo")
    c.discover_adapters()
    return {"proj": proj, "out_dir": out_dir, "state": state}


def _sync(env, **kw) -> int:
    return c.convert_all(
        adapters=["claude_code"],
        out_dir=env["out_dir"],
        state_file=env["state"],
        include_current=True,
        **kw,
    )


def _bump_mtime(path: Path) -> None:
    st = path.stat()
    os.utime(path, (st.st_atime, st.st_mtime + 60))


def test_changed_source_updates_canonical_in_place(env):
    src = env["proj"] / "s.jsonl"
    _write_jsonl(src, "sess-own-1", "2026-04-16T10:00:00Z")
    assert _sync(env) == 0
    outs = sorted(env["out_dir"].rglob("*.md"))
    assert len(outs) == 1 and "--" not in outs[0].name

    # Resume the session: content grows, mtime changes.
    _write_jsonl(src, "sess-own-1", "2026-04-16T10:00:00Z", extra_turns=3)
    _bump_mtime(src)
    assert _sync(env) == 0

    outs = sorted(env["out_dir"].rglob("*.md"))
    assert len(outs) == 1, f"duplicate created: {[p.name for p in outs]}"
    assert "more 2" in outs[0].read_text(encoding="utf-8")


def test_state_loss_does_not_duplicate_corpus(env):
    src = env["proj"] / "s.jsonl"
    _write_jsonl(src, "sess-own-2", "2026-04-16T10:00:00Z")
    assert _sync(env) == 0
    env["state"].unlink()  # simulate a lost/reset state file
    assert _sync(env) == 0
    outs = sorted(env["out_dir"].rglob("*.md"))
    assert len(outs) == 1, (
        f"state loss duplicated the corpus: {[p.name for p in outs]}"
    )


def test_foreign_canonical_still_disambiguates(env):
    """A canonical file from a DIFFERENT session must not be touched."""
    a, b = env["proj"] / "a.jsonl", env["proj"] / "b.jsonl"
    _write_jsonl(a, "sess-a", "2026-04-16T10:00:00Z", slug="clash")
    assert _sync(env) == 0
    canonical = next(env["out_dir"].rglob("*.md"))
    before = canonical.read_text(encoding="utf-8")

    _write_jsonl(b, "sess-b", "2026-04-16T10:00:00Z", slug="clash")
    assert _sync(env) == 0

    outs = sorted(env["out_dir"].rglob("*.md"))
    assert len(outs) == 2, [p.name for p in outs]
    assert canonical.read_text(encoding="utf-8") == before
    assert any("--" in p.name for p in outs)


def test_stuck_disambiguated_output_converges(env):
    """The stuck-forever loop: the canonical name is held by a different
    session, our own ``--<hash>`` output exists from a prior run, and
    the source changes again. Before the fix this errored on every
    sync; now the hashed file is updated in place and any stale
    quarantine entry clears."""
    a, b = env["proj"] / "a.jsonl", env["proj"] / "b.jsonl"
    _write_jsonl(a, "sess-a", "2026-04-16T10:00:00Z", slug="clash")
    _write_jsonl(b, "sess-b", "2026-04-16T10:00:00Z", slug="clash")
    assert _sync(env) == 0
    assert len(list(env["out_dir"].rglob("*.md"))) == 2

    # b's source changes again — its output is the disambiguated file.
    quarantine.add_entry("claude_code", str(b), "stale entry from old bug")
    _write_jsonl(b, "sess-b", "2026-04-16T10:00:00Z", slug="clash",
                 extra_turns=2)
    _bump_mtime(b)
    assert _sync(env) == 0

    outs = sorted(env["out_dir"].rglob("*.md"))
    assert len(outs) == 2, f"grew the tree: {[p.name for p in outs]}"
    hashed = next(p for p in outs if "--" in p.name)
    assert "more 1" in hashed.read_text(encoding="utf-8")
    assert quarantine.load() == [], "stale quarantine entry not cleared"


def test_true_collision_errors_but_exit_zero_by_default(env):
    """A genuinely foreign file at the disambiguated path still errors —
    but per-file errors no longer fail the whole run unless asked."""
    src = env["proj"] / "s.jsonl"
    _write_jsonl(src, "sess-own-3", "2026-04-16T10:00:00Z", slug="clash")

    # Foreign files (different sessionId) squat on BOTH names.
    env["out_dir"].mkdir(parents=True)
    foreign = "---\nsessionId: someone-else\n---\nbody\n"
    canonical = "2026-04-16T10-00-my-proj-clash.md"
    hashed = f"2026-04-16T10-00-my-proj-clash--{c._source_hash8(src)}.md"
    (env["out_dir"] / canonical).write_text(foreign, encoding="utf-8")
    (env["out_dir"] / hashed).write_text(foreign, encoding="utf-8")

    assert _sync(env) == 0
    assert len(quarantine.load()) == 1

    assert _sync(env, force=False, fail_on_errors=True) == 1
