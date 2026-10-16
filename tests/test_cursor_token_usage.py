"""Unit tests for Cursor → Claude usage mapping (#325)."""
from __future__ import annotations

from llmwiki.cursor_token_usage import (
    extract_cursor_usage_from_record,
    map_cursor_usage_to_claude_usage,
)


def test_inclusive_subtract_splits_cache_from_input():
    raw = {
        "input_tokens": 1000,
        "output_tokens": 200,
        "cache_read_tokens": 300,
        "cache_write_tokens": 100,
    }
    mapped = map_cursor_usage_to_claude_usage(raw)
    assert mapped == {
        "input_tokens": 600,
        "cache_creation_input_tokens": 100,
        "cache_read_input_tokens": 300,
        "output_tokens": 200,
    }


def test_clamp_when_cache_exceeds_input():
    raw = {
        "input_tokens": 50,
        "output_tokens": 10,
        "cache_read_tokens": 40,
        "cache_write_tokens": 30,
    }
    mapped = map_cursor_usage_to_claude_usage(raw)
    assert mapped is not None
    assert mapped["input_tokens"] == 0
    assert mapped["cache_read_input_tokens"] == 40
    assert mapped["cache_creation_input_tokens"] == 30


def test_missing_cache_fields_treated_as_zero():
    raw = {"input_tokens": 500, "output_tokens": 42}
    mapped = map_cursor_usage_to_claude_usage(raw)
    assert mapped == {
        "input_tokens": 500,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
        "output_tokens": 42,
    }


def test_snake_cache_aliases():
    raw = {
        "input_tokens": 80,
        "output_tokens": 5,
        "cache_read": 20,
        "cache_write": 10,
    }
    mapped = map_cursor_usage_to_claude_usage(raw)
    assert mapped is not None
    assert mapped["input_tokens"] == 50
    assert mapped["cache_read_input_tokens"] == 20
    assert mapped["cache_creation_input_tokens"] == 10


def test_occupancy_only_rejected():
    occupancy = {
        "used_tokens": 120_000,
        "max_tokens": 200_000,
    }
    assert map_cursor_usage_to_claude_usage(occupancy) is None


def test_all_zero_throughput_not_measured():
    raw = {"input_tokens": 0, "output_tokens": 0}
    assert map_cursor_usage_to_claude_usage(raw) is None


def test_output_only_turn():
    raw = {"output_tokens": 17}
    mapped = map_cursor_usage_to_claude_usage(raw)
    assert mapped is not None
    assert mapped["input_tokens"] == 0
    assert mapped["output_tokens"] == 17


def test_dual_hook_same_payload_maps_once_per_call():
    """Map layer is pure; callers must not sum stop + afterAgentResponse."""
    hook_usage = {
        "input_tokens": 400,
        "output_tokens": 50,
        "cache_read_tokens": 100,
        "cache_write_tokens": 0,
    }
    once = map_cursor_usage_to_claude_usage(hook_usage)
    twice = map_cursor_usage_to_claude_usage(hook_usage)
    assert once == twice
    assert once["input_tokens"] == 300


def test_extract_from_message_usage():
    rec = {
        "type": "assistant",
        "message": {
            "usage": {
                "input_tokens": 10,
                "output_tokens": 3,
            },
        },
    }
    mapped = extract_cursor_usage_from_record(rec)
    assert mapped is not None
    assert mapped["output_tokens"] == 3


def test_extract_rejects_occupancy_on_record():
    rec = {
        "type": "assistant",
        "used_tokens": 99_000,
        "max_tokens": 128_000,
    }
    assert extract_cursor_usage_from_record(rec) is None


def test_camel_case_stream_json_usage():
    """Agent CLI stream-json result.usage uses camelCase (#325)."""
    raw = {
        "inputTokens": 1000,
        "outputTokens": 20,
        "cacheReadTokens": 400,
        "cacheWriteTokens": 100,
    }
    mapped = map_cursor_usage_to_claude_usage(raw)
    assert mapped == {
        "input_tokens": 500,
        "cache_creation_input_tokens": 100,
        "cache_read_input_tokens": 400,
        "output_tokens": 20,
    }


def test_extract_nested_camel_case_usage():
    rec = {
        "type": "result",
        "usage": {
            "inputTokens": 80,
            "outputTokens": 5,
            "cacheReadTokens": 20,
            "cacheWriteTokens": 0,
        },
    }
    mapped = extract_cursor_usage_from_record(rec)
    assert mapped is not None
    assert mapped["input_tokens"] == 60
    assert mapped["output_tokens"] == 5
