"""Static topic pages for the topic-first knowledge graph (#54).

For every topic node in :func:`llmwiki.topics.build_topic_graph` we emit
``site/topics/<slug>.html`` — the static equivalent of the MCP
``wiki_search`` tool: the sessions that mention the topic (linked to
their compiled session pages) plus the topics it co-occurs with. A
``topics/index.html`` lists every topic by reach.

Reuses the site shell helpers in :mod:`llmwiki.build` (imported lazily to
avoid a circular import — ``build`` calls this module).
"""

from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any

from llmwiki._frontmatter import parse_frontmatter
from llmwiki.topics import KIND_OTHER, topic_slug
from llmwiki.wikilinks import WIKILINK_RE, strip_anchor

_ALIAS_NORM = re.compile(r"[\s\-_]+")

# Fenced blocks suspend heading detection: a ``##`` inside one is code, not a
# section boundary.
_FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
_HEADING_RE = re.compile(r"^ {0,3}(#{1,6})\s+(.*)$")
# The two sections the topic page renders itself, from the graph.
_OMITTED_SECTIONS = frozenset({"connections", "sessions"})

# Human-readable singular name per wiki folder, for the identity-line chip.
# Keys mirror `llmwiki.topics.TOPIC_KIND_FOLDERS`.
_KIND_LABELS = {
    "entities": "Entity",
    "concepts": "Concept",
    "projects": "Project",
    "questions": "Question",
    "comparisons": "Comparison",
    "syntheses": "Synthesis",
    "sources": "Source",
}
_ALIAS_TOOLTIP = (
    "Alternate spellings or related names sessions used in [[wikilinks]] "
    "before consolidation merged them under this topic."
)


def _display_aliases(canonical: str, aliases: list[str]) -> list[str]:
    """Collapse near-duplicate spellings for the topic-page alias note.

    Sessions tag the same scope with different casing/spacing (``Armenian
    Language`` vs ``ArmenianLanguage``). The graph keeps every raw spelling
    internally; the static page shows one readable form per cluster.
    """
    best: dict[str, str] = {}
    for a in aliases:
        if not a or a == canonical:
            continue
        key = _ALIAS_NORM.sub("", a.lower())
        prev = best.get(key)
        if prev is None:
            best[key] = a
            continue
        # Prefer spaced Title Case over camelCase / hyphenated when tied.
        score = ((" " in a), -len(a))
        prev_score = ((" " in prev), -len(prev))
        if score > prev_score:
            best[key] = a
    return sorted(best.values(), key=str.lower)


def _neighbors(topic_id: str, edges: list[dict[str, Any]]) -> list[tuple[str, int]]:
    """Return ``[(other_topic, weight), ...]`` sorted by weight desc."""
    out: list[tuple[str, int]] = []
    for e in edges:
        if e["source"] == topic_id:
            out.append((e["target"], e["weight"]))
        elif e["target"] == topic_id:
            out.append((e["source"], e["weight"]))
    out.sort(key=lambda x: (-x[1], x[0].lower()))
    return out


def _session_links(slugs: list[str], sessions_meta: dict[str, dict[str, str]]) -> str:
    """Render a session list; link to the compiled page when one exists."""
    if not slugs:
        return '<p class="muted">No sessions.</p>'
    rows = []
    for s in slugs:
        meta = sessions_meta.get(s, {})
        title = meta.get("title") or s
        url = meta.get("url") or ""
        if url:
            rows.append(
                f'<li><a href="../{html.escape(url)}">{html.escape(title)}</a></li>'
            )
        else:
            rows.append(f"<li>{html.escape(title)} <span class=\"muted\">(no page)</span></li>")
    return '<ul class="topic-session-list">\n' + "\n".join(rows) + "\n</ul>"


def _kind_label(kind: str) -> str:
    """Human-readable singular name for a wiki folder, ``""`` when there is none.

    A topic no page describes carries ``KIND_OTHER`` and gets no label — the
    chip is dropped rather than filled with a placeholder (FR8).
    """
    if not kind or kind == KIND_OTHER:
        return ""
    return _KIND_LABELS.get(kind) or kind.removesuffix("s").capitalize()


