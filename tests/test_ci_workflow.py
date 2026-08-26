"""Tests for the wiki-checks CI workflow (v1.0, #163) and the #109 lint gate."""

from __future__ import annotations

import re
from pathlib import Path

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
    assert "demo/**" in text
    assert "docs/**" in text
    assert "scripts/refresh_demo.py" in text


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


# ─── R4 boundary: --fail-on-errors, not --strict ────────────────────────


def _seed_wiki(vault: Path, *, page_type: str, last_updated: str) -> None:
    page = vault / "wiki" / "entities" / "Topic.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(
        f'---\ntitle: "Topic"\ntype: {page_type}\nlast_updated: {last_updated}\n---\n\n# Topic\n',
        encoding="utf-8",
    )


def test_fail_on_errors_exits_nonzero_on_a_seeded_error(tmp_path: Path, capsys) -> None:
    """An error-severity finding fails the same gate CI uses."""
    vault = tmp_path / "vault"
    _seed_wiki(vault, page_type="not-a-kind", last_updated="2026-01-01")
    args = build_parser().parse_args([
        "lint", "--vault", str(vault), "--fail-on-errors",
        "--rules", "frontmatter_validity",
    ])
    assert args.func(args) == 1
    capsys.readouterr()


def test_workflow_never_regenerates_the_demo() -> None:
    """R3: refreshing is local. CI may print a dry-run plan; it must not synth."""
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "llmwiki synth" not in text
    assert "--docs-only" not in text
    assert "refresh_demo.py --dry-run" in text
    for line in text.splitlines():
        if "refresh_demo.py" not in line:
            continue
        stripped = line.strip()
        if stripped.startswith("- "):
            continue  # path filter
        if stripped.startswith("#"):
            continue
        assert "--dry-run" in line, f"CI must not run a real refresh: {line!r}"


def test_fail_on_errors_exits_zero_on_warnings_only(tmp_path: Path, capsys) -> None:
    """`--fail-on-errors` alone tolerates warnings: a warning-only wiki exits 0.

    Pins the flag's own semantics against a temp vault, not the workflow.
    content_freshness is warning-severity, so a page old enough to fire it
    leaves the gate green under --fail-on-errors. Failing on warnings is the
    separate, deliberate act of passing --fail-on-warnings — which the demo
    gate now does, with content_freshness switched off in demo/llmwiki.json so
    the snapshot's age cannot redden it (#150).
    """
    vault = tmp_path / "vault"
    _seed_wiki(vault, page_type="entity", last_updated="2020-01-01")
    args = build_parser().parse_args([
        "lint", "--vault", str(vault), "--fail-on-errors",
        "--rules", "content_freshness",
    ])
    assert args.func(args) == 0
    capsys.readouterr()