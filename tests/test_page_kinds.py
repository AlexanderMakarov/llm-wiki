"""The page-kind vocabulary, and what depends on it (#109).

`source`, `entity`, `concept`, `project` and `synthesis` are the kinds a
reader or agent browses; `navigation` and `context` are build machinery.
Nothing else is a valid `type:`, and no surface — graph palette, viewer
legend, MCP tool schema, Obsidian export — offers a kind outside that set.

Wikilink resolution is name-based, so relocating a page between wiki
folders leaves inbound `[[links]]` intact. `test_wikilink_resolution_*`
is the evidence behind that claim.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from llmwiki.backlinks import _collect_pages, build_reverse_index
from llmwiki.graph import build_graph, write_html
from llmwiki.lint import load_pages, run_all
from llmwiki.lint.rules.frontmatter_validity import FrontmatterValidity
from llmwiki.mcp.server import TOOLS
from llmwiki.obsidian_output import EXPORTED_DIRS
from llmwiki.references import build_index
from llmwiki.render.graph_viewer import GRAPH_VIEWER_JS
from llmwiki.schema import ALL_PAGE_KINDS, PAGE_KINDS, SYSTEM_PAGE_KINDS
from llmwiki.topics import TOPIC_KIND_FOLDERS
from llmwiki.topics_page import kind_label
from llmwiki.wikilinks import wikilink_targets

REMOVED_KINDS = ("question", "comparison")
REMOVED_FOLDERS = ("questions", "comparisons")


def _page(path: Path, body: str, **meta: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    front = "".join(f"{k}: {v}\n" for k, v in meta.items())
    path.write_text(f"---\n{front}---\n\n{body}\n", encoding="utf-8")


# ─── vocabulary ────────────────────────────────────────────────────────


@pytest.mark.parametrize("kind", REMOVED_KINDS)
def test_removed_kinds_are_not_in_the_vocabulary(kind: str) -> None:
    assert kind not in ALL_PAGE_KINDS


def test_surviving_kinds() -> None:
    assert PAGE_KINDS == ("source", "entity", "concept", "project", "synthesis")
    assert SYSTEM_PAGE_KINDS == ("navigation", "context")


@pytest.mark.parametrize("kind", REMOVED_KINDS)
def test_frontmatter_validity_rejects_a_removed_kind(tmp_path: Path, kind: str) -> None:
    wiki = tmp_path / "wiki"
    _page(wiki / "concepts" / "Thing.md", "# Thing", title='"Thing"', type=kind)

    issues = run_all(load_pages(wiki), selected=["frontmatter_validity"])

    assert [i["rule"] for i in issues] == ["frontmatter_validity"]
    assert issues[0]["severity"] == "error"
    assert kind in issues[0]["message"]


@pytest.mark.parametrize("kind", ALL_PAGE_KINDS)
def test_frontmatter_validity_accepts_every_surviving_kind(
    tmp_path: Path, kind: str
) -> None:
    wiki = tmp_path / "wiki"
    _page(wiki / "concepts" / "Thing.md", "# Thing", title='"Thing"', type=kind)

    assert run_all(load_pages(wiki), selected=["frontmatter_validity"]) == []


def test_lint_rule_enforces_the_schema_it_does_not_define_it() -> None:
    assert FrontmatterValidity.VALID_TYPES == set(ALL_PAGE_KINDS)


# ─── surfaces that advertise the vocabulary ────────────────────────────


@pytest.mark.parametrize("kind", REMOVED_KINDS)
def test_mcp_search_schema_does_not_advertise_a_removed_kind(kind: str) -> None:
    schema = next(t for t in TOOLS if t["name"] == "wiki_search")["inputSchema"]
    assert kind not in schema["properties"]["kind"]["enum"]
    assert schema["properties"]["kind"]["enum"] == list(PAGE_KINDS)


@pytest.mark.parametrize("folder", REMOVED_FOLDERS)
def test_graph_palette_declares_no_colour_for_a_removed_folder(
    tmp_path: Path, folder: str
) -> None:
    graph = {"nodes": [], "edges": [],
             "stats": {"total_pages": 0, "total_edges": 0,
                       "orphans": [], "top_linked": []}}
    out = tmp_path / "graph.html"
    write_html(graph, out)

    assert f"--g-node-{folder}" not in out.read_text(encoding="utf-8")


@pytest.mark.parametrize("folder", REMOVED_FOLDERS)
def test_graph_viewer_offers_no_colour_or_legend_label(folder: str) -> None:
    colors = GRAPH_VIEWER_JS[
        GRAPH_VIEWER_JS.index("const colors = {"):
        GRAPH_VIEWER_JS.index("};", GRAPH_VIEWER_JS.index("const colors = {"))
    ]
    labels = GRAPH_VIEWER_JS[
        GRAPH_VIEWER_JS.index("const KIND_LABELS = {"):
        GRAPH_VIEWER_JS.index("};", GRAPH_VIEWER_JS.index("const KIND_LABELS = {"))
    ]
    assert folder not in colors
    assert folder not in labels
    assert folder.capitalize() not in labels


@pytest.mark.parametrize("folder", REMOVED_FOLDERS)
def test_removed_folders_are_not_a_topic_kind_or_an_export_target(folder: str) -> None:
    assert folder not in TOPIC_KIND_FOLDERS
    assert folder not in EXPORTED_DIRS


@pytest.mark.parametrize("folder", REMOVED_FOLDERS)
def test_a_leftover_folder_still_gets_a_generic_topic_label(folder: str) -> None:
    """A user vault may still carry the folder until they migrate, and the
    topic chip must name it rather than crash on the missing entry."""
    assert kind_label(folder) == folder.removesuffix("s").capitalize()


# ─── the spike: wikilink resolution is name-based, not path-based ──────


def _seed_linked_pair(wiki: Path, folder: str) -> Path:
    """A page under ``folder`` plus a source page linking to it by name."""
    target = wiki / folder / "CacheBudget.md"
    _page(target, "# Cache budget\n\n## Connections\n- [[demo-session]]",
          title='"Cache budget"', type="concept")
    _page(wiki / "sources" / "demo-session.md",
          "# Demo session\n\n## Connections\n- [[CacheBudget]] — how it relates",
          title='"Demo session"', type="source", date="2026-08-01")
    return target


def _inbound_link_evidence(wiki: Path) -> dict[str, object]:
    """Every resolver's answer to 'does [[CacheBudget]] resolve?'"""
    pages = load_pages(wiki)
    graph = build_graph(wiki_dir=wiki)
    return {
        "graph_edges": {(e["source"], e["target"]) for e in graph["edges"]},
        "broken_edges": graph["broken_edges"],
        "backlink_referrers": {
            e.slug
            for e in build_reverse_index(_collect_pages(wiki)).get("CacheBudget", [])
        },
        "reference_target_rel": {
            r.target_rel for r in build_index(pages).get("CacheBudget", [])
        },
        "link_integrity": run_all(pages, selected=["link_integrity"]),
    }


