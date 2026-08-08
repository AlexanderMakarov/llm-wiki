"""FR2 Sources links — prefer HTML else raw with target=_blank (#122)."""

from __future__ import annotations

from pathlib import Path

from llmwiki.build import render_session
from llmwiki.topics import build_topic_graph
from llmwiki.topics_page import build_topic_pages
from llmwiki.trace import (
    SourceLink,
    format_sources_html,
    provenance_links_for_raw,
    raw_site_copy_href,
    sources_links,
)


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _chain_vault(tmp_path: Path, *, with_session_html: bool) -> Path:
    vault = tmp_path / "vault"
    raw_name = "2026-01-01T12-00-demo-kickoff.md"
    _write(
        vault / "raw" / "sessions" / raw_name,
        (
            '---\ntitle: "Kickoff transcript"\ntype: source\n'
            "project: demo\n---\n\nbody\n"
        ),
    )
    _write(
        vault / "wiki" / "sources" / "kickoff.md",
        (
            '---\ntitle: "Kickoff session"\ntype: source\n'
            "project: demo\n"
            f"source_file: raw/sessions/{raw_name}\n"
            "---\n\n## Summary\n\nAbout [[Demo]].\n"
        ),
    )
    _write(
        vault / "wiki" / "entities" / "Demo.md",
        (
            '---\ntitle: "Demo"\ntype: entity\nsources: [kickoff]\n'
            "last_updated: 2026-01-02\n---\n\n# Demo\n\n"
            "## Key Facts\n- One fact.\n"
        ),
    )
    if with_session_html:
        html_path = (
            vault / "site" / "sessions" / "demo" / "2026-01-01T12-00-demo-kickoff.html"
        )
        _write(html_path, "<html></html>\n")
        _write(vault / "site" / "sources" / "demo" / raw_name, "copied\n")
    return vault


# ─── helpers ──────────────────────────────────────────────────────────────


def test_raw_site_copy_href_flat_session():
    assert (
        raw_site_copy_href("raw/sessions/a.md", project="demo")
        == "sources/demo/a.md"
    )


def test_raw_site_copy_href_flat_and_nested_docs():
    assert raw_site_copy_href("raw/docs/note.md") == "documents/note.md"
    assert (
        raw_site_copy_href("raw/docs/proj/note.md") == "documents/proj/note.md"
    )


def test_format_sources_html_empty():
    assert format_sources_html([]) == ""


def test_format_sources_html_prefer_html_no_blank():
    html = format_sources_html(
        [SourceLink(title="Kickoff", href="sessions/demo/x.html", is_raw=False)],
        link_prefix="../",
    )
    assert 'href="../sessions/demo/x.html"' in html
    assert "target=" not in html
    assert "(raw)" not in html


def test_format_sources_html_raw_has_blank_and_noopener():
    html = format_sources_html(
        [SourceLink(title="Kickoff", href="sources/demo/x.md", is_raw=True)],
        link_prefix="../",
    )
    assert 'href="../sources/demo/x.md"' in html
    assert 'target="_blank"' in html
    assert 'rel="noopener"' in html
    assert "(raw)" in html


def test_sources_links_prefer_html_when_site_file_exists(tmp_path: Path):
    vault = _chain_vault(tmp_path, with_session_html=True)
    links = sources_links(vault, "wiki/entities/Demo.md")
    assert len(links) == 1
    assert links[0].is_raw is False
    assert links[0].href == "sessions/demo/2026-01-01T12-00-demo-kickoff.html"
    assert links[0].title == "Kickoff session"


def test_sources_links_raw_fallback_without_html(tmp_path: Path):
    vault = _chain_vault(tmp_path, with_session_html=False)
    links = sources_links(vault, "wiki/entities/Demo.md")
    assert len(links) == 1
    assert links[0].is_raw is True
    assert links[0].href == "sources/demo/2026-01-01T12-00-demo-kickoff.md"


def test_sources_links_empty_when_no_sources(tmp_path: Path):
    vault = tmp_path / "vault"
    _write(
        vault / "wiki" / "entities" / "Alone.md",
        '---\ntitle: "Alone"\ntype: entity\n---\n\n# Alone\n',
    )
    assert sources_links(vault, "Alone") == []


