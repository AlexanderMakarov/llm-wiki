"""Synthesizer child processes the synth run can stop on demand (#181).

The CLI backends (Claude, Cursor) run one child process per page. Each child
starts in its own session, so a terminal Ctrl+C reaches only the synth run and
the pages in flight finish. When the run is abandoned instead — a second
Ctrl+C while those pages drain — waiting for every child up to the backend
timeout would keep the operator stuck, so the backend kills them through
:class:`TrackedChildren`.
"""

from __future__ import annotations

import os
import signal
import subprocess
import threading
import time
from collections.abc import Sequence

#: Seconds a child gets to exit after SIGTERM before it is killed outright.
DEFAULT_KILL_GRACE = 2.0

_POLL_INTERVAL = 0.05


def _signal_child(proc: subprocess.Popen[str], *, force: bool) -> None:
    """Terminate (or kill, with ``force``) one child and, on POSIX, its process group.

    The child is its own process-group leader (``start_new_session``), so the
    group signal also reaches anything the CLI spawned. Windows has no process
    groups here; ``terminate()`` / ``kill()`` stop the child itself.
    """
    try:
        if os.name == "posix":
            os.killpg(proc.pid, signal.SIGKILL if force else signal.SIGTERM)
        elif force:
            proc.kill()
        else:
            proc.terminate()
    except (ProcessLookupError, PermissionError, OSError):
        pass


class TrackedChildren:
    """Lock-guarded registry of one backend's live child processes.

    :meth:`run` behaves like ``subprocess.run(argv, input=..., capture_output=True,
    text=True, timeout=..., start_new_session=True)`` — same return value, same
    ``TimeoutExpired`` (after killing the child) and ``OSError`` behaviour — while
    the child is visible to :meth:`kill_all` from another thread.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._live: set[subprocess.Popen[str]] = set()

    def __len__(self) -> int:
        """Number of children currently running through :meth:`run`."""
        with self._lock:
            return len(self._live)

    def run(
        self,
        argv: Sequence[str],
        *,
        input: str | None = None,
        timeout: float,
    ) -> subprocess.CompletedProcess[str]:
        """Run ``argv`` to completion in a new session and capture its text output."""
        proc = subprocess.Popen(
            list(argv),
            stdin=subprocess.PIPE if input is not None else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        with self._lock:
            self._live.add(proc)
        try:
            try:
                stdout, stderr = proc.communicate(input, timeout=timeout)
            except subprocess.TimeoutExpired as exc:
                proc.kill()
                exc.stdout, exc.stderr = proc.communicate()
                raise
            except BaseException:
                proc.kill()
                raise
        finally:
            with self._lock:
                self._live.discard(proc)
        return subprocess.CompletedProcess(list(argv), proc.returncode, stdout, stderr)

    def kill_all(self, *, grace: float = DEFAULT_KILL_GRACE) -> int:
        """Stop every live child: SIGTERM, then SIGKILL whatever outlives ``grace``.

        Returns how many children were signalled. Never raises. A killed child
        exits non-zero, so the page it was writing fails instead of landing.
        """
        with self._lock:
            procs = [p for p in self._live if p.poll() is None]
        for proc in procs:
            _signal_child(proc, force=False)
        deadline = time.monotonic() + max(grace, 0.0)
        alive = procs
        while alive and time.monotonic() < deadline:
            time.sleep(_POLL_INTERVAL)
            alive = [p for p in alive if p.poll() is None]
        for proc in alive:
            _signal_child(proc, force=True)
        return len(procs)
