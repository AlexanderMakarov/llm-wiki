"""Wiring for Cursor usage map, usage store upsert, migrate, coverage (#325).

# @spec: 328-cursor-cli-token-usage
"""
from __future__ import annotations

import json
from pathlib import Path

from llmwiki.adapters.contrib.cursor_cli import CursorCliAdapter
from llmwiki.migrate_session_tokens import run_migration
from llmwiki.session_tokens_usage import load_session_tokens, upsert_session_tokens
from llmwiki.viz_tokens import (
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
    # Do not re-read the developer's real agent stores during unit tests.
    monkeypatch.setattr(
        "llmwiki.migrate_session_tokens._backfill_capable_adapter",
        lambda *args, **kwargs: None,
    )
    report = run_migration(vault=vault, dry_run=False)
    assert report["errors"] == 0
    assert report["raw_upserts"] >= 1
    data = load_session_tokens(vault)
    assert data["sessions"]["sess-migrate-1"]["totals"]["input"] == 10
    assert data["totals"]["sum"] == 17


def test_coverage_hint_includes_measured_known_lines():
    by_agent = {
        "claude_code": {"measured": 2, "known": 3, "totals": {}},
        "cursor_cli": {"measured": 0, "known": 5, "totals": {}},
    }
    lines = format_token_coverage_measured_known(by_agent)
    assert lines == ["2/3 Claude Code sessions with measured token usage."]
    html = render_token_coverage_hint("tok", by_agent=by_agent)
    assert "2/3 Claude Code sessions with measured token usage." in html
    assert "Cursor CLI" not in html or "0/5" not in html


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
