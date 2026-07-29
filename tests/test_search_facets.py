"""Tests for enhanced search facets (v1.0, #161)."""

from __future__ import annotations

from llmwiki.search_facets import (
    _parse_confidence,
    _parse_tags_field,
    aggregate_facets,
    enrich_entry,
    filter_entries,
    rank_by_confidence,
)

# ─── _parse_tags_field ──────────────────────────────────────────────


def test_parse_tags_simple():
    assert _parse_tags_field("[flutter, python]") == ["flutter", "python"]


def test_parse_tags_filters_noise():
    assert _parse_tags_field("[claude-code, flutter]") == ["flutter"]


def test_parse_tags_empty():
    assert _parse_tags_field("") == []
    assert _parse_tags_field("[]") == []


def test_parse_tags_lowercase():
    assert _parse_tags_field("[Flutter, PYTHON]") == ["flutter", "python"]


def test_parse_tags_handles_none():
    assert _parse_tags_field(None) == []


# ─── _parse_confidence ──────────────────────────────────────────────


def test_parse_confidence_valid():
    assert _parse_confidence("0.75") == 0.75


def test_parse_confidence_empty():
    assert _parse_confidence("") == 0.0
    assert _parse_confidence(None) == 0.0


def test_parse_confidence_clamps():
    assert _parse_confidence("1.5") == 1.0
    assert _parse_confidence("-0.5") == 0.0


def test_parse_confidence_invalid():
    assert _parse_confidence("high") == 0.0


# ─── enrich_entry ────────────────────────────────────────────────────


def test_enrich_entry_adds_all_facet_fields():
    entry = {"id": "x", "title": "Test"}
    meta = {
        "confidence": "0.8",
        "lifecycle": "verified",
        "entity_type": "tool",
        "tags": "[flutter, mobile]",
    }
    result = enrich_entry(entry, meta)
    assert result["confidence"] == 0.8
    assert result["lifecycle"] == "verified"
    assert result["entity_type"] == "tool"
    assert result["tags"] == ["flutter", "mobile"]


def test_enrich_entry_defaults_when_meta_empty():
    entry = {"id": "x"}
    enrich_entry(entry, {})
    assert entry["confidence"] == 0.0
    assert entry["lifecycle"] == ""
    assert entry["entity_type"] == ""
    assert entry["tags"] == []


def test_enrich_entry_lowercases_lifecycle():
    entry = {"id": "x"}
    enrich_entry(entry, {"lifecycle": "VERIFIED"})
    assert entry["lifecycle"] == "verified"


# ─── aggregate_facets ────────────────────────────────────────────────


def test_aggregate_entity_types():
    entries = [
        {"entity_type": "tool"},
        {"entity_type": "tool"},
        {"entity_type": "concept"},
    ]
    result = aggregate_facets(entries)
    assert result["entity_type"]["tool"] == 2
    assert result["entity_type"]["concept"] == 1


def test_aggregate_lifecycles():
    entries = [
        {"lifecycle": "draft"},
        {"lifecycle": "verified"},
        {"lifecycle": "draft"},
    ]
    result = aggregate_facets(entries)
    assert result["lifecycle"]["draft"] == 2
    assert result["lifecycle"]["verified"] == 1


def test_aggregate_tags():
    entries = [
        {"tags": ["flutter", "mobile"]},
        {"tags": ["flutter", "ios"]},
    ]
    result = aggregate_facets(entries)
    assert result["tags"]["flutter"] == 2
    assert result["tags"]["mobile"] == 1
    assert result["tags"]["ios"] == 1


def test_aggregate_confidence_buckets():
    entries = [
        {"confidence": 0.9},
        {"confidence": 0.6},
        {"confidence": 0.3},
        {"confidence": 0.0},
    ]
    result = aggregate_facets(entries)
    assert result["confidence"]["high"] == 1
    assert result["confidence"]["medium"] == 1
    assert result["confidence"]["low"] == 1
    assert result["confidence"]["none"] == 1


def test_aggregate_empty():
    result = aggregate_facets([])
    assert result["entity_type"] == {}
    assert result["lifecycle"] == {}
    assert result["tags"] == {}
    assert result["confidence"] == {}


def test_aggregate_skips_empty_fields():
    entries = [{"entity_type": ""}]
    result = aggregate_facets(entries)
    assert result["entity_type"] == {}


# ─── rank_by_confidence ──────────────────────────────────────────────


def test_rank_no_query_sorts_by_confidence():
    entries = [
        {"title": "low", "confidence": 0.2},
        {"title": "high", "confidence": 0.9},
        {"title": "mid", "confidence": 0.5},
    ]
    ranked = rank_by_confidence(entries)
    assert [e["title"] for e in ranked] == ["high", "mid", "low"]


def test_rank_with_query_matches_title():
    entries = [
        {"title": "Flutter doc", "body": "", "tags": [], "confidence": 0.1},
        {"title": "Random", "body": "", "tags": [], "confidence": 0.9},
    ]
    ranked = rank_by_confidence(entries, query="flutter")
    # Even though confidence is low, title match wins
    assert ranked[0]["title"] == "Flutter doc"


def test_rank_confidence_tiebreaker():
    entries = [
        {"title": "X", "body": "", "tags": [], "confidence": 0.9},
        {"title": "Y", "body": "", "tags": [], "confidence": 0.3},
    ]
    # No query → pure confidence
    ranked = rank_by_confidence(entries)
    assert ranked[0]["title"] == "X"


def test_rank_empty_list():
    assert rank_by_confidence([]) == []


# ─── filter_entries ──────────────────────────────────────────────────


def test_filter_by_entity_type():
    entries = [
        {"entity_type": "tool"},
        {"entity_type": "concept"},
    ]
    result = filter_entries(entries, entity_types=["tool"])
    assert len(result) == 1
    assert result[0]["entity_type"] == "tool"


def test_filter_by_lifecycle():
    entries = [
        {"lifecycle": "draft"},
        {"lifecycle": "verified"},
    ]
    result = filter_entries(entries, lifecycles=["verified"])
    assert len(result) == 1


def test_filter_by_tags_any_match():
    entries = [
        {"tags": ["flutter"]},
        {"tags": ["python"]},
        {"tags": ["flutter", "mobile"]},
    ]
    result = filter_entries(entries, tags=["flutter"])
    assert len(result) == 2


def test_filter_by_confidence_range():
    entries = [
        {"confidence": 0.9},
        {"confidence": 0.5},
        {"confidence": 0.1},
    ]
    result = filter_entries(entries, min_confidence=0.4, max_confidence=0.8)
    assert len(result) == 1
    assert result[0]["confidence"] == 0.5


def test_filter_combines_all():
    entries = [
        {"entity_type": "tool", "lifecycle": "verified",
         "tags": ["flutter"], "confidence": 0.9},
        {"entity_type": "tool", "lifecycle": "draft",
         "tags": ["flutter"], "confidence": 0.9},
    ]
    result = filter_entries(
        entries,
        entity_types=["tool"],
        lifecycles=["verified"],
        tags=["flutter"],
        min_confidence=0.5,
    )
    assert len(result) == 1


def test_filter_no_criteria_returns_all():
    entries = [{"x": 1}, {"x": 2}]
    result = filter_entries(entries)
    assert len(result) == 2
