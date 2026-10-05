"""Tests for ``scripts/loop_ready_issue_herdr.py`` (#296).

# @layer: unit
# @spec: 303-loop-ready-issue-herdr
"""

from __future__ import annotations

import importlib.util
import json
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


def test_run_dry_run_pick_next_via_fake_run_gh(loop_mod):
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

    lines = loop_mod.run_dry_run(LABEL, "owner/repo", run_gh=fake_run_gh)
    text = "\n".join(lines)
    assert "repo: owner/repo" in text
    assert "3 with 'agent-ready' label, 3 is assigned on 'viewer'" in text
    assert "next: #8 Next eligible" in text


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
            return subprocess.CompletedProcess(argv, 0, json.dumps(graphql_payload), "")
        if argv[1] == "api" and len(argv) > 2 and "check-runs" in argv[2]:
            assert "--slurp" in argv
            return subprocess.CompletedProcess(argv, 0, json.dumps(slurp_pages), "")
        raise AssertionError(f"unexpected gh argv: {argv}")

    status = loop_mod.fetch_issue_merge_and_ci_status("o/r", 42, run_gh=fake_run_gh)
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
