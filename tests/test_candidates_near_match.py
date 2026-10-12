"""Unit tests for ``llmwiki.candidates_near_match`` pure match + attach (#326).

# @spec: 326-harvest-discard-reason-surface
"""

from __future__ import annotations

from pathlib import Path

import pytest

from llmwiki.candidates_near_match import (
    EMPTY_REASON_DISPLAY,
    LENGTH_DELTA,
    MIN_FOLDED_KEY_LENGTH,
    NEAR_MATCH_SIMILARITY,
    attach_prior_dismissals,
    format_dismissal_reason,
    near_match_dismissal,
)
from llmwiki.dismissal_ledger import upsert_dismissal
from llmwiki.topics import _DEFAULT_SIMILARITY as TOPICS_SIMILARITY
from llmwiki.wikilinks import norm_page_key


def _dismissal(
    name: str,
    *,
    reason: str = "noise",
    discarded_at: str = "2026-03-01T12:00:00+00:00",
    key: str | None = None,
) -> dict[str, str]:
    return {
        "key": key if key is not None else norm_page_key(name),
        "name": name,
        "reason": reason,
        "discarded_at": discarded_at,
        "stub": f"archive/{name}.md",
    }


def test_similarity_constant_aligns_with_topics() -> None:
    """Near-match threshold matches topics._DEFAULT_SIMILARITY (0.90)."""
    assert NEAR_MATCH_SIMILARITY == TOPICS_SIMILARITY == 0.90


def test_format_dismissal_reason_empty_uses_placeholder() -> None:
    """Blank or missing reason displays as (discarded without explanation)."""
    assert format_dismissal_reason("") == EMPTY_REASON_DISPLAY
    assert format_dismissal_reason("   ") == EMPTY_REASON_DISPLAY
    assert format_dismissal_reason(None) == EMPTY_REASON_DISPLAY
    assert format_dismissal_reason("hosting detail") == "hosting detail"


def test_exact_folded_key_is_not_a_near_match() -> None:
    """Same norm_page_key as a dismissal is excluded (exact settled identity)."""
    rows = [_dismissal("Foobar", reason="hosting detail, not subject matter")]
    assert near_match_dismissal("FooBar", rows) is None
    assert near_match_dismissal("foo-bar", rows) is None


def test_near_match_plural_variant() -> None:
    """A close spelling variant above 0.90 attaches the prior dismissal."""
    rows = [_dismissal("ApiClient", reason="library wrapper, not a topic")]
    prior = near_match_dismissal("ApiClients", rows)
    assert prior is not None
    assert prior["name"] == "ApiClient"
    assert prior["reason"] == "library wrapper, not a topic"
    assert prior["ratio"] >= NEAR_MATCH_SIMILARITY


def test_short_folded_keys_are_skipped() -> None:
    """Folded keys shorter than MIN_FOLDED_KEY_LENGTH never near-match."""
    assert MIN_FOLDED_KEY_LENGTH == 4
    # Both keys length 3 — would be high ratio but must skip.
    rows = [_dismissal("abc", key="abc")]
    assert near_match_dismissal("abd", rows) is None
    # Pending short, dismissal long enough.
    rows = [_dismissal("Abcde", key="abcde")]
    assert near_match_dismissal("ab", rows) is None


def test_length_prefilter_skips_large_relative_delta() -> None:
    """Relative length delta above LENGTH_DELTA skips SequenceMatcher."""
    assert LENGTH_DELTA == 0.25
    # "hostingdetail" (13) vs a much longer key — delta > 0.25.
    long_name = "HostingDetailExtraSuffixStuff"
    rows = [_dismissal("HostingDetail")]
    pending_key = norm_page_key(long_name)
    dismiss_key = norm_page_key("HostingDetail")
    rel = abs(len(pending_key) - len(dismiss_key)) / max(len(pending_key), len(dismiss_key))
    assert rel > LENGTH_DELTA
    assert near_match_dismissal(long_name, rows) is None


def test_below_threshold_is_not_a_match() -> None:
    """Pairs under 0.90 (e.g. Markdown vs Markitdown) stay unmarked."""
    rows = [_dismissal("Markdown")]
    assert near_match_dismissal("Markitdown", rows) is None


