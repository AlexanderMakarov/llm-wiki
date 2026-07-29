"""Tests for the shared tag utility module (post-v1.0 audit cleanup)."""

from __future__ import annotations

from llmwiki.categories import scan_tags as cat_scan_tags
from llmwiki.tag_utils import NOISE_TAGS, parse_tags_field, scan_tags

# ─── NOISE_TAGS ──────────────────────────────────────────────────────


def test_noise_tags_contains_expected_values():
    assert "claude-code" in NOISE_TAGS
    assert "session-transcript" in NOISE_TAGS
    assert "demo" in NOISE_TAGS
    assert "" in NOISE_TAGS


def test_noise_tags_is_set_not_list():
    assert isinstance(NOISE_TAGS, set)


# ─── parse_tags_field ────────────────────────────────────────────────


def test_parse_yaml_list_form():
    assert parse_tags_field("[flutter, python]") == ["flutter", "python"]


def test_parse_comma_list_without_brackets():
    assert parse_tags_field("flutter, python") == ["flutter", "python"]


def test_parse_filters_noise():
    assert parse_tags_field("[claude-code, flutter]") == ["flutter"]
    assert parse_tags_field("[session-transcript, demo, real-tag]") == ["real-tag"]


def test_parse_empty_string():
    assert parse_tags_field("") == []


def test_parse_none():
    assert parse_tags_field(None) == []


def test_parse_empty_list_brackets():
    assert parse_tags_field("[]") == []


def test_parse_lowercases():
    assert parse_tags_field("[Flutter, PYTHON, Rust]") == ["flutter", "python", "rust"]


def test_parse_strips_whitespace():
    assert parse_tags_field("[ flutter ,  mobile ]") == ["flutter", "mobile"]


def test_parse_strips_quotes():
    assert parse_tags_field('["flutter", "python"]') == ["flutter", "python"]
    assert parse_tags_field("['a', 'b']") == ["a", "b"]


def test_parse_accepts_non_string():
    """parse_tags_field should coerce non-str inputs via str()."""
    # Int should not crash — just produce empty after processing
    result = parse_tags_field(42)
    assert isinstance(result, list)


# ─── scan_tags ────────────────────────────────────────────────────────


def _mk(meta: dict) -> dict:
    return {"meta": meta}


def test_scan_basic():
    pages = {
        "a.md": _mk({"tags": "[flutter]"}),
        "b.md": _mk({"tags": "[flutter, python]"}),
        "c.md": _mk({"tags": "[python]"}),
    }
    tags = scan_tags(pages)
    assert sorted(tags["flutter"]) == ["a.md", "b.md"]
    assert sorted(tags["python"]) == ["b.md", "c.md"]


def test_scan_empty_pages():
    assert scan_tags({}) == {}


def test_scan_no_tags_field():
    assert scan_tags({"a.md": _mk({})}) == {}


def test_scan_deterministic():
    """Same input → same output (sorted page lists)."""
    pages = {
        "c.md": _mk({"tags": "[tag1]"}),
        "a.md": _mk({"tags": "[tag1]"}),
        "b.md": _mk({"tags": "[tag1]"}),
    }
    tags = scan_tags(pages)
    assert tags["tag1"] == ["a.md", "b.md", "c.md"]


def test_scan_filters_noise_from_each_page():
    pages = {
        "a.md": _mk({"tags": "[claude-code, real-tag]"}),
    }
    tags = scan_tags(pages)
    assert "claude-code" not in tags
    assert "real-tag" in tags


# ─── Consumers import scan_tags from the owning module ───────────────


def test_categories_module_still_exposes_scan_tags():
    """categories.py re-uses tag_utils.scan_tags for category generation."""
    assert cat_scan_tags is scan_tags