def test_provenance_links_for_raw_excludes_self_html(tmp_path: Path):
    vault = _chain_vault(tmp_path, with_session_html=True)
    raw_rel = "raw/sessions/2026-01-01T12-00-demo-kickoff.md"
    self_href = "sessions/demo/2026-01-01T12-00-demo-kickoff.html"
    links = provenance_links_for_raw(
        vault, raw_rel, project="demo", exclude_href=self_href
    )
    assert len(links) == 1
    assert links[0].is_raw is True
    assert links[0].href == "sources/demo/2026-01-01T12-00-demo-kickoff.md"


# ─── topic pages: evidence list (no frontmatter provenance panel) ──────────


def test_topic_page_has_sources_collapse_not_provenance_panel(tmp_path: Path):
    """Topic pages list graph evidence under Sources; no provenance-sources block."""
    vault = _chain_vault(tmp_path, with_session_html=True)
    out = tmp_path / "out"
    graph = build_topic_graph(vault / "wiki", min_sessions=1)
    written = build_topic_pages(graph, out, wiki_dir=vault / "wiki")
    topic = next(p for p in written if p.name == "demo.html")
    text = topic.read_text(encoding="utf-8")
    assert 'class="collapse-section topic-sources"' in text
    assert 'summary>Sources<span class="collapse-section-count"' in text
    assert "provenance-sources" not in text
    assert "<h2>Sources</h2>" not in text
    # Evidence comes from graph sessions, not frontmatter provenance titles.
    assert "<h3>Sessions</h3>" in text


def test_topic_page_omits_empty_document_subsection(tmp_path: Path):
    """Session-only evidence: Sources collapse has Sessions, no Documents heading."""
    vault = tmp_path / "vault"
    _write(
        vault / "wiki" / "entities" / "Alone.md",
        '---\ntitle: "Alone"\ntype: entity\n---\n\n# Alone\n\n## Key Facts\n- x\n',
    )
    _write(
        vault / "wiki" / "sources" / "s.md",
        (
            '---\ntitle: "S"\ntype: source\nproject: p\n'
            "source_file: raw/sessions/s.md\n---\n\n[[Alone]]\n"
        ),
    )
    _write(vault / "raw" / "sessions" / "s.md", "---\ntitle: s\n---\n\n[[Alone]]\n")
    out = tmp_path / "out"
    graph = build_topic_graph(vault / "wiki", min_sessions=1)
    written = build_topic_pages(graph, out, wiki_dir=vault / "wiki")
    topic = next(p for p in written if p.name == "alone.html")
    text = topic.read_text(encoding="utf-8")
    assert 'class="collapse-section topic-sources"' in text
    assert "<h3>Sessions</h3>" in text
    assert "<h3>Documents</h3>" not in text
    assert "provenance-sources" not in text


def test_render_session_sources_raw_when_wiki_summary_exists(tmp_path: Path):
    vault = _chain_vault(tmp_path, with_session_html=False)
    raw_name = "2026-01-01T12-00-demo-kickoff.md"
    path = vault / "raw" / "sessions" / raw_name
    meta = {
        "slug": "kickoff",
        "title": "Kickoff transcript",
        "project": "demo",
        "date": "2026-01-01",
    }
    out = render_session(path, meta, "hello", tmp_path / "site", "demo", vault=vault)
    text = out.read_text(encoding="utf-8")
    assert "<h2>Sources</h2>" in text
    assert 'href="../../sources/demo/2026-01-01T12-00-demo-kickoff.md"' in text
    assert 'target="_blank"' in text
    assert "(raw)" in text
    assert "entities/" not in text
    assert "concepts/" not in text


def test_render_session_no_sources_without_wiki_summary(tmp_path: Path):
    path = _write(
        tmp_path / "raw" / "sessions" / "orphan.md",
        '---\ntitle: "Orphan"\nproject: demo\n---\n\nbody\n',
    )
    out = render_session(
        path,
        {"slug": "orphan", "title": "Orphan", "project": "demo", "date": "2026-01-01"},
        "body",
        tmp_path / "site",
        "demo",
        vault=tmp_path,
    )
    text = out.read_text(encoding="utf-8")
    assert "<h2>Sources</h2>" not in text


