"""page_findability — titled pages and resolved wikilinks must be findable (#197)."""

from __future__ import annotations

from typing import Any

from llmwiki.lint import LintRule, register
from llmwiki.lint.rules._search_options import search_options_skip_reason
from llmwiki.search.engine import search_match
from llmwiki.search.evaluate import (
    PAGE_CAP_FOR_FINDABILITY,
    collect_wikilink_lookups,
    rank_of,
    sample_evenly,
    titled_wiki_pages,
    unique_title_queries,
    wikilink_lookup_queries,
)
from llmwiki.search.scoring import ExtractQuery


def _is_phrase_anchor(anchor: str) -> bool:
    """Multi-word / multi-token anchors use extract; bare names use match."""
    stripped = anchor.strip()
    if " " in stripped:
        return True
    return len(ExtractQuery.parse(stripped).tokens) > 1


@register
class PageFindability(LintRule):
    """Error when a titled page or resolved wikilink target is not returned."""

    name = "page_findability"
    severity = "error"
    description = (
        "A titled page is not returned for its own title, or a resolved "
        "[[wikilink]] anchor does not return its target page"
    )

    def skip_reason(self) -> str | None:
        return search_options_skip_reason(self.options)

    def run(
        self,
        pages: dict[str, dict[str, Any]],
        **_kwargs: Any,
    ) -> list[dict[str, Any]]:
        del pages  # score over scan_corpus, not lint's load_pages dict
        ctx = self.options.search_context
        assert ctx is not None  # skip_reason would have fired
        scan = ctx.corpus()
        # Title lookups match MCP extract (wiki only) — do not let raw/
        # sessions outrank wiki pages for a page's own title.
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

        if sampled:
            queries, targets = unique_title_queries(sampled)
            ranks = rank_of(wiki_pages, queries, targets)
            by_raw = {q.raw: page for q, page in zip(queries, sampled, strict=True)}

            for raw, rank in ranks.items():
                page = by_raw[raw]
                if rank is None:
                    issues.append({
                        "rule": self.name,
                        "severity": self.severity,
                        "page": page.rel_path,
                        "message": (
                            f"not returned when searching for its own title "
                            f"{page.title!r} (score ≤ 0 or absent from search corpus)"
                        ),
                    })
                elif rank > PAGE_CAP_FOR_FINDABILITY:
                    issues.append({
                        "rule": self.name,
                        "severity": self.severity,
                        "page": page.rel_path,
                        "message": (
                            f"not returned when searching for its own title "
                            f"{page.title!r}: results cut short before reaching it "
                            f"(rank {rank} > page cap {PAGE_CAP_FOR_FINDABILITY})"
                        ),
                    })

        # R2: [[wikilink]] anchors → resolved target (same resolver as graph).
        all_lookups = collect_wikilink_lookups(scan.pages)
        sampled_lookups = sample_evenly(all_lookups, sample_max)
        issues.append({
            "rule": self.name,
            "severity": "info",
            "page": "",
            "message": (
                f"checked {len(sampled_lookups)} of {len(all_lookups)} "
                f"wikilink lookups"
            ),
        })
        if not sampled_lookups:
            return issues

        phrase_lookups = [
            pair for pair in sampled_lookups if _is_phrase_anchor(pair[0])
        ]
        term_lookups = [
            pair for pair in sampled_lookups if not _is_phrase_anchor(pair[0])
        ]

        if phrase_lookups:
            wl_queries, wl_targets = wikilink_lookup_queries(phrase_lookups)
            wl_ranks = rank_of(wiki_pages, wl_queries, wl_targets)
            by_wl = {
                q.raw: (anchor, rel)
                for q, (anchor, rel) in zip(
                    wl_queries, phrase_lookups, strict=True
                )
            }
            for raw, rank in wl_ranks.items():
                anchor, target_rel = by_wl[raw]
                if rank is None:
                    issues.append({
                        "rule": self.name,
                        "severity": self.severity,
                        "page": target_rel,
                        "message": (
                            f"wikilink {anchor!r} did not return resolved "
                            f"target {target_rel} (score ≤ 0 or absent from "
                            f"search corpus)"
                        ),
                    })
                elif rank > PAGE_CAP_FOR_FINDABILITY:
                    issues.append({
                        "rule": self.name,
                        "severity": self.severity,
                        "page": target_rel,
                        "message": (
                            f"wikilink {anchor!r} did not return resolved "
                            f"target {target_rel}: results cut short "
                            f"(rank {rank} > page cap {PAGE_CAP_FOR_FINDABILITY})"
                        ),
                    })

        if term_lookups:
            # One multi-query pass — same corpus search_match MCP/CLI use.
            unique_anchors = list(dict.fromkeys(a for a, _ in term_lookups))
            match_results = search_match(
                wiki_pages,
                unique_anchors,
                page_cap=PAGE_CAP_FOR_FINDABILITY,
            )
            for anchor, target_rel in term_lookups:
                target_norm = target_rel.replace("\\", "/")
                result = match_results.get(anchor)
                hit_paths = {
                    p.rel_path.replace("\\", "/")
                    for p in (result.pages if result else ())
                }
                if target_norm in hit_paths:
                    continue
                if result is not None and result.truncated:
                    issues.append({
                        "rule": self.name,
                        "severity": self.severity,
                        "page": target_rel,
                        "message": (
                            f"wikilink {anchor!r} did not return resolved "
                            f"target {target_rel}: results cut short "
                            f"(page cap {PAGE_CAP_FOR_FINDABILITY})"
                        ),
                    })
                else:
                    issues.append({
                        "rule": self.name,
                        "severity": self.severity,
                        "page": target_rel,
                        "message": (
                            f"wikilink {anchor!r} did not return resolved "
                            f"target {target_rel} (score ≤ 0 or absent from "
                            f"search corpus)"
                        ),
                    })

        return issues
