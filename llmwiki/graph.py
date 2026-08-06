"""Knowledge graph builder for llmwiki.

Walks every file under `wiki/` looking for `[[wikilink]]` references, builds a
node-and-edge list, writes `graph/graph.json`, and generates an interactive
`graph/graph.html` using vis.js loaded from a CDN (optional offline fallback).

Stdlib only — no networkx, no vis.js bundled.

Usage:

    python3 -m llmwiki graph              # writes graph/graph.json + graph.html
    python3 -m llmwiki graph --json       # json only
    python3 -m llmwiki graph --html       # html only
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from llmwiki import REPO_ROOT
from llmwiki._frontmatter import parse_frontmatter
from llmwiki.wikilinks import WIKILINK_RE

WIKI_DIR = REPO_ROOT / "wiki"
GRAPH_DIR = REPO_ROOT / "graph"

# Wiki sources often use ``YYYY-MM-DD-<raw-stem>`` filenames while raw/
# sessions/ and site/sessions/ use ``<raw-stem>`` (wiki-add, #54).
_DATE_WIKI_STEM = re.compile(r"^\d{4}-\d{2}-\d{2}-(.+)$")

# #328: wiki-layer pages that have no corresponding site HTML page.
# Graph clicks on these used to 404 — the viewer now disables the click
# and shows a tooltip.  We keep the node + edges (for the graph
# topology) but mark `site_url = None`.
_NO_SITE_TYPES = {"entities", "concepts", "syntheses", "questions",
                  "comparisons", "hot", "categories", "projects_meta"}
# #arch-l7: canonical system-page list lives in llmwiki/_system_pages.py.
# Graph wants the slug form (already stripped of `.md`); lint wants the
# filename form. Same set, different shape.
from llmwiki._system_pages import SYSTEM_PAGE_SLUGS as _NO_SITE_BASENAMES  # noqa: E402


def _source_raw_stem(text: str, wiki_slug: str) -> str:
    """Derive the raw/session stem when ``source_file`` frontmatter is absent.

    Prefers an explicit ``slug:`` field, then strips a leading ISO date from
    the wiki filename (``2026-06-25-evrika-1-09`` → ``evrika-1-09``).
    """
    sm = re.search(r"^slug:\s*(.+)$", text, re.MULTILINE)
    if sm:
        s = sm.group(1).strip().strip("'\"")
        if s:
            return s
    dm = _DATE_WIKI_STEM.match(wiki_slug)
    if dm:
        return dm.group(1)
    return wiki_slug


def _is_raw_doc_page(text: str) -> bool:
    """True when a ``wiki/sources`` page stands for a ``raw/docs/`` document
    rather than a session transcript.

    Documents compile to ``documents/<project>/<stem>.html``
    (``raw_docs_site``) while sessions compile to ``sessions/…``, so the two
    need different link prefixes. ``llmwiki add`` stamps every raw doc with
    ``wiki-add``/``raw-doc`` tags; a genuine session page has neither, which
    keeps session links on the sessions/ prefix.
    """
    m = re.search(r"^tags:\s*(.+)$", text, re.MULTILINE)
    if not m:
        return False
    tags = m.group(1).lower()
    return "raw-doc" in tags or "wiki-add" in tags


def _source_project(text: str, rel_parts: tuple[str, ...]) -> str:
    pm = re.search(r"^project:\s*(.+)$", text, re.MULTILINE)
    if pm:
        return pm.group(1).strip().strip("'\"")
    return rel_parts[1] if len(rel_parts) >= 3 else ""


def _compute_site_url(text: str, rel_parts: tuple[str, ...],
                      slug: str, type_: str) -> str | None:
    """Map a wiki page to its generated site URL (or ``None`` when no
    site page exists).

    * ``wiki/index.md`` → ``index.html``
    * ``wiki/projects/<slug>.md`` → ``projects/<slug>.html``
    * ``wiki/sources/<proj>/<stem>.md`` → the matching compiled page, looked up
      from the ``source_file`` frontmatter field (wiki source pages use bare
      slugs but site session pages use date-prefixed stems). Session sources
      resolve under ``sessions/``; ``raw/docs/`` documents — which
      ``raw_docs_site`` renders — resolve under ``documents/``.
    * entities / concepts / syntheses / nav files → None

    Never raises — returns ``None`` on any lookup miss so the caller can
    gracefully disable the click.
    """
    if slug == "index" and len(rel_parts) == 1:
        return "index.html"
    if len(rel_parts) >= 2 and rel_parts[0] == "projects":
        return f"projects/{slug}.html"
    if len(rel_parts) >= 2 and rel_parts[0] == "sources":
        project = _source_project(text, rel_parts)
        # Primary: ``source_file`` frontmatter (CC-converted sessions).
        m = re.search(r"^source_file:[ \t]*([^\n\r]*)", text, re.MULTILINE)
        sf = m.group(1).strip().strip("'\"") if m else ""
        if sf:
            # A raw/docs/ source is a document, not a session — it compiles
            # under documents/. Splitting it on raw/sessions/ used to raise
            # and return None, so those pages got no link at all.
            if "raw/docs/" in sf:
                rel = sf.split("raw/docs/", 1)[1].removesuffix(".md")
                if "/" in rel:
                    return f"documents/{rel}.html"
                return f"documents/{project}/{rel}.html" if project else None
            try:
                rel = sf.split("raw/sessions/", 1)[1]
            except IndexError:
                return None
            rel = rel.removesuffix(".md")
            if "/" in rel:
                return f"sessions/{rel}.html"
            if not project:
                return None
            return f"sessions/{project}/{rel}.html"
        # No source_file: session pages and wiki-add raw docs both land here,
        # and they compile under different roots — pick by the raw-doc tags.
        raw_stem = _source_raw_stem(text, slug)
        if project and raw_stem:
            root = "documents" if _is_raw_doc_page(text) else "sessions"
            return f"{root}/{project}/{raw_stem}.html"
        return None
    if type_ in _NO_SITE_TYPES:
        return None
    if slug in _NO_SITE_BASENAMES:
        return None
    return None


def _frontmatter_str(meta: dict[str, Any], key: str) -> str | None:
    """Return one frontmatter field as a trimmed string, or ``None``.

    ``_parse_scalar`` coerces bare ints/floats, so values are normalised back
    to text. Absent, empty, and whitespace-only all collapse to ``None`` — no
    fallback to another field is invented here (#108, FR2).
    """
    value = meta.get(key)
    if value is None or isinstance(value, list | dict):
        return None
    return str(value).strip() or None


def scan_pages(wiki_dir: Path | None = None) -> dict[str, dict[str, Any]]:
    """Return a dict {slug: {path, type, title, out_links, site_url,
    last_updated, date}}.

    ``last_updated`` is the page's own review date and ``date`` is the date the
    page records for itself — on a source page that is the session's date, not
    the time synth ran. Both are ``None`` when the frontmatter omits them.

    ``wiki_dir`` defaults to the module ``WIKI_DIR`` (repo mode). Pass a
    vault's ``wiki/`` here so ``build --vault`` graphs the vault's pages
    instead of the repo's demo wiki (#54).
    """
    wiki_dir = wiki_dir or WIKI_DIR
    # `path` is reported relative to the wiki root's parent so vault and
    # repo builds both yield stable ``wiki/...`` paths.
    path_root = wiki_dir.parent
    pages: dict[str, dict[str, Any]] = {}
    if not wiki_dir.exists():
        return pages
    for p in sorted(wiki_dir.rglob("*.md")):
        slug = p.stem
        if slug in ("README",):
            continue
        # Type = parent directory name when under sources/entities/concepts/etc.
        try:
            rel = p.relative_to(wiki_dir)
            type_ = rel.parts[0] if len(rel.parts) > 1 else "root"
        except ValueError:
            type_ = "root"
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        # One frontmatter parse feeds title, review date, and page date.
        meta, _body = parse_frontmatter(text)
        title = _frontmatter_str(meta, "title") or slug
        # Extract wikilinks
        out_links = set(WIKILINK_RE.findall(text))
        site_url = _compute_site_url(text, rel.parts, slug, type_)
        pages[slug] = {
            "path": str(p.relative_to(path_root)),
            "type": type_,
            "title": title,
            "out_links": out_links,
            "site_url": site_url,
            "last_updated": _frontmatter_str(meta, "last_updated"),
            "date": _frontmatter_str(meta, "date"),
        }
    return pages


def _verify_site_url(site_url: str | None, site_dir: Path | None) -> str | None:
    """Return ``site_url`` unchanged if the file exists, else ``None``.

    #328: prevents the viewer from offering links that 404.  When
    ``site_dir`` is ``None`` (graph built before the site has been
    compiled) we keep the URL as-is — the caller is telling us the
    site doesn't exist yet, and we'd rather have a 404 than drop
    every session link.
    """
    if not site_url or site_dir is None:
        return site_url
    if not site_dir.is_dir():
        return site_url
    return site_url if (site_dir / site_url).is_file() else None


def build_graph(verify_site_dir: Path | None = None,
                wiki_dir: Path | None = None) -> dict[str, Any]:
    """Build the knowledge graph.

    ``verify_site_dir``: when given and the directory exists, each
    node's ``site_url`` is validated against the compiled site — URLs
    pointing at non-existent files are nulled so the viewer shows a
    graceful tooltip instead of 404ing.  Defaults to ``site/`` under
    ``REPO_ROOT`` when called from ``copy_to_site`` (see below).

    ``wiki_dir``: the ``wiki/`` to graph; defaults to the repo's. Pass a
    vault's ``wiki/`` so ``build --vault`` graphs the user's pages (#54).
    """
    pages = scan_pages(wiki_dir)
    if verify_site_dir is not None:
        for p in pages.values():
            p["site_url"] = _verify_site_url(p.get("site_url"), verify_site_dir)

    # Compute in-degree
    in_deg: dict[str, int] = {slug: 0 for slug in pages}
    for page in pages.values():
        for target in page["out_links"]:
            if target in in_deg:
                in_deg[target] += 1

    # Nodes
    nodes = []
    for slug, page in pages.items():
        nodes.append(
            {
                "id": slug,
                "label": page["title"],
                "type": page["type"],
                "path": page["path"],
                # #328: map wiki page → real site HTML URL so clicks don't 404.
                # None for pages that have no compiled site page.
                "site_url": page.get("site_url"),
                "in_degree": in_deg.get(slug, 0),
                "out_degree": len(page["out_links"]),
            }
        )

    # Edges
    edges = []
    broken_edges = []
    for slug, page in pages.items():
        for target in page["out_links"]:
            if target in pages:
                edges.append({"source": slug, "target": target})
            else:
                broken_edges.append({"source": slug, "target": target, "broken": True})

    return {
        "nodes": nodes,
        "edges": edges,
        "broken_edges": broken_edges,
        "stats": {
            "total_pages": len(pages),
            "total_edges": len(edges),
            "broken_edges": len(broken_edges),
            "orphans": [n["id"] for n in nodes if n["in_degree"] == 0],
            "top_linked": sorted(nodes, key=lambda n: -n["in_degree"])[:5],
            "top_linking": sorted(nodes, key=lambda n: -n["out_degree"])[:5],
        },
    }


def write_json(graph: dict[str, Any], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(graph, indent=2), encoding="utf-8")


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<script>
  // #477: read the same localStorage key the rest of the site uses
  // ("llmwiki-theme") BEFORE first paint to avoid a flash of the wrong
  // theme. Falls back to system preference, then dark.
  (function () {
    try {
      var t = localStorage.getItem('llmwiki-theme');
      if (!t) {
        t = (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) ? 'light' : 'dark';
      }
      document.documentElement.setAttribute('data-theme', t);
    } catch (e) {
      document.documentElement.setAttribute('data-theme', 'dark');
    }
  })();
</script>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>llmwiki — Knowledge Graph</title>
<!-- #456: pull in the same site stylesheet so the top nav we inject below
     looks identical to every other page on the site. Loaded BEFORE the
     graph's own <style> block so graph-specific selectors (#header, #network,
     etc.) keep their precedence and the visualization layout is untouched. -->
<link rel="stylesheet" href="style.css">
<style>
  /* Theme vars — mirror the site palette so dark/light sync works. */
  :root[data-theme="dark"] {
    --g-bg: #0c0a1d;
    --g-panel: #110f26;
    --g-border: #2d2b4a;
    --g-text: #e2e8f0;
    --g-muted: #94a3b8;
    --g-accent: #a78bfa;
    --g-node-source: #7c3aed;
    --g-node-entities: #2563eb;
    --g-node-concepts: #059669;
    --g-node-syntheses: #d97706;
    --g-node-projects: #db2777;
    --g-node-questions: #0891b2;
    --g-node-comparisons: #b45309;
    --g-node-other: #65a30d;
    --g-node-root: #64748b;
    --g-node-topic: #7c3aed;
    --g-orphan: #ef4444;
    --g-edge: rgba(148, 163, 184, 0.4);
    --g-highlight: #facc15;
    --g-search-match: #ef4444;
  }
  :root[data-theme="light"] {
    --g-bg: #f8fafc;
    --g-panel: #ffffff;
    --g-border: #e2e8f0;
    --g-text: #0f172a;
    --g-muted: #475569;
    --g-accent: #7c3aed;
    --g-node-source: #7c3aed;
    --g-node-entities: #2563eb;
    --g-node-concepts: #059669;
    --g-node-syntheses: #d97706;
    --g-node-projects: #db2777;
    --g-node-questions: #0891b2;
    --g-node-comparisons: #b45309;
    --g-node-other: #65a30d;
    --g-node-root: #64748b;
    --g-node-topic: #7c3aed;
    --g-orphan: #dc2626;
    --g-edge: rgba(100, 116, 139, 0.45);
    --g-highlight: #ca8a04;
    --g-search-match: #dc2626;
  }

  html, body {
    margin: 0; padding: 0; height: 100%;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: var(--g-bg); color: var(--g-text);
    transition: background 0.2s, color 0.2s;
  }
  #header {
    padding: 12px 20px; border-bottom: 1px solid var(--g-border);
    background: var(--g-panel);
    display: flex; align-items: center; gap: 16px; flex-wrap: wrap;
  }
  #header h1 { margin: 0; font-size: 1.05rem; font-weight: 600; flex: 0 0 auto; }
  #header .crumbs { font-size: 0.82rem; color: var(--g-muted); }
  #header .spacer { flex: 1 1 auto; }

  .control {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 6px 10px; border: 1px solid var(--g-border); border-radius: 6px;
    background: var(--g-bg); color: var(--g-text);
    font-size: 0.82rem; cursor: pointer;
    transition: background 0.15s, border-color 0.15s;
  }
  .control:hover { border-color: var(--g-accent); }
  .control input {
    border: none; outline: none; background: transparent;
    color: var(--g-text); font-size: 0.82rem; min-width: 160px;
  }
  .control input::placeholder { color: var(--g-muted); }
  /* #21: layout-density dropdown sits in the same control pill as the
     cluster toggle. Match the pill's typography; kill the native chrome. */
  .control select {
    border: none; outline: none; background: transparent;
    color: var(--g-text); font-size: 0.82rem; font-family: inherit;
    cursor: pointer; font-weight: 600;
  }
  .control select option { background: var(--g-panel); color: var(--g-text); }

  /* #456: site nav above the graph subheader takes ~56px; subheader itself
     ~58px. Subtract both so the canvas fills the remaining viewport.
     #328: #graph-stage is the positioning context for the overlays, which
     are siblings of #network (vis wipes #network's own children on init). */
  #graph-stage { position: relative; width: 100%; height: calc(100vh - 56px - 58px); }
  #network { width: 100%; height: 100%; }

  /* Orphan highlight: nodes with 0 inbound links get a red stroke.
     This matches the issue's "orphan pages glow red" requirement. */

  #stats-overlay {
    position: absolute; bottom: 16px; right: 16px;
    background: var(--g-panel); border: 1px solid var(--g-border);
    border-radius: 8px; padding: 12px 16px;
    max-width: 280px; font-size: 0.8rem;
    box-shadow: 0 6px 24px rgba(0, 0, 0, 0.3);
    backdrop-filter: blur(4px);
    z-index: 10;
  }
  #stats-overlay h3 {
    margin: 0 0 8px 0; font-size: 0.78rem;
    text-transform: uppercase; letter-spacing: 0.04em;
    color: var(--g-muted);
  }
  /* Rows carry dates as well as counts (#108 FR7): a value too wide to sit
     beside its label wraps under it rather than colliding with it. */
  #stats-overlay .stat {
    display: flex; flex-wrap: wrap; gap: 2px 12px;
    justify-content: space-between; padding: 2px 0; }
  #stats-overlay .stat b { color: var(--g-text); margin-left: auto; white-space: nowrap; }
  #stats-overlay .hub-item { font-family: ui-monospace, monospace; font-size: 0.75rem; color: var(--g-muted); }
  #stats-overlay .hub-item b { color: var(--g-accent); }
  /* #54 topic-mode side panel: per-topic / per-edge content can run long, so
     cap the height and scroll. */
  #stats-overlay { max-height: calc(100vh - 160px); overflow-y: auto; }
  #stats-overlay h3 { position: sticky; top: 0; background: var(--g-panel); }
  #stats-overlay .panel-open {
    display: inline-block; margin: 6px 0 2px; font-size: 0.78rem;
    color: var(--g-accent); text-decoration: none; font-weight: 600;
  }
  #stats-overlay .panel-sessions { display: flex; flex-direction: column; gap: 3px; }
  #stats-overlay .panel-sessions .panel-link {
    font-size: 0.76rem; color: var(--g-text); text-decoration: none;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
  #stats-overlay .panel-sessions .panel-link:hover { color: var(--g-accent); text-decoration: underline; }
  #stats-overlay .panel-muted { font-size: 0.74rem; color: var(--g-muted); }

  #legend {
    position: absolute; top: 16px; right: 16px;
    background: var(--g-panel); border: 1px solid var(--g-border);
    border-radius: 8px; padding: 10px 14px;
    font-size: 0.75rem; z-index: 10;
  }
  #legend .dot {
    display: inline-block; width: 10px; height: 10px;
    border-radius: 50%; margin-right: 6px; vertical-align: middle;
  }
  #legend .row { padding: 2px 0; color: var(--g-muted); }

  #offline-notice {
    position: absolute; inset: 0; display: none;
    align-items: center; justify-content: center;
    background: var(--g-bg); color: var(--g-muted);
    font-size: 0.9rem; z-index: 20;
  }
  #offline-notice.show { display: flex; }

  /* G-19 (#305): node context menu — shown on right-click or long-tap.
     Keyboard-accessible; closes on Escape / outside click. */
  #ctx-menu {
    /* position: fixed — placed from clientX/clientY (viewport coords) in
       showContextMenu, so a fixed box lands exactly under the pointer. */
    position: fixed; display: none; z-index: 30;
    min-width: 220px;
    background: var(--g-panel); border: 1px solid var(--g-border);
    border-radius: 8px; padding: 4px; font-size: 0.82rem;
    box-shadow: 0 8px 30px rgba(0, 0, 0, 0.35);
  }
  #ctx-menu.show { display: block; }
  #ctx-menu .ctx-header {
    padding: 6px 10px; font-family: ui-monospace, monospace;
    font-size: 0.75rem; color: var(--g-muted);
    border-bottom: 1px solid var(--g-border); margin-bottom: 4px;
  }
  #ctx-menu button {
    display: block; width: 100%; text-align: left;
    padding: 7px 10px; border: 0; border-radius: 5px;
    background: transparent; color: var(--g-text);
    font-size: 0.82rem; cursor: pointer;
    font-family: inherit;
  }
  #ctx-menu button:hover:not([disabled]),
  #ctx-menu button:focus:not([disabled]) {
    background: rgba(124, 58, 237, 0.18);
    outline: none;
  }
  #ctx-menu button[disabled] {
    color: var(--g-muted); cursor: not-allowed; opacity: 0.55;
  }
  #ctx-menu .ctx-kbd {
    float: right; font-family: ui-monospace, monospace;
    font-size: 0.7rem; color: var(--g-muted);
    margin-left: 12px;
  }
  #ctx-menu .ctx-separator {
    height: 1px; background: var(--g-border);
    margin: 4px -4px;
  }

  a { color: var(--g-accent); }

  @media (max-width: 640px) {
    #stats-overlay, #legend { max-width: 180px; font-size: 0.72rem; }
  }
</style>
<!-- #ui-h14 (#571): pin vis-network to a specific version + SRI hash so
     a malicious or accidental upstream change can't ship code to every
     visitor of the site. Bump the version + regenerate integrity via
     `curl -s <url> | openssl dgst -sha384 -binary | openssl base64 -A`
     when upgrading. -->
<script src="https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js"
        integrity="sha384-yxKDWWf0wwdUj/gPeuL11czrnKFQROnLgY8ll7En9NYoXibgg3C6NK/UDHNtUgWJ"
        crossorigin="anonymous"
        referrerpolicy="no-referrer"></script>
</head>
<body>
<a href="#main-content" class="skip-link">Skip to content</a>
__SITE_NAV__
<main id="main-content">
<div id="header">
  <h1>llmwiki — Knowledge Graph</h1>
  <span class="crumbs" id="top-crumbs"></span>
  <span class="spacer"></span>
  <label class="control" title="Filter nodes by label">
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
    <input id="search-input" type="search" placeholder="Search nodes… (type to filter)" autocomplete="off">
  </label>
  <!-- #21: layout-density switch. 'sparse' (forceAtlas2, loose springs) is
       the default readable spread; 'tight' pulls single-edge leaf topics
       back toward the cluster with extra central gravity. Choice persists
       in localStorage so it survives navigation. -->
  <label class="control" title="Layout density">
    Layout:
    <select id="layout-select" aria-label="Layout density">
      <option value="sparse">sparse</option>
      <option value="tight">tight</option>
    </select>
  </label>
  <button class="control" id="cluster-toggle" title="Group nodes by kind (entities, concepts, …)">
    Cluster: <b id="cluster-mode">off</b>
  </button>
  <!-- #456: removed the standalone back-to-site link and theme toggle —
       both responsibilities now live in the site nav above. The site's
       script.js wires #theme-toggle (in the nav) to data-theme +
       localStorage.llmwiki-theme; the graph's CSS reacts to data-theme
       via :root[data-theme=...] selectors so the visualization re-themes
       in lockstep without needing a duplicate ID here. -->
</div>

<!-- #328: the overlays (legend / stats / context menu / offline notice) are
     SIBLINGS of #network, not children. vis-network takes over its container
     and wipes any pre-existing children on init — nesting these inside
     #network silently destroyed the legend, stats and context menu (and made
     every click throw on the now-null ctxMenu). #graph-stage is the shared
     positioning context so the absolutely-positioned overlays still sit over
     the canvas. -->
<div id="graph-stage">
<div id="network"></div>
  <div id="offline-notice">vis-network failed to load — check your connection or host the library locally.</div>
  <div id="legend" aria-label="Node color legend">
    <div class="row"><span class="dot" style="background: var(--g-node-source)"></span>sources</div>
    <div class="row"><span class="dot" style="background: var(--g-node-entities)"></span>entities</div>
    <div class="row"><span class="dot" style="background: var(--g-node-concepts)"></span>concepts</div>
    <div class="row"><span class="dot" style="background: var(--g-node-syntheses)"></span>syntheses</div>
    <div class="row"><span class="dot" style="border: 2px solid var(--g-orphan); background: transparent"></span>orphan</div>
  </div>
  <div id="stats-overlay" aria-label="Graph statistics">
    <h3>Stats</h3>
    <div class="stat"><span>Pages</span><b id="s-pages">0</b></div>
    <div class="stat"><span>Edges</span><b id="s-edges">0</b></div>
    <div class="stat"><span>Orphans</span><b id="s-orphans">0</b></div>
    <div class="stat"><span>Avg connections</span><b id="s-avg">0</b></div>
    <h3 style="margin-top: 10px;">Top hubs</h3>
    <div id="s-hubs"></div>
  </div>
  <!-- G-19 (#305) node context menu — right-click / long-tap target -->
  <div id="ctx-menu" role="menu" aria-label="Node actions">
    <div class="ctx-header" id="ctx-target">—</div>
    <button type="button" role="menuitem" data-action="open">Open page <span class="ctx-kbd">Enter</span></button>
    <button type="button" role="menuitem" data-action="neighbours">Find neighbours (1-hop) <span class="ctx-kbd">N</span></button>
    <button type="button" role="menuitem" data-action="copy-slug">Copy slug <span class="ctx-kbd">C</span></button>
    <button type="button" role="menuitem" data-action="copy-path">Copy wiki path</button>
    <button type="button" role="menuitem" data-action="view-references">View references (CLI hint)</button>
    <div class="ctx-separator" role="separator"></div>
    <button type="button" role="menuitem" data-action="mark-stale" disabled
            title="Requires `llmwiki serve --edit` (not yet shipped)">
      Mark stale
    </button>
    <button type="button" role="menuitem" data-action="archive" disabled
            title="Requires `llmwiki serve --edit` (not yet shipped)">
      Archive
    </button>
  </div>
</div>
</main>
__SITE_PALETTE__
<!-- #456: load the site's script.js so the nav's command palette,
     theme toggle, and keyboard shortcuts (g h / g p / g s / / / ?) work
     here too. The site's theme handler reads & writes the same
     localStorage key (`llmwiki-theme`) the pre-paint script in <head>
     reads, so the graph's data-theme stays in sync without a local
     handler. -->
<script src="script.js" defer></script>

<script>
'use strict';
const GRAPH = __GRAPH_JSON__;

// #456: graph used to wire its own #theme-toggle button + #theme-label.
// Both responsibilities now live in the site nav (script.js handles the
// click; CSS variables react to data-theme automatically). Local handler
// removed so two listeners don't fight over the same event.
const root = document.documentElement;

// ─── Check vis-network loaded (local fallback hook) ────────────────────
if (typeof vis === 'undefined') {
  document.getElementById('offline-notice').classList.add('show');
} else {
  main();
}

function main() {
  const cssVar = name =>
    getComputedStyle(document.documentElement).getPropertyValue(name).trim() || '#7c3aed';
  const colors = {
    sources: () => cssVar('--g-node-source'),
    entities: () => cssVar('--g-node-entities'),
    concepts: () => cssVar('--g-node-concepts'),
    syntheses: () => cssVar('--g-node-syntheses'),
    projects: () => cssVar('--g-node-projects'),
    questions: () => cssVar('--g-node-questions'),
    comparisons: () => cssVar('--g-node-comparisons'),
    other: () => cssVar('--g-node-other'),
    root: () => cssVar('--g-node-root'),
    topic: () => cssVar('--g-node-topic'),
  };
  const orphanColor = () => cssVar('--g-orphan');
  const KIND_LABELS = {
    entities: 'Entities', concepts: 'Concepts', projects: 'Projects',
    questions: 'Questions', comparisons: 'Comparisons',
    syntheses: 'Syntheses', sources: 'Sources', other: 'Other',
  };
  const kindLabel = k => KIND_LABELS[k] || k;
  // Singular form of the same label, naming one topic in the side panel as
  // the static page's chip does (topics_page.py `_KIND_LABELS`). Derived from
  // KIND_LABELS so the forms can't drift. 'other' takes the label injected
  // from topics_page.KIND_OTHER_LABEL: no page describes the topic, and that
  // absence is itself worth naming rather than leaving the row out (#108 FR8).
  const kindLabelOne = k => {
    if (!k || k === 'other') return __KIND_OTHER_LABEL__;
    const s = kindLabel(k);
    if (s.endsWith('ies')) return s.slice(0, -3) + 'y';
    if (s.endsWith('ses')) return s.slice(0, -3) + 'sis';
    return s.replace(/s$/, '');
  };
  const kindColor = k => (colors[k] || colors.topic)();
  // Surface viewer failures on the page, not just in the console —
  // script.js owns the banner, so fall back if it hasn't loaded yet.
  const reportGraphError = (context, err) => {
    if (window.__llmwikiReportError) window.__llmwikiReportError(context, err);
    else if (window.console) console.error('[llmwiki] ' + context, err);
  };

  // #54: topic-first mode. Nodes are topics (never sessions); edges are
  // topic↔topic co-occurrences bridged by sessions. Drives sizing, the
  // contextual side panel, and double-click-to-open below.
  const TOPIC = GRAPH.mode === 'topic';
  const SESS = GRAPH.sessions || {};

  // ─── Stats overlay ───────────────────────────────────────────────────
  const stats = GRAPH.stats || {};
  const statsEl = document.getElementById('stats-overlay');
  if (TOPIC) {
    document.getElementById('top-crumbs').textContent =
      (stats.total_topics ?? GRAPH.nodes.length) + ' topics · ' +
      (stats.total_edges ?? GRAPH.edges.length) + ' connections · ' +
      (stats.total_sessions ?? 0) + ' sessions';
    const lg = document.getElementById('legend');
    // One row per kind actually present — a wiki with no concept pages
    // shouldn't advertise a concept swatch.
    const presentKinds = [...new Set(GRAPH.nodes.map(n => n.kind || 'other'))].sort();
    if (lg) lg.innerHTML =
      presentKinds.map(k =>
        '<div class="row"><span class="dot" style="background: ' + kindColor(k) +
        // 'other' reads as the panel and page chip do, not as 'Other'.
        '"></span>' + escapeHtml(k === 'other' ? kindLabelOne(k) : kindLabel(k)) + '</div>').join('') +
      '<div class="row"><span class="dot" style="background: var(--g-edge)"></span>shared sessions</div>' +
      '<div class="row" style="color:var(--g-muted)">size = #sessions</div>';
  } else {
    const pages = stats.total_pages ?? GRAPH.nodes.length;
    const edgeCount = stats.total_edges ?? GRAPH.edges.length;
    const orphans = stats.orphans ?? [];
    document.getElementById('s-pages').textContent = pages;
    document.getElementById('s-edges').textContent = edgeCount;
    document.getElementById('s-orphans').textContent = orphans.length;
    document.getElementById('s-avg').textContent =
      pages > 0 ? (edgeCount / pages).toFixed(2) : '0';
    document.getElementById('top-crumbs').textContent =
      pages + ' pages · ' + edgeCount + ' edges · ' + orphans.length + ' orphans';

    const hubsEl = document.getElementById('s-hubs');
    (stats.top_linked || []).slice(0, 5).forEach(n => {
      if (!n || n.in_degree === 0) return;
      const row = document.createElement('div');
      row.className = 'hub-item';
      row.innerHTML = '<b>' + String(n.in_degree).padStart(3) + '</b> ' +
        escapeHtml(n.id);
      hubsEl.appendChild(row);
    });
  }

  // ─── Build vis DataSets ──────────────────────────────────────────────
  const nodes = new vis.DataSet(GRAPH.nodes.map(n => {
    if (TOPIC) {
      return {
        id: n.id,
        label: n.label,
        color: {
          // Topics inherit the colour of the wiki folder they resolve to,
          // so entities and concepts stay distinguishable both loose and
          // collapsed into clusters.
          background: kindColor(n.kind),
          border: kindColor(n.kind),
          highlight: { background: cssVar('--g-highlight'), border: cssVar('--g-highlight') },
        },
        borderWidth: 1,
        value: Math.max(n.session_count || 1, 1),
        // Deliberately no `group`: vis owns that key and re-applies its own
        // automatic group palette when a cluster reopens, overwriting the
        // per-kind colours above. `kind` is ours, so it survives.
        kind: n.kind || 'other',
        title: n.label + ' · ' + (n.session_count || 0) + ' sessions · ' +
          (n.degree || 0) + ' connected\nClick to focus · double-click to open',
        site_url: n.site_url,
        session_count: n.session_count,
        degree: n.degree,
        sessions: n.sessions || [],
        // A node keeps only the keys named here, and the panel reads freshness
        // off the vis node — so these must be forwarded (#108 FR7).
        first_seen: n.first_seen,
        last_seen: n.last_seen,
        last_updated: n.last_updated,
        type: 'topic',
      };
    }
    const isOrphan = n.in_degree === 0;
    return {
      id: n.id,
      label: n.label,
      color: {
        background: (colors[n.type] || colors.root)(),
        border: isOrphan ? orphanColor() : (colors[n.type] || colors.root)(),
        highlight: { background: cssVar('--g-highlight'), border: cssVar('--g-highlight') },
      },
      borderWidth: isOrphan ? 3 : 1,
      value: Math.max(n.in_degree, 1),
      kind: n.type,
      title:
        n.type + ' · ' + n.in_degree + ' inbound, ' + n.out_degree + ' outbound' +
        (n.path ? '\nClick to open ' + n.path : ''),
      path: n.path,
      site_url: n.site_url,
      type: n.type,
    };
  }));
  // Topic edges carry their bridging-session list; index them by a stable id
  // so an edge click can show "how these two topics connect".
  const edgeData = {};
  const edges = new vis.DataSet(GRAPH.edges.map((e, i) => {
    if (TOPIC) {
      const id = 'e' + i;
      edgeData[id] = e;
      return {
        id: id,
        from: e.source,
        to: e.target,
        width: Math.min(1 + (e.weight || 1) * 0.6, 8),
        color: { color: cssVar('--g-edge'), highlight: cssVar('--g-highlight') },
        title: e.source + ' ↔ ' + e.target + ' · ' + (e.weight || 0) + ' shared sessions',
      };
    }
    return {
      from: e.source,
      to: e.target,
      arrows: 'to',
      color: { color: cssVar('--g-edge') },
      title: e.source + ' → ' + e.target,
    };
  }));

  // ─── Render network ──────────────────────────────────────────────────
  const container = document.getElementById('network');

  // #21: layout-density presets. forceAtlas2Based spreads hub-heavy graphs
  // far more evenly than barnesHut, which let the dominant hub collapse
  // everything inward into an unreadable clump. `tight` adds central
  // gravity + shorter/stiffer springs to reel single-edge leaves back in.
  const LAYOUTS = {
    sparse: {
      solver: 'forceAtlas2Based',
      forceAtlas2Based: { gravitationalConstant: -120, springLength: 180,
        springConstant: 0.08, avoidOverlap: 0.6, damping: 0.4 },
      stabilization: { iterations: 2000 },
    },
    tight: {
      solver: 'forceAtlas2Based',
      forceAtlas2Based: { gravitationalConstant: -120, centralGravity: 0.06,
        springLength: 120, springConstant: 0.14, avoidOverlap: 0.7, damping: 0.4 },
      stabilization: { iterations: 2000 },
    },
  };
  // Persisted choice (defaults to sparse). Guarded so a locked-down
  // localStorage can't break the render.
  let layoutMode = 'sparse';
  try {
    const s = localStorage.getItem('llmwiki-graph-layout');
    if (s === 'sparse' || s === 'tight') layoutMode = s;
  } catch (e) { /* private mode / disabled storage */ }

  const network = new vis.Network(container, { nodes, edges }, {
    nodes: {
      shape: 'dot',
      font: { color: cssVar('--g-text'), size: 12, face: 'system-ui' },
      scaling: { min: 8, max: 32, label: { enabled: true, min: 10, max: 18 } },
    },
    // #21: cubicBezier is a STATIC curve type, so edges keep their
    // curvature after the physics freeze. The old "continuous" type
    // rendered as near-straight lines; the "dynamic" type would curve
    // more but needs live physics, conflicting with the #9 freeze.
    edges: { smooth: { enabled: true, type: 'cubicBezier', roundness: 0.4 } },
    physics: LAYOUTS[layoutMode],
    interaction: { hover: true, tooltipDelay: 120 },
  });

  // #9: freeze the layout once the simulation settles. Physics left running
  // keeps perturbing node positions live ("shaking" on every open).
  // `once`, not `on`, and re-registered explicitly on each layout switch,
  // so a stray restabilize (e.g. clustering) never yanks the camera.
  function freezeWhenStable(fit) {
    network.once('stabilizationIterationsDone', () => {
      network.setOptions({ physics: false });
      if (fit) network.fit();
    });
  }
  freezeWhenStable(true);

  // #21: switch layout density live, then re-freeze + fit. Fitting here is
  // intentional — the #9 no-yank rule guards incidental clicks; a deliberate
  // layout change repositions every node, so framing it is expected.
  // Re-run the layout after a change that moves every node, then re-freeze
  // and frame the result. Physics is frozen the rest of the time, so
  // without this a structural change (a layout switch, or collapsing the
  // graph into clusters) leaves every node stacked at whatever position it
  // was created at, reading as one merged dot in the middle of the canvas.
  function restabilize() {
    freezeWhenStable(true);
    network.setOptions({ physics: Object.assign({ enabled: true }, LAYOUTS[layoutMode]) });
    // setOptions re-enables *live* physics but does NOT emit
    // stabilizationIterationsDone, so the freeze handler above would never
    // fire and the new layout would shake forever (#9). Kick an explicit
    // stabilization run to drive it to a settled, frozen state.
    network.stabilize();
  }

  function applyLayout(mode) {
    if (!LAYOUTS[mode]) return;
    layoutMode = mode;
    try { localStorage.setItem('llmwiki-graph-layout', mode); } catch (e) {}
    restabilize();
  }
  const layoutSelect = document.getElementById('layout-select');
  if (layoutSelect) {
    layoutSelect.value = layoutMode;
    layoutSelect.addEventListener('change', e => applyLayout(e.target.value));
  }

  // ─── Click: focus neighbourhood + navigate (#328) ─────────────────────
  // A left-click ALWAYS highlights the node's 1-hop neighbourhood — the
  // Obsidian-style "show me what links here" view — so clicking is never a
  // silent no-op. This matters because only sources, projects and sessions
  // are compiled to standalone pages (build.py); entity / concept /
  // synthesis nodes have site_url === null, and the connected core of the
  // graph is made entirely of those. Nodes that DO have a compiled page
  // additionally open it. Clicking empty canvas clears the focus.
  network.on('click', params => {
    if (params.nodes && params.nodes.length) {
      const node = nodes.get(params.nodes[0]);
      if (!node) return;
      highlightNeighbours(node.id);
      if (TOPIC) {
        showTopicPanel(node);              // single click = focus + per-topic panel
      } else if (node.site_url) {
        window.open(node.site_url, '_blank', 'noopener');
      } else {
        _flashNoSiteTooltip(node, params.event);
      }
      return;
    }
    // Empty space — or, in topic mode, an edge (its bridging sessions).
    if (TOPIC && params.edges && params.edges.length) {
      const e = edgeData[params.edges[0]];
      if (e) { try { network.selectEdges([params.edges[0]]); } catch (_) {} showEdgePanel(e); return; }
    }
    resetHighlight();
    if (TOPIC) renderGlobalStats();
  });

  // Double-click opens the node's page (the topic page in topic mode), so a
  // single click stays reserved for focus + the side panel.
  network.on('doubleClick', params => {
    if (!params.nodes || !params.nodes.length) return;
    const node = nodes.get(params.nodes[0]);
    if (node && node.site_url) window.open(node.site_url, '_blank', 'noopener');
  });

  // ─── Topic-mode side panel (#54) ──────────────────────────────────────
  // Replaces the whole-wiki Stats widget with per-topic / per-edge info.
  function topicNeighbors(id) {
    const out = [];
    (GRAPH.edges || []).forEach(e => {
      if (e.source === id) out.push([e.target, e.weight]);
      else if (e.target === id) out.push([e.source, e.weight]);
    });
    out.sort((a, b) => b[1] - a[1]);
    return out;
  }
  function topicSessionLinks(slugs, limit) {
    const rows = (slugs || []).slice(0, limit).map(s => {
      const m = SESS[s] || {};
      const t = escapeHtml(m.title || s);
      return m.url
        ? '<a class="panel-link" href="' + escapeHtml(m.url) + '">' + t + '</a>'
        : '<span class="panel-muted">' + t + '</span>';
    });
    const extra = (slugs || []).length - rows.length;
    return rows.join('') + (extra > 0 ? '<span class="panel-muted">+' + extra + ' more…</span>' : '');
  }
  function statRow(label, value) {
    return '<div class="stat"><span>' + escapeHtml(label) + '</span><b>' +
      escapeHtml(value) + '</b></div>';
  }
  // Session-derived dates, one date or a range. Empty when no session carries
  // one — never a placeholder (#108 FR2).
  function topicActivity(node) {
    const seen = [node.first_seen, node.last_seen].filter(Boolean).map(String);
    if (!seen.length) return '';
    const first = seen[0], last = seen[seen.length - 1];
    return first === last ? first : first + ' – ' + last;
  }
  // Kind and freshness — the facts the topic page names, so the map can be
  // triaged without opening pages (#108 FR7). Kind always renders, naming the
  // unclassified state when no page describes the topic. Active comes from
  // sessions, Reviewed from the page's own curation date: two facts, two rows,
  // each dropped when the node lacks its field.
  function topicIdentityRows(node) {
    let h = statRow('Kind', kindLabelOne(node.kind));
    const active = topicActivity(node);
    if (active) h += statRow('Active', active);
    if (node.last_updated) h += statRow('Reviewed', String(node.last_updated));
    return h;
  }
  function showTopicPanel(node) {
    const neigh = topicNeighbors(node.id);
    let h = '<h3>' + escapeHtml(node.label) + '</h3>';
    h += '<div class="stat"><span>Sessions</span><b>' + (node.session_count || 0) + '</b></div>';
    h += '<div class="stat"><span>Connected topics</span><b>' + (node.degree || 0) + '</b></div>';
    try {
      h += topicIdentityRows(node);
    } catch (err) {
      reportGraphError('Could not read details for "' + node.label + '"', err);
    }
    // Current tab, like every other link in the site: only double-clicking a
    // node is the deliberate "take this elsewhere" gesture (#108 FR10).
    if (node.site_url) h += '<a class="panel-open" href="' + escapeHtml(node.site_url) + '">Open page →</a>';
    if (neigh.length) {
      h += '<h3 style="margin-top:10px">Top connections</h3>';
      h += neigh.slice(0, 6).map(p =>
        '<div class="hub-item"><b>' + String(p[1]).padStart(2) + '</b> ' + escapeHtml(p[0]) + '</div>').join('');
    }
    h += '<h3 style="margin-top:10px">Sessions</h3>';
    h += '<div class="panel-sessions">' + topicSessionLinks(node.sessions, 25) + '</div>';
    statsEl.innerHTML = h;
  }
  function showEdgePanel(e) {
    let h = '<h3>' + escapeHtml(e.source) + ' ↔ ' + escapeHtml(e.target) + '</h3>';
    h += '<div class="stat"><span>Shared sessions</span><b>' + (e.weight || 0) + '</b></div>';
    h += '<p class="panel-muted" style="margin:6px 0">Sessions mentioning both:</p>';
    h += '<div class="panel-sessions">' + topicSessionLinks(e.sessions, 30) + '</div>';
    statsEl.innerHTML = h;
  }
  function renderGlobalStats() {
    const s = GRAPH.stats || {};
    let h = '<h3>Stats</h3>';
    h += '<div class="stat"><span>Topics</span><b>' + (s.total_topics ?? GRAPH.nodes.length) + '</b></div>';
    h += '<div class="stat"><span>Connections</span><b>' + (s.total_edges ?? GRAPH.edges.length) + '</b></div>';
    h += '<div class="stat"><span>Sessions</span><b>' + (s.total_sessions ?? 0) + '</b></div>';
    h += '<h3 style="margin-top:10px">Top hubs</h3>';
    (s.top_topics || []).forEach(t => {
      h += '<div class="hub-item"><b>' + String(t.count).padStart(3) + '</b> ' + escapeHtml(t.id) + '</div>';
    });
    h += '<p class="panel-muted" style="margin-top:8px">Click a topic to focus · double-click to open · click an edge for shared sessions</p>';
    statsEl.innerHTML = h;
  }
  if (TOPIC) renderGlobalStats();

  // Restore every node to its base colour — clears a neighbourhood focus
  // (or a search dim). Defined here, called only at interaction time, so
  // `baseColors` is already populated by then.
  function resetHighlight() {
    const update = [];
    nodes.forEach(n => { update.push({ id: n.id, color: baseColors[n.id] }); });
    nodes.update(update);
  }

  // Transient "no page" hint for entity / concept / nav nodes.
  function _flashNoSiteTooltip(node, ev) {
    const tip = document.createElement('div');
    tip.textContent = node.label + ' — no compiled page (see ## Connections)';
    tip.style.cssText =
      'position:fixed;z-index:50;padding:6px 10px;border-radius:6px;' +
      'background:var(--g-panel);border:1px solid var(--g-border);' +
      'color:var(--g-muted);font-size:0.78rem;' +
      'pointer-events:none;transition:opacity 0.3s;';
    tip.style.left = (ev.clientX + 12) + 'px';
    tip.style.top = (ev.clientY + 12) + 'px';
    document.body.appendChild(tip);
    setTimeout(() => { tip.style.opacity = '0'; }, 1400);
    setTimeout(() => { tip.remove(); }, 1800);
  }

  // ─── G-19 (#305): node context menu ──────────────────────────────────
  // The context menu is wired up only when its DOM nodes are present.
  // Closes #386 — a minimal graph render without these elements would
  // throw on the addEventListener calls below.
  const ctxMenu = document.getElementById('ctx-menu');
  const ctxTarget = document.getElementById('ctx-target');
  let ctxNode = null;

  function showContextMenu(nodeId, clientX, clientY) {
    const node = nodes.get(nodeId);
    if (!node) return;
    ctxNode = node;
    ctxTarget.textContent = node.label || node.id;
    // Position the menu, clamped inside the viewport.
    ctxMenu.style.left = '0px';
    ctxMenu.style.top = '0px';
    ctxMenu.classList.add('show');
    const rect = ctxMenu.getBoundingClientRect();
    const maxX = window.innerWidth - rect.width - 8;
    const maxY = window.innerHeight - rect.height - 8;
    ctxMenu.style.left = Math.min(clientX, maxX) + 'px';
    ctxMenu.style.top = Math.min(clientY, maxY) + 'px';
    const first = ctxMenu.querySelector('button:not([disabled])');
    if (first) first.focus();
  }

  function hideContextMenu() {
    ctxMenu.classList.remove('show');
    ctxNode = null;
  }

  network.on('oncontext', params => {
    const nodeId = network.getNodeAt(params.pointer.DOM);
    if (nodeId) {
      // Only swallow the native menu where we actually replace it.
      params.event.preventDefault();
      showContextMenu(nodeId, params.event.clientX, params.event.clientY);
    } else {
      // Right-click on empty canvas belongs to the browser: the native
      // context menu, and mouse-gesture extensions that drive navigation
      // from a held right button. Preventing it unconditionally made the
      // graph page the one place on the site where those stop working.
      hideContextMenu();
    }
  });

  document.addEventListener('click', e => {
    if (!ctxMenu.contains(e.target)) hideContextMenu();
  });
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && ctxMenu.classList.contains('show')) {
      e.preventDefault();
      hideContextMenu();
    }
  });

  // Highlight the 1-hop neighbourhood of `nodeId`; dim everything else.
  function highlightNeighbours(nodeId) {
    const neighbourIds = new Set([nodeId]);
    GRAPH.edges.forEach(e => {
      if (e.source === nodeId) neighbourIds.add(e.target);
      if (e.target === nodeId) neighbourIds.add(e.source);
    });
    const update = [];
    nodes.forEach(n => {
      const inSet = neighbourIds.has(n.id);
      update.push({
        id: n.id,
        color: inSet
          ? baseColors[n.id]
          : { background: 'rgba(100,100,100,0.12)', border: 'rgba(100,100,100,0.25)' },
      });
    });
    nodes.update(update);
  }

  async function copyToClipboard(text) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (_) {
      // Fallback: textarea trick for older browsers / privacy mode.
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.style.position = 'fixed'; ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.focus(); ta.select();
      let ok = false;
      try { ok = document.execCommand('copy'); } catch (_) {}
      document.body.removeChild(ta);
      return ok;
    }
  }

  if (ctxMenu) ctxMenu.addEventListener('click', async e => {
    const btn = e.target.closest('button[data-action]');
    if (!btn || btn.disabled || !ctxNode) return;
    const action = btn.dataset.action;
    const node = ctxNode;
    hideContextMenu();
    switch (action) {
      case 'open': {
        // #328: use precomputed site_url so nodes without a compiled
        // page degrade gracefully instead of 404. Navigates in the current
        // tab — only double-click opens a new one (#108 FR10).
        if (node.site_url) {
          window.location.href = node.site_url;
        } else {
          alert(node.label + ' — no compiled page exists for this node. '
            + 'Entities, concepts, and nav files live in wiki/ but aren\u2019t rendered as standalone site pages.');
        }
        break;
      }
      case 'neighbours':
        highlightNeighbours(node.id);
        break;
      case 'copy-slug':
        await copyToClipboard(String(node.id));
        break;
      case 'copy-path':
        await copyToClipboard(String(node.path || node.id));
        break;
      case 'view-references': {
        const slug = String(node.id).replace(/"/g, '\\"');
        await copyToClipboard('llmwiki references "' + slug + '"');
        alert('Copied CLI command to clipboard:\n\n  llmwiki references "' + slug + '"');
        break;
      }
      default:
        /* mark-stale / archive: disabled placeholder — requires edit mode */
        break;
    }
  });

  // Keyboard shortcuts while menu is visible.
  if (ctxMenu) ctxMenu.addEventListener('keydown', e => {
    if (!ctxNode) return;
    const map = { 'n': 'neighbours', 'c': 'copy-slug', 'Enter': 'open' };
    const action = map[e.key];
    if (action) {
      const btn = ctxMenu.querySelector('button[data-action="' + action + '"]');
      if (btn && !btn.disabled) { e.preventDefault(); btn.click(); }
    }
  });

  // ─── Live search filter ──────────────────────────────────────────────
  const searchInput = document.getElementById('search-input');
  let baseColors = {};
  nodes.forEach(n => { baseColors[n.id] = n.color; });

  function applyFilter(q) {
    q = (q || '').trim().toLowerCase();
    // #9: matches get a dedicated red — base palette colors are too dim
    // against the blue-ish background to read as "found". Resolved per
    // call so a theme flip mid-search picks up the right shade.
    const matchColor = {
      background: cssVar('--g-search-match'),
      border: cssVar('--g-search-match'),
    };
    const update = [];
    nodes.forEach(n => {
      const label = (n.label || '').toString().toLowerCase();
      const dim = q && !label.includes(q) && !String(n.id).toLowerCase().includes(q);
      update.push({
        id: n.id,
        color: dim ? { background: 'rgba(100,100,100,0.15)', border: 'rgba(100,100,100,0.3)' }
                   : (q ? matchColor : baseColors[n.id]),
      });
    });
    nodes.update(update);
  }
  if (searchInput) searchInput.addEventListener('input', e => applyFilter(e.target.value));

  // ─── Cluster toggle ──────────────────────────────────────────────────
  // Groups on `kind` (the wiki folder a node resolves to), not `type`: in
  // topic mode every node's type is literally 'topic', so a type-keyed
  // cluster collapses the whole graph into one dot and hides every edge.
  const nodeKind = n => n.kind || n.type || 'other';
  const clusterKinds = [...new Set(GRAPH.nodes.map(nodeKind))].sort();
  let clusterMode = 'off';
  const clusterBtn = document.getElementById('cluster-toggle');
  const clusterModeEl = document.getElementById('cluster-mode');
  if (clusterBtn && clusterKinds.length < 2) {
    // One kind means one cluster means a single dot — say so rather than
    // offer a control that can only make the graph less useful.
    clusterBtn.disabled = true;
    clusterBtn.title = 'Nothing to cluster: every node is "' +
      kindLabel(clusterKinds[0] || 'other') + '". Clusters appear once the ' +
      'wiki has pages in more than one folder (entities, concepts, …).';
    if (clusterModeEl) clusterModeEl.textContent = 'n/a';
  } else if (clusterBtn) {
    clusterBtn.title = 'Group nodes by kind (' +
      clusterKinds.map(kindLabel).join(' · ') + ')';
    clusterBtn.addEventListener('click', () => {
      clusterMode = clusterMode === 'off' ? 'kind' : 'off';
      if (clusterModeEl) clusterModeEl.textContent = clusterMode;
      if (clusterMode === 'kind') {
        clusterKinds.forEach(k => {
          const size = GRAPH.nodes.filter(n => nodeKind(n) === k).length;
          // vis refuses to wrap a single node (and logs its own error
          // trying). A lone node already reads as itself.
          if (size < 2) return;
          try {
            network.cluster({
              // joinCondition re-runs over what's on the canvas, which now
              // includes clusters from earlier passes. A cluster node only
              // carries the properties we gave it, so without this guard
              // the `kind` fallback sorts every existing cluster into the
              // kind being built and nests them inside it.
              joinCondition: n => !n.isKindCluster && nodeKind(n) === k,
              clusterNodeProperties: {
                id: 'cluster:' + k,
                label: kindLabel(k) + ' (' + size + ')',
                color: { background: kindColor(k), border: kindColor(k) },
                value: size,
                kind: k,
                isKindCluster: true,
              },
            });
          } catch (err) {
            reportGraphError('Could not cluster "' + kindLabel(k) + '"', err);
          }
        });
      } else {
        clusterKinds.forEach(k => {
          const id = 'cluster:' + k;
          try {
            if (network.isCluster(id)) network.openCluster(id);
          } catch (err) {
            reportGraphError('Could not expand "' + kindLabel(k) + '"', err);
          }
        });
      }
      // Clustering and expanding both create nodes at a single point with
      // physics frozen. Re-run the layout so they spread out and the view
      // reframes on what is now on screen.
      restabilize();
    });
  }
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}
</script>
</body>
</html>
"""


def write_html(graph: dict[str, Any], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # json.dumps with ensure_ascii=False keeps unicode labels readable in
    # source view. Embedding the JSON directly in a ``<script>`` block is
    # safe because ``json.dumps`` escapes ``</`` sequences; we also double-
    # check that there's no ``</script>`` in the rendered text below.
    payload = json.dumps(graph, ensure_ascii=False)
    # Post-final-review: HTML parsers are case-insensitive on tag names,
    # so `</SCRIPT>` and `</Script>` would still close our block early.
    # Match all variants — same fix in exporters.py.
    payload = re.sub(r"</script\b", "<\\/script", payload, flags=re.IGNORECASE)
    # #456: inject the site's standard nav so graph.html isn't a navigation
    # dead end. Imported lazily to avoid a top-level circular dependency
    # (build.py imports graph.copy_to_site).
    from llmwiki.build import nav_bar, search_palette_markup  # noqa: PLC0415 — cycle: graph↔build

    # The panel names an undescribed topic exactly as the static page's chip
    # does, so the label has one definition (#108 FR7).
    from llmwiki.topics_page import KIND_OTHER_LABEL  # noqa: PLC0415 — cycle: graph↔topics↔graph

    site_nav_html = nav_bar(active="graph", link_prefix="")
    # The nav renders a search button and script.js binds Cmd+K, but both
    # no-op unless the dialog they open is on the page too — graph.html
    # shipped the button without the dialog until this was wired up.
    # `__GRAPH_JSON__` goes in last: it is the only substitution carrying wiki
    # text, so a page titled `__SITE_NAV__` cannot have its own title replaced
    # once the payload is already in place.
    html = (
        HTML_TEMPLATE
        .replace("__SITE_NAV__", site_nav_html)
        .replace("__SITE_PALETTE__", search_palette_markup(js_prefix=""))
        .replace("__KIND_OTHER_LABEL__", json.dumps(KIND_OTHER_LABEL))
        .replace("__GRAPH_JSON__", payload)
    )
    out_path.write_text(html, encoding="utf-8")


def copy_to_site(site_dir: Path, *, graph: dict[str, Any] | None = None,
                 wiki_dir: Path | None = None) -> Path | None:
    """Emit ``site/graph.html`` so the interactive viewer is reachable
    from the static site (v1.1.0 · #118).

    If ``graph`` is omitted we rebuild it from the wiki on the fly so
    callers can wire this into ``build_site()`` without having to run
    ``llmwiki graph`` first.

    ``wiki_dir`` selects which ``wiki/`` to graph (default: repo). A
    ``build --vault`` build passes the vault's ``wiki/`` (#54).

    Returns the path written, or ``None`` when the wiki has no pages.
    """
    # #328: verify site_urls against the actual compiled site so dead
    # links get nulled to the graceful "no page" tooltip.
    g = graph or build_graph(verify_site_dir=site_dir, wiki_dir=wiki_dir)
    if not g.get("nodes"):
        return None
    out = site_dir / "graph.html"
    write_html(g, out)
    return out


def _rel(path: Path) -> str:
    """Repo-relative for repo output, absolute for a vault's."""
    return str(path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path)


def build_and_report(write_json_flag: bool = True, write_html_flag: bool = True,
                     wiki_dir: Path | None = None,
                     graph_dir: Path | None = None) -> int:
    """``wiki_dir``/``graph_dir`` select which wiki to graph and where the
    output lands; both default to the repo's (demo/dev mode). The CLI
    passes the resolved vault's so a configured vault is never bypassed."""
    source_dir = wiki_dir or WIKI_DIR
    out_dir = graph_dir or GRAPH_DIR
    graph = build_graph(wiki_dir=wiki_dir)
    if not graph["nodes"]:
        print(f"warning: no wiki pages found under {source_dir}", file=sys.stderr)
        return 1

    out_dir.mkdir(parents=True, exist_ok=True)

    if write_json_flag:
        json_path = out_dir / "graph.json"
        write_json(graph, json_path)
        print(f"  wrote {_rel(json_path)}")

    if write_html_flag:
        html_path = out_dir / "graph.html"
        write_html(graph, html_path)
        print(f"  wrote {_rel(html_path)}")

    stats = graph["stats"]
    print()
    print(f"  {stats['total_pages']} pages · {stats['total_edges']} edges · "
          f"{stats['broken_edges']} broken · {len(stats['orphans'])} orphans")

    if stats["top_linked"]:
        print()
        print("  Top linked-to:")
        for n in stats["top_linked"]:
            if n["in_degree"] > 0:
                print(f"    {n['in_degree']:3} ← {n['id']}")

    if stats["top_linking"]:
        print()
        print("  Top linking-from:")
        for n in stats["top_linking"]:
            if n["out_degree"] > 0:
                print(f"    {n['out_degree']:3} → {n['id']}")

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Write graph.json only")
    parser.add_argument("--html", action="store_true", help="Write graph.html only")
    args = parser.parse_args(argv)
    # Default: write both
    if not args.json and not args.html:
        return build_and_report(True, True)
    return build_and_report(args.json, args.html)


if __name__ == "__main__":
    sys.exit(main())
