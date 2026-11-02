#!/usr/bin/env python3
"""Wait until post-merge CI on ``main`` matches the herdr α gate (#296 / delivery-flow).

Workers use the same predicate as ``scripts/loop_ready_issue_herdr.py`` so
Definition of Done and driver advance stay aligned.

    python3 scripts/wait_post_merge_ci.py --issue 355 --repo OWNER/NAME
    python3 scripts/wait_post_merge_ci.py --pr 380
    python3 scripts/wait_post_merge_ci.py --merge-sha ae91b85...
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_herdr_module():
    import importlib.util

    path = REPO_ROOT / "scripts" / "loop_ready_issue_herdr.py"
    spec = importlib.util.spec_from_file_location("loop_ready_issue_herdr", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


_herdr = _load_herdr_module()
advance_ready = _herdr.advance_ready
default_run_gh = _herdr.default_run_gh
fetch_check_runs_for_sha = _herdr.fetch_check_runs_for_sha
fetch_issue_merge_and_ci_status = _herdr.fetch_issue_merge_and_ci_status
format_advance_poll_line = _herdr.format_advance_poll_line
parse_owner_name = _herdr.parse_owner_name


def _gh_json(proc: subprocess.CompletedProcess[str], ctx: str) -> Any:
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(f"{ctx}: gh failed ({proc.returncode}): {err}")
    import json

    return json.loads(proc.stdout or "null")


def merge_sha_from_pr(pr: int, repo: str | None, run_gh=default_run_gh) -> str:
    """Resolve the merge commit OID for a merged PR via ``gh pr view``."""
    argv = ["gh", "pr", "view", str(pr), "--json", "mergeCommit"]
    if repo:
        owner, name = parse_owner_name(repo)
        argv.extend(["--repo", f"{owner}/{name}"])
    proc = run_gh(argv)
    data = _gh_json(proc, f"PR #{pr} mergeCommit")
    if not isinstance(data, dict):
        raise RuntimeError(f"PR #{pr}: missing mergeCommit (not merged?)")
    mc = data.get("mergeCommit") or {}
    if not isinstance(mc, dict):
        raise RuntimeError(f"PR #{pr}: invalid mergeCommit")
    oid = mc.get("oid")
    if not isinstance(oid, str) or not oid.strip():
        raise RuntimeError(f"PR #{pr}: not merged yet")
    return oid.strip()


def wait_post_merge_ci(
    *,
    repo: str,
    issue_number: int | None = None,
    merge_sha: str | None = None,
    poll_seconds: int = 30,
    timeout_seconds: int = 1800,
    run_gh=default_run_gh,
    sleep_fn=time.sleep,
) -> str:
    """Block until α is satisfied. Returns merge commit SHA."""
    if poll_seconds < 1:
        raise ValueError("poll_seconds must be >= 1")
    deadline = time.monotonic() + timeout_seconds
    while True:
        if issue_number is not None:
            status = fetch_issue_merge_and_ci_status(repo, issue_number, run_gh)
            merge_info = status["merge_info"]
            check_runs = status["check_runs"]
            if advance_ready(merge_info, check_runs):
                sha = merge_info.get("merge_commit_sha")
                if isinstance(sha, str) and sha:
                    return sha
                raise RuntimeError(f"#{issue_number}: α ready but merge SHA missing")
            print(format_advance_poll_line(status, poll_seconds))
        elif merge_sha:
            check_runs = fetch_check_runs_for_sha(repo, merge_sha, run_gh)
            merge_info = {"merged": True, "merge_commit_sha": merge_sha}
            if advance_ready(merge_info, check_runs):
                return merge_sha
            status = {
                "issue_number": 0,
                "merge_info": merge_info,
                "check_runs": check_runs,
            }
            print(format_advance_poll_line(status, poll_seconds))
        else:
            raise RuntimeError("issue_number or merge_sha required")

        if time.monotonic() >= deadline:
            raise RuntimeError(
                f"post-merge CI did not reach α within {timeout_seconds}s"
            )
        sleep_fn(poll_seconds)


def build_parser() -> argparse.ArgumentParser:
    """CLI for waiting until post-merge CI satisfies the herdr α gate."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", metavar="OWNER/NAME", help="GitHub repo (default: gh repo view)")
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--issue", type=int, metavar="N", help="Issue closed by the merged PR")
    group.add_argument("--merge-sha", metavar="SHA", help="Merge commit on default branch")
    group.add_argument("--pr", type=int, metavar="N", help="Merged PR number")
    ap.add_argument(
        "--poll-seconds",
        type=int,
        default=30,
        metavar="SEC",
        help="Poll interval (default: 30; herdr driver default is 300)",
    )
    ap.add_argument(
        "--timeout",
        type=int,
        default=1800,
        metavar="SEC",
        help="Max wait (default: 1800)",
    )
    return ap


def resolve_repo(explicit: str | None, run_gh=default_run_gh) -> str:
    """Return ``OWNER/NAME`` from ``--repo`` or ``gh repo view``."""
    if explicit and explicit.strip():
        return explicit.strip()
    proc = run_gh(["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"])
    if proc.returncode != 0:
        raise RuntimeError("could not resolve repo; pass --repo OWNER/NAME")
    return (proc.stdout or "").strip()


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo = resolve_repo(args.repo)
    try:
        if args.pr is not None:
            sha = merge_sha_from_pr(args.pr, repo)
            wait_post_merge_ci(
                repo=repo,
                merge_sha=sha,
                poll_seconds=args.poll_seconds,
                timeout_seconds=args.timeout,
            )
        else:
            wait_post_merge_ci(
                repo=repo,
                issue_number=args.issue,
                merge_sha=args.merge_sha,
                poll_seconds=args.poll_seconds,
                timeout_seconds=args.timeout,
            )
    except (RuntimeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("post-merge CI α satisfied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
