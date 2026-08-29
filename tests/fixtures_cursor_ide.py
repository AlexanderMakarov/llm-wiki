"""Synthetic Cursor IDE ``state.vscdb`` helpers for tests (#2)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


def make_cursor_ide_db(
    path: Path,
    *,
    composers: list[dict[str, Any]],
) -> Path:
    """Write a minimal global ``state.vscdb`` with ``cursorDiskKV`` + ``composerHeaders``.

    Each composer dict supports:
      - composer_id (str, UUID-like)
      - bubbles: list of {bubble_id, type (1|2), text, created_at?}
      - conversation_order: optional list of bubble_ids (defaults to bubbles order)
      - is_archived, is_subagent (bool)
      - workspace_id (str | None)
      - created_at / last_updated_at (ms int)
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    con = sqlite3.connect(path)
    con.execute(
        "CREATE TABLE cursorDiskKV (key TEXT PRIMARY KEY, value BLOB)"
    )
    con.execute(
        """
        CREATE TABLE composerHeaders (
            composerId TEXT PRIMARY KEY,
            workspaceId TEXT,
            createdAt INTEGER,
            lastUpdatedAt INTEGER,
            isArchived INTEGER,
            isSubagent INTEGER,
            recency REAL,
            checkpointAt INTEGER,
            value BLOB
        )
        """
    )
    for c in composers:
        cid = c["composer_id"]
        bubbles = c.get("bubbles") or []
        order = c.get("conversation_order") or [b["bubble_id"] for b in bubbles]
        created = int(c.get("created_at", 1_700_000_000_000))
        updated = int(c.get("last_updated_at", created))
        conv = []
        by_id = {b["bubble_id"]: b for b in bubbles}
        for bid in order:
            b = by_id.get(bid, {"bubble_id": bid, "type": 1, "text": ""})
            conv.append({"type": b.get("type", 1), "bubbleId": bid, "text": b.get("text", "")})
        meta = {
            "composerId": cid,
            "createdAt": created,
            "lastUpdatedAt": updated,
            "status": "completed",
            "forceMode": "chat",
            "conversation": conv,
            "text": "",
            "richText": "",
        }
        con.execute(
            "INSERT INTO cursorDiskKV(key, value) VALUES (?, ?)",
            (f"composerData:{cid}", json.dumps(meta).encode()),
        )
        for b in bubbles:
            bid = b["bubble_id"]
            payload = {
                "type": b.get("type", 1),
                "bubbleId": bid,
                "text": b.get("text", ""),
                "toolResults": b.get("tool_results", []),
                "allThinkingBlocks": b.get("thinking", []),
                "isAgentic": bool(b.get("is_agentic", False)),
            }
            if "created_at" in b:
                payload["createdAt"] = b["created_at"]
            con.execute(
                "INSERT INTO cursorDiskKV(key, value) VALUES (?, ?)",
                (f"bubbleId:{cid}:{bid}", json.dumps(payload).encode()),
            )
        con.execute(
            """
            INSERT INTO composerHeaders(
                composerId, workspaceId, createdAt, lastUpdatedAt,
                isArchived, isSubagent, recency, checkpointAt, value
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                cid,
                c.get("workspace_id"),
                created,
                updated,
                1 if c.get("is_archived") else 0,
                1 if c.get("is_subagent") else 0,
                0.0,
                None,
                b"{}",
            ),
        )
    con.commit()
    con.close()
    return path
