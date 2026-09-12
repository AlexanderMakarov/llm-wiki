"""Multi-query, single-pass search engine (#197).

Visits each page once and evaluates every pending query against it. Each
query owns its own result-cap accumulators so N queries together cannot
leak state into each other. A one-query call is the N=1 case.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from llmwiki.search.corpus import ScannedPage
from llmwiki.search.scoring import (
    ExtractQuery,
    MatchedPage,
    extract_snippet,
    match_page,
    score_extract,
)

DEFAULT_HIT_CAP = 200
DEFAULT_PAGE_CAP = 200
DEFAULT_MAX_PAGES = 5


@dataclass(frozen=True, slots=True)
class ExtractHit:
    """One ranked extract-mode hit."""

    rel_path: str
    path: Path
    score: float
    snippet: str


@dataclass(frozen=True, slots=True)
class MatchResult:
    """Capped match-mode result for one term."""

    pages: tuple[MatchedPage, ...]
    truncated: bool


@dataclass
class _MatchAccum:
    term: str
    term_lower: str
    name_pages: list[MatchedPage] = field(default_factory=list)
    body_pages: list[MatchedPage] = field(default_factory=list)
    hit_count: int = 0
    line_cap_reached: bool = False
    dropped_pages: bool = False

    def saturated(self, page_cap: int) -> bool:
        return self.line_cap_reached and len(self.name_pages) >= page_cap


def _as_extract_queries(
    queries: Sequence[str | ExtractQuery],
) -> list[ExtractQuery]:
    out: list[ExtractQuery] = []
    for q in queries:
        if isinstance(q, ExtractQuery):
            out.append(q)
        else:
            out.append(ExtractQuery.parse(q))
    return out


def search_extract(
    pages: Iterable[ScannedPage],
    queries: Sequence[str | ExtractQuery],
    *,
    max_pages: int = DEFAULT_MAX_PAGES,
) -> dict[str, list[ExtractHit]]:
    """Score every page against every query in one pass.

    Returns a map from query ``raw`` → hits ordered by ``(-score, rel_path)``
    then truncated to ``max_pages``. Equal scores are path-stable (the
    determinism fix for MCP's filesystem-order tiebreak).
    """
    parsed = _as_extract_queries(queries)
    if not parsed:
        return {}
    # Accumulate all positive scores, then sort — same as the MCP loop.
    buckets: dict[str, list[ExtractHit]] = {q.raw: [] for q in parsed}
    for page in pages:
        for query in parsed:
            score = score_extract(page, query)
            if score <= 0:
                continue
            snippet = extract_snippet(page.text, query.tokens)
            buckets[query.raw].append(
                ExtractHit(
                    rel_path=page.rel_path,
                    path=page.path,
                    score=score,
                    snippet=snippet,
                )
            )
    result: dict[str, list[ExtractHit]] = {}
    for query in parsed:
        hits = buckets[query.raw]
        hits.sort(key=lambda h: (-h.score, h.rel_path))
        result[query.raw] = hits[:max_pages]
    return result


def search_match(
    pages: Iterable[ScannedPage],
    terms: Sequence[str],
    *,
    kind: str = "",
    page_cap: int = DEFAULT_PAGE_CAP,
    hit_cap: int = DEFAULT_HIT_CAP,
) -> dict[str, MatchResult]:
    """Match every page against every term in one pass.

    Each term owns name/body buckets, hit count, and truncation flags.
    Early-exit when every term is saturated (line cap reached and name
    bucket full) — the multi-query generalisation of the MCP break.
    """
    kind_norm = kind.strip().lower() if kind else ""
    accums = [_MatchAccum(term=t, term_lower=t.lower()) for t in terms]
    if not accums:
        return {}

    for page in pages:
        for accum in accums:
            if accum.saturated(page_cap):
                continue
            # With the line cap reached, only a name match can still add
            # output; skip body-only work once name pages are also full.
            matched = match_page(page, accum.term_lower, kind_norm)
            if matched is None:
                continue
            lines = matched.lines
            if accum.line_cap_reached:
                if not matched.name_match:
                    continue
                lines = ()
            else:
                kept: list[tuple[int, str]] = []
                for line in lines:
                    if accum.hit_count >= hit_cap:
                        accum.line_cap_reached = True
                        break
                    kept.append(line)
                    accum.hit_count += 1
                lines = tuple(kept)
                if not lines and not matched.name_match:
                    continue
                matched = MatchedPage(
                    rel_path=matched.rel_path,
                    title=matched.title,
                    name_match=matched.name_match,
                    lines=lines,
                )
            if not (matched.lines or matched.name_match):
                continue
            bucket = accum.name_pages if matched.name_match else accum.body_pages
            if len(bucket) >= page_cap:
                accum.dropped_pages = True
                continue
            bucket.append(matched)
        # Check after the page so a saturated query does not pull the next
        # file from a streaming walk (N1 / disk early-exit).
        if all(a.saturated(page_cap) for a in accums):
            break

    result: dict[str, MatchResult] = {}
    for accum in accums:
        name_pages = sorted(accum.name_pages, key=lambda p: p.rel_path)
        body_pages = sorted(accum.body_pages, key=lambda p: p.rel_path)
        pages_out = name_pages + body_pages
        dropped = accum.dropped_pages
        if len(pages_out) > page_cap:
            pages_out = pages_out[:page_cap]
            dropped = True
        truncated = accum.line_cap_reached or dropped
        result[accum.term] = MatchResult(
            pages=tuple(pages_out), truncated=truncated
        )
    return result
