"""Tests for the wiki-checks CI workflow (v1.0, #163)."""

from __future__ import annotations

import re

from llmwiki import REPO_ROOT
from llmwiki.cli import build_parser

WORKFLOW = REPO_ROOT / ".github" / "workflows" / "wiki-checks.yml"


def test_workflow_exists():
    assert WORKFLOW.is_file()


def test_workflow_has_name():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert text.startswith("name:")


def test_triggers_on_push_and_pr():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "push:" in text
    assert "pull_request:" in text


def test_workflow_dispatch_trigger():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in text


def test_path_filters_include_llmwiki():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "llmwiki/**" in text


def test_runs_on_ubuntu():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "runs-on: ubuntu-latest" in text


def test_uses_pinned_python_version():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "python-version:" in text


def test_installs_llmwiki():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "pip install -e ." in text


def test_checks_the_demo_vault_by_name():
    """The job names the vault rather than relying on a directory it seeded.

    Seeding copied sessions into a root vault, which no longer exists — the
    demo is self-contained at ``demo/`` and every step addresses it directly.
    """
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "--vault demo" in text
    assert "demo/raw/sessions" not in text


def test_every_llmwiki_command_it_runs_actually_exists():
    """Guard against the job invoking a subcommand the CLI does not have.

    This job previously called ``llmwiki eval`` and ``llmwiki check-links``,
    neither of which is a subcommand, each swallowed by ``|| true``. The job
    reported success while doing nothing, and no test noticed because the
    assertions only checked that the strings were present.
    """
    known = set(build_parser()._subparsers._group_actions[0].choices)  # noqa: SLF001
    # Same-line only: `\s` would span a newline and match the next YAML key.
    invoked = set(re.findall(r"llmwiki[ \t]+([a-z][a-z-]*)", WORKFLOW.read_text(encoding="utf-8")))
    unknown = invoked - known
    assert not unknown, f"workflow invokes non-existent subcommand(s): {sorted(unknown)}"


def test_runs_lint_with_fail_on_errors():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "llmwiki lint" in text
    assert "--fail-on-errors" in text


def test_runs_build():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "llmwiki build" in text


def test_runs_adapters_listing():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "llmwiki adapters" in text


def test_has_read_only_permissions():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "contents: read" in text


def test_pinned_setup_python_version():
    """Workflow pins actions/setup-python to a floating major (@vN), not a branch tip."""
    text = WORKFLOW.read_text(encoding="utf-8")
    assert re.search(r"actions/setup-python@v\d+", text)


def test_pinned_checkout_version():
    """Workflow pins actions/checkout to a floating major (@vN), not a branch tip."""
    text = WORKFLOW.read_text(encoding="utf-8")
    assert re.search(r"actions/checkout@v\d+", text)