"""Raw-documents site section — Home dashboard + Raw/Recent pages.

Renders the wiki-add document layer (``raw/docs/**``) into the static
site:

- a shared file-tree sidebar loaded once from ``documents-tree.json|.js``
- one canonical HTML page per logical document under ``site/documents/…`` (multi-part chunk paths keep stub redirects at ``-NN`` URLs)
- the Home queue dashboard (body of ``index.html``)
- the Raw tree pane (body of ``raw.html``)
- the Recent-documents list (body of ``recent.html``)

The module is chrome-agnostic: page shells (head / nav / footer) are
injected as callables by ``build.py``, mirroring how
``docs_pages.compile_docs_site`` avoids a circular import.
"""
from __future__ import annotations

import html
import json
import re
import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

from llmwiki._frontmatter import parse_frontmatter
from llmwiki.render.data import write_js_sidecar
from llmwiki.trace import (
    build_source_file_index,
    format_sources_html,
    provenance_links_for_raw,
)

# Path-safe segment — same alphabet as build._safe_slug (#405). Files
# whose relative path contains any other segment are skipped (they
# could otherwise escape out_dir when composing output paths).
_SAFE_SEG_RE = re.compile(r"^[A-Za-z0-9._-]+$")

# "Doc Title (part 3/11: Section)" → "Doc Title" — kbbuilder's chunk
# title decoration, stripped when we present chunks as one document.
_PART_SUFFIX_RE = re.compile(r"\s*\(part \d+/\d+[^)]*\)\s*$")

# Trailing ``-NN`` on a stem (add_doc chunk naming ``<slug>-01`` …).
# Collision suffixes from ``_dedupe`` are ``-2``, ``-3`` (unpadded) and
# must NOT be stripped — same rule as ``add_doc._doc_ref``.
_CHUNK_STEM_SUFFIX_RE = re.compile(r"-\d{2}$")

# add_doc injects ``> Part i of N of **Title** — sub.`` above each chunk body.
# Some older/broken writes left ``> Part i of N of ****.`` (empty bold title) —
# match any ``> Part i of N of …`` line, not only well-formed ``**Title**``.
_PART_BREADCRUMB_RE = re.compile(
    r"^>\s*Part\s+\d+\s+of\s+\d+\s+of\b.*$",
    re.MULTILINE,
)

# Leading ATX heading line (for stripping repeated part-title chrome).
_LEADING_ATX_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


@dataclass
class RawDocFile:
    """One markdown file under raw/docs/."""

    path: Path                # absolute source path
    rel: PurePosixPath        # relative to raw/docs, e.g. "grp/chunk-01.md"
    meta: dict[str, Any]
    body: str

    @property
    def title(self) -> str:
        return str(self.meta.get("title") or self.rel.stem)

    @property
    def date(self) -> str:
        return str(self.meta.get("date", ""))

    @property
    def source_label(self) -> str:
        return str(self.meta.get("source", ""))

    @property
    def out_rel(self) -> str:
        """Site-relative HTML path, e.g. ``documents/grp/chunk-01.html``."""
        return f"documents/{self.rel.with_suffix('.html')}"

    @property
    def depth(self) -> int:
        """Directory depth below site root (documents/ counts as 1)."""
        return len(self.rel.parts)


@dataclass
class DocFolder:
    """One directory node of the raw/docs tree."""

    name: str
    folders: dict[str, DocFolder] = field(default_factory=dict)
    files: list[RawDocFile] = field(default_factory=list)


@dataclass
class DocEntry:
    """One logical document — files sharing a base slug within a directory.

    ``parts`` stays an ``int`` for Recent/Home meta ("3 parts"); ordered
    ``RawDocFile`` members live on ``part_files`` for later slices
    (unified HTML, search-index, tree leaves).
    """

    title: str
    date: str
    source_label: str
    url: str                  # canonical site-relative unified HTML path
    parts: int                # len(part_files); 1 for single-file docs
    id: str = ""              # e.g. document:proj/base-slug
    folder_parts: tuple[str, ...] = ()
    part_files: list[RawDocFile] = field(default_factory=list)


def clean_chunk_title(title: str) -> str:
    """Strip kbbuilder's ``(part i/N: …)`` suffix from a chunk title."""
    return _PART_SUFFIX_RE.sub("", title).strip()


