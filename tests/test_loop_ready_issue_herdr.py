"""Tests for ``scripts/loop_ready_issue_herdr.py`` (#296).

# @layer: unit
# @spec: 303-loop-ready-issue-herdr
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "loop_ready_issue_herdr.py"

LABEL = "agent-ready"
LOGIN = "viewer"


@pytest.fixture(scope="module")
def loop_mod():
    spec = importlib.util.spec_from_file_location("loop_ready_issue_herdr", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _issue(
    number: int,
    *,
    state: str | None = "OPEN",
    labels: list[str | dict] | None = None,
    assignees: list[str | dict] | None = None,
) -> dict:
    out: dict = {"number": number}
    if state is not None:
        out["state"] = state
    if labels is not None:
        out["labels"] = labels
    if assignees is not None:
        out["assignees"] = assignees
    return out


def test_work_for_today_counts_open_with_label_and_assignee(loop_mod):
    issues = [
        _issue(1, labels=[LABEL], assignees=[LOGIN]),
        _issue(2, labels=[LABEL], assignees=["other"]),
        _issue(3, labels=["other"], assignees=[LOGIN]),
        _issue(4, state="CLOSED", labels=[LABEL], assignees=[LOGIN]),
        _issue(5, labels=[{"name": LABEL}], assignees=[{"login": LOGIN}]),
    ]
    with_label, assigned = loop_mod.work_for_today_counts(issues, LOGIN, LABEL)
    assert with_label == 3
    assert assigned == 2


def test_work_for_today_counts_missing_state_counts_as_open(loop_mod):
    issues = [_issue(10, state=None, labels=[LABEL], assignees=[LOGIN])]
    with_label, assigned = loop_mod.work_for_today_counts(issues, LOGIN, LABEL)
    assert with_label == 1
    assert assigned == 1


def test_candidates_assigned_filters_label_and_assignee(loop_mod):
    issues = [
        _issue(1, labels=[LABEL], assignees=[LOGIN]),
        _issue(2, labels=[LABEL], assignees=["peer"]),
        _issue(3, labels=[LABEL], assignees=[LOGIN, "peer"]),
        _issue(4, state="CLOSED", labels=[LABEL], assignees=[LOGIN]),
        _issue(5, labels=["wip"], assignees=[LOGIN]),
    ]
    got = loop_mod.candidates_assigned(issues, LOGIN, LABEL)
    assert [i["number"] for i in got] == [1, 3]


def test_eligible_after_blocked_by_drops_open_blockers_only(loop_mod):
    candidates = [_issue(100), _issue(200), _issue(300)]
    blocked_by_map = {
        100: [{"number": 99, "state": "CLOSED"}],
        200: [{"number": 1, "state": "OPEN"}],
        300: [],
    }
    eligible = loop_mod.eligible_after_blocked_by(candidates, blocked_by_map)
    assert [i["number"] for i in eligible] == [100, 300]


def test_eligible_after_blocked_by_treats_missing_blocker_state_as_open(loop_mod):
    candidates = [_issue(50)]
    blocked_by_map = {50: [{"number": 1}]}
    assert loop_mod.eligible_after_blocked_by(candidates, blocked_by_map) == []


def test_sort_key_important_before_number(loop_mod):
    low = _issue(5, labels=[LABEL])
    high = _issue(2, labels=[LABEL, "important"])
    assert loop_mod.sort_key(high) < loop_mod.sort_key(low)


def test_sort_key_ascending_number_among_same_priority(loop_mod):
    a = _issue(10, labels=[LABEL])
    b = _issue(3, labels=[LABEL])
    assert loop_mod.sort_key(a) > loop_mod.sort_key(b)


def test_pick_next_skips_blocked_and_prefers_important_then_number(loop_mod):
    candidates = [
        _issue(20, labels=[LABEL], assignees=[LOGIN]),
        _issue(5, labels=[LABEL, "important"], assignees=[LOGIN]),
        _issue(8, labels=[LABEL], assignees=[LOGIN]),
    ]
    blocked_by_map = {5: [{"number": 1, "state": "OPEN"}]}
    picked = loop_mod.pick_next(candidates, blocked_by_map)
    assert picked is not None
    assert picked["number"] == 8


def test_pick_next_returns_none_when_all_blocked(loop_mod):
    candidates = [_issue(1), _issue(2)]
    blocked_by_map = {
        1: [{"number": 9, "state": "OPEN"}],
        2: [{"number": 8, "state": "OPEN"}],
    }
    assert loop_mod.pick_next(candidates, blocked_by_map) is None


def test_pick_next_chooses_lowest_important_when_multiple(loop_mod):
    candidates = [
        _issue(30, labels=[LABEL, "important"]),
        _issue(7, labels=["important", LABEL]),
    ]
    picked = loop_mod.pick_next(candidates, {})
    assert picked is not None
    assert picked["number"] == 7


@pytest.mark.parametrize(
    ("open_tabs", "expected_choice", "expected_in_progress", "expected_warning"),
    [
        ({}, 256, [], None),
        ({311: (5, "wD:t311"), 999: (1, "wD:t999")}, 311, [311], None),
        (
            {311: (30, "wD:t311"), 400: (31, "wD:t400")},
            311,
            [311, 400],
            "WARNING: 2 eligible issues have an open issue-N tab; resuming #311 first "
            "(oldest tab); the others (#400) wait their turn and are adopted later with "
            "no new prompt.",
        ),
        (
            {256: (31, "wD:t256"), 311: (30, "wD:t311")},
            311,
            [311, 256],
            "WARNING: 2 eligible issues have an open issue-N tab; resuming #311 first "
            "(oldest tab); the others (#256) wait their turn and are adopted later with "
            "no new prompt.",
        ),
        (
            {256: (7, "wD:t9"), 311: (7, "wD:t1")},
            311,
            [311, 256],
            "WARNING: 2 eligible issues have an open issue-N tab; resuming #311 first "
            "(oldest tab); the others (#256) wait their turn and are adopted later with "
            "no new prompt.",
        ),
    ],
    ids=["none", "one", "several-queue-order", "several-tab-order", "tie-by-tab-id"],
)
def test_pick_next_resume_first_prefers_oldest_open_tab(
    loop_mod, capsys, open_tabs, expected_choice, expected_in_progress, expected_warning
):
    """In-progress (open ``issue-N`` tab) beats queue head; several resume oldest tab first."""
    planned = [_issue(256), _issue(311), _issue(400)]
    choice, in_progress = loop_mod.pick_next_resume_first(planned, open_tabs)
    assert choice is not None
    assert choice["number"] == expected_choice
    assert [i["number"] for i in in_progress] == expected_in_progress
    err = capsys.readouterr().err
    if expected_warning is None:
        assert err == ""
    else:
        assert err.strip() == expected_warning


def test_pick_next_resume_first_empty_queue_ignores_tabs(loop_mod):
    assert loop_mod.pick_next_resume_first([], {7: (1, "wD:t7")}) == (None, [])


def test_warn_ineligible_open_tabs_warns_once_per_issue(loop_mod, capsys):
    """An open tab outside the eligible queue warns once per run and never blocks it."""
    planned = [_issue(256), _issue(311)]
    warned: set[int] = set()
    loop_mod.warn_ineligible_open_tabs(planned, {311, 77}, warned)
    loop_mod.warn_ineligible_open_tabs(planned, {311, 77, 88}, warned)
    assert capsys.readouterr().err.splitlines() == [
        "WARNING: issue-77 tab open but #77 is not in the eligible queue "
        "(closed, unlabeled, unassigned, or blocked); close the tab or restore label/assignee.",
        "WARNING: issue-88 tab open but #88 is not in the eligible queue "
        "(closed, unlabeled, unassigned, or blocked); close the tab or restore label/assignee.",
    ]
    assert warned == {77, 88}


@pytest.mark.parametrize(
    ("tabs", "closed", "expected"),
    [
        pytest.param(
            [{"label": "issue-5", "tab_id": "wD:t9", "number": 7},
             {"label": "issue-5", "tab_id": "wD:t2", "number": 3}],
            None,
            {5: (3, "wD:t2")},
            id="same_issue_lower_number_wins",
        ),
        pytest.param(
            [{"label": "issue-5", "tab_id": "wD:t2", "number": 3},
             {"label": "issue-5", "tab_id": "wD:t9", "number": 7}],
            {"wD:t2"},
            {5: (7, "wD:t9")},
            id="closed_tab_excluded",
        ),
        pytest.param(
            [{"label": "issue-5", "tab_id": "wD:t1"},
             {"label": "issue-5", "tab_id": "wD:t9", "number": 7}],
            None,
            {5: (7, "wD:t9")},
            id="missing_number_sorts_after_numbered",
        ),
    ],
)
def test_open_tabs_by_issue_picks_oldest_open_tab(loop_mod, tabs, closed, expected):
    def fake_herdr(argv: list[str]) -> subprocess.CompletedProcess[str]:
        body = json.dumps({"result": {"tabs": tabs, "type": "tab_list"}})
        return subprocess.CompletedProcess(argv, 0, body, "")

    issue_tabs = loop_mod.list_issue_tabs(fake_herdr)
    assert loop_mod.open_tabs_by_issue(issue_tabs, closed) == expected


def _green_ci_check(name: str = "ci") -> dict:
    return {"name": name, "status": "completed", "conclusion": "success"}


def test_advance_ready_false_when_not_merged(loop_mod):
    merge_info = {"merged": False, "merge_commit_sha": None, "pr_number": 42}
    checks = [_green_ci_check()]
    assert loop_mod.advance_ready(merge_info, checks) is False


def test_advance_ready_false_when_merged_and_no_check_runs(loop_mod):
    assert loop_mod.advance_ready({"merged": True}, []) is False


def test_advance_ready_true_when_all_checks_completed_success(loop_mod):
    merge_info = {"merged": True, "merge_commit_sha": "abc", "pr_number": 1}
    check_runs = [
        {"name": "lint", "status": "completed", "conclusion": "success"},
        {"name": "test", "status": "COMPLETED", "conclusion": "SUCCESS"},
    ]
    assert loop_mod.advance_ready(merge_info, check_runs) is True


def test_advance_ready_false_when_check_not_completed(loop_mod):
    merge_info = {"merged": True}
    check_runs = [
        {"name": "ci", "status": "in_progress", "conclusion": None},
    ]
    assert loop_mod.advance_ready(merge_info, check_runs) is False


def test_advance_ready_false_when_check_conclusion_failure(loop_mod):
    merge_info = {"merged": True}
    check_runs = [
        {"name": "ci", "status": "completed", "conclusion": "failure"},
    ]
    assert loop_mod.advance_ready(merge_info, check_runs) is False


def test_advance_ready_false_when_check_missing_conclusion(loop_mod):
    merge_info = {"merged": True}
    check_runs = [
        {"name": "ci", "status": "completed", "conclusion": None},
    ]
    assert loop_mod.advance_ready(merge_info, check_runs) is False


def test_advance_ready_false_when_any_check_failed(loop_mod):
    merge_info = {"merged": True}
    check_runs = [
        {"name": "optional", "status": "completed", "conclusion": "failure"},
        {"name": "ci", "status": "completed", "conclusion": "success"},
    ]
    assert loop_mod.advance_ready(merge_info, check_runs) is False


def _dry_run_herdr(scenario: str):
    """Fake herdr ``tab list`` for dry-run; ``missing`` mimics herdr not on PATH."""

    def fake_herdr(argv: list[str]) -> subprocess.CompletedProcess[str]:
        assert argv[1:3] == ["tab", "list"], argv
        if scenario == "missing":
            raise FileNotFoundError(2, "No such file or directory", "herdr")
        if scenario == "error":
            body = json.dumps({"error": {"code": "boom", "message": "no socket"}})
            return subprocess.CompletedProcess(argv, 1, body, "")
        tabs = (
            [
                {"label": "issue-20", "tab_id": "wD:t20", "number": 2},
                {"label": "issue-99", "tab_id": "wD:t99", "number": 3},
                {"label": "driver", "tab_id": "wD:tD", "number": 1},
            ]
            if scenario == "in_progress"
            else [
                {"label": "issue-8", "tab_id": "wD:t8", "number": 9},
                {"label": "issue-20", "tab_id": "wD:t20", "number": 4},
            ]
            if scenario == "several"
            else []
        )
        body = json.dumps({"result": {"tabs": tabs, "type": "tab_list"}})
        return subprocess.CompletedProcess(argv, 0, body, "")

    return fake_herdr


_DRY_8 = "#8 Next eligible https://example/o/r/issues/8"
_DRY_20 = "#20 Later https://example/o/r/issues/20"


# @regression
@pytest.mark.parametrize(
    ("scenario", "expected_tail", "expected_err"),
    [
        ("no_tabs", ["planned (2):", f"  1. {_DRY_8}", f"  2. {_DRY_20}", f"next: {_DRY_8}"], ""),
        (
            "in_progress",
            [
                "planned (2):",
                f"  1. {_DRY_20} (in progress, tab open)",
                f"  2. {_DRY_8}",
                f"next: {_DRY_20}",
            ],
            "WARNING: issue-99 tab open but #99 is not in the eligible queue",
        ),
        (
            "several",
            [
                "planned (2):",
                f"  1. {_DRY_20} (in progress, tab open)",
                f"  2. {_DRY_8} (in progress, tab open)",
                f"next: {_DRY_20}",
            ],
            "resuming #20 first (oldest tab); the others (#8)",
        ),
        (
            "missing",
            [
                "in-progress: unknown (herdr unavailable: herdr not found on PATH)",
                "planned (2):",
                f"  1. {_DRY_8}",
                f"  2. {_DRY_20}",
                f"next: {_DRY_8}",
            ],
            "",
        ),
        (
            "error",
            [
                "in-progress: unknown (herdr unavailable: herdr tab list failed (boom): no socket)",
                "planned (2):",
                f"  1. {_DRY_8}",
                f"  2. {_DRY_20}",
                f"next: {_DRY_8}",
            ],
            "",
        ),
    ],
)
def test_run_dry_run_pick_next_via_fake_run_gh(
    loop_mod, capsys, scenario, expected_tail, expected_err
):
    """Dry-run lists in-progress tickets first; herdr failure falls back to queue order."""
    issues = [
        {
            "number": 20,
            "title": "Later",
            "labels": [LABEL],
            "assignees": [LOGIN],
            "url": "https://example/o/r/issues/20",
            "state": "OPEN",
        },
        {
            "number": 5,
            "title": "Blocked important",
            "labels": [LABEL, "important"],
            "assignees": [LOGIN],
            "url": "https://example/o/r/issues/5",
            "state": "OPEN",
        },
        {
            "number": 8,
            "title": "Next eligible",
            "labels": [LABEL],
            "assignees": [LOGIN],
            "url": "https://example/o/r/issues/8",
            "state": "OPEN",
        },
    ]
    graphql_payload = {
        "data": {
            "repository": {
                "issue_20": {"number": 20, "blockedBy": {"nodes": []}},
                "issue_5": {
                    "number": 5,
                    "blockedBy": {"nodes": [{"number": 1, "state": "OPEN"}]},
                },
                "issue_8": {"number": 8, "blockedBy": {"nodes": []}},
            },
        },
    }

    def fake_run_gh(argv: list[str]) -> subprocess.CompletedProcess[str]:
        cmd = argv[0] if argv else ""
        if cmd == "gh" and len(argv) > 1 and argv[1] == "api" and argv[2] == "user":
            body = json.dumps({"login": LOGIN})
        elif cmd == "gh" and "repo" in argv and "view" in argv:
            body = json.dumps({"nameWithOwner": "owner/repo"})
        elif cmd == "gh" and "issue" in argv and "list" in argv:
            body = json.dumps(issues)
        elif cmd == "gh" and argv[1:3] == ["api", "graphql"]:
            body = json.dumps(graphql_payload)
        else:
            raise AssertionError(f"unexpected gh argv: {argv}")
        return subprocess.CompletedProcess(argv, 0, body, "")

    lines = loop_mod.run_dry_run(
        LABEL, "owner/repo", run_gh=fake_run_gh, run_herdr=_dry_run_herdr(scenario)
    )
    # #5 is absent: blocked by an open blocker.
    assert lines == [
        "repo: owner/repo",
        "herdr workspace: unscoped",
        "3 with 'agent-ready' label, 3 is assigned on 'viewer'",
        *expected_tail,
    ]
    err = capsys.readouterr().err
    if expected_err:
        assert expected_err in err
    else:
        assert err == ""


def test_close_worker_tab_closes_even_when_agent_gone(loop_mod):
    """``gone`` skips agent wait only — advance must still close the tab."""
    calls: list[list[str]] = []

    def fake_herdr(argv: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(list(argv))
        if argv[1:3] == ["tab", "close"]:
            return subprocess.CompletedProcess(
                argv, 0, json.dumps({"result": {"type": "ok"}}), ""
            )
        if argv[1:3] == ["tab", "list"]:
            return subprocess.CompletedProcess(
                argv,
                0,
                json.dumps({"result": {"tabs": [], "type": "tab_list"}}),
                "",
            )
        raise AssertionError(argv)

    worker = loop_mod.WorkerHandle(
        tab_id="wD:tK",
        pane_id="wD:pK",
        issue_number=305,
        issue_url="https://example/305",
        gone=True,
    )
    loop_mod.close_worker_tab(worker, run_herdr=fake_herdr)
    assert ["herdr", "tab", "close", "wD:tK"] in calls


def _adopt_fake_herdr(calls: list[list[str]], tabs: list[dict] | None):
    """Fake herdr for adopt tests; ``tabs=None`` makes ``tab list`` fail."""

    def fake_herdr(argv: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(list(argv))
        if argv[1:3] == ["tab", "list"]:
            if tabs is None:
                body = json.dumps({"error": {"code": "boom", "message": "no socket"}})
                return subprocess.CompletedProcess(argv, 1, body, "")
            body = json.dumps({"result": {"tabs": tabs, "type": "tab_list"}})
        elif argv[1:3] == ["pane", "list"]:
            panes = [{"pane_id": "wD:p1", "tab_id": "wD:t1", "agent": "cursor"}]
            body = json.dumps({"result": {"panes": panes, "type": "pane_list"}})
        else:
            raise AssertionError(argv)
        return subprocess.CompletedProcess(argv, 0, body, "")

    return fake_herdr


def test_adopt_existing_worker_tab_list_error_refuses_duplicate(loop_mod):
    calls: list[list[str]] = []
    fake = _adopt_fake_herdr(calls, None)
    with pytest.raises(RuntimeError, match=r"issue-42.*duplicate worker"):
        loop_mod.adopt_existing_worker(_issue(42), run_herdr=fake)
    assert [c[1:3] for c in calls] == [["tab", "list"]]


def test_adopt_existing_worker_multiple_tabs_adopts_first_and_warns(
    loop_mod, capsys
):
    calls: list[list[str]] = []
    tabs = [
        {"label": "issue-42", "tab_id": "wD:t1"},
        {"label": "issue-42", "tab_id": "wD:t2"},
    ]
    fake = _adopt_fake_herdr(calls, tabs)
    worker = loop_mod.adopt_existing_worker(_issue(42), run_herdr=fake)
    assert worker is not None
    assert worker.tab_id == "wD:t1"
    assert worker.adopted
    assert "closed when the issue advances" in capsys.readouterr().err
    assert not [c for c in calls if c[1:3] in (["tab", "create"], ["tab", "close"])]


def test_close_tab_id_treats_tab_not_found_as_ok(loop_mod):
    def fake_herdr(argv: list[str]) -> subprocess.CompletedProcess[str]:
        body = json.dumps(
            {"error": {"code": "tab_not_found", "message": "tab gone"}},
        )
        return subprocess.CompletedProcess(argv, 1, body, "")

    loop_mod.close_tab_id("wD:tMissing", run_herdr=fake_herdr)


def test_format_queue_counts_and_worker_opened_lines(loop_mod):
    assert (
        loop_mod.format_queue_counts_line(22, 1, "self-heal", "AlexanderMakarov")
        == "22 with 'self-heal' label, 1 is assigned on 'AlexanderMakarov'"
    )
    assert (
        loop_mod.format_loop_params_line(
            poll_seconds=300,
            agent_kind="cursor",
            once=False,
        )
        == "params: poll-seconds=300; agent-kind=cursor; mode=loop"
    )
    line = loop_mod.format_worker_opened_line(
        tab_label="issue-305",
        issue_number=305,
        title="Show docs",
        opened_at=datetime(2026, 10, 5, 13, 42, 5),
    )
    assert line == "issue-305 herdr tab opened for #305 gh issue Show docs at 13:42:05"


def test_load_skill_text_uses_fallback_when_missing(loop_mod, tmp_path):
    missing = tmp_path / "SKILL.md"
    assert loop_mod.load_skill_text(missing) == loop_mod._MINIMAL_SKILL_FALLBACK


def test_load_skill_text_reads_file(loop_mod, tmp_path):
    skill = tmp_path / "SKILL.md"
    skill.write_text("custom skill body\n", encoding="utf-8")
    assert loop_mod.load_skill_text(skill) == "custom skill body\n"


def test_load_skill_text_strips_yaml_frontmatter(loop_mod, tmp_path):
    skill = tmp_path / "SKILL.md"
    skill.write_text(
        "---\nname: loop-ready-issue-herdr\ndisable-model-invocation: true\n---\nBody only\n",
        encoding="utf-8",
    )
    assert loop_mod.load_skill_text(skill) == "Body only\n"


def test_build_worker_prompt_includes_url(loop_mod):
    text = loop_mod.build_worker_prompt("skill", "https://example/o/r/issues/1")
    assert "skill" in text
    assert "https://example/o/r/issues/1" in text


def test_herdr_worker_disappeared_codes(loop_mod):
    assert loop_mod.herdr_worker_disappeared(
        {"error": {"code": "agent_not_found", "message": "x"}},
    )
    assert not loop_mod.herdr_worker_disappeared({"result": {"type": "ok"}})


def test_spawn_worker_for_issue_herdr_sequence(loop_mod):
    calls: list[list[str]] = []

    def fake_herdr(argv: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(list(argv))
        if argv[1:3] == ["tab", "create"]:
            body = json.dumps(
                {
                    "result": {
                        "root_pane": {"pane_id": "wZ:p1"},
                        "tab": {"tab_id": "wZ:t1"},
                    },
                },
            )
        elif argv[1:3] == ["agent", "start"]:
            body = json.dumps({"result": {"type": "ok"}})
        elif argv[1:3] == ["agent", "prompt"]:
            body = json.dumps({"result": {"type": "ok"}})
        else:
            raise AssertionError(f"unexpected herdr argv: {argv}")
        return subprocess.CompletedProcess(argv, 0, body, "")

    issue = {
        "number": 42,
        "url": "https://github.com/o/r/issues/42",
        "title": "T",
    }
    worker = loop_mod.spawn_worker_for_issue(
        issue,
        agent_kind="cursor",
        repo_root=Path("/tmp/repo"),
        run_herdr=fake_herdr,
        skill_path=Path("/nonexistent/skill.md"),
    )
    assert worker.tab_id == "wZ:t1"
    assert worker.pane_id == "wZ:p1"
    assert worker.issue_number == 42
    assert calls[0][3:5] == ["--cwd", "/tmp/repo"]
    assert calls[0][6] == "issue-42"
    assert calls[1][3] == "issue-42"
    assert calls[1][5] == "cursor"
    assert calls[2][3] == "wZ:p1"


def test_fetch_issue_merge_and_ci_status_graphql_closing_pr(loop_mod):
    graphql_payload = {
        "data": {
            "repository": {
                "defaultBranchRef": {"name": "main"},
                "issue": {
                    "state": "CLOSED",
                    "stateReason": "COMPLETED",
                    "closedByPullRequestsReferences": {
                        "nodes": [
                            {
                                "number": 9,
                                "merged": False,
                                "baseRefName": "main",
                                "mergeCommit": None,
                            },
                            {
                                "number": 10,
                                "merged": True,
                                "baseRefName": "main",
                                "mergeCommit": {"oid": "deadbeef"},
                            },
                        ],
                    },
                },
            },
        },
    }
    slurp_pages = [
        {"check_runs": [{"name": "ci", "status": "completed", "conclusion": "success"}]},
    ]

    def fake_run_gh(argv: list[str]) -> subprocess.CompletedProcess[str]:
        if argv[1:3] == ["api", "graphql"]:
            assert "-F" in argv and "number=42" in argv
            query_args = [
                argv[i + 1]
                for i, tok in enumerate(argv)
                if tok == "-f" and i + 1 < len(argv) and argv[i + 1].startswith("query=")
            ]
            assert query_args, argv
            query = query_args[0]
            assert "issue(number: $number)" in query
            assert "issue(number: 42)" not in query
            assert "state stateReason" in query
            return subprocess.CompletedProcess(argv, 0, json.dumps(graphql_payload), "")
        if argv[1] == "api" and len(argv) > 2 and "check-runs" in argv[2]:
            assert "--slurp" in argv
            return subprocess.CompletedProcess(argv, 0, json.dumps(slurp_pages), "")
        raise AssertionError(f"unexpected gh argv: {argv}")

    status = loop_mod.fetch_issue_merge_and_ci_status("o/r", 42, run_gh=fake_run_gh)
    assert status["issue_state"] == "CLOSED"
    assert status["state_reason"] == "COMPLETED"
    assert status["merge_info"]["merged"] is True
    assert status["merge_info"]["pr_number"] == 10
    assert status["merge_info"]["merge_commit_sha"] == "deadbeef"
    assert len(status["check_runs"]) == 1


def test_fetch_issue_merge_and_ci_status_merges_slurp_check_run_pages(loop_mod):
    graphql_payload = {
        "data": {
            "repository": {
                "defaultBranchRef": {"name": "main"},
                "issue": {
                    "closedByPullRequestsReferences": {
                        "nodes": [
                            {
                                "number": 1,
                                "merged": True,
                                "baseRefName": "main",
                                "mergeCommit": {"oid": "abc"},
                            },
                        ],
                    },
                },
            },
        },
    }
    slurp_pages = [
        {"check_runs": [{"name": "a", "status": "completed", "conclusion": "success"}]},
        {"check_runs": [{"name": "b", "status": "completed", "conclusion": "success"}]},
    ]

    def fake_run_gh(argv: list[str]) -> subprocess.CompletedProcess[str]:
        if argv[1:3] == ["api", "graphql"]:
            return subprocess.CompletedProcess(argv, 0, json.dumps(graphql_payload), "")
        if "check-runs" in " ".join(argv):
            return subprocess.CompletedProcess(argv, 0, json.dumps(slurp_pages), "")
        raise AssertionError(argv)

    status = loop_mod.fetch_issue_merge_and_ci_status("o/r", 1, run_gh=fake_run_gh)
    names = [r["name"] for r in status["check_runs"]]
    assert names == ["a", "b"]


def test_wait_until_ticket_advanced_polls_until_alpha(loop_mod):
    polls = {"n": 0}

    def fake_fetch(repo: str, issue_number: int, run_gh) -> dict:
        polls["n"] += 1
        merged = polls["n"] >= 2
        check_runs = [_green_ci_check()] if merged else []
        return {
            "issue_number": issue_number,
            "merge_info": {"merged": merged},
            "check_runs": check_runs,
        }

    worker = loop_mod.WorkerHandle(
        tab_id="wZ:t1",
        pane_id="wZ:p1",
        issue_number=7,
        issue_url="https://example/7",
    )

    def fake_herdr(argv: list[str]) -> subprocess.CompletedProcess[str]:
        body = json.dumps({"result": {"type": "agent_info"}})
        return subprocess.CompletedProcess(argv, 0, body, "")

    sleeps: list[float] = []
    loop_mod.wait_until_ticket_advanced(
        "o/r",
        worker,
        60,
        label="agent-ready",
        run_gh=lambda _a: subprocess.CompletedProcess([], 0, "", ""),
        run_herdr=fake_herdr,
        sleep_fn=sleeps.append,
        fetch_status=fake_fetch,
    )
    assert polls["n"] == 2
    assert worker.gone is False
    assert sleeps == [60.0]


def test_wait_until_ticket_advanced_sleeps_when_herdr_wait_returns_immediately(loop_mod):
    polls = {"n": 0}

    def fake_fetch(*_args, **_kwargs) -> dict:
        polls["n"] += 1
        merged = polls["n"] >= 2
        return {
            "issue_number": 1,
            "merge_info": {"merged": merged},
            "check_runs": [_green_ci_check()] if merged else [],
        }

    worker = loop_mod.WorkerHandle(
        tab_id="t",
        pane_id="p",
        issue_number=1,
        issue_url="https://example/1",
    )
    sleeps: list[float] = []
    wait_calls = {"n": 0}

    def fake_herdr(argv: list[str]) -> subprocess.CompletedProcess[str]:
        wait_calls["n"] += 1
        body = json.dumps({"result": {"type": "idle"}})
        return subprocess.CompletedProcess(argv, 0, body, "")

    loop_mod.wait_until_ticket_advanced(
        "o/r",
        worker,
        5,
        label="lbl",
        run_gh=lambda _a: subprocess.CompletedProcess([], 0, "", ""),
        run_herdr=fake_herdr,
        sleep_fn=sleeps.append,
        fetch_status=fake_fetch,
    )
    assert sleeps == [5.0]
    assert wait_calls["n"] == 1


def test_wait_until_ticket_advanced_worker_gone_keeps_polling_github(loop_mod):
    polls = {"n": 0}

    def fake_fetch(repo: str, issue_number: int, run_gh) -> dict:
        polls["n"] += 1
        merged = polls["n"] >= 3
        return {
            "issue_number": issue_number,
            "merge_info": {"merged": merged},
            "check_runs": [_green_ci_check()] if merged else [],
        }

    worker = loop_mod.WorkerHandle(
        tab_id="wZ:t1",
        pane_id="wZ:p1",
        issue_number=9,
        issue_url="https://example/9",
    )

    def fake_herdr(argv: list[str]) -> subprocess.CompletedProcess[str]:
        if argv[1:3] == ["agent", "wait"]:
            body = json.dumps(
                {"error": {"code": "agent_not_found", "message": "gone"}},
            )
            return subprocess.CompletedProcess(argv, 1, body, "")
        raise AssertionError(argv)

    sleeps: list[float] = []
    loop_mod.wait_until_ticket_advanced(
        "o/r",
        worker,
        10,
        label="lbl",
        run_gh=lambda _a: subprocess.CompletedProcess([], 0, "", ""),
        run_herdr=fake_herdr,
        sleep_fn=sleeps.append,
        fetch_status=fake_fetch,
    )
    assert worker.gone is True
    assert worker.warned_gone is True
    assert polls["n"] == 3
    assert sleeps == [10.0, 10.0]


def _status(
    *,
    merged: bool = False,
    state: str = "OPEN",
    state_reason: str | None = None,
    check_runs: list[dict] | None = None,
) -> dict:
    return {
        "issue_number": 7,
        "issue_state": state,
        "state_reason": state_reason,
        "merge_info": {"merged": merged, "pr_number": 10 if merged else None},
        "check_runs": check_runs or [],
    }


_PENDING_CHECK = {"name": "ci", "status": "in_progress", "conclusion": None}


# @regression
@pytest.mark.parametrize(
    ("statuses", "expected_reason", "expected_out"),
    [
        pytest.param(
            [_status(state="CLOSED", state_reason="COMPLETED")],
            "closed: COMPLETED, no merged closing PR; CI gate skipped",
            [],
            id="closed-without-merged-pr-advances",
        ),
        pytest.param(
            [_status(), _status(state="CLOSED", state_reason="NOT_PLANNED")],
            "closed: NOT_PLANNED, no merged closing PR; CI gate skipped",
            ["#7 open; no merged PR closes it yet — waiting 60s"],
            id="closed-while-waiting",
        ),
        pytest.param(
            [
                _status(merged=True, state="CLOSED", check_runs=[_PENDING_CHECK]),
                _status(merged=True, state="CLOSED", check_runs=[_green_ci_check()]),
            ],
            "merge + post-merge CI α",
            ["#7: PR #10 merged; post-merge CI 0/1 green (1 pending) — waiting 60s"],
            id="merged-and-auto-closed-still-waits-for-alpha",
        ),
    ],
)
def test_wait_until_ticket_advanced_issue_state_decision(
    loop_mod, capsys, statuses, expected_reason, expected_out
):
    """A merged closing PR keeps strict α even when CLOSED; a CLOSED issue without one advances."""
    pending = list(statuses)

    def fake_fetch(_repo: str, _issue_number: int, _run_gh) -> dict:
        if not pending:
            raise AssertionError("polled GitHub again after the issue should have advanced")
        return pending.pop(0)

    def fake_herdr(argv: list[str]) -> subprocess.CompletedProcess[str]:
        assert argv[1:3] == ["agent", "wait"], argv
        return subprocess.CompletedProcess(argv, 0, json.dumps({"result": {"type": "idle"}}), "")

    worker = loop_mod.WorkerHandle(
        tab_id="wZ:t7", pane_id="wZ:p7", issue_number=7, issue_url="https://example/7"
    )
    sleeps: list[float] = []
    reason = loop_mod.wait_until_ticket_advanced(
        "o/r",
        worker,
        60,
        label="lbl",
        run_gh=lambda _a: subprocess.CompletedProcess([], 0, "", ""),
        run_herdr=fake_herdr,
        sleep_fn=sleeps.append,
        fetch_status=fake_fetch,
    )
    assert reason == expected_reason
    assert pending == []
    assert sleeps == [60.0] * (len(statuses) - 1)
    assert capsys.readouterr().out.splitlines() == expected_out


@pytest.mark.parametrize(
    ("status", "worker_gone", "expected"),
    [
        pytest.param(
            _status(merged=True),
            False,
            "#7: PR #10 merged; no check runs yet on the merge commit — waiting 300s",
            id="no-check-runs",
        ),
        pytest.param(
            _status(
                merged=True,
                check_runs=[
                    _green_ci_check("a"),
                    {"name": "b", "status": "completed", "conclusion": "skipped"},
                    _green_ci_check("c"),
                    {"name": "d", "status": "completed", "conclusion": "failure"},
                    _PENDING_CHECK,
                ],
            ),
            False,
            "#7: PR #10 merged; post-merge CI 3/5 green (1 failed, 1 pending) — waiting 300s",
            id="mixed-checks",
        ),
        pytest.param(
            _status(),
            True,
            "#7 open; no merged PR closes it yet — waiting 300s (worker gone)",
            id="worker-gone-suffix",
        ),
    ],
)
def test_format_advance_poll_line(loop_mod, status, worker_gone, expected):
    """The per-poll status line names the blocking condition, CI tally, and a gone worker."""
    assert loop_mod.format_advance_poll_line(status, 300, worker_gone=worker_gone) == expected


def _sweep_fake_herdr(calls: list[list[str]], tabs: list[dict] | None, fail_close: set[str]):
    """Fake herdr for the closed-issue sweep; ``tabs=None`` fails ``tab list``."""

    def fake_herdr(argv: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(list(argv))
        if argv[1:3] == ["tab", "list"]:
            if tabs is None:
                body = json.dumps({"error": {"code": "boom", "message": "no socket"}})
                return subprocess.CompletedProcess(argv, 1, body, "")
            body = json.dumps({"result": {"tabs": tabs, "type": "tab_list"}})
        elif argv[1:3] == ["tab", "close"]:
            if argv[3] in fail_close:
                body = json.dumps({"error": {"code": "busy", "message": "locked"}})
                return subprocess.CompletedProcess(argv, 1, body, "")
            body = json.dumps({"result": {"type": "ok"}})
        else:
            raise AssertionError(argv)
        return subprocess.CompletedProcess(argv, 0, body, "")

    return fake_herdr


def _states_fake_gh(
    queries: list[str], repository: dict, returncode: int = 1, stdout: str | None = None
):
    """Fake ``gh api graphql``: real gh exits 1 when the response carries GraphQL errors."""
    def fake_run_gh(argv: list[str]) -> subprocess.CompletedProcess[str]:
        assert argv[1:3] == ["api", "graphql"], argv
        queries.append(next(a for a in argv if a.startswith("query=")))
        if stdout is not None:
            return subprocess.CompletedProcess(argv, returncode, stdout, "HTTP 502")
        payload = {
            "data": {"repository": repository},
            "errors": [{"type": "NOT_FOUND", "path": ["repository", "issue_7"]}],
        }
        stderr = "gh: Could not resolve to an Issue with the number of 7."
        return subprocess.CompletedProcess(argv, returncode, json.dumps(payload), stderr)

    return fake_run_gh


# @regression
def test_close_tabs_for_closed_issues_closes_only_closed_issue_tabs(loop_mod, capsys):
    """Only ``issue-N`` tabs whose issue is CLOSED close; open, unresolved, and other tabs stay."""
    tabs = [
        {"label": "issue-5", "tab_id": "wD:t5"},
        {"label": "issue-6", "tab_id": "wD:t6"},
        {"label": "issue-7", "tab_id": "wD:t7"},
        {"label": "issue-5", "tab_id": "wD:t5b"},
        {"label": "issue-8-old", "tab_id": "wD:t8"},
        {"label": "driver", "tab_id": "wD:tD"},
    ]
    herdr_calls: list[list[str]] = []
    queries: list[str] = []
    repository = {
        "issue_5": {"number": 5, "state": "CLOSED"},
        "issue_6": {"number": 6, "state": "OPEN"},
        "issue_7": None,
    }
    closed = loop_mod.close_tabs_for_closed_issues(
        "o/r",
        run_gh=_states_fake_gh(queries, repository),
        run_herdr=_sweep_fake_herdr(herdr_calls, tabs, set()),
    )
    assert closed == ["wD:t5", "wD:t5b"]
    assert [c for c in herdr_calls if c[1:3] == ["tab", "close"]] == [
        ["herdr", "tab", "close", "wD:t5"],
        ["herdr", "tab", "close", "wD:t5b"],
    ]
    assert len(queries) == 1
    assert sorted(re.findall(r"issue_(\d+): issue", queries[0])) == ["5", "6", "7"]
    assert capsys.readouterr().out.splitlines() == [
        "Closed herdr tab issue-5 (wD:t5): #5 is closed.",
        "Closed herdr tab issue-5 (wD:t5b): #5 is closed.",
    ]


# @regression
@pytest.mark.parametrize(
    ("failure", "expected_closed", "expected_warning"),
    [
        ("herdr_list", [], "WARNING: closed-issue tab sweep skipped: herdr tab list failed"),
        ("gh", [], "WARNING: closed-issue tab sweep skipped: gh api graphql (issue states)"),
        ("close", ["wD:t2"], "WARNING: could not close herdr tab issue-1 (wD:t1)"),
    ],
)
def test_close_tabs_for_closed_issues_warns_instead_of_raising(
    loop_mod, capsys, failure, expected_closed, expected_warning
):
    """A herdr list, GitHub, or single-close failure warns on stderr and never raises."""
    tabs = [{"label": "issue-1", "tab_id": "wD:t1"}, {"label": "issue-2", "tab_id": "wD:t2"}]
    herdr_calls: list[list[str]] = []
    queries: list[str] = []
    repository = {
        "issue_1": {"number": 1, "state": "CLOSED"},
        "issue_2": {"number": 2, "state": "CLOSED"},
    }
    closed = loop_mod.close_tabs_for_closed_issues(
        "o/r",
        run_gh=_states_fake_gh(
            queries, repository, stdout="" if failure == "gh" else None
        ),
        run_herdr=_sweep_fake_herdr(
            herdr_calls,
            None if failure == "herdr_list" else tabs,
            {"wD:t1"} if failure == "close" else set(),
        ),
    )
    assert closed == expected_closed
    assert expected_warning in capsys.readouterr().err
    assert len(queries) == (0 if failure == "herdr_list" else 1)
