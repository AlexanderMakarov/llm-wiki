"""Tests for #108 FR6 — every topic kind gets its own colour in the map.

A kind the legend lists but the viewer's `colors` map omits falls through to
`--g-node-topic`, so the row and the node disagree. These tests pin the
palette to `llmwiki.topics.TOPIC_KIND_FOLDERS` — every kind is coloured, every
colour the viewer asks for is declared in both themes, no two kinds share one,
and red stays reserved for the two signal states (`--g-orphan`,
`--g-search-match`).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from llmwiki.graph import write_html
from llmwiki.render.graph_viewer import GRAPH_VIEWER_JS
from llmwiki.topics import KIND_OTHER, TOPIC_KIND_FOLDERS

# Every kind the viewer can label, and therefore must colour.
KINDS = frozenset(TOPIC_KIND_FOLDERS | {KIND_OTHER})


@pytest.fixture
def graph_out(tmp_path: Path) -> Path:
    """The generated `graph.html` path for an empty graph."""
    g = {"nodes": [], "edges": [],
         "stats": {"total_pages": 0, "total_edges": 0, "orphans": [], "top_linked": []}}
    out = tmp_path / "graph.html"
    write_html(g, out)
    return out


@pytest.fixture
def rendered(graph_out: Path) -> str:
    return graph_out.read_text(encoding="utf-8")


@pytest.fixture
def viewer_js(graph_out: Path) -> str:
    return (graph_out.parent / "graph-viewer.js").read_text(encoding="utf-8")


def _theme_vars(html: str, theme: str) -> dict[str, str]:
    """CSS custom properties declared in one `:root[data-theme=...]` block."""
    start = html.index(f':root[data-theme="{theme}"] {{')
    block = html[start:html.index("}", start)]
    return dict(re.findall(r"(--[\w-]+):\s*([^;]+);", block))


def _kind_vars(viewer_js: str) -> dict[str, str]:
    """Kind → CSS variable name, as declared in the viewer's `colors` map."""
    start = viewer_js.index("const colors = {")
    block = viewer_js[start:viewer_js.index("};", start)]
    return dict(re.findall(r"(\w+):\s*\(\)\s*=>\s*cssVar\('(--[\w-]+)'\)", block))


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_both_theme_blocks_declare_every_variable_the_viewer_asks_for(
    rendered: str, viewer_js: str, theme: str
):
    declared = _theme_vars(rendered, theme)
    for kind, var in _kind_vars(viewer_js).items():
        assert var in declared, f"{var} ({kind}) missing from the {theme} theme block"


def test_every_kind_has_an_entry_in_the_colors_map(viewer_js: str):
    assert KINDS <= set(_kind_vars(viewer_js))


def test_unknown_kinds_still_fall_back_to_the_topic_colour():
    assert "const kindColor = k => (colors[k] || colors.topic)();" in GRAPH_VIEWER_JS


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_no_two_kinds_share_a_colour(rendered: str, viewer_js: str, theme: str):
    declared = _theme_vars(rendered, theme)
    kind_vars = _kind_vars(viewer_js)
    by_kind = {kind: declared[kind_vars[kind]] for kind in KINDS}
    assert len(set(by_kind.values())) == len(by_kind), by_kind


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_no_kind_takes_the_colour_reserved_for_orphans_or_search(
    rendered: str, viewer_js: str, theme: str
):
    declared = _theme_vars(rendered, theme)
    kind_vars = _kind_vars(viewer_js)
    reserved = {declared["--g-orphan"], declared["--g-search-match"]}
    for kind in KINDS:
        assert declared[kind_vars[kind]] not in reserved, kind
