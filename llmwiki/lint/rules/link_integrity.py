"""link_integrity — [[wikilinks]] must resolve to existing pages."""

from __future__ import annotations

import re

from llmwiki.lint import WIKILINK_RE, LintRule, register
from llmwiki.lint.rules._helpers import _page_slug

_NORM_RE = re.compile(r"[^a-z0-9]")


def _norm_slug(s: str) -> str:
    """Case/punct-insensitive key: ``LLM-Wiki`` / ``llm wiki`` → ``llmwiki``."""
    return _NORM_RE.sub("", s.lower())


def _is_candidate_rel(rel: str) -> bool:
    """True when ``rel`` lives under ``wiki/candidates/`` (any OS separator)."""
    return "candidates/" in rel.replace("\\", "/")


@register
class LinkIntegrity(LintRule):
    """[[wikilinks]] must resolve to existing **trusted** pages.

    Pending candidates under ``wiki/candidates/`` do **not** satisfy
    inbound links (#90). The review queue exists so approval means
    something — a metric that clears itself at generation time undercuts
    that gate. Harvesting already refuses to treat candidates as resolved
    (otherwise re-runs are no-ops); this rule matches that answer.
    """

    name = "link_integrity"
    severity = "warning"
    auto_fixable = True

    def run(self, pages, *, llm_callback=None):
        del llm_callback  # unused — reserved / legacy kwarg
        # Exact slugs + normalized alias map (first page wins per key).
        # Candidates are loaded by lint but do not close the gap until promoted.
        trusted = [rel for rel in pages if not _is_candidate_rel(rel)]
        slugs = {_page_slug(rel) for rel in trusted}
        by_norm: dict[str, str] = {}
        for slug in slugs:
            key = _norm_slug(slug)
            if key and key not in by_norm:
                by_norm[key] = slug

        issues = []
        for rel, page in pages.items():
            for target in set(WIKILINK_RE.findall(page["body"])):
                # Strip any embedded section anchors
                t = target.split("#")[0].strip()
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
