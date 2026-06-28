"""Tests for `graph.site_url` computation + click-to-navigate safety (#328).

Covers:
* Wiki/index.md → index.html
* Wiki/projects/<slug>.md → projects/<slug>.html
* Wiki/sources/<proj>/<stem>.md uses source_file frontmatter to derive
  the matching sessions/<proj>/<date-stem>.html
* entities / concepts / syntheses / nav files → None
* Missing source_file → None
* _verify_site_url nullifies dead URLs when site_dir exists
* _verify_site_url leaves URLs intact when site_dir is None
* Click handler + context menu both read site_url
"""

from __future__ import annotations

from pathlib import Path

import pytest

import llmwiki.graph as graph_mod
from llmwiki.graph import (
    HTML_TEMPLATE,
    _compute_site_url,
    _verify_site_url,
    build_graph,
    scan_pages,
    write_html,
)


# ─── _compute_site_url ────────────────────────────────────────────────────


def test_index_maps_to_root():
    assert _compute_site_url("", ("index.md",), "index", "root") == "index.html"


def test_project_page():
    assert _compute_site_url("", ("projects", "foo.md"), "foo", "projects") == "projects/foo.html"


def test_source_uses_source_file_frontmatter():
    text = (
        "---\ntitle: X\n"
        "source_file: raw/sessions/research/2026-04-06-jiggly-coalescing-bee.md\n"
        "---\nbody\n"
    )
    url = _compute_site_url(
        text, ("sources", "research", "jiggly-coalescing-bee.md"),
        "jiggly-coalescing-bee", "sources",
    )
    assert url == "sessions/research/2026-04-06-jiggly-coalescing-bee.html"


def test_source_without_source_file_returns_none():
    text = "---\ntitle: X\n---\nbody\n"
    url = _compute_site_url(
        text, ("sources", "research", "foo.md"), "foo", "sources",
    )
    assert url is None


def test_source_with_flat_raw_path():
    # #54: a flat ``raw/sessions/<stem>.md`` source_file (the layout vault
    # syncs use) must still resolve to the project-nested compiled page
    # ``sessions/<project>/<stem>.html``. The project comes from the wiki
    # sources subdirectory when no ``project:`` frontmatter is present.
    text = (
        "---\ntitle: X\n"
        "source_file: raw/sessions/2026-04-17T12-00-proj-slug.md\n"
        "---\n"
    )
    url = _compute_site_url(
        text, ("sources", "proj", "slug.md"), "slug", "sources",
    )
    assert url == "sessions/proj/2026-04-17T12-00-proj-slug.html"


def test_source_flat_raw_path_uses_project_frontmatter():
    # When present, ``project:`` frontmatter is authoritative for the session
    # page's directory (it matches what build.py groups sessions by).
    text = (
        "---\ntitle: X\nproject: llm-wiki\n"
        "source_file: raw/sessions/2026-06-14T19-45-llm-wiki-104d9792.md\n"
        "---\n"
    )
    url = _compute_site_url(
        text, ("sources", "llm-wiki", "2026-06-14-104d9792.md"),
        "2026-06-14-104d9792", "sources",
    )
    assert url == "sessions/llm-wiki/2026-06-14T19-45-llm-wiki-104d9792.html"


def test_entity_returns_none():
    assert _compute_site_url("", ("entities", "Foo.md"), "Foo", "entities") is None


def test_concept_returns_none():
    assert _compute_site_url("", ("concepts", "RAG.md"), "RAG", "concepts") is None


def test_synthesis_returns_none():
    assert _compute_site_url("", ("syntheses", "analysis.md"), "analysis", "syntheses") is None


def test_nav_files_return_none():
    for slug in ("CRITICAL_FACTS", "MEMORY", "SOUL", "hints", "overview"):
        assert _compute_site_url("", (f"{slug}.md",), slug, "root") is None


def test_compute_handles_quoted_source_file():
    text = '---\nsource_file: "raw/sessions/proj/file.md"\n---\n'
    url = _compute_site_url(
        text, ("sources", "proj", "file.md"), "file", "sources",
    )
    assert url == "sessions/proj/file.html"


# ─── _verify_site_url ────────────────────────────────────────────────────


def test_verify_keeps_existing_file(tmp_path):
    (tmp_path / "foo.html").write_text("<html>", encoding="utf-8")
    assert _verify_site_url("foo.html", tmp_path) == "foo.html"


