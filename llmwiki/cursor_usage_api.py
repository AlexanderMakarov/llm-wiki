"""Cursor dashboard / Admin usage API for ACP sessions (#356).

Undocumented Cursor web endpoints supply per-request ``tokenUsage`` keyed by
``conversationId`` when IDE hooks and ACP streams carry no usage. Opt-in via
``cursor_usage_api`` in sessions config (default ``off``). Credentials are read
from local Cursor CLI / IDE stores only — never logged or written to the vault
except aggregated token totals.
"""
from __future__ import annotations

import base64
import json
import os
import sqlite3
import time
import urllib.error
import urllib.request
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from llmwiki.cursor_token_events import usage_records_for_conversation
from llmwiki.cursor_token_usage import map_cursor_usage_to_claude_usage
from llmwiki.sync.lookback import resolve_effective_since
from llmwiki.usage import usage_dir

CACHE_NAME = "cursor-usage-api-cache.json"
STATE_NAME = "cursor-usage-api-state.json"
DASHBOARD_URL = "https://cursor.com/api/dashboard/get-filtered-usage-events"
ADMIN_URL = "https://api.cursor.com/teams/filtered-usage-events"
_POLL_MIN_SECONDS = 3600
#: Backfill cap when no sync lookback is configured (dashboard retention is
#: undocumented; months of history were observed).
_MAX_BACKFILL_DAYS = 365
_DEFAULT_PAGE_SIZE = 500
_ORIGIN = "https://cursor.com"

_ACTIVE_VAULT: Path | None = None


def set_active_vault(vault: Path | None) -> None:
    """During ``sync``, the convert loop sets the vault for adapter merge."""
    global _ACTIVE_VAULT
    _ACTIVE_VAULT = vault


def active_vault() -> Path | None:
    return _ACTIVE_VAULT


def resolve_cursor_usage_api_mode(config: Mapping[str, Any] | None) -> str:
    """Return ``off``, ``dashboard``, or ``admin``."""
    if not isinstance(config, Mapping):
        return "off"
    raw = config.get("cursor_usage_api")
    if raw is None and isinstance(config.get("filters"), Mapping):
        raw = config["filters"].get("cursor_usage_api")
    if not isinstance(raw, str):
        return "off"
    mode = raw.strip().lower()
    if mode in ("dashboard", "admin"):
        return mode
    return "off"


def _b64url_json(segment: str) -> dict[str, Any] | None:
    pad = "=" * (-len(segment) % 4)
    try:
        raw = base64.urlsafe_b64decode(segment + pad)
        obj = json.loads(raw.decode("utf-8"))
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    return obj if isinstance(obj, dict) else None


def user_id_from_jwt(access_token: str) -> str | None:
    """Last ``|`` segment of JWT ``sub`` (Cursor WorkOS session shape)."""
    parts = access_token.split(".")
    if len(parts) < 2:
        return None
    payload = _b64url_json(parts[1])
    if not payload:
        return None
    sub = payload.get("sub")
    if not isinstance(sub, str) or not sub.strip():
        return None
    if "|" in sub:
        return sub.rsplit("|", 1)[-1].strip() or None
    return sub.strip()


def _read_json_file(path: Path) -> dict[str, Any] | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, dict) else None


def load_cli_auth_json() -> dict[str, Any] | None:
    path = Path.home() / ".config" / "cursor" / "auth.json"
    return _read_json_file(path)


def load_cli_config_auth_info() -> dict[str, Any] | None:
    path = Path.home() / ".cursor" / "cli-config.json"
    doc = _read_json_file(path)
    if not doc:
        return None
    info = doc.get("authInfo")
    return info if isinstance(info, dict) else None


def load_ide_access_token() -> str | None:
    """Read ``cursorAuth/accessToken`` from IDE globalStorage (read-only)."""
    db = Path.home() / ".config" / "Cursor" / "User" / "globalStorage" / "state.vscdb"
    if not db.is_file():
        return None
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            row = con.execute(
                "SELECT value FROM ItemTable WHERE key = ?",
                ("cursorAuth/accessToken",),
            ).fetchone()
        finally:
            con.close()
    except sqlite3.Error:
        return None
    if not row or row[0] is None:
        return None
    if isinstance(row[0], bytes):
        text = row[0].decode("utf-8", errors="replace").strip()
    else:
        text = str(row[0]).strip()
    return text or None


