"""The suite must not mutate tracked files in the clone (#91).

A test that rewrites a tracked file can launder gitignored local data into a
committed one — ``wiki/index.md`` is regenerated from whatever pages sit on
disk, including pages under ignored paths. ``.gitignore`` is not a containment
boundary, so the guard watches the tracked set directly.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from tests.settings_sandbox import SettingsSandbox
from tests.tracked_files import changed_paths, snapshot, tracked_files

# ─── Snapshot / diff ───────────────────────────────────────────────────


def test_snapshot_flags_a_modified_file(tmp_path: Path) -> None:
    watched = tmp_path / "seed.md"
    watched.write_text("original\n", encoding="utf-8")

    before = snapshot([watched])
    watched.write_text("rewritten\n", encoding="utf-8")

    assert changed_paths(before, snapshot([watched])) == [str(watched)]


def test_snapshot_ignores_untouched_files(tmp_path: Path) -> None:
    watched = tmp_path / "seed.md"
    watched.write_text("original\n", encoding="utf-8")

    before = snapshot([watched])

    assert changed_paths(before, snapshot([watched])) == []


def test_snapshot_flags_a_same_length_rewrite(tmp_path: Path) -> None:
    """Detection must not depend on the file's size changing.

    Pins the edge case a stat-based fast path could regress: reindex-style
    rewrites often preserve length while changing content.
    """
    watched = tmp_path / "seed.md"
    watched.write_text("aaaa\n", encoding="utf-8")

    before = snapshot([watched])
    watched.write_text("bbbb\n", encoding="utf-8")

    assert changed_paths(before, snapshot([watched])) == [str(watched)]


def test_snapshot_flags_a_deleted_file(tmp_path: Path) -> None:
    """Deleting a tracked file is as much a mutation as rewriting one."""
    watched = tmp_path / "seed.md"
    watched.write_text("original\n", encoding="utf-8")

    before = snapshot([watched])
    watched.unlink()

    assert changed_paths(before, snapshot([watched])) == [str(watched)]


def test_missing_file_stays_missing_without_flagging(tmp_path: Path) -> None:
    """A path git knows about but that is absent both times is not a change."""
    absent = tmp_path / "never-existed.md"

    assert changed_paths(snapshot([absent]), snapshot([absent])) == []


# ─── Tracked-file discovery ────────────────────────────────────────────


def test_tracked_files_lists_committed_paths_only(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "committed.md").write_text("x\n", encoding="utf-8")
    (tmp_path / "untracked.md").write_text("y\n", encoding="utf-8")
    subprocess.run(["git", "add", "committed.md"], cwd=tmp_path, check=True)

    names = {p.name for p in tracked_files(tmp_path)}

    assert "committed.md" in names
    assert "untracked.md" not in names


# ─── The guard actually fires ──────────────────────────────────────────


def _run_guarded_suite(tmp_path: Path, test_body: str) -> subprocess.CompletedProcess[str]:
    """Run one test under the guard in a throwaway repo with a tracked seed and an ignored config."""
    repo = tmp_path / "repo"
    (repo / "tests").mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    (repo / "seed.md").write_text("original\n", encoding="utf-8")
    (repo / ".gitignore").write_text("config.json\n", encoding="utf-8")
    subprocess.run(["git", "add", "seed.md", ".gitignore"], cwd=repo, check=True)

    (repo / "tests" / "conftest.py").write_text(
        "import sys\n"
        f"sys.path.insert(0, {str(Path.cwd())!r})\n"
        "from tests.tracked_files import pytest_sessionfinish, pytest_sessionstart  # noqa: F401\n",
        encoding="utf-8",
    )
    (repo / "tests" / "test_dirty.py").write_text(
        "from pathlib import Path\n"
        "ROOT = Path(__file__).parent.parent\n"
        f"{test_body}",
        encoding="utf-8",
    )
    return subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-p", "no:cacheprovider"],
        cwd=repo,
        capture_output=True,
        text=True,
    )


def test_guard_fails_a_test_that_dirties_a_tracked_file(tmp_path: Path) -> None:
    """A run whose test rewrites a tracked file fails and names the file, even though the test itself passed."""
    result = _run_guarded_suite(
        tmp_path,
        "def test_rewrites_a_tracked_file():\n"
        "    ROOT.joinpath('seed.md').write_text('mutated\\n')\n",
    )

    assert result.returncode != 0, result.stdout
    assert "1 passed" in result.stdout
    assert "this pytest run changed 1 tracked or real settings file(s)" in result.stdout
    assert "seed.md" in result.stdout


def test_guard_fails_a_test_that_writes_the_operator_config(tmp_path: Path) -> None:
    """A run whose test writes the gitignored root config.json fails, naming the file."""
    result = _run_guarded_suite(
        tmp_path,
        "def test_writes_the_operator_config():\n"
        "    ROOT.joinpath('config.json').write_text('{\"synthesis\": {\"backend\": \"dummy\"}}\\n')\n",
    )

    assert result.returncode != 0, result.stdout
    assert "config.json" in result.stdout


def _seed_claude_settings(home: Path) -> Path:
    """Write a home Claude settings file holding another tool's entry only."""
    settings = home / ".claude" / "settings.json"
    settings.parent.mkdir(parents=True, exist_ok=True)
    settings.write_text('{\n  "theme": "dark"\n}\n', encoding="utf-8")
    return settings


def test_guard_fails_a_test_that_adds_an_llmwiki_hook_to_the_home_settings(
    tmp_path: Path, settings_sandbox: SettingsSandbox
) -> None:
    """A run whose test writes an llmwiki hook into the home Claude settings fails, naming the file."""
    settings = _seed_claude_settings(settings_sandbox.home)
    result = _run_guarded_suite(
        tmp_path,
        "def test_installs_a_hook():\n"
        "    settings = Path.home() / '.claude' / 'settings.json'\n"
        "    settings.write_text('{\"hooks\": {\"SessionStart\": \"python3 -m llmwiki sync\"}}\\n')\n",
    )

    assert result.returncode != 0, result.stdout
    assert f"{settings} (llmwiki entries)" in result.stdout


def test_guard_ignores_other_tools_editing_the_home_settings(
    tmp_path: Path, settings_sandbox: SettingsSandbox
) -> None:
    """Another tool's change to the shared home settings does not fail the run."""
    _seed_claude_settings(settings_sandbox.home)
    result = _run_guarded_suite(
        tmp_path,
        "def test_other_tool_saves_a_setting():\n"
        "    settings = Path.home() / '.claude' / 'settings.json'\n"
        "    settings.write_text('{\"theme\": \"light\"}\\n')\n",
    )

    assert result.returncode == 0, result.stdout


def test_guard_fails_a_test_that_installs_a_unit_into_the_home_directory(tmp_path: Path) -> None:
    """A run whose test leaves an llmwiki scheduler unit in the home directory fails, naming the unit directory."""
    result = _run_guarded_suite(
        tmp_path,
        "def test_installs_a_unit():\n"
        "    staging = Path.home() / '.automation'\n"
        "    staging.mkdir(exist_ok=True)\n"
        "    (staging / 'llmwiki-maintain-vault-0123abcd.timer').write_text('# timer\\n')\n",
    )

    assert result.returncode != 0, result.stdout
    assert ".automation/llmwiki-maintain*" in result.stdout