def _activity_span(node: dict[str, Any]) -> str:
    """Render the session-derived activity dates, ``""`` when there are none.

    ``first_seen`` / ``last_seen`` come from the sessions that mention the
    topic, so this says when the topic was actually worked on. A topic seen in
    one session — or on one day — shows a single date rather than a range.
    """
    seen = [str(d) for d in (node.get("first_seen"), node.get("last_seen")) if d]
    if not seen:
        return ""
    text = seen[0] if seen[0] == seen[-1] else f"{seen[0]} – {seen[-1]}"
    return f'<span class="topic-activity">Active {html.escape(text)}</span>'


def _reviewed_span(node: dict[str, Any]) -> str:
    """Render the backing page's own review date, ``""`` when it records none.

    Distinct from :func:`_activity_span`: this is when a human or agent last
    curated the page, not when sessions touched the topic.
    """
    reviewed = node.get("last_updated")
    if not reviewed:
        return ""
    return (
        '<span class="topic-reviewed">Reviewed '
        f"{html.escape(str(reviewed))}</span>"
    )


def _identity_line(node: dict[str, Any], neighbor_count: int) -> str:
    """Render the topic page's identity line: kind chip, dates, counts, slug.

    The activity dates and the review date are two different facts and are
    labelled as such. Every element is omitted entirely when the node lacks
    its field — no labels without values, no placeholder text (FR1, FR2, FR8).
    """
    parts: list[str] = []
    label = _kind_label(str(node.get("kind") or ""))
    if label:
        parts.append(f'<span class="topic-kind-chip">{html.escape(label)}</span>')
    for span in (_activity_span(node), _reviewed_span(node)):
        if span:
            parts.append(span)
    parts.append(f"{neighbor_count} connected topics")
    session_count = node.get("session_count")
    if session_count is not None:
        parts.append(f"{session_count} sessions")
    slug = topic_slug(str(node.get("id", "")))
    if slug:
        parts.append(f"<code>{html.escape(slug)}</code>")
    return " · ".join(parts)


def _node_urls(nodes: list[dict[str, Any]]) -> dict[str, str]:
    """Map every topic id → the ``site_url`` its node resolved to."""
    return {str(n.get("id", "")): str(n.get("site_url") or "") for n in nodes}


def _topic_href(name: str, node_urls: dict[str, str]) -> str:
    """Link from one topic page to another topic, relative to ``topics/``.

    A node's ``site_url`` is site-root-relative and normally names the topic's
    own page, but a project topic resolves to its project page instead (#108,
    FR4). Since topic pages live in ``topics/``, a sibling topic is
    ``<slug>.html`` while anything else needs a ``../`` prefix.
    """
    url = node_urls.get(name) or ""
    if not url:
        return f"{topic_slug(name)}.html"
    if url.startswith("topics/"):
        return url.removeprefix("topics/")
    return f"../{url}"


def _topic_links(
    neighbors: list[tuple[str, int]], node_urls: dict[str, str]
) -> str:
    """Render the connected-topics list, honouring each node's resolved URL."""
    if not neighbors:
        return '<p class="muted">No connected topics.</p>'
    rows = []
    for name, weight in neighbors:
        href = html.escape(_topic_href(name, node_urls), quote=True)
        rows.append(
            f'<li><a href="{href}">{html.escape(name)}</a>'
            f' <span class="muted">· {weight} shared</span></li>'
        )
    return '<ul class="topic-neighbor-list">\n' + "\n".join(rows) + "\n</ul>"


