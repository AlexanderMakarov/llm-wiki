"""Cursor usage API adapter (#356)."""
from __future__ import annotations

import base64
import json
from datetime import datetime
from pathlib import Path

from llmwiki.adapters.contrib.cursor_cli import CursorCliAdapter
from llmwiki.cursor_token_events import append_hook_event
from llmwiki.cursor_usage_api import (
    _merge_events_into_cache,
    api_totals_for_conversation,
    apply_api_totals_to_raw_sessions,
    conversation_has_hook_usage,
    load_cache,
    resolve_cursor_usage_api_mode,
    save_cache,
    set_active_vault,
    sync_cursor_usage_api,
    usage_records_from_api_cache,
    user_id_from_jwt,
)
from llmwiki.session_tokens_usage import load_session_tokens


def _jwt(payload: dict) -> str:
    header = base64.urlsafe_b64encode(b'{"alg":"none"}').decode().rstrip("=")
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"{header}.{body}.sig"


def test_user_id_from_jwt_sub_pipe_segment():
    token = _jwt({"sub": "workos|user|acct-user-99"})
    assert user_id_from_jwt(token) == "acct-user-99"


def test_resolve_mode_default_off():
    assert resolve_cursor_usage_api_mode({}) == "off"
    assert resolve_cursor_usage_api_mode({"cursor_usage_api": "dashboard"}) == "dashboard"
    assert resolve_cursor_usage_api_mode({"cursor_usage_api": "ADMIN"}) == "admin"


def test_merge_dashboard_events_into_cache():
    fixture = Path(__file__).parent / "fixtures/cursor_usage_api/dashboard_page1.json"
    body = json.loads(fixture.read_text(encoding="utf-8"))
    events = body["usageEventsDisplay"]
    cache: dict = {"by_conversation": {}, "high_water_ms": 0}
    added = _merge_events_into_cache(cache, events, source="dashboard")
    assert added == 2
    row = cache["by_conversation"]["aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"]
    totals = row["totals"]
    assert totals["input"] == 1200
    assert totals["output"] == 75
    assert totals["cache_read"] == 200
    assert totals["cache_creation"] == 100


def test_sync_dashboard_no_network(tmp_path: Path, monkeypatch):
    fixture = Path(__file__).parent / "fixtures/cursor_usage_api/dashboard_page1.json"
    body = json.loads(fixture.read_text(encoding="utf-8"))

    def fake_fetch(**kwargs):
        return 200, body, None

    monkeypatch.setattr(
        "llmwiki.cursor_usage_api.load_cursor_session_credentials",
        lambda: ("user-1", "token-redacted"),
    )
    monkeypatch.setattr("llmwiki.cursor_usage_api.fetch_dashboard_page", fake_fetch)
    monkeypatch.setattr("llmwiki.cursor_usage_api.should_poll_now", lambda *a, **k: True)

    cfg = {"cursor_usage_api": "dashboard"}
    lines = sync_cursor_usage_api(tmp_path, cfg, force_poll=True)
    assert any("merged" in line for line in lines)
    cache = load_cache(tmp_path)
    assert "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee" in cache["by_conversation"]


def test_hook_wins_over_api(tmp_path: Path, monkeypatch):
    log = tmp_path / "events.jsonl"
    monkeypatch.setenv("LLMWIKI_CURSOR_TOKEN_EVENTS", str(log))
    cid = "conv-prefer-hook"
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
            cid: {
                "events": [
                    {
                        "conversationId": cid,
                        "timestamp": 1,
                        "tokenUsage": {"inputTokens": 9999, "outputTokens": 9999},
                    }
                ],
                "totals": {"input": 9999, "output": 9999, "cache_read": 0, "cache_creation": 0},
            }
        },
        "high_water_ms": 0,
    }
    save_cache(tmp_path, cache)
    assert conversation_has_hook_usage(cid)
    assert api_totals_for_conversation(tmp_path, cid) is None
    assert usage_records_from_api_cache(cid, tmp_path) == []


def test_normalize_merges_api_when_no_hook(tmp_path: Path, monkeypatch):
    cid = "sess-api-only"
    cache = {
        "by_conversation": {
            cid: {
                "events": [
                    {
                        "conversationId": cid,
                        "timestamp": 1,
                        "tokenUsage": {
                            "inputTokens": 300,
                            "outputTokens": 30,
                            "cacheReadTokens": 50,
                            "cacheWriteTokens": 10,
                        },
                    }
                ],
                "totals": {"input": 240, "output": 30, "cache_read": 50, "cache_creation": 10},
            }
        },
        "high_water_ms": 0,
    }
    save_cache(tmp_path, cache)
    set_active_vault(tmp_path)
    adapter = CursorCliAdapter({})
    out = adapter.normalize_records(
        [
            {"type": "cursor_cli_meta", "sessionId": cid},
            {"role": "user", "content": "hi"},
        ]
    )
    usage_rows = [r for r in out if r.get("type") == "assistant"]
    assert len(usage_rows) == 1
    usage = usage_rows[0]["message"]["usage"]
    assert usage["input_tokens"] == 240
    assert usage["output_tokens"] == 30


def test_sync_admin_401_soft(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        "llmwiki.cursor_usage_api.load_admin_api_key",
        lambda cfg: "crsr_test_key",
    )
    monkeypatch.setattr(
        "llmwiki.cursor_usage_api.fetch_admin_page",
        lambda **kwargs: (401, None, "unauthorized"),
    )
    monkeypatch.setattr("llmwiki.cursor_usage_api.should_poll_now", lambda *a, **k: True)
    lines = sync_cursor_usage_api(tmp_path, {"cursor_usage_api": "admin"}, force_poll=True)
    assert any("401" in line for line in lines)


