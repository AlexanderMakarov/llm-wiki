"""Provenance walker: wiki page → source summaries → raw transcripts (#122).

Pure library — no argparse / MCP. Walks existing frontmatter only:

* ``sources:`` on any wiki page → ``wiki/sources/**/<slug>.md``
* ``source_file:`` on a source summary → vault-relative ``raw/…`` path

Missing hops are marked ``status="missing"`` rather than omitted. Never reads
or invents body excerpts. Locators that escape the vault are rejected.

Site renderers (topics / sessions / documents) use :func:`sources_links` and
:func:`format_sources_html` for FR2 prefer-HTML-else-raw links.

Session/document builds use :func:`build_source_file_index` once per batch so
:func:`find_wiki_source_for_raw` stays O(1) instead of rescanning
``wiki/sources/**`` for every page.
"""

from __future__ import annotations

import html
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from llmwiki._frontmatter import parse_frontmatter
from llmwiki.candidates import parse_sources_field, resolve_source_page
from llmwiki.graph import _compute_site_url, _verify_site_url

Role = Literal["page", "source", "raw"]
Status = Literal["ok", "missing"]


@dataclass(frozen=True)
class TraceHop:
    """One step in a downward provenance chain."""

    role: Role
    title: str
    location: str
    status: Status
    site_href: str | None = None


@dataclass(frozen=True)
class TraceResult:
    """Ordered downward hops from :func:`trace_page`."""

    hops: list[TraceHop] = field(default_factory=list)


@dataclass(frozen=True)
class SourceLink:
    """One site Sources entry (prefer HTML; else raw site copy)."""

    title: str
    href: str
    is_raw: bool = False


class TraceError(ValueError):
    """Starting page cannot be resolved, or the locator is unsafe."""


def _vault_root(vault: Path) -> Path:
    return Path(vault).expanduser().resolve()


def _under_vault(vault: Path, path: Path) -> Path | None:
    """Return ``path`` resolved when it stays inside ``vault``, else ``None``."""
    try:
        resolved = path.expanduser().resolve()
        resolved.relative_to(vault)
    except (OSError, ValueError):
        return None
    return resolved


def _rel_to_vault(vault: Path, path: Path) -> str:
    return path.resolve().relative_to(vault).as_posix()


def _looks_like_path(locator: str) -> bool:
    return (
        "/" in locator
        or "\\" in locator
        or locator.endswith(".md")
        or locator.startswith("wiki")
    )


def _resolve_path_locator(vault: Path, wiki: Path, locator: str) -> Path:
    """Resolve a path-shaped locator under ``vault/wiki``; reject escapes."""
    candidate = Path(locator)
    if candidate.is_absolute():
        resolved = _under_vault(vault, candidate)
    elif locator == "wiki" or locator.startswith(("wiki/", "wiki\\")):
        resolved = _under_vault(vault, vault / locator)
    else:
        under_wiki = _under_vault(vault, wiki / locator)
        if under_wiki is not None and under_wiki.is_file():
            resolved = under_wiki
        else:
            resolved = _under_vault(vault, vault / locator)
    if resolved is None:
        raise TraceError(f"path outside vault: {locator}")
    try:
        resolved.relative_to(wiki)
    except ValueError as exc:
        raise TraceError(f"path outside vault: {locator}") from exc
    if not resolved.is_file():
        raise TraceError(f"page not found: {locator}")
    return resolved


def _resolve_locator(vault: Path, locator: str) -> Path:
    """Resolve a vault-relative path or page name under ``vault/wiki``.

    Raises:
        TraceError: empty locator, path traversal, or no matching wiki page.
    """
    loc = (locator or "").strip()
    if not loc:
        raise TraceError("empty page locator")

    wiki = (vault / "wiki").resolve()
    # Traversal segments are never treated as a bare page name.
    if ".." in Path(loc).parts:
        return _resolve_path_locator(vault, wiki, loc)

    if _looks_like_path(loc):
        return _resolve_path_locator(vault, wiki, loc)

    # Name / stem scan under wiki/.
    slug = loc.removesuffix(".md")
    if not slug or slug in {".", ".."}:
        raise TraceError(f"page not found: {locator}")
    matches = [
        m
        for m in sorted(wiki.rglob(f"{slug}.md"))
        if _under_vault(vault, m) is not None
    ]
    if not matches:
        raise TraceError(f"page not found: {locator}")
    # Prefer trusted pages over candidates/ when the stem collides.
    preferred = [m for m in matches if "candidates" not in m.parts]
    return (preferred or matches)[0]


def _meta_str(meta: dict[str, object], key: str) -> str:
    value = meta.get(key)
    if value is None or isinstance(value, list | dict):
        return ""
    return str(value).strip().strip('"').strip("'")


