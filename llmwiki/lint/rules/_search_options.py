"""Shared skip gate for search findability lint rules (#197)."""

from __future__ import annotations

from llmwiki.lint import LintOptions


def search_options_skip_reason(options: LintOptions) -> str | None:
    """Skip when ``content_root`` or ``search_context`` is missing.

    Direct rule construction (tests, perf suite) leaves both unset; an
    unrunnable check must not read as a clean vault.
    """
    if options.content_root is None or options.search_context is None:
        return "search options not provided"
    return None
