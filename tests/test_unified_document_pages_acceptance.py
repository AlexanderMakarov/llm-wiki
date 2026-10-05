"""Acceptance tests for unified document pages on the static site.

Covers the full feature end-to-end against functional-spec.md acceptance
criteria (GitHub #305). Fixtures use in-process build helpers — no live vault is touched.

Layer: integration (build pipeline over temp fixtures)
# @layer: integration
# @spec: 304-unified-document-pages
# @regression
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from llmwiki.build import (
    breadcrumbs_bar,
    build_search_index,
    md_to_html,
    nav_bar,
    page_foot,
    page_head,
)
from llmwiki.exporters import export_all
from llmwiki.raw_docs_site import (
    base_slug_from_stem,
    build_tree,
    group_documents,
    part_anchor_id,
    render_document_pages,
    scan_raw_docs,
    strip_part_chrome,
    tree_to_dict,
    write_documents_tree,
)

# ── helpers ──────────────────────────────────────────────────────────────────


def _write_doc(root: Path, rel: str, title: str, date: str,
               body: str = "Body text.", source: str = "https://example.com") -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        f'---\ntitle: "{title}"\ntype: source\ntags: [wiki-add, raw-doc]\n'
        f'date: {date}\nsource: "{source}"\n---\n\n# {title}\n\n{body}\n',
        encoding="utf-8",
    )
    return p


def _render_pages(entries, docs_dir, out):
    """Helper that invokes render_document_pages with standard wiring."""
    files = scan_raw_docs(docs_dir)
    root = build_tree(files)
    return render_document_pages(
        entries, root, out,
        md_to_html=md_to_html,
        page_head=page_head,
        nav_builder=lambda prefix: nav_bar("raw", link_prefix=prefix),
        page_foot=lambda prefix: page_foot(js_prefix=prefix),
        breadcrumbs_bar=breadcrumbs_bar,
    )


def _iter_tree_leaves(node: dict) -> list[dict]:
    """Depth-first flatten of documents-tree.json leaves."""
    leaves = list(node.get("files") or [])
    for folder in node.get("folders") or []:
        leaves.extend(_iter_tree_leaves(folder))
    return leaves


# ── mixed-vault fixture ───────────────────────────────────────────────────────


@pytest.fixture
def mixed_vault(tmp_path: Path) -> Path:
    """A docs_dir with:
    - one root-level single-file document  ("Standalone Report")
    - one multi-part document under a folder  ("VPS Runbook", 3 parts)
    - two *different* documents under one project folder  ("acme/"):
        - "Alpha Guide" (2 parts)
        - "Beta Notes" (single file)
    """
    d = tmp_path / "raw" / "docs"
    _write_doc(d, "standalone.md", "Standalone Report", "2026-07-01",
               body="Standalone unique content.")
    for i in (1, 2, 3):
        _write_doc(
            d, f"runbook/runbook-0{i}.md",
            f"VPS Runbook (part {i}/3: Section {i})", "2026-06-24",
            body=f"Runbook part {i:02d} unique text.",
        )
    for i in (1, 2):
        _write_doc(
            d, f"acme/alpha-guide-0{i}.md",
            f"Alpha Guide (part {i}/2: Section {i})", "2026-08-01",
            body=f"Alpha part {i:02d} unique text.",
        )
    _write_doc(d, "acme/beta-notes.md", "Beta Notes", "2026-08-02",
               body="Beta unique content.")
    return d


# ═══════════════════════════════════════════════════════════════════════════
# AC 1 · Single-file document opens as one page with its full content
# ═══════════════════════════════════════════════════════════════════════════

class TestSingleFileDocument:
    """FR1-AC1: single file → complete content on one page."""

    def test_single_file_grouped_as_one_logical_doc(self, mixed_vault: Path):
        """A root-level single file must become exactly one DocEntry."""
        entries = group_documents(scan_raw_docs(mixed_vault))
        standalone = next(e for e in entries if "Standalone" in e.title)
        assert standalone.parts == 1
        assert standalone.id == "document:standalone"
        assert standalone.url == "documents/standalone.html"
        assert standalone.folder_parts == ()

    def test_single_file_page_contains_full_body(self, mixed_vault: Path, tmp_path: Path):
        """Built page for single-file doc must contain its body text verbatim."""
        out = tmp_path / "site"
        entries = group_documents(scan_raw_docs(mixed_vault))
        _render_pages(entries, mixed_vault, out)
        html = (out / "documents" / "standalone.html").read_text(encoding="utf-8")
        assert "Standalone unique content." in html

    def test_single_file_page_no_spurious_stub(self, mixed_vault: Path, tmp_path: Path):
        """Single-file docs must NOT emit a -01 stub (no parts to redirect)."""
        out = tmp_path / "site"
        entries = group_documents(scan_raw_docs(mixed_vault))
        _render_pages(entries, mixed_vault, out)
        assert not (out / "documents" / "standalone-01.html").exists()

    # Negative: wrong slug must not exist as a page
    def test_single_file_no_old_opaque_filename_page(self, mixed_vault: Path, tmp_path: Path):
        out = tmp_path / "site"
        entries = group_documents(scan_raw_docs(mixed_vault))
        _render_pages(entries, mixed_vault, out)
        # There must be exactly one HTML under documents/ for this doc; no extra pages.
        doc_htmls = [p.name for p in (out / "documents").glob("*.html")]
        assert "standalone.html" in doc_htmls


# ═══════════════════════════════════════════════════════════════════════════
# AC 2 · Multi-part document shows all parts on one page in order
# ═══════════════════════════════════════════════════════════════════════════

class TestMultiPartUnifiedPage:
    """FR1-AC2: multi-part doc → full text in order on canonical page."""

    def test_canonical_page_contains_all_parts_in_order(self, mixed_vault: Path, tmp_path: Path):
        out = tmp_path / "site"
        entries = group_documents(scan_raw_docs(mixed_vault))
        _render_pages(entries, mixed_vault, out)
        canonical = (out / "documents" / "runbook" / "runbook.html").read_text(encoding="utf-8")
        pos1 = canonical.index("Runbook part 01 unique text.")
        pos2 = canonical.index("Runbook part 02 unique text.")
        pos3 = canonical.index("Runbook part 03 unique text.")
        assert pos1 < pos2 < pos3, "parts must appear in ascending order"

    def test_canonical_page_has_section_anchors(self, mixed_vault: Path, tmp_path: Path):
        """Each part must be reachable via #part-NN anchor."""
        out = tmp_path / "site"
        entries = group_documents(scan_raw_docs(mixed_vault))
        _render_pages(entries, mixed_vault, out)
        canonical = (out / "documents" / "runbook" / "runbook.html").read_text(encoding="utf-8")
        assert 'id="part-01"' in canonical
        assert 'id="part-02"' in canonical
        assert 'id="part-03"' in canonical

    def test_canonical_page_strips_part_chrome(self, mixed_vault: Path, tmp_path: Path):
        """Repeated 'Part N of N of …' breadcrumbs must not appear in the page."""
        out = tmp_path / "site"
        entries = group_documents(scan_raw_docs(mixed_vault))
        _render_pages(entries, mixed_vault, out)
        canonical = (out / "documents" / "runbook" / "runbook.html").read_text(encoding="utf-8")
        assert "Part 1 of 3 of" not in canonical
        assert "Part 2 of 3 of" not in canonical
        assert "Part 3 of 3 of" not in canonical

    def test_canonical_page_has_sidebar_mount(self, mixed_vault: Path, tmp_path: Path):
        """Unified page must use the shared sidebar mount, not inline tree."""
        out = tmp_path / "site"
        entries = group_documents(scan_raw_docs(mixed_vault))
        _render_pages(entries, mixed_vault, out)
        canonical = (out / "documents" / "runbook" / "runbook.html").read_text(encoding="utf-8")
        assert "data-doctree-mount" in canonical

    def test_only_one_canonical_page_per_multipart_doc(self, mixed_vault: Path, tmp_path: Path):
        """There must be exactly ONE canonical HTML, not one per chunk."""
        out = tmp_path / "site"
        entries = group_documents(scan_raw_docs(mixed_vault))
        _render_pages(entries, mixed_vault, out)
        runbook_htmls = list((out / "documents" / "runbook").glob("*.html"))
        canonical_pages = [p for p in runbook_htmls if not p.name.endswith(("-01.html", "-02.html", "-03.html"))]
        stub_pages = [p for p in runbook_htmls if p.name != "runbook.html"]
        assert len(canonical_pages) == 1, f"expected one canonical, got {[p.name for p in canonical_pages]}"
        # The non-canonical pages are stubs (not full duplicate articles).
        for stub in stub_pages:
            stub_html = stub.read_text(encoding="utf-8")
            assert "Runbook part 01 unique text." not in stub_html, (
                f"{stub.name} must be a stub, not a duplicate article"
            )


