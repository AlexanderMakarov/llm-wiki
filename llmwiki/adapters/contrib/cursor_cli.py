"""Cursor CLI (cursor-agent) session-store adapter.

This is distinct from the Cursor *IDE* adapter (``cursor.py``), which reads the
IDE's ``workspaceStorage/state.vscdb``. The Cursor **CLI** (``cursor-agent``)
stores each chat under:

    ~/.cursor/chats/<workspace-hash>/<chat-uuid>/store.db

``store.db`` is a content-addressed blob store (git-like)::

    meta(key, value)      -- value is hex-encoded JSON: {agentId, latestRootBlobId, ...}
    blobs(id, data)       -- id = content hash; data = a JSON message OR a binary
                             protobuf "tree" node that references child blob ids

Message blobs are JSON: ``{"role": "system"|"user"|"assistant"|"tool",
"content": str|list, ...}``. They carry no timestamp/sequence field — ordering
lives in the binary tree. We recover order by reading the root tree blob
(``latestRootBlobId``) and sorting message blobs by the byte offset at which
their id first appears in the root blob's bytes. That reproduces the on-screen
conversation order (validated against real transcripts).

Fidelity notes:
- User prompts are kept **verbatim** (full content, including any ``<user_info>``
  context Cursor injects) so nothing the user typed is lost.
- System prompts and tool-result turns are dropped (noise for a knowledge wiki).
- Assistant ``reasoning`` blocks map to ``thinking`` (dropped by the shared
  renderer by default); ``text`` is kept; ``tool-call`` maps to ``tool_use``.
- Store meta ``agentId`` is injected as ``sessionId`` (never the filesystem
  stem ``store``); ``createdAt`` (unix ms) becomes an ISO ``timestamp`` so
  ``started`` / filenames reflect the real chat time (#180 smoke fix).
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from llmwiki.adapters import register
from llmwiki.adapters.base import BaseAdapter

# Synthetic record type injected by ``load_records`` so store-meta audit
# fields survive ``normalize_records`` / ``filter_records`` and reach
# ``is_headless_session`` + ``render_session_markdown``.
_CURSOR_CLI_META_TYPE = "cursor_cli_meta"
_AUTO_REVIEW_MODE = "auto-review"


@register("cursor_cli", aliases=["cursor-cli"])
class CursorCliAdapter(BaseAdapter):
    """Cursor CLI (cursor-agent) — reads ~/.cursor/chats/*/*/store.db"""

    is_ai_session = True

    session_store_path = Path.home() / ".cursor" / "chats"

    def discover_sessions(self) -> list[Path]:
        store = Path(self.session_store_path).expanduser()
        if not store.exists():
            return []
        return sorted(store.rglob("store.db"))

    def derive_project_slug(self, path: Path) -> str:
        """Use the workspace-hash directory (first segment under chats/)."""
        store = Path(self.session_store_path).expanduser()
        try:
            rel = path.relative_to(store)
        except ValueError:
            return path.parent.name
        ws = rel.parts[0] if rel.parts else path.parent.name
        return f"cursor-{ws[:12]}"

    # ── non-JSONL load: parse the SQLite blob store into ordered messages ──

    def load_records(self, path: Path) -> list[dict[str, Any]]:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        con.text_factory = bytes
        try:
            blobs = dict(con.execute("SELECT id, data FROM blobs").fetchall())
            meta_rows = con.execute("SELECT key, value FROM meta").fetchall()
        finally:
            con.close()

        json_msgs: dict[str, dict[str, Any]] = {}
        for bid, data in blobs.items():
            try:
                obj = json.loads(data.decode("utf-8"))
            except Exception:
                continue
            if isinstance(obj, dict) and ("role" in obj or "content" in obj):
                json_msgs[bid.decode()] = obj

        store_meta = self._decode_store_meta(meta_rows)
        root_id = (store_meta or {}).get("latestRootBlobId") or None
        ordered_ids = self._order_by_tree(root_id, blobs, set(json_msgs))
        if ordered_ids:
            messages = [json_msgs[i] for i in ordered_ids if i in json_msgs]
        else:
            # Fallback: no recoverable tree — return messages in arbitrary store order.
            messages = list(json_msgs.values())
        audit = self._audit_record_from_store_meta(store_meta)
        return ([audit] + messages) if audit is not None else messages

    @staticmethod
    def _decode_store_meta(meta_rows: list[tuple]) -> dict[str, Any] | None:
        """Decode the first hex-encoded JSON object from the store.db meta table.

        Cursor stores session launch fields (``approvalMode``, ``subagentInfo``,
        ``latestRootBlobId``, …) as hex(UTF-8 JSON) in ``meta.value``.
        """
        for _key, value in meta_rows:
            try:
                raw = value.decode() if isinstance(value, bytes) else value
                decoded = json.loads(bytes.fromhex(raw).decode("utf-8"))
                if isinstance(decoded, dict):
                    return decoded
            except Exception:
                continue
        return None

    @staticmethod
    def _audit_record_from_store_meta(
        store_meta: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        """Flatten useful store-meta fields into a synthetic record for convert.

        Always prefers ``agentId`` as ``sessionId`` / short ``slug`` so rendered
        frontmatter never falls back to the filesystem stem ``store``. Prefers
        ``createdAt`` (unix ms) as an ISO ``timestamp`` for ``first_record_time``.
        """
        if not store_meta:
            return None
        audit: dict[str, Any] = {"type": _CURSOR_CLI_META_TYPE}

        agent_id = store_meta.get("agentId")
        if agent_id is not None and str(agent_id).strip():
            aid = str(agent_id).strip()
            audit["sessionId"] = aid
            # First UUID segment (or first 12 chars) — readable + unique enough.
            segment = aid.split("-", 1)[0].strip()
            if segment:
                audit["slug"] = segment[:12]

        created = store_meta.get("createdAt")
        iso = _created_at_to_iso(created)
        if iso:
            audit["timestamp"] = iso

        am = store_meta.get("approvalMode")
        if am is not None and am != "":
            audit["approvalMode"] = am

        if "subagentInfo" in store_meta and store_meta.get("subagentInfo") is not None:
            si = store_meta["subagentInfo"]
            # Presence alone marks headless. Strings / other non-dicts must not
            # be treated as mappings (``.keys()`` / ``.get`` crash — #180 smoke).
            audit["subagentInfo"] = si
            if isinstance(si, dict):
                type_name = si.get("typeName")
                if type_name:
                    audit["subagentTypeName"] = type_name

        # Only inject when we have something worth auditing / classifying /
        # identifying (sessionId, timestamp, or headless markers).
        if len(audit) == 1:
            return None
        return audit

    @staticmethod
    def _order_by_tree(
        root_id: str | None, blobs: dict, known_ids: set[str]
    ) -> list[str]:
        """Order known message ids by first byte-offset in the root tree blob."""
        if not root_id:
            return []
        root = blobs.get(root_id.encode())
        if root is None:
            return []
        hexs = root.hex()
        offsets: list[tuple[int, str]] = []
        for sid in known_ids:
            i = hexs.find(sid)
            if i >= 0:
                offsets.append((i, sid))
        offsets.sort()
        return [sid for _i, sid in offsets]

    # ── map Cursor records into the shared Claude-style schema ──

    def normalize_records(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for rec in records:
            if not isinstance(rec, dict):
                continue
            # Keep the store-meta audit sentinel so headless detection and
            # frontmatter persistence still see approvalMode / subagentInfo
            # after message-role mapping.
            if rec.get("type") == _CURSOR_CLI_META_TYPE:
                out.append(rec)
                continue
            role = rec.get("role")
            if role == "user":
                content = rec.get("content")
                text = content if isinstance(content, str) else _join_text(content)
                out.append({"type": "user", "message": {"role": "user", "content": text}})
            elif role == "assistant":
                blocks = _map_assistant_blocks(rec.get("content"))
                if blocks:
                    out.append(
                        {"type": "assistant", "message": {"role": "assistant", "content": blocks}}
                    )
            # system + tool roles are intentionally dropped.
        return out

    def is_headless_session(self, records: list[dict[str, Any]]) -> bool:
        """True for Cursor nested Task/subagents or auto-review launches (#180).

        Headless when store meta has ``subagentInfo`` present **or**
        ``approvalMode`` equals ``auto-review`` (case-normalized). Interactive
        top-level Agent sessions (no subagentInfo, not auto-review) stay
        eligible.

        ``subagentInfo`` may be a dict, a non-empty string, or another non-None
        value — presence is enough. Never call ``.keys()`` / ``.get`` on a
        non-dict value.

        Precedence vs ``include_subagents``: Cursor nested agents are gated by
        ``exclude_headless`` (this method), not by Claude's path-based
        ``include_subagents`` filter. ``convert_all`` applies exclude_headless
        first; turning that filter off still includes these sessions.
        """
        for r in records:
            if not isinstance(r, dict):
                continue
            if "subagentInfo" in r and r.get("subagentInfo") is not None:
                return True
            am = r.get("approvalMode")
            if isinstance(am, str) and am.strip().lower() == _AUTO_REVIEW_MODE:
                return True
        return False


def _created_at_to_iso(created: Any) -> str | None:
    """Convert Cursor ``createdAt`` (unix ms, or s) to an ISO-8601 UTC string."""
    if isinstance(created, bool) or created is None:
        return None
    try:
        value = float(created)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    # Heuristic: ≥ 1e12 → milliseconds; else seconds.
    seconds = value / 1000.0 if value >= 1_000_000_000_000 else value
    try:
        ts = datetime.fromtimestamp(seconds, tz=UTC)
    except (OverflowError, OSError, ValueError):
        return None
    return ts.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _join_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts = [
        b.get("text", "")
        for b in content
        if isinstance(b, dict) and b.get("type") in ("text", "reasoning")
    ]
    return "\n".join(p for p in parts if p)


def _map_assistant_blocks(content: Any) -> list[dict[str, Any]]:
    if isinstance(content, str):
        return [{"type": "text", "text": content}] if content else []
    if not isinstance(content, list):
        return []
    blocks: list[dict[str, Any]] = []
    for b in content:
        if not isinstance(b, dict):
            continue
        t = b.get("type")
        if t == "text":
            blocks.append({"type": "text", "text": b.get("text", "")})
        elif t == "reasoning":
            blocks.append({"type": "thinking", "thinking": b.get("text", "")})
        elif t == "tool-call":
            blocks.append(
                {
                    "type": "tool_use",
                    "name": b.get("toolName", "tool"),
                    "input": b.get("args") or b.get("input") or {},
                }
            )
    return blocks
