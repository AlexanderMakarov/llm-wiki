"""Unit tests for Codex CLI → Claude usage mapping (#324).

@spec: 329-codex-cli-token-usage
"""
from __future__ import annotations

from llmwiki.codex_token_usage import (
    extract_codex_session_usage,
    map_codex_token_usage_to_claude_usage,
)


def _token_count_event(
    *,
    total: dict | None = None,
    last: dict | None = None,
    model_context_window: int | None = None,
    rate_limits: dict | None = None,
) -> dict:
    info: dict = {}
    if total is not None:
        info["total_token_usage"] = total
    if last is not None:
        info["last_token_usage"] = last
    if model_context_window is not None:
        info["model_context_window"] = model_context_window
    payload: dict = {"type": "token_count", "info": info}
    if rate_limits is not None:
        payload["rate_limits"] = rate_limits
    return {"type": "event_msg", "payload": payload}


def test_inclusive_subtract_splits_cache_from_input():
    raw = {
        "input_tokens": 1000,
        "cached_input_tokens": 300,
        "cache_write_input_tokens": 100,
        "output_tokens": 200,
        "reasoning_output_tokens": 0,
        "total_tokens": 1200,
    }
    mapped = map_codex_token_usage_to_claude_usage(raw)
    assert mapped == {
        "input_tokens": 600,
        "cache_creation_input_tokens": 100,
        "cache_read_input_tokens": 300,
        "output_tokens": 200,
    }


def test_clamp_when_cache_exceeds_input():
    raw = {
        "input_tokens": 50,
        "cached_input_tokens": 40,
        "cache_write_input_tokens": 30,
        "output_tokens": 10,
    }
    mapped = map_codex_token_usage_to_claude_usage(raw)
    assert mapped is not None
    assert mapped["input_tokens"] == 0
    assert mapped["cache_read_input_tokens"] == 40
    assert mapped["cache_creation_input_tokens"] == 30


def test_reasoning_subtracted_when_key_present():
    raw = {
        "input_tokens": 100,
        "cached_input_tokens": 0,
        "cache_write_input_tokens": 0,
        "output_tokens": 80,
        "reasoning_output_tokens": 50,
    }
    mapped = map_codex_token_usage_to_claude_usage(raw)
    assert mapped is not None
    assert mapped["output_tokens"] == 30


def test_reasoning_clamp_when_exceeds_output():
    raw = {
        "input_tokens": 10,
        "output_tokens": 5,
        "reasoning_output_tokens": 9,
    }
    mapped = map_codex_token_usage_to_claude_usage(raw)
    assert mapped is not None
    assert mapped["output_tokens"] == 0


def test_reasoning_key_absent_keeps_output_as_is():
    raw = {
        "input_tokens": 100,
        "cached_input_tokens": 0,
        "cache_write_input_tokens": 0,
        "output_tokens": 80,
    }
    mapped = map_codex_token_usage_to_claude_usage(raw)
    assert mapped is not None
    assert mapped["output_tokens"] == 80


def test_missing_cache_fields_treated_as_zero():
    raw = {"input_tokens": 500, "output_tokens": 42}
    mapped = map_codex_token_usage_to_claude_usage(raw)
    assert mapped == {
        "input_tokens": 500,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
        "output_tokens": 42,
    }


def test_empty_and_all_zero_rejected():
    assert map_codex_token_usage_to_claude_usage({}) is None
    assert map_codex_token_usage_to_claude_usage(
        {"input_tokens": 0, "output_tokens": 0}
    ) is None
    assert map_codex_token_usage_to_claude_usage(None) is None  # type: ignore[arg-type]


def test_occupancy_only_blob_rejected():
    assert map_codex_token_usage_to_claude_usage({"model_context_window": 128_000}) is None