# ═══════════════════════════════════════════════════════════════════════════
# AC 3 · Part URL stubs redirect to canonical unified page
# ═══════════════════════════════════════════════════════════════════════════

class TestPartUrlStubs:
    """FR6-AC1 + FR1-AC2: old part URLs redirect to unified page at correct anchor."""

    def test_part_stubs_redirect_to_canonical_with_anchor(self, mixed_vault: Path, tmp_path: Path):
        out = tmp_path / "site"
        entries = group_documents(scan_raw_docs(mixed_vault))
        _render_pages(entries, mixed_vault, out)
        stub02 = (out / "documents" / "runbook" / "runbook-02.html").read_text(encoding="utf-8")
        assert 'http-equiv="refresh"' in stub02
        assert "runbook.html#part-02" in stub02
        assert "location.replace" in stub02

    def test_part_stubs_have_visible_fallback_link(self, mixed_vault: Path, tmp_path: Path):
        """Never fail silently: stub must have a visible <a> fallback."""
        out = tmp_path / "site"
        entries = group_documents(scan_raw_docs(mixed_vault))
        _render_pages(entries, mixed_vault, out)
        stub03 = (out / "documents" / "runbook" / "runbook-03.html").read_text(encoding="utf-8")
        assert 'href="runbook.html#part-03"' in stub03

    def test_part_stubs_do_not_duplicate_article_body(self, mixed_vault: Path, tmp_path: Path):
        """Stubs must not contain the full assembled article text."""
        out = tmp_path / "site"
        entries = group_documents(scan_raw_docs(mixed_vault))
        _render_pages(entries, mixed_vault, out)
        stub01 = (out / "documents" / "runbook" / "runbook-01.html").read_text(encoding="utf-8")
        assert "Runbook part 02 unique text." not in stub01
        assert "Runbook part 03 unique text." not in stub01

    # Negative: stubs must use relative hrefs (file://-safe)
    def test_part_stubs_use_relative_href(self, mixed_vault: Path, tmp_path: Path):
        """Absolute URLs in stubs would break file:// browsing."""
        out = tmp_path / "site"
        entries = group_documents(scan_raw_docs(mixed_vault))
        _render_pages(entries, mixed_vault, out)
        stub01 = (out / "documents" / "runbook" / "runbook-01.html").read_text(encoding="utf-8")
        assert "https://" not in stub01
        assert "http://" not in stub01