def test_api_only_conversation_upserts_as_cursor_cli_metrics_only(tmp_path: Path):
    """ACP chats with no raw page still count as Cursor CLI Tokens (#356)."""
    cid = "acp-no-raw-aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    cache = {
        "by_conversation": {
            cid: {
                "events": [
                    {
                        "conversationId": cid,
                        "timestamp": 1_700_000_000_000,
                        "tokenUsage": {
                            "inputTokens": 1000,
                            "outputTokens": 50,
                            "cacheReadTokens": 200,
                            "cacheWriteTokens": 0,
                        },
                    }
                ],
                "totals": {
                    "input": 800,
                    "output": 50,
                    "cache_read": 200,
                    "cache_creation": 0,
                },
            }
        },
        "high_water_ms": 1_700_000_000_000,
    }
    save_cache(tmp_path, cache)
    (tmp_path / "raw" / "sessions").mkdir(parents=True)
    (tmp_path / "site").mkdir()
    patched, upserted = apply_api_totals_to_raw_sessions(tmp_path)
    assert patched == 0
    assert upserted == 1
    data = load_session_tokens(tmp_path)
    stub = data["sessions"][cid]
    assert stub["agent"] == "cursor_cli"
    assert stub["metrics_only"] is True
    assert stub["in_raw"] is False
    assert stub["totals"]["input"] == 800
    assert stub["totals"]["output"] == 50
    assert data["by_agent"]["cursor_cli"]["measured"] == 1


def _capture_dashboard_windows(monkeypatch) -> list[tuple[int, int]]:
    """Fake an empty dashboard and record each requested ``[start, end)`` window."""
    windows: list[tuple[int, int]] = []

    def fake_fetch(**kwargs):
        windows.append((kwargs["start_ms"], kwargs["end_ms"]))
        return 200, {"totalUsageEventsCount": 0, "usageEventsDisplay": []}, None

    monkeypatch.setattr(
        "llmwiki.cursor_usage_api.load_cursor_session_credentials",
        lambda: ("user-1", "token-redacted"),
    )
    monkeypatch.setattr("llmwiki.cursor_usage_api.fetch_dashboard_page", fake_fetch)
    return windows


def _ms(day: str) -> int:
    return int(datetime.fromisoformat(f"{day}T00:00:00+00:00").timestamp() * 1000)


def test_first_poll_backfills_from_lookback_since(tmp_path: Path, monkeypatch):
    """ACP sessions older than the first poll get Tokens: fetch starts at ``since``."""
    windows = _capture_dashboard_windows(monkeypatch)
    cfg = {"cursor_usage_api": "dashboard", "filters": {"since": "2026-06-01"}}
    sync_cursor_usage_api(tmp_path, cfg, force_poll=True)
    assert windows and windows[0][0] == _ms("2026-06-01")


def test_existing_cache_without_backfill_marker_refetches_history(
    tmp_path: Path, monkeypatch
):
    """Caches written before the backfill fix only hold ~3 days; re-fetch from ``since``."""
    save_cache(tmp_path, {"by_conversation": {}, "high_water_ms": _ms("2026-11-01")})
    windows = _capture_dashboard_windows(monkeypatch)
    cfg = {"cursor_usage_api": "dashboard", "filters": {"since": "2026-06-01"}}
    sync_cursor_usage_api(tmp_path, cfg, force_poll=True)
    assert windows[0][0] == _ms("2026-06-01")


def test_after_backfill_polls_are_incremental(tmp_path: Path, monkeypatch):
    windows = _capture_dashboard_windows(monkeypatch)
    cfg = {"cursor_usage_api": "dashboard", "filters": {"since": "2026-06-01"}}
    sync_cursor_usage_api(tmp_path, cfg, force_poll=True)
    cache = load_cache(tmp_path)
    cache["high_water_ms"] = _ms("2026-11-01")
    save_cache(tmp_path, cache)
    windows.clear()
    sync_cursor_usage_api(tmp_path, cfg, force_poll=True)
    assert windows[0][0] == _ms("2026-11-01")


def test_earlier_since_triggers_new_backfill(tmp_path: Path, monkeypatch):
    windows = _capture_dashboard_windows(monkeypatch)
    sync_cursor_usage_api(
        tmp_path,
        {"cursor_usage_api": "dashboard", "filters": {"since": "2026-06-01"}},
        force_poll=True,
    )
    cache = load_cache(tmp_path)
    cache["high_water_ms"] = _ms("2026-11-01")
    save_cache(tmp_path, cache)
    windows.clear()
    sync_cursor_usage_api(
        tmp_path,
        {"cursor_usage_api": "dashboard", "adapters": {"cursor_cli": {"since": "2026-03-01"}}},
        force_poll=True,
    )
    assert windows[0][0] == _ms("2026-03-01")


def test_failed_backfill_is_retried(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        "llmwiki.cursor_usage_api.load_cursor_session_credentials",
        lambda: ("user-1", "token-redacted"),
    )
    monkeypatch.setattr(
        "llmwiki.cursor_usage_api.fetch_dashboard_page",
        lambda **kwargs: (429, None, "60"),
    )
    cfg = {"cursor_usage_api": "dashboard", "filters": {"since": "2026-06-01"}}
    sync_cursor_usage_api(tmp_path, cfg, force_poll=True)
    windows = _capture_dashboard_windows(monkeypatch)
    sync_cursor_usage_api(tmp_path, cfg, force_poll=True)
    assert windows[0][0] == _ms("2026-06-01")
