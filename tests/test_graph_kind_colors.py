"""Tests for #108 FR6 — every topic kind gets its own colour in the map.

`projects`, `questions`, `comparisons` and `other` used to have no entry in
the viewer's `colors` map, so all four fell through to `--g-node-topic` while
the legend still listed them as separate rows. These tests pin the palette to
`llmwiki.topics.TOPIC_KIND_FOLDERS` so adding a wiki folder later fails here
rather than silently losing a colour, and keep red reserved for the two signal
states (`--g-orphan`, `--g-search-match`).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from llmwiki.graph import write_html
from llmwiki.topics import KIND_OTHER, TOPIC_KIND_FOLDERS

# Every kind the viewer can label, and therefore must colour.
KINDS = frozenset(TOPIC_KIND_FOLDERS | {KIND_OTHER})
NEW_VARS = (
    "--g-node-projects",
    "--g-node-questions",
    "--g-node-comparisons",
    "--g-node-other",
)


@pytest.fixture
def rendered(tmp_path: Path) -> str:
    """The generated `graph.html` for an empty graph."""
    g = {"nodes": [], "edges": [],
         "stats": {"total_pages": 0, "total_edges": 0, "orphans": [], "top_linked": []}}
    out = tmp_path / "graph.html"
    write_html(g, out)
    return out.read_text(encoding="utf-8")


def _theme_vars(html: str, theme: str) -> dict[str, str]:
    """CSS custom properties declared in one `:root[data-theme=...]` block."""
    start = html.index(f':root[data-theme="{theme}"] {{')
    block = html[start:html.index("}", start)]
    return dict(re.findall(r"(--[\w-]+):\s*([^;]+);", block))


def _kind_vars(html: str) -> dict[str, str]:
    """Kind → CSS variable name, as declared in the viewer's `colors` map."""
    start = html.index("const colors = {")
    block = html[start:html.index("};", start)]
    return dict(re.findall(r"(\w+):\s*\(\)\s*=>\s*cssVar\('(--[\w-]+)'\)", block))


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_both_theme_blocks_declare_the_new_kind_variables(rendered: str, theme: str):
    declared = _theme_vars(rendered, theme)
    for var in NEW_VARS:
        assert var in declared, f"{var} missing from the {theme} theme block"


def test_every_kind_has_an_entry_in_the_colors_map(rendered: str):
    assert KINDS <= set(_kind_vars(rendered))


def test_unknown_kinds_still_fall_back_to_the_topic_colour(rendered: str):
    assert "const kindColor = k => (colors[k] || colors.topic)();" in rendered


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_no_two_kinds_share_a_colour(rendered: str, theme: str):
    declared = _theme_vars(rendered, theme)
    kind_vars = _kind_vars(rendered)
    by_kind = {kind: declared[kind_vars[kind]] for kind in KINDS}
    assert len(set(by_kind.values())) == len(by_kind), by_kind


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_no_kind_takes_the_colour_reserved_for_orphans_or_search(
    rendered: str, theme: str
):
    declared = _theme_vars(rendered, theme)
    kind_vars = _kind_vars(rendered)
    reserved = {declared["--g-orphan"], declared["--g-search-match"]}
    for kind in KINDS:
        assert declared[kind_vars[kind]] not in reserved, kind
