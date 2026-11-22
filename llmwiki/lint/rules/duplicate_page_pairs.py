"""duplicate_page_pairs — flag pending vocabulary-fold duplicate live pages (#365).

Distinct from :mod:`llmwiki.lint.rules.duplicate_detection` (title+body
similarity). This rule uses :func:`llmwiki.topics.detect_duplicate_pairs`
over entities/concepts/projects.
"""

from __future__ import annotations

from pathlib import Path

from llmwiki.lint import LintRule, register
from llmwiki.topics import detect_duplicate_pairs


@register
class DuplicatePagePairs(LintRule):
    """Flag live curated/project pages that look like spelling/topic duplicates (#365).

    Emits one info finding per pending pair from
    :func:`detect_duplicate_pairs` (keep-distinct ledger rows are already
    omitted). Review via ``llmwiki candidates list`` or
    ``site/candidates.html`` (Possible duplicate pages) — merge-pages or
    keep-distinct. Not the body-similarity ``duplicate_detection`` rule.
    """

    name = "duplicate_page_pairs"
    severity = "info"

    def run(self, pages, *, llm_callback=None):
        del llm_callback
        issues = []
        if not pages:
            return issues
        sample_page = next(iter(pages.values()))
        page_path = sample_page.get("path")
        if not isinstance(page_path, Path):
            return issues
        wiki_dir = page_path.parent
        for _ in range(6):
            if wiki_dir.name == "wiki":
                break
            if wiki_dir == wiki_dir.parent:
                return issues
            wiki_dir = wiki_dir.parent
        if wiki_dir.name != "wiki":
            return issues
        for pair in detect_duplicate_pairs(wiki_dir):
            issues.append({
                "rule": self.name,
                "severity": self.severity,
                "page": pair.a.path,
                "message": (
                    f"possible duplicate pages '{pair.a.title}' ({pair.a.kind}) "
                    f"and '{pair.b.title}' ({pair.b.kind}) — review with "
                    f"`llmwiki candidates list` or site/candidates.html "
                    f"(Possible duplicate pages); merge-pages or keep-distinct"
                ),
            })
        return issues
