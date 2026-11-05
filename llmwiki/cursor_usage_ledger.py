"""Cursor IDE usage ledger scanner — ``state.vscdb`` bubble token counts (#396).

Read-only scan of global ``cursorDiskKV`` ``bubbleId:*`` rows for
``tokenCount.{inputTokens,outputTokens}``. Aggregates per ``composerId`` (IDE
Composer session id — same as ``cursor_ide`` ``sessionId``). Does not invent
CLI ``store.db`` usage; CLI chat folder UUIDs are not present in this DB.

Precedence vs other Cursor token sources (documented in UPGRADING):

1. Stop-hook / stream-json JSONL (``conversation_id``)
2. This local ledger (``composerId`` / matching ``sessionId``)
3. Opt-in ``cursor_usage_api`` (#356)
"""
from __future__ import annotations

import json
import sqlite3
import time
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from llmwiki.cursor_token_usage import map_cursor_usage_to_claude_usage
from llmwiki.cursor_usage_api import conversation_has_hook_usage
from llmwiki.usage import usage_dir

CACHE_NAME = "cursor-usage-ledger-cache.json"
_VOLATILE_TTL_SECONDS = 60.0
_BUCKET_KEYS = ("input", "cache_creation", "cache_read", "output")

# Process-local volatile scan cache (mtime/size + short TTL while IDE rewrites DB).
_volatile: dict[str, Any] = {"path": None, "mtime": 0.0, "size": 0, "expires": 0.0, "data": None}


def resolve_cursor_usage_ledger_enabled(config: Mapping[str, Any] | None) -> bool:
    """Default **on** — local read-only; set ``cursor_usage_ledger: false`` to disable."""
    if not isinstance(config, Mapping):
        return True
    raw = config.get("cursor_usage_ledger")
    if raw is None and isinstance(config.get("filters"), Mapping):
        raw = config["filters"].get("cursor_usage_ledger")
    if raw is None:
        return True
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        text = raw.strip().lower()
        if text in ("0", "false", "off", "no"):
            return False
        if text in ("1", "true", "on", "yes"):
            return True
    return True


def global_vscdb_path() -> Path:
    return Path.home() / ".config" / "Cursor" / "User" / "globalStorage" / "state.vscdb"


def cache_path(vault: Path) -> Path:
    return usage_dir(vault) / CACHE_NAME


def _read_json_file(path: Path) -> dict[str, Any] | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, dict) else None


def load_cache(vault: Path) -> dict[str, Any]:
    path = cache_path(vault)
    if not path.is_file():
        return {"by_conversation": {}, "db_mtime": 0, "db_size": 0}
    doc = _read_json_file(path)
    if not doc:
        return {"by_conversation": {}, "db_mtime": 0, "db_size": 0}
    by_conv = doc.get("by_conversation")
    if not isinstance(by_conv, dict):
        by_conv = {}
    try:
        mtime = float(doc.get("db_mtime") or 0)
    except (TypeError, ValueError):
        mtime = 0.0
    try:
        size = int(doc.get("db_size") or 0)
    except (TypeError, ValueError):
        size = 0
    return {"by_conversation": by_conv, "db_mtime": mtime, "db_size": size}


def save_cache(vault: Path, data: Mapping[str, Any]) -> None:
    d = usage_dir(vault)
    d.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(dict(data), indent=2, ensure_ascii=False) + "\n"
    cache_path(vault).write_text(payload, encoding="utf-8")


def _buckets_from_token_count(inp: int, out: int) -> dict[str, int] | None:
    mapped = map_cursor_usage_to_claude_usage(
        {"inputTokens": max(0, inp), "outputTokens": max(0, out)}
    )
    if not mapped:
        return None
    return {
        "input": int(mapped.get("input_tokens") or 0),
        "cache_creation": int(mapped.get("cache_creation_input_tokens") or 0),
        "cache_read": int(mapped.get("cache_read_input_tokens") or 0),
        "output": int(mapped.get("output_tokens") or 0),
    }


