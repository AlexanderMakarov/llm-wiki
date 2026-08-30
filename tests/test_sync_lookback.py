"""Unit tests for durable sync lookback resolution (#192 / Slice 1–3).

# @layer: unit
# @spec: 177-sync-lookback
# @regression
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from llmwiki import REPO_ROOT
from llmwiki import convert as convert_mod
from llmwiki.adapters.base import BaseAdapter, SessionRef, lookback_cutoff_ts
from llmwiki.adapters.contrib.cursor_ide import CursorAdapter
from llmwiki.state_store import default_state, mtime_to_iso, read_state, write_state
from llmwiki.sync.lookback import (
    gc_sync_files_for_lookback,
    parse_since_date,
    resolve_effective_since,
)
from tests.changelog_notes import shipping_section_text
from tests.fixtures_cursor_ide import make_cursor_ide_db


def _dt(day: str) -> datetime:
    return datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=UTC)


def test_parse_since_date_valid():
    assert parse_since_date("2026-07-31") == _dt("2026-07-31")


def test_parse_since_date_invalid_raises():
    with pytest.raises(ValueError, match=r"--since must be YYYY-MM-DD"):
        parse_since_date("not-a-date")


@pytest.mark.parametrize(
    ("cli", "config", "adapter", "expected"),
    [
        pytest.param(
            "2026-08-01",
            {
                "filters": {"since": "2026-01-01"},
                "adapters": {"claude_code": {"since": "2026-06-01"}},
            },
            "claude_code",
            _dt("2026-08-01"),
            id="cli_wins_over_adapter_and_filters",
        ),
        pytest.param(
            None,
            {
                "filters": {"since": "2026-01-01"},
                "adapters": {"claude_code": {"since": "2026-06-15"}},
            },
            "claude_code",
            _dt("2026-06-15"),
            id="adapter_date_overrides_filters",
        ),
        pytest.param(
            None,
            {
                "filters": {"since": "2026-01-01"},
                "adapters": {"openclaw": {"since": "all"}},
            },
            "openclaw",
            None,
            id="adapter_all_means_no_gate",
        ),
        pytest.param(
            None,
            {
                "filters": {"since": "2026-03-01"},
                "adapters": {"claude_code": {"since": ""}},
            },
            "claude_code",
            _dt("2026-03-01"),
            id="empty_adapter_inherits_filters",
        ),
        pytest.param(
            None,
            {
                "filters": {"since": "2026-03-01"},
                "adapters": {"claude_code": {"enabled": True}},
            },
            "claude_code",
            _dt("2026-03-01"),
            id="absent_adapter_key_inherits_filters",
        ),
        pytest.param(
            None,
            {"filters": {"since": "2026-04-01"}},
            "claude_code",
            _dt("2026-04-01"),
            id="no_adapters_section_inherits_filters",
        ),
        pytest.param(
            None,
            {"adapters": {"claude_code": {"since": "2026-05-01"}}},
            "claude_code",
            _dt("2026-05-01"),
            id="adapter_only_no_shared",
        ),
        pytest.param(
            None,
            {},
            "claude_code",
            None,
            id="absent_config_unlimited",
        ),
        pytest.param(
            None,
            {"filters": {}},
            "claude_code",
            None,
            id="absent_filters_since_unlimited",
        ),
        pytest.param(
            None,
            {"filters": {"since": ""}},
            "claude_code",
            None,
            id="empty_filters_since_unlimited",
        ),
        pytest.param(
            None,
            {
                "filters": {"since": "2026-01-01"},
                "adapters": {
                    "claude_code": {"since": "all"},
                    "openclaw": {"since": "2026-07-01"},
                },
            },
            "openclaw",
            _dt("2026-07-01"),
            id="sibling_all_does_not_affect_other_adapter",
        ),
        pytest.param(
            "2026-08-15",
            {
                "filters": {"since": "2026-01-01"},
                "adapters": {"openclaw": {"since": "all"}},
            },
            "openclaw",
            _dt("2026-08-15"),
            id="cli_overrides_adapter_all",
        ),
        pytest.param(
            "",
            {"filters": {"since": "2026-02-01"}},
            "claude_code",
            _dt("2026-02-01"),
            id="empty_cli_falls_through_to_filters",
        ),
        pytest.param(
            None,
            {
                "filters": {"since": "2026-01-01"},
                "claude_code": {"since": "2026-09-01"},
            },
            "claude_code",
            _dt("2026-09-01"),
            id="legacy_top_level_adapter_block",
        ),
    ],
)
def test_resolve_effective_since_precedence(cli, config, adapter, expected):
    assert resolve_effective_since(cli, config, adapter) == expected


@pytest.mark.parametrize(
    ("cli", "config", "adapter"),
    [
        pytest.param("bad-date", {}, "claude_code", id="invalid_cli"),
        pytest.param(
            None,
            {"filters": {"since": "yesterday"}},
            "claude_code",
            id="invalid_filters_since",
        ),
        pytest.param(
            None,
            {"adapters": {"claude_code": {"since": "2026-13-40"}}},
            "claude_code",
            id="invalid_adapter_since",
        ),
        pytest.param(
            None,
            {"filters": {"since": "all"}},
            "claude_code",
            id="all_only_valid_on_adapter",
        ),
    ],
)
def test_resolve_effective_since_invalid_raises(cli, config, adapter):
    with pytest.raises(ValueError, match=r"--since must be YYYY-MM-DD"):
        resolve_effective_since(cli, config, adapter)


def test_convert_all_uses_per_adapter_resolution(tmp_path, monkeypatch, capsys):
    """Invalid shared lookback must fail the sync run with exit 2."""

    class _FakeAdapter:
        name = "claude_code"

        def __init__(self, config):
            self.config = config

        def discover_session_refs(self):
            return []

    cfg_path = tmp_path / "sessions_config.json"
    cfg_path.write_text(
        '{"filters": {"since": "not-a-day"}, "adapters": {}}',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        convert_mod,
        "select_sync_adapters",
        lambda config, explicit: [_FakeAdapter],
    )
    rc = convert_mod.convert_all(
        adapters=["claude_code"],
        out_dir=tmp_path / "raw" / "sessions",
        state_file=tmp_path / "llmwiki-state.json",
        config_file=cfg_path,
        dry_run=True,
    )
    assert rc == 2
    err = capsys.readouterr().err
    assert "--since must be YYYY-MM-DD" in err
    assert "not-a-day" in err


def _user_assistant(
    *,
    session_id: str,
    day: str,
    text: str = "hello",
) -> list[dict]:
    """Minimal Claude-style records with timestamps on ``day``."""
    return [
        {
            "type": "user",
            "timestamp": f"{day}T12:00:00.000Z",
            "sessionId": session_id,
            "cwd": "/tmp/proj",
            "message": {"role": "user", "content": text},
        },
        {
            "type": "assistant",
            "timestamp": f"{day}T12:00:01.000Z",
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "ok"}],
            },
        },
    ]


def test_early_mtime_prune_skips_load(tmp_path, monkeypatch, capsys):
    """Refs with mtime before lookback never reach load_records (#192 R4)."""
    loads: list[str] = []
    old_ts = _dt("2020-01-15").timestamp()
    new_ts = _dt("2026-08-15").timestamp()
    old_loc = str(tmp_path / "old.jsonl")
    new_loc = str(tmp_path / "new.jsonl")

    class _FakeAdapter:
        name = "claude_code"

        def __init__(self, config):
            self.config = config

        def discover_session_refs(self, since_dt=None):
            # Return both; convert_all must still mtime-prune before load.
            del since_dt
            return [
                SessionRef(key="old.jsonl", mtime=old_ts, locator=old_loc),
                SessionRef(key="new.jsonl", mtime=new_ts, locator=new_loc),
            ]

        def derive_project_slug(self, path):
            return "proj"

        def load_records(self, path):
            loads.append(str(path))
            name = Path(path).name
            day = "2020-01-15" if name.startswith("old") else "2026-08-15"
            return _user_assistant(session_id=f"sess-{name}", day=day, text=name)

        def normalize_records(self, records):
            return records

        def is_headless_session(self, records):
            return False

        def is_subagent(self, path):
            return False

    cfg_path = tmp_path / "sessions_config.json"
    cfg_path.write_text(
        json.dumps({"filters": {"since": "2026-08-01", "exclude_headless": False}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        convert_mod,
        "select_sync_adapters",
        lambda config, explicit: [_FakeAdapter],
    )
    out = tmp_path / "raw" / "sessions"
    state = tmp_path / "llmwiki-state.json"
    rc = convert_mod.convert_all(
        adapters=["claude_code"],
        out_dir=out,
        state_file=state,
        config_file=cfg_path,
        include_current=True,
    )
    assert rc == 0
    assert loads == [new_loc]
    assert list(out.glob("*.md"))
    out_txt = capsys.readouterr().out
    assert "candidates: 1 (after lookback filter)" in out_txt
    assert "synced: 1" in out_txt
    # R4.4: mtime-pruned key must NOT appear in sync.files (lookback-only skip).
    files = read_state(state).get("sync", {}).get("files", {})
    assert "claude_code::old.jsonl" not in files, (
        "mtime-pruned session must not be stamped in sync.files (R4 AC4)"
    )


def test_post_load_since_gate_still_filters_without_state_write(
    tmp_path, monkeypatch, capsys
):
    """Recent mtime + old record activity → filtered; no sync.files stamp."""
    loads: list[str] = []
    # Fresh mtime passes early prune; content timestamps are before lookback.
    fresh_ts = _dt("2026-08-20").timestamp()
    loc = str(tmp_path / "stale-content.jsonl")

    class _FakeAdapter:
        name = "claude_code"

        def __init__(self, config):
            self.config = config

        def discover_session_refs(self, since_dt=None):
            del since_dt
            return [SessionRef(key="stale.jsonl", mtime=fresh_ts, locator=loc)]

        def derive_project_slug(self, path):
            return "proj"

        def load_records(self, path):
            loads.append(str(path))
            return _user_assistant(
                session_id="sess-stale",
                day="2025-01-01",
                text="old activity",
            )

        def normalize_records(self, records):
            return records

        def is_headless_session(self, records):
            return False

        def is_subagent(self, path):
            return False

    cfg_path = tmp_path / "sessions_config.json"
    cfg_path.write_text(
        json.dumps({"filters": {"since": "2026-08-01", "exclude_headless": False}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        convert_mod,
        "select_sync_adapters",
        lambda config, explicit: [_FakeAdapter],
    )
    out = tmp_path / "raw" / "sessions"
    state = tmp_path / "llmwiki-state.json"
    rc = convert_mod.convert_all(
        adapters=["claude_code"],
        out_dir=out,
        state_file=state,
        config_file=cfg_path,
        include_current=True,
    )
    assert rc == 0
    assert loads == [loc]
    assert list(out.glob("*.md")) == []
    files = read_state(state).get("sync", {}).get("files", {})
    assert "claude_code::stale.jsonl" not in files
    out_txt = capsys.readouterr().out
    assert "candidates: 1 (after lookback filter)" in out_txt
    assert "synced: 0" in out_txt
    assert "filters.since" in out_txt
    assert "adapters.<name>.since" in out_txt
    assert "configure-sources" in out_txt


def test_lookback_hint_printed_when_unlimited(tmp_path, monkeypatch, capsys):
    """R5: hint even when no lookback is configured."""

    class _FakeAdapter:
        name = "claude_code"

        def __init__(self, config):
            self.config = config

        def discover_session_refs(self, since_dt=None):
            del since_dt
            return []

    cfg_path = tmp_path / "sessions_config.json"
    cfg_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        convert_mod,
        "select_sync_adapters",
        lambda config, explicit: [_FakeAdapter],
    )
    rc = convert_mod.convert_all(
        adapters=["claude_code"],
        out_dir=tmp_path / "raw" / "sessions",
        state_file=tmp_path / "llmwiki-state.json",
        config_file=cfg_path,
        dry_run=True,
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "candidates: 0 (after lookback filter)" in out
    assert "synced: 0" in out
    assert "filters.since" in out
    assert "configure-sources" in out


def test_cursor_discover_filters_old_headers_when_since_dt(tmp_path: Path):
    """Cursor IDE: since_dt drops old composers before they become refs."""
    old_cid = "11111111-1111-1111-1111-111111111111"
    new_cid = "22222222-2222-2222-2222-222222222222"
    b_old = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    b_new = "cccccccc-cccc-cccc-cccc-cccccccccccc"
    db = make_cursor_ide_db(
        tmp_path / "state.vscdb",
        composers=[
            {
                "composer_id": old_cid,
                "created_at": 1_600_000_000_000,  # ~2020-09
                "last_updated_at": 1_600_000_000_000,
                "bubbles": [{"bubble_id": b_old, "type": 1, "text": "old"}],
            },
            {
                "composer_id": new_cid,
                "created_at": 1_755_000_000_000,  # ~2025-08
                "last_updated_at": 1_755_000_000_000,
                "bubbles": [{"bubble_id": b_new, "type": 1, "text": "new"}],
            },
        ],
    )
    ad = CursorAdapter(config={"adapters": {"cursor_ide": {"global_db": str(db)}}})
    all_refs = ad.discover_session_refs()
    assert {r.key for r in all_refs} == {
        f"composer/{old_cid}",
        f"composer/{new_cid}",
    }
    filtered = ad.discover_session_refs(since_dt=_dt("2025-01-01"))
    assert [r.key for r in filtered] == [f"composer/{new_cid}"]


def test_gc_sync_files_for_lookback_unit():
    """Old adapter keys drop; in-window, siblings, and junk stay."""
    since = _dt("2026-08-01")
    old_ts = _dt("2020-01-15").timestamp()
    in_ts = _dt("2026-08-15").timestamp()
    files = {
        "claude_code::old.jsonl": mtime_to_iso(old_ts),
        "claude_code::recent.jsonl": in_ts,  # in-memory float, same as convert
        "claude_code::boundary.jsonl": since.timestamp(),
        "claude_code::junk.jsonl": "not-an-mtime",
        "openclaw::old.jsonl": mtime_to_iso(old_ts),
        "claude_code_extra::old.jsonl": mtime_to_iso(old_ts),
    }
    removed = gc_sync_files_for_lookback(files, "claude_code", since)
    assert removed == 1
    assert "claude_code::old.jsonl" not in files
    assert "claude_code::recent.jsonl" in files
    assert "claude_code::boundary.jsonl" in files
    assert files["claude_code::junk.jsonl"] == "not-an-mtime"
    assert "openclaw::old.jsonl" in files
    assert "claude_code_extra::old.jsonl" in files


class _EmptyAdapter:
    """Discover-nothing adapter used to exercise post-loop GC."""

    def __init__(self, config):
        self.config = config

    def discover_session_refs(self, since_dt=None):
        del since_dt
        return []


class _ClaudeEmpty(_EmptyAdapter):
    name = "claude_code"


class _OpenclawEmpty(_EmptyAdapter):
    name = "openclaw"


def _seed_lookback_gc_state(state_file: Path) -> None:
    """Write a unified state file with old + in-window stamps and sentinels."""
    old_ts = _dt("2020-01-15").timestamp()
    in_ts = _dt("2026-08-15").timestamp()
    payload = default_state()
    payload["sync"]["files"] = {
        "claude_code::old.jsonl": mtime_to_iso(old_ts),
        "claude_code::recent.jsonl": mtime_to_iso(in_ts),
        "openclaw::old.jsonl": mtime_to_iso(old_ts),
        "codex_cli::ancient.jsonl": mtime_to_iso(old_ts),
    }
    payload["queue"]["items"] = [{"id": "keep-queue", "status": "pending"}]
    payload["synth"]["files"] = {"sources/keep.md": mtime_to_iso(old_ts)}
    payload["quarantine"]["entries"] = [{"path": "keep.jsonl", "reason": "x"}]
    payload["ops"]["last_queue_run_at"] = "2026-01-01T00:00:00Z"
    write_state(payload, state_file)


def test_convert_all_gcs_old_sync_files_keeps_in_window_and_other_adapters(
    tmp_path, monkeypatch
):
    """After a successful sync: old lookback keys gone; no-lookback adapter untouched."""
    state = tmp_path / "llmwiki-state.json"
    _seed_lookback_gc_state(state)
    cfg_path = tmp_path / "sessions_config.json"
    cfg_path.write_text(
        json.dumps(
            {
                "filters": {"since": "2026-08-01", "exclude_headless": False},
                "adapters": {"openclaw": {"since": "all"}},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        convert_mod,
        "select_sync_adapters",
        lambda config, explicit: [_ClaudeEmpty, _OpenclawEmpty],
    )
    rc = convert_mod.convert_all(
        adapters=["claude_code", "openclaw"],
        out_dir=tmp_path / "raw" / "sessions",
        state_file=state,
        config_file=cfg_path,
        include_current=True,
    )
    assert rc == 0
    got = read_state(state)
    files = got["sync"]["files"]
    assert "claude_code::old.jsonl" not in files
    assert "claude_code::recent.jsonl" in files
    assert "openclaw::old.jsonl" in files
    assert "codex_cli::ancient.jsonl" in files
    assert got["queue"]["items"][0]["id"] == "keep-queue"
    assert "sources/keep.md" in got["synth"]["files"]
    assert got["quarantine"]["entries"][0]["path"] == "keep.jsonl"
    assert got["ops"]["last_queue_run_at"] == "2026-01-01T00:00:00Z"


def test_convert_all_dry_run_does_not_gc_sync_files(tmp_path, monkeypatch):
    """Dry-run must not persist lookback GC."""
    state = tmp_path / "llmwiki-state.json"
    _seed_lookback_gc_state(state)
    cfg_path = tmp_path / "sessions_config.json"
    cfg_path.write_text(
        json.dumps({"filters": {"since": "2026-08-01"}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        convert_mod,
        "select_sync_adapters",
        lambda config, explicit: [_ClaudeEmpty],
    )
    rc = convert_mod.convert_all(
        adapters=["claude_code"],
        out_dir=tmp_path / "raw" / "sessions",
        state_file=state,
        config_file=cfg_path,
        dry_run=True,
    )
    assert rc == 0
    files = read_state(state).get("sync", {}).get("files", {})
    assert "claude_code::old.jsonl" in files
    assert "claude_code::recent.jsonl" in files


# ─── Slice 4: estimate_sync_candidates ───────────────────────────────────


def test_default_estimate_sync_candidates_by_mtime(tmp_path: Path):
    """Default estimate: eligible = all refs; window by mtime (no headless peek)."""
    store = tmp_path / "store"
    store.mkdir()
    old = store / "old.jsonl"
    new = store / "new.jsonl"
    old.write_text("{}\n", encoding="utf-8")
    new.write_text("{}\n", encoding="utf-8")

    cutoff = lookback_cutoff_ts(days=30)
    old_mtime = cutoff - 86_400
    new_mtime = cutoff + 86_400

    class _Fake(BaseAdapter):
        name = "fake"
        session_store_path = store

        def discover_session_refs(self, since_dt=None):
            del since_dt
            return [
                SessionRef(key="old.jsonl", mtime=old_mtime, locator=str(old)),
                SessionRef(key="new.jsonl", mtime=new_mtime, locator=str(new)),
            ]

    est = _Fake().estimate_sync_candidates()
    assert est.eligible == 2
    assert est.in_last_30_days == 1
    assert est.earliest == datetime.fromtimestamp(old_mtime, tz=UTC)


def test_cursor_estimate_excludes_empty_and_subagent(tmp_path: Path):
    """Cursor override: headers only — drop empty + isSubagent; split by dates."""
    old_cid = "11111111-1111-1111-1111-111111111111"
    new_cid = "22222222-2222-2222-2222-222222222222"
    empty_cid = "33333333-3333-3333-3333-333333333333"
    sub_cid = "44444444-4444-4444-4444-444444444444"
    b_old = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    b_new = "cccccccc-cccc-cccc-cccc-cccccccccccc"
    b_sub = "dddddddd-dddd-dddd-dddd-dddddddddddd"

    cutoff = lookback_cutoff_ts(days=30)
    # ms timestamps relative to cutoff
    old_ms = int((cutoff - 86_400) * 1000)
    new_ms = int((cutoff + 86_400) * 1000)

    db = make_cursor_ide_db(
        tmp_path / "state.vscdb",
        composers=[
            {
                "composer_id": old_cid,
                "created_at": old_ms,
                "last_updated_at": old_ms,
                "bubbles": [{"bubble_id": b_old, "type": 1, "text": "old"}],
            },
            {
                "composer_id": new_cid,
                "created_at": new_ms,
                "last_updated_at": new_ms,
                "bubbles": [{"bubble_id": b_new, "type": 1, "text": "new"}],
            },
            {
                "composer_id": empty_cid,
                "created_at": new_ms,
                "last_updated_at": new_ms,
                "bubbles": [],
            },
            {
                "composer_id": sub_cid,
                "created_at": new_ms,
                "last_updated_at": new_ms,
                "is_subagent": True,
                "bubbles": [{"bubble_id": b_sub, "type": 1, "text": "agent"}],
            },
        ],
    )
    ad = CursorAdapter(config={"adapters": {"cursor_ide": {"global_db": str(db)}}})
    est = ad.estimate_sync_candidates()
    assert est.eligible == 2  # old + new; not empty, not subagent
    assert est.in_last_30_days == 1  # only new
    assert est.earliest is not None
    assert est.earliest == datetime.fromtimestamp(cutoff - 86_400, tz=UTC)


# ─── R3.2: invalid CLI --since → convert_all exit 2 ───────────────────────


def test_convert_all_invalid_cli_since_exits_2(tmp_path, monkeypatch, capsys):
    """R3 AC2: invalid one-run date exits 2 with a clear error (same style as bad config)."""

    class _FakeAdapter:
        name = "claude_code"

        def __init__(self, config):
            self.config = config

        def discover_session_refs(self, since_dt=None):
            del since_dt
            return []

    cfg_path = tmp_path / "sessions_config.json"
    cfg_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        convert_mod,
        "select_sync_adapters",
        lambda config, explicit: [_FakeAdapter],
    )
    rc = convert_mod.convert_all(
        adapters=["claude_code"],
        out_dir=tmp_path / "raw" / "sessions",
        state_file=tmp_path / "llmwiki-state.json",
        config_file=cfg_path,
        since="not-a-date",
        dry_run=True,
    )
    assert rc == 2
    err = capsys.readouterr().err
    assert "--since must be YYYY-MM-DD" in err
    assert "not-a-date" in err


def test_cli_since_does_not_gc_sync_files(tmp_path, monkeypatch):
    """CLI ``--since`` prunes this run but must not persist GC."""
    state = tmp_path / "llmwiki-state.json"
    _seed_lookback_gc_state(state)
    cfg_path = tmp_path / "sessions_config.json"
    cfg_path.write_text(json.dumps({"filters": {}}), encoding="utf-8")
    monkeypatch.setattr(
        convert_mod,
        "select_sync_adapters",
        lambda config, explicit: [_ClaudeEmpty],
    )
    rc = convert_mod.convert_all(
        adapters=["claude_code"],
        out_dir=tmp_path / "raw" / "sessions",
        state_file=state,
        config_file=cfg_path,
        ignore_file=tmp_path / "no-ignore",
        since="2026-08-01",
        include_current=True,
    )
    assert rc == 0
    files = read_state(state).get("sync", {}).get("files", {})
    assert "claude_code::old.jsonl" in files
    assert "claude_code::recent.jsonl" in files


def test_notes_adapter_stamps_survive_lookback_gc(tmp_path, monkeypatch):
    """Obsidian-style .md sources are not GC'd (B2)."""
    note_dir = tmp_path / "vault"
    note_dir.mkdir()
    note = note_dir / "old-note.md"
    note.write_text("# Note\n\n" + ("body " * 20), encoding="utf-8")
    mtime = _dt("2026-08-20").timestamp()

    class _Notes(BaseAdapter):
        name = "obsidian"
        is_ai_session = False
        session_store_path = note_dir

        def discover_session_refs(self, since_dt=None):
            del since_dt
            return [SessionRef(key="old-note.md", mtime=mtime, locator=str(note))]

    monkeypatch.setattr(
        convert_mod,
        "select_sync_adapters",
        lambda config, explicit: [_Notes],
    )
    state = tmp_path / "llmwiki-state.json"
    out = tmp_path / "raw" / "sessions"
    ignore = tmp_path / "no-ignore"
    cfg = tmp_path / "cfg.json"
    cfg.write_text(
        json.dumps({"filters": {"since": "2026-08-01", "exclude_headless": False}}),
        encoding="utf-8",
    )
    rc = convert_mod.convert_all(
        adapters=["obsidian"],
        out_dir=out,
        state_file=state,
        config_file=cfg,
        ignore_file=ignore,
        include_current=True,
    )
    assert rc == 0
    assert "obsidian::old-note.md" in read_state(state)["sync"]["files"]

    cfg.write_text(
        json.dumps({"filters": {"since": "2026-08-25", "exclude_headless": False}}),
        encoding="utf-8",
    )
    rc = convert_mod.convert_all(
        adapters=["obsidian"],
        out_dir=out,
        state_file=state,
        config_file=cfg,
        ignore_file=ignore,
        include_current=True,
    )
    assert rc == 0
    assert "obsidian::old-note.md" in read_state(state)["sync"]["files"]


def test_md_resync_after_stamp_loss_is_not_an_error(tmp_path, monkeypatch):
    """Widening after a lost stamp overwrites our own notes copy (B2 owned=)."""
    note_dir = tmp_path / "vault"
    note_dir.mkdir()
    note = note_dir / "old-note.md"
    note.write_text("# Note\n\n" + ("body " * 20), encoding="utf-8")
    mtime = _dt("2026-08-20").timestamp()

    class _Notes(BaseAdapter):
        name = "obsidian"
        is_ai_session = False
        session_store_path = note_dir

        def discover_session_refs(self, since_dt=None):
            del since_dt
            return [SessionRef(key="old-note.md", mtime=mtime, locator=str(note))]

    monkeypatch.setattr(
        convert_mod,
        "select_sync_adapters",
        lambda config, explicit: [_Notes],
    )
    state = tmp_path / "llmwiki-state.json"
    out = tmp_path / "raw" / "sessions"
    ignore = tmp_path / "no-ignore"
    cfg = tmp_path / "cfg.json"
    cfg.write_text(
        json.dumps({"filters": {"since": "2026-08-01", "exclude_headless": False}}),
        encoding="utf-8",
    )
    assert convert_mod.convert_all(
        adapters=["obsidian"],
        out_dir=out,
        state_file=state,
        config_file=cfg,
        ignore_file=ignore,
        include_current=True,
    ) == 0
    payload = read_state(state)
    payload["sync"]["files"].pop("obsidian::old-note.md", None)
    write_state(payload, state)
    rc = convert_mod.convert_all(
        adapters=["obsidian"],
        out_dir=out,
        state_file=state,
        config_file=cfg,
        ignore_file=ignore,
        include_current=True,
        fail_on_errors=True,
    )
    assert rc == 0
    assert "obsidian::old-note.md" in read_state(state)["sync"]["files"]


# ─── R8: docs keys exist in configuration-reference.md ─────────────────────

_CONFIG_REF = REPO_ROOT / "docs" / "configuration-reference.md"
_CHANGELOG = REPO_ROOT / "CHANGELOG.md"
_UPGRADING = REPO_ROOT / "docs" / "UPGRADING.md"


def test_config_reference_documents_filters_since():
    """R8 AC1: configuration-reference.md declares filters.since key."""
    text = _CONFIG_REF.read_text(encoding="utf-8")
    assert "`filters.since`" in text or "filters.since" in text


def test_config_reference_documents_per_adapter_since():
    """R8 AC1: configuration-reference.md declares adapters.<name>.since."""
    text = _CONFIG_REF.read_text(encoding="utf-8")
    assert "`adapters.<name>.since`" in text


def test_config_reference_documents_all_value():
    """R8 AC1: 'all' is documented as the no-date-gate per-adapter value."""
    text = _CONFIG_REF.read_text(encoding="utf-8")
    assert '"all"' in text or "`all`" in text, (
        "configuration-reference.md must document 'all' as the no-gate per-adapter value"
    )


def test_config_reference_documents_gc_and_no_state_on_skip():
    """R8 AC3: docs state lookback-skipped sessions are not remembered and GC is noted."""
    text = _CONFIG_REF.read_text(encoding="utf-8")
    assert "sync.files" in text, (
        "configuration-reference.md must mention sync.files in lookback GC context"
    )
    lower = text.lower()
    assert "not" in lower and ("stamp" in lower or "written" in lower or "remember" in lower), (
        "configuration-reference.md must state lookback-only skips are not written to sync.files"
    )


def test_changelog_unreleased_mentions_lookback():
    """R8 AC2: CHANGELOG [Unreleased] (or latest section) records the lookback feature."""
    text = shipping_section_text(_CHANGELOG.read_text(encoding="utf-8"))
    lower = text.lower()
    assert "lookback" in lower or "filters.since" in lower or "#192" in lower, (
        "CHANGELOG must mention durable sync lookback (#192)"
    )


def test_upgrading_md_has_lookback_note():
    """R8 AC2: UPGRADING.md explains lookback GC and that skips are not remembered."""
    text = _UPGRADING.read_text(encoding="utf-8")
    lower = text.lower()
    assert "filters.since" in lower or "lookback" in lower, (
        "UPGRADING.md must document the durable sync lookback feature"
    )
    assert "sync.files" in lower or "not remembered" in lower or "never" in lower, (
        "UPGRADING.md must note that lookback-only skips are not remembered"
    )
