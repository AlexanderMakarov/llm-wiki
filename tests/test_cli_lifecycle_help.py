"""Top-level and key-subcommand help as a lifecycle map.

@spec: 199-cli-lifecycle-help
"""

from __future__ import annotations

import re

from llmwiki.cli import build_parser

# Headings from functional-spec R1 — exact strings as printed in --help.
_LIFECYCLE_HEADINGS = (
    "Start here",
    "Daily loop (this order)",
    "Run the loop for me",
    "Look around",
    "Take things out",
    "Rare — one-time",
)


def _root_parser():
    return build_parser()


def _subparsers(parser):
    for action in parser._actions:
        if hasattr(action, "choices") and isinstance(action.choices, dict):
            return action.choices
    raise AssertionError("could not locate subparsers on build_parser()")


def _name_count(text: str, name: str) -> int:
    """Word-boundary count; hyphens stay part of the token (configure-sources)."""
    return len(re.findall(rf"(?<![\w-]){re.escape(name)}(?![\w-])", text))


def test_root_help_contains_six_lifecycle_headings():
    help_text = _root_parser().format_help()
    for heading in _LIFECYCLE_HEADINGS:
        assert heading in help_text, f"missing lifecycle heading: {heading!r}"


def test_root_help_epilog_states_canonical_loop_and_synth_non_rebuild():
    help_text = _root_parser().format_help()
    assert "Canonical loop:" in help_text
    assert "ingest" in help_text
    assert "synth" in help_text
    assert "build" in help_text
    assert "Rebuild the site afterwards so candidates and analytics stay current" in help_text or (
        "rebuild the site so candidates and analytics stay current" in help_text
    )


def test_every_live_subcommand_appears_exactly_once_in_root_description():
    parser = _root_parser()
    description = parser.description or ""
    choices = _subparsers(parser)
    for name in choices:
        count = _name_count(description, name)
        assert count == 1, (
            f"{name!r} appears {count} time(s) in root description; expected exactly 1"
        )


def test_top_level_help_has_no_issue_numbers():
    help_text = _root_parser().format_help()
    hits = re.findall(r"#\d+", help_text)
    assert not hits, f"top-level help must not contain issue numbers: {hits}"


def test_synth_help_covers_review_then_build_and_no_site_rebuild():
    help_text = _subparsers(_root_parser())["synth"].format_help()
    assert "wiki/candidates/" in help_text
    assert "rebuild the site afterwards so candidates and analytics stay current" in help_text.lower() or (
        "Rebuild the site afterwards so candidates and analytics stay current" in help_text
    )
    assert "candidates command" in help_text.lower() or "candidates command" in help_text


def test_candidates_help_covers_after_synth_and_rebuild_sync():
    help_text = _subparsers(_root_parser())["candidates"].format_help()
    assert "Runs after synth" in help_text
    assert "Candidates page in sync" in help_text
    assert "--no-rebuild" in help_text


def test_queue_help_covers_deferred_work_and_daily_loop_opt_out():
    help_text = _subparsers(_root_parser())["queue"].format_help()
    assert "deferred" in help_text.lower()
    assert "Most people never need this command" in help_text
    assert "sync" in help_text and "synth" in help_text and "build" in help_text
    assert "all" in help_text


def test_all_help_covers_full_pipeline_and_skippable_stages():
    help_text = _subparsers(_root_parser())["all"].format_help()
    assert "full pipeline" in help_text.lower()
    assert "Skip stages" in help_text


def test_migrate_help_covers_list_vs_apply_and_registration():
    help_text = _subparsers(_root_parser())["migrate"].format_help()
    assert "llmwiki migrate --list" in help_text or "migrate --list" in help_text
    assert "Nothing is applied until you choose a name" in help_text
    assert "Does not run sync, synth, build" in help_text
    assert "New migrations are registered here" not in help_text