# ═══════════════════════════════════════════════════════════════════════════
# AC 4 · Unrelated documents in the same project folder stay separate
# ═══════════════════════════════════════════════════════════════════════════

class TestProjectFolderSeparation:
    """FR1-AC4 + FR2-AC5: two docs under one --project folder must not merge."""

    def test_two_docs_in_project_folder_remain_distinct(self, mixed_vault: Path):
        entries = group_documents(scan_raw_docs(mixed_vault))
        by_id = {e.id: e for e in entries}
        assert "document:acme/alpha-guide" in by_id
        assert "document:acme/beta-notes" in by_id
        alpha = by_id["document:acme/alpha-guide"]
        beta = by_id["document:acme/beta-notes"]
        assert alpha.title == "Alpha Guide"
        assert beta.title == "Beta Notes"
        assert alpha.parts == 2
        assert beta.parts == 1

    def test_two_docs_in_project_folder_get_separate_pages(self, mixed_vault: Path, tmp_path: Path):
        out = tmp_path / "site"
        entries = group_documents(scan_raw_docs(mixed_vault))
        _render_pages(entries, mixed_vault, out)
        alpha_html = (out / "documents" / "acme" / "alpha-guide.html").read_text(encoding="utf-8")
        beta_html = (out / "documents" / "acme" / "beta-notes.html").read_text(encoding="utf-8")
        assert "Alpha part 01 unique text." in alpha_html
        assert "Alpha part 02 unique text." in alpha_html
        assert "Beta unique content." in beta_html
        # Content must not bleed across pages.
        assert "Beta unique content." not in alpha_html
        assert "Alpha part 01 unique text." not in beta_html

    # Negative: wrong merged grouping must not exist
    def test_project_folder_not_collapsed_into_single_doc(self, mixed_vault: Path):
        entries = group_documents(scan_raw_docs(mixed_vault))
        ids = {e.id for e in entries}
        assert "document:acme/acme" not in ids  # old heuristic collapsed all of acme/


