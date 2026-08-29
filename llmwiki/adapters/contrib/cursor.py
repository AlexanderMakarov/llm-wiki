"""Cursor IDE adapter — Composer history from global ``state.vscdb``.

Reads ``cursorDiskKV`` / ``composerHeaders`` in Cursor's globalStorage DB.
Distinct from ``cursor_cli`` (Agent CLI ``~/.cursor/chats/.../store.db``).

Schema notes (verified against a real Linux install; see
``context/spec/176-cursor-ide-ingest/cursor-ide-store-inventory.md``):

- Sessions: ``composerHeaders`` (+ ``composerData:<composerId>``)
- Messages: ``bubbleId:<composerId>:<bubbleId>`` (``type`` 1=user, 2=assistant)
- Order: ``composerData.conversation[].bubbleId`` when ids match, else createdAt
- Headless: ``composerHeaders.isSubagent == 1``
- Archived: ``isArchived == 1`` — still ingested (same composerId)
- Project slug: ``cursor-<workspaceId[:12]>`` when workspaceId is set
"""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from llmwiki.adapters import register
from llmwiki.adapters.base import BaseAdapter, SessionRef
from llmwiki.adapters.contrib.cursor_slug import cursor_workspace_slug
from llmwiki.adapters.settings import adapter_block

_CURSOR_IDE_META = "cursor_ide_meta"
_LOCATOR_RE = re.compile(r"^cursor-ide:composer:(.+)$")