def test_extract_prefers_last_total_not_sum_of_totals():
    """Successive total_token_usage snapshots are cumulative — take last only."""
    early = {
        "input_tokens": 100,
        "cached_input_tokens": 0,
        "cache_write_input_tokens": 0,
        "output_tokens": 20,
        "reasoning_output_tokens": 0,
    }
    late = {
        "input_tokens": 400,
        "cached_input_tokens": 50,
        "cache_write_input_tokens": 10,
        "output_tokens": 90,
        "reasoning_output_tokens": 30,
    }
    records = [
        _token_count_event(total=early, last=early),
        _token_count_event(total=late, last={
            "input_tokens": 300,
            "cached_input_tokens": 50,
            "cache_write_input_tokens": 10,
            "output_tokens": 70,
            "reasoning_output_tokens": 30,
        }),
    ]
    mapped = extract_codex_session_usage(records)
    assert mapped == {
        "input_tokens": 340,  # 400 - 50 - 10
        "cache_creation_input_tokens": 10,
        "cache_read_input_tokens": 50,
        "output_tokens": 60,  # 90 - 30
    }
    # If we had summed both totals: input would be 500 — guard against that.
    assert mapped["input_tokens"] != 100 + 400 - 50 - 10


def test_extract_sums_last_when_totals_absent():
    turn1 = {
        "input_tokens": 100,
        "cached_input_tokens": 20,
        "cache_write_input_tokens": 5,
        "output_tokens": 40,
        "reasoning_output_tokens": 10,
    }
    turn2 = {
        "input_tokens": 200,
        "cached_input_tokens": 30,
        "cache_write_input_tokens": 0,
        "output_tokens": 50,
        "reasoning_output_tokens": 15,
    }
    records = [
        _token_count_event(last=turn1),
        _token_count_event(last=turn2),
    ]
    mapped = extract_codex_session_usage(records)
    assert mapped == {
        "input_tokens": 245,  # (100+200) - (20+30) - (5+0)
        "cache_creation_input_tokens": 5,
        "cache_read_input_tokens": 50,
        "output_tokens": 65,  # (40+50) - (10+15)
    }


def test_extract_falls_back_to_lasts_when_total_unmappable():
    """Empty / all-zero total_token_usage must not block last_token_usage (#324 review)."""
    last = {
        "input_tokens": 80,
        "cached_input_tokens": 10,
        "cache_write_input_tokens": 0,
        "output_tokens": 20,
        "reasoning_output_tokens": 5,
    }
    records = [
        _token_count_event(total={}, last=last),
        _token_count_event(
            total={
                "input_tokens": 0,
                "cached_input_tokens": 0,
                "cache_write_input_tokens": 0,
                "output_tokens": 0,
                "reasoning_output_tokens": 0,
            },
            last={
                "input_tokens": 40,
                "cached_input_tokens": 0,
                "cache_write_input_tokens": 5,
                "output_tokens": 10,
                "reasoning_output_tokens": 0,
            },
        ),
    ]
    mapped = extract_codex_session_usage(records)
    assert mapped == {
        "input_tokens": 105,  # (80+40) - (10+0) - (0+5)
        "cache_creation_input_tokens": 5,
        "cache_read_input_tokens": 10,
        "output_tokens": 25,  # (20+10) - (5+0)
    }


def test_extract_occupancy_only_returns_none():
    records = [_token_count_event(model_context_window=200_000)]
    assert extract_codex_session_usage(records) is None


def test_extract_rate_limits_only_returns_none():
    records = [
        {
            "type": "event_msg",
            "payload": {
                "type": "token_count",
                "info": None,
                "rate_limits": {"primary": {"used_percent": 12.5}},
            },
        }
    ]
    assert extract_codex_session_usage(records) is None


def test_extract_empty_session_returns_none():
    assert extract_codex_session_usage([]) is None
    assert extract_codex_session_usage(
        [{"type": "response_item", "payload": {"role": "user"}}]
    ) is None


def test_extract_ignores_non_token_count_events():
    records = [
        {"type": "event_msg", "payload": {"type": "task_started"}},
        _token_count_event(
            total={
                "input_tokens": 10,
                "output_tokens": 3,
                "cached_input_tokens": 0,
                "cache_write_input_tokens": 0,
            }
        ),
    ]
    mapped = extract_codex_session_usage(records)
    assert mapped is not None
    assert mapped["input_tokens"] == 10
    assert mapped["output_tokens"] == 3