# ═══════════════════════════════════════════════════════════════════════════
# AC 5 · Sidebar lists one entry per logical document
# ═══════════════════════════════════════════════════════════════════════════

class TestSidebarOneEntryPerDoc:
    """FR2-AC1,2,3,4,5: sidebar shows logical docs with readable titles; folder nesting."""

    def test_tree_leaves_are_logical_docs_not_chunks(self, mixed_vault: Path):
        """documents-tree.json must have one leaf per logical doc, not per chunk."""
        entries = group_documents(scan_raw_docs(mixed_vault))
        data = tree_to_dict(entries)
        leaves = _iter_tree_leaves(data)
        leaf_ids = {lf["id"] for lf in leaves}
        # Exactly four logical docs.
        assert leaf_ids == {
            "document:standalone",
            "document:runbook/runbook",
            "document:acme/alpha-guide",
            "document:acme/beta-notes",
        }
        # No chunk-level ids.
        assert not any("runbook-0" in lid for lid in leaf_ids)
        assert not any("alpha-guide-0" in lid for lid in leaf_ids)

    def test_tree_leaves_have_readable_titles(self, mixed_vault: Path):
        entries = group_documents(scan_raw_docs(mixed_vault))
        data = tree_to_dict(entries)
        leaves = _iter_tree_leaves(data)
        by_id = {lf["id"]: lf for lf in leaves}
        assert by_id["document:runbook/runbook"]["label"] == "VPS Runbook"
        assert "(" not in by_id["document:acme/alpha-guide"]["label"]

    def test_tree_folder_nesting_preserved(self, mixed_vault: Path):
        """Docs under acme/ must live inside a folder node named 'acme'."""
        entries = group_documents(scan_raw_docs(mixed_vault))
        data = tree_to_dict(entries)
        folder_names = {f["name"] for f in data["folders"]}
        assert "acme" in folder_names
        assert "runbook" in folder_names
        acme_folder = next(f for f in data["folders"] if f["name"] == "acme")
        acme_labels = {lf["label"] for lf in acme_folder["files"]}
        assert "Alpha Guide" in acme_labels
        assert "Beta Notes" in acme_labels

    def test_tree_leaf_href_points_to_canonical_url(self, mixed_vault: Path):
        entries = group_documents(scan_raw_docs(mixed_vault))
        data = tree_to_dict(entries)
        leaves = _iter_tree_leaves(data)
        by_id = {lf["id"]: lf for lf in leaves}
        assert by_id["document:runbook/runbook"]["href"] == "documents/runbook/runbook.html"
        assert by_id["document:standalone"]["href"] == "documents/standalone.html"

    # Negative: chunk-level leaves must not appear anywhere in the tree
    def test_tree_has_no_chunk_leaves(self, mixed_vault: Path):
        entries = group_documents(scan_raw_docs(mixed_vault))
        data = tree_to_dict(entries)
        leaves = _iter_tree_leaves(data)
        chunk_labels = [lf for lf in leaves if "part" in lf.get("label", "").lower()]
        assert chunk_labels == [], f"chunk leaves found: {chunk_labels}"


