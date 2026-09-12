"""search_consistency — search must agree with a literal corpus scan (#197)."""

from __future__ import annotations

from typing import Any

from llmwiki.lint import LintRule, register
from llmwiki.lint.rules._search_options import search_options_skip_reason
from llmwiki.search.engine import search_match
from llmwiki.search.evaluate import (
    DEFAULT_CONSISTENCY_TERM_COUNT,
    select_absent_terms,
    select_present_terms,
    survival_share,
)


@register
class SearchConsistency(LintRule):
    """Error when match-mode search disagrees with a literal vault scan."""

    name = "search_consistency"
    severity = "error"
    description = (
        "Search disagrees with a literal scan over wiki pages and session "
        "content; reports survival share as information"
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
        assert ctx is not None  # skip_reason already requires both options
        scan = ctx.corpus()
        corpus_pages = scan.pages

        present = select_present_terms(
            corpus_pages, count=DEFAULT_CONSISTENCY_TERM_COUNT
        )
        absent = select_absent_terms(corpus_pages, count=5)

        issues: list[dict[str, Any]] = []

        # R3: every term used is shown, both groups.
        issues.append({
            "rule": self.name,
            "severity": "info",
            "page": "",
            "message": (
                "present terms: "
                + (", ".join(present) if present else "(none)")
            ),
        })
        issues.append({
            "rule": self.name,
            "severity": "info",
            "page": "",
            "message": (
                "absent terms: "
                + (", ".join(absent) if absent else "(none)")
            ),
        })

        share = survival_share(present, corpus_pages)
        if share is not None:
            pct = round(100 * share)
            issues.append({
                "rule": self.name,
                "severity": "info",
                "page": "",
                "message": (
                    f"survival share: {pct}% of sampled session terms also "
                    f"appear in wiki pages (informational; never a failure)"
                ),
            })

        terms = list(present) + list(absent)
        if not terms:
            return issues

        results = search_match(corpus_pages, terms)
        blob = "\n".join(p.text_lower for p in corpus_pages)

        for term in present:
            literal = term.lower() in blob
            hits = results.get(term)
            has_hits = bool(hits and hits.pages)
            if literal and not has_hits:
                issues.append({
                    "rule": self.name,
                    "severity": self.severity,
                    "page": "",
                    "message": (
                        f"present term {term!r} is in the vault by literal "
                        f"scan but search returned no results"
                    ),
                })
            elif not literal and has_hits:
                # Selection promised present; if the file disappeared mid-run.
                issues.append({
                    "rule": self.name,
                    "severity": self.severity,
                    "page": "",
                    "message": (
                        f"term {term!r} selected as present but literal scan "
                        f"no longer finds it while search returned hits"
                    ),
                })

        for term in absent:
            literal = term.lower() in blob
            hits = results.get(term)
            has_hits = bool(hits and hits.pages)
            if not literal and has_hits:
                issues.append({
                    "rule": self.name,
                    "severity": self.severity,
                    "page": "",
                    "message": (
                        f"absent term {term!r} is not in the vault by literal "
                        f"scan but search returned results"
                    ),
                })
            elif literal and not has_hits:
                issues.append({
                    "rule": self.name,
                    "severity": self.severity,
                    "page": "",
                    "message": (
                        f"term {term!r} selected as absent but literal scan "
                        f"finds it while search returned nothing"
                    ),
                })

        return issues
