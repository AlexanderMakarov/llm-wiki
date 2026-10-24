"""Cursor turn-usage capture → durable JSONL events (#325).

``store.db`` JSON messages do not carry turn throughput. Sources that do:

1. IDE ``stop`` / ``afterAgentResponse`` hooks (snake_case fields) — forum
   https://forum.cursor.com/t/how-to-obtain-token-usage-per-request/168317
2. Agent CLI ``stream-json`` final ``result.usage`` (camelCase
   ``inputTokens`` / …)

This module:

- Installs a cheap POSIX ``/bin/sh`` ``stop`` hook (``--install-hook``) that
  appends the **full** stdin JSON blob as one JSONL line (~3 ms; not Python).
  Prefer this for the awaited IDE hook. The Python ingest path writes a
  minimized usage row instead; ``load_events`` accepts both shapes.
- Optionally appends via ``python3 -m llmwiki.cursor_token_events`` on stdin
  (ingest / debug — do not use as the awaited IDE hook body).
- Loads events for a ``conversation_id`` (matches Cursor ``agentId`` / session folder).
- Dedupes by ``generation_id`` / ``request_id`` so dual hooks do not double-count.
- ``--install-hook`` merges the IDE ``stop`` entry into ``~/.cursor/hooks.json``.

Default log: ``~/.cursor/llmwiki-cursor-token-events.jsonl`` (override with
``LLMWIKI_CURSOR_TOKEN_EVENTS``). Treat the managed-hook JSONL as local telemetry
(full Cursor stop payload), not a publishable artifact.
"""
from __future__ import annotations

import json
import os
import stat
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from llmwiki.cursor_token_usage import (
    map_cursor_usage_to_claude_usage,
    normalize_cursor_usage_keys,
)

_HOOK_MARKER = "llmwiki-cursor-token-stop"

# POSIX sh: works when Cursor runs under bash or zsh (shebang /bin/sh).
# Keep this tiny — Cursor awaits stop; spawn+append dominates latency.
STOP_HOOK_SCRIPT = """\
#!/bin/sh
# llmwiki-cursor-token-stop — append full Cursor stop-hook stdin JSON to JSONL.
# Latency-first: no JSON filter in sh. Python ingest writes minimized rows;
# sync accepts both. Keep this log local (not under site/).
set -eu
OUT="${LLMWIKI_CURSOR_TOKEN_EVENTS:-${HOME}/.cursor/llmwiki-cursor-token-events.jsonl}"
mkdir -p "$(dirname "$OUT")"
# One stdin blob → one JSONL line (O_APPEND; safe for concurrent writers on Linux).
payload=$(tr '\\n' ' ')
payload=$(printf '%s' "$payload" | sed 's/[[:space:]]*$//')
[ -n "$payload" ] || exit 0
printf '%s\\n' "$payload" >>"$OUT"
"""


def default_events_path() -> Path:
    """Default JSONL log the stop hook appends to, under the current home directory."""
    return Path.home() / ".cursor" / "llmwiki-cursor-token-events.jsonl"


def default_hooks_path() -> Path:
    """Cursor's ``hooks.json`` under the current home directory."""
    return Path.home() / ".cursor" / "hooks.json"


def default_hook_script_path() -> Path:
    """The managed stop-hook script under the current home directory."""
    return Path.home() / ".cursor" / "llmwiki-cursor-token-stop.sh"


def events_path(override: str | Path | None = None) -> Path:
    """Resolve the JSONL path (env / argument / default)."""
    if override is not None and str(override).strip():
        return Path(override).expanduser()
    env = os.environ.get("LLMWIKI_CURSOR_TOKEN_EVENTS", "").strip()
    if env:
        return Path(env).expanduser()
    return default_events_path()


