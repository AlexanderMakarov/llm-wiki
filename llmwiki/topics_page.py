"""Static topic pages for the topic-first knowledge graph (#54).

For every topic node in :func:`llmwiki.topics.build_topic_graph` we emit
``site/topics/<slug>.html`` — the static equivalent of the MCP
``wiki_entity_search`` tool: the sessions that mention the topic (linked to
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

_ALIAS_NORM = re.compile(r"[\s\-_]+")
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


def _topic_links(neighbors: list[tuple[str, int]]) -> str:
    from llmwiki.topics import topic_slug

    if not neighbors:
        return '<p class="muted">No connected topics.</p>'
    rows = []
    for name, weight in neighbors:
        rows.append(
            f'<li><a href="{html.escape(topic_slug(name))}.html">{html.escape(name)}</a>'
            f' <span class="muted">· {weight} shared</span></li>'
        )
    return '<ul class="topic-neighbor-list">\n' + "\n".join(rows) + "\n</ul>"


def build_topic_pages(graph: dict[str, Any], out_dir: Path) -> list[Path]:
    """Write ``topics/<slug>.html`` for every node + a ``topics/index.html``.

    Returns the list of files written.
    """
    from llmwiki.build import page_head, nav_bar, hero, page_foot
    from llmwiki.topics import topic_slug

    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    sessions_meta = graph.get("sessions", {})
    if not nodes:
        return []

    topics_dir = out_dir / "topics"
    topics_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    for node in nodes:
        name = node["id"]
        neighbors = _neighbors(name, edges)
        subtitle = f"{node['session_count']} sessions · {len(neighbors)} connected topics"
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
        body = (
            page_head(name, f"Sessions and connections for {name}", css_prefix="../")
            + nav_bar(active="graph", link_prefix="../")
            + hero(name, subtitle)
            + '<section class="container topic-page">\n'
            + alias_note
            + "<h2>Connected topics</h2>\n" + _topic_links(neighbors)
            + "<h2>Sessions</h2>\n" + _session_links(node.get("sessions", []), sessions_meta)
            + "</section>\n</main>\n"
            + page_foot(js_prefix="../")
        )
        path = topics_dir / f"{topic_slug(name)}.html"
        path.write_text(body, encoding="utf-8")
        written.append(path)

    # Index page — every topic by reach.
    rows = []
    for node in nodes:
        rows.append(
            f'<li><a href="{html.escape(topic_slug(node["id"]))}.html">{html.escape(node["id"])}</a>'
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
