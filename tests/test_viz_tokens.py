"""Tests for `llmwiki.viz_tokens` — token usage visualizations (v0.8 · #66)."""

from __future__ import annotations

import re

import pytest

from llmwiki.format_numbers import format_tokens
from llmwiki.render.css import CSS
from llmwiki.render.js import JS
from llmwiki.viz_tokens import (
    TOKEN_COVERAGE_LINES,
    _hit_ratio_tier,
    cache_hit_ratio,
    compute_site_stats,
    parse_token_totals,
    render_project_token_card,
    render_project_token_timeline,
    render_session_token_card,
    render_site_token_stat_grid,
    render_site_token_stats,
    render_token_coverage_hint,
)

# ─── format_tokens: K/M/B suffixes ───────────────────────────────────────


@pytest.mark.parametrize(
    "n,expected",
    [
        (0, "0"),
        (1, "1"),
        (999, "999"),
        (1000, "1.0K"),
        (1234, "1.2K"),
        (12_345, "12.3K"),
        (999_999, "1000.0K"),  # rounds to K
        (1_000_000, "1.0M"),
        (1_234_567, "1.2M"),
        (1_234_567_890, "1.2B"),
    ],
)
def test_format_tokens(n, expected):
    assert format_tokens(n) == expected


# ─── parse_token_totals handles every frontmatter shape ─────────────────


def test_parse_token_totals_from_json_string():
    meta = {"token_totals": '{"input": 100, "cache_read": 500}'}
    assert parse_token_totals(meta) == {"input": 100, "cache_read": 500}


def test_parse_token_totals_from_dict():
    meta = {"token_totals": {"input": 1, "output": 2}}
    assert parse_token_totals(meta) == {"input": 1, "output": 2}


def test_parse_token_totals_empty_returns_empty():
    for v in (None, "", "{}", {}):
        assert parse_token_totals({"token_totals": v}) == {}


def test_parse_token_totals_missing_returns_empty():
    assert parse_token_totals({}) == {}


def test_parse_token_totals_malformed_json_returns_empty():
    assert parse_token_totals({"token_totals": "{bad json"}) == {}


# ─── cache_hit_ratio ─────────────────────────────────────────────────────


def test_cache_hit_ratio_healthy():
    totals = {"input": 100, "cache_creation": 200, "cache_read": 1700}
    r = cache_hit_ratio(totals)
    assert r is not None
    assert abs(r - 0.85) < 0.01


def test_cache_hit_ratio_zero_input_returns_none():
    assert cache_hit_ratio({"input": 0, "cache_creation": 0, "cache_read": 0}) is None


def test_cache_hit_ratio_no_cache_read_is_zero():
    r = cache_hit_ratio({"input": 1000, "cache_creation": 0, "cache_read": 0})
    assert r == 0.0


def test_cache_hit_ratio_ignores_output():
    """Output tokens should NOT be in the denominator — they're generation,
    not context. Including them would artificially deflate the ratio."""
    with_output = {"input": 100, "cache_read": 900, "output": 10_000}
    without_output = {"input": 100, "cache_read": 900}
    assert cache_hit_ratio(with_output) == cache_hit_ratio(without_output)


# ─── _hit_ratio_tier tiers ───────────────────────────────────────────────


@pytest.mark.parametrize(
    "ratio,tier",
    [
        (None, "tier-unknown"),
        (0.0, "tier-red"),
        (0.49, "tier-red"),
        (0.50, "tier-yellow"),
        (0.79, "tier-yellow"),
        (0.80, "tier-green"),
        (0.99, "tier-green"),
        (1.00, "tier-green"),
    ],
)
def test_hit_ratio_tier(ratio, tier):
    assert _hit_ratio_tier(ratio)[0] == tier


# ─── render_session_token_card ───────────────────────────────────────────


def test_session_card_empty_returns_empty():
    assert render_session_token_card({}) == ""
    assert render_session_token_card({"token_totals": "{}"}) == ""


def test_session_card_renders_all_four_rows_when_present():
    meta = {
        "token_totals": '{"input": 10000, "cache_creation": 20000, "cache_read": 1000000, "output": 5000}'
    }
    card = render_session_token_card(meta)
    for label in ("Input", "Cache creation", "Cache read", "Output"):
        assert label in card
    # Formatted numbers
    assert "10.0K" in card
    assert "20.0K" in card
    assert "1.0M" in card
    assert "5.0K" in card