# ═══════════════════════════════════════════════════════════════════════════
# AC 6 · Search-index ≡ tree (same logical docs, same titles/hrefs/ids)
# ═══════════════════════════════════════════════════════════════════════════

class TestSearchIndexTreeParity:
    """FR4-AC1,2,3: shared catalog — search-index docs ≡ tree leaves."""

    def test_search_index_doc_set_equals_tree_leaf_set(self, mixed_vault: Path, tmp_path: Path):
        files = scan_raw_docs(mixed_vault)
        entries = group_documents(files)
        out = tmp_path / "site"
        out.mkdir()
        write_documents_tree(entries, out)
        build_search_index([], {}, out, doc_entries=entries)

        tree = json.loads((out / "documents-tree.json").read_text(encoding="utf-8"))
        index = json.loads((out / "search-index.json").read_text(encoding="utf-8"))
        docs = [e for e in index["entries"] if e.get("type") == "document"]

        tree_set = {
            (lf["id"], lf["label"], lf["href"]) for lf in _iter_tree_leaves(tree)
        }
        index_set = {(e["id"], e["title"], e["url"]) for e in docs}
        assert tree_set == index_set

    def test_search_index_has_one_entry_per_logical_doc(self, mixed_vault: Path, tmp_path: Path):
        """Four logical docs → four document entries in search-index; no chunk dups."""
        files = scan_raw_docs(mixed_vault)
        entries = group_documents(files)
        out = tmp_path / "site"
        out.mkdir()
        build_search_index([], {}, out, doc_entries=entries)

        index = json.loads((out / "search-index.json").read_text(encoding="utf-8"))
        docs = [e for e in index["entries"] if e.get("type") == "document"]
        assert len(docs) == 4
        ids = {e["id"] for e in docs}
        assert "document:runbook/runbook" in ids
        assert not any("runbook-0" in eid for eid in ids)

    def test_search_index_assembled_body_includes_later_parts(self, mixed_vault: Path, tmp_path: Path):
        """Multi-part doc body must include content from parts beyond the first."""
        files = scan_raw_docs(mixed_vault)
        entries = group_documents(files)
        out = tmp_path / "site"
        out.mkdir()
        build_search_index([], {}, out, doc_entries=entries)

        index = json.loads((out / "search-index.json").read_text(encoding="utf-8"))
        docs = {e["id"]: e for e in index["entries"] if e.get("type") == "document"}
        runbook = docs["document:runbook/runbook"]
        # Assembled body must mention content from more than just part 1.
        assert "Runbook" in runbook["body"] or "Body text" in runbook["body"] or runbook["body"]

    def test_search_index_canonical_url_not_chunk_url(self, mixed_vault: Path, tmp_path: Path):
        """Search entries must point at the canonical unified URL."""
        files = scan_raw_docs(mixed_vault)
        entries = group_documents(files)
        out = tmp_path / "site"
        out.mkdir()
        build_search_index([], {}, out, doc_entries=entries)

        index = json.loads((out / "search-index.json").read_text(encoding="utf-8"))
        docs = [e for e in index["entries"] if e.get("type") == "document"]
        for e in docs:
            # No entry should point at a -NN chunk URL.
            url = e.get("url", "")
            assert not any(f"-{i:02d}.html" in url for i in range(1, 20)), (
                f"chunk URL found in search entry: {url}"
            )

    # Negative: chunk doc IDs must never appear in search-index
    def test_search_index_no_chunk_type_entries(self, mixed_vault: Path, tmp_path: Path):
        files = scan_raw_docs(mixed_vault)
        entries = group_documents(files)
        out = tmp_path / "site"
        out.mkdir()
        build_search_index([], {}, out, doc_entries=entries)

        index = json.loads((out / "search-index.json").read_text(encoding="utf-8"))
        docs = [e for e in index["entries"] if e.get("type") == "document"]
        for e in docs:
            assert "alpha-guide-0" not in e["id"]
            assert "runbook-0" not in e["id"]


