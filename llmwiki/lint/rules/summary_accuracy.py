"""summary_accuracy — `summary:` field must be non-empty when present."""

from __future__ import annotations

from llmwiki.lint import LintRule, register


@register
class SummaryAccuracy(LintRule):
    """Flag pages whose summary: frontmatter field is present but empty."""

    name = "summary_accuracy"
    severity = "info"

    def run(self, pages, *, llm_callback=None):  # llm_callback kept for back-compat
        del llm_callback  # unused — reserved / legacy kwarg
        issues = []
        for rel, page in pages.items():
            meta = page["meta"]
            summary = meta.get("summary", "")
            if "summary" in meta and not str(summary).strip():
                issues.append({
                    "rule": self.name,
                    "severity": "info",
                    "page": rel,
                    "message": "summary field is empty",
                })
        return issues
