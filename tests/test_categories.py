"""Tests for category page generation (v1.0, #154)."""

from __future__ import annotations

from pathlib import Path

from llmwiki.categories import (
    dataview_page,
    generate_dataview_categories,
    generate_static_categories,
    scan_tags,
    static_page,
)
from llmwiki.tag_utils import NOISE_TAGS
from llmwiki.tag_utils import parse_tags_field as _parse_tags


def _mk_page(meta: dict) -> dict:
    return {"path": Path("x"), "rel": "x.md", "text": "", "meta": meta, "body": ""}


# ─── _parse_tags ─────────────────────────────────────────────────────


def test_parse_tags_simple():
    assert _parse_tags("[flutter, mobile]") == ["flutter", "mobile"]


def test_parse_tags_no_brackets():
    assert _parse_tags("flutter, mobile") == ["flutter", "mobile"]


def test_parse_tags_quoted():
    assert _parse_tags('["foo", "bar"]') == ["foo", "bar"]


def test_parse_tags_lowercase():
    assert _parse_tags("[Flutter, MOBILE]") == ["flutter", "mobile"]


def test_parse_tags_filters_noise():
    assert _parse_tags("[claude-code, flutter]") == ["flutter"]
    assert _parse_tags("[session-transcript, demo, real-tag]") == ["real-tag"]


def test_parse_tags_empty():
    assert _parse_tags("") == []
    assert _parse_tags("[]") == []


def test_parse_tags_handles_whitespace():
    assert _parse_tags("[ flutter ,  mobile ]") == ["flutter", "mobile"]


# ─── scan_tags ───────────────────────────────────────────────────────


def test_scan_tags_basic():
    pages = {
        "a.md": _mk_page({"tags": "[flutter]"}),
        "b.md": _mk_page({"tags": "[flutter, python]"}),
        "c.md": _mk_page({"tags": "[python]"}),
    }
    tags = scan_tags(pages)
    assert sorted(tags["flutter"]) == ["a.md", "b.md"]
    assert sorted(tags["python"]) == ["b.md", "c.md"]


def test_scan_tags_filters_noise():
    pages = {"a.md": _mk_page({"tags": "[claude-code, flutter]"})}
    tags = scan_tags(pages)
    assert "claude-code" not in tags
    assert "flutter" in tags


def test_scan_tags_empty_pages():
    assert scan_tags({}) == {}


def test_scan_tags_no_tags_field():
    pages = {"a.md": _mk_page({})}
    tags = scan_tags(pages)
    assert tags == {}


def test_scan_tags_deterministic_order():
    """Same input should produce same output."""
    pages = {
        "a.md": _mk_page({"tags": "[tag1]"}),
        "b.md": _mk_page({"tags": "[tag1]"}),
        "c.md": _mk_page({"tags": "[tag1]"}),
    }
    tags1 = scan_tags(pages)
    tags2 = scan_tags(pages)
    assert tags1 == tags2
    # Lists are sorted
    assert tags1["tag1"] == sorted(tags1["tag1"])


# ─── dataview_page ──────────────────────────────────────────────────


def test_dataview_page_has_frontmatter():
    text = dataview_page("flutter")
    assert text.startswith("---\n")
    assert "type: navigation" in text
    assert "tag: flutter" in text


def test_dataview_page_has_query():
    text = dataview_page("flutter")
    assert "```dataview" in text
    assert 'contains(tags, "flutter")' in text


def test_dataview_page_has_connections():
    text = dataview_page("flutter")
    assert "## Connections" in text


# ─── static_page ────────────────────────────────────────────────────


def test_static_page_groups_by_folder():
    pages = {
        "entities/Foo.md": _mk_page({"title": "Foo"}),
        "concepts/Bar.md": _mk_page({"title": "Bar"}),
        "entities/Baz.md": _mk_page({"title": "Baz"}),
    }
    page_rels = ["entities/Foo.md", "concepts/Bar.md", "entities/Baz.md"]
    text = static_page("mytag", page_rels, pages)
    assert "## entities" in text
    assert "## concepts" in text


def test_static_page_lists_count():
    pages = {"a.md": _mk_page({"title": "A"})}
    text = static_page("mytag", ["a.md"], pages)
    assert "1 pages tagged with `mytag`" in text


def test_static_page_uses_wikilinks():
    pages = {"entities/Foo.md": _mk_page({"title": "Foo"})}
    text = static_page("mytag", ["entities/Foo.md"], pages)
    assert "[[Foo|Foo]]" in text


def test_static_page_falls_back_to_slug_if_no_title():
    pages = {"entities/Foo.md": _mk_page({})}
    text = static_page("mytag", ["entities/Foo.md"], pages)
    assert "[[Foo|Foo]]" in text


# ─── generate_dataview_categories ───────────────────────────────────


def test_dataview_generator_respects_min_count(tmp_path: Path):
    tags = {
        "popular": ["a.md", "b.md", "c.md"],
        "lonely": ["a.md"],
    }
    written = generate_dataview_categories(tags, tmp_path, min_count=2)
    names = [p.name for p in written]
    assert "popular.md" in names
    assert "lonely.md" not in names


def test_dataview_generator_slugifies_tag(tmp_path: Path):
    tags = {"machine learning!": ["a.md", "b.md"]}
    written = generate_dataview_categories(tags, tmp_path, min_count=2)
    assert len(written) == 1
    # Space and ! become hyphens
    assert "-" in written[0].name


def test_dataview_generator_creates_out_dir(tmp_path: Path):
    out = tmp_path / "categories"
    tags = {"tag": ["a.md", "b.md"]}
    generate_dataview_categories(tags, out, min_count=1)
    assert out.is_dir()


def test_dataview_generator_empty_tags(tmp_path: Path):
    written = generate_dataview_categories({}, tmp_path)
    assert written == []


# ─── generate_static_categories ─────────────────────────────────────


def test_static_generator_writes_pages(tmp_path: Path):
    pages = {
        "a.md": _mk_page({"title": "A", "tags": "[flutter]"}),
        "b.md": _mk_page({"title": "B", "tags": "[flutter]"}),
    }
    written = generate_static_categories(pages, tmp_path, min_count=2)
    assert len(written) == 1
    content = written[0].read_text(encoding="utf-8")
    assert "## root" in content or "##" in content


def test_static_generator_skips_under_min_count(tmp_path: Path):
    pages = {
        "a.md": _mk_page({"title": "A", "tags": "[lonely]"}),
    }
    written = generate_static_categories(pages, tmp_path, min_count=2)
    assert written == []


def test_static_generator_custom_min_count(tmp_path: Path):
    pages = {
        "a.md": _mk_page({"title": "A", "tags": "[rare]"}),
    }
    written = generate_static_categories(pages, tmp_path, min_count=1)
    assert len(written) == 1


# ─── Noise tags ──────────────────────────────────────────────────────


def test_noise_tags_constants():
    assert "claude-code" in NOISE_TAGS
    assert "session-transcript" in NOISE_TAGS
    assert "demo" in NOISE_TAGS
