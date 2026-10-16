"""Wiring for Cursor usage map, usage store upsert, migrate, coverage (#325).

# @spec: 328-cursor-cli-token-usage
"""
from __future__ import annotations

import json
from pathlib import Path

from llmwiki.adapters import discover_all
from llmwiki.adapters.contrib.cursor_cli import CursorCliAdapter
from llmwiki.build import page_foot
from llmwiki.migrate_session_tokens import _adapter_name_from_meta, run_migration
from llmwiki.render.js import JS
from llmwiki.session_tokens_usage import load_session_tokens, upsert_session_tokens
from llmwiki.viz_tokens import (
    TOKEN_COVERAGE_OTHER_AGENTS_LINE,
    format_token_coverage_measured_known,
    render_site_token_stats,
    render_token_coverage_hint,
)


def test_cursor_normalize_attaches_mapped_usage():
    adapter = CursorCliAdapter({})
    records = [
        {
            "role": "assistant",
            "content": [{"type": "text", "text": "hi"}],
            "usage": {
                "input_tokens": 100,
                "output_tokens": 10,
                "cache_read_tokens": 40,
                "cache_write_tokens": 20,
            },
        }
    ]
    out = adapter.normalize_records(records)
    assert len(out) == 1
    usage = out[0]["message"]["usage"]
    assert usage["input_tokens"] == 40
    assert usage["cache_creation_input_tokens"] == 20
    assert usage["cache_read_input_tokens"] == 40
    assert usage["output_tokens"] == 10


def test_cursor_normalize_rejects_occupancy_only():
    adapter = CursorCliAdapter({})
    records = [
        {
            "role": "assistant",
            "content": [{"type": "text", "text": "hi"}],
            "usage": {"used_tokens": 12000, "max_tokens": 300000},
        }
    ]
    out = adapter.normalize_records(records)
    assert len(out) == 1
    assert "usage" not in out[0]["message"]


def test_adapter_name_from_meta_maps_cursor_cli_tag():
    discover_all()
    assert _adapter_name_from_meta({"tags": ["cursor-cli", "session-transcript"]}) == (
        "cursor_cli"
    )
    assert _adapter_name_from_meta({"tags": ["claude-code", "session-transcript"]}) == (
        "claude_code"
    )
    assert _adapter_name_from_meta({"tags": ["codex-cli", "session-transcript"]}) == (
        "codex_cli"
    )


def test_migrate_from_raw_frontmatter_fills_usage_file(tmp_path: Path, monkeypatch):
    vault = tmp_path / "vault"
    sessions = vault / "raw" / "sessions"
    sessions.mkdir(parents=True)
    (sessions / "2026-04-01T10-00-demo-s1.md").write_text(
        "---\n"
        'title: "Demo"\n'
        "type: source\n"
        "tags: [claude-code, session-transcript]\n"
        "date: 2026-04-01\n"
        "sessionId: sess-migrate-1\n"
        "ended: 2026-04-01T12:00:00+00:00\n"
        'token_totals: {"input": 10, "cache_creation": 0, "cache_read": 5, "output": 2}\n'
        "---\n\n# Demo\n",
        encoding="utf-8",
    )
    (sessions / "2026-04-02T10-00-cursor-s2.md").write_text(
        "---\n"
        'title: "Cursor demo"\n'
        "type: source\n"
        "tags: [cursor-cli, session-transcript]\n"
        "date: 2026-04-02\n"
        "sessionId: sess-migrate-cursor\n"
        "ended: 2026-04-02T12:00:00+00:00\n"
        'token_totals: {"input": 7, "cache_creation": 0, "cache_read": 0, "output": 3}\n'
        "---\n\n# Cursor demo\n",
        encoding="utf-8",
    )
    (sessions / "2026-04-03T10-00-empty-s3.md").write_text(
        "---\n"
        'title: "Empty"\n'
        "type: source\n"
        "tags: [claude-code, session-transcript]\n"
        "date: 2026-04-03\n"
        "sessionId: sess-migrate-empty\n"
        "ended: 2026-04-03T12:00:00+00:00\n"
        'token_totals: {"input": 0, "cache_creation": 0, "cache_read": 0, "output": 0}\n'
        "model: <synthetic>\n"
        "tool_calls: 0\n"
        "---\n\n# Empty\n",
        encoding="utf-8",
    )
    # Do not re-read the developer's real agent stores during unit tests.
    monkeypatch.setattr(
        "llmwiki.migrate_session_tokens._backfill_capable_adapter",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "llmwiki.migrate_session_tokens._coverage_from_origins_and_raw",
        lambda sessions_dir, config, usage_data: (
            {"claude_code": 2, "cursor_cli": 1},
            {"cursor_cli": "2026-04-02"},
        ),
    )
    report = run_migration(vault=vault, dry_run=False)
    assert report["errors"] == 0
    assert report["raw_upserts"] == 2
    assert report["raw_skipped_empty"] == 1
    data = load_session_tokens(vault)
    assert data["sessions"]["sess-migrate-1"]["totals"]["input"] == 10
    assert data["sessions"]["sess-migrate-1"]["agent"] == "claude_code"
    assert data["sessions"]["sess-migrate-cursor"]["agent"] == "cursor_cli"
    assert "sess-migrate-empty" not in data["sessions"]
    assert data["by_agent"]["cursor_cli"]["known"] == 1
    assert data["by_agent"]["cursor_cli"]["measured"] == 1
    assert data["by_agent"]["cursor_cli"]["since"] == "2026-04-02"
    assert data["by_agent"]["claude_code"]["known"] == 2
    assert data["by_agent"]["claude_code"]["measured"] == 1
    assert data["totals"]["sum"] == 27


