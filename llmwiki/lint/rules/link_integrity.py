"""link_integrity — [[wikilinks]] must resolve to existing pages."""

from __future__ import annotations

import re

from llmwiki.lint import LintRule, register
from llmwiki.lint.rules._helpers import _page_slug
from llmwiki.wikilinks import WIKILINK_RE, strip_anchor

_NORM_RE = re.compile(r"[^a-z0-9]")


def _norm_slug(s: str) -> str:
    """Case/punct-insensitive key: ``LLM-Wiki`` / ``llm wiki`` → ``llmwiki``."""
    return _NORM_RE.sub("", s.lower())


@register
class LinkIntegrity(LintRule):
    """[[wikilinks]] must resolve to existing pages."""

    name = "link_integrity"
    severity = "warning"
    auto_fixable = True

    def run(self, pages, *, llm_callback=None):
        del llm_callback  # unused — reserved / legacy kwarg
        # Exact slugs + normalized alias map (first page wins per key).
        slugs = {_page_slug(rel) for rel in pages}
        by_norm: dict[str, str] = {}
        for slug in slugs:
            key = _norm_slug(slug)
            if key and key not in by_norm:
                by_norm[key] = slug

        issues = []
        for rel, page in pages.items():
            # The raw target — anchor included — is what the message quotes,
            # so the operator can find the link they need to fix.
            for target in set(WIKILINK_RE.findall(page["body"])):
                t = strip_anchor(target)
                if not t:
                    continue
                if t in slugs or _norm_slug(t) in by_norm:
                    continue
                issues.append({
                    "rule": self.name,
                    "severity": "warning",
                    "page": rel,
                    "message": f"broken wikilink [[{target}]]",
                })
        return issues
