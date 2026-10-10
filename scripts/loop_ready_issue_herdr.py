#!/usr/bin/env python3
"""Serial ready-issue loop driver for herdr (#296).

Maintainer-only. Opt-in morning driver: summarize open labeled issues assigned
to you, spawn one herdr worker per ticket, and advance only after merge +
green post-merge CI on the default branch (or once the issue is closed with no
merged closing PR). ``issue-N`` tabs of already-closed issues are closed at the
top of every queue cycle.

Pure queue/sort/eligibility helpers are network-free; gh/herdr I/O is behind
injectable adapters for tests. Run from the repository root.

    python3 scripts/loop_ready_issue_herdr.py --label agent-ready --dry-run
    python3 scripts/loop_ready_issue_herdr.py --label agent-ready --once
    python3 scripts/loop_ready_issue_herdr.py --help

Requires local ``gh`` auth and ``herdr`` on PATH when not using ``--dry-run``.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from collections.abc import Callable, Collection
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent

# GitHub issue-shaped dicts (from ``gh`` list / GraphQL adapters).
Issue = dict[str, Any]
Blocker = dict[str, Any]
BlockedByMap = dict[int, list[Blocker]]
MergeInfo = dict[str, Any]
CheckRun = dict[str, Any]
IssueAdvanceStatus = dict[str, Any]

RunGh = Callable[[list[str]], subprocess.CompletedProcess[str]]
RunHerdr = Callable[[list[str]], subprocess.CompletedProcess[str]]
SleepFn = Callable[[float], None]

_AGENT_KINDS = ("cursor", "claude", "codex")

_SKILL_REL = Path(".claude/skills/loop-ready-issue-herdr/SKILL.md")

_MINIMAL_SKILL_FALLBACK = """\
# Loop ready issue (herdr) — one ticket

You are delivering **one** GitHub issue only. Do not list or advance the readiness queue.

