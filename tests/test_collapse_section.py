"""Shared collapse_section widget used by Home + Analytics."""

from __future__ import annotations

from llmwiki.render.collapse_section import (
    collapse_section,
    collapse_section_list,
    collapse_sections_wrap,
)
from llmwiki.viz_wiki_value import render_wiki_value_section


def test_collapse_section_escapes_title_and_shows_count():
    html = collapse_section("A <b>title</b>", 3, "<p>body</p>")
    assert "A &lt;b&gt;title&lt;/b&gt;" in html
    assert 'class="collapse-section"' in html
    assert 'class="collapse-section-count">3</span>' in html
    assert "<p>body</p>" in html
    assert " open" not in html


def test_collapse_section_open_and_list_helpers():
    opened = collapse_section("T", 0, "x", open=True)
    assert "<details class=\"collapse-section\" open>" in opened
    listed = collapse_section_list(
        "Dead stock",
        ["<li><code>a.md</code></li>", "<li><code>b.md</code></li>"],
        count=9,
        intro_html='<p class="muted">intro</p>',
        footer_html='<p class="muted">more</p>',
    )
    assert "collapse-section-count\">9</span>" in listed
    assert "<code>a.md</code>" in listed
    assert "intro" in listed
    assert "more" in listed
    wrap = collapse_sections_wrap(listed, collapse_section("Other", 1, "y"))
    assert wrap.startswith('<div class="collapse-sections">')
    assert wrap.count("collapse-section") >= 2


def test_analytics_dead_stock_uses_collapse_section():
    out = render_wiki_value_section(
        {"total_calls": 1, "per_tool": {"wiki_query": {"calls": 1, "zero_hits": 0}}},
        dead_stock=["wiki/sources/x.md", "wiki/sources/y.md"],
        dead_stock_total=5,
        wiki_page_count=2,
        corpus_mix={"session": 1, "doc": 1, "other": 0, "total": 2},
    )
    assert 'class="collapse-section wiki-value-dead-collapse"' in out
    assert ">Dead stock<" in out or ">Dead stock</" in out or "Dead stock" in out
    assert 'class="collapse-section-count">5</span>' in out
    assert "wiki/sources/x.md" in out
    assert "…and 3 more" in out
    assert "<h3>Dead stock" not in out
