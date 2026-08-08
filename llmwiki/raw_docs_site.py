"""Raw-documents site section — Home dashboard + Raw/Recent pages.

Renders the wiki-add document layer (``raw/docs/**``) into the static
site:

- a shared file-tree sidebar loaded once from ``documents-tree.json|.js``
- one HTML page per document file under ``site/documents/…``
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
    """One logical document for the Recent list — a chunked folder
    collapses into a single entry."""

    title: str
    date: str
    source_label: str
    url: str                  # site-relative URL of the (first) page
    parts: int                # 1 for single-file docs


def clean_chunk_title(title: str) -> str:
    """Strip kbbuilder's ``(part i/N: …)`` suffix from a chunk title."""
    return _PART_SUFFIX_RE.sub("", title).strip()


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
    """Collapse chunk folders into logical documents, newest first.

    Rule: files sharing a top-level folder under raw/docs are chunks of
    one document (kbbuilder writes ``raw/docs/<slug>/<slug>-NN.md``);
    root-level files are standalone documents.
    """
    by_group: dict[str, list[RawDocFile]] = {}
    singles: list[RawDocFile] = []
    for f in files:
        if len(f.rel.parts) > 1:
            by_group.setdefault(f.rel.parts[0], []).append(f)
        else:
            singles.append(f)

    entries: list[DocEntry] = []
    for f in singles:
        entries.append(DocEntry(
            title=clean_chunk_title(f.title),
            date=f.date,
            source_label=f.source_label,
            url=f.out_rel,
            parts=1,
        ))
    for _group, chunks in by_group.items():
        chunks = sorted(chunks, key=lambda c: c.rel.as_posix())
        first = chunks[0]
        entries.append(DocEntry(
            title=clean_chunk_title(first.title),
            date=max((c.date for c in chunks if c.date), default=""),
            source_label=first.source_label,
            url=first.out_rel,
            parts=len(chunks),
        ))
    entries.sort(key=lambda e: (e.date, e.title), reverse=True)
    return entries


# ─── sidebar tree ──────────────────────────────────────────────────────────


def tree_to_dict(root: DocFolder) -> dict[str, Any]:
    """Serialize ``DocFolder`` for ``documents-tree.json`` (site-root hrefs)."""

    def folder_dict(node: DocFolder) -> dict[str, Any]:
        return {
            "name": node.name,
            "folders": [
                folder_dict(child)
                for _name, child in sorted(node.folders.items())
            ],
            "files": [
                {
                    "label": (
                        clean_chunk_title(f.title)
                        if f.rel.parts[:-1] == ()
                        else f.rel.stem
                    ),
                    "href": f.out_rel,
                    "rel": f.rel.as_posix(),
                }
                for f in sorted(node.files, key=lambda f: f.rel.as_posix())
            ],
        }

    top = folder_dict(root)
    return {"folders": top["folders"], "files": top["files"]}


def write_documents_tree(root: DocFolder, out_dir: Path) -> Path:
    """Write ``documents-tree.json`` + ``.js`` sidecar once for the whole site."""
    payload = json.dumps(tree_to_dict(root), ensure_ascii=False, separators=(",", ":"))
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


def render_document_pages(
    files: list[RawDocFile],
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
    """Write one HTML page per raw doc file under ``site/documents/``.

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
    for f in files:
        prefix = "../" * f.depth
        crumbs = [("Home", "index.html")]
        if len(f.rel.parts) > 1:
            crumbs.append((f.rel.parts[0], ""))
        crumbs.append((clean_chunk_title(f.title) if len(f.rel.parts) == 1
                       else f.rel.stem, ""))
        sources_block = ""
        if vault is not None:
            raw_rel = f"raw/docs/{f.rel.as_posix()}"
            exclude = f.out_rel
            # Top-level project folder when nested under raw/docs/<proj>/…
            project = f.rel.parts[0] if len(f.rel.parts) > 1 else ""
            links = provenance_links_for_raw(
                vault,
                raw_rel,
                project=project,
                exclude_href=exclude,
                index=index,
            )
            sources_block = format_sources_html(links, link_prefix=prefix)
        body = f"""<main id="main-content">
<section class="section doctree-section">
  <div class="container">
    {breadcrumbs_bar(crumbs, link_prefix=prefix)}
    <div class="doctree-layout">
      {render_sidebar_mount(active_rel=f.rel, link_prefix=prefix)}
      <article class="article doc-article">
        {sources_block}{md_to_html(f.body)}
      </article>
    </div>
  </div>
</section>
</main>
"""
        page = (
            page_head(
                f"{f.title} — LLM Wiki",
                f"Raw document {f.rel.as_posix()}",
                css_prefix=prefix,
            )
            + nav_builder(prefix)
            + body
            + page_foot(prefix)
        )
        out_path = out_dir / Path(*f.out_rel.split("/"))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(page, encoding="utf-8")
        written.append(out_path)
        # Sibling .md copy for FR2 (raw) Sources fallback when exclude_href
        # is this page's HTML — mirrors session site/sources/… copies.
        md_dest = out_path.with_suffix(".md")
        try:
            shutil.copy2(f.path, md_dest)
        except OSError:
            pass
    return written
