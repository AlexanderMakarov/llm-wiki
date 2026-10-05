"""Tests for the raw-documents site section: Home file tree,
``documents/`` pages, and the Recent page.

``llmwiki.raw_docs_site`` models ``raw/docs/**`` (the wiki-add layer);
``llmwiki.build`` renders it as ``index.html`` (tree browser),
``recent.html`` (newest documents), and one page per document file.
"""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath

import pytest

from llmwiki.build import (
    breadcrumbs_bar,
    build_search_index,
    md_to_html,
    nav_bar,
    page_foot,
    page_head,
    render_index,
    render_recent,
)
from llmwiki.raw_docs_site import (
    RawDocFile,
    base_slug_from_stem,
    build_tree,
    clean_chunk_title,
    count_docs_by_project,
    group_documents,
    part_anchor_id,
    render_document_pages,
    render_sidebar,
    render_sidebar_mount,
    scan_raw_docs,
    strip_part_chrome,
    tree_to_dict,
    write_documents_tree,
)
from llmwiki.render.js import JS


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


def test_group_documents_single_file_root(docs_dir: Path):
    """Root-level lone file is one logical document with canonical flat URL."""
    entries = group_documents(scan_raw_docs(docs_dir))
    standalone = next(e for e in entries if e.title == "Standalone Doc")
    assert standalone.parts == 1
    assert standalone.id == "document:standalone"
    assert standalone.url == "documents/standalone.html"
    assert standalone.folder_parts == ()
    assert [f.rel.as_posix() for f in standalone.part_files] == ["standalone.md"]


def test_group_documents_multi_chunk_default_layout(docs_dir: Path):
    """Default add_doc layout: raw/docs/<slug>/<slug>-NN.md → one logical doc."""
    entries = group_documents(scan_raw_docs(docs_dir))
    assert [e.title for e in entries] == ["Standalone Doc", "VPS Runbook"]
    runbook = entries[1]
    assert runbook.parts == 3
    assert runbook.date == "2026-06-24"
    assert runbook.id == "document:runbook/runbook"
    assert runbook.url == "documents/runbook/runbook.html"
    assert runbook.folder_parts == ("runbook",)
    assert [f.rel.stem for f in runbook.part_files] == [
        "runbook-01", "runbook-02", "runbook-03",
    ]


def test_group_documents_two_docs_under_project_folder(tmp_path: Path):
    """--project folder with two distinct docs must not collapse into one (#305)."""
    d = tmp_path / "raw" / "docs"
    for i in (1, 2):
        _write_doc(
            d, f"acme/alpha-guide-0{i}.md",
            f"Alpha Guide (part {i}/2: Section {i})", "2026-08-01",
        )
    _write_doc(d, "acme/beta-notes.md", "Beta Notes", "2026-08-02")
    entries = group_documents(scan_raw_docs(d))
    by_id = {e.id: e for e in entries}
    assert set(by_id) == {
        "document:acme/alpha-guide",
        "document:acme/beta-notes",
    }
    alpha = by_id["document:acme/alpha-guide"]
    assert alpha.title == "Alpha Guide"
    assert alpha.parts == 2
    assert alpha.url == "documents/acme/alpha-guide.html"
    assert alpha.folder_parts == ("acme",)
    beta = by_id["document:acme/beta-notes"]
    assert beta.title == "Beta Notes"
    assert beta.parts == 1
    assert beta.url == "documents/acme/beta-notes.html"


def test_group_documents_cleaned_titles(tmp_path: Path):
    d = tmp_path / "raw" / "docs"
    _write_doc(
        d, "guide/guide-01.md",
        "Deploy Guide (part 1/2: Intro)", "2026-05-01",
    )
    _write_doc(
        d, "guide/guide-02.md",
        "Deploy Guide (part 2/2: Finish)", "2026-05-01",
    )
    entries = group_documents(scan_raw_docs(d))
    assert len(entries) == 1
    assert entries[0].title == "Deploy Guide"
    assert "(" not in entries[0].title


def test_base_slug_from_stem():
    assert base_slug_from_stem("runbook-01") == "runbook"
    assert base_slug_from_stem("runbook") == "runbook"
    # Collision suffix from add_doc._dedupe is unpadded — not a chunk index.
    assert base_slug_from_stem("runbook-2") == "runbook-2"


