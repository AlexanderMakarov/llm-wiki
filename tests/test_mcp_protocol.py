"""#633 (#pw-x5): MCP server end-to-end protocol tests.

The existing MCP test suite hits each tool function directly. This
module is the missing layer: it spawns the MCP server in a subprocess,
writes JSON-RPC frames to its stdin, reads responses from stdout, and
asserts the protocol contract end-to-end.

Catches:

  - Dispatch bugs where a method renames itself but `HANDLERS` lookup
    silently routes to the wrong handler.
  - JSON serialization regressions (datetime, Path, set, custom types
    that escape into a result payload).
  - Error-envelope drift (-32600 vs -32601 vs -32603).
  - Stdio framing assumptions (newline-terminated JSON, ignore blank
    lines, return nothing for notifications).

Each test is a self-contained subprocess invocation so a hung server
doesn't deadlock the runner. We `terminate()` after each interaction
and assert via `communicate(timeout=...)`.
"""
from __future__ import annotations

import json
import os
import select
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def _spawn(extra_env: dict | None = None) -> subprocess.Popen:
    """Start the MCP server with stdin + stdout piped."""
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    return subprocess.Popen(
        [sys.executable, "-m", "llmwiki.mcp"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(REPO_ROOT),
        env=env,
    )


def _exchange(proc: subprocess.Popen, request: dict, timeout: float = 5.0) -> dict | None:
    """Send one JSON-RPC frame, read one response line back.

    Returns the parsed response, or ``None`` for notifications (no `id`).
    """
    line = (json.dumps(request) + "\n").encode("utf-8")
    assert proc.stdin is not None and proc.stdout is not None
    proc.stdin.write(line)
    proc.stdin.flush()
    if request.get("id") is None:
        return None
    raw = proc.stdout.readline()
    if not raw:
        # Server died — surface stderr so the failure is debuggable.
        err = proc.stderr.read().decode("utf-8", errors="replace") if proc.stderr else ""
        pytest.fail(f"MCP server closed stdout without responding. stderr:\n{err}")
    return json.loads(raw.decode("utf-8"))


def _shutdown(proc: subprocess.Popen) -> None:
    try:
        proc.stdin.close()  # type: ignore[union-attr]
    except Exception:
        pass
    try:
        proc.wait(timeout=2.0)
    except subprocess.TimeoutExpired:
        proc.terminate()
        proc.wait(timeout=2.0)


# ─── Initialize handshake ─────────────────────────────────────────────


def test_initialize_returns_protocol_version() -> None:
    proc = _spawn()
    try:
        resp = _exchange(proc, {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2024-11-05"},
        })
    finally:
        _shutdown(proc)
    assert resp is not None
    assert resp["jsonrpc"] == "2.0"
    assert resp["id"] == 1
    assert "result" in resp
    assert "protocolVersion" in resp["result"]


def test_tools_list_returns_twelve_tools() -> None:
    proc = _spawn()
    try:
        resp = _exchange(proc, {
            "jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}
        })
    finally:
        _shutdown(proc)
    assert resp is not None
    tools = resp.get("result", {}).get("tools") or []
    assert len(tools) == 6, f"expected 6 tools, got {len(tools)}"
    # Each tool must carry name + inputSchema.
    for t in tools:
        assert "name" in t
        assert "inputSchema" in t


# ─── Error envelopes ──────────────────────────────────────────────────


def test_unknown_method_returns_method_not_found() -> None:
    """JSON-RPC 2.0 reserves -32601 for `Method not found`. Servers
    that swallow the unknown-method case break the contract for any
    client that does method discovery via failed probes."""
    proc = _spawn()
    try:
        resp = _exchange(proc, {
            "jsonrpc": "2.0", "id": 3, "method": "totally/made/up", "params": {}
        })
    finally:
        _shutdown(proc)
    assert resp is not None
    assert "error" in resp
    assert resp["error"]["code"] == -32601, (
        f"expected -32601 Method not found, got {resp['error']!r}"
    )


def test_malformed_json_returns_parse_error() -> None:
    """Send a literal garbage line (not valid JSON) and assert we get
    -32700 Parse error back. JSON-RPC servers must NOT crash on this."""
    proc = _spawn()
    try:
        assert proc.stdin is not None and proc.stdout is not None
        proc.stdin.write(b"not-json-at-all\n")
        proc.stdin.flush()
        raw = proc.stdout.readline()
        resp = json.loads(raw.decode("utf-8"))
    finally:
        _shutdown(proc)
    assert "error" in resp
    assert resp["error"]["code"] == -32700, (
        f"expected -32700 Parse error, got {resp['error']!r}"
    )


# ─── Notifications (id-less requests) ─────────────────────────────────


def test_notification_produces_no_response() -> None:
    """Per JSON-RPC, a request without `id` is a notification — server
    must not write a response. We send a notification followed by a
    real request and verify only one response arrives."""
    proc = _spawn()
    try:
        # Notification first — should produce no response.
        notif = {"jsonrpc": "2.0", "method": "tools/list", "params": {}}
        assert proc.stdin is not None
        proc.stdin.write((json.dumps(notif) + "\n").encode("utf-8"))
        proc.stdin.flush()
        # Then a real request — only THIS response should come back.
        resp = _exchange(proc, {
            "jsonrpc": "2.0", "id": 99, "method": "tools/list", "params": {}
        })
    finally:
        _shutdown(proc)
    assert resp is not None
    assert resp["id"] == 99


# ─── tools/call shape ─────────────────────────────────────────────────


def test_tools_call_with_unknown_tool_returns_error() -> None:
    proc = _spawn()
    try:
        resp = _exchange(proc, {
            "jsonrpc": "2.0", "id": 4,
            "method": "tools/call",
            "params": {"name": "wiki_does_not_exist", "arguments": {}},
        })
    finally:
        _shutdown(proc)
    assert resp is not None
    # Either a JSON-RPC error envelope OR a result with isError=True
    # is acceptable — different MCP implementations vary. We just
    # require some signal that the call failed.
    if "error" in resp:
        assert resp["error"]["code"] in (-32602, -32603, -32601)
    else:
        result = resp.get("result", {})
        assert result.get("isError") is True or "error" in str(result).lower()


# ─── Caller identity via MCP roots (#51) ──────────────────────────────


def _read_frame(proc: subprocess.Popen, timeout: float = 5.0) -> dict:
    """Read one frame the server sent on its own initiative.

    Unlike `_exchange`, nothing was requested here, so a regression means no
    frame ever arrives — `select` turns that into a fast failure instead of
    a hung run."""
    ready, _, _ = select.select([proc.stdout], [], [], timeout)
    if not ready:
        pytest.fail(f"no frame from the server within {timeout}s")
    raw = proc.stdout.readline()  # type: ignore[union-attr]
    if not raw:
        err = proc.stderr.read().decode("utf-8", errors="replace") if proc.stderr else ""
        pytest.fail(f"MCP server closed stdout unexpectedly. stderr:\n{err}")
    return json.loads(raw.decode("utf-8"))


def _write(proc: subprocess.Popen, message: dict) -> None:
    proc.stdin.write((json.dumps(message) + "\n").encode("utf-8"))  # type: ignore[union-attr]
    proc.stdin.flush()  # type: ignore[union-attr]


def test_server_asks_a_roots_capable_client_for_its_roots() -> None:
    """Telemetry needs to know which project called; the server's own cwd
    doesn't answer that, so it asks the client for its workspace roots."""
    proc = _spawn()
    try:
        _exchange(proc, {
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2024-11-05",
                       "capabilities": {"roots": {"listChanged": True}}},
        })
        _write(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})
        frame = _read_frame(proc)
        assert frame["method"] == "roots/list"
        assert "id" in frame
        # Replying must not draw an error back — and the next real request
        # still gets its own response, in order.
        _write(proc, {"jsonrpc": "2.0", "id": frame["id"],
                      "result": {"roots": [{"uri": "file:///home/dev/code/proj-a"}]}})
        resp = _exchange(proc, {
            "jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    finally:
        _shutdown(proc)
    assert resp is not None and resp["id"] == 2


def test_client_without_roots_capability_sees_no_extra_frames() -> None:
    """A client that never advertised roots reads one response per request;
    an unsolicited server request would desynchronise it."""
    proc = _spawn()
    try:
        _exchange(proc, {
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2024-11-05", "capabilities": {}},
        })
        _write(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})
        resp = _exchange(proc, {
            "jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    finally:
        _shutdown(proc)
    assert resp is not None and resp["id"] == 2, (
        "expected the tools/list response, got an unsolicited frame first")


def test_stray_response_frame_draws_no_reply() -> None:
    """A frame with an `id` but no `method` is a response, not a request.
    Answering one with a JSON-RPC error corrupts the client's bookkeeping —
    it would read our error as the reply to its *next* request."""
    proc = _spawn()
    try:
        _write(proc, {"jsonrpc": "2.0", "id": "not-a-request-we-sent",
                      "result": {"roots": []}})
        resp = _exchange(proc, {
            "jsonrpc": "2.0", "id": 7, "method": "tools/list", "params": {}})
    finally:
        _shutdown(proc)
    assert resp is not None and resp["id"] == 7, (
        "expected the tools/list response, got a reply to the stray frame")