def base_slug_from_stem(stem: str) -> str:
    """Stem with trailing ``-\\d{2}`` chunk suffix removed (add_doc pattern)."""
    return _CHUNK_STEM_SUFFIX_RE.sub("", stem)


def _part_sort_key(f: RawDocFile) -> tuple[str, int]:
    """Sort chunk parts by base stem then numeric ``-NN`` suffix."""
    stem = f.rel.stem
    m = _CHUNK_STEM_SUFFIX_RE.search(stem)
    if m:
        return (stem[: m.start()], int(m.group()[1:]))
    return (stem, -1)


def canonical_document_url(folder_parts: tuple[str, ...], base_slug: str) -> str:
    """Site-relative path for the unified document page (#305)."""
    if folder_parts:
        return f"documents/{'/'.join(folder_parts)}/{base_slug}.html"
    return f"documents/{base_slug}.html"


def document_id(folder_parts: tuple[str, ...], base_slug: str) -> str:
    """Stable logical-document id shared by Recent, search-index, tree."""
    if folder_parts:
        return f"document:{'/'.join(folder_parts)}/{base_slug}"
    return f"document:{base_slug}"


def part_anchor_id(part_index: int) -> str:
    """Stable deep-link id for part *N* (1-based) on a unified page."""
    return f"part-{part_index:02d}"