# ─── document Sources (C1 / I1 / B5) ───────────────────────────────────────


def _doc_chain_vault(
    tmp_path: Path,
    *,
    raw_under_docs: str,
    with_doc_html: bool,
    project: str = "myproj",
) -> Path:
    """Wiki source + entity citing a raw/docs file; optional site HTML (+ md)."""
    vault = tmp_path / "vault"
    _write(
        vault / "raw" / "docs" / Path(raw_under_docs),
        (
            f'---\ntitle: "Note body"\ntype: source\n'
            f"project: {project}\n---\n\nraw body\n"
        ),
    )
    wiki_slug = Path(raw_under_docs).stem
    _write(
        vault / "wiki" / "sources" / f"{wiki_slug}.md",
        (
            f'---\ntitle: "Note summary"\ntype: source\n'
            f"project: {project}\n"
            f"source_file: raw/docs/{raw_under_docs}\n"
            "---\n\n## Summary\n\nAbout [[DemoDoc]].\n"
        ),
    )
    _write(
        vault / "wiki" / "entities" / "DemoDoc.md",
        (
            f'---\ntitle: "DemoDoc"\ntype: entity\nsources: [{wiki_slug}]\n'
            "last_updated: 2026-01-02\n---\n\n# DemoDoc\n\n"
            "## Key Facts\n- One fact.\n"
        ),
    )
    if with_doc_html:
        rel_html = Path(raw_under_docs).with_suffix(".html")
        _write(vault / "site" / "documents" / rel_html, "<html></html>\n")
        _write(
            vault / "site" / "documents" / Path(raw_under_docs),
            "copied md\n",
        )
    return vault


def test_sources_links_flat_doc_prefer_html_not_under_project(tmp_path: Path):
    """C1: flat raw/docs/note.md → documents/note.html (not documents/<project>/)."""
    vault = _doc_chain_vault(
        tmp_path, raw_under_docs="note.md", with_doc_html=True, project="myproj"
    )
    links = sources_links(vault, "wiki/entities/DemoDoc.md")
    assert len(links) == 1
    assert links[0].is_raw is False
    assert links[0].href == "documents/note.html"
    assert "documents/myproj/" not in links[0].href


def test_sources_links_nested_doc_prefer_html(tmp_path: Path):
    vault = _doc_chain_vault(
        tmp_path, raw_under_docs="dir/file.md", with_doc_html=True
    )
    links = sources_links(vault, "wiki/entities/DemoDoc.md")
    assert len(links) == 1
    assert links[0].href == "documents/dir/file.html"
    assert links[0].is_raw is False


def test_provenance_links_for_raw_doc_excludes_self_html_falls_back_to_md(
    tmp_path: Path,
):
    """I1: exclude document HTML → (raw) link to documents/<rel>.md sibling."""
    vault = _doc_chain_vault(
        tmp_path, raw_under_docs="note.md", with_doc_html=True, project="myproj"
    )
    links = provenance_links_for_raw(
        vault,
        "raw/docs/note.md",
        project="myproj",
        exclude_href="documents/note.html",
    )
    assert len(links) == 1
    assert links[0].is_raw is True
    assert links[0].href == "documents/note.md"
    html = format_sources_html(links, link_prefix="../")
    assert 'href="../documents/note.md"' in html
    assert 'target="_blank"' in html
    assert "(raw)" in html


def test_provenance_links_for_raw_nested_doc_exclude_fallback(tmp_path: Path):
    vault = _doc_chain_vault(
        tmp_path, raw_under_docs="dir/file.md", with_doc_html=True
    )
    links = provenance_links_for_raw(
        vault,
        "raw/docs/dir/file.md",
        exclude_href="documents/dir/file.html",
    )
    assert len(links) == 1
    assert links[0].is_raw is True
    assert links[0].href == "documents/dir/file.md"
