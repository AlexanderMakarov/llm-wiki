"""Tests that the command palette's search index covers every docs
page + slash command (#277).

Before: the palette could only find sessions, projects, and the 3
hard-coded pages (home / projects / sessions).  After: every
`docs/**/*.md` and every `.claude/commands/*.md` appears.

The index is built into a throwaway directory by ``build_search_index`` (docs and
slash entries come from the source checkout, not a vault), so these tests run on a
clean checkout instead of skipping when ``site/`` has not been built.

# @spec: 414-tests-render-mirror
# #315
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from llmwiki.build import build_search_index


@pytest.fixture(scope="module")
def search_index(tmp_path_factory: pytest.TempPathFactory) -> dict:
    out_dir = tmp_path_factory.mktemp("palette_index")
    index_path = build_search_index([], {}, out_dir)
    return json.loads(Path(index_path).read_text(encoding="utf-8"))


def _entries(index: dict, kind: str) -> list[dict]:
    return [e for e in index["entries"] if e["type"] == kind]


# ─── docs coverage ──────────────────────────────────────────────────


def test_palette_index_contains_docs_entries(search_index):
    """The palette index carries many `docs` entries, not just the hard-coded pages."""
    docs_entries = _entries(search_index, "docs")
    assert len(docs_entries) >= 20, f"expected many docs entries, got {len(docs_entries)}"


@pytest.mark.parametrize(
    "url",
    [
        "docs/cheatsheet.html",
        "docs/UPGRADING.html",
        "docs/reference/cli.html",
        "docs/reference/mcp.html",
        "docs/reference/slash-commands.html",
        "docs/reference/ui.html",
    ],
)
def test_palette_index_includes_key_docs_pages(search_index, url):
    """The cheatsheet, upgrade guide and the CLI / MCP / slash / UI reference pages are findable in the palette."""
    urls = {e["url"] for e in _entries(search_index, "docs")}
    assert url in urls, f"{url} missing from palette docs entries"


def test_palette_index_includes_every_tutorial(search_index):
    """Every shipped tutorial (8 numbered + setup guide) has a palette entry."""
    tutorials = [e for e in _entries(search_index, "docs") if "/tutorials/" in e["url"]]
    assert len(tutorials) >= 8


# ─── slash coverage ─────────────────────────────────────────────────


def test_palette_index_contains_slash_entries(search_index):
    """The palette index carries many slash-command entries."""
    slashes = _entries(search_index, "slash")
    assert len(slashes) >= 10, f"expected many slashes, got {len(slashes)}"


def test_palette_slash_titles_start_with_slash(search_index):
    """Every slash entry is titled with its leading `/` command name."""
    for s in _entries(search_index, "slash"):
        assert s["title"].startswith("/"), f"slash title should start with /: {s['title']!r}"


def test_palette_slash_entries_have_empty_url(search_index):
    """Slash entries carry an empty url because the palette copies them to the clipboard rather than navigating."""
    for s in _entries(search_index, "slash"):
        assert s["url"] == "", f"slash entries must have empty url, got {s['url']!r}"


def test_palette_slash_entries_have_non_empty_description(search_index):
    """Every slash entry carries a searchable description body."""
    for s in _entries(search_index, "slash"):
        assert s["body"], f"slash {s['title']!r} has empty body"


def test_palette_slash_includes_known_wrappers(search_index):
    """The packaged `/wiki-*` wrappers are all indexed."""
    slashes = {e["title"] for e in _entries(search_index, "slash")}
    for expected in (
        "/wiki-build", "/wiki-sync", "/wiki-query", "/wiki-lint",
        "/wiki-candidates", "/wiki-synth",
    ):
        assert expected in slashes, f"missing slash in index: {expected}"
