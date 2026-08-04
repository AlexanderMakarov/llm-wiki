"""Unit tests for the AWOS context CI path-list gate (#117)."""

from __future__ import annotations

import io
import os
import subprocess
from pathlib import Path

import pytest

from tests.awos_context_gate import (
    gate_passes,
    git_changed_paths,
    is_armed_path,
    main,
    print_failure,
)


def _git_env(tmp_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["HOME"] = str(tmp_path)
    env["GIT_CONFIG_GLOBAL"] = str(tmp_path / "gitconfig")
    env["GIT_CONFIG_SYSTEM"] = "/dev/null"
    return env


def _git(repo: Path, env: dict[str, str], *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _write_commit(repo: Path, env: dict[str, str], relpath: str, content: str, msg: str) -> str:
    path = repo / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    _git(repo, env, "add", relpath)
    _git(repo, env, "commit", "-m", msg)
    return _git(repo, env, "rev-parse", "HEAD")


@pytest.mark.parametrize(
    "paths",
    [
        ["docs/tutorials/getting-started.md"],
        ["scripts/setup.sh"],
        ["examples/sample-vault/README.md"],
        [
            "docs/tutorials/foo.md",
            "scripts/bar.py",
            "examples/baz/qux.md",
            "docs/guides/install.md",
            "README.md",
        ],
    ],
)
def test_exempt_only_paths_pass(paths: list[str]) -> None:
    assert gate_passes(paths) is True


def test_armed_with_any_context_path_passes() -> None:
    assert (
        gate_passes(
            [
                "llmwiki/cli.py",
                "context/spec/003-awos-context-ci-gate/tasks.md",
            ]
        )
        is True
    )
    assert gate_passes(["tests/test_foo.py", "context/notes.md"]) is True
    assert gate_passes(["integrations/foo.py", "context/a/b/c.md"]) is True


def test_armed_without_context_fails() -> None:
    assert gate_passes(["llmwiki/cli.py"]) is False
    assert gate_passes(["integrations/foo.py", "docs/tutorials/x.md"]) is False


@pytest.mark.parametrize(
    ("path", "armed"),
    [
        ("docs/maintainers/REVIEW.md", True),
        ("docs/reference/cli.md", True),
        ("docs/guides/install.md", False),
        ("docs/tutorials/getting-started.md", False),
    ],
)
def test_docs_prefix_arming_edges(path: str, armed: bool) -> None:
    assert is_armed_path(path) is armed
    assert gate_passes([path]) is (not armed)


@pytest.mark.parametrize(
    ("path", "armed"),
    [
        (".github/workflows/pr-lint.yml", True),
        (".github/workflows/ci.yml", True),
        (".github/PULL_REQUEST_TEMPLATE.md", False),
        (".github/ISSUE_TEMPLATE/bug.yml", False),
    ],
)
def test_github_workflows_arm_other_github_does_not(path: str, armed: bool) -> None:
    assert is_armed_path(path) is armed
    assert gate_passes([path]) is (not armed)


@pytest.mark.parametrize(
    "path",
    [
        "tests/test_awos_context_gate.py",
        "tests/awos_context_gate.py",
        "tests/conftest.py",
        "tests/fixtures/sample.md",
    ],
)
def test_tests_paths_arm(path: str) -> None:
    assert is_armed_path(path) is True
    assert gate_passes([path]) is False
    assert gate_passes([path, "context/fix.md"]) is True


def test_failure_message_uses_error_annotations_without_label_bypass() -> None:
    buf = io.StringIO()
    print_failure(stream=buf)
    text = buf.getvalue()
    assert "::error::" in text
    assert "awos-exempt" not in text.lower()


def test_print_failure_defaults_to_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    print_failure()
    captured = capsys.readouterr()
    assert "::error::" in captured.out
    assert captured.err == ""


def test_git_changed_paths_lists_committed_files(tmp_path: Path) -> None:
    env = _git_env(tmp_path)
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, env, "init", "-b", "main")
    _git(repo, env, "config", "user.email", "USER@example.com")
    _git(repo, env, "config", "user.name", "USER")
    base = _write_commit(repo, env, "README.md", "root\n", "init")
    head = _write_commit(repo, env, "llmwiki/cli.py", "x\n", "arm")
    paths = git_changed_paths(base, head, cwd=str(repo))
    assert paths == ["llmwiki/cli.py"]


def test_main_fails_closed_when_armed_without_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    env = _git_env(tmp_path)
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, env, "init", "-b", "main")
    _git(repo, env, "config", "user.email", "USER@example.com")
    _git(repo, env, "config", "user.name", "USER")
    base = _write_commit(repo, env, "README.md", "root\n", "init")
    head = _write_commit(repo, env, "llmwiki/cli.py", "x\n", "arm without notes")
    monkeypatch.chdir(repo)

    rc = main(["--base", base, "--head", head])
    assert rc == 1
    out = capsys.readouterr().out
    assert "::error::" in out
    assert "context/" in out

    with pytest.raises(SystemExit) as exc_info:
        raise SystemExit(main(["--base", base, "--head", head]))
    assert exc_info.value.code == 1


def test_main_merge_base_honesty_passes_where_tip_to_tip_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Branch-only docs/tutorials change must pass; tip-to-tip vs advanced base fails."""
    env = _git_env(tmp_path)
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, env, "init", "-b", "main")
    _git(repo, env, "config", "user.email", "USER@example.com")
    _git(repo, env, "config", "user.name", "USER")
    _write_commit(repo, env, "README.md", "root\n", "init")
    _git(repo, env, "checkout", "-b", "feature")
    head = _write_commit(
        repo,
        env,
        "docs/tutorials/guide.md",
        "tutorial\n",
        "exempt tutorial only",
    )
    _git(repo, env, "checkout", "main")
    base_tip = _write_commit(repo, env, "llmwiki/new.py", "product\n", "base armed advance")
    mb = _git(repo, env, "merge-base", "main", "feature")
    monkeypatch.chdir(repo)

    assert main(["--base", mb, "--head", head]) == 0
    assert main(["--base", base_tip, "--head", head]) == 1


def test_main_emits_error_not_traceback_when_git_diff_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    env = _git_env(tmp_path)
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, env, "init", "-b", "main")
    _git(repo, env, "config", "user.email", "USER@example.com")
    _git(repo, env, "config", "user.name", "USER")
    _write_commit(repo, env, "README.md", "root\n", "init")
    monkeypatch.chdir(repo)

    rc = main(["--base", "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef", "--head", "HEAD"])
    assert rc == 1
    out = capsys.readouterr().out
    assert out.startswith("::error::could not diff ")
    assert "the gate cannot judge this PR" in out
    assert "CalledProcessError" not in out
    assert "Traceback" not in out
