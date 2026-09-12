"""Root-agnostic wiki search package (#197).

No import-time state. Consumers pass explicit roots / pages; MCP, CLI, and
lint all share :func:`scan_corpus`, :mod:`scoring`, and the multi-query engine.
"""

from __future__ import annotations

from llmwiki.search.context import SearchContext
from llmwiki.search.corpus import (
    DEFAULT_AGGREGATE_BUDGET,
    DEFAULT_PER_FILE_CAP,
    CorpusScan,
    CorpusWalkStats,
    ScannedPage,
    iter_scan_files,
    iter_scanned_pages,
    read_capped,
    scan_corpus,
)
from llmwiki.search.engine import (
    DEFAULT_HIT_CAP,
    DEFAULT_MAX_PAGES,
    DEFAULT_PAGE_CAP,
    ExtractHit,
    MatchResult,
    search_extract,
    search_match,
)
from llmwiki.search.evaluate import (
    DEFAULT_CONSISTENCY_TERM_COUNT,
    PAGE_CAP_FOR_FINDABILITY,
    alias_map_from_scanned_pages,
    collect_wikilink_lookups,
    find_outranker,
    rank_of,
    sample_evenly,
    select_absent_terms,
    select_present_terms,
    survival_share,
    titled_wiki_pages,
    unique_title_queries,
    wikilink_lookup_queries,
)
from llmwiki.search.scoring import (
    ExtractQuery,
    MatchedPage,
    extract_snippet,
    match_page,
    score_extract,
)

__all__ = [
    "DEFAULT_AGGREGATE_BUDGET",
    "DEFAULT_CONSISTENCY_TERM_COUNT",
    "DEFAULT_HIT_CAP",
    "DEFAULT_MAX_PAGES",
    "DEFAULT_PAGE_CAP",
    "DEFAULT_PER_FILE_CAP",
    "PAGE_CAP_FOR_FINDABILITY",
    "CorpusScan",
    "CorpusWalkStats",
    "ExtractHit",
    "ExtractQuery",
    "MatchResult",
    "MatchedPage",
    "ScannedPage",
    "SearchContext",
    "alias_map_from_scanned_pages",
    "collect_wikilink_lookups",
    "extract_snippet",
    "find_outranker",
    "iter_scan_files",
    "iter_scanned_pages",
    "match_page",
    "rank_of",
    "read_capped",
    "sample_evenly",
    "scan_corpus",
    "score_extract",
    "search_extract",
    "search_match",
    "select_absent_terms",
    "select_present_terms",
    "survival_share",
    "titled_wiki_pages",
    "unique_title_queries",
    "wikilink_lookup_queries",
]
