"""Repo quality-gate invariants for the unit suite (#280).

# @layer: unit
# @spec: 280-shrink-test-suite
"""

from __future__ import annotations

import os
import re
import subprocess
import tomllib
from pathlib import Path

import pytest

from llmwiki import REPO_ROOT

# Unconditional skips that only memorialize deleted product surfaces.
_DEAD_SKIP = re.compile(
    r"@pytest\.mark\.skip\([^)]*\b(removed|retired|deleted|no longer exists)\b",
    re.IGNORECASE,
)

CI = REPO_ROOT / ".github" / "workflows" / "ci.yml"
PR_LINT = REPO_ROOT / ".github" / "workflows" / "pr-lint.yml"
PYPROJECT = REPO_ROOT / "pyproject.toml"
CODING_STANDARDS = REPO_ROOT / "docs" / "CODING_STANDARDS.md"
CURSOR_TESTING_EXPERT = REPO_ROOT / ".cursor" / "agents" / "testing-expert.md"
CANONICAL_TESTING_EXPERT = REPO_ROOT / ".claude" / "agents" / "testing-expert.md"
TESTS_DIR = REPO_ROOT / "tests"
CLI_TESTS = TESTS_DIR / "cli"


# @regression
def test_pyproject_coverage_report_fail_under_is_87() -> None:
    """Unit coverage gate fails CI when product line coverage drops below 87%."""
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    assert data["tool"]["coverage"]["report"]["fail_under"] == 87


# @regression
def test_ci_lint_and_test_runs_pytest_with_llmwiki_cov() -> None:
    """Default CI unit job measures ``llmwiki`` line+branch coverage with pytest-cov."""
    text = CI.read_text(encoding="utf-8")
    assert "python -m pytest tests/" in text
    assert "--cov=llmwiki" in text
    assert "--cov-branch" in text
    assert "--cov-report=term-missing" in text
    assert "--cov-report=xml:coverage.xml" in text
    assert "--cov-report=json:coverage.json" in text
    assert "--cov-fail-under=0" in text
    assert "scripts/check_unit_coverage.py" in text
    assert "upload-artifact@v7" in text
    assert "coverage.xml" in text


# @regression
def test_check_unit_coverage_script_enforces_line_floor() -> None:
    """Line gate stays at 87% when CI measures branches in the same run."""
    text = (REPO_ROOT / "scripts" / "check_unit_coverage.py").read_text(encoding="utf-8")
    assert "LINE_FLOOR = 87" in text


# @regression
def test_pr_lint_runs_ai_tooling_lint() -> None:
    """PR governance must lint shipped agent kit and inner agent markdown."""
    text = PR_LINT.read_text(encoding="utf-8")
    assert "ai-linting:" in text
    assert "llmwiki/agent_kit" in text
    assert "AGNIX_VERSION:" in text
    assert ".claude/commands" in text
    assert ".claude/commands/*.md" not in text


# @regression
def test_ci_runs_uninstrumented_slow_perf_budget_tests() -> None:
    """Wall-clock lint_perf tests must still run in CI without coverage overhead."""
    run_lines = [
        ln
        for ln in CI.read_text(encoding="utf-8").splitlines()
        if not ln.lstrip().startswith("#")
    ]
    assert any(
        "tests/test_lint_perf.py" in ln and "-m slow" in ln and "-o addopts=" in ln
        for ln in run_lines
    )
    assert "performance-budget" in CI.read_text(encoding="utf-8")


# @regression
def test_no_dead_removed_surface_skip_markers_under_tests() -> None:
    """Unconditional skips that only memorialize deleted product surfaces are gone."""
    offenders: list[str] = []
    for path in TESTS_DIR.rglob("*.py"):
        if _DEAD_SKIP.search(path.read_text(encoding="utf-8")):
            offenders.append(str(path.relative_to(REPO_ROOT)))
    assert not offenders, f"remove dead skips: {offenders}"


# @regression
def test_coding_standards_doc_names_floor_and_cli_layout() -> None:
    """Agents can load coding standards for the coverage floor and mirrored CLI tests."""
    text = CODING_STANDARDS.read_text(encoding="utf-8")
    assert "fail_under = 87" in text
    assert "tests/cli/" in text


# @regression
def test_cli_unit_tests_live_under_mirrored_cli_package() -> None:
    """CLI unit coverage lives under ``tests/cli/`` as a package with test modules."""
    assert (CLI_TESTS / "__init__.py").is_file()
    assert any(CLI_TESTS.glob("test_*.py"))


# @regression
def test_cursor_testing_expert_points_at_claude_canonical() -> None:
    """Cursor testing-expert must symlink or stub-link the Claude canonical agent."""
    assert CURSOR_TESTING_EXPERT.exists()
    assert CANONICAL_TESTING_EXPERT.is_file()
    if CURSOR_TESTING_EXPERT.is_symlink():
        target = (CURSOR_TESTING_EXPERT.parent / CURSOR_TESTING_EXPERT.readlink()).resolve()
        assert target == CANONICAL_TESTING_EXPERT.resolve()
        return
    body = CURSOR_TESTING_EXPERT.read_text(encoding="utf-8").strip()
    assert len(body) < 500, "expected symlink or short stub, not a duplicated agent body"
    assert ".claude/agents/testing-expert" in body


def _classify_step_script() -> str:
    """Return the ``run:`` body of pr-lint's changelog ``classify`` step."""
    lines = PR_LINT.read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip() == "id: classify")
    run_at = next(i for i in range(start, len(lines)) if lines[i].strip() == "run: |")
    key_indent = len(lines[run_at]) - len(lines[run_at].lstrip())
    body: list[str] = []
    for line in lines[run_at + 1 :]:
        if line.strip() and len(line) - len(line.lstrip()) <= key_indent:
            break
        body.append(line)
    assert body, "classify step has an empty run script"
    return "\n".join(body)


# @regression
@pytest.mark.parametrize(
    ("title", "skip"),
    [
        ("chore: a", "true"),
        ("chore(flow): a", "true"),
        ("docs(x): a", "true"),
        ("test: a", "true"),
        ("feat: a", "false"),
        ("fix(cli): a", "false"),
        ("tests: a", "false"),
        ("chore(): a", "false"),
    ],
)
def test_pr_lint_changelog_classify_skips_scoped_docs_chore_test(
    title: str, skip: str, tmp_path: Path
) -> None:
    """docs/chore/test titles skip the CHANGELOG gate with or without a scope (#412)."""
    script = _classify_step_script()
    output = tmp_path / "github_output"
    env = {**os.environ, "TITLE": title, "GITHUB_OUTPUT": str(output)}
    subprocess.run(["bash", "-c", script], env=env, check=True)
    assert output.read_text(encoding="utf-8").strip() == f"skip={skip}"