def load_cursor_session_credentials() -> tuple[str, str] | None:
    """Return ``(user_id, access_token)`` from local stores, or ``None``."""
    access: str | None = None
    cli = load_cli_auth_json()
    if cli and isinstance(cli.get("accessToken"), str):
        access = cli["accessToken"].strip() or None
    if not access:
        access = load_ide_access_token()
    if not access:
        return None

    user_id: str | None = None
    auth_info = load_cli_config_auth_info()
    if auth_info and isinstance(auth_info.get("userId"), str):
        user_id = auth_info["userId"].strip() or None
    if not user_id:
        user_id = user_id_from_jwt(access)
    if not user_id:
        return None
    return user_id, access


def load_admin_api_key(config: Mapping[str, Any] | None) -> str | None:
    env = os.environ.get("CURSOR_ADMIN_API_KEY", "").strip()
    if env:
        return env
    if isinstance(config, Mapping):
        raw = config.get("cursor_usage_api_admin_key")
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    return None


def cache_path(vault: Path) -> Path:
    return usage_dir(vault) / CACHE_NAME


def state_path(vault: Path) -> Path:
    return usage_dir(vault) / STATE_NAME


def load_cache(vault: Path) -> dict[str, Any]:
    path = cache_path(vault)
    if not path.is_file():
        return {"by_conversation": {}, "high_water_ms": 0}
    doc = _read_json_file(path)
    if not doc:
        return {"by_conversation": {}, "high_water_ms": 0}
    by_conv = doc.get("by_conversation")
    if not isinstance(by_conv, dict):
        by_conv = {}
    try:
        hw = int(doc.get("high_water_ms") or 0)
    except (TypeError, ValueError):
        hw = 0
    return {"by_conversation": by_conv, "high_water_ms": hw}


def save_cache(vault: Path, data: Mapping[str, Any]) -> None:
    d = usage_dir(vault)
    d.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(dict(data), indent=2, ensure_ascii=False) + "\n"
    cache_path(vault).write_text(payload, encoding="utf-8")


def load_state(vault: Path) -> dict[str, Any]:
    path = state_path(vault)
    if not path.is_file():
        return {}
    doc = _read_json_file(path)
    return doc if isinstance(doc, dict) else {}


def save_state(vault: Path, data: Mapping[str, Any]) -> None:
    d = usage_dir(vault)
    d.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(dict(data), indent=2, ensure_ascii=False) + "\n"
    state_path(vault).write_text(payload, encoding="utf-8")


def _event_dedupe_key(event: Mapping[str, Any]) -> str:
    ts = event.get("timestamp")
    cid = event.get("conversationId") or event.get("conversation_id") or ""
    model = event.get("model") or ""
    return f"{cid}|{ts}|{model}"


def _parse_dashboard_events(body: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = body.get("usageEventsDisplay")
    if not isinstance(rows, list):
        return []
    out: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row, dict):
            out.append(row)
    return out


def _parse_admin_events(body: Mapping[str, Any]) -> list[dict[str, Any]]:
    for key in ("usageEvents", "usageEventsDisplay", "events"):
        rows = body.get(key)
        if isinstance(rows, list):
            return [r for r in rows if isinstance(r, dict)]
    return []


