"""The published demo is held to an enforced gate at stock settings (#150, R8).

CI used to run ``lint --vault demo --fail-on-errors`` and let every
warning-severity finding scroll past, because ``content_freshness`` asks "has
this page gone untouched for three months?" and the demo is a committed
snapshot — the answer turns true on a calendar date rather than on a defect.

``demo/llmwiki.json`` now declares that one check as not applicable, with a
written reason, and the workflow enforces warnings. The substance of that
change is the four guarantees below:

* the committed demo passes the enforced gate today;
* the report says out loud which check was skipped, and why;
* a real warning-severity defect still stops the gate;
* moving the clock past the staleness threshold does not — which is the whole
  reason the opt-out exists.

The demo declares nothing else. A ``min_refs`` override would make the one
published example the vault nobody's setup resembles, so the threshold stays
stock and is pinned as such here.
"""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from llmwiki import REPO_ROOT
from llmwiki.cli import build_parser
from llmwiki.lint import load_pages, run_lint
from llmwiki.lint import rules as _rules  # noqa: F401 — populate REGISTRY
from llmwiki.vault_settings import (
    VAULT_SETTINGS_FILENAME,
    disabled_lint_rules,
    load_vault_settings,
)

DEMO = REPO_ROOT / "demo"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "wiki-checks.yml"

#: Comfortably past ``ContentFreshness.STALE_DAYS`` for every committed page.
_WELL_PAST_STALE = timedelta(days=400)


def _gate(vault: Path) -> int:
    """Run exactly the command the workflow runs, against ``vault``."""
    args = build_parser().parse_args([
        "lint", "--vault", str(vault), "--fail-on-errors", "--fail-on-warnings",
    ])
    return args.func(args)


@pytest.fixture
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> datetime:
    """Move ``content_freshness``'s idea of "now" well past the threshold.

    Faking time is the only honest way to test this: editing the demo's dates
    would change the published example to suit its own test.
    """
    shifted = datetime.now(UTC) + _WELL_PAST_STALE

    class _Frozen(datetime):
        @classmethod
        def now(cls, tz=None):  # noqa: ANN001, ANN206 — mirrors datetime.now
            return shifted if tz is None else shifted.astimezone(tz)

    monkeypatch.setattr("llmwiki.lint.rules.content_freshness.datetime", _Frozen)
    return shifted


# ─── The declaration itself ──────────────────────────────────────────────


def test_demo_carries_a_committed_settings_file() -> None:
    path = DEMO / VAULT_SETTINGS_FILENAME
    assert path.is_file(), "the demo's opt-out must travel with the vault"
    json.loads(path.read_text(encoding="utf-8"))


def test_demo_disables_content_freshness_and_nothing_else() -> None:
    disabled = disabled_lint_rules(load_vault_settings(DEMO))
    assert list(disabled) == ["content_freshness"]


def test_the_opt_out_records_why() -> None:
    """R1/R2: a silenced check carries a reason a reviewer can weigh."""
    reason = disabled_lint_rules(load_vault_settings(DEMO))["content_freshness"]
    assert "snapshot" in reason.lower()
    assert reason.strip()


def test_demo_overrides_no_other_setting() -> None:
    """Stock settings, deliberately — a demo that configures things is not one."""
    settings = load_vault_settings(DEMO)
    assert set(settings) == {"lint"}
    assert set(settings["lint"]) == {"disabled_rules"}
    assert "min_refs" not in json.dumps(settings)


# ─── The gate ────────────────────────────────────────────────────────────


def test_committed_demo_passes_the_enforced_gate(capsys: pytest.CaptureFixture) -> None:
    assert _gate(DEMO) == 0
    capsys.readouterr()


def test_the_gate_report_names_the_skipped_check(capsys: pytest.CaptureFixture) -> None:
    """R2: a clean result must never read as "almost nothing was checked"."""
    _gate(DEMO)
    out = capsys.readouterr().out
    assert "content_freshness" in out
    reason = disabled_lint_rules(load_vault_settings(DEMO))["content_freshness"]
    assert reason in out


def test_a_real_warning_severity_defect_still_stops_the_gate(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """R8: enforcement is worth having only if something can still fail it.

    The seeded target is named by ``DEFAULT_MIN_REFS`` source pages, so it
    clears the stock significance threshold: this is a genuine gap the demo
    should have a page for, not a deliberate harvest decline.
    """
    copy = tmp_path / "demo-copy"
    copy.mkdir()
    shutil.copytree(DEMO / "wiki", copy / "wiki")
    shutil.copy2(DEMO / VAULT_SETTINGS_FILENAME, copy / VAULT_SETTINGS_FILENAME)

    seeded = sorted((copy / "wiki" / "sources").rglob("*.md"))[:3]
    assert len(seeded) == 3
    for page in seeded:
        page.write_text(
            page.read_text(encoding="utf-8") + "\n- [[GhostTopic]] — seeded gap\n",
            encoding="utf-8",
        )

    assert _gate(copy) == 1
    out = capsys.readouterr().out
    assert "GhostTopic" in out


# ─── The opt-out earns its keep ──────────────────────────────────────────


def test_demo_still_passes_when_the_clock_moves_past_the_threshold(
    frozen_clock: datetime, capsys: pytest.CaptureFixture
) -> None:
    """R8: the example must not redden on a calendar date."""
    assert _gate(DEMO) == 0
    capsys.readouterr()


def test_without_the_opt_out_the_moved_clock_would_have_failed_it(
    frozen_clock: datetime,
) -> None:
    """The control: prove the previous test is the opt-out working, not luck.

    Run the same rule against the same pages with nothing disabled and the
    demo is wall-to-wall stale — which is exactly the finding the enforced
    gate would trip on if the declaration were removed.
    """
    outcome = run_lint(load_pages(DEMO / "wiki"), selected=["content_freshness"])
    assert outcome.ran == ["content_freshness"]
    assert outcome.issues, "the frozen clock should have aged every dated page"
    assert all(i["severity"] == "warning" for i in outcome.issues)


# ─── The workflow that runs it ───────────────────────────────────────────


def test_workflow_enforces_warnings_alongside_errors() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "--fail-on-errors --fail-on-warnings" in text


def test_workflow_comment_explains_the_opt_out_that_allows_enforcement() -> None:
    """The old comment justified withholding enforcement; it no longer applies."""
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "--strict" not in text
    assert VAULT_SETTINGS_FILENAME in text
    assert "content_freshness" in text
