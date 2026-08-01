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


def test_guard_fails_a_test_that_dirties_a_tracked_file(tmp_path: Path) -> None:
    """End-to-end: a deliberately dirtying test must not pass silently."""
    repo = tmp_path / "repo"
    (repo / "tests").mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    (repo / "seed.md").write_text("original\n", encoding="utf-8")
    subprocess.run(["git", "add", "seed.md"], cwd=repo, check=True)

    (repo / "tests" / "conftest.py").write_text(
        "import sys\n"
        f"sys.path.insert(0, {str(Path.cwd())!r})\n"
        "from tests.tracked_files import tracked_file_guard  # noqa: F401\n",
        encoding="utf-8",
    )
    (repo / "tests" / "test_dirty.py").write_text(
        "from pathlib import Path\n"
        "def test_rewrites_a_tracked_file():\n"
        "    Path(__file__).parent.parent.joinpath('seed.md')"
        ".write_text('mutated\\n')\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-p", "no:cacheprovider"],
        cwd=repo,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0, result.stdout
    assert "seed.md" in result.stdout
    assert "test_rewrites_a_tracked_file" in result.stdout