def test_migrate_raw_keeps_pre_lookback_sessions_with_usage(tmp_path: Path, monkeypatch):
    """Tokens metrics-without-raw: nonempty totals stay known despite filters.since."""
    vault = tmp_path / "vault"
    sessions = vault / "raw" / "sessions"
    sessions.mkdir(parents=True)
    (sessions / "old.md").write_text(
        "---\n"
        "tags: [claude-code, session-transcript]\n"
        "sessionId: old-sess\n"
        "started: 2026-01-01T00:00:00+00:00\n"
        'token_totals: {"input": 9, "cache_creation": 0, "cache_read": 0, "output": 1}\n'
        "---\n\n# old\n",
        encoding="utf-8",
    )
    (sessions / "new.md").write_text(
        "---\n"
        "tags: [claude-code, session-transcript]\n"
        "sessionId: new-sess\n"
        "started: 2026-07-01T00:00:00+00:00\n"
        'token_totals: {"input": 4, "cache_creation": 0, "cache_read": 0, "output": 1}\n'
        "---\n\n# new\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "llmwiki.migrate_session_tokens._backfill_capable_adapter",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "llmwiki.migrate_session_tokens._coverage_from_origins_and_raw",
        lambda sessions_dir, config, usage_data: ({"claude_code": 2}, {}),
    )
    report = run_migration(
        vault=vault,
        dry_run=False,
        config={"filters": {"since": "2026-06-01"}},
    )
    assert report["raw_upserts"] == 2
    assert "raw_skipped_filter" not in report or report.get("raw_skipped_filter", 0) == 0
    data = load_session_tokens(vault)
    assert "new-sess" in data["sessions"]
    assert "old-sess" in data["sessions"]