def _title_from(meta: dict[str, object], fallback: str) -> str:
    return _meta_str(meta, "title") or fallback


def _sources_slugs(meta: dict[str, object]) -> list[str]:
    raw = meta.get("sources")
    if isinstance(raw, list):
        return parse_sources_field(raw)
    if raw is None:
        return parse_sources_field(None)
    return parse_sources_field(str(raw))


def _site_href_for_wiki_page(vault: Path, page: Path, text: str) -> str | None:
    """Site-relative href when compiled HTML exists under ``vault/site``."""
    wiki = vault / "wiki"
    try:
        rel = page.resolve().relative_to(wiki.resolve())
    except ValueError:
        return None
    slug = page.stem
    type_ = rel.parts[0] if len(rel.parts) > 1 else "root"
    url = _compute_site_url(text, rel.parts, slug, type_)
    site_dir = vault / "site"
    if not site_dir.is_dir():
        return None
    return _verify_site_url(url, site_dir)


def _raw_hop(vault: Path, source_file: str) -> TraceHop:
    """Hop for a ``source_file:`` claim (ok if the raw path exists)."""
    claimed = source_file.replace("\\", "/").strip()
    if not claimed:
        return TraceHop(
            role="raw",
            title="",
            location="",
            status="missing",
        )
    rel = claimed.lstrip("/")
    parts = Path(rel).parts
    if not parts or ".." in parts:
        return TraceHop(
            role="raw",
            title=Path(rel).name or claimed,
            location=claimed,
            status="missing",
        )
    abs_path = _under_vault(vault, vault / rel)
    if abs_path is None:
        return TraceHop(
            role="raw",
            title=Path(rel).name,
            location=rel,
            status="missing",
        )
    if not abs_path.is_file():
        return TraceHop(
            role="raw",
            title=abs_path.stem,
            location=rel,
            status="missing",
        )
    title = abs_path.stem
    try:
        meta, _ = parse_frontmatter(abs_path.read_text(encoding="utf-8"))
        title = _title_from(meta, title)
    except OSError:
        pass
    return TraceHop(
        role="raw",
        title=title,
        location=_rel_to_vault(vault, abs_path),
        status="ok",
    )


def _append_source_file_hop(
    hops: list[TraceHop],
    vault: Path,
    meta: dict[str, object],
) -> None:
    sf = _meta_str(meta, "source_file")
    if sf:
        hops.append(_raw_hop(vault, sf))


def trace_page(vault: Path, locator: str) -> TraceResult:
    """Walk downward provenance from a wiki page to raw transcripts.

    Args:
        vault: Vault root (contains ``wiki/``, optionally ``raw/`` + ``site/``).
        locator: Vault-relative path (``wiki/entities/Foo.md``) or page
            name/stem resolvable under ``wiki/``.

    Returns:
        :class:`TraceResult` with ordered hops. Partial missing hops do not
        fail the walk.

    Raises:
        TraceError: locator empty, escapes the vault, or starting page missing.
    """
    vault_root = _vault_root(vault)
    if not vault_root.is_dir():
        raise TraceError(f"vault not found: {vault}")

    page = _resolve_locator(vault_root, locator)
    try:
        text = page.read_text(encoding="utf-8")
    except OSError as exc:
        raise TraceError(f"page not readable: {locator}") from exc

    meta, _body = parse_frontmatter(text)
    hops: list[TraceHop] = [
        TraceHop(
            role="page",
            title=_title_from(meta, page.stem),
            location=_rel_to_vault(vault_root, page),
            status="ok",
            site_href=_site_href_for_wiki_page(vault_root, page, text),
        )
    ]

    wiki_dir = vault_root / "wiki"
    for slug in _sources_slugs(meta):
        src_path = resolve_source_page(wiki_dir, slug)
        if src_path is None:
            hops.append(
                TraceHop(
                    role="source",
                    title=slug,
                    location=slug,
                    status="missing",
                )
            )
            continue
        safe = _under_vault(vault_root, src_path)
        if safe is None or not safe.is_file():
            hops.append(
                TraceHop(
                    role="source",
                    title=slug,
                    location=slug,
                    status="missing",
                )
            )
            continue
        try:
            src_text = safe.read_text(encoding="utf-8")
        except OSError:
            hops.append(
                TraceHop(
                    role="source",
                    title=slug,
                    location=_rel_to_vault(vault_root, safe),
                    status="missing",
                )
            )
            continue
        src_meta, _ = parse_frontmatter(src_text)
        hops.append(
            TraceHop(
                role="source",
                title=_title_from(src_meta, slug),
                location=_rel_to_vault(vault_root, safe),
                status="ok",
                site_href=_site_href_for_wiki_page(vault_root, safe, src_text),
            )
        )
        _append_source_file_hop(hops, vault_root, src_meta)

    # Source-summary pages (and any page that records one) also emit raw.
    _append_source_file_hop(hops, vault_root, meta)

    return TraceResult(hops=hops)


