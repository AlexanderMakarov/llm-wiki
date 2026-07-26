"""Tests for the raw-documents site section: Home file tree,
``documents/`` pages, and the Recent page.

``llmwiki.raw_docs_site`` models ``raw/docs/**`` (the wiki-add layer);
``llmwiki.build`` renders it as ``index.html`` (tree browser),
``recent.html`` (newest documents), and one page per document file.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from llmwiki.build import render_index, render_recent, nav_bar
from llmwiki.raw_docs_site import (
    RawDocFile,
    build_tree,
    clean_chunk_title,
    count_docs_by_project,
    group_documents,
    render_document_pages,
    render_sidebar,
    render_sidebar_mount,
    scan_raw_docs,
    tree_to_dict,
    write_documents_tree,
)


def _write_doc(root: Path, rel: str, title: str, date: str,
               source: str = "https://example.com") -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        f'---\ntitle: "{title}"\ntype: source\ntags: [wiki-add, raw-doc]\n'
        f'date: {date}\nsource: "{source}"\n---\n\n# {title}\n\nBody text.\n',
        encoding="utf-8",
    )
    return p


@pytest.fixture
def docs_dir(tmp_path: Path) -> Path:
    """raw/docs with one root doc + one 3-chunk doc folder."""
    d = tmp_path / "raw" / "docs"
    _write_doc(d, "standalone.md", "Standalone Doc", "2026-07-01")
    for i in (1, 2, 3):
        _write_doc(
            d, f"runbook/runbook-0{i}.md",
            f"VPS Runbook (part {i}/3: Section {i})", "2026-06-24",
        )
    return d


def test_scan_finds_all_files_sorted(docs_dir: Path):
    files = scan_raw_docs(docs_dir)
    assert [f.rel.as_posix() for f in files] == [
        "runbook/runbook-01.md",
        "runbook/runbook-02.md",
        "runbook/runbook-03.md",
        "standalone.md",
    ]


def test_scan_skips_context_and_unsafe_files(docs_dir: Path):
    (docs_dir / "_context.md").write_text("folder meta", encoding="utf-8")
    evil = docs_dir / "a b"
    evil.mkdir()
    (evil / "x.md").write_text("unsafe dir name", encoding="utf-8")
    rels = {f.rel.as_posix() for f in scan_raw_docs(docs_dir)}
    assert "_context.md" not in rels
    assert not any(r.startswith("a b/") for r in rels)


def test_scan_missing_dir_is_empty(tmp_path: Path):
    assert scan_raw_docs(tmp_path / "nope") == []


def test_clean_chunk_title_strips_part_suffix():
    assert clean_chunk_title("VPS Runbook (part 1/11: Intro)") == "VPS Runbook"
    assert clean_chunk_title("Plain Title") == "Plain Title"


def test_group_documents_collapses_chunks_newest_first(docs_dir: Path):
    entries = group_documents(scan_raw_docs(docs_dir))
    assert [e.title for e in entries] == ["Standalone Doc", "VPS Runbook"]
    runbook = entries[1]
    assert runbook.parts == 3
    assert runbook.date == "2026-06-24"
    assert runbook.url == "documents/runbook/runbook-01.html"


def test_sidebar_marks_active_and_opens_folder(docs_dir: Path):
    files = scan_raw_docs(docs_dir)
    root = build_tree(files)
    active = files[1]  # runbook-02
    html_text = render_sidebar(root, active_rel=active.rel, link_prefix="../../")
    assert "<details open>" in html_text
    assert 'class="active"' in html_text
    assert 'href="../../documents/runbook/runbook-02.html"' in html_text


def test_tree_to_dict_and_write_documents_tree(docs_dir: Path, tmp_path: Path):
    files = scan_raw_docs(docs_dir)
    root = build_tree(files)
    data = tree_to_dict(root)
    assert any(f["rel"] == "standalone.md" for f in data["files"])
    runbook = next(f for f in data["folders"] if f["name"] == "runbook")
    assert {f["rel"] for f in runbook["files"]} == {
        "runbook/runbook-01.md",
        "runbook/runbook-02.md",
        "runbook/runbook-03.md",
    }
    out = tmp_path / "site"
    out.mkdir()
    path = write_documents_tree(root, out)
    assert path.name == "documents-tree.json"
    assert (out / "documents-tree.js").is_file()
    loaded = __import__("json").loads(path.read_text(encoding="utf-8"))
    assert loaded == data


def test_document_pages_use_mount_not_inline_tree(docs_dir: Path, tmp_path: Path):
    from llmwiki.build import (
        breadcrumbs_bar, md_to_html, page_foot, page_head,
    )
    out = tmp_path / "site"
    files = scan_raw_docs(docs_dir)
    root = build_tree(files)
    written = render_document_pages(
        files, root, out,
        md_to_html=md_to_html,
        page_head=page_head,
        nav_builder=lambda prefix: nav_bar("home", link_prefix=prefix),
        page_foot=lambda prefix: page_foot(js_prefix=prefix),
        breadcrumbs_bar=breadcrumbs_bar,
    )
    assert len(written) == 4
    page = (out / "documents" / "runbook" / "runbook-01.html").read_text(encoding="utf-8")
    assert 'data-doctree-mount' in page
    assert 'data-active-rel="runbook/runbook-01.md"' in page
    assert "doctree-loading" in page
    assert "Body text." in page
    # Must NOT inline every document link (that was the 350 MB blow-up).
    assert "runbook-02.html" not in page
    assert "standalone.html" not in page
    assert 'href="../../style.css"' in page
    mount = render_sidebar_mount(active_rel=files[0].rel, link_prefix="../../")
    assert "data-doctree-js" in mount
    assert "documents-tree.js" in mount


def test_render_index_is_tree_browser(docs_dir: Path, tmp_path: Path):
    out = tmp_path / "site"
    out.mkdir()
    files = scan_raw_docs(docs_dir)
    render_index(build_tree(files), group_documents(files), len(files), out)
    html_text = (out / "index.html").read_text(encoding="utf-8")
    # The Home pipeline State widget replaced the old queue-status cards.
    assert "Pipeline state" in html_text
    assert "llmwiki-state-widget" in html_text
    assert "Recent raw documents" in html_text
    assert "Standalone Doc" in html_text
    # The Commands collapsible moved into the state widget, which render/js.py
    # fills client-side — it is no longer emitted as static markup here.
    from llmwiki.render.js import JS
    assert 'detailsSection("Commands"' in JS
    assert "Open Raw browser" not in html_text


def test_render_index_empty_state(tmp_path: Path):
    out = tmp_path / "site"
    out.mkdir()
    render_index(build_tree([]), [], 0, out)
    html_text = (out / "index.html").read_text(encoding="utf-8")
    assert "No recent raw documents yet" in html_text


def test_render_recent_lists_docs_with_meta(docs_dir: Path, tmp_path: Path):
    out = tmp_path / "site"
    out.mkdir()
    files = scan_raw_docs(docs_dir)
    render_recent(group_documents(files), out)
    html_text = (out / "recent.html").read_text(encoding="utf-8")
    assert html_text.index("Standalone Doc") < html_text.index("VPS Runbook")
    assert "3 parts" in html_text
    assert "2026-07-01" in html_text


def test_nav_order_and_no_changelog():
    html_text = nav_bar(active="home")
    links = ["Home", "Raw", "Graph", "Projects", "Sessions", "Analytics", "Docs"]
    positions = [html_text.index(f">{label}</a>") for label in links]
    assert positions == sorted(positions)
    assert "changelog" not in html_text.lower()


def _doc(rel, project=None):
    """Helper to create a RawDocFile for testing."""
    from pathlib import PurePosixPath
    meta = {"project": project} if project else {}
    return RawDocFile(path=Path("/x"), rel=PurePosixPath(rel), meta=meta, body="")


def test_count_docs_by_project_uses_frontmatter_then_folder():
    files = [
        _doc("alpha/a.md", project="proj-x"),
        _doc("alpha/b.md", project="proj-x"),
        _doc("beta/c.md"),                 # no project → folder "beta"
        _doc("solo.md"),                   # no project, no folder → stem "solo"
    ]
    counts = count_docs_by_project(files)
    assert counts == {"proj-x": 2, "beta": 1, "solo": 1}
