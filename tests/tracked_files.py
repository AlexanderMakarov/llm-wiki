"""Guard: a pytest run must not change the clone or the developer's real settings.

Tests write into temp dirs. When one instead writes into the working copy —
usually by exercising a code path whose ``wiki_dir`` falls back to
``REPO_ROOT / "wiki"`` — the damage is not merely a dirty tree. Generators
like ``reindex`` rebuild a *tracked* page from *every* page on disk, including
pages under gitignored paths, so local data crosses the ignore boundary into
something ``git add`` will happily stage.

The guard watches the tracked set (``git ls-files``) rather than any ignore
rule. It also watches the settings llmwiki owns outside the tracked set: the
gitignored operator ``config.json`` at the repo root, and under the real home
directory the scheduler units, the Cursor stop-hook script, and llmwiki's
entries in the Claude and Cursor hook settings. Other tools edit those settings
files too, so only the lines naming llmwiki are compared.

Every pytest invocation is checked as a whole: one snapshot when the session
starts, one when it ends. A run that changed anything fails and lists what
changed; running the modules of that run one at a time names the module, since
each of those runs carries the same check.
"""

from __future__ import annotations

import hashlib
import subprocess
from collections.abc import Iterable
from pathlib import Path

import pytest

#: The real home directory, read when the suite imports this module — before
#: any test points ``HOME`` at its sandbox.
REAL_HOME = Path.home()

#: Scheduler unit files llmwiki installs, as (directory under home, glob).
_HOME_UNIT_GLOBS = (
    (".config/systemd/user", "llmwiki-maintain*"),
    ("Library/LaunchAgents", "com.llmwiki.*"),
    (".automation", "llmwiki-maintain*"),
)
#: Files under home that only llmwiki writes.
_HOME_OWNED_FILES = (".cursor/llmwiki-cursor-token-stop.sh",)
#: Settings files under home shared with other tools; only llmwiki lines count.
_HOME_SHARED_SETTINGS = (".claude/settings.json", ".cursor/hooks.json")

#: Sentinel hash for a path that is absent. Distinct from any real digest, so
#: create and delete are both visible as changes.
_ABSENT = "<absent>"

#: Where ``pytest_sessionstart`` keeps the starting snapshot on the session.
_SESSION_KEY = "_llmwiki_guard_before"


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

    The signature is ``size:mtime_ns``, not a content digest. Any write
    updates mtime, which is what the guard is looking for; a rewrite that
    preserves both size and nanosecond mtime would slip through, and git
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


def settings_snapshot(repo_root: Path, home: Path) -> dict[str, str]:
    """Map each llmwiki-owned settings location to a change signature.

    Covers the operator ``config.json`` under ``repo_root`` and, under
    ``home``, the scheduler units (compared by which llmwiki units exist), the
    llmwiki-only files, and llmwiki's lines in shared settings files. Creation
    and deletion are changes, like edits.
    """
    signatures = snapshot([repo_root / "config.json", *(home / rel for rel in _HOME_OWNED_FILES)])
    for rel, pattern in _HOME_UNIT_GLOBS:
        names = sorted(path.name for path in (home / rel).glob(pattern))
        signatures[str(home / rel / pattern)] = ";".join(names) or _ABSENT
    for rel in _HOME_SHARED_SETTINGS:
        signatures[f"{home / rel} (llmwiki entries)"] = _llmwiki_lines(home / rel)
    return signatures


def _llmwiki_lines(path: Path) -> str:
    """Digest of the lines in ``path`` that mention llmwiki, or ``_ABSENT``."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return _ABSENT
    ours = sorted(line.strip() for line in lines if "llmwiki" in line)
    return hashlib.sha256("\n".join(ours).encode("utf-8")).hexdigest() if ours else _ABSENT


def changed_paths(before: dict[str, str], after: dict[str, str]) -> list[str]:
    """Return paths whose content differs between two snapshots."""
    return sorted(
        path
        for path, digest in after.items()
        if before.get(path, _ABSENT) != digest
    )


def _guard_snapshot(root: Path) -> dict[str, str]:
    """Everything the guard watches for the repo at ``root``, empty outside a git repository."""
    paths = tracked_files(root)
    if not paths:
        return {}
    return {**snapshot(paths), **settings_snapshot(root, REAL_HOME)}


def pytest_sessionstart(session: pytest.Session) -> None:
    """Record what the guard watches before any test runs."""
    setattr(session, _SESSION_KEY, _guard_snapshot(Path(session.config.rootpath)))


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Fail the run when it changed a tracked file or a real settings file."""
    before = getattr(session, _SESSION_KEY, None)
    if not before:
        return
    dirty = changed_paths(before, _guard_snapshot(Path(session.config.rootpath)))
    if not dirty:
        return
    listed = "\n  ".join(dirty)
    message = (
        f"\nthis pytest run changed {len(dirty)} tracked or real settings file(s):\n  {listed}\n"
        "Tests write only into tmp_path and prepare settings through the settings_sandbox "
        "fixture. To find the test, run this run's test modules one at a time "
        "(`python3 -m pytest <module>`): each run carries the same check.\n"
    )
    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    if reporter is not None:
        reporter.write_line(message, red=True)
    else:
        print(message)
    session.exitstatus = pytest.ExitCode.TESTS_FAILED