def raw_site_copy_href(raw_location: str, *, project: str = "") -> str | None:
    """Site-root-relative path for the built-site markdown copy of a raw file.

    Sessions: matches the Download .md layout from
    :func:`llmwiki.build.render_session` (``sources/<project>/<filename>.md``).
    Nested ``raw/sessions/<proj>/…`` paths keep their project segment.

    Documents: ``raw/docs/<rel>.md`` → ``documents/<rel>.md``, matching the
    sibling copy written next to HTML by
    :func:`llmwiki.raw_docs_site.render_document_pages`.
    """
    loc = raw_location.replace("\\", "/").strip().lstrip("/")
    if not loc or ".." in Path(loc).parts:
        return None
    if loc.startswith("raw/sessions/"):
        rest = loc[len("raw/sessions/") :]
        if not rest:
            return None
        if "/" in rest:
            return f"sources/{rest}"
        proj = (project or "").strip()
        if not proj:
            return None
        return f"sources/{proj}/{Path(rest).name}"
    if loc.startswith("raw/docs/"):
        rest = loc[len("raw/docs/") :]
        if not rest or ".." in Path(rest).parts:
            return None
        return f"documents/{rest}"
    return None


def _source_project(meta: dict[str, object]) -> str:
    return _meta_str(meta, "project")


def _link_from_source_and_raw(
    source: TraceHop,
    raw: TraceHop | None,
    *,
    project: str = "",
    exclude_href: str | None = None,
) -> SourceLink | None:
    """Prefer verified HTML ``site_href``; else raw site-copy href."""
    if source.status != "ok":
        return None
    title = source.title or Path(source.location).stem or source.location
    href = source.site_href
    if href and exclude_href and href == exclude_href:
        href = None
    if href:
        return SourceLink(title=title, href=href, is_raw=False)
    if raw is not None and raw.status == "ok" and raw.location:
        raw_href = raw_site_copy_href(raw.location, project=project)
        if raw_href:
            return SourceLink(title=title, href=raw_href, is_raw=True)
    return None


def sources_links(
    vault: Path,
    locator: str,
    *,
    exclude_href: str | None = None,
) -> list[SourceLink]:
    """Site link targets for frontmatter ``sources:`` entries (FR2).

    Prefer each source hop's built HTML (``site_href``); otherwise the
    ``site/sources/…`` copy of its raw transcript, marked raw. Missing hops
    with neither HTML nor raw are omitted (lint reports those separately).
    Never invents ``entities/*.html`` / ``concepts/*.html`` URLs.
    """
    vault_root = _vault_root(vault)
    result = trace_page(vault_root, locator)
    links: list[SourceLink] = []
    seen: set[str] = set()
    hops = result.hops
    i = 0
    while i < len(hops):
        hop = hops[i]
        if hop.role != "source":
            i += 1
            continue
        raw: TraceHop | None = None
        if i + 1 < len(hops) and hops[i + 1].role == "raw":
            raw = hops[i + 1]
        project = ""
        if hop.status == "ok" and hop.location:
            src_path = _under_vault(vault_root, vault_root / hop.location)
            if src_path is not None and src_path.is_file():
                try:
                    meta, _ = parse_frontmatter(src_path.read_text(encoding="utf-8"))
                    project = _source_project(meta)
                except OSError:
                    project = ""
        link = _link_from_source_and_raw(
            hop,
            raw,
            project=project,
            exclude_href=exclude_href,
        )
        if link is not None and link.href not in seen:
            seen.add(link.href)
            links.append(link)
        i += 1
        if raw is not None:
            i += 1
    return links


# Process-local cache: vault resolve() → source_file index. Avoids O(n²)
# rglob+parse when callers omit ``index=`` (legacy / one-off lookups).
# Build batches should pass an explicit index built once per run.
_SOURCE_FILE_INDEX_CACHE: dict[Path, dict[str, Path]] = {}


def _normalize_source_file_key(raw_rel: str) -> str | None:
    """Return a vault-relative ``source_file`` key, or ``None`` if unsafe/empty."""
    target = raw_rel.replace("\\", "/").strip().lstrip("/")
    if not target or ".." in Path(target).parts:
        return None
    return target


