"""Vault-level pipeline lock shared by the mutating CLI entry points.

Two llmwiki processes writing the same vault corrupt each other's site
resets: a SessionStart-hook pipeline (sync → synthesize → build) writing
``site/sessions/`` while ``llmwiki add``'s post-add build rmtree's the
same directory dies with "could not reset site dir ... Directory not
empty" (field report on the #16 PR). ``sync``, ``build``, and ``add``
therefore serialize on one lock rooted at the vault (or the repo root
when no vault is in play).

The lock is an atomically-created directory — ``os.mkdir`` is atomic on
every platform — holding a ``pid`` file for staleness detection. It is
NOT reentrant: acquire it once at the outermost CLI layer, never inside
library code that a locked command may call.
"""

from __future__ import annotations

import os
import shutil
import sys
import time
from contextlib import contextmanager
from pathlib import Path

LOCK_DIRNAME = ".llmwiki-pipeline.lock"

# A lock older than this is presumed abandoned (crashed process on a
# platform where liveness can't be probed, or an unkillable stale dir).
_STALE_AFTER_SECONDS = 30 * 60


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists, owned by someone else
    except OSError:
        return True  # non-POSIX or exotic failure — assume alive
    return True


def _is_stale(lock_dir: Path) -> bool:
    try:
        pid = int((lock_dir / "pid").read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        # No readable pid (crash between mkdir and write, or foreign
        # tooling) — fall back to age alone.
        pid = -1
    if pid > 0 and not _pid_alive(pid):
        return True
    try:
        age = time.time() - lock_dir.stat().st_mtime
    except OSError:
        return False  # vanished — the retry loop will re-attempt mkdir
    return age > _STALE_AFTER_SECONDS


@contextmanager
def pipeline_lock(root: Path, timeout: float = 300.0, poll: float = 0.5):
    """Serialize mutating pipeline runs (sync/build/add) on one vault.

    Blocks up to ``timeout`` seconds waiting for a concurrent holder,
    breaking locks whose owning process is gone. Raises RuntimeError on
    timeout, naming the lock path and the holder's pid.
    """
    lock_dir = root / LOCK_DIRNAME
    deadline = time.monotonic() + timeout
    warned = False
    acquired = False
    try:
        while True:
            try:
                os.mkdir(lock_dir)
                acquired = True
                (lock_dir / "pid").write_text(str(os.getpid()), encoding="utf-8")
                break
            except FileExistsError:
                if _is_stale(lock_dir):
                    # Break the stale lock, then fall through to the deadline
                    # check — an un-removable dir must not loop forever.
                    shutil.rmtree(lock_dir, ignore_errors=True)
                try:
                    holder = (lock_dir / "pid").read_text(encoding="utf-8").strip()
                except OSError:
                    holder = "unknown"
                if not warned:
                    print(
                        f"waiting for another llmwiki process (pid {holder}) "
                        f"to finish with {root}...",
                        file=sys.stderr,
                    )
                    warned = True
                if time.monotonic() >= deadline:
                    raise RuntimeError(
                        f"timed out after {timeout:.0f}s waiting for pipeline lock "
                        f"{lock_dir} (held by pid {holder}); remove the directory "
                        "if no llmwiki process is running"
                    ) from None
                time.sleep(poll)
        yield
    finally:
        if acquired:
            shutil.rmtree(lock_dir, ignore_errors=True)