def test_wikilink_resolution_survives_a_move_between_wiki_folders(
    tmp_path: Path,
) -> None:
    """THE SPIKE (#109). Resolution keys on the page's filename, never on the
    folder it sits in, so relocating a page keeps every inbound `[[link]]`
    working without rewriting the referrer.

    A vault that still carries a legacy `wiki/questions/` folder is the real
    input here: the page moves into `wiki/concepts/`, filename unchanged.
    """
    wiki = tmp_path / "wiki"
    before_path = _seed_linked_pair(wiki, "questions")
    before = _inbound_link_evidence(wiki)

    after_path = wiki / "concepts" / before_path.name
    after_path.parent.mkdir(parents=True, exist_ok=True)
    before_path.rename(after_path)
    before_path.parent.rmdir()
    after = _inbound_link_evidence(wiki)

    # The link resolves before and after, and the referrer was never edited.
    assert ("demo-session", "CacheBudget") in before["graph_edges"]
    assert ("demo-session", "CacheBudget") in after["graph_edges"]
    assert before["broken_edges"] == [] == after["broken_edges"]
    assert before["backlink_referrers"] == {"demo-session"} == after["backlink_referrers"]
    assert before["link_integrity"] == [] == after["link_integrity"]

    # Only the *path* a resolver reports changes — the target slug does not.
    assert before["reference_target_rel"] == {"questions/CacheBudget.md"}
    assert after["reference_target_rel"] == {"concepts/CacheBudget.md"}


def test_wikilink_pattern_carries_no_path_segment() -> None:
    """The canonical pattern captures a bare name: a `[[folder/Name]]` target
    would resolve to the literal string `folder/Name`, which matches no page
    slug. Nothing in the wiki writes that form, and the migration must not
    start."""
    assert wikilink_targets("see [[CacheBudget]] and [[CacheBudget#facts]]") == {
        "CacheBudget"
    }
    assert re.search(r"/", "".join(wikilink_targets("[[CacheBudget]]"))) is None
