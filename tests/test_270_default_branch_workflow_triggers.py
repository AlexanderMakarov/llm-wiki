"""#270 — default-branch-only workflows must push-trigger on documented `main`."""

from __future__ import annotations

import re

from llmwiki import REPO_ROOT

WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"

# Default-branch-only push coverage (not the intentional master+main dual lists).
DEFAULT_BRANCH_PUSH_WORKFLOWS = (
    "release-drafter.yml",
    "cross-browser.yml",
    "agents-e2e.yml",
)

# Intentionally list both legacy and current names — must stay dual (#270 out of scope).
DUAL_BRANCH_WORKFLOWS = (
    "ci.yml",
    "e2e.yml",
    "gitleaks.yml",
)


def _documented_default_branch() -> str:
    """Expected default branch from project docs — not a bare untested constant."""
    contributing = (REPO_ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    match = re.search(r"Default branch is `([^`]+)`", contributing)
    assert match is not None, "CONTRIBUTING.md must state Default branch is `…`"
    branch = match.group(1)

    release = (REPO_ROOT / "docs" / "maintainers" / "RELEASE_PROCESS.md").read_text(
        encoding="utf-8"
    )
    assert f"`{branch}`" in release, (
        f"RELEASE_PROCESS.md must reference documented default branch `{branch}`"
    )
    return branch


def _push_branches(workflow_text: str) -> list[str]:
    match = re.search(
        r"(?m)^  push:\n(?:(?:    |\t).*\n)*?    branches:\s*\[([^\]]+)\]",
        workflow_text,
    )
    assert match is not None, "workflow must declare on.push.branches"
    return [
        part.strip().strip("\"'")
        for part in match.group(1).split(",")
        if part.strip()
    ]


def test_documented_default_branch_is_main():
    assert _documented_default_branch() == "main"


def test_default_branch_push_workflows_include_documented_default():
    default = _documented_default_branch()
    for name in DEFAULT_BRANCH_PUSH_WORKFLOWS:
        path = WORKFLOWS_DIR / name
        branches = _push_branches(path.read_text(encoding="utf-8"))
        assert default in branches, f"{name}: push branches {branches!r} missing {default!r}"
        # Must not cover only the legacy name when the default is main.
        if branches == ["master"]:
            raise AssertionError(
                f"{name}: push trigger is master-only; expected documented default {default!r}"
            )


def test_dual_branch_workflows_still_list_master_and_main():
    """ci / e2e / gitleaks intentionally keep both — do not narrow them in #270."""
    for name in DUAL_BRANCH_WORKFLOWS:
        path = WORKFLOWS_DIR / name
        text = path.read_text(encoding="utf-8")
        assert "master" in text and "main" in text, (
            f"{name}: expected dual master+main branch coverage to remain"
        )
