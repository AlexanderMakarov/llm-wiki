"""Topic vocabulary + topic-first knowledge graph (#54).

The wiki's value is the *topics* its sessions share — personal scopes like
projects, products, and major systems. This module turns the ``[[wikilinks]]``
the synth step embeds in ``wiki/sources/**`` into:

* an **auto-derived controlled vocabulary** — distinct topics with their
  spelling variants clustered together (case-fold + string similarity), ranked
  by how many sessions mention them. No persisted file, no LLM, recomputed each
  build so the wiki stays autonomous. The synth prompt feeds this list back to
  the model so future sessions reuse canonical names instead of coining new
  spellings.
* a **topic-only co-occurrence graph** — topics are nodes, an edge joins two
  topics that appear together in a session (the connection runs *through* the
  session), and each edge remembers the bridging sessions for drill-down.

Stdlib only. Reuses :func:`llmwiki.graph.scan_pages` (which already yields each
session's wikilink set + compiled ``site_url`` + title).
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Collection
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from llmwiki.graph import scan_pages
from llmwiki.topics_consolidate import load_cache
from llmwiki.wikilinks import strip_anchor

# Mirrors tags.near_duplicate_tags' SequenceMatcher comparison; 0.90 merges
# pure-case, plural, and hyphen/space variants (llm-wiki≈llmwiki 0.93,
# wikilinks≈wikilink 0.94) while leaving genuinely distinct names apart
# (Markdown vs Markitdown 0.89, kbbuilder vs code-kbbuilder 0.78).
_DEFAULT_SIMILARITY = 0.90

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def topic_slug(name: str) -> str:
    """Filesystem-safe slug for a topic page (``topics/<slug>.html``)."""
    s = _SLUG_RE.sub("-", name.strip().lower()).strip("-")
    return s or "topic"


@dataclass
class Topic:
    """A canonical topic and the sessions that mention it."""

    canonical: str
    aliases: set[str] = field(default_factory=set)
    sessions: set[str] = field(default_factory=set)
    description: str = ""

    @property
    def slug(self) -> str:
        return topic_slug(self.canonical)

    @property
    def count(self) -> int:
        return len(self.sessions)


def _session_pages(wiki_dir: Path | None) -> dict[str, dict[str, Any]]:
    """Return ``{slug: page}`` for session/source pages only."""
    return {
        slug: p
        for slug, p in scan_pages(wiki_dir).items()
        if p.get("type") == "sources"
    }


def _cluster_aliases(
    raw_counts: dict[str, int], *, similarity: float
) -> dict[str, str]:
    """Map every raw topic spelling → its canonical form.

    Union-find over two passes: (1) case-insensitive equality, (2) string
    similarity ≥ ``similarity``. Canonical per cluster = the spelling seen in
    the most sessions (ties → shortest, then lexicographic).
    """
    names = list(raw_counts)
    parent = {n: n for n in names}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    # Pass 1 — case-fold groups.
    by_lower: dict[str, list[str]] = defaultdict(list)
    for n in names:
        by_lower[n.strip().lower()].append(n)
    for grp in by_lower.values():
        for other in grp[1:]:
            union(grp[0], other)

    # Pass 2 — near-duplicate spellings (compare normalized forms once each).
    reps = sorted(by_lower)  # lowercased representatives
    rep_raw = {low: by_lower[low][0] for low in reps}
    for i, a in enumerate(reps):
        for b in reps[i + 1:]:
            if SequenceMatcher(None, a, b).ratio() >= similarity:
                union(rep_raw[a], rep_raw[b])

    # Choose canonical per cluster.
    clusters: dict[str, list[str]] = defaultdict(list)
    for n in names:
        clusters[find(n)].append(n)
    raw_to_canonical: dict[str, str] = {}
    for members in clusters.values():
        canonical = max(members, key=lambda n: (raw_counts[n], -len(n), n))
        for m in members:
            raw_to_canonical[m] = canonical
    return raw_to_canonical


def derive_vocabulary(
    wiki_dir: Path | None = None, *, similarity: float = _DEFAULT_SIMILARITY
) -> tuple[list[Topic], dict[str, str]]:
    """Auto-derive the topic vocabulary from session wikilinks.

    Returns ``(topics_sorted_by_count_desc, raw_spelling -> canonical)``.
    Pure CPU — no file, no LLM. This is the "known-topic list" fed back into
    the synth prompt and used to normalize the graph.
    """
    sessions = _session_pages(wiki_dir)
    # raw topic → set of session slugs (presence, not occurrence count).
    raw_sessions: dict[str, set[str]] = defaultdict(set)
    for slug, page in sessions.items():
        for raw in page.get("out_links", ()):  # already a set of link targets
            t = strip_anchor(str(raw))
            if t:
                raw_sessions[t].add(slug)

    # #54: an LLM consolidation pass (llmwiki consolidate-topics) may have
    # written an authoritative merge-map + descriptions. When present it wins
    # over the string-similarity heuristic: cache-known spellings map to their
    # curated canonical, dropped spellings are excluded, and unknown spellings
    # still fall back to the heuristic so new topics work before re-consolidating.
    cache = _load_consolidation_cache(wiki_dir)
    alias_map = cache.get("alias_map", {}) if cache else {}
    descriptions = cache.get("descriptions", {}) if cache else {}
    dropped = {str(d).lower() for d in (cache.get("dropped", []) if cache else [])}

    heuristic_raw = {t: len(s) for t, s in raw_sessions.items()
                     if t.lower() not in alias_map and t.lower() not in dropped}
    raw_to_canonical = _cluster_aliases(heuristic_raw, similarity=similarity)
    for raw in raw_sessions:
        low = raw.lower()
        if low in alias_map:
            raw_to_canonical[raw] = alias_map[low]
        elif low in dropped:
            continue  # consolidator removed this as noise

    topics: dict[str, Topic] = {}
    for raw, sess in raw_sessions.items():
        canonical = raw_to_canonical.get(raw)
        if canonical is None:
            continue  # dropped
        topic = topics.setdefault(
            canonical, Topic(canonical=canonical, description=descriptions.get(canonical, "")))
        topic.aliases.add(raw)
        topic.sessions |= sess

    ordered = sorted(topics.values(), key=lambda t: (-t.count, t.canonical.lower()))
    return ordered, raw_to_canonical


def _load_consolidation_cache(wiki_dir: Path | None):
    """Load the consolidation cache, swallowing any import/IO error."""
    try:

        return load_cache(wiki_dir)
    except Exception:
        return None


# `wiki/` subfolders whose name is a meaningful node kind. Topics resolve to
# one of these; everything else groups under KIND_OTHER. The names match the
# viewer's per-type colour map so a clustered graph keeps its palette.
TOPIC_KIND_FOLDERS = frozenset({
    "entities", "concepts", "projects", "syntheses", "sources",
})
KIND_OTHER = "other"


@dataclass(frozen=True, slots=True)
class TopicPage:
    """The wiki page backing a topic, as matched by :func:`topic_kind_lookup`."""

    kind: str
    slug: str
    path: str
    last_updated: str | None = None
    site_url: str | None = None


def topic_kind_lookup(wiki_dir: Path | None = None) -> dict[str, TopicPage]:
    """Map every wiki page's slug and title (lowercased) → its :class:`TopicPage`.

    Topics are wikilink targets, so a topic spelled ``Hazel`` is whatever
    ``wiki/entities/Hazel.md`` says it is. The folder a page lives in is
    the only kind signal the wiki schema carries, so that is what we key on.
    """
    lookup: dict[str, TopicPage] = {}
    for slug, page in scan_pages(wiki_dir).items():
        # `kind` is the wiki FOLDER the page lives in — `scan_pages` derives
        # `type` from the directory, never from frontmatter. Keep it that way:
        # project pages created before #102 still carry `type: entity` plus
        # `entity_type: project` in their frontmatter (see docs/UPGRADING.md),
        # so a frontmatter-derived kind would mis-file every one of them.
        kind = str(page.get("type", ""))
        if kind not in TOPIC_KIND_FOLDERS:
            continue
        record = TopicPage(
            kind=kind,
            slug=slug,
            path=str(page.get("path", "")),
            last_updated=page.get("last_updated") or None,
            site_url=page.get("site_url") or None,
        )
        lookup.setdefault(slug.strip().lower(), record)
        title = str(page.get("title", "")).strip().lower()
        if title:
            lookup.setdefault(title, record)
    return lookup


def resolve_topic_page(topic: Topic, lookup: dict[str, TopicPage]) -> TopicPage | None:
    """Backing page for one topic — canonical spelling wins, then any alias.

    Aliases matter: the canonical spelling is whichever variant appeared in
    the most sessions, which is not necessarily the one that matches a page
    filename. Returns ``None`` when no page describes the topic — the normal
    resting state of an un-promoted candidate, not an error.
    """
    for name in (topic.canonical, *sorted(topic.aliases)):
        record = lookup.get(str(name).strip().lower())
        if record is not None:
            return record
    return None


def resolve_project_topic_urls(
    graph: dict[str, Any], built_project_slugs: Collection[str]
) -> int:
    """Point every project topic at its project page. Returns the count rewritten.

    A topic is ``kind == "projects"`` because its canonical spelling or one of
    its aliases matched a page under ``wiki/projects/``, so the match already
    names which project it is — ``wiki_site_url`` carries that page's compiled
    URL. Adopting it as the node's ``site_url`` sends the map, the topic pages
    and the search index to the rich project page instead of the thin topic one.

    ``built_project_slugs`` is the set of projects the build actually wrote a
    page for. The membership test is the substance: ``wiki/projects/`` is
    written by ``ensure_project_stubs()`` while ``site/projects/`` comes from
    session groups, so a hand-authored project page with no recorded sessions
    exists in the wiki and not on the site. Those nodes keep
    ``topics/<slug>.html`` rather than being offered a link that 404s.
    """
    rewritten = 0
    for node in graph.get("nodes") or ():
        if node.get("kind") != "projects":
            continue
        slug = node.get("wiki_slug")
        url = node.get("wiki_site_url")
        # A project page can compile to no URL at all; skip rather than raise.
        if not slug or not url or slug not in built_project_slugs:
            continue
        node["site_url"] = url
        rewritten += 1
    return rewritten


def build_topic_graph(
    wiki_dir: Path | None = None,
    *,
    min_sessions: int = 2,
    max_neighbors: int = 12,
    similarity: float = _DEFAULT_SIMILARITY,
) -> dict[str, Any]:
    """Build the topic-only co-occurrence graph.

    ``min_sessions``: drop topics mentioned in fewer than this many sessions
    (default 2 — strips one-off noise; after a scope-level re-synth almost
    everything clears this anyway). ``max_neighbors``: keep only each topic's
    strongest co-occurrence edges so dense graphs stay readable.

    Returns ``{nodes, edges, sessions, stats}`` ready for the viewer + the
    topic-page generator. ``sessions`` maps session slug → {title, url, date}
    for drill-down rendering; each node's ``first_seen`` / ``last_seen`` are
    the earliest and latest of those dates, and are omitted when no session
    mentioning the topic carries one.
    """
    topics, raw_to_canonical = derive_vocabulary(wiki_dir, similarity=similarity)
    kept = [t for t in topics if t.count >= min_sessions]
    kept_names = {t.canonical for t in kept}

    pages = _session_pages(wiki_dir)
    sessions_meta: dict[str, dict[str, str]] = {}
    # session slug → set of canonical topics it mentions (kept ones only).
    session_topics: dict[str, set[str]] = {}
    for slug, page in pages.items():
        canon = {
            raw_to_canonical.get(strip_anchor(str(t)), "")
            for t in page.get("out_links", ())
        }
        canon = {c for c in canon if c in kept_names}
        if canon:
            session_topics[slug] = canon
        sessions_meta[slug] = {
            "title": page.get("title", slug),
            "url": page.get("site_url") or "",
            # The session's own date. Deliberately NOT `last_updated`, which on
            # a source page records when synth ran, not when the work happened.
            "date": page.get("date") or "",
        }

    # Co-occurrence: every unordered topic pair sharing a session.
    pair_sessions: dict[tuple[str, str], list[str]] = defaultdict(list)
    for slug, canon in session_topics.items():
        ordered = sorted(canon)
        for i, a in enumerate(ordered):
            for b in ordered[i + 1:]:
                pair_sessions[(a, b)].append(slug)

    # Prune to each node's strongest ``max_neighbors`` edges.
    by_node: dict[str, list[tuple[int, str, str]]] = defaultdict(list)
    for (a, b), sess in pair_sessions.items():
        w = len(sess)
        by_node[a].append((w, b, a))
        by_node[b].append((w, a, b))
    keep_pairs: set[tuple[str, str]] = set()
    for node, lst in by_node.items():
        lst.sort(reverse=True)
        for _w, other, _ in lst[:max_neighbors]:
            keep_pairs.add(tuple(sorted((node, other))))

    edges = []
    for (a, b) in sorted(keep_pairs):
        sess = pair_sessions[(a, b)]
        edges.append({
            "source": a,
            "target": b,
            "weight": len(sess),
            "sessions": sorted(sess, reverse=True),
        })

    degree: dict[str, int] = defaultdict(int)
    for e in edges:
        degree[e["source"]] += 1
        degree[e["target"]] += 1

    kind_lookup = topic_kind_lookup(wiki_dir)
    nodes = []
    for t in kept:
        page = resolve_topic_page(t, kind_lookup)
        node: dict[str, Any] = {
            "id": t.canonical,
            "label": t.canonical,
            "type": "topic",
            # Which wiki folder this topic's page lives in. Every node is a
            # `topic`, so `type` alone can't group the graph — `kind` is what
            # the viewer's Cluster control partitions on.
            "kind": page.kind if page else KIND_OTHER,
            "site_url": f"topics/{t.slug}.html",
            "session_count": t.count,
            "degree": degree.get(t.canonical, 0),
            "aliases": sorted(t.aliases),
            "description": t.description,
            "sessions": sorted(t.sessions, reverse=True),
        }
        if page is not None:
            # Which page describes the topic. `wiki_site_url` is that page's
            # own compiled URL and stays distinct from the node's `site_url`,
            # which always points at the generated topic page.
            node["wiki_slug"] = page.slug
            node["wiki_path"] = page.path
            if page.site_url:
                node["wiki_site_url"] = page.site_url
            if page.last_updated:
                # When the page was curated — a different fact from the
                # activity dates below, which come from the sessions.
                node["last_updated"] = page.last_updated
        seen = sorted(
            d for d in (sessions_meta.get(s, {}).get("date") for s in t.sessions) if d
        )
        if seen:
            node["first_seen"] = seen[0]
            node["last_seen"] = seen[-1]
        nodes.append(node)

    nodes.sort(key=lambda n: (-n["session_count"], n["id"].lower()))
    kind_counts: dict[str, int] = defaultdict(int)
    for n in nodes:
        kind_counts[n["kind"]] += 1
    stats = {
        "total_topics": len(nodes),
        "total_edges": len(edges),
        "total_sessions": len(pages),
        "kinds": dict(sorted(kind_counts.items())),
        "top_topics": [
            {"id": n["id"], "count": n["session_count"], "degree": n["degree"]}
            for n in nodes[:8]
        ],
    }
    return {
        "mode": "topic",
        "nodes": nodes,
        "edges": edges,
        "sessions": sessions_meta,
        "stats": stats,
    }