def page_content(text: str) -> str | None:
    """Return the markdown a topic page should render from its backing page.

    Frontmatter, the page's own leading ``# H1``, and the ``## Connections`` /
    ``## Sessions`` sections are dropped — the topic page already shows the
    title and renders both of those lists itself, from the graph. Everything
    else survives exactly as written, whatever the curator called it, so a
    renamed or newly added section still reaches the reader.

    A heading left with nothing under it is dropped too, so a page recording an
    empty section shows no heading for it. Returns ``None`` when nothing but
    whitespace is left, so the caller emits no section at all rather than an
    empty one (FR3, FR8).
    """
    _meta, body = parse_frontmatter(text)
    # (line, heading level) — the level is ``None`` for anything that is not a
    # heading, including a ``##`` inside a fenced block.
    kept: list[tuple[str, int | None]] = []
    in_fence = False
    fence_char = ""
    skipping = False
    seen_content = False
    for line in body.splitlines():
        level: int | None = None
        fence = _FENCE_RE.match(line)
        if fence:
            char = fence.group(1)[0]
            if not in_fence:
                in_fence, fence_char = True, char
            elif char == fence_char:
                in_fence = False
        elif not in_fence:
            heading = _HEADING_RE.match(line)
            if heading:
                level = len(heading.group(1))
                title = heading.group(2).strip().rstrip("#").strip().lower()
                if level == 1 and not seen_content:
                    continue  # the page's own title — the hero already shows it
                # Only a heading at `##` or above closes a section; a `###`
                # subsection belongs to whichever section encloses it.
                if level <= 2:
                    skipping = title in _OMITTED_SECTIONS
        if skipping:
            continue
        kept.append((line, level))
        if line.strip():
            seen_content = True
    return "\n".join(_drop_empty_sections(kept)).strip() or None


def _drop_empty_sections(lines: list[tuple[str, int | None]]) -> list[str]:
    """Drop every heading that has no content under it, innermost first.

    Walking backwards, ``covered`` is the heading level that the content seen
    so far is available to: prose serves any heading, while a heading that
    survives serves only headings shallower than itself. A heading reached with
    nothing available to it is an empty section and goes.
    """
    out: list[str] = []
    covered: int | None = None
    for line, level in reversed(lines):
        if level is not None:
            if covered is None or covered <= level:
                continue
            covered = level
        elif line.strip():
            covered = 7  # deeper than any heading — serves whatever encloses it
        out.append(line)
    out.reverse()
    return out


def _backing_page_markdown(node: dict[str, Any], wiki_root: Path | None) -> str | None:
    """Content of the wiki page describing ``node``, or ``None``.

    ``wiki_path`` is relative to the wiki root's parent, as ``scan_pages``
    records it. A vault can change between graph construction and page
    rendering, so an unreadable or vanished file yields no content instead of
    failing the build.
    """
    rel = str(node.get("wiki_path") or "")
    if not rel or wiki_root is None:
        return None
    try:
        text = (wiki_root / rel).read_text(encoding="utf-8")
    except OSError:
        return None
    return page_content(text)


def _topic_link_index(nodes: list[dict[str, Any]]) -> dict[str, str]:
    """Map every topic name and alias (lowercased) → its canonical topic id."""
    index: dict[str, str] = {}
    for node in nodes:
        canonical = str(node.get("id", ""))
        if not canonical:
            continue
        index.setdefault(canonical.strip().lower(), canonical)
        for alias in node.get("aliases", []):
            key = str(alias).strip().lower()
            if key:
                index.setdefault(key, canonical)
    return index


def _resolve_wikilinks(
    rendered: str,
    topic_index: dict[str, str],
    sessions_meta: dict[str, dict[str, str]],
    node_urls: dict[str, str] | None = None,
) -> str:
    """Turn ``[[wikilinks]]`` in rendered page content into working links.

    A target naming a topic links to wherever that topic resolved — its own
    page, or the project page a project topic routes to (FR4) — a target naming
    a session with a compiled page links to it, and anything else degrades to
    the plain text it wrapped rather than a dead link (FR3).

    Runs on ``md_to_html`` output, where the link text has already been escaped
    by the markdown renderer — escaping it a second time would double-encode
    it. Only the ``href``, which this function constructs from graph data that
    never passed through markdown, is escaped here.
    """
    sessions_lower = {str(k).strip().lower(): v for k, v in sessions_meta.items()}

    def resolve(match: re.Match[str]) -> str:
        raw_target, _, display = match.group(0)[2:-2].partition("|")
        label = display.strip() or raw_target.strip()
        key = strip_anchor(html.unescape(raw_target)).lower()
        canonical = topic_index.get(key)
        if canonical is not None:
            href = _topic_href(canonical, node_urls or {})
        else:
            url = str(sessions_lower.get(key, {}).get("url") or "")
            href = f"../{url}" if url else ""
        if not href:
            return label
        return f'<a href="{html.escape(href, quote=True)}">{label}</a>'

    return WIKILINK_RE.sub(resolve, rendered)


