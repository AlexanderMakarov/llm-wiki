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

from llmwiki.lint import LintOutcome, summarize
from llmwiki.vault_settings import VAULT_SETTINGS_FILENAME

__all__ = ["render_json", "render_text"]

#: How many findings of one rule are listed before the tail is summarised.
_MAX_PER_RULE = 20


def _considered(outcome: LintOutcome) -> list[str]:
    """The rules this run would have used — the denominator both lines quote.

    ``run_lint`` always fills :attr:`LintOutcome.considered`; the fallback
    covers an outcome assembled by hand, for which "what ran plus what was
    switched off" is the same set.
    """
    if outcome.considered:
        return list(outcome.considered)
    return [*outcome.ran, *(n for n in outcome.skipped if n not in outcome.ran)]


def _skipped_lines(outcome: LintOutcome, settings_filename: str) -> list[str]:
    """The "here is what nobody checked" block, or nothing to say.

    Both numbers count against the rules this run would have used, never
    against the whole registry: a rule the vault disables that ``--rules``
    never selected was not skipped by this run, and a run narrowed to three
    rules cannot skip one of seventeen.
    """
    considered = _considered(outcome)
    in_run = set(considered)
    relevant = {
        name: reason
        for name, reason in outcome.skipped.items()
        if name in in_run
    }
    if not relevant:
        return []
    lines = [
        f"  skipped {len(relevant)} of {len(considered)} rules "
        f"(disabled in {settings_filename}):"
    ]
    for name, reason in sorted(relevant.items()):
        lines.append(f"    - {name} — {reason}" if reason else f"    - {name}")
    return lines


def render_text(
    outcome: LintOutcome,
    total_pages: int,
    *,
    settings_filename: str = VAULT_SETTINGS_FILENAME,
) -> str:
    """Render a lint outcome as the report ``llmwiki lint`` prints.

    The returned string carries no trailing newline; ``print`` supplies it,
    which reproduces the blank line the report has always ended on.

    ``settings_filename`` names the file a skipped rule was declared in.
    It is an argument rather than a lookup so the renderer stays a renderer:
    *why* a rule was skipped is the caller's knowledge, not lint's.
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
        # The count is of what this run would have used, not of the whole
        # registry: `--rules` can empty `ran` without disabling anything.
        n = len(_considered(outcome))
        lines.append(
            f"  nothing was checked — all {n} "
            f"{'rule' if n == 1 else 'rules'} this run would have used "
            f"{'was' if n == 1 else 'were'} skipped, so this is not a "
            "clean result"
        )
    lines.extend(_skipped_lines(outcome, settings_filename))
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

    ``ran`` names the checks that actually produced this payload. Without
    it a run narrowed by ``rules`` — which the MCP tool accepts — is
    indistinguishable from a full one, and a short report reads as a clean
    one; ``disabled_rules`` only covers the narrowing the vault declared.
    """
    return {
        "summary": summarize(outcome.issues),
        "issues": outcome.issues,
        "total_pages": total_pages,
        "disabled_rules": dict(outcome.skipped),
        "ran": list(outcome.ran),
    }
