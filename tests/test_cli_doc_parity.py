"""Every `llmwiki <subcommand>` advertised in the README must exist.

#494 caught a README CLI table that listed removed commands. The README
is now a product page (no ``## CLI reference`` table — that lives in
``docs/reference/cli.md``). This still scans every ``llmwiki <name>``
invocation in the README so a stale command cannot come back.
"""

from __future__ import annotations

import re
from pathlib import Path

from llmwiki.cli import build_parser

REPO_ROOT = Path(__file__).resolve().parents[1]
README = REPO_ROOT / "README.md"

_FENCE_RE = re.compile(r"```(?:bash|shell|text|cmd)?\n(.*?)```", re.DOTALL)
_CMD_RE = re.compile(r"(?:^|\s)llmwiki\s+([a-z][a-z0-9-]*)\b")
_INLINE_RE = re.compile(r"`llmwiki\s+([a-z][a-z0-9-]*)")


def _collect_real_subcommands() -> set[str]:
    """Return the set of registered subparser names."""
    parser = build_parser()
    for action in parser._actions:
        if hasattr(action, "choices") and isinstance(action.choices, dict):
            return set(action.choices)
    raise AssertionError("could not locate subparsers on build_parser()")


def _collect_readme_subcommands() -> set[str]:
    text = README.read_text(encoding="utf-8")
    names: set[str] = set()
    for block in _FENCE_RE.findall(text):
        names.update(_CMD_RE.findall(block))
    names.update(_INLINE_RE.findall(text))
    return {name for name in names if name != "version"}


def test_every_readme_cli_line_maps_to_a_real_subparser():
    """Every `llmwiki <name>` in README.md must exist as a real
    subparser. Closes #494."""
    real = _collect_real_subcommands()
    advertised = _collect_readme_subcommands()
    phantom = advertised - real
    assert not phantom, (
        f"README CLI table advertises subcommands that don't exist: "
        f"{sorted(phantom)}. Real subparsers: {sorted(real)}. "
        f"Either wire up the missing subparsers in cli.py:build_parser() or "
        f"remove the lines from README.md (the original bug, #494)."
    )
