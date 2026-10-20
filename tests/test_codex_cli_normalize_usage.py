"""Adapter wiring: Codex normalize_records attaches mapped message.usage (#324).

@spec: 329-codex-cli-token-usage
"""
from __future__ import annotations

import json
from pathlib import Path

from llmwiki.adapters.codex_cli import CodexCliAdapter
from llmwiki.convert import compute_token_totals, parse_jsonl

_FIXTURE = (
    Path(__file__).resolve().parent / "fixtures" / "codex_token_count_session.jsonl"
)

# Final cumulative total_token_usage from the fixture (last token_count only).
_EXPECTED_USAGE = {
    "input_tokens": 340,  # 400 - 50 - 10
    "cache_creation_input_tokens": 10,
    "cache_read_input_tokens": 50,
    "output_tokens": 60,  # 90 - 30 reasoning omitted
}


def test_normalize_fixture_attaches_usage_on_last_assistant():
    adapter = CodexCliAdapter()
    raw = parse_jsonl(_FIXTURE)
    out = adapter.normalize_records(raw)

    assistants = [r for r in out if r.get("type") == "assistant"]
    assert len(assistants) == 2
    assert "usage" not in assistants[0]["message"]
    assert assistants[1]["message"]["usage"] == _EXPECTED_USAGE

    # Conversation mapping unchanged: user turns + assistant text preserved.
    users = [r for r in out if r.get("type") == "user"]
    assert len(users) == 2
    assert "Summarize the plan" in users[0]["message"]["content"]
    assert assistants[0]["message"]["content"][0]["text"] == "Here is a short plan."
    assert assistants[1]["message"]["content"][0]["text"] == "Added adapter coverage."


def test_normalize_fixture_totals_match_final_cumulative_not_sum():
    adapter = CodexCliAdapter()
    raw = parse_jsonl(_FIXTURE)
    out = adapter.normalize_records(raw)
    totals = compute_token_totals(out)
    assert totals == {
        "input": 340,
        "cache_creation": 10,
        "cache_read": 50,
        "output": 60,
    }
    # Guard: summing both cumulative snapshots would inflate input to 500.
    assert totals["input"] != 100 + 400 - 50 - 10


def test_normalize_synthetic_assistant_when_usage_but_no_assistant():
    adapter = CodexCliAdapter()
    records = [
        {
            "type": "event_msg",
            "payload": {
                "type": "token_count",
                "info": {
                    "total_token_usage": {
                        "input_tokens": 10,
                        "cached_input_tokens": 0,
                        "cache_write_input_tokens": 0,
                        "output_tokens": 3,
                        "reasoning_output_tokens": 0,
                    }
                },
            },
        }
    ]
    out = adapter.normalize_records(records)
    assert len(out) == 1
    assert out[0]["type"] == "assistant"
    assert out[0]["message"]["usage"] == {
        "input_tokens": 10,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
        "output_tokens": 3,
    }
    assert out[0]["message"]["content"] == []


def test_normalize_occupancy_and_rate_limits_alone_no_usage():
    adapter = CodexCliAdapter()
    records = [
        {
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": "hi"}],
            },
        },
        {
            "type": "event_msg",
            "payload": {
                "type": "token_count",
                "info": {"model_context_window": 200_000},
                "rate_limits": {"primary": {"used_percent": 12.5}},
            },
        },
    ]
    out = adapter.normalize_records(records)
    assistants = [r for r in out if r.get("type") == "assistant"]
    assert len(assistants) == 1
    assert "usage" not in assistants[0]["message"]
    assert compute_token_totals(out) == {
        "input": 0,
        "cache_creation": 0,
        "cache_read": 0,
        "output": 0,
    }


def test_fixture_file_has_multiple_monotonic_token_counts():
    """Sanity: fixture itself is multi-event cumulative (not a single snapshot)."""
    lines = [
        json.loads(line)
        for line in _FIXTURE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    totals = []
    for rec in lines:
        if rec.get("type") != "event_msg":
            continue
        payload = rec.get("payload") or {}
        if payload.get("type") != "token_count":
            continue
        info = payload.get("info") or {}
        total = info.get("total_token_usage") or {}
        if "input_tokens" in total:
            totals.append(int(total["input_tokens"]))
    assert len(totals) >= 2
    assert totals == sorted(totals)
    assert totals[-1] > totals[0]