def test_session_card_shows_cache_hit_ratio_with_tier_class():
    meta = {
        "token_totals": '{"input": 100, "cache_creation": 200, "cache_read": 1700, "output": 0}'
    }
    card = render_session_token_card(meta)
    assert "Cache hit ratio" in card
    assert "85%" in card
    assert "tier-green" in card
    assert "healthy" in card


def test_session_card_shows_total_in_header():
    meta = {
        "token_totals": '{"input": 100, "cache_creation": 100, "cache_read": 100, "output": 100}'
    }
    card = render_session_token_card(meta)
    assert "400 total" in card


def test_session_card_bar_widths_scale_to_max():
    """The largest category sets the 100% mark; smaller ones scale down.
    Zero-count categories (cache_creation, output here) render as 0%."""
    meta = {
        "token_totals": '{"input": 100, "cache_read": 1000, "cache_creation": 0, "output": 0}'
    }
    card = render_session_token_card(meta)
    widths = re.findall(r'width: (\d+(?:\.\d+)?)%', card)
    widths_f = sorted(float(w) for w in widths)
    # Four rows: [0, 0, 10, 100]
    assert widths_f[-1] == 100.0  # cache_read
    # Smallest non-zero width must be ~10% (input is 10% of 1000)
    nonzero = [w for w in widths_f if w > 0]
    assert 9 <= min(nonzero) <= 11
    # cache_creation and output are 0 → 0.0%
    assert widths_f.count(0.0) == 2


def test_session_card_uses_category_classes_per_row():
    meta = {
        "token_totals": '{"input": 10, "cache_creation": 20, "cache_read": 30, "output": 40}'
    }
    card = render_session_token_card(meta)
    for cat in ("input", "cache_creation", "cache_read", "output"):
        assert f"token-bar-{cat}" in card


# ─── render_project_token_timeline ──────────────────────────────────────


def test_project_timeline_empty_returns_empty():
    assert render_project_token_timeline([], "foo") == ""


def test_project_timeline_single_session_still_renders():
    metas = [{"date": "2026-04-07", "token_totals": '{"input": 100, "cache_read": 1000}'}]
    svg = render_project_token_timeline(metas, "demo")
    assert svg.startswith("<svg")
    assert "role=\"img\"" in svg
    assert "demo token usage timeline" in svg


def test_project_timeline_has_axis_lines_and_path():
    metas = [
        {"date": "2026-04-01", "token_totals": '{"input": 100, "cache_read": 5000}'},
        {"date": "2026-04-07", "token_totals": '{"input": 200, "cache_read": 50000}'},
    ]
    svg = render_project_token_timeline(metas, "demo")
    assert '<line class="axis"' in svg
    assert '<path class="area"' in svg
    # Y-axis labels should be formatted token numbers
    assert ">5.1K<" in svg or ">5.0K<" in svg
    # X-axis labels should be YYYY-MM
    assert ">2026-04<" in svg


def test_project_timeline_skips_sessions_without_tokens():
    """Sessions missing `token_totals` are silently dropped, not plotted."""
    metas = [
        {"date": "2026-04-01", "token_totals": "{}"},
        {"date": "2026-04-07", "token_totals": '{"input": 100, "cache_read": 200}'},
    ]
    svg = render_project_token_timeline(metas, "demo")
    assert svg != ""


# ─── render_project_token_card ──────────────────────────────────────────


def test_project_card_has_header_with_total_and_ratio():
    metas = [
        {"date": "2026-04-01", "token_totals": '{"input": 100, "cache_creation": 200, "cache_read": 1700, "output": 5000}'}
    ]
    card = render_project_token_card(metas, "demo")
    assert "Token usage · timeline" in card
    assert "7.0K total" in card
    assert "85%" in card
    assert "tier-green" in card


def test_project_card_empty_returns_empty():
    assert render_project_token_card([], "demo") == ""


# ─── compute_site_stats ─────────────────────────────────────────────────


def test_compute_site_stats_zero_input():
    assert compute_site_stats({})["session_count"] == 0


def test_compute_site_stats_finds_best_ratio_and_heaviest():
    by_project = {
        "alpha": [
            {"token_totals": '{"input": 100, "cache_read": 900, "output": 10}'},
            {"token_totals": '{"input": 100, "cache_read": 900, "output": 10}'},
        ],
        "beta": [
            {"token_totals": '{"input": 1000, "cache_read": 10, "output": 10000}'},
        ],
    }
    stats = compute_site_stats(by_project)
    assert stats["session_count"] == 3
    assert stats["total_tokens"] == (1010 + 1010 + 11010)
    # alpha has ~90% hit ratio, beta has ~1%
    assert stats["best_ratio_project"][0] == "alpha"
    assert stats["best_ratio_project"][1] > 0.85
    # beta has the most total tokens (12010 > 2020)
    assert stats["heaviest_project"][0] == "beta"


