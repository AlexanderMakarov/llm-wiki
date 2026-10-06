"""Repo quality-gate invariants for the unit suite (#280).

# @layer: unit
# @spec: 280-shrink-test-suite
"""

from __future__ import annotations

import re
import tomllib

from llmwiki import REPO_ROOT

_DEAD_SKIP = re.compile(
    r"@pytest\.mark\.skip\([^)]*subcommand removed",
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
    """Default CI unit job measures ``llmwiki`` coverage with pytest-cov."""
    text = CI.read_text(encoding="utf-8")
    assert "python -m pytest tests/" in text
    assert "--cov=llmwiki" in text
    assert "--cov-report=term-missing" in text


# @regression
def test_pr_lint_runs_ai_tooling_lint() -> None:
    """PR governance must lint shipped agent kit and inner agent markdown."""
    text = PR_LINT.read_text(encoding="utf-8")
    assert "ai-linting:" in text
    assert "llmwiki/agent_kit" in text
    assert ".claude/commands/*.md" in text


# @regression
def test_ci_runs_uninstrumented_slow_perf_budget_tests() -> None:
    """Wall-clock lint_perf tests must still run in CI without coverage overhead."""
    text = CI.read_text(encoding="utf-8")
    assert "tests/test_lint_perf.py" in text
    assert "-m slow" in text
    assert "performance-budget" in text


# @regression
def test_no_dead_subcommand_removed_skip_markers_under_tests() -> None:
    """Permanently skipped tests that only document removed CLI surfaces are gone."""
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
