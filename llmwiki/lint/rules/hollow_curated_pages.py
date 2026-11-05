"""hollow_curated_pages — curated entity/concept with no graph edge and no body."""

from __future__ import annotations

from pathlib import Path

from llmwiki.lint import LintRule, register
from llmwiki.topics_health import hollow_isolated_curated_pages


@register
class HollowCuratedPages(LintRule):
    """Flag reviewed pages that are isolated in the topic graph and carry no facts.

    A page whose only prose lives under omitted sections (Connections, Sessions,
    Sources) and that no co-cited topic reaches is hollow — fix by adding Key
    Facts, merging, discarding, or deleting the file (#248 amendment).
    """

    name = "hollow_curated_pages"
    severity = "warning"

    def run(self, pages, *, llm_callback=None):
        del llm_callback  # graph is built from wiki dir, not the page map
        wiki_dir = _infer_wiki_dir(pages)
        if wiki_dir is None:
            return []
        issues = []
        for rel, title in hollow_isolated_curated_pages(wiki_dir):
            issues.append({
                "rule": self.name,
                "severity": self.severity,
                "page": rel,
                "message": (
                    f"curated page '{title}' has no connected topics and no "
                    "renderable body — add Key Facts, merge, discard, or remove "
                    "the file"
                ),
            })
        return issues


def _infer_wiki_dir(pages: dict) -> Path | None:
    if not pages:
        return None
    sample = next(iter(pages.values()))
    page_path = sample.get("path")
    if not isinstance(page_path, Path):
        return None
    wiki_dir = page_path.parent
    for _ in range(6):
        if wiki_dir.name == "wiki":
            return wiki_dir
        if wiki_dir == wiki_dir.parent:
            return None
        wiki_dir = wiki_dir.parent
    return None
