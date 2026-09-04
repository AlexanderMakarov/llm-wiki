"""Acceptance tests for #112: CLI help as a lifecycle map.

Covers functional-spec.md acceptance criteria R1–R6 not already tested
in tests/test_cli_lifecycle_help.py (slice-3 help assertions) or
tests/test_reference_coverage.py (doc/CLI parity).

AC coverage matrix (R<n> → test name):
    R1  → test_no_migrate_star_at_top_level
    R3  → test_synthesize_and_consolidate_absent_from_choices
    R4  → test_migrate_no_args_prints_catalog
    R4  → test_migrate_list_flag_prints_same_catalog_as_bare_migrate
    R4  → test_migrate_list_and_name_together_is_error
    R4  → test_migrate_catalog_contains_six_expected_names
    R4  → test_migrate_subparsers_register_six_names
    R5  → test_agents_md_contains_register_under_migrate_rule
    R5  → test_claude_md_contains_register_under_migrate_rule

# @layer: unit
# @spec: 199-cli-lifecycle-help
# @regression
"""

from __future__ import annotations

import argparse
import io
import sys

import pytest

from llmwiki import REPO_ROOT
from llmwiki.cli import _MIGRATIONS, build_parser, cmd_migrate

# ─── helpers ────────────────────────────────────────────────────────────────


def _subparser_choices(parser: argparse.ArgumentParser) -> dict[str, argparse.ArgumentParser]:
    for action in parser._actions:
        if hasattr(action, "choices") and isinstance(action.choices, dict):
            return action.choices
    raise AssertionError("could not locate subparsers on build_parser()")


def _call_migrate(migration: str | None = None, list_migrations: bool = False) -> tuple[int, str, str]:
    """Call cmd_migrate with fabricated Namespace; return (rc, stdout, stderr)."""
    ns = argparse.Namespace(migration=migration, list_migrations=list_migrations)
    out_buf, err_buf = io.StringIO(), io.StringIO()
    old_stdout, old_stderr = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = out_buf, err_buf
    try:
        rc = cmd_migrate(ns)
    finally:
        sys.stdout, sys.stderr = old_stdout, old_stderr
    return rc, out_buf.getvalue(), err_buf.getvalue()


# ─── R1 — no migrate-* at top level ─────────────────────────────────────────


def test_no_migrate_star_at_top_level():
    """R1-AC: every migrate-* command must be gone from the top-level registry.

    The six old top-level names must not appear as subparser choices.
    """
    dead_top_level = {
        "migrate-state",
        "migrate-raw-redaction",
        "migrate-tools-used",
        "migrate-page-kinds",
        "migrate-topic-kinds",
        "migrate-broken-provenance",
    }
    choices = set(_subparser_choices(build_parser()).keys())
    found = dead_top_level & choices
    assert not found, (
        f"These migrate-* names must not be top-level commands: {sorted(found)}"
    )


# ─── R3 — dead commands removed ─────────────────────────────────────────────


def test_synthesize_and_consolidate_absent_from_choices():
    """R3-AC: removed commands synthesize and consolidate-topics must not be registered."""
    choices = set(_subparser_choices(build_parser()).keys())
    for dead_name in ("synthesize", "consolidate-topics"):
        assert dead_name not in choices, (
            f"'{dead_name}' must not appear in the live command registry"
        )


# ─── R4 — migrate list vs apply ─────────────────────────────────────────────


def test_migrate_no_args_prints_catalog():
    """R4-AC: bare `llmwiki migrate` prints the catalog; nothing is written to disk."""
    rc, stdout, _stderr = _call_migrate(migration=None, list_migrations=False)
    assert rc == 0
    # The catalog must contain every migration name.
    for name, _purpose, _when in _MIGRATIONS:
        assert name in stdout, f"bare migrate: catalog missing migration '{name}'"