def document_search_body_sample(
    entry: DocEntry,
    *,
    md_to_plain_text: Callable[[str], str],
    cap: int = 1200,
    min_per_part: int = 80,
) -> str:
    """Plain-text sample for Ctrl+K — budget split across parts.

    A single ``assembled[:cap]`` prefix drops later parts once early text is
    long. Take up to ``max(min_per_part, cap // n)`` chars from each part
    (chrome stripped), then join and apply the global ``cap``.
    """
    parts = entry.part_files
    if not parts:
        return ""
    per = max(min_per_part, cap // len(parts))
    pieces = [
        md_to_plain_text(
            strip_part_chrome(
                part.body, doc_title=entry.title, part_title=part.title,
            )
        )[:per]
        for part in parts
    ]
    return "\n\n".join(pieces)[:cap]


def strip_part_chrome(body: str, *, doc_title: str, part_title: str) -> str:
    """Remove add_doc part breadcrumbs and repeated part-title H1 chrome.

    Single-file docs keep their leading H1 (it is the document title, not
    generated part chrome). Multi-chunk titles carry ``(part i/N…)`` and/or
    a ``> Part i of N…`` breadcrumb — those are stripped.
    """
    had_breadcrumb = bool(_PART_BREADCRUMB_RE.search(body))
    text = _PART_BREADCRUMB_RE.sub("", body)
    is_part_chrome = had_breadcrumb or bool(_PART_SUFFIX_RE.search(part_title))
    if not is_part_chrome:
        return text.lstrip("\n")
    titles = {
        t for t in (
            part_title.strip(),
            doc_title.strip(),
            clean_chunk_title(part_title),
        ) if t
    }
    lines = text.lstrip("\n").splitlines(keepends=True)
    if lines:
        m = _LEADING_ATX_RE.match(lines[0].rstrip("\n"))
        if m and m.group(2).strip() in titles:
            lines = lines[1:]
            while lines and not lines[0].strip():
                lines = lines[1:]
    return "".join(lines)


def _site_url_depth(url: str) -> int:
    """How many ``../`` segments reach site root from a site-relative URL."""
    return max(0, len(PurePosixPath(url).parts) - 1)


def _sibling_href(canonical_url: str, fragment: str = "") -> str:
    """Basename-relative href to ``canonical_url`` (same directory as the stub)."""
    href = PurePosixPath(canonical_url).name
    if fragment:
        return f"{href}#{fragment}"
    return href


def scan_raw_docs(docs_dir: Path) -> list[RawDocFile]:
    """Walk ``raw/docs/**/*.md`` and return parsed files, sorted by rel path.

    Skips ``_``-prefixed files (folder metadata such as ``_context.md``)
    and anything whose relative path contains a non-path-safe segment.
    """
    out: list[RawDocFile] = []
    if not docs_dir.is_dir():
        return out
    for p in sorted(docs_dir.rglob("*.md")):
        rel = PurePosixPath(p.relative_to(docs_dir).as_posix())
        if any(part.startswith("_") for part in rel.parts):
            continue
        if not all(_SAFE_SEG_RE.match(part) for part in rel.parts):
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        meta, body = parse_frontmatter(text)
        out.append(RawDocFile(path=p, rel=rel, meta=meta, body=body))
    return out


def count_docs_by_project(files: list[RawDocFile]) -> dict[str, int]:
    """Count raw documents per owning project.

    Attribution mirrors ``add_doc``: the ``project`` frontmatter field when
    present, else the top folder segment under ``raw/docs``, else the file
    stem for a bare top-level doc.
    """
    out: dict[str, int] = {}
    for f in files:
        proj = str(f.meta.get("project") or "").strip()
        if not proj:
            proj = f.rel.parts[0] if len(f.rel.parts) > 1 else f.rel.stem
        out[proj] = out.get(proj, 0) + 1
    return out


def build_tree(files: list[RawDocFile]) -> DocFolder:
    """Fold the flat file list into a nested folder tree."""
    root = DocFolder(name="")
    for f in files:
        node = root
        for part in f.rel.parts[:-1]:
            node = node.folders.setdefault(part, DocFolder(name=part))
        node.files.append(f)
    return root


def group_documents(files: list[RawDocFile]) -> list[DocEntry]:
    """Group files into logical documents by base slug within each directory.

    Within each directory under ``raw/docs/``:

    1. Partition by **base slug** — stem with trailing ``-\\d{2}`` removed
       (matches ``add_doc`` chunk naming ``<slug>-NN``).
    2. Each base-slug group is one logical document; parts sorted by
       stem / numeric suffix.
    3. Root-level files group the same way (a lone ``foo.md`` is one doc).

    This replaces the old "whole top-level folder = one document" rule so
    ``--project`` folders with several docs stay separate (#305).
    """
    by_dir: dict[tuple[str, ...], list[RawDocFile]] = {}
    for f in files:
        by_dir.setdefault(f.rel.parts[:-1], []).append(f)

    entries: list[DocEntry] = []
    for folder_parts, dir_files in by_dir.items():
        by_base: dict[str, list[RawDocFile]] = {}
        for f in dir_files:
            by_base.setdefault(base_slug_from_stem(f.rel.stem), []).append(f)
        for base, chunks in by_base.items():
            chunks = sorted(chunks, key=_part_sort_key)
            first = chunks[0]
            entries.append(DocEntry(
                title=clean_chunk_title(first.title),
                date=max((c.date for c in chunks if c.date), default=""),
                source_label=first.source_label,
                url=canonical_document_url(folder_parts, base),
                parts=len(chunks),
                id=document_id(folder_parts, base),
                folder_parts=folder_parts,
                part_files=chunks,
            ))
    entries.sort(key=lambda e: (e.date, e.title), reverse=True)
    return entries


# ─── sidebar tree ──────────────────────────────────────────────────────────


def tree_to_dict(entries: list[DocEntry]) -> dict[str, Any]:
    """Serialize logical documents for ``documents-tree.json`` (site-root hrefs).

    Leaves are one per :class:`DocEntry` (not per chunk file): ``id`` / ``label``
    / ``href`` match the search-index ``type:"document"`` meta entries; ``rel``
    is the first part's path under ``raw/docs`` for sidebar active highlighting.
    Folder nesting follows ``folder_parts``.
    """

    @dataclass
    class _Node:
        name: str
        folders: dict[str, _Node] = field(default_factory=dict)
        files: list[DocEntry] = field(default_factory=list)

    root = _Node(name="")
    for entry in entries:
        node = root
        for part in entry.folder_parts:
            node = node.folders.setdefault(part, _Node(name=part))
        node.files.append(entry)

    def _leaf(entry: DocEntry) -> dict[str, Any]:
        rel = (
            entry.part_files[0].rel.as_posix()
            if entry.part_files
            else ""
        )
        return {
            "id": entry.id,
            "label": entry.title,
            "href": entry.url,
            "rel": rel,
        }

    def folder_dict(node: _Node) -> dict[str, Any]:
        return {
            "name": node.name,
            "folders": [
                folder_dict(child)
                for _name, child in sorted(node.folders.items())
            ],
            "files": [
                _leaf(e)
                for e in sorted(
                    node.files,
                    key=lambda e: (
                        e.part_files[0].rel.as_posix()
                        if e.part_files
                        else e.title
                    ),
                )
            ],
        }

    top = folder_dict(root)
    return {"folders": top["folders"], "files": top["files"]}


def write_documents_tree(entries: list[DocEntry], out_dir: Path) -> Path:
    """Write ``documents-tree.json`` + ``.js`` sidecar once for the whole site."""
    payload = json.dumps(
        tree_to_dict(entries), ensure_ascii=False, separators=(",", ":"),
    )
    out_path = out_dir / "documents-tree.json"
    out_path.write_text(payload, encoding="utf-8")
    write_js_sidecar(out_path, "documents-tree", payload)
    return out_path


def render_sidebar_mount(
    *,
    active_rel: PurePosixPath | None = None,
    link_prefix: str = "",
) -> str:
    """Empty doctree aside; ``script.js`` fills it from ``documents-tree.js``."""
    active = html.escape(active_rel.as_posix()) if active_rel else ""
    prefix = html.escape(link_prefix)
    raw_href = f"{prefix}raw.html"
    return (
        f'<aside class="doctree-sidebar" aria-label="Documents tree" '
        f'data-doctree-mount data-active-rel="{active}" '
        f'data-link-prefix="{prefix}" '
        f'data-doctree-js="{prefix}documents-tree.js">'
        '<div class="doctree-title">Documents</div>'
        '<p class="muted doctree-loading">Loading documents tree…</p>'
        f'<noscript><p class="muted">Enable JavaScript to browse the tree, '
        f'or open <a href="{raw_href}">Raw</a>.</p></noscript>'
        "</aside>"
    )


def render_sidebar(
    root: DocFolder,
    active_rel: PurePosixPath | None = None,
    link_prefix: str = "",
) -> str:
    """Render the shared file-tree sidebar as static HTML (tests / fallback).

    Production pages use :func:`render_sidebar_mount` + ``documents-tree.js``
    so the ~250 KB tree is not duplicated into every document HTML file.
    """
    def file_link(f: RawDocFile) -> str:
        cls = ' class="active" aria-current="page"' if f.rel == active_rel else ""
        label = clean_chunk_title(f.title) if f.rel.parts[:-1] == () else f.rel.stem
        return (
            f'<li><a href="{link_prefix}{html.escape(f.out_rel)}"{cls}>'
            f"{html.escape(label)}</a></li>"
        )

    def folder_html(node: DocFolder, path_parts: tuple[str, ...]) -> str:
        is_open = bool(
            active_rel is not None
            and active_rel.parts[: len(path_parts)] == path_parts
        )
        inner = children_html(node, path_parts)
        return (
            f'<li><details{" open" if is_open else ""}>'
            f"<summary>{html.escape(node.name)}</summary>"
            f"{inner}</details></li>"
        )

    def children_html(node: DocFolder, path_parts: tuple[str, ...]) -> str:
        items = [
            folder_html(child, path_parts + (name,))
            for name, child in sorted(node.folders.items())
        ]
        items += [file_link(f) for f in sorted(node.files, key=lambda f: f.rel.as_posix())]
        return "<ul>" + "".join(items) + "</ul>"

    if not root.folders and not root.files:
        body = '<p class="muted">No documents yet.</p>'
    else:
        body = children_html(root, ())
    return (
        '<aside class="doctree-sidebar" aria-label="Documents tree">'
        '<div class="doctree-title">Documents</div>'
        f"{body}</aside>"
    )


# ─── page bodies ───────────────────────────────────────────────────────────


def render_dashboard_body(
    entries: list[DocEntry],
    doc_file_count: int,
    *,
    vault_root: Path | None = None,
    repo_root: Path | None = None,
    automation_html: str = "",
) -> str:
    """Body of index.html — pipeline State table mount + recent raw docs."""
    if not entries:
        recent_block = '<p class="muted">No recent raw documents yet.</p>'
    else:
        rows = []
        for e in entries[:20]:
            bits = [b for b in (e.date, e.source_label, f"{e.parts} parts" if e.parts > 1 else "") if b]
            rows.append(
                '<li class="recent-doc">'
                f'<a href="{html.escape(e.url)}">{html.escape(e.title)}</a>'
                f'<div class="recent-doc-meta muted">{html.escape(" · ".join(bits))}</div>'
                "</li>"
            )
        recent_block = '<ol class="recent-docs">' + "".join(rows) + "</ol>"
    attrs = ""
    if vault_root is not None:
        attrs += f' data-vault-root="{html.escape(str(vault_root))}"'
    if repo_root is not None:
        attrs += f' data-repo-root="{html.escape(str(repo_root))}"'
    auto_block = automation_html or ""
    return f"""<section class="section doctree-section">
  <div class="container">
    <div class="queue-widget">
      {auto_block}
      <h2>Pipeline state</h2>
      <div id="llmwiki-state-widget" class="state-widget" data-llmwiki-state-widget{attrs}>
        <p class="muted">Loading pipeline state…</p>
      </div>
      <h3>Recent raw documents</h3>
      {recent_block}
    </div>
  </div>
</section>
</main>
"""


def render_raw_body(
    _root: DocFolder,
    entries: list[DocEntry],
    doc_file_count: int,
) -> str:
    """Body of raw.html — tree sidebar mount + intro pane."""
    sidebar = render_sidebar_mount(active_rel=None, link_prefix="")
    if doc_file_count == 0:
        intro = (
            '<p>No raw documents yet. Add one with <code>wiki-add</code> '
            "(a URL, a pasted document, or a file) and it will appear here "
            "after the next build.</p>"
        )
    else:
        newest = "".join(
            f'<li><a href="{html.escape(e.url)}">{html.escape(e.title)}</a>'
            f'<span class="muted"> · {html.escape(e.date)}'
            + (f" · {e.parts} parts" if e.parts > 1 else "")
            + "</span></li>"
            for e in entries[:5]
        )
        intro = (
            f"<p>{len(entries)} documents ({doc_file_count} files). "
            "Pick one from the tree, or start with the newest:</p>"
            f'<ul class="recent-docs-mini">{newest}</ul>'
            '<p class="muted">Full recent list is available on the Home dashboard.</p>'
        )
    return f"""<section class="section doctree-section">
  <div class="container">
    <div class="doctree-layout">
      {sidebar}
      <div class="doctree-main">
        <h2>Browse documents</h2>
        {intro}
      </div>
    </div>
  </div>
</section>
</main>
"""


def render_recent_body(entries: list[DocEntry]) -> str:
    """Body of recent.html — newest documents first."""
    if not entries:
        items = '<p class="muted">No documents yet.</p>'
    else:
        rows = []
        for e in entries:
            meta_bits = [b for b in (
                e.date,
                e.source_label,
                f"{e.parts} parts" if e.parts > 1 else "",
            ) if b]
            rows.append(
                '<li class="recent-doc">'
                f'<a href="{html.escape(e.url)}">{html.escape(e.title)}</a>'
                f'<div class="recent-doc-meta muted">{html.escape(" · ".join(meta_bits))}</div>'
                "</li>"
            )
        items = '<ol class="recent-docs">' + "".join(rows) + "</ol>"
    return f"""<section class="section">
  <div class="container narrow">
    {items}
  </div>
</section>
</main>
"""


def _assemble_unified_article(
    entry: DocEntry,
    *,
    md_to_html: Callable[[str], str],
) -> tuple[str, list[str]]:
    """Concatenate stripped part bodies into one article; return (html, anchors).

    Each part is wrapped in ``<section id="part-NN">``. When a part still has
    a usable ATX heading after chrome stripping, that heading stays in the
    body (TOC ids from ``md_to_html``); otherwise the ``part-NN`` section id
    is the deep-link target for stubs.
    """
    sections: list[str] = []
    anchors: list[str] = []
    for i, part in enumerate(entry.part_files, start=1):
        anchor = part_anchor_id(i)
        anchors.append(anchor)
        cleaned = strip_part_chrome(
            part.body, doc_title=entry.title, part_title=part.title,
        )
        frag = md_to_html(cleaned) if cleaned.strip() else ""
        sections.append(
            f'<section id="{html.escape(anchor)}" class="doc-part">'
            f"{frag}</section>"
        )
    article = "".join(sections)
    # Multi-part chrome stripping removes per-part title H1s; emit the
    # document title once so the article keeps a proper outline.
    if len(entry.part_files) > 1:
        article = f"<h1>{html.escape(entry.title)}</h1>" + article
    return article, anchors


def render_part_stub_html(
    *,
    canonical_href: str,
    part_label: str,
    doc_title: str,
) -> str:
    """Minimal stub page: meta refresh + script + visible fallback link.

    ``canonical_href`` must be a same-directory relative URL (``file://``-safe),
    including the ``#part-NN`` fragment.
    """
    href = html.escape(canonical_href, quote=True)
    label = html.escape(part_label)
    title = html.escape(doc_title)
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        f'<meta http-equiv="refresh" content="0; url={href}">\n'
        f"<title>Redirecting to {title}</title>\n"
        f"<script>location.replace({json.dumps(canonical_href)});</script>\n"
        "</head>\n"
        "<body>\n"
        f"<p>This part of <strong>{title}</strong> is included in the "
        f'full document: <a href="{href}">{label}</a>.</p>\n'
        "</body>\n"
        "</html>\n"
    )


