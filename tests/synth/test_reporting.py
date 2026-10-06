"""Unit tests for ``llmwiki.synth.reporting`` CLI presentation helpers.

# @layer: unit
# @spec: 280-shrink-test-suite
# @regression
"""

from __future__ import annotations

import pytest

from llmwiki.synth.reporting import (
    print_candidates_pre_run,
    print_source_pages_current_state,
    print_synth_run_start,
    print_synth_run_summary,
)


def test_print_candidates_pre_run_empty_unresolved_links(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Zero unresolved wikilinks must print the empty pre-run Candidates block and pending-sources note."""
    print_candidates_pre_run(
        {
            "candidates": 0,
            "min_refs": 1,
            "broken_links": 0,
            "broken_targets": 0,
            "covered_links": 0,
            "distribution": {},
        }
    )
    out = capsys.readouterr().out
    assert (
        "Candidates (pre-run state): 0  "
        "(no unresolved wikilinks in wiki/sources/)"
    ) in out
    assert out.strip().endswith(
        "note: pending sources are not yet reflected in this figure"
    )
    assert "generate with:" not in out


def test_print_candidates_pre_run_reports_coverage_and_harvest_hint(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A non-empty backlog must print stub count, close-percentage, min-refs shape, and the harvest command."""
    print_candidates_pre_run(
        {
            "candidates": 3,
            "min_refs": 2,
            "broken_links": 4,
            "broken_targets": 2,
            "covered_links": 3,
            "distribution": {1: 1, 2: 2},
        }
    )
    out = capsys.readouterr().out
    assert "Candidates (pre-run state): 3 stub(s) at --min-refs 2" in out
    assert "closes 75% of 4 broken link(s) over 2 target(s)" in out
    assert "by --min-refs:   1:1  2:2" in out
    assert "  generate with:   llmwiki synth --candidates-only\n" in out
    assert "note: pending sources are not yet reflected in this figure" in out


def test_print_source_pages_current_state_omits_other_when_zero(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """On-disk source counts must list sessions/docs/stubs and omit a zero 'other' bucket."""
    print_source_pages_current_state(pages_on_disk=0)
    default_out = capsys.readouterr().out
    assert default_out.strip() == (
        "Source pages (current state): 0 on disk (0 sessions + 0 docs + 0 stubs)"
    )

    print_source_pages_current_state(
        pages_on_disk=10, sessions=4, docs=5, stubs=1, other=0
    )
    out = capsys.readouterr().out
    assert out.strip() == "Source pages (current state): 10 on disk (4 sessions + 5 docs + 1 stubs)"
    assert "other" not in out


def test_print_source_pages_current_state_includes_other_when_positive(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A positive 'other' count must appear in the current-state mix."""
    print_source_pages_current_state(
        pages_on_disk=11, sessions=4, docs=5, stubs=1, other=1
    )
    out = capsys.readouterr().out
    assert "11 on disk (4 sessions + 5 docs + 1 stubs + 1 other)" in out


def test_print_synth_run_start_empty_backlog_is_plain(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A zero or negative backlog must say nothing is left to synthesize."""
    print_synth_run_start(total=0, backend_name="dummy")
    assert capsys.readouterr().out.strip() == (
        "Nothing to synthesize — every source is already up to date."
    )


def test_print_synth_run_start_announces_backend_and_optional_concurrency(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A positive backlog must name the backend and, when set, how many pages run at once."""
    print_synth_run_start(total=3, backend_name="claude-cli", concurrency=2)
    assert capsys.readouterr().out.strip() == (
        "Synthesizing 3 source(s) with claude-cli (2 at a time)"
    )
    print_synth_run_start(total=1, backend_name="dummy")
    assert capsys.readouterr().out.strip() == "Synthesizing 1 source(s) with dummy"


def test_print_synth_run_summary_always_prints_count_and_duration(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Successful-run summary must print Synthesized and Duration even when usage is unknown."""
    print_synth_run_summary(synthesized=5, duration_s=42.0)
    out = capsys.readouterr().out
    assert "Synthesized: 5" in out
    assert "Duration: 42.0s" in out
    assert "Tokens:" not in out
    assert "Cost:" not in out
    assert "Candidates" not in out


def test_print_synth_run_summary_prints_known_tokens_and_cost(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Known token and dollar figures must appear; they must not be invented when omitted."""
    print_synth_run_summary(
        synthesized=2, duration_s=1.25, tokens=1500, cost_usd=0.0123
    )
    out = capsys.readouterr().out
    assert "Tokens: 1,500" in out
    assert "Cost: $0.0123" in out