def test_best_match_highest_ratio_wins() -> None:
    """When several dismissals qualify, the highest SequenceMatcher ratio wins."""
    rows = [
        _dismissal("HostingDetail", reason="closer"),
        _dismissal("HostingDetailz", reason="farther"),
    ]
    prior = near_match_dismissal("HostingDetails", rows)
    assert prior is not None
    assert prior["name"] == "HostingDetail"
    assert prior["reason"] == "closer"


def test_best_match_tie_break_most_recent_discarded_at() -> None:
    """Equal ratios prefer the most recent discarded_at."""
    rows = [
        _dismissal(
            "Wikilink",
            reason="older",
            discarded_at="2026-01-01T00:00:00+00:00",
        ),
        _dismissal(
            "Wikilink",
            reason="newer",
            discarded_at="2026-06-01T00:00:00+00:00",
            key="wikilink",
        ),
    ]
    prior = near_match_dismissal("Wikilinks", rows)
    assert prior is not None
    assert prior["reason"] == "newer"


def test_best_match_tie_break_lexicographic_name() -> None:
    """Equal ratio and discarded_at prefer lexicographically greater name (max)."""
    ts = "2026-03-01T12:00:00+00:00"
    rows = [
        {
            "key": "foobarr",
            "name": "Alpha",
            "reason": "a",
            "discarded_at": ts,
            "stub": "a.md",
        },
        {
            "key": "foobarr",
            "name": "Beta",
            "reason": "b",
            "discarded_at": ts,
            "stub": "b.md",
        },
    ]
    prior = near_match_dismissal("FooBar", rows)
    assert prior is not None
    assert prior["name"] == "Beta"
    assert prior["reason"] == "b"


def test_attach_prior_dismissals_with_inline_records() -> None:
    """attach_prior_dismissals annotates matching candidates without vault I/O."""
    candidates = [
        {"slug": "ApiClients", "title": "ApiClients", "kind": "entities"},
        {"slug": "Unrelated", "title": "Unrelated", "kind": "entities"},
        {"slug": "FooBar", "title": "FooBar", "kind": "entities"},
    ]
    rows = [
        _dismissal("ApiClient", reason="wrapper"),
        _dismissal("Foobar", reason="exact-fold-should-not-mark"),
    ]
    out = attach_prior_dismissals(candidates, dismissals=rows)
    assert out[0].get("prior_dismissal") is not None
    assert out[0]["prior_dismissal"]["name"] == "ApiClient"
    assert "prior_dismissal" not in out[1]
    # FooBar / Foobar share folded key → not a near-match
    assert "prior_dismissal" not in out[2]


def test_attach_loads_via_iter_dismissals(tmp_path: Path) -> None:
    """When dismissals omitted, attach uses ledger iter_dismissals (not raw JSON)."""
    wiki = tmp_path / "wiki"
    (wiki / "archive" / "candidates").mkdir(parents=True)
    upsert_dismissal(
        wiki,
        name="ApiClient",
        reason="library wrapper",
        stub="2026-03-01/ApiClient.md",
        discarded_at="2026-03-01T12:00:00+00:00",
    )
    candidates = [{"slug": "ApiClients", "title": "ApiClients"}]
    out = attach_prior_dismissals(candidates, wiki)
    assert out[0]["prior_dismissal"]["reason"] == "library wrapper"
    assert out[0]["prior_dismissal"]["ratio"] >= NEAR_MATCH_SIMILARITY


def test_attach_requires_wiki_dir_without_records() -> None:
    """Omitting both wiki_dir and dismissals raises ValueError."""
    with pytest.raises(ValueError, match="wiki_dir"):
        attach_prior_dismissals([{"slug": "X", "title": "X"}])


def test_format_used_for_empty_reason_on_match() -> None:
    """Matched empty reason still returns raw empty; display helper fills placeholder."""
    rows = [_dismissal("ApiClient", reason="")]
    prior = near_match_dismissal("ApiClients", rows)
    assert prior is not None
    assert prior["reason"] == ""
    assert format_dismissal_reason(prior["reason"]) == EMPTY_REASON_DISPLAY