def render_document_pages(
    entries: list[DocEntry],
    _root: DocFolder,
    out_dir: Path,
    *,
    md_to_html: Callable[[str], str],
    page_head: Callable[..., str],
    nav_builder: Callable[[str], str],
    page_foot: Callable[[str], str],
    breadcrumbs_bar: Callable[..., str],
    vault: Path | None = None,
    source_file_index: dict[str, Path] | None = None,
) -> list[Path]:
    """Write unified document HTML (+ part URL stubs) under ``site/documents/``.

    One complete article per :class:`DocEntry` at ``entry.url``. Multi-part
    docs also get a small stub at each non-canonical ``…/<slug>-NN.html`` that
    points at ``canonical#part-NN`` (#305). Sibling ``.md`` copies for every
    part are kept for FR2 / provenance fallback.

    ``_root`` is accepted for call-site compatibility; the doctree itself is
    loaded client-side from ``documents-tree.js`` (see
    :func:`write_documents_tree`). ``nav_builder(link_prefix)`` must return
    the nav with the Raw item active — document pages live under the Raw
    tree browser.

    Pass ``source_file_index`` from :func:`llmwiki.trace.build_source_file_index`
    when rendering many documents in one build (built once per batch).
    """
    written: list[Path] = []
    index = source_file_index
    if vault is not None and index is None:
        index = build_source_file_index(vault)

    for entry in entries:
        if not entry.part_files:
            continue
        first = entry.part_files[0]
        prefix = "../" * _site_url_depth(entry.url)
        crumbs = [("Home", "index.html")]
        if entry.folder_parts:
            crumbs.append((entry.folder_parts[0], ""))
        crumbs.append((entry.title, ""))

        sources_block = ""
        if vault is not None:
            raw_rel = f"raw/docs/{first.rel.as_posix()}"
            project = entry.folder_parts[0] if entry.folder_parts else ""
            links = provenance_links_for_raw(
                vault,
                raw_rel,
                project=project,
                exclude_href=entry.url,
                index=index,
            )
            sources_block = format_sources_html(links, link_prefix=prefix)

        article_html, anchors = _assemble_unified_article(
            entry, md_to_html=md_to_html,
        )
        body = f"""<main id="main-content">
<section class="section doctree-section">
  <div class="container">
    {breadcrumbs_bar(crumbs, link_prefix=prefix)}
    <div class="doctree-layout">
      {render_sidebar_mount(active_rel=first.rel, link_prefix=prefix)}
      <article class="article doc-article">
        {sources_block}{article_html}
      </article>
    </div>
  </div>
</section>
</main>
"""
        page = (
            page_head(
                f"{entry.title} — LLM Wiki",
                f"Raw document {entry.title}",
                css_prefix=prefix,
            )
            + nav_builder(prefix)
            + body
            + page_foot(prefix)
        )
        out_path = out_dir / Path(*entry.url.split("/"))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(page, encoding="utf-8")
        written.append(out_path)

        for i, part in enumerate(entry.part_files, start=1):
            # Sibling .md copy for FR2 (raw) Sources fallback.
            md_dest = out_dir / Path(*part.out_rel.split("/"))
            md_dest = md_dest.with_suffix(".md")
            md_dest.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(part.path, md_dest)
            except OSError:
                pass

            if part.out_rel == entry.url:
                continue
            # Non-canonical part URL → stub only (no duplicate article body).
            anchor = anchors[i - 1] if i - 1 < len(anchors) else part_anchor_id(i)
            stub_href = _sibling_href(entry.url, anchor)
            stub_html = render_part_stub_html(
                canonical_href=stub_href,
                part_label=f"{entry.title} (part {i})",
                doc_title=entry.title,
            )
            stub_path = out_dir / Path(*part.out_rel.split("/"))
            stub_path.parent.mkdir(parents=True, exist_ok=True)
            stub_path.write_text(stub_html, encoding="utf-8")
            written.append(stub_path)

    return written