def _conversation_id_from_payload(payload: Mapping[str, Any]) -> str:
    for key in (
        "conversation_id",
        "conversationId",
        "session_id",
        "sessionId",
        "agentId",
    ):
        val = payload.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def _generation_id_from_payload(payload: Mapping[str, Any]) -> str:
    for key in ("generation_id", "generationId", "request_id", "requestId"):
        val = payload.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def _usage_mapping_from_payload(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    """Flatten hook / stream-json shapes into one usage-like mapping."""
    usage = payload.get("usage")
    if isinstance(usage, Mapping):
        # stream-json result: {type:result, session_id, usage:{inputTokens,…}}
        merged = {**dict(usage), **{k: payload[k] for k in payload if k != "usage"}}
        return merged
    return payload


def append_hook_event(
    payload: Mapping[str, Any],
    *,
    path: Path | None = None,
) -> bool:
    """Append one event line when the payload carries usable turn totals.

    Accepts IDE hook stdin JSON and Agent CLI ``stream-json`` ``result``
    objects. Returns True when a line was written.
    """
    if not isinstance(payload, Mapping):
        return False
    conversation_id = _conversation_id_from_payload(payload)
    if not conversation_id:
        return False
    usage_src = _usage_mapping_from_payload(payload)
    mapped = map_cursor_usage_to_claude_usage(usage_src)
    if mapped is None:
        return False
    norm = normalize_cursor_usage_keys(usage_src)
    generation_id = _generation_id_from_payload(payload)
    row = {
        "conversation_id": conversation_id,
        "generation_id": generation_id or None,
        "hook_event_name": (
            payload.get("hook_event_name")
            or payload.get("hookEventName")
            or payload.get("type")
        ),
        "model": payload.get("model") or payload.get("model_id"),
        "input_tokens": norm.get("input_tokens"),
        "output_tokens": norm.get("output_tokens"),
        "cache_read_tokens": norm.get("cache_read_tokens"),
        "cache_write_tokens": norm.get("cache_write_tokens"),
    }
    out = events_path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")
    return True


def ingest_stream_json_text(
    text: str,
    *,
    path: Path | None = None,
) -> int:
    """Ingest ``result`` lines from Agent CLI ``stream-json`` stdout. Returns count."""
    n = 0
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        if obj.get("type") != "result":
            continue
        if append_hook_event(obj, path=path):
            n += 1
    return n


def load_events(
    *,
    path: Path | None = None,
    conversation_id: str | None = None,
) -> list[dict[str, Any]]:
    """Load JSONL events, optionally filtered to one conversation."""
    target = events_path(path)
    if not target.is_file():
        return []
    needle = (conversation_id or "").strip()
    rows: list[dict[str, Any]] = []
    try:
        text = target.read_text(encoding="utf-8")
    except OSError:
        return []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        cid = str(obj.get("conversation_id") or "").strip()
        if not cid:
            # Raw shell-hook lines may use camelCase ids.
            cid = _conversation_id_from_payload(obj)
        if needle and cid != needle:
            continue
        if cid and "conversation_id" not in obj:
            obj = {**obj, "conversation_id": cid}
        rows.append(obj)
    return rows


def usage_records_for_conversation(
    conversation_id: str,
    *,
    path: Path | None = None,
) -> list[dict[str, Any]]:
    """Synthetic assistant records with Claude-shaped ``message.usage``.

    Dedupes by ``generation_id`` (first wins) so ``stop`` + ``afterAgentResponse``
    for the same turn are not summed twice. Accepts normalized Python rows and
    raw IDE hook JSON appended by the shell script.
    """
    cid = (conversation_id or "").strip()
    if not cid:
        return []
    seen_gens: set[str] = set()
    out: list[dict[str, Any]] = []
    for event in load_events(path=path, conversation_id=cid):
        gen = _generation_id_from_payload(event) or str(
            event.get("generation_id") or ""
        ).strip()
        if gen:
            if gen in seen_gens:
                continue
            seen_gens.add(gen)
        mapped = map_cursor_usage_to_claude_usage(event)
        if mapped is None:
            continue
        out.append(
            {
                "type": "assistant",
                "message": {"role": "assistant", "content": [], "usage": mapped},
                "source": "cursor_token_hook",
            }
        )
    return out


def merge_cursor_stop_token_hook(
    hooks_json: dict[str, Any],
    command: str,
    *,
    install: bool,
) -> dict[str, Any]:
    """Idempotently merge/remove managed Cursor ``stop`` token-capture hook."""
    out = json.loads(json.dumps(hooks_json))
    out.setdefault("version", 1)
    hooks = out.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        hooks = {}
        out["hooks"] = hooks
    entries = hooks.get("stop")
    if not isinstance(entries, list):
        entries = []
    cleaned = [
        e
        for e in entries
        if not (
            isinstance(e, dict)
            and _HOOK_MARKER in str(e.get("command", e.get("script", "")))
        )
    ]
    if install:
        cleaned.append(
            {
                "command": f"# {_HOOK_MARKER}\n{command}",
            }
        )
    if cleaned:
        hooks["stop"] = cleaned
    elif "stop" in hooks:
        del hooks["stop"]
    return out


def default_stop_hook_command(script_path: str | Path | None = None) -> str:
    """Shell command for Cursor ``hooks.json`` ``stop`` entry (POSIX script path)."""
    path = Path(script_path) if script_path is not None else default_hook_script_path()
    return str(path.expanduser())


def write_stop_hook_script(script_path: Path | None = None) -> Path:
    """Write the managed POSIX stop-hook script and make it executable."""
    target = Path(script_path) if script_path is not None else default_hook_script_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(STOP_HOOK_SCRIPT, encoding="utf-8")
    mode = target.stat().st_mode
    target.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return target


def install_stop_hook(
    *,
    hooks_path: Path | None = None,
    script_path: Path | None = None,
    backup: bool = True,
) -> Path:
    """Write the shell stop script and merge it into ``hooks.json``. Returns hooks path."""
    script = write_stop_hook_script(script_path)
    target = Path(hooks_path) if hooks_path is not None else default_hooks_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_file():
        raw = target.read_text(encoding="utf-8")
        try:
            doc = json.loads(raw) if raw.strip() else {"version": 1, "hooks": {}}
        except json.JSONDecodeError as exc:
            raise SystemExit(f"error: cannot parse {target}: {exc}") from exc
        if backup:
            bak = target.with_suffix(target.suffix + ".bak")
            bak.write_text(raw, encoding="utf-8")
    else:
        doc = {"version": 1, "hooks": {}}
    if not isinstance(doc, dict):
        doc = {"version": 1, "hooks": {}}
    merged = merge_cursor_stop_token_hook(
        doc, default_stop_hook_command(script), install=True
    )
    target.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
    return target


def main(argv: list[str] | None = None) -> int:
    """CLI: stdin ingest, ``--install-hook``, or ``--ingest-stream-json FILE``."""
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] in ("--install-hook", "install-hook"):
        hooks = install_stop_hook()
        script = default_hook_script_path()
        print(f"installed Cursor stop token hook → {hooks}")
        print(f"shell handler → {script}")
        return 0
    if args and args[0] in ("--ingest-stream-json", "ingest-stream-json"):
        if len(args) < 2:
            print(
                "usage: python3 -m llmwiki.cursor_token_events "
                "--ingest-stream-json FILE",
                file=sys.stderr,
            )
            return 2
        text = Path(args[1]).read_text(encoding="utf-8")
        n = ingest_stream_json_text(text)
        print(f"ingested {n} result usage line(s)")
        return 0
    raw = sys.stdin.read()
    if not raw.strip():
        return 0
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        # Allow NDJSON stdin (stream-json pipe).
        ingest_stream_json_text(raw)
        return 0
    if isinstance(payload, dict):
        # Single JSON object: hook payload or one result line.
        append_hook_event(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