def _http_post_json(
    url: str,
    payload: Mapping[str, Any],
    *,
    headers: Mapping[str, str],
    basic_user: str | None = None,
    timeout: float = 60.0,
) -> tuple[int, dict[str, Any] | None, str | None]:
    data = json.dumps(payload).encode("utf-8")
    req_headers = {"Content-Type": "application/json", **dict(headers)}
    req = urllib.request.Request(url, data=data, headers=req_headers, method="POST")
    if basic_user:
        token = base64.b64encode(f"{basic_user}:".encode()).decode("ascii")
        req.add_header("Authorization", f"Basic {token}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = int(getattr(resp, "status", 200) or 200)
            text = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        status = exc.code
        retry = exc.headers.get("Retry-After") if exc.headers else None
        detail = retry or exc.reason or "http error"
        try:
            text = exc.read().decode("utf-8", errors="replace")
            parsed = json.loads(text) if text.strip() else None
        except (OSError, json.JSONDecodeError):
            parsed = None
        return status, parsed if isinstance(parsed, dict) else None, str(detail)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return 0, None, str(exc)
    try:
        parsed = json.loads(text) if text.strip() else {}
    except json.JSONDecodeError:
        return status, None, "invalid json response"
    return status, parsed if isinstance(parsed, dict) else None, None


def fetch_dashboard_page(
    *,
    user_id: str,
    access_token: str,
    start_ms: int,
    end_ms: int,
    page: int,
    page_size: int = _DEFAULT_PAGE_SIZE,
) -> tuple[int, dict[str, Any] | None, str | None]:
    cookie = f"WorkosCursorSessionToken={user_id}%3A%3A{access_token}"
    headers = {
        "Origin": _ORIGIN,
        "Cookie": cookie,
    }
    body = {
        "teamId": 0,
        "startDate": start_ms,
        "endDate": end_ms,
        "page": page,
        "pageSize": page_size,
    }
    return _http_post_json(DASHBOARD_URL, body, headers=headers)


def fetch_admin_page(
    *,
    api_key: str,
    start_ms: int,
    end_ms: int,
    page: int,
    page_size: int = _DEFAULT_PAGE_SIZE,
) -> tuple[int, dict[str, Any] | None, str | None]:
    body = {
        "startDate": start_ms,
        "endDate": end_ms,
        "page": page,
        "pageSize": page_size,
    }
    return _http_post_json(ADMIN_URL, body, headers={}, basic_user=api_key)


def _claude_buckets_from_events(events: list[Mapping[str, Any]]) -> dict[str, int]:
    totals = {"input": 0, "cache_creation": 0, "cache_read": 0, "output": 0}
    for event in events:
        usage = event.get("tokenUsage")
        if not isinstance(usage, Mapping):
            usage = event
        mapped = map_cursor_usage_to_claude_usage(usage)
        if not mapped:
            continue
        totals["input"] += int(mapped.get("input_tokens") or 0)
        totals["cache_creation"] += int(mapped.get("cache_creation_input_tokens") or 0)
        totals["cache_read"] += int(mapped.get("cache_read_input_tokens") or 0)
        totals["output"] += int(mapped.get("output_tokens") or 0)
    return totals


def conversation_has_hook_usage(conversation_id: str) -> bool:
    """True when stop-hook / stream-json JSONL already has measurable usage."""
    cid = (conversation_id or "").strip()
    if not cid:
        return False
    return bool(usage_records_for_conversation(cid))


def api_totals_for_conversation(vault: Path, conversation_id: str) -> dict[str, int] | None:
    """Aggregated four-bucket totals from the vault API cache."""
    cid = (conversation_id or "").strip()
    if not cid:
        return None
    if conversation_has_hook_usage(cid):
        return None
    from llmwiki.cursor_usage_ledger import conversation_has_ledger_usage  # noqa: PLC0415

    if conversation_has_ledger_usage(vault, cid):
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


def usage_records_from_api_cache(
    conversation_id: str,
    vault: Path,
) -> list[dict[str, Any]]:
    """Synthetic assistant records from API cache (one per cached event)."""
    cid = (conversation_id or "").strip()
    if not cid or conversation_has_hook_usage(cid):
        return []
    from llmwiki.cursor_usage_ledger import conversation_has_ledger_usage  # noqa: PLC0415

    if conversation_has_ledger_usage(vault, cid):
        return []
    cache = load_cache(vault)
    by_conv = cache.get("by_conversation")
    if not isinstance(by_conv, dict):
        return []
    row = by_conv.get(cid)
    if not isinstance(row, dict):
        return []
    events = row.get("events")
    if not isinstance(events, list):
        return []
    out: list[dict[str, Any]] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        usage = event.get("tokenUsage")
        if not isinstance(usage, Mapping):
            usage = event
        mapped = map_cursor_usage_to_claude_usage(usage)
        if mapped is None:
            continue
        out.append(
            {
                "type": "assistant",
                "message": {"role": "assistant", "content": [], "usage": mapped},
                "source": "cursor_usage_api",
            }
        )
    return out


def _merge_events_into_cache(
    cache: dict[str, Any],
    events: list[dict[str, Any]],
    *,
    source: str,
) -> int:
    by_conv = cache.setdefault("by_conversation", {})
    if not isinstance(by_conv, dict):
        by_conv = {}
        cache["by_conversation"] = by_conv
    seen: set[str] = set()
    for conv_row in by_conv.values():
        if not isinstance(conv_row, dict):
            continue
        keys = conv_row.get("_keys")
        if isinstance(keys, list):
            for k in keys:
                if isinstance(k, str):
                    seen.add(k)
            continue
        evs = conv_row.get("events")
        if isinstance(evs, list):
            for ev in evs:
                if isinstance(ev, dict):
                    seen.add(_event_dedupe_key(ev))
    added = 0
    high_water = int(cache.get("high_water_ms") or 0)
    for event in events:
        key = _event_dedupe_key(event)
        if key in seen:
            continue
        seen.add(key)
        cid = event.get("conversationId") or event.get("conversation_id")
        if not isinstance(cid, str) or not cid.strip():
            continue
        cid = cid.strip()
        try:
            ts = int(event.get("timestamp") or 0)
        except (TypeError, ValueError):
            ts = 0
        if ts > high_water:
            high_water = ts
        row = by_conv.get(cid)
        if not isinstance(row, dict):
            row = {"events": [], "_keys": [], "source": source}
            by_conv[cid] = row
        ev_list = row.setdefault("events", [])
        key_list = row.setdefault("_keys", [])
        if not isinstance(ev_list, list) or not isinstance(key_list, list):
            continue
        ev_list.append(event)
        key_list.append(key)
        added += 1
    cache["high_water_ms"] = high_water
    for _cid, row in by_conv.items():
        if not isinstance(row, dict):
            continue
        evs = row.get("events")
        if not isinstance(evs, list):
            continue
        row["totals"] = _claude_buckets_from_events(evs)
        row["source"] = row.get("source") or source
    return added


def backfill_floor_ms(config: Mapping[str, Any] | None, *, now_ms: int) -> int:
    """Oldest event time to fetch: the ``cursor_cli`` sync lookback.

    Uses ``adapters.cursor_cli.since`` / ``filters.since`` so Tokens cover the
    same window as session ingest. With no lookback (or an invalid one), the
    floor is :data:`_MAX_BACKFILL_DAYS` ago.
    """
    cap_ms = now_ms - int(timedelta(days=_MAX_BACKFILL_DAYS).total_seconds() * 1000)
    try:
        since_dt = resolve_effective_since(
            None, dict(config) if isinstance(config, Mapping) else None, "cursor_cli"
        )
    except ValueError:
        since_dt = None
    if since_dt is None:
        return cap_ms
    if since_dt.tzinfo is None:
        since_dt = since_dt.replace(tzinfo=UTC)
    return max(cap_ms, int(since_dt.timestamp() * 1000))


def should_poll_now(vault: Path, *, force: bool = False) -> bool:
    if force:
        return True
    st = load_state(vault)
    last = st.get("last_poll_epoch")
    try:
        last_f = float(last)
    except (TypeError, ValueError):
        return True
    return (time.time() - last_f) >= _POLL_MIN_SECONDS


def sync_cursor_usage_api(
    vault: Path,
    config: Mapping[str, Any] | None,
    *,
    dry_run: bool = False,
    force_poll: bool = False,
) -> list[str]:
    """Fetch usage events and merge into ``usage/cursor-usage-api-cache.json``.

    Returns human-readable status lines (fail-soft). Never includes secrets.
    """
    mode = resolve_cursor_usage_api_mode(config)
    if mode == "off":
        return []
    if dry_run:
        return [f"cursor usage api: skipped (dry-run, mode={mode})"]
    if not should_poll_now(vault, force=force_poll):
        return ["cursor usage api: skipped (polled within the last hour)"]

    cache = load_cache(vault)
    st = load_state(vault)
    now_ms = int(time.time() * 1000)
    floor_ms = backfill_floor_ms(config, now_ms=now_ms)
    try:
        backfilled_from = int(st.get("backfilled_from_ms") or 0)
    except (TypeError, ValueError):
        backfilled_from = 0
    needs_backfill = backfilled_from <= 0 or floor_ms < backfilled_from
    start_ms = int(cache.get("high_water_ms") or 0)
    if needs_backfill or start_ms <= 0:
        start_ms = floor_ms

    messages: list[str] = []
    all_events: list[dict[str, Any]] = []

    if mode == "dashboard":
        creds = load_cursor_session_credentials()
        if not creds:
            return ["cursor usage api: no local Cursor session token (dashboard)"]
        user_id, access_token = creds
        page = 1
        while True:
            status, body, err = fetch_dashboard_page(
                user_id=user_id,
                access_token=access_token,
                start_ms=start_ms,
                end_ms=now_ms,
                page=page,
            )
            if status in (401, 403):
                return [f"cursor usage api: dashboard auth failed (HTTP {status})"]
            if status == 429:
                hint = f" retry after {err}" if err else ""
                return [f"cursor usage api: dashboard rate limited (HTTP 429){hint}"]
            if status != 200 or body is None:
                detail = err or "unknown error"
                return [f"cursor usage api: dashboard fetch failed ({detail})"]
            if not _schema_looks_valid(body, dashboard=True):
                return ["cursor usage api: dashboard response shape changed"]
            batch = _parse_dashboard_events(body)
            all_events.extend(batch)
            total = body.get("totalUsageEventsCount")
            if not batch or page * _DEFAULT_PAGE_SIZE >= int(total or 0):
                break
            page += 1

    elif mode == "admin":
        api_key = load_admin_api_key(config)
        if not api_key:
            return ["cursor usage api: no admin API key (set CURSOR_ADMIN_API_KEY)"]
        page = 1
        while True:
            status, body, err = fetch_admin_page(
                api_key=api_key,
                start_ms=start_ms,
                end_ms=now_ms,
                page=page,
            )
            if status in (401, 403):
                return [f"cursor usage api: admin auth failed (HTTP {status})"]
            if status == 429:
                hint = f" retry after {err}" if err else ""
                return [f"cursor usage api: admin rate limited (HTTP 429){hint}"]
            if status != 200 or body is None:
                detail = err or "unknown error"
                return [f"cursor usage api: admin fetch failed ({detail})"]
            if not _schema_looks_valid(body, dashboard=False):
                return ["cursor usage api: admin response shape changed"]
            batch = _parse_admin_events(body)
            all_events.extend(batch)
            if len(batch) < _DEFAULT_PAGE_SIZE:
                break
            page += 1

    added = _merge_events_into_cache(cache, all_events, source=mode)
    save_cache(vault, cache)
    st["last_poll_epoch"] = time.time()
    st["last_poll_at"] = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    st["last_mode"] = mode
    st["last_added"] = added
    if needs_backfill:
        st["backfilled_from_ms"] = floor_ms
    save_state(vault, st)
    since_note = ""
    if needs_backfill:
        since_day = datetime.fromtimestamp(floor_ms / 1000, UTC).strftime("%Y-%m-%d")
        since_note = f", backfilled since {since_day}"
    messages.append(
        f"cursor usage api: merged {added} new event(s) from {len(all_events)} fetched "
        f"({mode}{since_note})"
    )
    return messages


def _schema_looks_valid(body: Mapping[str, Any], *, dashboard: bool) -> bool:
    if dashboard:
        rows = body.get("usageEventsDisplay")
        return isinstance(rows, list)
    for key in ("usageEvents", "usageEventsDisplay", "events"):
        if isinstance(body.get(key), list):
            return True
    return False


def _bucket_from_api_row(row: Mapping[str, Any]) -> dict[str, int] | None:
    totals = row.get("totals")
    if not isinstance(totals, Mapping):
        return None
    bucket = {
        "input": int(totals.get("input") or 0),
        "cache_creation": int(totals.get("cache_creation") or 0),
        "cache_read": int(totals.get("cache_read") or 0),
        "output": int(totals.get("output") or 0),
    }
    if not any(bucket.values()):
        return None
    return bucket


def _last_activity_from_api_row(row: Mapping[str, Any]) -> str:
    """Best-effort ISO time from the newest event ``timestamp`` (ms)."""
    best_ms = 0
    events = row.get("events")
    if isinstance(events, list):
        for event in events:
            if not isinstance(event, Mapping):
                continue
            try:
                ts = int(event.get("timestamp") or 0)
            except (TypeError, ValueError):
                continue
            if ts > best_ms:
                best_ms = ts
    if best_ms > 0:
        return datetime.fromtimestamp(best_ms / 1000.0, tz=UTC).isoformat()
    return datetime.now(UTC).isoformat()


def _raw_paths_by_session_id(raw_dir: Path) -> dict[str, Path]:
    """Map frontmatter ``sessionId`` → raw path (first wins)."""
    from llmwiki._frontmatter import parse_frontmatter  # noqa: PLC0415 — avoid import cycle

    out: dict[str, Path] = {}
    if not raw_dir.is_dir():
        return out
    for path in raw_dir.glob("*.md"):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        meta, _body = parse_frontmatter(text)
        sid = str(meta.get("sessionId") or "").strip()
        if sid and sid not in out:
            out[sid] = path
    return out


def apply_api_totals_to_raw_sessions(
    vault: Path,
    *,
    dry_run: bool = False,
) -> tuple[int, int]:
    """Persist API usage as ``cursor_cli`` Tokens (ACP and interactive alike).

    Every cached ``conversationId`` with measurable totals upserts into
    ``usage/session-tokens.json`` under agent ``cursor_cli`` — the same agent
    as interactive ``cursor-agent`` (#356). Sessions already in ``raw/`` get
    ``token_totals`` patched when missing; conversations with no raw page
    (typical for headless ACP/AO workers) still count as ``metrics_only``.
    Hook JSONL still wins: those conversation ids are skipped.

    Returns ``(patched_raw_files, upserted_sessions)``.
    """
    from llmwiki._frontmatter import parse_frontmatter  # noqa: PLC0415 — avoid import cycle
    from llmwiki.migrate_session_tokens import (  # noqa: PLC0415
        _last_activity_from_meta,
        patch_raw_token_totals,
    )
    from llmwiki.session_tokens_usage import (  # noqa: PLC0415
        emit_session_tokens_sidecar,
        upsert_session_tokens,
    )

    cache = load_cache(vault)
    by_conv = cache.get("by_conversation")
    if not isinstance(by_conv, dict) or not by_conv:
        return 0, 0

    raw_dir = vault / "raw" / "sessions"
    raw_by_sid = _raw_paths_by_session_id(raw_dir)
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
        from llmwiki.cursor_usage_ledger import conversation_has_ledger_usage  # noqa: PLC0415

        if conversation_has_ledger_usage(vault, session_key):
            continue
        bucket = _bucket_from_api_row(row)
        if bucket is None:
            continue

        raw_path = raw_by_sid.get(session_key)
        in_raw = raw_path is not None
        metrics_only = not in_raw
        last_activity = _last_activity_from_api_row(row)

        if raw_path is not None:
            try:
                text = raw_path.read_text(encoding="utf-8")
            except OSError:
                text = ""
            if text:
                meta, _body = parse_frontmatter(text)
                last_activity = _last_activity_from_meta(meta, raw_path.stat().st_mtime)
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

        fp = f"cursor-usage-api:{session_key}:{json.dumps(bucket, sort_keys=True)}"
        if upsert_session_tokens(
            vault,
            session_key=session_key,
            agent="cursor_cli",
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
