"""claim_verification — entity/concept/project pages with claims should cite sources."""

from __future__ import annotations

import re

from llmwiki.lint import LintRule, register


@register
class ClaimVerification(LintRule):
    """Flag entity/concept/project pages that make claims but cite no sources."""

    name = "claim_verification"
    severity = "info"

    CHECKED_TYPES = ("entity", "concept", "project")

    def run(self, pages, *, llm_callback=None):  # llm_callback kept for back-compat
        del llm_callback  # unused — reserved / legacy kwarg
        # Structural: entity/concept/project pages with ## Key Facts /
        # ## Key Claims should also cite sources (frontmatter, ## Sessions,
        # or ## Sources).
        issues = []
        for rel, page in pages.items():
            meta = page["meta"]
            if meta.get("type") not in self.CHECKED_TYPES:
                continue
            has_claims = bool(re.search(r"## Key (Facts|Claims)", page["body"]))
            has_sources = bool(meta.get("sources")) or \
                "## Sessions" in page["body"] or \
                "## Sources" in page["body"]
            if has_claims and not has_sources:
                issues.append({
                    "rule": self.name,
                    "severity": "info",
                    "page": rel,
                    "message": "page makes claims but cites no sources",
                })
        return issues
