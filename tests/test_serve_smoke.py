"""Smoke test for ``llmwiki serve`` (#278).

Ensures the server starts, binds to a port, serves index.html with a
200, and shuts down cleanly.  No browser — pure HTTP client check.
"""

from __future__ import annotations

import http.client
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_until_accepting(port: int, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                return True
        except OSError:
            time.sleep(0.05)
    return False


@pytest.fixture()
def minimal_site(tmp_path: Path) -> Path:
    """Seed a tiny site/ tree that serve can actually render."""
    site = tmp_path / "site"
    site.mkdir()
    (site / "index.html").write_text(
        "<!DOCTYPE html><html><head><title>T</title></head>"
        "<body><h1>Smoke-test home</h1></body></html>",
        encoding="utf-8",
    )
    (site / "hello.txt").write_text("hi", encoding="utf-8")
    return site


def test_serve_starts_and_serves_index(minimal_site: Path) -> None:
    """Spawn `llmwiki serve --dir <tmp>` and confirm it serves index.html."""
    port = _free_port()
    proc = subprocess.Popen(
        [
            sys.executable, "-m", "llmwiki", "serve",
            "--dir", str(minimal_site),
            "--port", str(port),
            "--host", "127.0.0.1",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(REPO_ROOT),
    )
    try:
        assert _wait_until_accepting(port), (
            f"server didn't bind on 127.0.0.1:{port} within timeout"
        )
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
        conn.request("GET", "/")
        resp = conn.getresponse()
        body = resp.read().decode("utf-8", errors="replace")
        assert resp.status == 200, f"got status {resp.status}"
        assert "Smoke-test home" in body
        conn.close()

        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
        conn.request("GET", "/hello.txt")
        resp = conn.getresponse()
        assert resp.status == 200
        assert resp.read() == b"hi"
        conn.close()
    finally:
        if os.name == "nt":
            proc.terminate()
        else:
            proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()


def test_serve_rejects_missing_dir(tmp_path: Path) -> None:
    """Non-existent --dir should exit non-zero, not silently bind."""
    port = _free_port()
    proc = subprocess.run(
        [
            sys.executable, "-m", "llmwiki", "serve",
            "--dir", str(tmp_path / "does-not-exist"),
            "--port", str(port),
            "--host", "127.0.0.1",
        ],
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert proc.returncode != 0, (
        f"serve on a missing dir should fail but got rc={proc.returncode}\n"
        f"stdout={proc.stdout!r}\nstderr={proc.stderr!r}"
    )


def test_serve_help_mentions_flags() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "llmwiki", "serve", "--help"],
        capture_output=True, text=True, timeout=5,
    )
    assert proc.returncode == 0
    for flag in ("--dir", "--port", "--host", "--open"):
        assert flag in proc.stdout, f"--help missing {flag}"