def test_verify_nulls_missing_file(tmp_path):
    assert _verify_site_url("bogus.html", tmp_path) is None


def test_verify_passes_through_when_site_dir_none():
    assert _verify_site_url("anything.html", None) == "anything.html"


def test_verify_passes_through_when_site_dir_missing(tmp_path):
    assert _verify_site_url("x.html", tmp_path / "does-not-exist") == "x.html"


def test_verify_handles_none_input():
    assert _verify_site_url(None, None) is None


# ─── build_graph integration ─────────────────────────────────────────────


def _seed_wiki(tmp_path: Path) -> Path:
    wiki = tmp_path / "wiki"
    (wiki / "entities").mkdir(parents=True)
    (wiki / "concepts").mkdir(parents=True)
    (wiki / "projects").mkdir(parents=True)
    (wiki / "sources" / "proj").mkdir(parents=True)
    (wiki / "index.md").write_text(
        "---\ntitle: Wiki Index\n---\n\n- [[Foo]]\n- [[bar]]\n",
        encoding="utf-8",
    )
    (wiki / "entities" / "Foo.md").write_text(
        "---\ntitle: Foo Co.\n---\n\n[[bar]] is related\n",
        encoding="utf-8",
    )
    (wiki / "concepts" / "bar.md").write_text(
        "---\ntitle: bar\n---\n\nJust a concept.\n",
        encoding="utf-8",
    )
    (wiki / "projects" / "proj.md").write_text(
        "---\ntitle: My Project\n---\n\n",
        encoding="utf-8",
    )
    (wiki / "sources" / "proj" / "session1.md").write_text(
        "---\ntitle: S1\n"
        "source_file: raw/sessions/proj/2026-04-17-session1.md\n"
        "---\n[[Foo]] and [[proj]]\n",
        encoding="utf-8",
    )
    return wiki


def test_graph_includes_site_urls(tmp_path, monkeypatch):
    wiki = _seed_wiki(tmp_path)
    monkeypatch.setattr(graph_mod, "WIKI_DIR", wiki)
    monkeypatch.setattr(graph_mod, "REPO_ROOT", tmp_path)
    g = build_graph()
    urls = {n["id"]: n["site_url"] for n in g["nodes"]}
    assert urls["index"] == "index.html"
    assert urls["proj"] == "projects/proj.html"
    assert urls["session1"] == "sessions/proj/2026-04-17-session1.html"
    # Entities + concepts get None.
    assert urls["Foo"] is None
    assert urls["bar"] is None


def test_build_graph_verify_site_dir_nulls_missing(tmp_path, monkeypatch):
    wiki = _seed_wiki(tmp_path)
    monkeypatch.setattr(graph_mod, "WIKI_DIR", wiki)
    monkeypatch.setattr(graph_mod, "REPO_ROOT", tmp_path)
    site = tmp_path / "site"
    site.mkdir()
    # Seed only one of the expected URLs.
    (site / "index.html").write_text("<html>", encoding="utf-8")
    g = build_graph(verify_site_dir=site)
    urls = {n["id"]: n["site_url"] for n in g["nodes"]}
    assert urls["index"] == "index.html"
    # proj + session1 pages missing in site/ → null.
    assert urls["proj"] is None
    assert urls["session1"] is None


# ─── Rendered HTML template has click handler using site_url ────────────


def test_template_click_handler_uses_site_url():
    assert "node.site_url" in HTML_TEMPLATE
    # Old broken rewrite path must be gone.
    assert "replace(/^wiki\\//, '')" not in HTML_TEMPLATE
    assert "_flashNoSiteTooltip" in HTML_TEMPLATE


def test_template_context_menu_open_uses_site_url():
    # Find the `case 'open':` block and assert it uses site_url.
    idx = HTML_TEMPLATE.index("case 'open':")
    end = HTML_TEMPLATE.index("break", idx)
    block = HTML_TEMPLATE[idx:end]
    assert "node.site_url" in block


def test_template_renders_no_page_alert():
    idx = HTML_TEMPLATE.index("case 'open':")
    end = HTML_TEMPLATE.index("break", idx)
    block = HTML_TEMPLATE[idx:end]
    assert "no compiled page" in block