def _merge_bucket(dst: dict[str, int], src: Mapping[str, int]) -> None:
    for key in _BUCKET_KEYS:
        dst[key] = int(dst.get(key) or 0) + int(src.get(key) or 0)


def _parse_bubble_token_count(val: bytes | str | None) -> tuple[int, int] | None:
    if val is None:
        return None
    if isinstance(val, bytes):
        text = val.decode("utf-8", errors="replace")
    else:
        text = str(val)
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict):
        return None
    tc = obj.get("tokenCount")
    if not isinstance(tc, dict):
        return None
    try:
        inp = int(tc.get("inputTokens") or 0)
        out = int(tc.get("outputTokens") or 0)
    except (TypeError, ValueError):
        return None
    if inp == 0 and out == 0:
        return None
    return inp, out


def scan_global_vscdb(db_path: Path) -> dict[str, Any]:
    """Aggregate measurable bubble ``tokenCount`` per ``composerId``."""
    out: dict[str, Any] = {
        "by_conversation": {},
        "db_mtime": 0.0,
        "db_size": 0,
        "scanned_at": datetime.now(UTC).isoformat(),
    }
    if not db_path.is_file():
        return out
    try:
        st = db_path.stat()
        out["db_mtime"] = st.st_mtime
        out["db_size"] = st.st_size
    except OSError:
        return out

    by_conv: dict[str, dict[str, Any]] = {}
    try:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.Error:
        return out
    try:
        tables = {
            r[0]
            for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        if "cursorDiskKV" not in tables:
            return out
        header_last: dict[str, int] = {}
        if "composerHeaders" in tables:
            for cid, last in con.execute(
                "SELECT composerId, lastUpdatedAt FROM composerHeaders"
            ):
                if cid and last is not None:
                    try:
                        header_last[str(cid)] = int(last)
                    except (TypeError, ValueError):
                        pass
        cur = con.execute(
            "SELECT key, value FROM cursorDiskKV WHERE key LIKE 'bubbleId:%'"
        )
        for key, val in cur:
            parts = str(key).split(":", 2)
            if len(parts) < 3:
                continue
            composer_id = parts[1].strip()
            if not composer_id:
                continue
            parsed = _parse_bubble_token_count(val)
            if parsed is None:
                continue
            inp, oout = parsed
            buckets = _buckets_from_token_count(inp, oout)
            if buckets is None:
                continue
            row = by_conv.setdefault(
                composer_id,
                {
                    "totals": {k: 0 for k in _BUCKET_KEYS},
                    "bubble_count": 0,
                    "source": "cursor_usage_ledger",
                },
            )
            _merge_bucket(row["totals"], buckets)
            row["bubble_count"] = int(row.get("bubble_count") or 0) + 1
            if composer_id in header_last:
                row["last_updated_ms"] = header_last[composer_id]
    except sqlite3.Error:
        return out
    finally:
        con.close()

    # Drop empty totals
    cleaned: dict[str, Any] = {}
    for cid, row in by_conv.items():
        totals = row.get("totals")
        if not isinstance(totals, dict):
            continue
        if not any(int(totals.get(k) or 0) for k in _BUCKET_KEYS):
            continue
        cleaned[cid] = row
    out["by_conversation"] = cleaned
    return out


def _volatile_get(db_path: Path) -> dict[str, Any] | None:
    global _volatile
    try:
        st = db_path.stat()
    except OSError:
        return None
    now = time.time()
    if (
        _volatile.get("path") == db_path
        and _volatile.get("mtime") == st.st_mtime
        and _volatile.get("size") == st.st_size
        and now < float(_volatile.get("expires") or 0)
        and isinstance(_volatile.get("data"), dict)
    ):
        return _volatile["data"]
    data = scan_global_vscdb(db_path)
    _volatile = {
        "path": db_path,
        "mtime": st.st_mtime,
        "size": st.st_size,
        "expires": now + _VOLATILE_TTL_SECONDS,
        "data": data,
    }
    return data


def _db_unchanged(cache: Mapping[str, Any], db_path: Path) -> bool:
    try:
        st = db_path.stat()
    except OSError:
        return False
    try:
        return (
            float(cache.get("db_mtime") or 0) == st.st_mtime
            and int(cache.get("db_size") or 0) == st.st_size
        )
    except (TypeError, ValueError):
        return False


def sync_cursor_usage_ledger(
    vault: Path,
    config: Mapping[str, Any] | None,
    *,
    dry_run: bool = False,
    force_rescan: bool = False,
) -> list[str]:
    """Refresh ``usage/cursor-usage-ledger-cache.json`` from global ``state.vscdb``."""
    if not resolve_cursor_usage_ledger_enabled(config):
        return []
    db_path = global_vscdb_path()
    if not db_path.is_file():
        return ["cursor usage ledger: global state.vscdb not found (skipped)"]

    cache = load_cache(vault)
    if not force_rescan and _db_unchanged(cache, db_path):
        count = len(cache.get("by_conversation") or {})
        return [f"cursor usage ledger: unchanged ({count} composer thread(s) with tokens)"]

    if dry_run:
        scanned = _volatile_get(db_path) or scan_global_vscdb(db_path)
        n = len(scanned.get("by_conversation") or {})
        return [f"cursor usage ledger: would rescan ({n} composer thread(s) with tokens)"]

    scanned = _volatile_get(db_path) or scan_global_vscdb(db_path)
    save_cache(vault, scanned)
    n = len(scanned.get("by_conversation") or {})
    return [f"cursor usage ledger: merged {n} composer thread(s) with tokens"]


def ledger_totals_for_conversation(vault: Path, conversation_id: str) -> dict[str, int] | None:
    cid = (conversation_id or "").strip()
    if not cid or conversation_has_hook_usage(cid):
        return None
    cache = load_cache(vault)
    by_conv = cache.get("by_conversation")
    if not isinstance(by_conv, dict):
        return None
    row = by_conv.get(cid)
    if not isinstance(row, dict):
        return None
    totals = row.get("totals")
    if not isinstance(totals, dict):
        return None
    out = {
        "input": int(totals.get("input") or 0),
        "cache_creation": int(totals.get("cache_creation") or 0),
        "cache_read": int(totals.get("cache_read") or 0),
        "output": int(totals.get("output") or 0),
    }
    if not any(out.values()):
        return None
    return out


def usage_records_from_ledger_cache(
    conversation_id: str,
    vault: Path,
) -> list[dict[str, Any]]:
    """One synthetic assistant row when the vault ledger cache has totals."""
    totals = ledger_totals_for_conversation(vault, conversation_id)
    if totals is None:
        return []
    mapped = {
        "input_tokens": totals["input"],
        "cache_creation_input_tokens": totals["cache_creation"],
        "cache_read_input_tokens": totals["cache_read"],
        "output_tokens": totals["output"],
    }
    return [
        {
            "type": "assistant",
            "message": {"role": "assistant", "content": [], "usage": mapped},
            "source": "cursor_usage_ledger",
        }
    ]


def conversation_has_ledger_usage(vault: Path, conversation_id: str) -> bool:
    return ledger_totals_for_conversation(vault, conversation_id) is not None


def _last_activity_from_ledger_row(row: Mapping[str, Any]) -> str:
    try:
        ms = int(row.get("last_updated_ms") or 0)
    except (TypeError, ValueError):
        ms = 0
    if ms > 0:
        return datetime.fromtimestamp(ms / 1000.0, tz=UTC).isoformat()
    return datetime.now(UTC).isoformat()


def apply_ledger_totals_to_raw_sessions(
    vault: Path,
    *,
    dry_run: bool = False,
) -> tuple[int, int]:
    """Upsert ledger totals for ``sessionId`` keys; hook JSONL still wins."""
    from llmwiki._frontmatter import parse_frontmatter  # noqa: PLC0415
    from llmwiki.adapters import discover_all  # noqa: PLC0415
    from llmwiki.cursor_usage_api import _raw_paths_by_session_id  # noqa: PLC0415
    from llmwiki.migrate_session_tokens import (  # noqa: PLC0415
        _adapter_name_from_meta,
        _last_activity_from_meta,
        patch_raw_token_totals,
    )

    discover_all()
    from llmwiki.session_tokens_usage import (  # noqa: PLC0415
        emit_session_tokens_sidecar,
        upsert_session_tokens,
    )

    cache = load_cache(vault)
    by_conv = cache.get("by_conversation")
    if not isinstance(by_conv, dict) or not by_conv:
        return 0, 0

    raw_by_sid = _raw_paths_by_session_id(vault / "raw" / "sessions")
    patched = upserted = 0
    site_dir = vault / "site"

    for session_key, row in sorted(by_conv.items()):
        if not isinstance(session_key, str) or not session_key.strip():
            continue
        session_key = session_key.strip()
        if not isinstance(row, Mapping):
            continue
        if conversation_has_hook_usage(session_key):
            continue
        totals = row.get("totals")
        if not isinstance(totals, Mapping):
            continue
        bucket = {
            "input": int(totals.get("input") or 0),
            "cache_creation": int(totals.get("cache_creation") or 0),
            "cache_read": int(totals.get("cache_read") or 0),
            "output": int(totals.get("output") or 0),
        }
        if not any(bucket.values()):
            continue

        raw_path = raw_by_sid.get(session_key)
        in_raw = raw_path is not None
        metrics_only = not in_raw
        last_activity = _last_activity_from_ledger_row(row)

        agent = "cursor_ide"
        if raw_path is not None:
            try:
                text = raw_path.read_text(encoding="utf-8")
            except OSError:
                text = ""
            if text:
                meta, _body = parse_frontmatter(text)
                last_activity = _last_activity_from_meta(meta, raw_path.stat().st_mtime)
                resolved = _adapter_name_from_meta(meta)
                if resolved in ("cursor_ide", "cursor_cli"):
                    agent = resolved
                existing_line = meta.get("token_totals")
                if existing_line is None or not str(existing_line).strip():
                    if dry_run:
                        patched += 1
                    else:
                        new_text = patch_raw_token_totals(text, bucket)
                        if new_text != text:
                            raw_path.write_text(new_text, encoding="utf-8")
                            patched += 1

        if dry_run:
            upserted += 1
            continue

        fp = f"cursor-usage-ledger:{session_key}:{json.dumps(bucket, sort_keys=True)}"
        if upsert_session_tokens(
            vault,
            session_key=session_key,
            agent=agent,
            totals=bucket,
            fingerprint=fp,
            last_activity=last_activity,
            in_raw=in_raw,
            metrics_only=metrics_only,
        ):
            upserted += 1

    if upserted and site_dir.is_dir() and not dry_run:
        emit_session_tokens_sidecar(vault, site_dir)
    return patched, upserted


def bubble_token_usage_record(rec: Mapping[str, Any]) -> dict[str, int] | None:
    """Map one IDE bubble ``tokenCount`` blob to Claude usage fields."""
    if not isinstance(rec, Mapping):
        return None
    tc = rec.get("tokenCount")
    if not isinstance(tc, Mapping):
        return None
    try:
        inp = int(tc.get("inputTokens") or 0)
        out = int(tc.get("outputTokens") or 0)
    except (TypeError, ValueError):
        return None
    if inp == 0 and out == 0:
        return None
    buckets = _buckets_from_token_count(inp, out)
    if buckets is None:
        return None
    return {
        "input_tokens": buckets["input"],
        "cache_creation_input_tokens": buckets["cache_creation"],
        "cache_read_input_tokens": buckets["cache_read"],
        "output_tokens": buckets["output"],
    }