def test_migrate_list_flag_prints_same_catalog_as_bare_migrate():
    """R4-AC: `llmwiki migrate --list` prints the same catalog as bare migrate."""
    _, stdout_bare, _ = _call_migrate(migration=None, list_migrations=False)
    _, stdout_list, _ = _call_migrate(migration=None, list_migrations=True)
    # Both paths reach _print_migrate_catalog — output must match exactly.
    assert stdout_bare == stdout_list, (
        "migrate --list and bare migrate must print identical catalog output"
    )


def test_migrate_list_and_name_together_is_error():
    """R4-AC: --list combined with a migration name is an error (exit 2, stderr message)."""
    rc, _stdout, stderr = _call_migrate(migration="raw-redaction", list_migrations=True)
    assert rc == 2, f"expected exit 2 for --list + name, got {rc}"
    assert "--list cannot be combined" in stderr


def test_migrate_catalog_contains_six_expected_names():
    """R4-AC: the six migration names are present in _MIGRATIONS (same as today's commands)."""
    expected = {
        "state",
        "raw-redaction",
        "tools-used",
        "page-kinds",
        "topic-kinds",
        "broken-provenance",
    }
    actual = {name for name, _purpose, _when in _MIGRATIONS}
    missing = expected - actual
    extra = actual - expected
    assert not missing, f"_MIGRATIONS is missing expected names: {sorted(missing)}"
    assert not extra, f"_MIGRATIONS has unexpected extra names: {sorted(extra)}"


def test_migrate_subparsers_register_six_names():
    """R4-AC: the migrate subparser tree registers all six names (argparse level)."""
    expected = {
        "state",
        "raw-redaction",
        "tools-used",
        "page-kinds",
        "topic-kinds",
        "broken-provenance",
    }
    migrate_parser = _subparser_choices(build_parser())["migrate"]
    # Walk migrate's own sub-subparsers.
    migrate_choices: dict[str, object] = {}
    for action in migrate_parser._actions:
        if hasattr(action, "choices") and isinstance(action.choices, dict):
            migrate_choices = action.choices
            break

    registered = set(migrate_choices.keys())
    missing = expected - registered
    assert not missing, (
        f"migrate subparser missing these registered names: {sorted(missing)}"
    )
    extra = registered - expected
    assert not extra, (
        f"migrate subparser has unexpected extra names: {sorted(extra)}"
    )


@pytest.mark.parametrize("name", ["state", "raw-redaction", "tools-used", "page-kinds", "topic-kinds", "broken-provenance"])
def test_each_migration_name_help_is_parseable(name: str):
    """R4-AC: each migration sub-subparser can format its own help without error."""
    migrate_parser = _subparser_choices(build_parser())["migrate"]
    for action in migrate_parser._actions:
        if hasattr(action, "choices") and isinstance(action.choices, dict):
            sub = action.choices.get(name)
            assert sub is not None, f"migrate sub-subparser '{name}' not found"
            help_text = sub.format_help()
            assert len(help_text) > 0
            return
    pytest.fail(f"could not locate subparsers on migrate parser for '{name}'")


# ─── R5 — contributor schema files contain the rule ─────────────────────────


def test_agents_md_contains_register_under_migrate_rule():
    """R5-AC: AGENTS.md instructs contributors to add new migrations under migrate."""
    text = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "migrate" in text.lower(), "AGENTS.md should mention migrate"
    # The rule must say new migrations go into migrate, not as new top-level commands.
    assert "never" in text.lower() or "not as" in text.lower(), (
        "AGENTS.md must state that new migrations are NOT added as new top-level commands"
    )
    assert "register" in text.lower() or "add" in text.lower(), (
        "AGENTS.md must say to register new migrations under migrate"
    )


def test_claude_md_contains_register_under_migrate_rule():
    """R5-AC: CLAUDE.md instructs contributors to add new migrations under migrate."""
    text = (REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert "migrate" in text.lower(), "CLAUDE.md should mention migrate"
    assert "never" in text.lower() or "not as" in text.lower(), (
        "CLAUDE.md must state that new migrations are NOT added as new top-level commands"
    )
    assert "register" in text.lower() or "add" in text.lower(), (
        "CLAUDE.md must say to register new migrations under migrate"
    )
