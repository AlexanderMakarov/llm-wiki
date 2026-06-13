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
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from llmwiki.adapters import register
from llmwiki.adapters.base import BaseAdapter


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

        root_id = self._root_blob_id(meta_rows)
        ordered_ids = self._order_by_tree(root_id, blobs, set(json_msgs))
        if ordered_ids:
            return [json_msgs[i] for i in ordered_ids if i in json_msgs]
        # Fallback: no recoverable tree — return messages in arbitrary store order.
        return list(json_msgs.values())

    @staticmethod
    def _root_blob_id(meta_rows: list[tuple]) -> str | None:
        for _key, value in meta_rows:
            try:
                raw = value.decode() if isinstance(value, bytes) else value
                decoded = json.loads(bytes.fromhex(raw).decode("utf-8"))
                rid = decoded.get("latestRootBlobId")
                if rid:
                    return rid
            except Exception:
                continue
        return None

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