1. Use the issue URL provided below.
2. Inspect labels: if `bug` is present run `/fix-bug`; otherwise run `/implement-feature`.
3. Follow the delivery flow for that command through PR merge; do not start another issue.
"""

_WORKER_GONE_ERROR_CODES = frozenset(
    {"agent_not_found", "pane_not_found", "tab_not_found"},
)
# Tab already closed — advance cleanup is still success.
_TAB_ALREADY_CLOSED_CODES = frozenset({"tab_not_found"})

_ISSUE_LIST_JSON_FIELDS = "number,title,labels,assignees,url,state"

_GREEN_CONCLUSIONS = frozenset({"success", "skipped", "neutral"})

# herdr tab labels the driver gives worker tabs (``issue-N``).
_ISSUE_TAB_LABEL_RE = re.compile(r"^issue-(\d+)$")

ADVANCE_REASON_MERGED = "merge + post-merge CI α"


def _issue_state_open(issue: Issue) -> bool:
    state = issue.get("state")
    if state is None:
        return True
    return str(state).upper() == "OPEN"


def _label_names(issue: Issue) -> set[str]:
    raw = issue.get("labels") or []
    names: set[str] = set()
    for item in raw:
        if isinstance(item, str):
            names.add(item)
        elif isinstance(item, dict) and item.get("name"):
            names.add(str(item["name"]))
    return names


def _assignee_logins(issue: Issue) -> set[str]:
    raw = issue.get("assignees") or []
    logins: set[str] = set()
    for item in raw:
        if isinstance(item, str):
            logins.add(item)
        elif isinstance(item, dict) and item.get("login"):
            logins.add(str(item["login"]))
    return logins


def _issue_number(issue: Issue) -> int:
    number = issue.get("number")
    if number is None:
        raise ValueError("issue missing number")
    return int(number)


def work_for_today_counts(
    issues: list[Issue],
    login: str,
    label: str,
) -> tuple[int, int]:
    """Return ``(open_with_label, assigned_to_me)`` for the readiness label."""
    with_label = 0
    assigned_to_me = 0
    for issue in issues:
        if not _issue_state_open(issue):
            continue
        if label not in _label_names(issue):
            continue
        with_label += 1
        if login in _assignee_logins(issue):
            assigned_to_me += 1
    return with_label, assigned_to_me


def candidates_assigned(
    issues: list[Issue],
    login: str,
    label: str,
) -> list[Issue]:
    """Open issues with ``label`` assigned to ``login`` (before blockedBy)."""
    out: list[Issue] = []
    for issue in issues:
        if not _issue_state_open(issue):
            continue
        if label not in _label_names(issue):
            continue
        if login not in _assignee_logins(issue):
            continue
        out.append(issue)
    return out


def _blocker_is_open(blocker: Blocker) -> bool:
    state = blocker.get("state")
    if state is None:
        return True
    return str(state).upper() == "OPEN"


def eligible_after_blocked_by(
    candidates: list[Issue],
    blocked_by_map: BlockedByMap,
) -> list[Issue]:
    """Drop candidates with any open blocker in ``blocked_by_map``."""
    eligible: list[Issue] = []
    for issue in candidates:
        number = _issue_number(issue)
        blockers = blocked_by_map.get(number) or []
        if any(_blocker_is_open(b) for b in blockers):
            continue
        eligible.append(issue)
    return eligible


def sort_key(issue: Issue) -> tuple[int, int]:
    """Sort: ``important`` first, then ascending issue number."""
    important = 0 if "important" in _label_names(issue) else 1
    return important, _issue_number(issue)


def planned_queue(
    candidates: list[Issue],
    blocked_by_map: BlockedByMap,
) -> list[Issue]:
    """Eligible issues in driver order (important first, then issue number)."""
    eligible = eligible_after_blocked_by(candidates, blocked_by_map)
    return sorted(eligible, key=sort_key)


def pick_next(
    candidates: list[Issue],
    blocked_by_map: BlockedByMap,
) -> Issue | None:
    """Next eligible issue in sort order, or ``None``."""
    planned = planned_queue(candidates, blocked_by_map)
    return planned[0] if planned else None


# Issue number -> (tab number, tab_id) of its open ``issue-N`` tab; lower sorts older.
OpenTabs = dict[int, tuple[int, str]]

_NO_TAB_NUMBER = sys.maxsize


def open_tabs_by_issue(
    issue_tabs: list[tuple[str, int, int]],
    closed: set[str] | None = None,
) -> OpenTabs:
    """Map issue number to its oldest open tab key, skipping tab ids in ``closed``."""
    found: OpenTabs = {}
    for tab_id, number, tab_number in issue_tabs:
        if closed and tab_id in closed:
            continue
        key = (tab_number, tab_id)
        if number not in found or key < found[number]:
            found[number] = key
    return found


def pick_next_resume_first(
    planned: list[Issue],
    open_tabs: OpenTabs,
) -> tuple[Issue | None, list[Issue]]:
    """Choose the next ticket, resuming an in-progress one before starting new work.

    In-progress means a planned issue with an open ``issue-N`` tab. Returns
    ``(choice, in_progress)``: ``in_progress`` is ordered oldest tab first
    (herdr tab ``number`` = position in the tab bar, new tabs append; ties by
    ``tab_id``; drag tabs to reprioritize), and ``choice`` is its first entry,
    else the head of the queue. Several in-progress issues print a WARNING; the
    others wait their turn and are adopted later with no new prompt.
    """
    in_progress = sorted(
        (i for i in planned if _issue_number(i) in open_tabs),
        key=lambda i: open_tabs[_issue_number(i)],
    )
    if len(in_progress) > 1:
        others = ", ".join(f"#{_issue_number(i)}" for i in in_progress[1:])
        print(
            f"WARNING: {len(in_progress)} eligible issues have an open issue-N tab; "
            f"resuming #{_issue_number(in_progress[0])} first (oldest tab); the others "
            f"({others}) wait their turn and are adopted later with no new prompt.",
            file=sys.stderr,
        )
    if in_progress:
        return in_progress[0], in_progress
    return (planned[0] if planned else None), in_progress


def warn_ineligible_open_tabs(
    planned: list[Issue],
    open_tabs: Collection[int],
    warned: set[int],
) -> None:
    """WARN once per issue number about an ``issue-N`` tab outside the eligible queue.

    Such a tab (label or assignee removed, newly blocked) does not hold the
    queue; ``warned`` carries the numbers already reported this driver run.
    """
    planned_numbers = {_issue_number(i) for i in planned}
    for number in sorted(set(open_tabs) - planned_numbers - warned):
        print(
            f"WARNING: issue-{number} tab open but #{number} is not in the eligible "
            "queue (closed, unlabeled, unassigned, or blocked); close the tab or "
            "restore label/assignee.",
            file=sys.stderr,
        )
        warned.add(number)


def advance_ready(merge_info: MergeInfo, check_runs: list[CheckRun]) -> bool:
    """True when linked PR is merged and every observed post-merge check run is green (α)."""
    if not merge_info.get("merged"):
        return False
    if not check_runs:
        return False
    return all(_check_run_bucket(run) == "green" for run in check_runs)


def _check_run_bucket(run: CheckRun) -> str:
    """Classify one check run as ``green``, ``pending``, or ``failed``."""
    if str(run.get("status") or "").lower() != "completed":
        return "pending"
    conclusion = run.get("conclusion")
    if conclusion is not None and str(conclusion).lower() in _GREEN_CONCLUSIONS:
        return "green"
    return "failed"


def closed_without_merge_reason(status: IssueAdvanceStatus) -> str | None:
    """Advance reason when the issue is CLOSED and no merged PR closes it; else ``None``.

    A merged closing PR auto-closes the issue too, so that case stays on α
    (``advance_ready``) and never short-circuits here.
    """
    if status["merge_info"].get("merged"):
        return None
    if str(status.get("issue_state") or "").upper() != "CLOSED":
        return None
    state_reason = status.get("state_reason") or "UNKNOWN"
    return f"closed: {state_reason}, no merged closing PR; CI gate skipped"


def format_advance_poll_line(
    status: IssueAdvanceStatus,
    poll_seconds: int,
    *,
    worker_gone: bool = False,
) -> str:
    """One stdout line per not-yet-advanced GitHub poll in the α wait loop."""
    number = status["issue_number"]
    merge_info = status["merge_info"]
    check_runs = status["check_runs"]
    if not merge_info.get("merged"):
        line = f"#{number} open; no merged PR closes it yet"
    else:
        pr = merge_info.get("pr_number")
        prefix = f"#{number}: PR #{pr} merged" if pr else f"#{number}: closing PR merged"
        if not check_runs:
            line = f"{prefix}; no check runs yet on the merge commit"
        else:
            buckets = [_check_run_bucket(run) for run in check_runs]
            extras = [
                f"{buckets.count(kind)} {kind}"
                for kind in ("failed", "pending")
                if buckets.count(kind)
            ]
            extra = f" ({', '.join(extras)})" if extras else ""
            line = (
                f"{prefix}; post-merge CI {buckets.count('green')}/{len(buckets)} "
                f"green{extra}"
            )
    gone = " (worker gone)" if worker_gone else ""
    return f"{line} — waiting {poll_seconds}s{gone}"


def default_run_gh(argv: list[str]) -> subprocess.CompletedProcess[str]:
    """Run ``gh`` with cwd at the repository root (injectable for tests)."""
    return subprocess.run(
        argv,
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def _gh_check(proc: subprocess.CompletedProcess[str], context: str) -> None:
    if proc.returncode == 0:
        return
    detail = (proc.stderr or proc.stdout or "").strip()
    raise RuntimeError(f"{context} failed (exit {proc.returncode}): {detail}")


def _gh_json(proc: subprocess.CompletedProcess[str], context: str) -> Any:
    _gh_check(proc, context)
    try:
        return json.loads(proc.stdout or "null")
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{context}: invalid JSON from gh") from exc


def _gh_json_slurp_pages(proc: subprocess.CompletedProcess[str], context: str) -> list[Any]:
    """Parse ``gh api --paginate --slurp`` stdout (JSON array of per-page objects)."""
    _gh_check(proc, context)
    try:
        payload = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{context}: invalid JSON from gh") from exc
    if not isinstance(payload, list):
        raise RuntimeError(f"{context}: expected slurp array from gh")
    return payload


def parse_owner_name(repo: str) -> tuple[str, str]:
    if "/" not in repo:
        raise ValueError(f"repo must be owner/name, got {repo!r}")
    owner, name = repo.split("/", 1)
    if not owner or not name:
        raise ValueError(f"repo must be owner/name, got {repo!r}")
    return owner, name


def fetch_viewer_login(run_gh: RunGh = default_run_gh) -> str:
    """Resolve authenticated viewer login via ``gh api user``."""
    proc = run_gh(["gh", "api", "user"])
    data = _gh_json(proc, "gh api user")
    login = data.get("login") if isinstance(data, dict) else None
    if not login:
        raise RuntimeError("gh api user: missing login in response")
    return str(login)


def resolve_repo(repo: str | None, run_gh: RunGh = default_run_gh) -> str:
    """Return ``owner/name``; default from ``gh repo view`` when omitted."""
    if repo:
        return repo
    proc = run_gh(["gh", "repo", "view", "--json", "nameWithOwner"])
    data = _gh_json(proc, "gh repo view")
    name_with_owner = data.get("nameWithOwner") if isinstance(data, dict) else None
    if not name_with_owner:
        raise RuntimeError("gh repo view: missing nameWithOwner")
    return str(name_with_owner)


def list_labeled_open_issues(
    repo: str,
    label: str,
    run_gh: RunGh = default_run_gh,
) -> list[Issue]:
    """One ``gh issue list`` call: open issues with ``label``."""
    proc = run_gh(
        [
            "gh",
            "issue",
            "list",
            "--repo",
            repo,
            "--label",
            label,
            "--state",
            "open",
            "--json",
            _ISSUE_LIST_JSON_FIELDS,
        ],
    )
    data = _gh_json(proc, "gh issue list")
    if not isinstance(data, list):
        raise RuntimeError("gh issue list: expected JSON array")
    return data


def _blocked_by_graphql_query(issue_numbers: list[int]) -> str:
    fields = "\n".join(
        (
            f"    issue_{n}: issue(number: {n}) {{"
            f" number blockedBy(first: 100) {{ nodes {{ number state }} }} }}"
            for n in issue_numbers
        ),
    )
    return (
        "query($owner: String!, $name: String!) {\n"
        "  repository(owner: $owner, name: $name) {\n"
        f"{fields}\n"
        "  }\n"
        "}"
    )


def fetch_blocked_by_map(
    repo: str,
    issue_numbers: list[int],
    run_gh: RunGh = default_run_gh,
) -> BlockedByMap:
    """Batched GraphQL ``blockedBy`` for candidate issue numbers only."""
    if not issue_numbers:
        return {}
    owner, name = parse_owner_name(repo)
    query = _blocked_by_graphql_query(issue_numbers)
    proc = run_gh(
        [
            "gh",
            "api",
            "graphql",
            "-f",
            f"query={query}",
            "-f",
            f"owner={owner}",
            "-f",
            f"name={name}",
        ],
    )
    payload = _gh_json(proc, "gh api graphql (blockedBy)")
    if not isinstance(payload, dict):
        raise RuntimeError("blockedBy GraphQL: expected object response")
    errors = payload.get("errors")
    if errors:
        raise RuntimeError(f"blockedBy GraphQL errors: {errors}")
    data = payload.get("data") or {}
    repository = data.get("repository") if isinstance(data, dict) else None
    if not isinstance(repository, dict):
        raise RuntimeError("blockedBy GraphQL: missing repository data")

    blocked_map: BlockedByMap = {}
    for number in issue_numbers:
        alias = f"issue_{number}"
        issue_node = repository.get(alias)
        if not issue_node:
            blocked_map[number] = []
            continue
        raw_nodes = (issue_node.get("blockedBy") or {}).get("nodes") or []
        blockers: list[Blocker] = []
        for node in raw_nodes:
            if not isinstance(node, dict):
                continue
            blockers.append(
                {
                    "number": node.get("number"),
                    "state": node.get("state"),
                },
            )
        blocked_map[number] = blockers
    return blocked_map


def _issue_states_graphql_query(issue_numbers: list[int]) -> str:
    fields = "\n".join(
        f"    issue_{n}: issue(number: {n}) {{ number state }}" for n in issue_numbers
    )
    return (
        "query($owner: String!, $name: String!) {\n"
        "  repository(owner: $owner, name: $name) {\n"
        f"{fields}\n"
        "  }\n"
        "}"
    )


def fetch_issue_states(
    repo: str,
    issue_numbers: list[int],
    run_gh: RunGh = default_run_gh,
) -> dict[int, str]:
    """Batched GraphQL ``state`` (``OPEN``/``CLOSED``) for ``issue_numbers``.

    Numbers GitHub cannot resolve as issues (deleted, a PR number) come back as
    null aliases with per-alias errors (``gh`` then exits 1 even though ``data``
    is partial); they are omitted from the result rather than failing the whole
    batch. Raises only when stdout is not JSON or has no ``data.repository``.
    """
    if not issue_numbers:
        return {}
    owner, name = parse_owner_name(repo)
    query = _issue_states_graphql_query(issue_numbers)
    proc = run_gh(
        [
            "gh",
            "api",
            "graphql",
            "-f",
            f"query={query}",
            "-f",
            f"owner={owner}",
            "-f",
            f"name={name}",
        ],
    )
    context = "gh api graphql (issue states)"
    if proc.returncode == 0:
        payload = _gh_json(proc, context)
    else:
        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError:
            payload = None
        if not isinstance(payload, dict):
            _gh_check(proc, context)
    data = payload.get("data") if isinstance(payload, dict) else None
    repository = data.get("repository") if isinstance(data, dict) else None
    if not isinstance(repository, dict):
        errors = payload.get("errors") if isinstance(payload, dict) else None
        raise RuntimeError(f"issue states GraphQL: missing repository data ({errors})")
    states: dict[int, str] = {}
    for number in issue_numbers:
        node = repository.get(f"issue_{number}")
        if isinstance(node, dict) and node.get("state"):
            states[number] = str(node["state"]).upper()
    return states


def _merge_status_graphql_query() -> str:
    """GraphQL for issue state + closing PRs; uses ``$number`` (must match ``-F number=``)."""
    return (
        "query($owner: String!, $name: String!, $number: Int!) {\n"
        "  repository(owner: $owner, name: $name) {\n"
        "    defaultBranchRef { name }\n"
        "    issue(number: $number) {\n"
        "      state stateReason\n"
        "      closedByPullRequestsReferences(first: 10, includeClosedPrs: true) {\n"
        "        nodes {\n"
        "          number\n"
        "          merged\n"
        "          baseRefName\n"
        "          mergeCommit { oid }\n"
        "        }\n"
        "      }\n"
        "    }\n"
        "  }\n"
        "}"
    )


def _pick_merged_pr_node(
    nodes: list[dict[str, Any]],
    default_branch: str | None,
) -> dict[str, Any] | None:
    merged = [n for n in nodes if n.get("merged")]
    if not merged:
        return None
    if default_branch:
        for node in merged:
            if node.get("baseRefName") == default_branch:
                return node
    return merged[0]


def fetch_issue_merge_and_ci_status(
    repo: str,
    issue_number: int,
    run_gh: RunGh = default_run_gh,
) -> IssueAdvanceStatus:
    """Fetch issue state, merge, and post-merge check-run shapes for the wait loop.

    ``issue_state`` / ``state_reason`` feed ``closed_without_merge_reason``;
    ``merge_info`` / ``check_runs`` feed ``advance_ready`` (α). Not used by
    ``--dry-run``.
    """
    owner, name = parse_owner_name(repo)
    merge_info: MergeInfo = {
        "merged": False,
        "merge_commit_sha": None,
        "pr_number": None,
    }
    check_runs: list[CheckRun] = []
    issue_state: str | None = None
    state_reason: str | None = None

    merge_query = _merge_status_graphql_query()
    merge_proc = run_gh(
        [
            "gh",
            "api",
            "graphql",
            "-f",
            f"query={merge_query}",
            "-f",
            f"owner={owner}",
            "-f",
            f"name={name}",
            "-F",
            f"number={issue_number}",
        ],
    )
    merge_payload = _gh_json(merge_proc, f"gh api graphql (merge status #{issue_number})")
    if isinstance(merge_payload, dict):
        errors = merge_payload.get("errors")
        if errors:
            raise RuntimeError(f"merge status GraphQL errors: {errors}")
        data = merge_payload.get("data") or {}
        repository = data.get("repository") if isinstance(data, dict) else None
        if isinstance(repository, dict):
            default_branch_ref = repository.get("defaultBranchRef") or {}
            default_branch = (
                default_branch_ref.get("name")
                if isinstance(default_branch_ref, dict)
                else None
            )
            issue_node = repository.get("issue")
            if isinstance(issue_node, dict):
                issue_state = issue_node.get("state")
                state_reason = issue_node.get("stateReason")
                refs = issue_node.get("closedByPullRequestsReferences") or {}
                raw_nodes = refs.get("nodes") if isinstance(refs, dict) else None
                nodes = [n for n in (raw_nodes or []) if isinstance(n, dict)]
                picked = _pick_merged_pr_node(nodes, str(default_branch) if default_branch else None)
                if picked:
                    merge_info["merged"] = True
                    merge_info["pr_number"] = picked.get("number")
                    merge_commit = picked.get("mergeCommit") or {}
                    if isinstance(merge_commit, dict):
                        merge_info["merge_commit_sha"] = merge_commit.get("oid")

    sha = merge_info.get("merge_commit_sha")
    if sha:
        checks_proc = run_gh(
            [
                "gh",
                "api",
                f"repos/{owner}/{name}/commits/{sha}/check-runs",
                "--paginate",
                "--slurp",
            ],
        )
        pages = _gh_json_slurp_pages(
            checks_proc,
            f"check-runs for issue #{issue_number}",
        )
        raw_runs: list[Any] = []
        for page in pages:
            if not isinstance(page, dict):
                continue
            page_runs = page.get("check_runs") or []
            if isinstance(page_runs, list):
                raw_runs.extend(page_runs)
        for row in raw_runs:
            if not isinstance(row, dict):
                continue
            check_runs.append(
                {
                    "name": row.get("name"),
                    "status": row.get("status"),
                    "conclusion": row.get("conclusion"),
                },
            )

    return {
        "issue_number": issue_number,
        "issue_state": issue_state,
        "state_reason": state_reason,
        "merge_info": merge_info,
        "check_runs": check_runs,
    }


def format_queue_counts_line(
    open_with_label: int,
    assigned_to_me: int,
    label: str,
    login: str,
) -> str:
    """One-line work-for-today counts (startup and ``--dry-run``)."""
    return (
        f"{open_with_label} with {label!r} label, "
        f"{assigned_to_me} is assigned on {login!r}"
    )


def format_loop_params_line(
    *,
    poll_seconds: int,
    agent_kind: str,
    once: bool,
) -> str:
    """Startup line describing how this driver invocation will behave."""
    mode = "once" if once else "loop"
    return (
        f"params: poll-seconds={poll_seconds}; agent-kind={agent_kind}; mode={mode}"
    )


def format_worker_opened_line(
    *,
    tab_label: str,
    issue_number: int,
    title: str,
    adopted: str | None = None,
    opened_at: datetime | None = None,
) -> str:
    """Confirm herdr tab open (or adopted by ``tab_id``) for a GitHub issue."""
    when = (opened_at or datetime.now()).strftime("%H:%M:%S")
    title_bit = f" {title}" if title else ""
    verb = f"adopted ({adopted}, no new prompt; close it to restart)" if adopted else "opened"
    return (
        f"{tab_label} herdr tab {verb} for #{issue_number} gh issue"
        f"{title_bit} at {when}"
    )


def format_planned_issue_line(issue: Issue, *, index: int, in_progress: bool = False) -> str:
    """One numbered planned-queue line for dry-run / startup."""
    number = _issue_number(issue)
    title = str(issue.get("title") or "")
    url = str(issue.get("url") or "")
    marker = " (in progress, tab open)" if in_progress else ""
    return f"  {index}. #{number} {title} {url}".rstrip() + marker


def format_workspace_line(workspace: str | None) -> str:
    """Startup line naming the herdr workspace tabs are scoped to."""
    return f"herdr workspace: {workspace or 'unscoped'}"


def format_dry_run_lines(
    *,
    login: str,
    repo: str,
    label: str,
    open_with_label: int,
    assigned_to_me: int,
    planned: list[Issue],
    in_progress: list[Issue] | None = None,
    herdr_unavailable: str | None = None,
    workspace: str | None = None,
) -> list[str]:
    """Dry-run summary: workspace, counts, planned queue (in-progress first), ``next:``.

    ``in_progress`` lists planned issues with an open ``issue-N`` tab, oldest
    tab first. ``herdr_unavailable`` (a short reason) prints one ``in-progress:
    unknown`` line; the queue then stays in plain driver order.
    """
    in_progress = in_progress or []
    lines = [
        f"repo: {repo}",
        format_workspace_line(workspace),
        format_queue_counts_line(open_with_label, assigned_to_me, label, login),
    ]
    if herdr_unavailable is not None:
        lines.append(f"in-progress: unknown (herdr unavailable: {herdr_unavailable})")
    if not planned:
        lines.append("planned: none")
        lines.append("next: none")
        return lines
    resumed = {_issue_number(i) for i in in_progress}
    ordered = in_progress + [i for i in planned if _issue_number(i) not in resumed]
    lines.append(f"planned ({len(ordered)}):")
    for idx, issue in enumerate(ordered, start=1):
        lines.append(
            format_planned_issue_line(
                issue, index=idx, in_progress=_issue_number(issue) in resumed
            )
        )
    next_issue = ordered[0]
    number = _issue_number(next_issue)
    title = str(next_issue.get("title") or "")
    url = str(next_issue.get("url") or "")
    lines.append(f"next: #{number} {title} {url}".rstrip())
    return lines


@dataclass
class WorkerHandle:
    """References for one herdr worker tab (serial N=1)."""

    tab_id: str
    pane_id: str
    issue_number: int
    issue_url: str
    adopted: bool = False
    gone: bool = False
    warned_gone: bool = False


def default_run_herdr(argv: list[str]) -> subprocess.CompletedProcess[str]:
    """Run ``herdr`` with cwd at the repository root (injectable for tests)."""
    return subprocess.run(
        argv,
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


# herdr subcommands that default to the UI-active workspace unless told otherwise.
_WORKSPACE_SCOPED_COMMANDS = (("tab", "create"), ("tab", "list"))


def scope_run_herdr(run_herdr: RunHerdr, workspace: str | None) -> RunHerdr:
    """Pin ``tab create`` / ``tab list`` to ``workspace`` (``None`` leaves argv unchanged).

    Without ``--workspace`` herdr creates tabs in whichever workspace is active
    in the UI and lists tabs from every workspace, so worker tabs land beside
    unrelated work and another workspace's ``issue-N`` tab could be adopted or
    closed.
    """
    if not workspace:
        return run_herdr

    def scoped(argv: list[str]) -> subprocess.CompletedProcess[str]:
        if tuple(argv[1:3]) in _WORKSPACE_SCOPED_COMMANDS:
            argv = [*argv[:3], "--workspace", workspace, *argv[3:]]
        return run_herdr(argv)

    return scoped


def resolve_workspace(cli_workspace: str | None, *, dry_run: bool = False) -> str | None:
    """``--workspace``, else the driver pane's ``HERDR_WORKSPACE_ID``; warn when neither is set."""
    workspace = cli_workspace or os.environ.get("HERDR_WORKSPACE_ID") or None
    if workspace is None:
        effect = (
            "tabs from every workspace are listed"
            if dry_run
            else "worker tabs open in the UI-active workspace and tabs from every "
            "workspace are considered"
        )
        print(
            "WARNING: no herdr workspace (not running inside herdr and no --workspace); "
            f"{effect}.",
            file=sys.stderr,
        )
    return workspace


