"""orphan_detection — pages with zero inbound links are orphans."""

from __future__ import annotations

import re

from llmwiki._system_pages import SYSTEM_PAGE_SLUGS
from llmwiki.lint import LintRule, register
from llmwiki.lint.rules._helpers import _page_slug, _resolve_index_href
from llmwiki.wikilinks import (
    build_page_alias_map,
    resolve_wikilink_target,
    wikilink_targets,
)

# Markdown catalog links — index.md (and other pages) list sources as
# `[title](sources/….md)` rather than `[[wikilinks]]`.
_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


@register
class OrphanDetection(LintRule):
    """Pages with zero inbound [[wikilinks]] or catalog markdown links are orphans."""

    name = "orphan_detection"
    severity = "info"

    def run(self, pages, *, llm_callback=None):
        del llm_callback  # unused — reserved / legacy kwarg
        slugs = {_page_slug(rel) for rel in pages}
        alias_map = build_page_alias_map(
            {_page_slug(rel): page["body"] for rel, page in pages.items()}
        )
        # Collect inbound from [[wikilinks]] and markdown [text](path.md) hrefs.
        inbound: dict[str, int] = {}
        for _rel, page in pages.items():
            for t in wikilink_targets(page["body"]):
                resolved = resolve_wikilink_target(t, slugs, alias_map) or t
                inbound[resolved] = inbound.get(resolved, 0) + 1
            for match in _MD_LINK_RE.finditer(page["body"]):
                href = match.group(2)
                if href.startswith(("http://", "https://", "mailto:")):
                    continue
                resolved = _resolve_index_href(href)
                if not resolved or resolved not in pages:
                    continue
                slug = _page_slug(resolved)
                inbound[slug] = inbound.get(slug, 0) + 1

        # #py-l5 (#603): pull the skip list from the canonical
        # SYSTEM_PAGE_SLUGS so dashboard.md can't get lint-flagged as
        # an orphan in one rule while exempt in another (it WAS being
        # flagged here even though MetadataValidator's EXEMPT_FILES
        # already exempted it from the strict title/type check).
        issues = []
        for rel in pages:
            slug = _page_slug(rel)
            # Skip navigation / context / index files (canonical list).
            if rel.endswith("_context.md") or slug in SYSTEM_PAGE_SLUGS:
                continue
            if inbound.get(slug, 0) == 0:
                issues.append({
                    "rule": self.name,
                    "severity": "info",
                    "page": rel,
                    "message": "orphan page (no inbound [[wikilinks]] or catalog links)",
                })
        return issues
