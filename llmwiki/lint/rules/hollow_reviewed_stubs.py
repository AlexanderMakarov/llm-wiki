"""hollow_reviewed_stubs — promoted entity/concept pages that are still empty (#90)."""

from __future__ import annotations

from llmwiki.lint import LintRule, register

_TRUSTED_PREFIXES = ("entities/", "concepts/")


def _is_hollow_body(body: str) -> bool:
    """True when nothing above ``## Connections`` is real prose.

    Harvest stubs ship with a title and an empty ``## Key Facts``; reviewers
    own everything above Connections. Headings and blank lines alone mean the
    page still has no knowledge content — link integrity is satisfied by
    existence, not substance.
    """
    above, _, _ = body.partition("## Connections")
    for line in above.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("#"):
            continue
        return False
    return True


@register
class HollowReviewedStubs(LintRule):
    """Flag promoted entity/concept pages that are still empty stubs (#90).

    After ``candidates promote``, ``status: reviewed`` pages exist in the
    trusted tree but may still carry only the harvest skeleton. Thin is
    correct while pending under ``wiki/candidates/`` — those are exempt.
    Enriching a promoted stub is a real LLM (or human) pass.
    """

    name = "hollow_reviewed_stubs"
    severity = "warning"

    def run(self, pages, *, llm_callback=None):
        del llm_callback
        issues = []
        for rel, page in pages.items():
            rel_posix = rel.replace("\\", "/")
            if "candidates/" in rel_posix:
                continue
            if not rel_posix.startswith(_TRUSTED_PREFIXES):
                continue
            if page["meta"].get("status") != "reviewed":
                continue
            if not _is_hollow_body(page["body"]):
                continue
            issues.append({
                "rule": self.name,
                "severity": self.severity,
                "page": rel,
                "message": (
                    "promoted page is still an empty stub (no prose above "
                    "## Connections) — enrich Key Facts before treating it "
                    "as trusted knowledge"
                ),
            })
        return issues
