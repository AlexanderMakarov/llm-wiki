"""Guardrail: every `/wiki-*` slash command that wraps a CLI subcommand
must stay aligned with the CLI surface (#279).

Context: users reach for `/wiki-candidates` inside Claude Code and the
slash file is supposed to dispatch `python3 -m llmwiki candidates …`.
If the CLI grows a new flag, or a slash gets renamed, the two surfaces
can drift silently.  These tests pin the contract:

* Every `.claude/commands/wiki-*.md` that wraps a CLI subcommand
  references the correct ``python3 -m llmwiki <subcommand>`` name.
* Every CLI subcommand the slash wraps exists in ``build_parser()``.
* Slash-command file names must start with ``wiki-`` for the pipeline.
* The subcommand the slash wraps is inferred from its first fenced
  bash block — if none, the test reminds the author to add one.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SLASH_DIR = REPO_ROOT / ".claude" / "commands"

# Slashes that are pure prompts / orchestration (no CLI subcommand to
# match). Listing them explicitly so future authors can't accidentally
# skip the parity check for a real wrapper.
NON_WRAPPER_SLASHES = {
    "wiki-ingest",     # prompt-driven ingest workflow
    "wiki-query",      # model-orchestrated query workflow
    "wiki-reflect",    # higher-order self-reflection, no single CLI
    "wiki-sync",       # bundles multiple CLI calls
    "wiki-update",     # in-place surgical edit
    "wiki-lint",       # prompt-driven grep workflow per CLAUDE.md
    "maintainer",      # loader skill, not a CLI wrapper
    "release",         # orchestration
    "review-pr",       # prompt-driven
    "triage-issue",    # prompt-driven
}

# Slash files whose CLI subcommand was removed. They're excluded from
# both wrapper-parity and non-wrapper-parity checks.
LEGACY_SLASH_FILES = {
    "wiki-export-marp",  # export-marp CLI subcommand removed
}


def _cli_subcommands() -> set[str]:
    from llmwiki.cli import build_parser
    parser = build_parser()
    for a in parser._actions:
        if hasattr(a, "choices") and a.choices:
            return set(a.choices.keys())
    raise AssertionError("couldn't find subparsers in build_parser()")


def _wrapped_subcommand(slash_file: Path) -> str | None:
    """Return the CLI subcommand a slash file wraps, or ``None``."""
    text = slash_file.read_text(encoding="utf-8")
    # Pull the first ``python3 -m llmwiki <subcommand>`` reference.
    m = re.search(r"python3\s+-m\s+llmwiki\s+([a-z][a-z0-9_-]*)", text)
    return m.group(1) if m else None


def _all_slash_files() -> list[Path]:
    if not SLASH_DIR.is_dir():
        return []
    return sorted(
        p for p in SLASH_DIR.glob("*.md")
        if p.stem not in {"README"}
    )


# ─── Existence + naming ─────────────────────────────────────────────────


def test_slash_dir_exists():
    assert SLASH_DIR.is_dir(), f"missing {SLASH_DIR.relative_to(REPO_ROOT)}"


def test_every_slash_has_wiki_prefix_or_is_governance():
    governance = {"maintainer", "release", "review-pr", "triage-issue"}
    for p in _all_slash_files():
        assert p.stem.startswith("wiki-") or p.stem in governance, (
            f"slash file {p.name!r} must either start with 'wiki-' or be a "
            "known governance command"
        )


# ─── CLI parity per wrapper ─────────────────────────────────────────────


def test_every_wrapper_slash_points_at_a_real_subcommand():
    cli = _cli_subcommands()
    offenders: list[str] = []
    for p in _all_slash_files():
        if p.stem in NON_WRAPPER_SLASHES | LEGACY_SLASH_FILES:
            continue
        sub = _wrapped_subcommand(p)
        if sub is None:
            offenders.append(f"{p.name}: no `python3 -m llmwiki <sub>` in body")
            continue
        if sub not in cli:
            offenders.append(
                f"{p.name}: wraps `{sub}` which isn't a real CLI subcommand "
                f"(known: {sorted(cli)})"
            )
    assert not offenders, "slash-CLI parity drift:\n  " + "\n  ".join(offenders)


def test_wrapper_slash_name_matches_cli_subcommand():
    """``/wiki-candidates`` must wrap ``candidates``, ``/wiki-lint`` must
    wrap ``lint``, etc. Prevents confusing mismatches like the old
    ``/wiki-review`` → ``candidates`` split that we fixed in #272."""
    mismatches: list[str] = []
    for p in _all_slash_files():
        if p.stem in NON_WRAPPER_SLASHES | LEGACY_SLASH_FILES:
            continue
        sub = _wrapped_subcommand(p)
        if sub is None:
            continue
        expected_prefix = f"wiki-{sub}"
        if p.stem != expected_prefix:
            mismatches.append(
                f"{p.name} wraps `{sub}` but should be named {expected_prefix}.md"
            )
    assert not mismatches, (
        "slash filename ↔ CLI subcommand mismatch:\n  "
        + "\n  ".join(mismatches)
    )


# ─── Content quality ───────────────────────────────────────────────────


def test_every_wrapper_slash_has_at_least_one_bash_example():
    offenders: list[str] = []
    for p in _all_slash_files():
        if p.stem in NON_WRAPPER_SLASHES | LEGACY_SLASH_FILES:
            continue
        text = p.read_text(encoding="utf-8")
        if "```" not in text and "python3" not in text:
            offenders.append(p.name)
    assert not offenders, (
        "wrapper slash files missing a code example:\n  "
        + "\n  ".join(offenders)
    )


def test_known_wrappers_match_expected_set():
    """Canonical wrappers — if this list drifts, update both sides."""
    expected = {
        "wiki-build": "build",
        "wiki-candidates": "candidates",
        "wiki-graph": "graph",
        "wiki-init": "init",
        "wiki-serve": "serve",
    }
    for slash_stem, cli_sub in expected.items():
        p = SLASH_DIR / f"{slash_stem}.md"
        assert p.is_file(), f"missing slash file: {p.name}"
        wrapped = _wrapped_subcommand(p)
        assert wrapped == cli_sub, (
            f"{p.name} wraps `{wrapped}` but expected `{cli_sub}`"
        )


# ─── Non-wrapper guard ─────────────────────────────────────────────────


def test_non_wrapper_slashes_dont_claim_to_wrap_cli():
    """If you add `python3 -m llmwiki ...` to a prompt-driven slash, it
    must either wrap that subcommand correctly OR drop the CLI mention.
    Prevents "confusing by having a CLI line that's actually a hint,
    not the implementation" drift."""
    cli = _cli_subcommands()
    for stem in NON_WRAPPER_SLASHES:
        p = SLASH_DIR / f"{stem}.md"
        if not p.is_file():
            continue
        sub = _wrapped_subcommand(p)
        if sub is None:
            continue
        # It mentioned a CLI — it must at least be a real one.
        assert sub in cli, (
            f"{p.name} mentions non-existent CLI subcommand {sub!r}"
        )
