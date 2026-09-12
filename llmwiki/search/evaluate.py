"""Answer-key reducers over shared scoring (#197).

``rank_of`` counts how many pages outrank a named target without retaining
result lists — O(1) memory per query, same ``score_extract`` the engine uses.

Sampling and term selection for lint findability rules also live here so
the rules share one deterministic path with no RNG. Wikilink lookups reuse
``build_page_alias_map`` / ``resolve_wikilink_target`` so the answer key
matches the knowledge-graph resolver.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from pathlib import PurePosixPath

from llmwiki._frontmatter import parse_frontmatter
from llmwiki.search.corpus import ScannedPage
from llmwiki.search.engine import DEFAULT_PAGE_CAP
from llmwiki.search.scoring import ExtractQuery, score_extract
from llmwiki.wikilinks import (
    WIKILINK_RE,
    build_page_alias_map,
    resolve_wikilink_target,
    strip_anchor,
)

#: Present-term token shape for ``search_consistency`` (§2.4).
_PRESENT_TERM_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]{5,}")

#: Default sample size for present terms (measured at 40/40 agreement).
DEFAULT_CONSISTENCY_TERM_COUNT = 40

#: Synthetic absent-term prefix; counter advances on corpus collision.
_ABSENT_TERM_PREFIX = "zzabsentterm"


def _page_slug(rel_path: str) -> str:
    """Stem of a corpus ``rel_path`` (``wiki/entities/Foo.md`` → ``Foo``)."""
    return PurePosixPath(rel_path.replace("\\", "/")).stem


def _as_queries(queries: Sequence[str | ExtractQuery]) -> list[ExtractQuery]:
    out: list[ExtractQuery] = []
    for q in queries:
        if isinstance(q, ExtractQuery):
            out.append(q)
        else:
            out.append(ExtractQuery.parse(q))
    return out


def sample_evenly[T](items: Sequence[T], max_n: int) -> list[T]:
    """Return up to ``max_n`` items spaced evenly over ``items`` (already sorted).

    No RNG: indices are ``round(i * (len-1) / (max_n-1))`` for ``i`` in
    ``0..max_n-1``. When ``len(items) <= max_n``, returns a copy of all items.
    """
    if max_n <= 0 or not items:
        return []
    if len(items) <= max_n:
        return list(items)
    if max_n == 1:
        return [items[0]]
    last = len(items) - 1
    indices = [round(i * last / (max_n - 1)) for i in range(max_n)]
    # Deduplicate while preserving order (rounding can collide on small n).
    seen: set[int] = set()
    out: list[T] = []
    for idx in indices:
        if idx not in seen:
            seen.add(idx)
            out.append(items[idx])
    return out


def titled_wiki_pages(pages: Sequence[ScannedPage]) -> list[ScannedPage]:
    """Wiki (non-raw) pages with a non-empty title, sorted by ``rel_path``."""
    titled = [p for p in pages if not p.is_raw and p.title.strip()]
    return sorted(titled, key=lambda p: p.rel_path)


def unique_title_queries(
    pages: Sequence[ScannedPage],
) -> tuple[list[ExtractQuery], dict[str, str]]:
    """Build extract queries for each page title with collision-safe ``raw`` keys.

    Scoring uses ``lower`` / ``tokens`` from the real title; ``raw`` embeds
    ``rel_path`` so two pages that share a title still get distinct ranks.
    """
    queries: list[ExtractQuery] = []
    targets: dict[str, str] = {}
    for page in pages:
        base = ExtractQuery.parse(page.title)
        raw = f"{page.rel_path}\0{page.title}"
        queries.append(
            ExtractQuery(raw=raw, lower=base.lower, tokens=list(base.tokens))
        )
        targets[raw] = page.rel_path
    return queries, targets


def rank_of(
    pages: Iterable[ScannedPage],
    queries: Sequence[str | ExtractQuery],
    targets: Mapping[str, str],
) -> dict[str, int | None]:
    """Return 1-based extract ranks for each query's target ``rel_path``.

    ``targets`` maps query ``raw`` → target relative path. A target that
    never scores above zero (or is absent) yields ``None``. Ordering matches
    the engine: higher score first, then ``rel_path`` ascending on ties.

    Two passes over ``pages`` keep per-query state to a few integers (target
    score + earlier-count) instead of capped hit lists.
    """
    parsed = _as_queries(queries)
    page_list = pages if isinstance(pages, list) else list(pages)

    target_score: dict[str, float | None] = {q.raw: None for q in parsed}
    seen_target: dict[str, bool] = {q.raw: False for q in parsed}
    for page in page_list:
        for query in parsed:
            target_path = targets.get(query.raw)
            if target_path is None or page.rel_path != target_path:
                continue
            seen_target[query.raw] = True
            target_score[query.raw] = score_extract(page, query)

    earlier: dict[str, int] = {q.raw: 0 for q in parsed}
    for page in page_list:
        for query in parsed:
            target_path = targets.get(query.raw)
            ts = target_score.get(query.raw)
            if (
                target_path is None
                or ts is None
                or not seen_target[query.raw]
                or ts <= 0
                or page.rel_path == target_path
            ):
                continue
            score = score_extract(page, query)
            if score <= 0:
                continue
            if score > ts or (score == ts and page.rel_path < target_path):
                earlier[query.raw] += 1

    result: dict[str, int | None] = {}
    for query in parsed:
        ts = target_score[query.raw]
        if not seen_target[query.raw] or ts is None or ts <= 0:
            result[query.raw] = None
        else:
            result[query.raw] = earlier[query.raw] + 1
    return result


def find_outranker(
    pages: Sequence[ScannedPage],
    query: ExtractQuery,
    target: ScannedPage,
) -> tuple[ScannedPage | None, bool]:
    """Return ``(outranker_or_tie_peer, is_tie)`` for title-ambiguity messages.

    When the top competitor has a strictly higher score, ``is_tie`` is False.
    When the best competitor ties the target's score (and sorts earlier by
    path), ``is_tie`` is True and the peer is that earlier page.
    """
    target_score = score_extract(target, query)
    if target_score <= 0:
        return None, False

    best: ScannedPage | None = None
    best_score = float("-inf")
    for page in pages:
        if page.rel_path == target.rel_path:
            continue
        score = score_extract(page, query)
        if score <= 0:
            continue
        if best is None or score > best_score or (
            score == best_score and page.rel_path < best.rel_path
        ):
            best = page
            best_score = score

    if best is None:
        return None, False
    if best_score > target_score:
        return best, False
    if best_score == target_score and best.rel_path < target.rel_path:
        return best, True
    return None, False


def select_present_terms(
    pages: Sequence[ScannedPage],
    *,
    count: int = DEFAULT_CONSISTENCY_TERM_COUNT,
) -> list[str]:
    """Deterministic present terms from scanned raw pages only.

    Uses the first and last raw page by sorted ``rel_path`` (same intent as
    first/last session files, but only over the searchable corpus — oversized
    or budget-skipped files never contribute). Tokenises capped ``page.text``
    with ``_PRESENT_TERM_RE``, deduplicates, sorts, then samples evenly to
    ``count``. Empty when the scan has no raw pages.
    """
    raw_pages = sorted(
        (p for p in pages if p.is_raw),
        key=lambda p: p.rel_path.replace("\\", "/"),
    )
    if not raw_pages:
        return []
    chosen = [raw_pages[0]]
    if len(raw_pages) > 1:
        chosen.append(raw_pages[-1])
    found: set[str] = set()
    for page in chosen:
        found.update(_PRESENT_TERM_RE.findall(page.text))
    ordered = sorted(found)
    return sample_evenly(ordered, count)


def alias_map_from_scanned_pages(
    pages: Sequence[ScannedPage],
) -> tuple[dict[str, str], dict[str, str], set[str]]:
    """Build graph-compatible alias map + slug→rel_path from wiki scan pages.

    Returns ``(alias_map, slug_to_rel, slugs)``. Bodies are frontmatter-stripped
    so ``## Aliases`` matches :func:`llmwiki.graph.build_graph`. Later sorted
    paths win on stem collision (same as ``scan_pages``).
    """
    wiki = sorted(
        (p for p in pages if not p.is_raw),
        key=lambda p: p.rel_path.replace("\\", "/"),
    )
    slug_to_rel: dict[str, str] = {}
    bodies: dict[str, str] = {}
    for page in wiki:
        slug = _page_slug(page.rel_path)
        if slug in ("README",):
            continue
        slug_to_rel[slug] = page.rel_path.replace("\\", "/")
        _meta, body = parse_frontmatter(page.text)
        del _meta
        bodies[slug] = body
    slugs = set(slug_to_rel)
    return build_page_alias_map(bodies), slug_to_rel, slugs


def collect_wikilink_lookups(
    pages: Sequence[ScannedPage],
) -> list[tuple[str, str]]:
    """Return sorted ``(anchor_text, resolved_rel_path)`` lookups from wiki pages.

    Each distinct resolved ``[[wikilink]]`` anchor (display-pipe ignored; anchor
    strip applied) maps to the page the graph resolver would credit. Unresolved
    links and cold-storage pages (already absent from the scan) are omitted.
    First declaration wins when the same anchor resolves more than once.
    """
    alias_map, slug_to_rel, slugs = alias_map_from_scanned_pages(pages)
    lookups: dict[str, str] = {}
    wiki = sorted(
        (p for p in pages if not p.is_raw),
        key=lambda p: p.rel_path.replace("\\", "/"),
    )
    for page in wiki:
        for raw in WIKILINK_RE.findall(page.text):
            anchor = strip_anchor(raw)
            if not anchor:
                continue
            resolved = resolve_wikilink_target(anchor, slugs, alias_map)
            if resolved is None:
                continue
            target_rel = slug_to_rel.get(resolved)
            if target_rel is None:
                continue
            if anchor not in lookups:
                lookups[anchor] = target_rel
    return sorted(lookups.items(), key=lambda pair: (pair[0], pair[1]))


def wikilink_lookup_queries(
    lookups: Sequence[tuple[str, str]],
) -> tuple[list[ExtractQuery], dict[str, str]]:
    """Build extract queries for wikilink anchors with collision-safe ``raw`` keys.

    Scoring uses the anchor as written; ``raw`` embeds the expected
    ``rel_path`` so identical anchors that somehow differ still rank apart.
    """
    queries: list[ExtractQuery] = []
    targets: dict[str, str] = {}
    for anchor, rel_path in lookups:
        base = ExtractQuery.parse(anchor)
        raw = f"{rel_path}\0{anchor}"
        queries.append(
            ExtractQuery(raw=raw, lower=base.lower, tokens=list(base.tokens))
        )
        targets[raw] = rel_path
    return queries, targets


def select_absent_terms(
    pages: Sequence[ScannedPage],
    *,
    count: int = 5,
) -> list[str]:
    """Generate synthetic terms confirmed absent from ``pages`` text.

    Pattern ``zzabsenttermNNNN``, advancing the counter on collision.
    """
    blob = "\n".join(p.text_lower for p in pages)
    out: list[str] = []
    n = 0
    while len(out) < count:
        candidate = f"{_ABSENT_TERM_PREFIX}{n:04d}"
        n += 1
        if candidate.lower() in blob:
            continue
        out.append(candidate)
    return out


def survival_share(
    present_terms: Sequence[str],
    wiki_pages: Sequence[ScannedPage],
) -> float | None:
    """Fraction of ``present_terms`` that also occur in non-raw wiki text.

    Returns ``None`` when there are no present terms (nothing to report).
    """
    if not present_terms:
        return None
    wiki_blob = "\n".join(p.text_lower for p in wiki_pages if not p.is_raw)
    survived = sum(1 for t in present_terms if t.lower() in wiki_blob)
    return survived / len(present_terms)


#: Re-export so lint rules can cite the same cap search uses for "cut short".
PAGE_CAP_FOR_FINDABILITY = DEFAULT_PAGE_CAP
