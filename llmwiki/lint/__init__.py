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

import re
from pathlib import Path
from typing import Any

from llmwiki import REPO_ROOT

# #495: use the canonical parser instead of a local LF-only regex.
# The local copy missed BOM (#423) and CRLF (#409) line endings — every
# Windows- or BOM-prefixed wiki page silently parsed as zero
# frontmatter, so every lint rule that read `meta["type"]` skipped it.
from llmwiki._frontmatter import parse_frontmatter as _parse_fm

WIKI_DIR = REPO_ROOT / "wiki"
WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]")


class LintRule:
    """Base class for lint rules."""

    name: str = "base"
    description: str = ""
    severity: str = "warning"
    auto_fixable: bool = False

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
        # Skip README and archive/ — the latter holds demoted and
        # discarded pages, so linting it re-reports resolved issues and
        # lets an archived slug keep satisfying [[wikilinks]].
        if p.name == "README.md" or rel_path.parts[0] == "archive":
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

def run_all(
    pages: dict[str, dict[str, Any]],
    *,
    selected: list[str] | None = None,
    **_kwargs: Any,
) -> list[dict[str, Any]]:
    """Run all registered lint rules. Returns a flat list of issues.

    Parameters
    ----------
    pages : dict
        Output of :func:`load_pages`.
    selected : list[str], optional
        Run only these rules by name. Default: all.

    Extra keyword arguments (``include_llm``, ``llm_callback``) are accepted
    and ignored for back-compat with callers written before #72 removed the
    unused LLM lint gate.

    Raises
    ------
    UnknownRuleError
        If ``selected`` names a rule that is not in :data:`REGISTRY`. A
        misspelled or removed rule name must fail loudly — skipping it
        would report a clean vault while running nothing.
    """
    # Import all rule modules so they register themselves
    from llmwiki.lint import rules  # noqa: F401, PLC0415 — lazy package rules registry

    if selected:
        unknown = [name for name in selected if name not in REGISTRY]
        if unknown:
            raise UnknownRuleError(unknown, sorted(REGISTRY))

    issues: list[dict[str, Any]] = []
    for name, rule_cls in REGISTRY.items():
        if selected and name not in selected:
            continue
        rule = rule_cls()
        try:
            issues.extend(rule.run(pages))
        except Exception as e:
            issues.append({
                "rule": name,
                "severity": "error",
                "page": "",
                "message": f"rule raised exception: {e}",
            })
    return issues


def summarize(issues: list[dict[str, Any]]) -> dict[str, int]:
    """Return {severity: count} summary."""
    summary: dict[str, int] = {}
    for i in issues:
        sev = i.get("severity", "info")
        summary[sev] = summary.get(sev, 0) + 1
    return summary
