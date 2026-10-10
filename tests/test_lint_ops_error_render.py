"""Home ``ops.last_lint_error`` shows the findings that tripped the fail policy.

Relevant to #256: the note used to truncate the alphabetical console report,
so early ``content_freshness`` warnings filled the visible lines and the
errors behind ``--lint-fail errors`` never appeared.

# @spec: 234-home-timeline-automation-stamps
# @spec: 256-lint-banner-errors
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from llmwiki import cli, pipeline
from llmwiki.cli import build_parser
from llmwiki.lint import LintOutcome
from llmwiki.lint.report import render_ops_error, render_text
from llmwiki.state_store import (
    configure_state_file,
    default_state,
    read_state,
    write_state,
)


def _issue(rule: str, severity: str, page: str, message: str = "bad") -> dict:
    return {"rule": rule, "severity": severity, "page": page, "message": message}


def _mixed_outcome() -> LintOutcome:
    """Alphabetically early warnings and info ahead of a late error rule."""
    issues = [
        *(_issue("content_freshness", "warning", f"sources/S{i}.md", "stale") for i in range(8)),
        _issue("broken_wikilink", "info", "entities/A.md", "hint"),
        _issue("page_findability", "error", "entities/Lost.md", "not findable"),
        _issue("orphan_page", "warning", "concepts/Alone.md", "no inbound links"),
    ]
    rules = ["broken_wikilink", "content_freshness", "orphan_page", "page_findability"]
    return LintOutcome(issues=issues, ran=rules, considered=rules)


def test_fail_on_errors_shows_only_errors_not_earlier_warnings():
    """# @layer: unit"""
    text = render_ops_error(_mixed_outcome(), 12, fail_on="errors")

    assert "## page_findability (1)" in text
    assert "  [error] entities/Lost.md: not findable" in text
    assert "content_freshness" not in text
    assert "[warning]" not in text
    assert "[info]" not in text
    assert text.splitlines()[:2] == [
        "  scanned 12 pages",
        "  11 issues: 1 errors, 9 warnings, 1 info",
    ]


def test_fail_on_warnings_orders_errors_before_warnings_and_omits_info():
    """# @layer: unit"""
    text = render_ops_error(_mixed_outcome(), 12, fail_on="warnings")
    lines = text.splitlines()

    headers = [ln for ln in lines if ln.startswith("## ")]
    assert headers == [
        "## page_findability (1)",
        "## content_freshness (8)",
        "## orphan_page (1)",
    ]
    assert "broken_wikilink" not in text


def test_note_is_not_truncated_in_python():
    """Home JS limits the displayed lines; the stored note keeps every finding.

    # @layer: unit
    """
    lines = render_ops_error(_mixed_outcome(), 12, fail_on="warnings").split("\n")

    assert len(lines) > 10
    assert "…" not in lines
    assert lines[-1] == "  [warning] concepts/Alone.md: no inbound links"


def test_skipped_rules_block_is_not_rendered():
    """# @layer: unit"""
    base = _mixed_outcome()
    outcome = LintOutcome(
        issues=base.issues,
        skipped={"alpha": "off", "beta": "off"},
        ran=base.ran,
        considered=[*base.considered, "alpha", "beta"],
    )

    assert "skipped 2 of 6" in render_text(outcome, 12)
    assert "skipped" not in render_ops_error(outcome, 12, fail_on="errors")


def _vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "wiki").mkdir(parents=True)
    configure_state_file(vault)
    write_state(default_state(), vault / "llmwiki-state.json")
    return vault


def _assert_errors_first_note(state_file: Path) -> None:
    ops = read_state(state_file)["ops"]
    assert ops["last_lint_status"] == "failed"
    assert "page_findability" in ops["last_lint_error"]
    assert "[error]" in ops["last_lint_error"]
    assert "content_freshness" not in ops["last_lint_error"]
    # The full console report backs Home's "Linter output" section.
    assert "## content_freshness (8)" in ops["last_lint_report"]
    assert "## page_findability (1)" in ops["last_lint_report"]


def _many_errors_outcome() -> LintOutcome:
    issues = [_issue("page_findability", "error", f"entities/E{i}.md") for i in range(11)]
    return LintOutcome(issues=issues, ran=["page_findability"], considered=["page_findability"])


def test_cmd_lint_fail_on_errors_stores_errors_first_note(tmp_path: Path, capsys):
    """``lint --fail-on-errors`` stores the error; the console keeps the full report.

    # @layer: unit
    """
    vault = _vault(tmp_path)
    args = build_parser().parse_args(["lint", "--vault", str(vault), "--fail-on-errors"])

    with (
        patch.object(cli, "load_pages", return_value=[object()] * 12),
        patch.object(cli, "run_lint", return_value=_mixed_outcome()),
    ):
        rc = cli.cmd_lint(args)

    assert rc == 1
    assert "## content_freshness (8)" in capsys.readouterr().out
    _assert_errors_first_note(vault / "llmwiki-state.json")


def test_lint_step_stores_errors_first_note(tmp_path: Path):
    """Pipeline lint under ``errors`` stores the error, not the early warnings.

    # @layer: unit
    """
    vault = _vault(tmp_path)

    with (
        patch.object(pipeline, "load_pages", return_value=[object()] * 12),
        patch.object(pipeline, "run_lint", return_value=_mixed_outcome()),
    ):
        rc, summary = pipeline._run_lint_step(vault / "wiki", lint_fail="errors")

    assert rc == 0
    assert summary["error"] == 1
    _assert_errors_first_note(vault / "llmwiki-state.json")


def test_stored_note_can_exceed_ten_lines(tmp_path: Path):
    """Python stores the whole selected note; only Home JS shortens what it shows.

    # @layer: unit
    """
    vault = _vault(tmp_path)

    with (
        patch.object(pipeline, "load_pages", return_value=[object()] * 12),
        patch.object(pipeline, "run_lint", return_value=_many_errors_outcome()),
    ):
        pipeline._run_lint_step(vault / "wiki", lint_fail="errors")

    note = read_state(vault / "llmwiki-state.json")["ops"]["last_lint_error"]
    assert len(note.split("\n")) > 10
    assert "entities/E10.md" in note
    assert "…" not in note
