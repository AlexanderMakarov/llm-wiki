"""Lint rule registry (v1.0 · #155).

Originally the 11 rules from the LLM Book design spec
(08-quality-maintenance.md); has since grown past that.  The live
count is ``len(REGISTRY)`` — see ``llmwiki/lint/rules.py`` for the
canonical list.  Each rule is a subclass of :class:`LintRule`
registered via the ``@register`` decorator.

Usage::

    from llmwiki.lint import run_all, load_pages

    pages = load_pages()  # reads wiki/*.md into dicts
    issues = run_all(pages)
    for issue in issues:
        print(f"{issue['severity']} [{issue['rule']}] {issue['message']}")

Rule severity levels: ``error``, ``warning``, ``info``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from llmwiki import REPO_ROOT

# #495: use the canonical parser instead of a local LF-only regex.
# The local copy missed BOM (#423) and CRLF (#409) line endings — every
# Windows- or BOM-prefixed wiki page silently parsed as zero
# frontmatter, so every lint rule that read `meta["type"]` skipped it.
from llmwiki._frontmatter import parse_frontmatter as _parse_fm
from llmwiki._system_pages import is_archived_path
from llmwiki.vault_settings import DEFAULT_MIN_REFS

WIKI_DIR = REPO_ROOT / "wiki"


@dataclass(frozen=True)
class LintOptions:
    """Run-time settings handed to every rule instance by the runner (#150).

    Options travel on the rule *instance*, never as a new keyword argument to
    :meth:`LintRule.run`: 16 of the 17 registered rules declare
    ``run(self, pages, *, llm_callback=None)`` and the runner turns a rule
    exception into an error-severity issue, so a new kwarg would report a
    clean vault as 16 errors instead of failing loudly.
    """

    #: How many distinct source pages must name a wikilink target before an
    #: unresolved link to it counts as a defect. Shared with the candidate
    #: harvest via :data:`llmwiki.vault_settings.DEFAULT_MIN_REFS`, so the step
    #: that declines to materialize a target and the check that reports the
    #: missing page cannot disagree.
    min_refs: int = DEFAULT_MIN_REFS


class LintRule:
    """Base class for lint rules."""

    name: str = "base"
    description: str = ""
    severity: str = "warning"
    auto_fixable: bool = False
    #: Set on the instance by :func:`run_all` before :meth:`run` is called.
    #: A class-level default means a rule constructed directly — as the tests
    #: and the perf suite do — always has one.
    options: LintOptions = LintOptions()

    def run(
        self,
        pages: dict[str, dict[str, Any]],
        **_kwargs: Any,
    ) -> list[dict[str, Any]]:
        """Run the rule against the given pages. Return a list of issues.

        Each issue dict has: ``rule`` (name), ``severity``, ``page`` (path),
        ``message``, optional ``fix`` (auto-fix suggestion).

        Extra keyword arguments are accepted and ignored so older callers
        that passed ``llm_callback=…`` (removed in #72) keep working.
        """
        raise NotImplementedError


class UnknownRuleError(ValueError):
    """Raised when a caller selects a lint rule name that is not registered."""

    def __init__(self, unknown: list[str], valid: list[str]) -> None:
        self.unknown = list(unknown)
        self.valid = list(valid)
        super().__init__(
            f"unknown lint rule(s): {', '.join(self.unknown)}. "
            f"Valid rules: {', '.join(self.valid)}"
        )


REGISTRY: dict[str, type[LintRule]] = {}


def register(cls: type[LintRule]) -> type[LintRule]:
    """Decorator to register a lint rule."""
    REGISTRY[cls.name] = cls
    return cls


# ─── Page loading ──────────────────────────────────────────────────────

def parse_frontmatter(text: str) -> dict[str, Any]:
    """Parse YAML-like frontmatter from markdown text.

    #495: thin wrapper around the canonical
    :func:`llmwiki._frontmatter.parse_frontmatter` so lint sees the
    same shape — including BOM-stripped, CRLF-tolerant input, real
    list/bool values — as build.py and the synth pipeline.
    Backward-compatible: returns the meta dict only (callers that
    want body still use ``FRONTMATTER_RE.sub("", text, count=1)``).
    """
    meta, _body = _parse_fm(text)
    return meta


def load_pages(wiki_dir: Path | None = None) -> dict[str, dict[str, Any]]:
    """Load all wiki pages. Returns dict of relative_path → page dict.

    Each page dict has: ``path``, ``text``, ``meta`` (frontmatter), ``body``.
    """
    root = wiki_dir or WIKI_DIR
    if not root.is_dir():
        return {}
    pages: dict[str, dict[str, Any]] = {}
    for p in sorted(root.rglob("*.md")):
        rel_path = p.relative_to(root)
        # Skip README and archive/. archive/ is cold storage (#140): it holds
        # demoted and discarded pages, so linting it would re-report issues
        # already resolved by the discard. Leaving those pages out also means
        # link_integrity reports a [[wikilink]] to a discarded slug as broken,
        # which is the intended reading — the target was deliberately thrown
        # away, and the link needs a human decision, not a silent resolve.
        if p.name == "README.md" or is_archived_path(rel_path.parts):
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        # #495: derive both meta + body from the canonical parser in
        # one pass — was two regex hits before, and the body-substitution
        # used the legacy LF-only regex which would leave CRLF-prefixed
        # frontmatter intact in body output.
        meta, body = _parse_fm(text)
        rel = str(rel_path)
        pages[rel] = {
            "path": p,
            "rel": rel,
            "text": text,
            "meta": meta,
            "body": body,
        }
    return pages


# ─── Runner ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class LintOutcome:
    """What a lint run found *and* what it never looked at (#150).

    A report that only carries findings cannot tell a clean vault from a
    vault whose checks were all switched off, so the runner returns both
    and :mod:`llmwiki.lint.report` prints both.
    """

    #: Every issue the rules that ran produced, in registry order, each
    #: rule's own findings sorted by ``(page, message)`` — see
    #: :func:`_issue_sort_key`.
    issues: list[dict[str, Any]] = field(default_factory=list)
    #: Rules the vault switched off → the recorded reason (``""`` when none).
    #: The vault's whole declaration, including rules this run never selected.
    skipped: dict[str, str] = field(default_factory=dict)
    #: Names of the rules that actually ran, in registry order.
    ran: list[str] = field(default_factory=list)
    #: Names of the rules this run *would* have used had the vault disabled
    #: nothing — the whole registry, or the ``selected`` subset of it, in
    #: registry order. Reports count against this rather than against
    #: ``REGISTRY``: a run narrowed to one rule that the vault happens to
    #: disable skipped one rule of one, not one of seventeen.
    considered: list[str] = field(default_factory=list)


def _normalize_disabled(
    disabled: Mapping[str, str] | Iterable[str] | None,
) -> dict[str, str]:
    """Accept either declared shape and return ``{rule name: reason}``."""
    if not disabled:
        return {}
    if isinstance(disabled, Mapping):
        return {str(name): ("" if reason is None else str(reason))
                for name, reason in disabled.items()}
    return dict.fromkeys((str(name) for name in disabled), "")


def _issue_sort_key(issue: Mapping[str, Any]) -> tuple[str, str]:
    """Order one rule's findings by page, then message.

    Several rules walk a ``set`` — ``link_integrity`` iterates
    :func:`llmwiki.wikilinks.wikilink_targets`, which returns one — so with
    ``PYTHONHASHSEED`` randomised two *processes* emit the same findings in
    different order. The CLI and the MCP server are different processes, and
    both promise the same report for the same vault (#150 R9), so a raw
    payload diff between them must not disagree about ordering alone.
    """
    return (str(issue.get("page", "")), str(issue.get("message", "")))


def run_lint(
    pages: dict[str, dict[str, Any]],
    *,
    selected: list[str] | None = None,
    disabled: Mapping[str, str] | Iterable[str] | None = None,
    options: LintOptions | None = None,
) -> LintOutcome:
    """Run the registered lint rules and report what was skipped.

    Parameters
    ----------
    pages : dict
        Output of :func:`load_pages`.
    selected : list[str], optional
        Run only these rules by name. Default: all.
    disabled : mapping or iterable, optional
        Rules the vault declared as not applicable — either
        ``{"name": "reason"}`` or ``["name"]``. A disabled rule is never
        constructed and contributes no issues.
    options : LintOptions, optional
        Run-time settings set on each rule instance before it runs.

    Raises
    ------
    UnknownRuleError
        If ``selected`` or ``disabled`` names a rule that is not in
        :data:`REGISTRY`. A misspelled or retired name must fail loudly:
        skipping it silently would leave a check switched on that the
        author believed they had switched off, and report the result as
        clean.
    """
    # Import all rule modules so they register themselves
    from llmwiki.lint import rules  # noqa: F401, PLC0415 — lazy package rules registry

    skipped = _normalize_disabled(disabled)
    unknown = [name for name in (selected or []) if name not in REGISTRY]
    unknown += [name for name in skipped if name not in REGISTRY]
    if unknown:
        raise UnknownRuleError(unknown, sorted(REGISTRY))

    resolved_options = options or LintOptions()
    considered = [name for name in REGISTRY if not selected or name in selected]
    issues: list[dict[str, Any]] = []
    ran: list[str] = []
    for name in considered:
        if name in skipped:
            continue
        ran.append(name)
        rule = REGISTRY[name]()
        rule.options = resolved_options
        try:
            issues.extend(sorted(rule.run(pages), key=_issue_sort_key))
        except Exception as e:
            issues.append({
                "rule": name,
                "severity": "error",
                "page": "",
                "message": f"rule raised exception: {e}",
            })
    return LintOutcome(
        issues=issues, skipped=skipped, ran=ran, considered=considered
    )


def run_all(
    pages: dict[str, dict[str, Any]],
    *,
    selected: list[str] | None = None,
    options: LintOptions | None = None,
    **_kwargs: Any,
) -> list[dict[str, Any]]:
    """Run all registered lint rules. Returns a flat list of issues.

    A thin wrapper over :func:`run_lint` for the callers that only want
    findings. Callers that must distinguish "found nothing" from "checked
    nothing" use :func:`run_lint` and read :attr:`LintOutcome.skipped`.

    Extra keyword arguments (``include_llm``, ``llm_callback``) are accepted
    and ignored for back-compat with callers written before #72 removed the
    unused LLM lint gate.
    """
    return run_lint(pages, selected=selected, options=options).issues


def summarize(issues: list[dict[str, Any]]) -> dict[str, int]:
    """Return {severity: count} summary."""
    summary: dict[str, int] = {}
    for i in issues:
        sev = i.get("severity", "info")
        summary[sev] = summary.get(sev, 0) + 1
    return summary
