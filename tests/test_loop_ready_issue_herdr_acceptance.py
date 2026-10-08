"""Acceptance tests for herdr ready-issue loop (#296 / spec 303-loop-ready-issue-herdr).

# @layer: integration
# @spec: 303-loop-ready-issue-herdr
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "loop_ready_issue_herdr.py"
SKILL = REPO / ".claude/skills/loop-ready-issue-herdr/SKILL.md"
MAINTAINER_DOC = REPO / "docs/maintainers/LOOP_READY_ISSUE_HERDR.md"

CUSTOM_LABEL = "ready-for-agent"
LOGIN = "maintainer"


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
    title: str = "T",
    state: str = "OPEN",
    labels: list[str] | None = None,
    assignees: list[str] | None = None,
    url: str | None = None,
) -> dict:
    return {
        "number": number,
        "title": title,
        "state": state,
        "labels": labels or [],
        "assignees": assignees or [],
        "url": url or f"https://example/o/r/issues/{number}",
    }


def _fake_gh_factory(
    *,
    login: str,
    repo: str,
    issues: list[dict],
    blocked_by_map: dict[int, list[dict]] | None = None,
    issue_states: dict[int, str] | None = None,
    merge_status: dict | None = None,
):
    """Fake ``gh``; GraphQL alias queries answer each ``issue_N`` asked for.

    Alias states come from ``issues`` then ``issue_states``; a number in neither
    gets a null node. ``merge_status`` is the ``repository`` object returned for
    the wait loop's merge-status query.
    """
    blocked_by_map = blocked_by_map or {}
    states = {issue["number"]: issue["state"] for issue in issues} | (issue_states or {})

    def fake_run_gh(argv: list[str]) -> subprocess.CompletedProcess[str]:
        cmd = argv[0] if argv else ""
        if cmd == "gh" and len(argv) > 2 and argv[1] == "api" and argv[2] == "user":
            body = json.dumps({"login": login})
        elif cmd == "gh" and "repo" in argv and "view" in argv:
            body = json.dumps({"nameWithOwner": repo})
        elif cmd == "gh" and "issue" in argv and "list" in argv:
            body = json.dumps(issues)
        elif cmd == "gh" and argv[1:3] == ["api", "graphql"]:
            query = next(a for a in argv if a.startswith("query="))
            if "closedByPullRequestsReferences" in query:
                assert merge_status is not None, "unexpected merge-status poll"
                body = json.dumps({"data": {"repository": merge_status}})
            else:
                data: dict = {"repository": {}}
                for num in map(int, re.findall(r"issue_(\d+): issue", query)):
                    data["repository"][f"issue_{num}"] = (
                        {
                            "number": num,
                            "state": states[num],
                            "blockedBy": {"nodes": blocked_by_map.get(num, [])},
                        }
                        if num in states
                        else None
                    )
                body = json.dumps({"data": data})
        else:
            raise AssertionError(f"unexpected gh argv: {argv}")
        return subprocess.CompletedProcess(argv, 0, body, "")

    return fake_run_gh


# @regression
def test_acceptance_work_for_today_and_queue_eligibility_pipeline(loop_mod):
    """§2.3–2.4: label L counts, assignee gate, blockedBy skip, important then number."""
    issues = [
        _issue(100, labels=[CUSTOM_LABEL], assignees=[LOGIN]),
        _issue(101, labels=[CUSTOM_LABEL], assignees=["peer"]),
        _issue(102, labels=["other"], assignees=[LOGIN]),
        _issue(103, state="CLOSED", labels=[CUSTOM_LABEL], assignees=[LOGIN]),
        _issue(50, labels=[CUSTOM_LABEL, "important"], assignees=[LOGIN]),
        _issue(60, labels=[CUSTOM_LABEL], assignees=[LOGIN]),
    ]
    with_label, assigned = loop_mod.work_for_today_counts(issues, LOGIN, CUSTOM_LABEL)
    assert with_label == 4
    assert assigned == 3

    candidates = loop_mod.candidates_assigned(issues, LOGIN, CUSTOM_LABEL)
    assert {i["number"] for i in candidates} == {50, 60, 100}

    blocked_by_map = {50: [{"number": 1, "state": "OPEN"}]}
    picked = loop_mod.pick_next(candidates, blocked_by_map)
    assert picked is not None
    assert picked["number"] == 60


# @regression
def test_acceptance_dry_run_pipeline_fake_run_gh(loop_mod):
    """§2.3 / §2.9: startup summary + next pick without herdr (full gh stub path)."""
    issues = [
        _issue(8, title="Next eligible", labels=[CUSTOM_LABEL], assignees=[LOGIN]),
        _issue(5, title="Blocked important", labels=[CUSTOM_LABEL, "important"], assignees=[LOGIN]),
    ]
    fake_run_gh = _fake_gh_factory(
        login=LOGIN,
        repo="org/wik",
        issues=issues,
        blocked_by_map={5: [{"number": 1, "state": "OPEN"}]},
    )
    lines = loop_mod.run_dry_run(CUSTOM_LABEL, "org/wik", run_gh=fake_run_gh)
    text = "\n".join(lines)
    assert "repo: org/wik" in text
    assert f"2 with {CUSTOM_LABEL!r} label, 2 is assigned on {LOGIN!r}" in text
    assert "planned (1):" in text  # #5 blocked
    assert "  1. #8 Next eligible" in text
    assert "next: #8 Next eligible" in text


# @regression
@pytest.mark.parametrize(
    ("merge_info", "check_runs", "expected"),
    [
        ({"merged": False}, [], False),
        ({"merged": True}, [], False),
        (
            {"merged": True},
            [{"name": "ci", "status": "completed", "conclusion": "success"}],
            True,
        ),
        (
            {"merged": True},
            [{"name": "ci", "status": "completed", "conclusion": "failure"}],
            False,
        ),
    ],
)
def test_acceptance_advance_alpha_option(loop_mod, merge_info, check_runs, expected):
    """§2.8: advance only when merged and all observed post-merge checks are green."""
    assert loop_mod.advance_ready(merge_info, check_runs) is expected


# @regression
def test_acceptance_early_close_warning_text_contract(loop_mod, capsys):
    """§2.8: worker tab gone before merge → WARNING + restore lines; still poll GitHub."""
    worker = loop_mod.WorkerHandle(
        tab_id="wZ:t1",
        pane_id="wZ:p1",
        issue_number=77,
        issue_url="https://github.com/o/r/issues/77",
    )
    polls = {"n": 0}

    def fake_fetch(_repo: str, issue_number: int, _run_gh) -> dict:
        polls["n"] += 1
        merged = polls["n"] >= 2
        check_runs = (
            [{"name": "ci", "status": "completed", "conclusion": "success"}]
            if merged
            else []
        )
        return {
            "issue_number": issue_number,
            "merge_info": {"merged": merged},
            "check_runs": check_runs,
        }

    def fake_herdr(argv: list[str]) -> subprocess.CompletedProcess[str]:
        body = json.dumps({"error": {"code": "agent_not_found", "message": "gone"}})
        return subprocess.CompletedProcess(argv, 1, body, "")

    loop_mod.wait_until_ticket_advanced(
        "o/r",
        worker,
        15,
        label=CUSTOM_LABEL,
        run_gh=lambda _a: subprocess.CompletedProcess([], 0, "", ""),
        run_herdr=fake_herdr,
        sleep_fn=lambda _s: None,
        fetch_status=fake_fetch,
    )
    err = capsys.readouterr().err
    assert "WARNING: worker for issue #77 disappeared before merge+CI advance (α)." in err
    assert "https://github.com/o/r/issues/77" in err
    assert f"--label {CUSTOM_LABEL}" in err
    assert "--once for a single ticket" in err
    assert "keeps polling GitHub for α on #77" in err
    assert worker.gone is True
    assert polls["n"] == 2


def test_acceptance_skill_disable_model_invocation_frontmatter():
    """§2.6 / technical-considerations: skill must not be self-invoked by agents."""
    text = SKILL.read_text(encoding="utf-8")
    assert SKILL.is_file()
    assert re.search(r"(?m)^disable-model-invocation:\s*true\s*$", text)


# @regression
def test_acceptance_skill_one_ticket_route_contract():
    """§2.6: bug → /fix-bug; else /implement-feature; no queue advance in skill."""
    text = SKILL.read_text(encoding="utf-8")
    assert "/fix-bug" in text
    assert "/implement-feature" in text
    assert "Do not start a second ticket" in text or "Do not start a second" in text
    assert "advance to the next queued issue" in text


def test_acceptance_maintainer_note_herdr_required():
    """§2.2: doc states herdr is required; manual delivery commands remain."""
    doc = MAINTAINER_DOC.read_text(encoding="utf-8")
    assert re.search(r"herdr required", doc, re.IGNORECASE)
    assert "/implement-feature" in doc
    assert "/fix-bug" in doc
    assert re.search(r"Without herdr|without herdr", doc)


# @regression
def test_acceptance_argparse_poll_seconds_default_300(loop_mod):
    """technical-considerations: --poll-seconds default 300."""
    args = loop_mod.build_parser().parse_args(["--label", "x"])
    assert args.poll_seconds == 300


def test_acceptance_argparse_rejects_missing_label(loop_mod):
    with pytest.raises(SystemExit):
        loop_mod.build_parser().parse_args([])


# @regression
@pytest.mark.parametrize("existing_tab", [False, True], ids=["spawn", "adopt"])
def test_acceptance_run_main_loop_once_single_worker(
    loop_mod, monkeypatch, capsys, existing_tab
):
    """§2.5 / §2.9: serial N=1 — one worker, α wait, tab close, exit with --once.

    An open ``issue-N`` tab (restored herdr session, driver restart) is adopted:
    no new tab, agent start, or prompt, so in-progress delivery is not restarted.
    """
    issues = [_issue(11, title="Only ticket", labels=[CUSTOM_LABEL], assignees=[LOGIN])]
    fake_run_gh = _fake_gh_factory(login=LOGIN, repo="o/r", issues=issues)

    spawn_events: list[str] = []
    tabs = [{"label": "issue-11", "tab_id": "wD:tR"}] if existing_tab else []
    panes = [
        {"pane_id": "wD:pShell", "tab_id": "wD:tR"},
        {"pane_id": "wD:pAgent", "tab_id": "wD:tR", "agent": "cursor"},
        {"pane_id": "wD:pOther", "tab_id": "wD:tX", "agent": "cursor"},
    ]
    waited_on: list[str] = []

    def fake_run_herdr(argv: list[str]) -> subprocess.CompletedProcess[str]:
        if argv[1:3] == ["tab", "list"]:
            body = json.dumps({"result": {"tabs": tabs, "type": "tab_list"}})
        elif argv[1:3] == ["pane", "list"]:
            body = json.dumps({"result": {"panes": panes, "type": "pane_list"}})
        elif argv[1:3] == ["tab", "create"]:
            spawn_events.append("create")
            body = json.dumps(
                {
                    "result": {
                        "root_pane": {"pane_id": "p1"},
                        "tab": {"tab_id": "t1"},
                    },
                },
            )
        elif argv[1:3] == ["agent", "start"]:
            spawn_events.append("start")
            body = json.dumps({"result": {"type": "ok"}})
        elif argv[1:3] == ["agent", "prompt"]:
            spawn_events.append("prompt")
            body = json.dumps({"result": {"type": "ok"}})
        elif argv[1:3] == ["agent", "wait"]:
            body = json.dumps({"result": {"type": "blocked"}})
        elif argv[1:3] == ["tab", "close"]:
            spawn_events.append("close")
            body = json.dumps({"result": {"type": "ok"}})
        else:
            raise AssertionError(f"unexpected herdr argv: {argv}")
        return subprocess.CompletedProcess(argv, 0, body, "")

    def fake_wait(_repo, worker, *_args, **_kwargs) -> str:
        """Default fetch_status is bound at def time; stub α wait for driver integration."""
        waited_on.append(worker.pane_id)
        return "merge + post-merge CI α"

    monkeypatch.setattr(loop_mod, "wait_until_ticket_advanced", fake_wait)

    code = loop_mod.run_main_loop(
        CUSTOM_LABEL,
        "o/r",
        "cursor",
        300,
        once=True,
        run_gh=fake_run_gh,
        run_herdr=fake_run_herdr,
        sleep_fn=lambda _s: None,
        repo_root=REPO,
    )
    out = capsys.readouterr().out
    assert code == 0
    assert f"1 with {CUSTOM_LABEL!r} label, 1 is assigned on {LOGIN!r}" in out
    assert "params: poll-seconds=300; agent-kind=cursor; mode=once" in out
    assert "Advanced #11 (merge + post-merge CI α); worker tab closed." in out
    if existing_tab:
        assert spawn_events == ["close"]
        assert waited_on == ["wD:pAgent"]
        assert "issue-11 herdr tab adopted (wD:tR, no new prompt; close it to restart) for #11 gh issue" in out
    else:
        assert spawn_events == ["create", "start", "prompt", "close"]
        assert waited_on == ["p1"]
        assert "issue-11 herdr tab opened for #11 gh issue" in out


def test_acceptance_empty_queue_once_exits_without_sleep(loop_mod, capsys):
    """§2.9 negative: no eligible work with --once → exit 0 immediately, no spawn."""
    fake_run_gh = _fake_gh_factory(login=LOGIN, repo="o/r", issues=[])
    sleeps: list[float] = []

    def fake_run_herdr(argv: list[str]) -> subprocess.CompletedProcess[str]:
        if argv[1:3] == ["tab", "list"]:
            body = json.dumps({"result": {"tabs": [], "type": "tab_list"}})
            return subprocess.CompletedProcess(argv, 0, body, "")
        raise AssertionError(f"herdr must only list tabs when queue empty: {argv}")

    code = loop_mod.run_main_loop(
        CUSTOM_LABEL,
        "o/r",
        "cursor",
        180,
        once=True,
        run_gh=fake_run_gh,
        run_herdr=fake_run_herdr,
        sleep_fn=sleeps.append,
    )
    assert code == 0
    assert sleeps == []
    out = capsys.readouterr().out
    assert "No eligible issues" in out
    assert "exiting (--once)" in out


def test_acceptance_spawn_worker_prompt_inlines_repo_skill(loop_mod):
    """§2.6 / §2.10: default worker prompt includes shipped skill route text."""
    captured: list[str] = []

    def fake_herdr(argv: list[str]) -> subprocess.CompletedProcess[str]:
        if argv[1:3] == ["tab", "list"]:
            body = json.dumps({"result": {"tabs": [], "type": "tab_list"}})
        elif argv[1:3] == ["agent", "prompt"]:
            captured.append(argv[4])
            body = json.dumps({"result": {"type": "ok"}})
        elif argv[1:3] == ["tab", "create"]:
            body = json.dumps(
                {
                    "result": {
                        "root_pane": {"pane_id": "p"},
                        "tab": {"tab_id": "t"},
                    },
                },
            )
        elif argv[1:3] == ["agent", "start"]:
            body = json.dumps({"result": {"type": "ok"}})
        else:
            raise AssertionError(argv)
        return subprocess.CompletedProcess(argv, 0, body, "")

    issue = _issue(5, url="https://github.com/o/r/issues/5")
    loop_mod.spawn_worker_for_issue(
        issue,
        agent_kind="cursor",
        repo_root=REPO,
        run_herdr=fake_herdr,
        skill_path=SKILL,
    )
    assert captured
    prompt = captured[0]
    assert "https://github.com/o/r/issues/5" in prompt
    assert "/fix-bug" in prompt
    assert "/implement-feature" in prompt


# @regression
def test_acceptance_startup_sweep_closes_tabs_of_closed_issues(loop_mod, capsys):
    """Startup closes orphan ``issue-N`` tabs whose issue is CLOSED; open-issue tabs stay."""
    fake_run_gh = _fake_gh_factory(
        login=LOGIN,
        repo="o/r",
        issues=[],
        issue_states={9: "CLOSED", 12: "OPEN"},
    )
    tabs = [
        {"label": "issue-9", "tab_id": "wD:tOld"},
        {"label": "issue-12", "tab_id": "wD:tLive"},
    ]
    herdr_calls: list[list[str]] = []

    def fake_run_herdr(argv: list[str]) -> subprocess.CompletedProcess[str]:
        herdr_calls.append(list(argv))
        if argv[1:3] == ["tab", "list"]:
            body = json.dumps({"result": {"tabs": tabs, "type": "tab_list"}})
        elif argv[1:3] == ["tab", "close"]:
            body = json.dumps({"result": {"type": "ok"}})
        else:
            raise AssertionError(f"unexpected herdr argv: {argv}")
        return subprocess.CompletedProcess(argv, 0, body, "")

    code = loop_mod.run_main_loop(
        CUSTOM_LABEL,
        "o/r",
        "cursor",
        300,
        once=True,
        run_gh=fake_run_gh,
        run_herdr=fake_run_herdr,
        sleep_fn=lambda _s: None,
    )
    out = capsys.readouterr().out
    assert code == 0
    assert [c[1:] for c in herdr_calls] == [["tab", "list"], ["tab", "close", "wD:tOld"]]
    assert "Closed herdr tab issue-9 (wD:tOld): #9 is closed." in out
    assert "exiting (--once)" in out


# @regression
def test_acceptance_issue_closed_without_merge_advances_and_closes_tab(loop_mod, capsys):
    """An issue closed with no merged closing PR advances at once and states why."""
    issues = [_issue(11, title="Only ticket", labels=[CUSTOM_LABEL], assignees=[LOGIN])]
    fake_run_gh = _fake_gh_factory(
        login=LOGIN,
        repo="o/r",
        issues=issues,
        merge_status={
            "defaultBranchRef": {"name": "main"},
            "issue": {
                "state": "CLOSED",
                "stateReason": "NOT_PLANNED",
                "closedByPullRequestsReferences": {"nodes": []},
            },
        },
    )
    closed_tabs: list[str] = []

    def fake_run_herdr(argv: list[str]) -> subprocess.CompletedProcess[str]:
        if argv[1:3] == ["tab", "list"]:
            body = json.dumps({"result": {"tabs": [], "type": "tab_list"}})
        elif argv[1:3] == ["tab", "create"]:
            body = json.dumps(
                {"result": {"root_pane": {"pane_id": "p1"}, "tab": {"tab_id": "t1"}}},
            )
        elif argv[1:3] in (["agent", "start"], ["agent", "prompt"]):
            body = json.dumps({"result": {"type": "ok"}})
        elif argv[1:3] == ["tab", "close"]:
            closed_tabs.append(argv[3])
            body = json.dumps({"result": {"type": "ok"}})
        else:
            raise AssertionError(f"unexpected herdr argv: {argv}")
        return subprocess.CompletedProcess(argv, 0, body, "")

    def no_sleep(_seconds: float) -> None:
        raise AssertionError("a closed issue must advance without another poll")

    code = loop_mod.run_main_loop(
        CUSTOM_LABEL,
        "o/r",
        "cursor",
        300,
        once=True,
        run_gh=fake_run_gh,
        run_herdr=fake_run_herdr,
        sleep_fn=no_sleep,
        repo_root=REPO,
    )
    out = capsys.readouterr().out
    assert code == 0
    assert closed_tabs == ["t1"]
    assert (
        "Advanced #11 (closed: NOT_PLANNED, no merged closing PR; CI gate skipped); "
        "worker tab closed." in out
    )
