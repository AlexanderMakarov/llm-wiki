"""title_ambiguity — warn when a page is not rank-1 for its own title (#197)."""

from __future__ import annotations

from typing import Any

from llmwiki.lint import LintRule, register
from llmwiki.lint.rules._search_options import search_options_skip_reason
from llmwiki.search.evaluate import (
    find_outranker,
    rank_of,
    sample_evenly,
    titled_wiki_pages,
    unique_title_queries,
)
from llmwiki.search.scoring import ExtractQuery


@register
class TitleAmbiguity(LintRule):
    """Warning when a titled page is not the first result for its own title."""

    name = "title_ambiguity"
    severity = "warning"
    description = (
        "A titled page is not ranked first for its own title "
        "(names the outranker, or a tie)"
    )

    def skip_reason(self) -> str | None:
        return search_options_skip_reason(self.options)

    def run(
        self,
        pages: dict[str, dict[str, Any]],
        **_kwargs: Any,
    ) -> list[dict[str, Any]]:
        del pages
        ctx = self.options.search_context
        assert ctx is not None
        scan = ctx.corpus()
        # Match MCP extract / phrase search: wiki corpus only.
        wiki_pages = [p for p in scan.pages if not p.is_raw]
        titled = titled_wiki_pages(wiki_pages)
        sample_max = self.options.findability_sample_max
        sampled = sample_evenly(titled, sample_max)
        issues: list[dict[str, Any]] = [
            {
                "rule": self.name,
                "severity": "info",
                "page": "",
                "message": (
                    f"checked {len(sampled)} of {len(titled)} titled wiki pages"
                ),
            }
        ]
        if not sampled:
            return issues

        queries, targets = unique_title_queries(sampled)
        ranks = rank_of(wiki_pages, queries, targets)

        for page, query in zip(sampled, queries, strict=True):
            rank = ranks.get(query.raw)
            if rank is None or rank == 1:
                continue
            # Re-parse without the collision-safe raw so messaging uses the title.
            title_query = ExtractQuery.parse(page.title)
            peer, is_tie = find_outranker(wiki_pages, title_query, page)
            if peer is None:
                issues.append({
                    "rule": self.name,
                    "severity": self.severity,
                    "page": page.rel_path,
                    "message": (
                        f"not ranked first for its own title {page.title!r} "
                        f"(rank {rank})"
                    ),
                })
                continue
            peer_label = peer.title or peer.rel_path
            if is_tie:
                issues.append({
                    "rule": self.name,
                    "severity": self.severity,
                    "page": page.rel_path,
                    "message": (
                        f"tied with {peer.rel_path} ({peer_label!r}) "
                        f"for title {page.title!r}"
                    ),
                })
            else:
                issues.append({
                    "rule": self.name,
                    "severity": self.severity,
                    "page": page.rel_path,
                    "message": (
                        f"outranked by {peer.rel_path} ({peer_label!r}) "
                        f"for title {page.title!r}"
                    ),
                })
        return issues