def test_compute_site_stats_ignores_empty_sessions():
    by_project = {"alpha": [{"token_totals": "{}"}, {"token_totals": None}]}
    stats = compute_site_stats(by_project)
    assert stats["session_count"] == 0
    assert stats["heaviest_project"] is None
    assert stats["best_ratio_project"] is None


# ─── render_site_token_stats ────────────────────────────────────────────


def test_site_stats_block_returns_empty_when_no_data():
    assert render_site_token_stats({}) == ""


def test_site_stats_block_renders_three_cards():
    # #27 / #223: Tokens card shows avg with explicit token-data divisor, plus Best cache hit
    # and Heaviest project (by tokens); note clarifies billed throughput vs context occupancy.
    by_project = {
        "alpha": [{"token_totals": '{"input": 100, "cache_read": 900}'}],
        "beta": [{"token_totals": '{"input": 500, "cache_read": 10, "output": 2000}'}],
    }
    block = render_site_token_stats(by_project)
    assert "Tokens" in block
    assert "by 2/2 sessions (" in block
    assert "/s)" in block
    assert "Cumulative billed throughput" in block
    assert "not context-window occupancy" in block
    assert "Best cache hit" in block
    assert "Heaviest project (by tokens)" in block
    assert 'href="projects/alpha.html"' in block
    assert 'href="projects/beta.html"' in block


def test_site_stats_labels_token_bearing_divisor_count():
    """#223: avg divisor stays token-bearing sessions; sub-label must surface N.

    Hero session count can exceed sessions with ≥1 non-zero token category.
    Old unlabeled ``/ session avg`` hid that narrower population; Option 2 keeps
    the divisor but labels it, plus a billed-throughput clarification note.
    """
    # 7 sessions total; only 4 have non-zero token categories (40.0K → 10.0K avg).
    by_project = {
        "alpha": [
            {"token_totals": '{"input": 5000, "output": 5000}'},  # 10K
            {"token_totals": '{"input": 10000}'},  # 10K
            {"token_totals": "{}"},  # no data
            {},  # missing token_totals
        ],
        "beta": [
            {"token_totals": '{"input": 0, "output": 0, "cache_read": 0}'},  # all-zero
            {"token_totals": '{"cache_read": 10000}'},  # 10K
            {"token_totals": '{"input": 5000, "cache_creation": 5000}'},  # 10K
        ],
    }
    block = render_site_token_stats(by_project)
    assert "40.0K" in block
    # 7 session metas; 4 with token data → by 4/7 sessions (10.0K/s)
    assert "by 4/7 sessions (10.0K/s)" in block
    assert "with token data" not in block
    assert "/ session avg" not in block
    assert "Cumulative billed throughput" in block
    assert "not context-window occupancy" in block


def test_site_stats_block_respects_link_prefix():
    by_project = {
        "alpha": [{"token_totals": '{"input": 100, "cache_read": 900}'}],
    }
    block = render_site_token_stats(by_project, link_prefix="../")
    assert 'href="../projects/alpha.html"' in block


def test_site_stats_block_appends_extra_cards_in_same_row():
    by_project = {
        "alpha": [{"token_totals": '{"input": 100, "cache_read": 900}'}],
    }
    extra = '<a class="token-stat"><div class="token-stat-label muted">Heaviest project by MCP usage</div></a>'
    block = render_site_token_stats(by_project, extra_cards=extra)
    # single grid row: Tokens card and the extra MCP card share one token-stat-grid
    assert block.count("token-stat-grid") == 1
    assert "Tokens" in block and "Heaviest project by MCP usage" in block


def test_site_stats_block_renders_extra_cards_even_without_token_data():
    extra = '<a class="token-stat"><div class="token-stat-label muted">Heaviest project by MCP usage</div></a>'
    block = render_site_token_stats({}, extra_cards=extra)
    assert "Heaviest project by MCP usage" in block
    assert "Tokens" not in block          # no token cards when there are no sessions


def test_site_token_stat_grid_usage_store_wires_floating_hint():
    """#321 / #323: usage-backed grid uses the shared floating hint trigger."""
    metas = {"p": [{}]}
    usage_file = {"totals": {"sum": 500}, "by_agent": {"Claude": {"measured": 1, "known": 1}}}
    grid, _ = render_site_token_stat_grid(metas, session_tokens_usage=usage_file)
    assert "llmwiki-hint-trigger" in grid