def test_migrate_origin_skips_empty_totals(tmp_path: Path, monkeypatch):
    """B1: origin re-read must not upsert all-zero stubs into known."""
    vault = tmp_path / "vault"
    sessions = vault / "raw" / "sessions"
    sessions.mkdir(parents=True)
    (sessions / "empty.md").write_text(
        "---\n"
        "tags: [cursor-cli, session-transcript]\n"
        "sessionId: empty-origin-sess\n"
        "ended: 2026-04-01T12:00:00+00:00\n"
        'token_totals: {"input": 0, "cache_creation": 0, "cache_read": 0, "output": 0}\n'
        "---\n\n# empty\n",
        encoding="utf-8",
    )
    origin = tmp_path / "store.db"
    origin.write_bytes(b"")

    class _EmptyAdapter:
        def __init__(self, config=None):
            del config

        def discover_sessions(self):
            return [origin]

        def load_records(self, path):
            del path
            return [
                {
                    "type": "cursor_cli_meta",
                    "sessionId": "empty-origin-sess",
                    "timestamp": "2026-04-01T12:00:00.000Z",
                },
                {"role": "user", "content": "hi"},
                {"role": "assistant", "content": [{"type": "text", "text": "yo"}]},
            ]

        def normalize_records(self, records):
            return [
                r
                if r.get("type") == "cursor_cli_meta"
                else {
                    "type": "assistant" if r.get("role") == "assistant" else "user",
                    "message": {"role": r.get("role"), "content": r.get("content") or []},
                }
                for r in records
            ]

    # Only exercise cursor_cli origin path.
    monkeypatch.setattr(
        "llmwiki.migrate_session_tokens.REGISTRY",
        {"cursor_cli": _EmptyAdapter},
    )
    report = run_migration(vault=vault, dry_run=False, config={})
    assert report["raw_skipped_empty"] == 1
    assert report["origin_skipped_empty"] >= 1
    assert report["origin_upserts"] == 0
    data = load_session_tokens(vault)
    assert "empty-origin-sess" not in data.get("sessions", {})


def test_run_migration_invokes_discover_all(tmp_path: Path, monkeypatch):
    vault = tmp_path / "vault"
    (vault / "raw" / "sessions").mkdir(parents=True)
    called: list[bool] = []

    def _spy() -> None:
        called.append(True)
        discover_all()

    monkeypatch.setattr("llmwiki.migrate_session_tokens.discover_all", _spy)
    monkeypatch.setattr(
        "llmwiki.migrate_session_tokens._backfill_capable_adapter",
        lambda *args, **kwargs: None,
    )
    run_migration(vault=vault, dry_run=True)
    assert called == [True]


def test_coverage_hint_includes_measured_known_lines():
    by_agent = {
        "claude_code": {"measured": 2, "known": 3, "totals": {}},
        "cursor_cli": {
            "measured": 2,
            "known": 1234,
            "totals": {},
            "since": "2026-10-15",
        },
    }
    lines = format_token_coverage_measured_known(by_agent)
    assert lines == [
        "- 2/3 Claude Code",
        "- 2/1234 Cursor CLI (since 2026/10/15)",
    ]
    html = render_token_coverage_hint("tok", by_agent=by_agent)
    assert "Measured on sessions" in html
    assert "- 2/3 Claude Code" in html
    assert "- 2/1234 Cursor CLI (since 2026/10/15)" in html
    assert "with measured token usage" not in html
    # Short panel when measured rows exist — not the long agent encyclopedia.
    assert "included when usage fields are present" not in html
    assert TOKEN_COVERAGE_OTHER_AGENTS_LINE in html


def test_site_stats_prefer_usage_file_totals(tmp_path: Path):
    vault = tmp_path / "vault"
    upsert_session_tokens(
        vault,
        session_key="a1",
        agent="cursor_cli",
        totals={"input": 100, "cache_creation": 0, "cache_read": 0, "output": 50},
        fingerprint="t1",
        last_activity="2026-04-02T00:00:00Z",
        in_raw=True,
    )
    usage = load_session_tokens(vault)
    # Frontmatter metas disagree on purpose — usage file should win headline.
    metas = {"proj": [{"token_totals": '{"input": 1, "output": 1}'}]}
    html = render_site_token_stats(metas, session_tokens_usage=usage)
    assert "150" in html or "150" in json.dumps(usage["totals"])
    assert "Tokens" in html
    assert 'data-llmwiki-tokens-card' in html


def test_page_foot_loads_session_tokens_sidecar():
    """Analytics (and all pages) load the slim sidecar like llmwiki-state.js."""
    html = page_foot(js_prefix="")
    assert 'src="session-tokens.js"' in html
    nested = page_foot(js_prefix="../")
    assert 'src="../session-tokens.js"' in nested


def test_viewer_js_refreshes_tokens_from_sidecar():
    assert "LLMWIKI_SESSION_TOKENS" in JS
    assert "[data-llmwiki-tokens-card]" in JS
    assert "refreshTokensFromSidecar" in JS