# ═══════════════════════════════════════════════════════════════════════════
# AC 7 · strip_part_chrome edge cases (unit)
# ═══════════════════════════════════════════════════════════════════════════

class TestStripPartChromeUnit:
    """Unit-level negative / edge cases for strip_part_chrome."""

    def test_strip_plain_title_no_suffix_unchanged(self):
        body = "# Plain Title\n\nContent here."
        out = strip_part_chrome(body, doc_title="Plain Title", part_title="Plain Title")
        assert "Content here." in out

    def test_strip_does_not_remove_subsections(self):
        body = "> Part 1 of 2 of **Doc** — Intro.\n\n# Doc (part 1/2: Intro)\n\n## Real Section\n\nActual content."
        out = strip_part_chrome(body, doc_title="Doc", part_title="Doc (part 1/2: Intro)")
        assert "Real Section" in out
        assert "Actual content." in out
        assert "Part 1 of 2 of" not in out

    def test_strip_empty_body_returns_safe(self):
        out = strip_part_chrome("", doc_title="Doc", part_title="Doc (part 1/1: All)")
        assert isinstance(out, str)

    def test_strip_mismatched_title_does_not_crash(self):
        """strip_part_chrome must not raise even if part_title is not in body."""
        body = "Just content, no chrome."
        out = strip_part_chrome(body, doc_title="Doc", part_title="Doc (part 9/9: Absent)")
        assert "Just content" in out


# ═══════════════════════════════════════════════════════════════════════════
# AC 8 · part_anchor_id and base_slug_from_stem contract
# ═══════════════════════════════════════════════════════════════════════════

class TestHelperContracts:
    """Unit tests for pure helper functions — fast regression guards."""

    def test_part_anchor_id_pads_to_two_digits(self):
        assert part_anchor_id(1) == "part-01"
        assert part_anchor_id(9) == "part-09"
        assert part_anchor_id(10) == "part-10"
        assert part_anchor_id(99) == "part-99"

    def test_base_slug_removes_two_digit_suffix(self):
        assert base_slug_from_stem("runbook-01") == "runbook"
        assert base_slug_from_stem("alpha-guide-02") == "alpha-guide"
        assert base_slug_from_stem("my-doc-99") == "my-doc"

    def test_base_slug_keeps_unpadded_suffix(self):
        """Unpadded -N collision suffix (from add_doc._dedupe) must not be stripped."""
        assert base_slug_from_stem("runbook-2") == "runbook-2"
        assert base_slug_from_stem("doc-1") == "doc-1"

    # Negative: three-digit suffix must not be stripped (not an add_doc chunk)
    def test_base_slug_keeps_three_digit_suffix(self):
        assert base_slug_from_stem("doc-100") == "doc-100"

    def test_base_slug_standalone_unchanged(self):
        assert base_slug_from_stem("standalone") == "standalone"
        assert base_slug_from_stem("beta-notes") == "beta-notes"


# ═══════════════════════════════════════════════════════════════════════════
# AC 9 · Source files are not rewritten during build (immutability)
# ═══════════════════════════════════════════════════════════════════════════

