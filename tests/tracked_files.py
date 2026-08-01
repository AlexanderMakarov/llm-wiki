"""Guard: the test suite must not mutate tracked files in the clone (#91).

Tests write into temp dirs. When one instead writes into the working copy —
usually by exercising a code path whose ``wiki_dir`` falls back to
``REPO_ROOT / "wiki"`` — the damage is not merely a dirty tree. Generators
like ``reindex`` rebuild a *tracked* page from *every* page on disk, including
pages under gitignored paths, so local data crosses the ignore boundary into
something ``git add`` will happily stage.

The guard watches the tracked set (``git ls-files``) rather than any ignore
rule, and attributes a change to the test that caused it.
"""

from __future__ import annotations

import subprocess
from collections.abc import Iterable
from pathlib import Path

import pytest

#: Sentinel hash for a path that is absent. Distinct from any real digest, so
#: create and delete are both visible as changes.
_ABSENT = "<absent>"


def tracked_files(repo_root: Path) -> list[Path]:
    """Return paths git tracks under ``repo_root``.

    Returns an empty list when git is unavailable or the directory is not a
    repository — the guard degrades to a no-op rather than failing the suite
    for an environmental reason.
    """
    try:
        proc = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=repo_root,
            capture_output=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return []
    return [
        repo_root / name.decode("utf-8", "replace")
        for name in proc.stdout.split(b"\0")
        if name
    ]


def snapshot(paths: Iterable[Path]) -> dict[str, str]:
    """Map each path to a change signature, or ``_ABSENT`` if it is not there.

    The signature is ``size:mtime_ns``, not a content digest. Hashing the
    tracked set costs ~270s across a full suite run — far too much for a
    fixture that has to run on every test — while stat is effectively free.
    Any write updates mtime, which is what the guard is looking for; a rewrite
    that preserves both size and nanosecond mtime would slip through, and git
    itself makes the same trade.
    """
    signatures: dict[str, str] = {}
    for path in paths:
        try:
            st = path.stat()
            signatures[str(path)] = f"{st.st_size}:{st.st_mtime_ns}"
        except OSError:
            signatures[str(path)] = _ABSENT
    return signatures


def changed_paths(before: dict[str, str], after: dict[str, str]) -> list[str]:
    """Return paths whose content differs between two snapshots."""
    return sorted(
        path
        for path, digest in after.items()
        if before.get(path, _ABSENT) != digest
    )


@pytest.fixture(autouse=True)
def tracked_file_guard(request: pytest.FixtureRequest):
    """Fail any test that leaves a tracked file modified.

    The tracked list is resolved once per session; digests are taken per test
    so the failure names the culprit instead of surfacing later as an
    unexplained ``git status`` entry.
    """
    paths = _watched(request)
    if not paths:
        yield
        return

    before = snapshot(paths)
    yield
    dirty = changed_paths(before, snapshot(paths))
    if dirty:
        listed = "\n  ".join(dirty)
        pytest.fail(
            f"test mutated {len(dirty)} tracked file(s) in the working copy:"
            f"\n  {listed}\n"
            "Tests must write only into tmp_path. A code path whose wiki_dir "
            "or state file falls back to the repo root will rewrite the "
            "clone — pass an explicit directory instead.",
            pytrace=False,
        )


def _watched(request: pytest.FixtureRequest) -> list[Path]:
    """Resolve (once per session) the tracked files this run should watch."""
    key = "_llmwiki_tracked_files"
    cached = getattr(request.session, key, None)
    if cached is None:
        # rootpath, not this file's parent: the guard must watch whichever
        # repo the session is running in, including the throwaway one its
        # own test builds.
        cached = tracked_files(Path(request.config.rootpath))
        setattr(request.session, key, cached)
    return cached
