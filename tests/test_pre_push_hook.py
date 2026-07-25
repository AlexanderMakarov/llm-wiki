"""Tests for the .githooks/pre-push ruff linter hook."""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK_PATH = REPO_ROOT / ".githooks" / "pre-push"
ZERO_SHA = "0" * 40


def test_pre_push_hook_exists_and_is_executable() -> None:
    assert HOOK_PATH.is_file()
    mode = HOOK_PATH.stat().st_mode
    assert mode & stat.S_IXUSR


def test_pre_push_hook_is_posix_shell() -> None:
    first_line = HOOK_PATH.read_text(encoding="utf-8").splitlines()[0]
    assert first_line.startswith("#!/bin/sh") or first_line.startswith("#!/usr/bin/env sh")
    result = subprocess.run(["sh", "-n", str(HOOK_PATH)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def _git_env(tmp_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["HOME"] = str(tmp_path)
    env["GIT_CONFIG_GLOBAL"] = str(tmp_path / "gitconfig")
    env["GIT_CONFIG_SYSTEM"] = "/dev/null"
    return env


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    env = _git_env(tmp_path)
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, env=env, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "USER@example.com"],
        cwd=repo,
        env=env,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "USER"],
        cwd=repo,
        env=env,
        check=True,
        capture_output=True,
    )
    return repo


def _commit_file(repo: Path, env: dict[str, str], name: str, content: str) -> str:
    path = repo / name
    path.write_text(content, encoding="utf-8")
    subprocess.run(["git", "add", name], cwd=repo, env=env, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", f"add {name}"], cwd=repo, env=env, check=True, capture_output=True)
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _run_hook(
    repo: Path,
    tmp_path: Path,
    local_sha: str,
    remote_sha: str = ZERO_SHA,
    extra_env: dict[str, str] | None = None,
    remote_name: str = "origin",
    local_ref: str = "refs/heads/main",
    remote_ref: str = "refs/heads/main",
) -> subprocess.CompletedProcess[str]:
    hook_dest = repo / ".git" / "hooks" / "pre-push"
    hook_dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(HOOK_PATH, hook_dest)
    hook_dest.chmod(hook_dest.stat().st_mode | stat.S_IXUSR)

    env = _git_env(tmp_path)
    if extra_env:
        env.update(extra_env)
    remote_url = "https://example.com/repo.git"
    stdin = f"{local_ref} {local_sha} {remote_ref} {remote_sha}\n"
    return subprocess.run(
        ["sh", str(hook_dest), remote_name, remote_url],
        cwd=repo,
        env=env,
        input=stdin,
        capture_output=True,
        text=True,
    )


def _configure_git_user(repo: Path, env: dict[str, str]) -> None:
    subprocess.run(
        ["git", "config", "user.email", "USER@example.com"],
        cwd=repo,
        env=env,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "USER"],
        cwd=repo,
        env=env,
        check=True,
        capture_output=True,
    )


def _setup_backlog_repo_with_remote(tmp_path: Path) -> tuple[Path, dict[str, str], str]:
    """Work repo with legacy ruff violations already pushed to remote ``original``."""
    env = _git_env(tmp_path)
    bare = tmp_path / "remote.git"
    bare.mkdir()
    subprocess.run(
        ["git", "init", "--bare", "-b", "main"],
        cwd=bare,
        env=env,
        check=True,
        capture_output=True,
    )
    repo = tmp_path / "work"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, env=env, check=True, capture_output=True)
    _configure_git_user(repo, env)
    _commit_file(repo, env, "legacy_a.py", "import os\n")
    _commit_file(repo, env, "legacy_b.py", "import sys\n")
    _commit_file(repo, env, "legacy_c.py", "import json\n")
    subprocess.run(
        ["git", "remote", "add", "original", str(bare)],
        cwd=repo,
        env=env,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "push", "-u", "original", "main"],
        cwd=repo,
        env=env,
        check=True,
        capture_output=True,
    )
    return repo, env, "original"


@pytest.mark.skipif(shutil.which("ruff") is None, reason="ruff not on PATH")
def test_pre_push_hook_fails_on_ruff_violation(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    env = _git_env(tmp_path)
    local_sha = _commit_file(repo, env, "bad.py", "import os\n\nx = 1\n")

    result = _run_hook(repo, tmp_path, local_sha)
    assert result.returncode != 0
    assert "bad.py" in result.stdout + result.stderr


def test_pre_push_skip_env_var(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    env = _git_env(tmp_path)
    local_sha = _commit_file(repo, env, "bad.py", "import os\n\nx = 1\n")

    result = _run_hook(repo, tmp_path, local_sha, extra_env={"LLMWIKI_SKIP_PREPUSH": "1"})
    assert result.returncode == 0
    assert "LLMWIKI_SKIP_PREPUSH" in result.stdout + result.stderr


def test_pre_push_hook_no_py_files_exits_zero(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    env = _git_env(tmp_path)
    local_sha = _commit_file(repo, env, "README.md", "# hello\n")

    result = _run_hook(repo, tmp_path, local_sha)
    assert result.returncode == 0


@pytest.mark.skipif(shutil.which("ruff") is None, reason="ruff not on PATH")
def test_new_branch_push_ignores_preexisting_violations_on_remote(tmp_path: Path) -> None:
    repo, env, remote_name = _setup_backlog_repo_with_remote(tmp_path)
    subprocess.run(["git", "checkout", "-b", "feature"], cwd=repo, env=env, check=True, capture_output=True)
    local_sha = _commit_file(repo, env, "new_clean.py", "x = 1\n")

    result = _run_hook(
        repo,
        tmp_path,
        local_sha,
        remote_name=remote_name,
        local_ref="refs/heads/feature",
        remote_ref="refs/heads/feature",
    )
    combined = result.stdout + result.stderr

    assert result.returncode == 0
    for legacy in ("legacy_a.py", "legacy_b.py", "legacy_c.py"):
        assert legacy not in combined


@pytest.mark.skipif(shutil.which("ruff") is None, reason="ruff not on PATH")
def test_new_branch_push_lints_only_new_violating_file(tmp_path: Path) -> None:
    repo, env, remote_name = _setup_backlog_repo_with_remote(tmp_path)
    subprocess.run(["git", "checkout", "-b", "feature"], cwd=repo, env=env, check=True, capture_output=True)
    local_sha = _commit_file(repo, env, "new_bad.py", "import os\n\nx = 1\n")

    result = _run_hook(
        repo,
        tmp_path,
        local_sha,
        remote_name=remote_name,
        local_ref="refs/heads/feature",
        remote_ref="refs/heads/feature",
    )
    combined = result.stdout + result.stderr

    assert result.returncode != 0
    assert "new_bad.py" in combined
    for legacy in ("legacy_a.py", "legacy_b.py", "legacy_c.py"):
        assert legacy not in combined