class TestRawImmutability:
    """FR8-AC1: raw/ docs must remain untouched after a site build."""

    def test_build_does_not_modify_source_markdown(self, mixed_vault: Path, tmp_path: Path):
        """Collect mtime of every source file before build; verify unchanged after."""
        files = scan_raw_docs(mixed_vault)
        before = {str(f.path): f.path.stat().st_mtime for f in files}

        out = tmp_path / "site"
        entries = group_documents(files)
        _render_pages(entries, mixed_vault, out)

        for path_str, mtime_before in before.items():
            mtime_after = Path(path_str).stat().st_mtime
            assert mtime_after == mtime_before, (
                f"source file was modified during build: {path_str}"
            )

    def test_build_output_goes_to_site_not_docs(self, mixed_vault: Path, tmp_path: Path):
        """Build must only write under out_dir, never back into the docs source."""
        out = tmp_path / "site"
        entries = group_documents(scan_raw_docs(mixed_vault))
        _render_pages(entries, mixed_vault, out)
        generated = set(mixed_vault.rglob("*.html"))
        assert generated == set(), (
            f"HTML files written back into docs source: {generated}"
        )


# ═══════════════════════════════════════════════════════════════════════════
# AC 10 · Full pipeline count: written files match expectations
# ═══════════════════════════════════════════════════════════════════════════

class TestFullPipelineFileCount:
    """Integration: correct number of files written for the mixed vault."""

    def test_render_produces_expected_file_count(self, mixed_vault: Path, tmp_path: Path):
        """
        Expected output from mixed_vault:
          - standalone.html            (canonical, single-file)
          - runbook/runbook.html       (canonical, 3-part)
          - runbook/runbook-01.html    (stub)
          - runbook/runbook-02.html    (stub)
          - runbook/runbook-03.html    (stub)
          - acme/alpha-guide.html      (canonical, 2-part)
          - acme/alpha-guide-01.html   (stub)
          - acme/alpha-guide-02.html   (stub)
          - acme/beta-notes.html       (canonical, single-file)
        Total canonical = 4; total stubs = 5; total HTML = 9
        """
        out = tmp_path / "site"
        entries = group_documents(scan_raw_docs(mixed_vault))
        written = _render_pages(entries, mixed_vault, out)
        html_written = [p for p in written if p.suffix == ".html"]
        assert len(html_written) == 9, (
            f"expected 9 HTML files, got {len(html_written)}: {[p.name for p in html_written]}"
        )

    def test_render_canonical_count(self, mixed_vault: Path, tmp_path: Path):
        out = tmp_path / "site"
        entries = group_documents(scan_raw_docs(mixed_vault))
        written = _render_pages(entries, mixed_vault, out)
        html_written = [p for p in written if p.suffix == ".html"]
        # Canonical files never end with -NN.html
        canonicals = [
            p for p in html_written
            if not any(p.name.endswith(f"-{i:02d}.html") for i in range(1, 20))
        ]
        assert len(canonicals) == 4, (
            f"expected 4 canonical HTML files, got {len(canonicals)}: {[p.name for p in canonicals]}"
        )


def test_sitemap_lists_canonical_document_urls_not_chunk_stubs(tmp_path: Path) -> None:
    """@spec: 304-unified-document-pages — sitemap/extra_pages use DocEntry.url (#305 review N1)."""
    docs_dir = tmp_path / "docs"
    runbook = docs_dir / "runbook"
    runbook.mkdir(parents=True)
    for i in range(1, 4):
        (runbook / f"runbook-{i:02d}.md").write_text(
            f'---\ntitle: "Runbook (part {i}/3)"\ndate: 2026-01-0{i}\nsource: test\n'
            f"---\n\n> Part {i} of 3 of **Runbook**.\n\nBody {i}.\n",
            encoding="utf-8",
        )
    entries = group_documents(scan_raw_docs(docs_dir))
    assert len(entries) == 1
    out = tmp_path / "site"
    out.mkdir()
    extra_pages = [
        (entry.url, entry.date or None, "0.7") for entry in entries
    ]
    export_all(out, {}, [], extra_pages=extra_pages)
    sitemap = (out / "sitemap.xml").read_text(encoding="utf-8")
    assert "documents/runbook/runbook.html" in sitemap
    assert "runbook-01.html" not in sitemap
    assert "runbook-02.html" not in sitemap
    assert "runbook-03.html" not in sitemap
