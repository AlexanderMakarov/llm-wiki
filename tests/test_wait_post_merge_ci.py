"""Tests for ``scripts/wait_post_merge_ci.py`` (herdr α shared with workers).

# @layer: unit
# @spec: 303-loop-ready-issue-herdr
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "wait_post_merge_ci.py"


@pytest.fixture(scope="module")
def wait_mod():
    spec = importlib.util.spec_from_file_location("wait_post_merge_ci", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_wait_post_merge_ci_returns_sha_when_alpha_ready(wait_mod):
    sha = "abc123"
    calls = {"n": 0}

    def run_gh(_argv):
        calls["n"] += 1
        return type("P", (), {"returncode": 0, "stdout": "{}", "stderr": ""})()

    def fetch(_repo, _issue, _run_gh):
        return {
            "issue_number": 355,
            "merge_info": {"merged": True, "merge_commit_sha": sha},
            "check_runs": [
                {"name": "ci", "status": "completed", "conclusion": "success"},
            ],
        }

    wait_mod.fetch_issue_merge_and_ci_status = fetch  # type: ignore[method-assign]
    out = wait_mod.wait_post_merge_ci(
        repo="OWNER/REPO",
        issue_number=355,
        poll_seconds=1,
        timeout_seconds=60,
        run_gh=run_gh,
        sleep_fn=lambda _s: None,
    )
    assert out == sha
    assert calls["n"] == 0


def test_wait_post_merge_ci_times_out(wait_mod):
    def fetch(_repo, _issue, _run_gh):
        return {
            "issue_number": 1,
            "merge_info": {"merged": True, "merge_commit_sha": "deadbeef"},
            "check_runs": [],
        }

    wait_mod.fetch_issue_merge_and_ci_status = fetch  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match="within 2s"):
        wait_mod.wait_post_merge_ci(
            repo="OWNER/REPO",
            issue_number=1,
            poll_seconds=1,
            timeout_seconds=2,
            run_gh=lambda _a: None,
            sleep_fn=lambda _s: None,
        )


def test_merge_sha_from_pr(wait_mod):
    payload = {"mergeCommit": {"oid": "mergeoid99"}}

    def run_gh(argv):
        assert argv[:3] == ["gh", "pr", "view"]
        return type(
            "P",
            (),
            {"returncode": 0, "stdout": json.dumps(payload), "stderr": ""},
        )()

    assert wait_mod.merge_sha_from_pr(380, "o/r", run_gh=run_gh) == "mergeoid99"


def test_fetch_check_runs_for_sha_flattens_pages(wait_mod):
    pages = [
        {"check_runs": [{"name": "a", "status": "completed", "conclusion": "success"}]},
        {"check_runs": [{"name": "b", "status": "completed", "conclusion": "skipped"}]},
    ]

    def run_gh(_argv):
        return type(
            "P",
            (),
            {"returncode": 0, "stdout": json.dumps(pages), "stderr": ""},
        )()

    runs = wait_mod.fetch_check_runs_for_sha("owner/name", "sha1", run_gh=run_gh)
    assert len(runs) == 2
    assert runs[0]["name"] == "a"
    assert runs[1]["conclusion"] == "skipped"