def test_sidebar_marks_active_and_opens_folder(docs_dir: Path):
    files = scan_raw_docs(docs_dir)
    root = build_tree(files)
    active = files[1]  # runbook-02
    html_text = render_sidebar(root, active_rel=active.rel, link_prefix="../../")
    assert "<details open>" in html_text
    assert 'class="active"' in html_text
    assert 'href="../../documents/runbook/runbook-02.html"' in html_text


def test_tree_to_dict_and_write_documents_tree(docs_dir: Path, tmp_path: Path):
    """Tree leaves are logical docs — one leaf for a multi-part runbook (#305)."""
    files = scan_raw_docs(docs_dir)
    entries = group_documents(files)
    data = tree_to_dict(entries)
    assert any(f["rel"] == "standalone.md" for f in data["files"])
    standalone = next(f for f in data["files"] if f["rel"] == "standalone.md")
    assert standalone["id"] == "document:standalone"
    assert standalone["label"] == "Standalone Doc"
    assert standalone["href"] == "documents/standalone.html"
    runbook = next(f for f in data["folders"] if f["name"] == "runbook")
    assert len(runbook["files"]) == 1
    leaf = runbook["files"][0]
    assert leaf == {
        "id": "document:runbook/runbook",
        "label": "VPS Runbook",
        "href": "documents/runbook/runbook.html",
        "rel": "runbook/runbook-01.md",
    }
    out = tmp_path / "site"
    out.mkdir()
    path = write_documents_tree(entries, out)
    assert path.name == "documents-tree.json"
    assert (out / "documents-tree.js").is_file()
    loaded = __import__("json").loads(path.read_text(encoding="utf-8"))
    assert loaded == data


def test_document_pages_use_mount_not_inline_tree(docs_dir: Path, tmp_path: Path):
    out = tmp_path / "site"
    files = scan_raw_docs(docs_dir)
    root = build_tree(files)
    entries = group_documents(files)
    written = render_document_pages(
        entries, root, out,
        md_to_html=md_to_html,
        page_head=page_head,
        nav_builder=lambda prefix: nav_bar("home", link_prefix=prefix),
        page_foot=lambda prefix: page_foot(js_prefix=prefix),
        breadcrumbs_bar=breadcrumbs_bar,
    )
    # 2 canonical pages + 3 part stubs for the runbook.
    assert len(written) == 5
    page = (out / "documents" / "runbook" / "runbook.html").read_text(encoding="utf-8")
    assert 'data-doctree-mount' in page
    assert 'data-active-rel="runbook/runbook-01.md"' in page
    assert "doctree-loading" in page
    assert "Body text." in page
    # Sibling .md copy for FR2 (raw) Sources fallback (#122).
    assert (out / "documents" / "runbook" / "runbook-01.md").is_file()
    assert (out / "documents" / "standalone.md").is_file()
    # Must NOT inline every document link (that was the 350 MB blow-up).
    assert "runbook-02.html" not in page
    assert "standalone.html" not in page
    assert 'href="../../style.css"' in page
    mount = render_sidebar_mount(active_rel=files[0].rel, link_prefix="../../")
    assert "data-doctree-js" in mount
    assert "documents-tree.js" in mount


def test_strip_part_chrome_removes_degenerate_empty_bold_breadcrumb():
    """Older chunks sometimes have ``> Part i of N of ****.`` (empty title)."""
    body = "> Part 3 of 4 of ****.\n\n## Experience\n\nDid things.\n"
    out = strip_part_chrome(
        body,
        doc_title="Example Curriculum Vitae (extended)",
        part_title="Example Curriculum Vitae (extended) (part 3/4)",
    )
    assert "Part 3 of 4" not in out
    assert "****" not in out
    assert "## Experience" in out


def test_strip_part_chrome_removes_breadcrumb_and_title_h1():
    body = (
        "> Part 1 of 3 of **VPS Runbook** — Intro.\n\n"
        "# VPS Runbook (part 1/3: Intro)\n\n"
        "Real section body.\n"
    )
    out = strip_part_chrome(
        body,
        doc_title="VPS Runbook",
        part_title="VPS Runbook (part 1/3: Intro)",
    )
    assert "Part 1 of" not in out
    assert "VPS Runbook (part 1/3: Intro)" not in out
    assert "Real section body." in out


