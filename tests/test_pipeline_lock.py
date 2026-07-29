"""Tests for llmwiki.pipeline_lock — vault-level pipeline serialization (PR #19 field report)."""

from __future__ import annotations

import os
import subprocess
import sys
import time

import pytest

import llmwiki.cli as cli_mod
import llmwiki.pipeline_lock as lock_mod
from llmwiki.pipeline_lock import LOCK_DIRNAME, pipeline_lock


def test_acquire_creates_and_releases_lock(tmp_path):
    lock_dir = tmp_path / LOCK_DIRNAME
    with pipeline_lock(tmp_path):
        assert lock_dir.is_dir()
        assert (lock_dir / "pid").read_text() == str(os.getpid())
    assert not lock_dir.exists()


def test_released_on_exception(tmp_path):
    with pytest.raises(ValueError, match="boom"):
        with pipeline_lock(tmp_path):
            raise ValueError("boom")
    assert not (tmp_path / LOCK_DIRNAME).exists()


def test_contended_lock_times_out_with_holder_pid(tmp_path):
    lock_dir = tmp_path / LOCK_DIRNAME
    lock_dir.mkdir()
    (lock_dir / "pid").write_text(str(os.getpid()))  # alive holder (us)
    start = time.monotonic()
    with pytest.raises(RuntimeError, match=str(os.getpid())):
        with pipeline_lock(tmp_path, timeout=0.5, poll=0.05):
            pass  # pragma: no cover — never acquired
    assert time.monotonic() - start < 5
    assert lock_dir.is_dir()  # a live holder's lock is never broken


def test_stale_dead_pid_lock_is_broken(tmp_path):
    lock_dir = tmp_path / LOCK_DIRNAME
    lock_dir.mkdir()
    # A PID that is certainly dead: spawn a process and wait for it.
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    (lock_dir / "pid").write_text(str(proc.pid))
    with pipeline_lock(tmp_path, timeout=5, poll=0.05):
        assert (lock_dir / "pid").read_text() == str(os.getpid())
    assert not lock_dir.exists()


def test_stale_old_mtime_lock_without_pid_is_broken(tmp_path):
    lock_dir = tmp_path / LOCK_DIRNAME
    lock_dir.mkdir()  # no pid file — crash between mkdir and write
    old = time.time() - 60 * 60
    os.utime(lock_dir, (old, old))
    with pipeline_lock(tmp_path, timeout=5, poll=0.05):
        pass
    assert not lock_dir.exists()


def test_fresh_pidless_lock_is_respected(tmp_path):
    # Young lock with no pid yet (another process between mkdir and
    # pid-write): not stale, must be waited on.
    lock_dir = tmp_path / LOCK_DIRNAME
    lock_dir.mkdir()
    with pytest.raises(RuntimeError, match="unknown"):
        with pipeline_lock(tmp_path, timeout=0.3, poll=0.05):
            pass  # pragma: no cover


def test_cmd_add_dry_run_takes_no_lock(tmp_path, monkeypatch, capsys):
    """--dry-run must stay lock-free (and must not leave a lock behind)."""

    src = tmp_path / "in.md"
    src.write_text("# Dry Run Doc\n\nbody\n")
    vault = tmp_path / "vault"
    (vault / "raw" / "docs").mkdir(parents=True)
    (vault / "wiki").mkdir()

    def _forbidden(*a, **k):  # pragma: no cover — failure path
        raise AssertionError("dry-run must not acquire the pipeline lock")

    monkeypatch.setattr(lock_mod, "pipeline_lock", _forbidden)
    monkeypatch.setattr(cli_mod, "pipeline_lock", _forbidden, raising=False)

    args = cli_mod.build_parser().parse_args(
        ["add", "--dry-run", "--vault", str(vault), str(src)]
    )
    rc = args.func(args)
    assert rc == 0
    assert "Dry Run Doc" in capsys.readouterr().out
    assert not (vault / lock_mod.LOCK_DIRNAME).exists()
