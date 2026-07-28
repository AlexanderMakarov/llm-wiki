"""Tests for v0.8 session metrics (#63) — extends the converter with
structured per-session metrics in frontmatter.
"""

from __future__ import annotations

import json

import pytest

from llmwiki.convert import (
    compute_duration_seconds,
    compute_hour_buckets,
    compute_token_totals,
    compute_tool_counts,
    compute_turn_count,
    extract_tools_used,
    summarize_tool_use,
    tool_use_recorded_names,
)

# ─── synthetic records fixture ───────────────────────────────────────────


@pytest.fixture
def synthetic_records():
    """Five-record session spanning one hour with Bash + 2×Read tool calls."""
    return [
        {
            "type": "user",
            "message": {"content": "Hello"},
            "timestamp": "2026-04-07T10:00:00Z",
        },
        {
            "type": "assistant",
            "message": {
                "model": "claude-haiku-4-5",
                "content": [
                    {"type": "text", "text": "Hi"},
                    {"type": "tool_use", "name": "Bash", "input": {"command": "ls"}},
                ],
                "usage": {
                    "input_tokens": 100,
                    "cache_creation_input_tokens": 50,
                    "cache_read_input_tokens": 200,
                    "output_tokens": 30,
                },
            },
            "timestamp": "2026-04-07T10:00:05Z",
        },
        {
            "type": "user",
            "message": {"content": [{"type": "tool_result", "content": "ok"}]},
            "timestamp": "2026-04-07T10:00:06Z",
        },
        {
            "type": "user",
            "message": {"content": "Another turn"},
            "timestamp": "2026-04-07T11:05:00Z",
        },
        {
            "type": "assistant",
            "message": {
                "model": "claude-haiku-4-5",
                "content": [
                    {"type": "tool_use", "name": "Read", "input": {"file_path": "/a"}},
                    {"type": "tool_use", "name": "Read", "input": {"file_path": "/b"}},
                ],
                "usage": {"input_tokens": 200, "output_tokens": 10},
            },
            "timestamp": "2026-04-07T11:05:02Z",
        },
    ]


# ─── compute_tool_counts ─────────────────────────────────────────────────


def test_tool_counts_basic(synthetic_records):
    counts = compute_tool_counts(synthetic_records)
    assert counts == {"Read": 2, "Bash": 1}


def test_tool_counts_empty_session():
    assert compute_tool_counts([]) == {}


def test_tool_counts_ignores_non_assistant():
    records = [
        {"type": "user", "message": {"content": "hi"}},
        {"type": "system", "message": {}},
    ]
    assert compute_tool_counts(records) == {}


def test_tool_counts_handles_missing_name():
    records = [
        {
            "type": "assistant",
            "message": {"content": [{"type": "tool_use"}]},
        }
    ]
    assert compute_tool_counts(records) == {"Unknown": 1}


def test_tool_counts_sorted_descending():
    records = [
        {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "tool_use", "name": "Edit"},
                    {"type": "tool_use", "name": "Bash"},
                    {"type": "tool_use", "name": "Bash"},
                    {"type": "tool_use", "name": "Bash"},
                    {"type": "tool_use", "name": "Edit"},
                    {"type": "tool_use", "name": "Read"},
                ]
            },
        }
    ]
    counts = compute_tool_counts(records)
    # Bash (3) > Edit (2) > Read (1); insertion order preserved
    assert list(counts.keys()) == ["Bash", "Edit", "Read"]
    assert counts == {"Bash": 3, "Edit": 2, "Read": 1}


# ─── CallMcpTool expansion ─────────────────────────────────────────────────


def _call_mcp_block(
    server: str | None = "llmwiki",
    tool: str | None = "wiki_query",
    *,
    tool_key: str = "toolName",
) -> dict:
    inp: dict = {"arguments": {"query": "test"}}
    if server is not None:
        inp["server"] = server
    if tool is not None:
        inp[tool_key] = tool
    return {
        "type": "tool_use",
        "name": "CallMcpTool",
        "input": inp,
    }


def test_tool_use_recorded_names_expands_call_mcp_tool():
    block = _call_mcp_block()
    assert tool_use_recorded_names(block) == [
        "CallMcpTool",
        "mcp__llmwiki__wiki_query",
    ]


def test_tool_use_recorded_names_accepts_tool_alias():
    block = _call_mcp_block(tool_key="tool")
    assert tool_use_recorded_names(block) == [
        "CallMcpTool",
        "mcp__llmwiki__wiki_query",
    ]