def test_unified_page_assembles_parts_and_stubs_redirect(docs_dir: Path, tmp_path: Path):
    """Multi-part vault → one canonical HTML; part URLs are stubs (#305 Slice 2)."""
    out = tmp_path / "site"
    files = scan_raw_docs(docs_dir)
    # Give each runbook part distinct body text so assembly is observable.
    for f in files:
        if f.rel.parts[0] != "runbook":
            continue
        idx = f.rel.stem.split("-")[-1]
        f.body = (
            f"> Part {int(idx)} of 3 of **VPS Runbook** — Section {int(idx)}.\n\n"
            f"# VPS Runbook (part {int(idx)}/3: Section {int(idx)})\n\n"
            f"Runbook part {idx} unique text.\n"
        )
    entries = group_documents(files)
    render_document_pages(
        entries, build_tree(files), out,
        md_to_html=md_to_html,
        page_head=page_head,
        nav_builder=lambda prefix: nav_bar("raw", link_prefix=prefix),
        page_foot=lambda prefix: page_foot(js_prefix=prefix),
        breadcrumbs_bar=breadcrumbs_bar,
    )

    canonical = (out / "documents" / "runbook" / "runbook.html").read_text(
        encoding="utf-8",
    )
    assert "Runbook part 01 unique text." in canonical
    assert "Runbook part 02 unique text." in canonical
    assert "Runbook part 03 unique text." in canonical
    assert 'id="part-01"' in canonical
    assert 'id="part-02"' in canonical
    assert 'id="part-03"' in canonical
    assert "Part 1 of 3 of" not in canonical
    assert "doctree-loading" in canonical

    stub = (out / "documents" / "runbook" / "runbook-02.html").read_text(
        encoding="utf-8",
    )
    assert "Runbook part 02 unique text." not in stub
    assert 'http-equiv="refresh"' in stub
    assert 'url=runbook.html#part-02' in stub
    assert 'href="runbook.html#part-02"' in stub
    assert "location.replace" in stub
    assert part_anchor_id(2) == "part-02"

    single = (out / "documents" / "standalone.html").read_text(encoding="utf-8")
    assert "Body text." in single
    assert 'data-doctree-mount' in single
    # Single-file docs have no -NN stub sibling.
    assert not (out / "documents" / "standalone-01.html").exists()


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


def _iter_tree_leaves(node: dict) -> list[dict]:
    """Flatten documents-tree.json leaves depth-first."""
    leaves = list(node.get("files") or [])
    for folder in node.get("folders") or []:
        leaves.extend(_iter_tree_leaves(folder))
    return leaves


def test_search_index_documents_match_tree_leaves(docs_dir: Path, tmp_path: Path):
    """search-index document set ≡ documents-tree leaves (ids/titles/hrefs)."""
    files = scan_raw_docs(docs_dir)
    entries = group_documents(files)
    out = tmp_path / "site"
    out.mkdir()
    write_documents_tree(entries, out)
    build_search_index([], {}, out, doc_entries=entries)

    tree = json.loads((out / "documents-tree.json").read_text(encoding="utf-8"))
    index = json.loads((out / "search-index.json").read_text(encoding="utf-8"))
    docs = [e for e in index["entries"] if e.get("type") == "document"]

    tree_set = {
        (leaf["id"], leaf["label"], leaf["href"]) for leaf in _iter_tree_leaves(tree)
    }
    index_set = {(e["id"], e["title"], e["url"]) for e in docs}
    assert tree_set == index_set
    assert len(docs) == len(entries) == 2


def test_multipart_doc_is_one_search_palette_entry(docs_dir: Path, tmp_path: Path):
    """A 3-chunk runbook yields one type:document meta entry, not three."""
    files = scan_raw_docs(docs_dir)
    entries = group_documents(files)
    out = tmp_path / "site"
    out.mkdir()
    build_search_index([], {}, out, doc_entries=entries)

    index = json.loads((out / "search-index.json").read_text(encoding="utf-8"))
    docs = [e for e in index["entries"] if e.get("type") == "document"]
    by_id = {e["id"]: e for e in docs}
    assert "document:runbook/runbook" in by_id
    runbook = by_id["document:runbook/runbook"]
    assert runbook["title"] == "VPS Runbook"
    assert runbook["url"] == "documents/runbook/runbook.html"
    assert not any(
        e["id"].startswith("document:runbook/runbook-0") for e in docs
    )
    # Assembled body includes later-part text (not only part 1).
    assert "Body text." in runbook["body"]