def build_topic_pages(
    graph: dict[str, Any], out_dir: Path, wiki_dir: Path | None = None
) -> list[Path]:
    """Write ``topics/<slug>.html`` for every node + a ``topics/index.html``.

    ``wiki_dir`` is the vault's ``wiki/`` directory. Pass it to render each
    topic's backing page content on its topic page; omit it and the pages carry
    the identity line and the link lists only.

    Returns the list of files written.
    """
    from llmwiki.build import (  # noqa: PLC0415 — cycle: topics_page↔build
        hero,
        md_to_html,
        nav_bar,
        page_foot,
        page_head,
    )

    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    sessions_meta = graph.get("sessions", {})
    if not nodes:
        return []

    # `wiki_path` is recorded relative to the wiki root's parent.
    wiki_root = wiki_dir.parent if wiki_dir is not None else None
    topic_index = _topic_link_index(nodes)
    node_urls = _node_urls(nodes)

    topics_dir = out_dir / "topics"
    topics_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    for node in nodes:
        name = node["id"]
        neighbors = _neighbors(name, edges)
        subtitle = _identity_line(node, len(neighbors))
        aliases = _display_aliases(name, node.get("aliases", []))
        alias_note = ""
        if aliases:
            tip = html.escape(_ALIAS_TOOLTIP, quote=True)
            alias_note = (
                '<p class="muted topic-aliases">'
                f'<span class="topic-aliases-label" title="{tip}">'
                "<strong>Also tagged as</strong></span>: "
                + ", ".join(html.escape(a) for a in aliases)
                + "</p>"
            )
        # The curated content is the payload; the link lists are context, so it
        # sits above them. Nothing at all is emitted when the page records none.
        content_block = ""
        page_md = _backing_page_markdown(node, wiki_root)
        if page_md:
            content_block = (
                '<div class="topic-page-content">\n'
                + _resolve_wikilinks(
                    md_to_html(page_md), topic_index, sessions_meta, node_urls
                )
                + "\n</div>\n"
            )
        body = (
            page_head(name, f"Sessions and connections for {name}", css_prefix="../")
            + nav_bar(active="graph", link_prefix="../")
            + hero(name, subtitle, subtitle_is_html=True)
            + '<section class="container topic-page">\n'
            + alias_note
            + content_block
            + "<h2>Connected topics</h2>\n" + _topic_links(neighbors, node_urls)
            + "<h2>Sessions</h2>\n" + _session_links(node.get("sessions", []), sessions_meta)
            + "</section>\n</main>\n"
            + page_foot(js_prefix="../")
        )
        path = topics_dir / f"{topic_slug(name)}.html"
        path.write_text(body, encoding="utf-8")
        written.append(path)

    # Index page — every topic by reach. `topics/index.html` sits in the same
    # directory as the topic pages, so it uses the same href rules and routes a
    # project topic to its project page like every other link does (FR4).
    rows = []
    for node in nodes:
        href = html.escape(_topic_href(str(node["id"]), node_urls), quote=True)
        rows.append(
            f'<li><a href="{href}">{html.escape(node["id"])}</a>'
            f' <span class="muted">· {node["session_count"]} sessions · {node["degree"]} links</span></li>'
        )
    index_body = (
        page_head("Topics", "Every topic in the wiki by reach", css_prefix="../")
        + nav_bar(active="graph", link_prefix="../")
        + hero("Topics", f"{len(nodes)} topics across {graph.get('stats', {}).get('total_sessions', 0)} sessions")
        + '<section class="container topic-index">\n<ul class="topic-index-list">\n'
        + "\n".join(rows)
        + "\n</ul>\n</section>\n</main>\n"
        + page_foot(js_prefix="../")
    )
    index_path = topics_dir / "index.html"
    index_path.write_text(index_body, encoding="utf-8")
    written.append(index_path)
    return written