def test_tool_use_recorded_names_accepts_tool_name_alias():
    block = _call_mcp_block(tool_key="tool_name")
    assert tool_use_recorded_names(block) == [
        "CallMcpTool",
        "mcp__llmwiki__wiki_query",
    ]


def test_tool_use_recorded_names_missing_server_stays_wrapper_only():
    block = _call_mcp_block(server=None)
    assert tool_use_recorded_names(block) == ["CallMcpTool"]


def test_tool_use_recorded_names_missing_tool_stays_wrapper_only():
    block = _call_mcp_block(tool=None)
    assert tool_use_recorded_names(block) == ["CallMcpTool"]


def test_extract_tools_used_expands_call_mcp_tool():
    records = [
        {
            "type": "assistant",
            "message": {"content": [_call_mcp_block()]},
        }
    ]
    assert extract_tools_used(records) == [
        "CallMcpTool",
        "mcp__llmwiki__wiki_query",
    ]


def test_compute_tool_counts_expands_call_mcp_tool():
    records = [
        {
            "type": "assistant",
            "message": {
                "content": [
                    _call_mcp_block(tool="wiki_query"),
                    _call_mcp_block(tool="wiki_search"),
                ]
            },
        }
    ]
    counts = compute_tool_counts(records)
    assert counts == {
        "CallMcpTool": 2,
        "mcp__llmwiki__wiki_query": 1,
        "mcp__llmwiki__wiki_search": 1,
    }


def test_summarize_call_mcp_tool_shows_server_and_tool():
    from llmwiki.convert import Redactor

    block = _call_mcp_block(server="llmwiki", tool="wiki_query")
    out = summarize_tool_use(block, Redactor({}), {})
    assert out == "`CallMcpTool`: `llmwiki` / `wiki_query`"


def test_summarize_call_mcp_tool_without_tool_falls_back_to_inputs():
    from llmwiki.convert import Redactor

    block = {
        "type": "tool_use",
        "name": "CallMcpTool",
        "input": {"server": "llmwiki", "arguments": {}},
    }
    out = summarize_tool_use(block, Redactor({}), {})
    assert out == "`CallMcpTool` (inputs: server, arguments)"


# ─── compute_token_totals ────────────────────────────────────────────────


def test_token_totals_basic(synthetic_records):
    totals = compute_token_totals(synthetic_records)
    assert totals == {
        "input": 300,
        "cache_creation": 50,
        "cache_read": 200,
        "output": 40,
    }


def test_token_totals_missing_usage_is_zero():
    records = [{"type": "assistant", "message": {"content": []}}]
    assert compute_token_totals(records) == {
        "input": 0,
        "cache_creation": 0,
        "cache_read": 0,
        "output": 0,
    }


def test_token_totals_empty_session():
    assert compute_token_totals([]) == {
        "input": 0,
        "cache_creation": 0,
        "cache_read": 0,
        "output": 0,
    }


def test_token_totals_partial_usage_counts_zero_for_missing_fields():
    records = [
        {
            "type": "assistant",
            "message": {"content": [], "usage": {"input_tokens": 500}},
        }
    ]
    totals = compute_token_totals(records)
    assert totals["input"] == 500
    assert totals["output"] == 0
    assert totals["cache_creation"] == 0
    assert totals["cache_read"] == 0


# ─── compute_turn_count ──────────────────────────────────────────────────


def test_turn_count_counts_real_user_prompts(synthetic_records):
    assert compute_turn_count(synthetic_records) == 2


def test_turn_count_empty_session():
    assert compute_turn_count([]) == 0


def test_turn_count_ignores_tool_result_deliveries():
    # tool_result is a list-content user record; should NOT count as a turn
    records = [
        {"type": "user", "message": {"content": "real prompt"}},
        {"type": "user", "message": {"content": [{"type": "tool_result", "content": "ok"}]}},
    ]
    assert compute_turn_count(records) == 1


# ─── compute_hour_buckets ────────────────────────────────────────────────


def test_hour_buckets_basic(synthetic_records):
    buckets = compute_hour_buckets(synthetic_records)
    assert buckets == {"2026-04-07T10": 3, "2026-04-07T11": 2}


def test_hour_buckets_sorted_chronologically():
    records = [
        {"type": "user", "timestamp": "2026-04-07T15:00:00Z", "message": {}},
        {"type": "user", "timestamp": "2026-04-07T09:00:00Z", "message": {}},
        {"type": "user", "timestamp": "2026-04-07T12:00:00Z", "message": {}},
    ]
    buckets = compute_hour_buckets(records)
    assert list(buckets.keys()) == ["2026-04-07T09", "2026-04-07T12", "2026-04-07T15"]


