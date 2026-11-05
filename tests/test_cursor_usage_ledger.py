"""Cursor IDE usage ledger (#396)."""
from __future__ import annotations

import json
from pathlib import Path

from llmwiki.cursor_token_events import append_hook_event
from llmwiki.cursor_usage_api import load_cache as load_api_cache
from llmwiki.cursor_usage_api import usage_records_from_api_cache
from llmwiki.cursor_usage_ledger import (
    apply_ledger_totals_to_raw_sessions,
    load_cache,
    resolve_cursor_usage_ledger_enabled,
    scan_global_vscdb,
    sync_cursor_usage_ledger,
    usage_records_from_ledger_cache,
)
from tests.fixtures_cursor_ide import make_cursor_ide_db


def test_resolve_ledger_enabled_default_on():
    assert resolve_cursor_usage_ledger_enabled({}) is True
    assert resolve_cursor_usage_ledger_enabled({"cursor_usage_ledger": False}) is False


def test_scan_aggregates_bubble_token_count(tmp_path: Path):
    cid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    db = make_cursor_ide_db(
        tmp_path / "state.vscdb",
        composers=[
            {
                "composer_id": cid,
                "bubbles": [
                    {
                        "bubble_id": "b1",
                        "type": 2,
                        "text": "hi",
                        "token_count": {"inputTokens": 100, "outputTokens": 5},
                    },
                    {
                        "bubble_id": "b2",
                        "type": 2,
                        "text": "again",
                        "token_count": {"inputTokens": 50, "outputTokens": 10},
                    },
                ],
            }
        ],
    )
    scanned = scan_global_vscdb(db)
    row = scanned["by_conversation"][cid]
    assert row["totals"]["input"] == 150
    assert row["totals"]["output"] == 15
    assert row["bubble_count"] == 2


def test_sync_writes_vault_cache(tmp_path: Path, monkeypatch):
    cid = "bbbbbbbb-bbbb-cccc-dddd-eeeeeeeeeeee"
    db = make_cursor_ide_db(
        tmp_path / "state.vscdb",
        composers=[
            {
                "composer_id": cid,
                "bubbles": [
                    {
                        "bubble_id": "b1",
                        "type": 2,
                        "text": "x",
                        "token_count": {"inputTokens": 20, "outputTokens": 2},
                    },
                ],
            }
        ],
    )
    monkeypatch.setattr(
        "llmwiki.cursor_usage_ledger.global_vscdb_path",
        lambda: db,
    )
    lines = sync_cursor_usage_ledger(tmp_path, {}, force_rescan=True)
    assert any("merged" in line for line in lines)
    cache = load_cache(tmp_path)
    assert cid in cache["by_conversation"]


def test_hook_wins_over_ledger(tmp_path: Path, monkeypatch):
    log = tmp_path / "events.jsonl"
    monkeypatch.setenv("LLMWIKI_CURSOR_TOKEN_EVENTS", str(log))
    cid = "conv-prefer-hook-ledger"
    append_hook_event(
        {
            "conversation_id": cid,
            "generation_id": "g1",
            "input_tokens": 100,
            "output_tokens": 10,
        }
    )
    cache = {
        "by_conversation": {
            cid: {"totals": {"input": 9999, "output": 9999, "cache_creation": 0, "cache_read": 0}}
        }
    }
    (tmp_path / "usage").mkdir(parents=True)
    (tmp_path / "usage" / "cursor-usage-ledger-cache.json").write_text(
        json.dumps(cache), encoding="utf-8"
    )
    assert usage_records_from_ledger_cache(cid, tmp_path) == []


def test_ledger_wins_over_api(tmp_path: Path, monkeypatch):
    cid = "composer-ledger-over-api"
    ledger = {
        "by_conversation": {
            cid: {"totals": {"input": 50, "output": 5, "cache_creation": 0, "cache_read": 0}}
        }
    }
    (tmp_path / "usage").mkdir(parents=True)
    (tmp_path / "usage" / "cursor-usage-ledger-cache.json").write_text(
        json.dumps(ledger), encoding="utf-8"
    )
    api = {
        "by_conversation": {
            cid: {
                "totals": {"input": 9000, "output": 9000, "cache_creation": 0, "cache_read": 0},
                "events": [],
            }
        },
        "high_water_ms": 0,
    }
    (tmp_path / "usage" / "cursor-usage-api-cache.json").write_text(
        json.dumps(api), encoding="utf-8"
    )
    assert usage_records_from_api_cache(cid, tmp_path) == []
    rows = usage_records_from_ledger_cache(cid, tmp_path)
    assert rows and rows[0]["message"]["usage"]["input_tokens"] == 50


def test_apply_ledger_patches_raw_frontmatter(tmp_path: Path, monkeypatch):
    cid = "cccccccc-cccc-cccc-cccc-cccccccccccc"
    sessions = tmp_path / "raw" / "sessions"
    sessions.mkdir(parents=True)
    raw = sessions / "2026-01-01-cursor-test.md"
    raw.write_text(
        f"""---
title: Test
type: source
tags: [cursor-ide]
sessionId: {cid}
started: 2026-01-01T00:00:00+00:00
---

# Test
""",
        encoding="utf-8",
    )
    cache = {
        "by_conversation": {
            cid: {"totals": {"input": 40, "output": 4, "cache_creation": 0, "cache_read": 0}}
        }
    }
    (tmp_path / "usage").mkdir(parents=True)
    (tmp_path / "usage" / "cursor-usage-ledger-cache.json").write_text(
        json.dumps(cache), encoding="utf-8"
    )
    patched, upserted = apply_ledger_totals_to_raw_sessions(tmp_path)
    assert patched == 1
    assert upserted == 1
    assert "token_totals:" in raw.read_text(encoding="utf-8")
    # API cache untouched
    assert load_api_cache(tmp_path)["by_conversation"] == {}