@register("cursor")
class CursorAdapter(BaseAdapter):
    """Cursor IDE — Composer threads from globalStorage/state.vscdb."""

    _DESCRIPTION_OVERRIDE = (
        "Cursor IDE — Composer ingest from globalStorage/state.vscdb (#2)"
    )

    ingest_ready = False

    SUPPORTED_SCHEMA_VERSIONS = ["v1"]
    is_ai_session = True

    DEFAULT_GLOBAL_DBS = [
        Path.home() / "Library" / "Application Support" / "Cursor" / "User" / "globalStorage" / "state.vscdb",
        Path.home() / ".config" / "Cursor" / "User" / "globalStorage" / "state.vscdb",
        Path.home() / "AppData" / "Roaming" / "Cursor" / "User" / "globalStorage" / "state.vscdb",
    ]

    DEFAULT_ROOTS = [
        Path.home() / "Library" / "Application Support" / "Cursor" / "User" / "workspaceStorage",
        Path.home() / ".config" / "Cursor" / "User" / "workspaceStorage",
        Path.home() / "AppData" / "Roaming" / "Cursor" / "User" / "workspaceStorage",
    ]

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        ad_cfg = adapter_block(config or {}, "cursor")
        roots = ad_cfg.get("roots") or []
        self.roots: list[Path] = (
            [Path(p).expanduser() for p in roots] if roots else list(self.DEFAULT_ROOTS)
        )
        gdb = ad_cfg.get("global_db")
        self._global_dbs: list[Path] = (
            [Path(gdb).expanduser()]
            if gdb
            else list(self.DEFAULT_GLOBAL_DBS)
        )
        # Cache headers/meta between discover and load within one adapter instance.
        self._header_cache: dict[str, dict[str, Any]] | None = None
        self._db_path: Path | None = None

    @property
    def session_store_path(self):  # type: ignore[override]
        # Availability: global DB or workspace roots.
        return [*self._global_dbs, *self.roots]

    def _resolve_global_db(self) -> Path | None:
        for p in self._global_dbs:
            p = Path(p).expanduser()
            if p.exists():
                return p
        return None

    def discover_sessions(self) -> list[Path]:
        """Unused by convert — prefer ``discover_session_refs``. Returns []."""
        return []

    def discover_session_refs(self) -> list[SessionRef]:
        db = self._resolve_global_db()
        if db is None:
            return []
        self._db_path = db
        headers = self._load_headers(db)
        self._header_cache = headers
        refs: list[SessionRef] = []
        for cid, hdr in headers.items():
            # Skip empty threads (no bubbles) — still discover? Spec: empty → filtered.
            # Discover all with header or composerData; empty filtered at load.
            mtime = _ms_to_unix(hdr.get("lastUpdatedAt") or hdr.get("createdAt")) or db.stat().st_mtime
            refs.append(
                SessionRef(
                    key=f"composer/{cid}",
                    mtime=mtime,
                    locator=f"cursor-ide:composer:{cid}",
                )
            )
        return refs

    def derive_project_slug(self, path: Path | str) -> str:
        cid = _composer_id_from_locator(path)
        if cid and self._header_cache is not None:
            wid = (self._header_cache.get(cid) or {}).get("workspaceId")
            if wid:
                return cursor_workspace_slug(str(wid))
        if cid:
            return cursor_workspace_slug(cid.replace("-", "")[:12] or cid[:12])
        return "cursor-unnamed"

    def load_records(self, path: Path | str) -> list[dict[str, Any]]:
        cid = _composer_id_from_locator(path)
        if not cid:
            return []
        db = self._db_path or self._resolve_global_db()
        if db is None:
            return []
        if self._header_cache is None:
            self._header_cache = self._load_headers(db)
        hdr = self._header_cache.get(cid) or {}
        bubbles = self._load_bubbles(db, cid)
        if not bubbles:
            return []
        meta: dict[str, Any] = {
            "type": _CURSOR_IDE_META,
            "sessionId": cid,
            "slug": cid.split("-", 1)[0][:12] if "-" in cid else cid[:12],
        }
        created = hdr.get("createdAt")
        iso = _ms_to_iso(created)
        if iso:
            meta["timestamp"] = iso
        if hdr.get("isArchived"):
            meta["isArchived"] = True
        if hdr.get("isSubagent"):
            meta["isSubagent"] = True
        if hdr.get("workspaceId"):
            meta["workspaceId"] = hdr["workspaceId"]
        return [meta, *bubbles]

    def normalize_records(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for rec in records:
            if not isinstance(rec, dict):
                continue
            if rec.get("type") == _CURSOR_IDE_META:
                out.append(rec)
                continue
            # Raw bubble shape from load_records
            if "bubbleId" in rec or rec.get("_cursor_ide_bubble"):
                btype = rec.get("type")
                text = _bubble_text(rec)
                if btype in (1, "1"):
                    out.append({"type": "user", "message": {"role": "user", "content": text}})
                elif btype in (2, "2"):
                    blocks = _assistant_blocks(rec, text)
                    if blocks:
                        out.append(
                            {
                                "type": "assistant",
                                "message": {"role": "assistant", "content": blocks},
                            }
                        )
                continue
            # Already normalized
            if rec.get("type") in ("user", "assistant"):
                out.append(rec)
        return out

    def is_headless_session(self, records: list[dict[str, Any]]) -> bool:
        """True for Composer threads marked ``isSubagent`` in composerHeaders."""
        for r in records:
            if isinstance(r, dict) and r.get("isSubagent"):
                return True
        return False

    # ─── SQLite helpers ────────────────────────────────────────────────

    def _load_headers(self, db: Path) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            tables = {
                r[0]
                for r in con.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            if "composerHeaders" in tables:
                for row in con.execute(
                    "SELECT composerId, workspaceId, createdAt, lastUpdatedAt, "
                    "isArchived, isSubagent FROM composerHeaders"
                ):
                    cid, wid, created, updated, archived, sub = row
                    if not cid:
                        continue
                    out[str(cid)] = {
                        "composerId": str(cid),
                        "workspaceId": wid,
                        "createdAt": created,
                        "lastUpdatedAt": updated,
                        "isArchived": bool(archived),
                        "isSubagent": bool(sub),
                    }
            # Ensure every composerData key is present (headers may be subset).
            if "cursorDiskKV" in tables:
                for (key,) in con.execute(
                    "SELECT key FROM cursorDiskKV WHERE typeof(key)='text' "
                    "AND key LIKE 'composerData:%'"
                ):
                    cid = key.split(":", 1)[1]
                    if cid not in out:
                        out[cid] = {
                            "composerId": cid,
                            "workspaceId": None,
                            "createdAt": None,
                            "lastUpdatedAt": None,
                            "isArchived": False,
                            "isSubagent": False,
                        }
                    # Enrich timestamps from composerData when missing
                    if out[cid].get("createdAt") is None:
                        val = con.execute(
                            "SELECT value FROM cursorDiskKV WHERE key=?", (key,)
                        ).fetchone()
                        if val:
                            try:
                                obj = _json_obj(val[0])
                                out[cid]["createdAt"] = obj.get("createdAt")
                                out[cid]["lastUpdatedAt"] = obj.get("lastUpdatedAt") or obj.get(
                                    "createdAt"
                                )
                            except Exception:
                                pass
        finally:
            con.close()
        return out

    def _load_bubbles(self, db: Path, composer_id: str) -> list[dict[str, Any]]:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            rows = con.execute(
                "SELECT key, value FROM cursorDiskKV WHERE typeof(key)='text' "
                "AND key LIKE ?",
                (f"bubbleId:{composer_id}:%",),
            ).fetchall()
            by_id: dict[str, dict[str, Any]] = {}
            for key, val in rows:
                try:
                    obj = _json_obj(val)
                except Exception:
                    continue
                if not isinstance(obj, dict):
                    continue
                bid = key.rsplit(":", 1)[-1]
                obj["_cursor_ide_bubble"] = True
                obj.setdefault("bubbleId", bid)
                by_id[bid] = obj

            order: list[str] = []
            meta_row = con.execute(
                "SELECT value FROM cursorDiskKV WHERE key=?",
                (f"composerData:{composer_id}",),
            ).fetchone()
            if meta_row:
                try:
                    meta = _json_obj(meta_row[0])
                    for el in meta.get("conversation") or []:
                        if isinstance(el, dict) and el.get("bubbleId"):
                            order.append(str(el["bubbleId"]))
                except Exception:
                    pass

            ordered: list[dict[str, Any]] = []
            seen: set[str] = set()
            for bid in order:
                if bid in by_id and bid not in seen:
                    ordered.append(by_id[bid])
                    seen.add(bid)
            rest = [b for bid, b in by_id.items() if bid not in seen]
            rest.sort(key=lambda b: (b.get("createdAt") is None, b.get("createdAt") or 0, b.get("bubbleId") or ""))
            ordered.extend(rest)
            return ordered
        finally:
            con.close()


def _composer_id_from_locator(path: Path | str) -> str | None:
    s = str(path)
    m = _LOCATOR_RE.match(s)
    if m:
        return m.group(1)
    return None


def _json_obj(val: Any) -> dict[str, Any]:
    if isinstance(val, dict):
        return val
    if isinstance(val, (bytes, bytearray)):
        return json.loads(val.decode("utf-8"))
    if isinstance(val, str):
        return json.loads(val)
    raise TypeError(type(val))


def _ms_to_unix(ms: Any) -> float | None:
    if isinstance(ms, bool) or ms is None:
        return None
    try:
        v = float(ms)
    except (TypeError, ValueError):
        return None
    if v <= 0:
        return None
    return v / 1000.0 if v >= 1_000_000_000_000 else v


def _ms_to_iso(ms: Any) -> str | None:
    seconds = _ms_to_unix(ms)
    if seconds is None:
        return None
    try:
        ts = datetime.fromtimestamp(seconds, tz=UTC)
    except (OverflowError, OSError, ValueError):
        return None
    return ts.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _bubble_text(rec: dict[str, Any]) -> str:
    text = rec.get("text")
    if isinstance(text, str) and text.strip():
        return text
    rich = rec.get("richText")
    if isinstance(rich, str) and rich.strip():
        # Strip crude HTML/tags for wiki plaintext.
        return re.sub(r"<[^>]+>", "", rich).strip()
    return ""


def _assistant_blocks(rec: dict[str, Any], text: str) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    thinking = rec.get("allThinkingBlocks") or []
    if isinstance(thinking, list):
        for t in thinking:
            if isinstance(t, str) and t.strip():
                blocks.append({"type": "thinking", "thinking": t})
            elif isinstance(t, dict):
                body = t.get("text") or t.get("thinking") or ""
                if body:
                    blocks.append({"type": "thinking", "thinking": str(body)})
    if text:
        blocks.append({"type": "text", "text": text})
    tools = rec.get("toolResults") or []
    if isinstance(tools, list):
        for tr in tools:
            if isinstance(tr, dict):
                blocks.append(
                    {
                        "type": "tool_use",
                        "name": str(tr.get("name") or tr.get("toolName") or "tool"),
                        "input": tr.get("args") or tr.get("input") or tr,
                    }
                )
            elif tr:
                blocks.append({"type": "text", "text": str(tr)})
    former = rec.get("toolFormerData")
    if isinstance(former, dict) and former.get("name"):
        blocks.append(
            {
                "type": "tool_use",
                "name": str(former.get("name") or "tool"),
                "input": former.get("params") or former.get("input") or {},
            }
        )
    return blocks