def test_hour_buckets_normalises_timezone():
    # 10:00 UTC+5 == 05:00 UTC
    records = [
        {"type": "user", "timestamp": "2026-04-07T10:00:00+05:00", "message": {}}
    ]
    buckets = compute_hour_buckets(records)
    assert buckets == {"2026-04-07T05": 1}


def test_hour_buckets_skips_missing_timestamps():
    records = [
        {"type": "user", "message": {}},
        {"type": "user", "timestamp": "", "message": {}},
        {"type": "user", "timestamp": "2026-04-07T10:00:00Z", "message": {}},
    ]
    assert compute_hour_buckets(records) == {"2026-04-07T10": 1}


def test_hour_buckets_all_values_are_positive_integers(synthetic_records):
    buckets = compute_hour_buckets(synthetic_records)
    for key, val in buckets.items():
        assert isinstance(val, int)
        assert val >= 1
        assert "T" in key


# ─── compute_duration_seconds ────────────────────────────────────────────


def test_duration_seconds_basic(synthetic_records):
    # 11:05:02 - 10:00:00 = 3902s
    assert compute_duration_seconds(synthetic_records) == 3902


def test_duration_seconds_empty_session():
    assert compute_duration_seconds([]) == 0


def test_duration_seconds_single_record():
    records = [
        {"type": "user", "timestamp": "2026-04-07T10:00:00Z", "message": {}},
    ]
    assert compute_duration_seconds(records) == 0


def test_duration_seconds_never_negative():
    # Out-of-order records; duration is last - first which is still positive
    records = [
        {"type": "user", "timestamp": "2026-04-07T12:00:00Z", "message": {}},
        {"type": "user", "timestamp": "2026-04-07T10:00:00Z", "message": {}},
    ]
    assert compute_duration_seconds(records) == 7200


# ─── end-to-end render_session_markdown ──────────────────────────────────


def test_render_session_markdown_emits_v08_metrics(synthetic_records, tmp_path):
    from llmwiki.convert import Redactor, render_session_markdown

    redactor = Redactor({})
    jsonl = tmp_path / "abc123.jsonl"
    jsonl.touch()
    md, _slug, _started = render_session_markdown(
        synthetic_records,
        jsonl_path=jsonl,
        project_slug="test-project",
        redact=redactor,
        config={},
        is_subagent_file=False,
    )
    # All 5 new keys are in the frontmatter
    assert "tool_counts:" in md
    assert "token_totals:" in md
    assert "turn_count:" in md
    assert "hour_buckets:" in md
    assert "duration_seconds:" in md
    # Values are valid JSON that round-trips
    for line in md.splitlines():
        if line.startswith("tool_counts: "):
            assert json.loads(line[len("tool_counts: ") :]) == {"Read": 2, "Bash": 1}
        if line.startswith("token_totals: "):
            assert json.loads(line[len("token_totals: ") :]) == {
                "input": 300,
                "cache_creation": 50,
                "cache_read": 200,
                "output": 40,
            }
        if line.startswith("turn_count: "):
            assert line == "turn_count: 2"
        if line.startswith("duration_seconds: "):
            assert line == "duration_seconds: 3902"


def test_render_session_markdown_is_idempotent(synthetic_records, tmp_path):
    """Re-running the converter on an unchanged record set produces
    byte-identical output."""
    from llmwiki.convert import Redactor, render_session_markdown

    redactor = Redactor({})
    jsonl = tmp_path / "abc123.jsonl"
    jsonl.touch()
    md1, _, _ = render_session_markdown(
        synthetic_records, jsonl, "p", redactor, {}, False
    )
    md2, _, _ = render_session_markdown(
        synthetic_records, jsonl, "p", redactor, {}, False
    )
    assert md1 == md2


def test_render_session_markdown_keeps_legacy_fields(synthetic_records, tmp_path):
    """Adding new frontmatter keys must not remove the old ones."""
    from llmwiki.convert import Redactor, render_session_markdown

    redactor = Redactor({})
    jsonl = tmp_path / "abc123.jsonl"
    jsonl.touch()
    md, _, _ = render_session_markdown(
        synthetic_records, jsonl, "p", redactor, {}, False
    )
    for legacy in ("title:", "slug:", "project:", "started:", "ended:",
                   "model:", "user_messages:", "tool_calls:", "tools_used:"):
        assert legacy in md, f"lost legacy frontmatter key: {legacy}"