def build_source_file_index(vault: Path) -> dict[str, Path]:
    """Map normalized ``source_file:`` values → wiki source paths (one scan).

    Walks ``wiki/sources/**/*.md`` once, parses frontmatter, and indexes
    each non-empty ``source_file`` claim. First path wins when multiple
    pages claim the same raw file (matches :func:`find_wiki_source_for_raw`
    sorted order). Skips ``_*.md`` stubs (folder context files).
    """
    vault_root = _vault_root(vault)
    index: dict[str, Path] = {}
    sources_dir = vault_root / "wiki" / "sources"
    if not sources_dir.is_dir():
        return index
    for path in sorted(sources_dir.rglob("*.md")):
        if path.name.startswith("_"):
            continue
        safe = _under_vault(vault_root, path)
        if safe is None:
            continue
        try:
            meta, _ = parse_frontmatter(safe.read_text(encoding="utf-8"))
        except OSError:
            continue
        claimed = _normalize_source_file_key(_meta_str(meta, "source_file"))
        if claimed is None or claimed in index:
            continue
        index[claimed] = safe
    return index


def _source_file_index_for(vault_root: Path, index: dict[str, Path] | None) -> dict[str, Path]:
    """Return ``index`` or a process-cached index for ``vault_root``."""
    if index is not None:
        return index
    cached = _SOURCE_FILE_INDEX_CACHE.get(vault_root)
    if cached is not None:
        return cached
    built = build_source_file_index(vault_root)
    _SOURCE_FILE_INDEX_CACHE[vault_root] = built
    return built


def find_wiki_source_for_raw(
    vault: Path,
    raw_rel: str,
    *,
    index: dict[str, Path] | None = None,
) -> Path | None:
    """Return the wiki source page whose ``source_file:`` matches ``raw_rel``.

    Args:
        vault: Vault root.
        raw_rel: Vault-relative raw path (e.g. ``raw/sessions/….md``).
        index: Optional prebuilt map from :func:`build_source_file_index`.
            Build/render batches should pass this to avoid a full sources
            scan per page. When omitted, a process-local cache is used
            (one scan per vault resolve() for the process).
    """
    vault_root = _vault_root(vault)
    target = _normalize_source_file_key(raw_rel)
    if target is None:
        return None
    return _source_file_index_for(vault_root, index).get(target)


def provenance_links_for_raw(
    vault: Path,
    raw_rel: str,
    *,
    project: str = "",
    exclude_href: str | None = None,
    index: dict[str, Path] | None = None,
) -> list[SourceLink]:
    """Wiki-summary (+ nested ``sources:``) links for a session/document page.

    Finds the matching wiki source summary for ``raw_rel``. Prefer that
    summary's built HTML (typically the session/document page); when that
    would be ``exclude_href`` (the page being rendered) or is missing, fall
    back to the raw site copy (``site/sources/…`` for sessions,
    ``site/documents/….md`` for docs). Also includes any further
    ``sources:`` listed on the wiki summary itself.

    Pass ``index`` from :func:`build_source_file_index` when rendering many
    pages in one build so the sources tree is scanned only once.
    """
    vault_root = _vault_root(vault)
    src_path = find_wiki_source_for_raw(vault_root, raw_rel, index=index)
    if src_path is None:
        return []
    locator = _rel_to_vault(vault_root, src_path)
    try:
        text = src_path.read_text(encoding="utf-8")
    except OSError:
        return []
    meta, _ = parse_frontmatter(text)
    source_hop = TraceHop(
        role="source",
        title=_title_from(meta, src_path.stem),
        location=locator,
        status="ok",
        site_href=_site_href_for_wiki_page(vault_root, src_path, text),
    )
    raw_hop = _raw_hop(vault_root, _meta_str(meta, "source_file") or raw_rel)
    proj = _source_project(meta) or project
    links: list[SourceLink] = []
    seen: set[str] = set()
    primary = _link_from_source_and_raw(
        source_hop,
        raw_hop,
        project=proj,
        exclude_href=exclude_href,
    )
    if primary is not None:
        seen.add(primary.href)
        links.append(primary)
    for link in sources_links(vault_root, locator, exclude_href=exclude_href):
        if link.href not in seen:
            seen.add(link.href)
            links.append(link)
    return links


def format_sources_html(
    links: list[SourceLink],
    *,
    link_prefix: str = "",
) -> str:
    """Render a Sources list, or ``""`` when there is nothing to show (FR2)."""
    if not links:
        return ""
    rows: list[str] = []
    for link in links:
        href = html.escape(f"{link_prefix}{link.href}", quote=True)
        label = html.escape(link.title)
        if link.is_raw:
            rows.append(
                f'<li><a href="{href}" target="_blank" rel="noopener">{label}'
                f' <span class="muted">(raw)</span></a></li>'
            )
        else:
            rows.append(f'<li><a href="{href}">{label}</a></li>')
    return (
        '<div class="provenance-sources">\n'
        "<h2>Sources</h2>\n"
        '<ul class="provenance-sources-list">\n'
        + "\n".join(rows)
        + "\n</ul>\n</div>\n"
    )