def parse_herdr_response(proc: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    """Parse JSON stdout from herdr CLI (single object per invocation)."""
    raw = (proc.stdout or "").strip()
    if not raw:
        return {"error": {"code": "empty_stdout", "message": "herdr produced no stdout"}}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {
            "error": {
                "code": "invalid_json",
                "message": (raw[:240] + "…") if len(raw) > 240 else raw,
            },
        }
    if isinstance(payload, dict):
        return payload
    return {"error": {"code": "unexpected_shape", "message": "expected JSON object"}}


def herdr_error_code(payload: dict[str, Any]) -> str | None:
    err = payload.get("error")
    if isinstance(err, dict) and err.get("code"):
        return str(err["code"])
    return None


def herdr_worker_disappeared(payload: dict[str, Any]) -> bool:
    code = herdr_error_code(payload)
    return bool(code and code in _WORKER_GONE_ERROR_CODES)


def _herdr_require_ok(
    proc: subprocess.CompletedProcess[str],
    context: str,
) -> dict[str, Any]:
    payload = parse_herdr_response(proc)
    code = herdr_error_code(payload)
    if code:
        message = ""
        err = payload.get("error")
        if isinstance(err, dict):
            message = str(err.get("message") or "")
        detail = message or (proc.stderr or "").strip()
        raise RuntimeError(f"{context} failed ({code}): {detail}")
    return payload


def _strip_yaml_frontmatter(text: str) -> str:
    if not text.startswith("---"):
        return text
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return text
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            return "".join(lines[idx + 1 :])
    return text


def load_skill_text(skill_path: Path | None = None) -> str:
    """Load driver-injected skill body (YAML frontmatter stripped); fallback when absent."""
    path = skill_path if skill_path is not None else REPO_ROOT / _SKILL_REL
    if path.is_file():
        return _strip_yaml_frontmatter(path.read_text(encoding="utf-8"))
    return _MINIMAL_SKILL_FALLBACK


def build_worker_prompt(skill_text: str, issue_url: str) -> str:
    """Inline skill plus the one-ticket issue URL for ``herdr agent prompt``."""
    url = issue_url.strip()
    return f"{skill_text.rstrip()}\n\n---\nDeliver this issue only:\n{url}\n"


def format_worker_gone_warning(
    issue_number: int,
    issue_url: str,
    label: str,
) -> str:
    """Restore instructions when the worker tab/agent vanishes before α."""
    return (
        f"WARNING: worker for issue #{issue_number} disappeared before "
        f"merge+CI advance (α).\n"
        f"  Issue: {issue_url}\n"
        f"  Restore: if the issue-{issue_number} tab is still open, restart the agent "
        "there and continue delivery (a driver re-run adopts that tab); if you "
        "closed it, press Ctrl+C and re-run the driver to start a fresh worker.\n"
        f"    python3 scripts/loop_ready_issue_herdr.py --label {label}\n"
        "  (add --once for a single ticket). Ctrl+C stops the driver loop.\n"
        f"  The driver keeps polling GitHub for α on #{issue_number} until advance "
        "or you stop."
    )


def spawn_worker_for_issue(
    issue: Issue,
    *,
    agent_kind: str,
    repo_root: Path = REPO_ROOT,
    run_herdr: RunHerdr = default_run_herdr,
    skill_path: Path | None = None,
) -> WorkerHandle:
    """``tab create`` → ``agent start`` → ``agent prompt`` for one issue."""
    number = _issue_number(issue)
    issue_url = str(issue.get("url") or "")
    tab_label = f"issue-{number}"
    agent_name = f"issue-{number}"

    create_proc = run_herdr(
        [
            "herdr",
            "tab",
            "create",
            "--cwd",
            str(repo_root),
            "--label",
            tab_label,
            "--no-focus",
        ],
    )
    create_payload = _herdr_require_ok(create_proc, "herdr tab create")
    result = create_payload.get("result")
    if not isinstance(result, dict):
        raise RuntimeError("herdr tab create: missing result")
    root_pane = result.get("root_pane")
    tab = result.get("tab")
    if not isinstance(root_pane, dict) or not isinstance(tab, dict):
        raise RuntimeError("herdr tab create: missing root_pane or tab")
    pane_id = root_pane.get("pane_id")
    tab_id = tab.get("tab_id")
    if not pane_id or not tab_id:
        raise RuntimeError("herdr tab create: missing pane_id or tab_id")

    start_proc = run_herdr(
        [
            "herdr",
            "agent",
            "start",
            agent_name,
            "--kind",
            agent_kind,
            "--pane",
            str(pane_id),
        ],
    )
    _herdr_require_ok(start_proc, "herdr agent start")

    prompt_text = build_worker_prompt(load_skill_text(skill_path), issue_url)
    prompt_proc = run_herdr(
        ["herdr", "agent", "prompt", str(pane_id), prompt_text],
    )
    _herdr_require_ok(prompt_proc, "herdr agent prompt")

    return WorkerHandle(
        tab_id=str(tab_id),
        pane_id=str(pane_id),
        issue_number=number,
        issue_url=issue_url,
    )


def _list_tab_records(run_herdr: RunHerdr = default_run_herdr) -> list[dict[str, Any]]:
    """One ``herdr tab list``; raise ``RuntimeError`` on a herdr error."""
    proc = run_herdr(["herdr", "tab", "list"])
    payload = parse_herdr_response(proc)
    code = herdr_error_code(payload)
    if code:
        message = ""
        err = payload.get("error")
        if isinstance(err, dict):
            message = str(err.get("message") or "")
        detail = message or (proc.stderr or "").strip()
        raise RuntimeError(f"herdr tab list failed ({code}): {detail}")
    result = payload.get("result")
    tabs = result.get("tabs") if isinstance(result, dict) else None
    if not isinstance(tabs, list):
        return []
    return [tab for tab in tabs if isinstance(tab, dict) and tab.get("tab_id")]


def list_tabs_with_label(
    label: str,
    run_herdr: RunHerdr = default_run_herdr,
) -> list[str]:
    """Return ``tab_id`` values whose herdr label matches ``label``."""
    return [
        str(tab["tab_id"])
        for tab in _list_tab_records(run_herdr)
        if str(tab.get("label") or "") == label
    ]


def list_issue_tabs(
    run_herdr: RunHerdr = default_run_herdr,
) -> list[tuple[str, int, int]]:
    """Return ``(tab_id, N, tab_number)`` for every herdr tab labeled exactly ``issue-N``.

    ``tab_number`` is herdr's tab ``number`` (tab bar position, lower = started
    earlier); a tab without one sorts last.
    """
    found: list[tuple[str, int, int]] = []
    for tab in _list_tab_records(run_herdr):
        match = _ISSUE_TAB_LABEL_RE.match(str(tab.get("label") or ""))
        if match:
            raw_number = tab.get("number")
            tab_number = raw_number if isinstance(raw_number, int) else _NO_TAB_NUMBER
            found.append((str(tab["tab_id"]), int(match.group(1)), tab_number))
    return found


def close_tab_id(
    tab_id: str,
    run_herdr: RunHerdr = default_run_herdr,
) -> None:
    """Close one herdr tab; ``tab_not_found`` is a no-op success."""
    proc = run_herdr(["herdr", "tab", "close", tab_id])
    payload = parse_herdr_response(proc)
    code = herdr_error_code(payload)
    if code in _TAB_ALREADY_CLOSED_CODES:
        return
    if code:
        message = ""
        err = payload.get("error")
        if isinstance(err, dict):
            message = str(err.get("message") or "")
        detail = message or (proc.stderr or "").strip()
        raise RuntimeError(f"herdr tab close failed ({code}): {detail}")


def close_worker_tab(
    worker: WorkerHandle,
    run_herdr: RunHerdr = default_run_herdr,
) -> None:
    """Close the worker tab after α — even when the agent already disappeared.

    ``worker.gone`` only means stop polling ``herdr agent wait``; the tab often
    remains (idle) and must still be closed on advance.
    """
    close_tab_id(worker.tab_id, run_herdr)
    # Best-effort: close any other tabs still labeled issue-N (stale restarts).
    tab_label = f"issue-{worker.issue_number}"
    try:
        leftovers = list_tabs_with_label(tab_label, run_herdr)
    except RuntimeError as exc:
        print(f"WARNING: could not list tabs to sweep {tab_label!r}: {exc}", file=sys.stderr)
        return
    for tab_id in leftovers:
        if tab_id == worker.tab_id:
            continue
        try:
            close_tab_id(tab_id, run_herdr)
        except RuntimeError as exc:
            print(
                f"WARNING: could not close leftover tab {tab_id} ({tab_label}): {exc}",
                file=sys.stderr,
            )


def list_issue_tabs_or_warn(
    run_herdr: RunHerdr = default_run_herdr,
) -> list[tuple[str, int, int]] | None:
    """``list_issue_tabs``, or ``None`` after a WARNING when herdr fails to list tabs."""
    try:
        return list_issue_tabs(run_herdr)
    except RuntimeError as exc:
        print(f"WARNING: closed-issue tab sweep skipped: {exc}", file=sys.stderr)
        return None


def close_tabs_for_closed_issues(
    repo: str,
    run_gh: RunGh = default_run_gh,
    run_herdr: RunHerdr = default_run_herdr,
    *,
    issue_tabs: list[tuple[str, int, int]] | None = None,
) -> list[str]:
    """Close every ``issue-N`` herdr tab whose GitHub issue is CLOSED; return closed tab ids.

    ``issue_tabs`` reuses a ``list_issue_tabs`` result from this queue cycle;
    when omitted the sweep lists tabs itself. Best-effort: a herdr list,
    GraphQL, or single-close failure prints a WARNING and is skipped. A tab
    whose issue GitHub does not return is left alone.
    """
    if issue_tabs is None:
        issue_tabs = list_issue_tabs_or_warn(run_herdr)
        if issue_tabs is None:
            return []
    if not issue_tabs:
        return []
    numbers = sorted({number for _, number, _ in issue_tabs})
    try:
        states = fetch_issue_states(repo, numbers, run_gh)
    except RuntimeError as exc:
        print(f"WARNING: closed-issue tab sweep skipped: {exc}", file=sys.stderr)
        return []
    closed: list[str] = []
    for tab_id, number, _ in issue_tabs:
        if states.get(number) != "CLOSED":
            continue
        try:
            close_tab_id(tab_id, run_herdr)
        except RuntimeError as exc:
            print(
                f"WARNING: could not close herdr tab issue-{number} ({tab_id}): {exc}",
                file=sys.stderr,
            )
            continue
        print(f"Closed herdr tab issue-{number} ({tab_id}): #{number} is closed.")
        closed.append(tab_id)
    return closed


def list_tab_panes(
    tab_id: str,
    run_herdr: RunHerdr = default_run_herdr,
) -> list[dict[str, Any]]:
    """Return herdr pane records that belong to ``tab_id``."""
    payload = _herdr_require_ok(run_herdr(["herdr", "pane", "list"]), "herdr pane list")
    result = payload.get("result")
    panes = result.get("panes") if isinstance(result, dict) else None
    if not isinstance(panes, list):
        return []
    return [p for p in panes if isinstance(p, dict) and p.get("tab_id") == tab_id]


def adopt_existing_worker(
    issue: Issue,
    run_herdr: RunHerdr = default_run_herdr,
) -> WorkerHandle | None:
    """Reuse an open ``issue-N`` tab instead of restarting delivery from scratch.

    A tab labeled ``issue-N`` means a worker already owns the ticket (e.g. a
    herdr session restored after reboot, or a driver restart). The driver
    resumes polling for α against it and sends no new prompt. Close the tab by
    hand to make the driver start a fresh worker.
    """
    number = _issue_number(issue)
    tab_label = f"issue-{number}"
    try:
        tab_ids = list_tabs_with_label(tab_label, run_herdr)
    except RuntimeError as exc:
        raise RuntimeError(
            f"cannot check for an open {tab_label} tab ({exc}); "
            "refusing to spawn a possible duplicate worker"
        ) from exc
    if not tab_ids:
        return None
    if len(tab_ids) > 1:
        print(
            f"WARNING: {len(tab_ids)} herdr tabs labeled {tab_label} "
            f"({', '.join(tab_ids)}); adopting {tab_ids[0]}; the others are closed "
            "when the issue advances.",
            file=sys.stderr,
        )
    tab_id = tab_ids[0]
    panes = list_tab_panes(tab_id, run_herdr)
    # Prefer the pane running an agent; a bare shell pane still lets α polling work.
    panes.sort(key=lambda p: not p.get("agent"))
    if not panes or not panes[0].get("pane_id"):
        raise RuntimeError(f"herdr tab {tab_id} ({tab_label}) has no panes to adopt")
    return WorkerHandle(
        tab_id=tab_id,
        pane_id=str(panes[0]["pane_id"]),
        issue_number=number,
        issue_url=str(issue.get("url") or ""),
        adopted=True,
    )


_MAX_CONSECUTIVE_FETCH_FAILURES = 5


def wait_until_ticket_advanced(
    repo: str,
    worker: WorkerHandle,
    poll_seconds: int,
    *,
    label: str,
    run_gh: RunGh = default_run_gh,
    run_herdr: RunHerdr = default_run_herdr,
    sleep_fn: SleepFn = time.sleep,
    fetch_status: Callable[
        [str, int, RunGh],
        IssueAdvanceStatus,
    ] = fetch_issue_merge_and_ci_status,
) -> str:
    """Block until ``worker``'s issue advances; return the advance reason.

    Order per poll: a merged closing PR waits for α (non-empty, all-green
    post-merge CI) even though GitHub already auto-closed the issue; otherwise a
    CLOSED issue advances at once (CI gate skipped); otherwise keep waiting and
    print one status line. ``herdr agent wait`` is interleaved while the worker
    is live.
    """
    if poll_seconds < 1:
        raise ValueError("poll_seconds must be >= 1")
    timeout_ms = poll_seconds * 1000
    consecutive_fetch_failures = 0

    while True:
        try:
            status = fetch_status(repo, worker.issue_number, run_gh)
        except RuntimeError as exc:
            consecutive_fetch_failures += 1
            print(
                f"GitHub advance poll for #{worker.issue_number} failed "
                f"({consecutive_fetch_failures}/{_MAX_CONSECUTIVE_FETCH_FAILURES}): "
                f"{exc}\n"
                f"  Worker for #{worker.issue_number} keeps running — the driver only "
                f"uses this poll to decide when to start the *next* ticket; retrying "
                f"in {poll_seconds}s.",
                file=sys.stderr,
            )
            if consecutive_fetch_failures >= _MAX_CONSECUTIVE_FETCH_FAILURES:
                raise
            sleep_fn(poll_seconds)
            continue
        consecutive_fetch_failures = 0

        if advance_ready(status["merge_info"], status["check_runs"]):
            return ADVANCE_REASON_MERGED
        closed_reason = closed_without_merge_reason(status)
        if closed_reason:
            return closed_reason
        print(format_advance_poll_line(status, poll_seconds, worker_gone=worker.gone))

        if not worker.gone:
            wait_proc = run_herdr(
                [
                    "herdr",
                    "agent",
                    "wait",
                    worker.pane_id,
                    "--timeout",
                    str(timeout_ms),
                ],
            )
            wait_payload = parse_herdr_response(wait_proc)
            if herdr_worker_disappeared(wait_payload):
                worker.gone = True
                if not worker.warned_gone:
                    print(
                        format_worker_gone_warning(
                            worker.issue_number,
                            worker.issue_url,
                            label,
                        ),
                        file=sys.stderr,
                    )
                    worker.warned_gone = True

        sleep_fn(poll_seconds)


def run_main_loop(
    label: str,
    repo: str | None,
    agent_kind: str,
    poll_seconds: int,
    once: bool,
    *,
    run_gh: RunGh = default_run_gh,
    run_herdr: RunHerdr = default_run_herdr,
    sleep_fn: SleepFn = time.sleep,
    repo_root: Path = REPO_ROOT,
    workspace: str | None = None,
) -> int:
    """Startup summary, then serial spawn → wait → advance until ``once`` or Ctrl+C.

    Each queue cycle (the first one is startup) lists herdr ``issue-N`` tabs
    once, closes those whose issue is already CLOSED on GitHub, then resumes an
    eligible issue that still has an open tab before starting new work (at most
    one ticket at a time). If the tab list fails, selection falls back to queue
    order and ``adopt_existing_worker`` still refuses to spawn a duplicate.
    Worker tabs are created in, and only looked up in, herdr ``workspace``.
    """
    run_herdr = scope_run_herdr(run_herdr, workspace)
    login = fetch_viewer_login(run_gh)
    resolved_repo = resolve_repo(repo, run_gh)

    def queue_snapshot() -> tuple[list[Issue], list[Issue], BlockedByMap]:
        issues = list_labeled_open_issues(resolved_repo, label, run_gh)
        candidates = candidates_assigned(issues, login, label)
        numbers = [_issue_number(issue) for issue in candidates]
        blocked_by_map = fetch_blocked_by_map(resolved_repo, numbers, run_gh)
        return issues, candidates, blocked_by_map

    issues, candidates, blocked_by_map = queue_snapshot()
    open_with_label, assigned_to_me = work_for_today_counts(issues, login, label)
    print(f"repo: {resolved_repo}")
    print(format_workspace_line(workspace))
    print(format_queue_counts_line(open_with_label, assigned_to_me, label, login))
    print(
        format_loop_params_line(
            poll_seconds=poll_seconds,
            agent_kind=agent_kind,
            once=once,
        ),
    )

    warned_ineligible: set[int] = set()
    try:
        while True:
            issue_tabs = list_issue_tabs_or_warn(run_herdr)
            open_tabs: OpenTabs = {}
            if issue_tabs is not None:
                closed = set(
                    close_tabs_for_closed_issues(
                        resolved_repo, run_gh, run_herdr, issue_tabs=issue_tabs
                    )
                )
                open_tabs = open_tabs_by_issue(issue_tabs, closed)
            _, candidates, blocked_by_map = queue_snapshot()
            planned = planned_queue(candidates, blocked_by_map)
            warn_ineligible_open_tabs(planned, open_tabs, warned_ineligible)
            next_issue, _ = pick_next_resume_first(planned, open_tabs)
            if next_issue is None:
                if once:
                    print(
                        f"No eligible issues assigned with label {label!r}; "
                        "exiting (--once).",
                    )
                    return 0
                print(
                    f"No eligible issues assigned with label {label!r}; "
                    f"sleeping {poll_seconds}s before re-listing.",
                )
                sleep_fn(poll_seconds)
                continue

            number = _issue_number(next_issue)
            title = str(next_issue.get("title") or "")
            worker = adopt_existing_worker(next_issue, run_herdr)
            if worker is None:
                worker = spawn_worker_for_issue(
                    next_issue,
                    agent_kind=agent_kind,
                    repo_root=repo_root,
                    run_herdr=run_herdr,
                )
            print(
                format_worker_opened_line(
                    tab_label=f"issue-{number}",
                    issue_number=number,
                    title=title,
                    adopted=worker.tab_id if worker.adopted else None,
                ),
            )
            reason = wait_until_ticket_advanced(
                resolved_repo,
                worker,
                poll_seconds,
                label=label,
                run_gh=run_gh,
                run_herdr=run_herdr,
                sleep_fn=sleep_fn,
            )
            close_worker_tab(worker, run_herdr)
            print(f"Advanced #{number} ({reason}); worker tab closed.")
            if once:
                return 0
    except KeyboardInterrupt:
        print(
            "\nloop_ready_issue_herdr: stopped by operator (Ctrl+C). "
            "In-flight workers are left open; re-running with the same --label adopts "
            "an open issue-N tab instead of restarting that ticket.",
            file=sys.stderr,
        )
        return 130


def _dry_run_open_tabs(run_herdr: RunHerdr) -> tuple[OpenTabs, str | None]:
    """Read-only ``herdr tab list`` for dry-run: ``(open tabs, None)`` or ``({}, reason)``."""
    try:
        return open_tabs_by_issue(list_issue_tabs(run_herdr)), None
    except FileNotFoundError:
        return {}, "herdr not found on PATH"
    except (OSError, RuntimeError) as exc:
        return {}, str(exc)


def run_dry_run(
    label: str,
    repo: str | None,
    run_gh: RunGh = default_run_gh,
    run_herdr: RunHerdr = default_run_herdr,
    workspace: str | None = None,
) -> list[str]:
    """Resolve gh context, list issues, pick next; return printable summary lines.

    Reads ``herdr tab list`` (read-only, scoped to ``workspace``) so in-progress
    tickets come first and ``next:`` is the resume-first choice; a herdr failure
    never fails dry-run.
    """
    run_herdr = scope_run_herdr(run_herdr, workspace)
    login = fetch_viewer_login(run_gh)
    resolved_repo = resolve_repo(repo, run_gh)
    issues = list_labeled_open_issues(resolved_repo, label, run_gh)
    open_with_label, assigned_to_me = work_for_today_counts(issues, login, label)
    candidates = candidates_assigned(issues, login, label)
    candidate_numbers = [_issue_number(issue) for issue in candidates]
    blocked_by_map = fetch_blocked_by_map(resolved_repo, candidate_numbers, run_gh)
    planned = planned_queue(candidates, blocked_by_map)
    open_tabs, herdr_unavailable = _dry_run_open_tabs(run_herdr)
    warn_ineligible_open_tabs(planned, open_tabs, set())
    _, in_progress = pick_next_resume_first(planned, open_tabs)
    return format_dry_run_lines(
        login=login,
        repo=resolved_repo,
        label=label,
        open_with_label=open_with_label,
        assigned_to_me=assigned_to_me,
        planned=planned,
        in_progress=in_progress,
        herdr_unavailable=herdr_unavailable,
        workspace=workspace,
    )


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument(
        "--label",
        required=True,
        metavar="NAME",
        help="Readiness label name (queue membership requires this label and assignee)",
    )
    ap.add_argument(
        "--repo",
        metavar="OWNER/NAME",
        help="GitHub repository (default: gh repo view from cwd)",
    )
    ap.add_argument(
        "--agent-kind",
        choices=_AGENT_KINDS,
        default="cursor",
        help="herdr worker agent kind (default: cursor)",
    )
    ap.add_argument(
        "--poll-seconds",
        type=int,
        default=300,
        metavar="SEC",
        help="GitHub merge/CI poll interval and empty-queue refresh (default: 300)",
    )
    ap.add_argument(
        "--once",
        action="store_true",
        help="Process at most one ticket then exit",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Print summary and next issue (reads herdr tab list read-only); no herdr spawn",
    )
    ap.add_argument(
        "--workspace",
        metavar="WORKSPACE_ID",
        help="herdr workspace for worker tabs and tab lookups "
        "(default: HERDR_WORKSPACE_ID of the pane running the driver)",
    )
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    workspace = resolve_workspace(args.workspace, dry_run=args.dry_run)
    if args.dry_run:
        try:
            for line in run_dry_run(args.label, args.repo, workspace=workspace):
                print(line)
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        return 0
    try:
        return run_main_loop(
            args.label,
            args.repo,
            args.agent_kind,
            args.poll_seconds,
            args.once,
            workspace=workspace,
        )
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
