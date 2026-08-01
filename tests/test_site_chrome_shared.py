"""Regression tests for shared site chrome + viewer interaction fixes.

Each test pins a behaviour that was broken and is easy to re-break, because
none of them are visible from a unit test of the module that owns them:

* Docs pages emit the shared ``page_foot`` (footer, palette, ``script.js``).
  Without it the nav they already render is inert — the theme toggle, ⌘K
  palette, and hamburger drawer are all wired by ``script.js``.
* The theme cycle derives its starting point from the rendered theme, not
  from ``localStorage`` alone, so the first click always changes something.
* The graph only swallows right-click over a node, leaving empty canvas to
  the browser (and to mouse-gesture extensions).
* Clustering groups on ``kind`` (the wiki folder) rather than ``type``,
  which is the constant ``'topic'`` for every node in topic mode.
* Structural graph changes re-run the layout, which is otherwise frozen.
"""

from __future__ import annotations

from pathlib import Path

from llmwiki.build import page_foot
from llmwiki.docs_pages import compile_docs_site
from llmwiki.graph import HTML_TEMPLATE
from llmwiki.render.css import CSS
from llmwiki.render.js import JS
from llmwiki.topics import build_topic_graph

# ─── Docs pages share the site runtime ────────────────────────────────────


def _write_doc(root: Path, rel: str, body: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"---\ntitle: X\ntype: guide\ndocs_shell: true\n---\n{body}", encoding="utf-8")


def test_docs_pages_emit_shared_page_foot(tmp_path: Path):
    _write_doc(tmp_path, "index.md", "# Hub\n\nBody.\n")
    _write_doc(tmp_path, "tutorials/01-a.md", "# 01 · A\n\nBody.\n")
    site = tmp_path / "site"
    site.mkdir()
    compile_docs_site(
        tmp_path, site, page_foot=lambda prefix: page_foot(js_prefix=prefix)
    )

    hub = (site / "docs" / "index.html").read_text()
    nested = (site / "docs" / "tutorials" / "01-a.html").read_text()

    # script.js is what makes the rendered theme toggle / palette do anything.
    assert 'src="../script.js"' in hub
    assert 'src="../../script.js"' in nested, "nested docs pages need a deeper prefix"
    # The palette markup and its index URL travel with the footer.
    assert 'id="palette"' in hub
    assert 'LLMWIKI_INDEX_URL = "../search-index.json"' in hub
    assert 'LLMWIKI_INDEX_URL = "../../search-index.json"' in nested


def test_docs_pages_without_page_foot_still_close_the_document(tmp_path: Path):
    # page_foot stays optional so tests can render markup without the runtime.
    _write_doc(tmp_path, "index.md", "# Hub\n\nBody.\n")
    site = tmp_path / "site"
    site.mkdir()
    compile_docs_site(tmp_path, site)
    hub = (site / "docs" / "index.html").read_text()
    assert hub.rstrip().endswith("</html>")
    assert "script.js" not in hub


# ─── Theme toggle ─────────────────────────────────────────────────────────


def test_theme_cycle_starts_from_rendered_theme_not_storage():
    # The pre-paint script always pins data-theme, so a cycle that begins by
    # pinning "dark" unconditionally is a no-op on an already-dark page.
    assert "function effectiveTheme()" in JS
    assert 'return effectiveTheme() === "dark" ? "light" : "dark";' in JS


def test_theme_cycle_is_shared_by_both_toggles():
    # One implementation, so desktop and mobile can't drift apart.
    assert "window.__llmwikiCycleTheme = cycleTheme;" in JS
    assert JS.count("localStorage.setItem(\"llmwiki-theme\"") == 1, (
        "theme writes should go through the single shared cycle"
    )
    assert "window.__llmwikiCycleTheme()" in JS  # mobile button delegates


# ─── Graph: right-click ───────────────────────────────────────────────────


def test_graph_only_prevents_context_menu_over_a_node():
    # preventDefault must sit inside the `if (nodeId)` branch — unconditional
    # prevention kills mouse-gesture extensions on the whole canvas.
    start = HTML_TEMPLATE.index("network.on('oncontext'")
    handler = HTML_TEMPLATE[start:start + 600]
    prevent = handler.index("params.event.preventDefault();")
    guard = handler.index("if (nodeId) {")
    assert guard < prevent, (
        "preventDefault() runs before the node check — empty canvas would "
        "lose its native right-click"
    )


# ─── Graph: clustering ────────────────────────────────────────────────────


def test_cluster_groups_on_kind_not_type():
    assert "const nodeKind = n => n.kind || n.type || 'other';" in HTML_TEMPLATE
    assert "joinCondition: n => !n.isKindCluster && nodeKind(n) === k" in HTML_TEMPLATE
    # Existing clusters must be excluded or they nest inside the next one.
    assert "isKindCluster: true" in HTML_TEMPLATE


def test_cluster_nodes_carry_no_vis_group_key():
    # `group` is vis's own key: it re-applies an automatic palette when a
    # cluster reopens, overwriting our per-kind colours.
    assert "group: n.kind" not in HTML_TEMPLATE
    assert "group: 'topic'" not in HTML_TEMPLATE


def test_structural_graph_changes_restabilize():
    # Physics is frozen after the first layout; without a re-run every node
    # created by (un)clustering stacks at one point.
    assert "function restabilize()" in HTML_TEMPLATE
    assert HTML_TEMPLATE.count("restabilize();") >= 2  # applyLayout + cluster


def test_cluster_failures_surface_on_the_page():
    assert "reportGraphError" in HTML_TEMPLATE
    assert "window.__llmwikiReportError" in HTML_TEMPLATE


# ─── Topic kinds ──────────────────────────────────────────────────────────


def _seed_vault(wiki: Path) -> None:
    (wiki / "sources").mkdir(parents=True)
    (wiki / "entities").mkdir(parents=True)
    (wiki / "concepts").mkdir(parents=True)
    for n in (1, 2):
        (wiki / "sources" / f"s{n}.md").write_text(
            f"---\ntitle: S{n}\ntype: source\n---\n"
            "Body [[Acmecorp]] and [[Widgetry]] and [[Unpaged]].\n",
            encoding="utf-8",
        )
    (wiki / "entities" / "Acmecorp.md").write_text(
        '---\ntitle: "Acmecorp"\ntype: entity\n---\n# Acmecorp\n', encoding="utf-8")
    (wiki / "concepts" / "Widgetry.md").write_text(
        '---\ntitle: "Widgetry"\ntype: concept\n---\n# Widgetry\n', encoding="utf-8")


def test_topic_nodes_resolve_to_their_wiki_folder(tmp_path: Path):
    wiki = tmp_path / "wiki"
    _seed_vault(wiki)
    graph = build_topic_graph(wiki)
    kinds = {n["id"]: n["kind"] for n in graph["nodes"]}
    assert kinds["Acmecorp"] == "entities"
    assert kinds["Widgetry"] == "concepts"
    # A wikilink with no page behind it is still a topic, just an unsorted one.
    assert kinds["Unpaged"] == "other"
    assert graph["stats"]["kinds"] == {"concepts": 1, "entities": 1, "other": 1}


# ─── Vertical rhythm ──────────────────────────────────────────────────────


def test_hero_spacing_comes_from_tokens():
    # One place to tune the masthead rhythm for every page family.
    assert "--hero-y:" in CSS
    assert ".hero { padding: var(--hero-y); margin-bottom: var(--hero-gap);" in CSS


def test_progress_bar_does_not_capture_pointer_events():
    bar = CSS[CSS.index(".progress-bar {"):]
    assert "pointer-events: none;" in bar[:bar.index("}")]