# ─── #323: Tokens coverage hint ─────────────────────────────────────────
# @spec: 323-total-tokens-coverage-hint
# @regression: #323 — site-wide Tokens headline must disclose which agents feed it


def test_token_coverage_lines_name_each_agent_group_and_missing_is_not_zero():
    """#323 / #324 / #396: disclosure names each agent group including Cursor IDE ledger."""
    text = " ".join(TOKEN_COVERAGE_LINES)
    for phrase in (
        "input, output, cache creation, and cache read",
        "Claude Code",
        "OpenClaw and OpenCode",
        "compatible usage fields",
        "Cursor CLI",
        "Codex CLI: included when usage fields are present",
        "Cursor IDE: included when Composer bubble tokenCount",
        "Gemini CLI",
        "Copilot CLI / Chat",
        "not evidence of zero tokens",
        "recorded-usage total, not a complete all-agent total",
    ):
        assert phrase in text, phrase
    # #324: Codex is no longer lumped with Cursor IDE as "not captured".
    assert "Codex CLI and Cursor IDE" not in text


def test_token_coverage_hint_is_accessible_button_wired_to_tooltip():
    """#321: hint is a button targeting the global floating panel."""
    out = render_token_coverage_hint("token-coverage-site")
    assert "llmwiki-hint-trigger" in out
    assert 'aria-expanded="false"' in out
    assert 'aria-label="What do Tokens cover?' in out
    assert 'aria-describedby="llmwiki-floating-hint-panel"' in out
    assert 'data-hint-key="metric-tokens-coverage"' in out
    assert "data-hint-html" in out
    assert out.count("&lt;span class=&quot;token-coverage-line&quot;&gt;") == len(TOKEN_COVERAGE_LINES)


def test_token_coverage_hint_ids_are_unique_per_hint_id():
    """#321: token coverage uses one registry key; dynamic body lives in data-hint-html."""
    a = render_token_coverage_hint("alpha")
    b = render_token_coverage_hint("beta")
    assert 'data-hint-key="metric-tokens-coverage"' in a
    assert 'data-hint-key="metric-tokens-coverage"' in b
    assert "data-hint-html" in a


@pytest.mark.parametrize(
    "raw,expected",
    [
        ('x" onclick="alert(1)', "x--onclick--alert-1"),
        ("<script>", "script"),
        ("", "token-coverage"),
        ("!!!", "token-coverage"),
    ],
)
def test_token_coverage_hint_sanitizes_unsafe_ids(raw, expected):
    """#321: hint output is a button + data-hint-html; no inline onclick injection."""
    _ = expected
    out = render_token_coverage_hint(raw)
    assert "llmwiki-hint-trigger" in out
    assert '" onclick=' not in out
    assert "<script" not in out


def test_site_stats_tokens_label_contains_coverage_hint_and_keeps_counting():
    """#323: the Tokens label carries the hint while total / avg / token-data counts are unchanged."""
    by_project = {
        "alpha": [{"token_totals": '{"input": 100, "cache_read": 900}'}],
        "beta": [{"token_totals": '{"output": 3000}'}, {"token_totals": "{}"}],
    }
    block = render_site_token_stats(by_project)
    label = re.search(
        r'<div class="token-stat-label muted">Tokens(.*?)</div><div class="token-stat-value">',
        block,
        re.S,
    )
    assert label, "Tokens label not found"
    assert 'class="llmwiki-hint-trigger"' in label.group(1) or "llmwiki-hint-trigger" in label.group(1)
    assert 'data-hint-key="metric-tokens-coverage"' in label.group(1)
    assert "token-coverage-site-panel" not in block
    assert '<div class="token-stat-value">4.0K</div>' in block
    # 3 metas, 2 with token data → avg 2.0K/s
    assert "by 2/3 sessions (2.0K/s)" in block


def test_site_stats_without_token_data_renders_no_coverage_hint():
    """#323: no Tokens headline means no orphan coverage hint."""
    block = render_site_token_stats({"alpha": [{"token_totals": "{}"}]})
    assert "token-coverage" not in block


def test_token_coverage_css_reveals_on_hover_focus_and_aria_expanded():
    """#321: floating hint panel is positioned fixed with sentence case."""
    assert ".llmwiki-floating-hint-panel" in CSS
    assert "text-transform: none" in CSS


def test_token_coverage_js_toggles_dismisses_and_clamps():
    """#321: global floating hints wire click, Escape, and viewport clamping."""
    assert "wireGlobalFloatingHints" in JS
    assert "hintBodyFor" in JS
    assert 'e.key === "Escape"' in JS
    assert "getBoundingClientRect" in JS
