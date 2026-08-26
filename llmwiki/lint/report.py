"""Rendering of a lint run for people and for machines (#150).

One reporter, so the ``lint`` command, the ``all`` pipeline, and the MCP
tool cannot drift into three different accounts of the same wiki — and so
that "which checks were skipped" is added once rather than three times.

The honesty rule both renderers implement: a skipped rule is named
**whether or not anything was found**, and a run in which nothing was
checked says so instead of printing a clean summary.
"""

from __future__ import annotations

from typing import Any

from llmwiki.lint import REGISTRY, LintOutcome, summarize
from llmwiki.lint import rules as _rules  # noqa: F401 — populate REGISTRY
from llmwiki.vault_settings import VAULT_SETTINGS_FILENAME

__all__ = ["render_json", "render_text"]

#: How many findings of one rule are listed before the tail is summarised.
_MAX_PER_RULE = 20


def _skipped_lines(outcome: LintOutcome) -> list[str]:
    """The "here is what nobody checked" block, or nothing to say."""
    if not outcome.skipped:
        return []
    lines = [
        f"  skipped {len(outcome.skipped)} of {len(REGISTRY)} rules "
        f"(disabled in {VAULT_SETTINGS_FILENAME}):"
    ]
    for name, reason in sorted(outcome.skipped.items()):
        lines.append(f"    - {name} — {reason}" if reason else f"    - {name}")
    return lines


def render_text(outcome: LintOutcome, total_pages: int) -> str:
    """Render a lint outcome as the report ``llmwiki lint`` prints.

    The returned string carries no trailing newline; ``print`` supplies it,
    which reproduces the blank line the report has always ended on.
    """
    lines = [f"  scanned {total_pages} pages"]
    if outcome.ran:
        summary = summarize(outcome.issues)
        lines.append(
            f"  {sum(summary.values())} issues: "
            f"{summary.get('error', 0)} errors, "
            f"{summary.get('warning', 0)} warnings, "
            f"{summary.get('info', 0)} info"
        )
    else:
        # Not a clean wiki — an unexamined one. Printing "0 issues" here
        # would be the exact dishonesty the opt-out feature must not buy.
        lines.append(
            f"  nothing was checked — every one of the {len(REGISTRY)} lint "
            "rules was skipped, so this is not a clean result"
        )
    lines.extend(_skipped_lines(outcome))
    lines.append("")

    by_rule: dict[str, list[dict[str, Any]]] = {}
    for issue in outcome.issues:
        by_rule.setdefault(issue["rule"], []).append(issue)
    for rule, rule_issues in sorted(by_rule.items()):
        lines.append(f"## {rule} ({len(rule_issues)})")
        for issue in rule_issues[:_MAX_PER_RULE]:
            lines.append(f"  [{issue['severity']}] {issue['page']}: {issue['message']}")
        if len(rule_issues) > _MAX_PER_RULE:
            lines.append(f"  ... and {len(rule_issues) - _MAX_PER_RULE} more")
        lines.append("")
    return "\n".join(lines)


def render_json(outcome: LintOutcome, total_pages: int) -> dict[str, Any]:
    """Render a lint outcome as the ``--json`` payload.

    ``disabled_rules`` is always present, empty when the vault declared
    nothing, so a consumer can read it without probing for the key.
    """
    return {
        "summary": summarize(outcome.issues),
        "issues": outcome.issues,
        "total_pages": total_pages,
        "disabled_rules": dict(outcome.skipped),
    }
