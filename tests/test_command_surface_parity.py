"""Structural guardrail: Claude and Cursor slash-command surfaces (#227).

# @layer: unit
# @spec: 227-command-surface-parity
# @regression

Discovery model, as it actually is: both harnesses read top-level
``.claude/commands/*.md``, so one file there is invocable from Claude Code
*and* from Cursor — no per-surface duplicate is needed or wanted. Cursor
also reads ``.claude/skills/`` and ``.claude/agents/`` natively, which is
how the skill-backed ``/release`` body is shared.

What Cursor does **not** read is a nested namespace,
``.claude/commands/<ns>/<name>.md``. That is the one real gap, and it is
why the nine ``awos/`` commands need flat ``.cursor/commands/<ns>-<name>.md``
wrappers, generated from ``.awos/commands/`` by
``scripts/sync-awos-cursor-commands.sh``. Slash names differ accordingly:
``/awos:product`` on Claude, ``/awos-product`` on Cursor.

The tests below pin that model from both sides — nested namespaces must
have their flat wrapper, and a top-level command must *not* acquire a
redundant Cursor copy — plus the ``/maintainer`` and ``/triage-issue``
removals recorded in
``context/spec/227-command-surface-parity/flow-log.md``.

These tests are STRUCTURAL ONLY — file-level assertions against the repo
tree. They never invoke ``claude``, ``cursor-agent``, or any agent, and
never shell out to a network.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CLAUDE_CMDS = REPO_ROOT / ".claude" / "commands"
CURSOR_CMDS = REPO_ROOT / ".cursor" / "commands"

# ─── Allowlists (dicts, not bare sets, so every entry must be justified) ──

# Top-level Claude commands that nonetheless keep a `.cursor/commands/`
# file of the same name. Each entry needs a reason: the default is that no
# such duplicate should exist at all.
REDUNDANT_CURSOR_DUPLICATES: dict[str, str] = {
    "release": (
        "hand-written wrapper that predates the discovery that Cursor reads "
        "top-level .claude/commands/*.md; kept deliberately for now, and "
        "retiring it is tracked separately"
    ),
}

# Removed in #227 — must never come back, and no live doc may reference
# them as if they were still invocable.
REMOVED_COMMAND_NAMES = ("maintainer", "triage-issue")
# Negative lookbehind on the leading slash keeps this from tripping on an
# unrelated filesystem path like "docs/tests/maintainer reference" — a real
# slash-command mention is never itself preceded by another path segment.
REMOVED_COMMAND_PATTERNS = [re.compile(rf"(?<![\w/])/{name}\b") for name in REMOVED_COMMAND_NAMES]

# A small, explicit set of live, currently-accurate docs to scan for
# lingering references to the removed commands. Deliberately excludes:
#   - demo/**                          (synthetic vault fixtures, not repo docs)
#   - context/spec/**                  (historical flow logs / specs for past work)
#   - CHANGELOG.md                     (historical record of already-released versions)
#   - docs/maintainers/DECLINED.md     (deliberately preserves the original wording
#                                        plus a dated retirement note)
LIVE_DOCS = [
    REPO_ROOT / "docs" / "maintainers" / "README.md",
    REPO_ROOT / "docs" / "maintainers" / "TRIAGE.md",
    REPO_ROOT / "docs" / "maintainers" / "AWOS-CURSOR.md",
    REPO_ROOT / "docs" / "reference" / "slash-commands.md",
    REPO_ROOT / "docs" / "reference" / "cli.md",
    REPO_ROOT / "CONTRIBUTING.md",
    REPO_ROOT / "CLAUDE.md",
    REPO_ROOT / "context" / "product" / "delivery-flow.md",
]


# ─── Helpers ──────────────────────────────────────────────────────────────


def _top_level_claude_commands() -> list[Path]:
    return sorted(p for p in CLAUDE_CMDS.glob("*.md") if p.stem != "README")


def _nested_claude_commands() -> list[Path]:
    """Every ``.claude/commands/<ns>/<name>.md`` — the shape Cursor cannot load."""
    return sorted(p for p in CLAUDE_CMDS.glob("*/*.md") if p.stem != "README")


# ─── Property 1: nested namespaces need flat Cursor wrappers ────────────


def test_nested_claude_command_namespaces_have_flat_cursor_wrappers():
    # @regression
    # Cursor does not descend into `.claude/commands/<ns>/`, so each nested
    # command is only reachable there through a flat `<ns>-<name>.md`.
    offenders: list[str] = []
    for p in _nested_claude_commands():
        wrapper = CURSOR_CMDS / f"{p.parent.name}-{p.stem}.md"
        if not wrapper.is_file():
            offenders.append(f"{p.relative_to(REPO_ROOT)}: no {wrapper.relative_to(REPO_ROOT)} wrapper")
    assert not offenders, (
        "nested Claude command namespace is unreachable from Cursor — re-run "
        "scripts/sync-awos-cursor-commands.sh:\n  " + "\n  ".join(offenders)
    )


# ─── Property 2: top-level commands need no Cursor duplicate ───────────


def test_top_level_claude_commands_have_no_redundant_cursor_duplicate():
    # @regression
    # Cursor reads top-level `.claude/commands/*.md` directly, so a same-named
    # `.cursor/commands/` file is a second copy to keep in sync for nothing.
    offenders: list[str] = []
    for p in _top_level_claude_commands():
        if p.stem in REDUNDANT_CURSOR_DUPLICATES:
            assert REDUNDANT_CURSOR_DUPLICATES[p.stem].strip(), (
                f"REDUNDANT_CURSOR_DUPLICATES[{p.stem!r}] must carry a non-empty reason"
            )
            continue
        duplicate = CURSOR_CMDS / f"{p.stem}.md"
        if duplicate.is_file():
            offenders.append(
                f"{duplicate.relative_to(REPO_ROOT)} duplicates {p.relative_to(REPO_ROOT)}, "
                "which Cursor already loads"
            )
    assert not offenders, (
        "redundant Cursor copy of a top-level Claude command (delete it, or add a "
        "reason to REDUNDANT_CURSOR_DUPLICATES):\n  " + "\n  ".join(offenders)
    )


# ─── Property 3: removed commands stay removed ─────────────────────────


def test_removed_commands_do_not_exist_on_claude_side():
    # @regression
    offenders = [name for name in REMOVED_COMMAND_NAMES if (CLAUDE_CMDS / f"{name}.md").is_file()]
    assert not offenders, "removed command(s) reappeared under .claude/commands/: " + ", ".join(offenders)


def test_removed_commands_unreferenced_as_invocable_in_live_docs():
    # @regression
    offenders: list[str] = []
    for doc in LIVE_DOCS:
        if not doc.is_file():
            continue
        text = doc.read_text(encoding="utf-8")
        for pattern in REMOVED_COMMAND_PATTERNS:
            if pattern.search(text):
                offenders.append(f"{doc.relative_to(REPO_ROOT)}: still references {pattern.pattern!r}")
    assert not offenders, "removed command referenced as if still invocable:\n  " + "\n  ".join(offenders)
