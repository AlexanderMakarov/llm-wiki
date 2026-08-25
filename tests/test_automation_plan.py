"""Tests for the automation plan vocabulary: command, label, status round-trip."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from llmwiki.automation_plan import (
    DEFAULT_SCHEDULE,
    LEGACY_PROFILE_MAP,
    AutomationPlan,
    plan_command,
    plan_from_status,
    plan_label,
    plan_to_status,
    schedule_from_status,
    spends_tokens,
)

WORKING_DIR = Path("/srv/wiki")
PYTHON_BIN = "python3"
PREFIX = "cd /srv/wiki && python3 -m llmwiki"

ALL_PLANS = [
    AutomationPlan(job=job, graph=graph, lint_fail=lint_fail)
    for job in ("ingest", "maintain")
    for graph in ("none", "builtin", "graphify")
    for lint_fail in ("never", "errors", "warnings")
]


def command(plan: AutomationPlan) -> str:
    return plan_command(plan, python_bin=PYTHON_BIN, working_dir=WORKING_DIR)


@pytest.mark.parametrize(
    ("plan", "expected"),
    [
        (AutomationPlan(), f"{PREFIX} sync"),
        (AutomationPlan(job="ingest"), f"{PREFIX} sync"),
        (AutomationPlan(job="maintain"), f"{PREFIX} all --skip-graph"),
        (AutomationPlan(job="maintain", graph="none"), f"{PREFIX} all --skip-graph"),
        (AutomationPlan(job="maintain", graph="builtin"), f"{PREFIX} all --graph-engine builtin"),
        (AutomationPlan(job="maintain", graph="graphify"), f"{PREFIX} all --graph-engine graphify"),
        (AutomationPlan(job="maintain", lint_fail="errors"), f"{PREFIX} all --skip-graph --lint-fail errors"),
        (AutomationPlan(job="maintain", lint_fail="warnings"), f"{PREFIX} all --skip-graph --lint-fail warnings"),
        (
            AutomationPlan(job="maintain", graph="builtin", lint_fail="errors"),
            f"{PREFIX} all --graph-engine builtin --lint-fail errors",
        ),
        (
            AutomationPlan(job="maintain", graph="graphify", lint_fail="warnings"),
            f"{PREFIX} all --graph-engine graphify --lint-fail warnings",
        ),
    ],
)
def test_plan_command_exact_string(plan: AutomationPlan, expected: str):
    assert command(plan) == expected


def test_ingest_command_matches_legacy_profile_a_literal():
    """R7 regression guard: the ingest line is byte-for-byte the old profile-A line."""
    assert command(AutomationPlan(job="ingest")) == "cd /srv/wiki && python3 -m llmwiki sync"


def test_plan_command_quotes_paths_with_spaces():
    cmd = plan_command(AutomationPlan(), python_bin="/opt/py 3/bin/python", working_dir=Path("/srv/my wiki"))
    assert cmd == "cd '/srv/my wiki' && '/opt/py 3/bin/python' -m llmwiki sync"


def test_ingest_command_ignores_graph_and_lint_choices():
    plan = AutomationPlan(job="ingest", graph="graphify", lint_fail="warnings")
    assert command(plan) == f"{PREFIX} sync"


@pytest.mark.parametrize(
    ("plan", "expected"),
    [
        (AutomationPlan(), "Ingest only"),
        (AutomationPlan(job="maintain"), "Maintain"),
        (AutomationPlan(job="maintain", graph="builtin"), "Maintain + graph (built-in)"),
        (AutomationPlan(job="maintain", graph="graphify"), "Maintain + graph (graphify)"),
        (AutomationPlan(job="maintain", lint_fail="errors"), "Maintain + fail on errors"),
        (AutomationPlan(job="maintain", lint_fail="warnings"), "Maintain + fail on warnings"),
        (
            AutomationPlan(job="maintain", graph="builtin", lint_fail="warnings"),
            "Maintain + graph (built-in) + fail on warnings",
        ),
    ],
)
def test_plan_label(plan: AutomationPlan, expected: str):
    assert plan_label(plan) == expected


@pytest.mark.parametrize("plan", ALL_PLANS)
def test_plan_label_is_never_a_bare_letter(plan: AutomationPlan):
    label = plan_label(plan)
    assert label not in set(LEGACY_PROFILE_MAP)
    assert len(label) > 1
    assert label[0].isupper()


@pytest.mark.parametrize("plan", ALL_PLANS)
def test_spends_tokens_follows_the_job(plan: AutomationPlan):
    assert spends_tokens(plan) is (plan.job == "maintain")


@pytest.mark.parametrize("plan", ALL_PLANS)
def test_status_round_trip(plan: AutomationPlan):
    assert plan_from_status(plan_to_status(plan)) == plan


def test_plan_to_status_keys():
    status = plan_to_status(AutomationPlan(job="maintain", graph="builtin", lint_fail="errors"))
    assert status == {
        "job": "maintain",
        "graph": "builtin",
        "lint_fail": "errors",
        "label": "Maintain + graph (built-in) + fail on errors",
        "profile": "B",
    }


def test_plan_to_status_writes_legacy_letter_a_for_ingest():
    assert plan_to_status(AutomationPlan())["profile"] == "A"


@pytest.mark.parametrize(
    ("letter", "expected_job"),
    [("A", "ingest"), ("B", "maintain"), ("C", "maintain")],
)
def test_plan_from_legacy_profile_letter(letter: str, expected_job: str):
    plan = plan_from_status({"profile": letter, "hour": 8, "minute": 0})
    assert plan.job == expected_job
    assert plan.graph == "none"
    assert plan.lint_fail == "never"


@pytest.mark.parametrize(
    "status",
    [
        {"profile": "Z"},
        {"profile": None},
        {"hour": 8, "minute": 0},
        {},
        {"job": "not-a-job"},
        "not a dict",
        None,
    ],
)
def test_plan_from_status_falls_back_to_ingest_without_raising(status: object):
    assert plan_from_status(status) == AutomationPlan()


def test_plan_from_status_prefers_job_over_legacy_letter():
    plan = plan_from_status({"job": "maintain", "graph": "graphify", "lint_fail": "errors", "profile": "A"})
    assert plan == AutomationPlan(job="maintain", graph="graphify", lint_fail="errors")


def test_plan_from_status_ignores_unknown_graph_and_lint_values():
    plan = plan_from_status({"job": "maintain", "graph": "neo4j", "lint_fail": "always"})
    assert plan == AutomationPlan(job="maintain")


def test_legacy_profile_map_is_the_only_letter_vocabulary():
    assert set(LEGACY_PROFILE_MAP) == {"A", "B", "C"}
    assert LEGACY_PROFILE_MAP["B"] == LEGACY_PROFILE_MAP["C"]


def test_schedule_from_legacy_hour_and_minute():
    assert schedule_from_status({"profile": "A", "hour": 8, "minute": 0}) == "0 8 * * *"
    assert schedule_from_status({"hour": 21, "minute": 30}) == "30 21 * * *"


def test_schedule_key_wins_over_legacy_integers():
    status = {"schedule": "0 8 * * 1-5", "hour": 8, "minute": 0}
    assert schedule_from_status(status) == "0 8 * * 1-5"


@pytest.mark.parametrize(
    "status",
    [{}, {"schedule": "  "}, {"hour": "eight"}, {"hour": 99, "minute": -1}, None],
)
def test_schedule_from_status_falls_back_to_the_default(status: object):
    assert schedule_from_status(status) == DEFAULT_SCHEDULE


def test_automation_plan_is_frozen():
    plan = AutomationPlan()
    with pytest.raises(FrozenInstanceError):
        plan.job = "maintain"  # type: ignore[misc]
