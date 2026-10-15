"""Vault-wide session token totals in a single ``usage/session-tokens.json`` (#325)."""
from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from llmwiki.usage import usage_dir

SESSION_TOKENS_NAME = "session-tokens.json"
SIDECAR_GLOBAL = "LLMWIKI_SESSION_TOKENS"
_BUCKET_KEYS = ("input", "cache_creation", "cache_read", "output")


def _iso_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _empty_buckets() -> dict[str, int]:
    return {k: 0 for k in _BUCKET_KEYS}


def _bucket_sum(buckets: Mapping[str, Any]) -> int:
    return sum(int(buckets.get(k) or 0) for k in _BUCKET_KEYS)


def _add_buckets(dst: dict[str, int], src: Mapping[str, Any]) -> None:
    for key in _BUCKET_KEYS:
        dst[key] = int(dst.get(key) or 0) + int(src.get(key) or 0)


def _sub_buckets(dst: dict[str, int], src: Mapping[str, Any]) -> None:
    for key in _BUCKET_KEYS:
        dst[key] = int(dst.get(key) or 0) - int(src.get(key) or 0)


def _normalize_buckets(raw: Mapping[str, Any] | None) -> dict[str, int]:
    out = _empty_buckets()
    if not isinstance(raw, Mapping):
        return out
    for key in _BUCKET_KEYS:
        out[key] = int(raw.get(key) or 0)
    return out


def _is_measured(totals: Mapping[str, Any]) -> bool:
    return any(int(totals.get(k) or 0) != 0 for k in _BUCKET_KEYS)


def usage_path(vault: Path) -> Path:
    return usage_dir(vault) / SESSION_TOKENS_NAME


def _empty_document() -> dict[str, Any]:
    totals = _empty_buckets()
    totals["sum"] = 0
    return {
        "totals": totals,
        "by_agent": {},
        "days": {},
        "sessions": {},
        "attribution": {"day_rule": "last_activity_utc", "timezone": "UTC"},
        "updated_at": "",
    }


def _ensure_shape(raw: dict[str, Any]) -> dict[str, Any]:
    out = _empty_document()
    if isinstance(raw.get("totals"), dict):
        out["totals"].update(_normalize_buckets(raw["totals"]))
        out["totals"]["sum"] = _bucket_sum(out["totals"])
    if isinstance(raw.get("by_agent"), dict):
        out["by_agent"] = raw["by_agent"]
    if isinstance(raw.get("days"), dict):
        out["days"] = raw["days"]
    if isinstance(raw.get("sessions"), dict):
        out["sessions"] = raw["sessions"]
    if isinstance(raw.get("attribution"), dict):
        out["attribution"].update(raw["attribution"])
    if isinstance(raw.get("updated_at"), str):
        out["updated_at"] = raw["updated_at"]
    return out


def day_from_last_activity(iso_or_datetime: str | datetime) -> str:
    """UTC calendar day for last-activity attribution."""
    if isinstance(iso_or_datetime, datetime):
        ts = iso_or_datetime
    else:
        text = iso_or_datetime.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        ts = datetime.fromisoformat(text)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    else:
        ts = ts.astimezone(UTC)
    return ts.date().isoformat()


def rebuild_aggregates_from_sessions(data: dict[str, Any]) -> None:
    """Recompute ``totals``, ``by_agent``, and ``days`` from the session ledger."""
    sessions = data.get("sessions")
    if not isinstance(sessions, dict):
        sessions = {}
        data["sessions"] = sessions

    totals = _empty_buckets()
    totals["sum"] = 0
    by_agent: dict[str, Any] = {}
    days: dict[str, Any] = {}

    for stub in sessions.values():
        if not isinstance(stub, dict):
            continue
        agent = stub.get("agent")
        if not isinstance(agent, str) or not agent:
            continue
        day = stub.get("day")
        if not isinstance(day, str) or not day:
            continue
        bucket = _normalize_buckets(stub.get("totals"))

        _add_buckets(totals, bucket)
        agent_row = by_agent.setdefault(
            agent,
            {"measured": 0, "known": 0, "totals": _empty_buckets()},
        )
        agent_row["known"] = int(agent_row.get("known") or 0) + 1
        if _is_measured(bucket):
            agent_row["measured"] = int(agent_row.get("measured") or 0) + 1
        _add_buckets(agent_row["totals"], bucket)

        day_row = days.setdefault(day, {})
        agent_day = day_row.setdefault(agent, _empty_buckets())
        _add_buckets(agent_day, bucket)
        agent_day["sum"] = _bucket_sum(agent_day)

    totals["sum"] = _bucket_sum(totals)
    for agent_row in by_agent.values():
        if isinstance(agent_row.get("totals"), dict):
            agent_row["totals"]["sum"] = _bucket_sum(agent_row["totals"])

    data["totals"] = totals
    data["by_agent"] = by_agent
    data["days"] = days


def load_session_tokens(vault: Path) -> dict[str, Any]:
    path = usage_path(vault)
    if not path.is_file():
        return _empty_document()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _empty_document()
    if not isinstance(raw, dict):
        return _empty_document()
    data = _ensure_shape(raw)
    rebuild_aggregates_from_sessions(data)
    return data


def save_session_tokens(vault: Path, data: dict[str, Any]) -> None:
    """Persist atomically (temp file + ``os.replace``)."""
    d = usage_dir(vault)
    d.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    fd, tmp = tempfile.mkstemp(dir=str(d), prefix=".session-tokens-", suffix=".tmp")
    target = d / SESSION_TOKENS_NAME
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
        os.replace(tmp, target)
    finally:
        try:
            if os.path.exists(tmp):
                os.unlink(tmp)
        except OSError:
            pass


def _subtract_session_contribution(data: dict[str, Any], stub: Mapping[str, Any]) -> None:
    agent = stub.get("agent")
    day = stub.get("day")
    if not isinstance(agent, str) or not isinstance(day, str):
        return
    totals = _normalize_buckets(stub.get("totals"))
    _sub_buckets(data["totals"], totals)
    data["totals"]["sum"] = _bucket_sum(data["totals"])

    days = data["days"]
    if isinstance(days.get(day), dict) and isinstance(days[day].get(agent), dict):
        _sub_buckets(days[day][agent], totals)
        days[day][agent]["sum"] = _bucket_sum(days[day][agent])


def upsert_session_tokens(
    vault: Path,
    *,
    session_key: str,
    agent: str,
    totals: Mapping[str, int],
    fingerprint: str,
    last_activity: str,
    in_raw: bool = False,
    metrics_only: bool = False,
) -> bool:
    """Insert or update one session stub. Returns ``False`` when fingerprint unchanged."""
    data = load_session_tokens(vault)
    sessions = data["sessions"]
    if not isinstance(sessions, dict):
        sessions = {}
        data["sessions"] = sessions

    existing = sessions.get(session_key)
    if isinstance(existing, dict) and existing.get("fingerprint") == fingerprint:
        return False

    if isinstance(existing, dict):
        _subtract_session_contribution(data, existing)

    day = day_from_last_activity(last_activity)
    bucket = _normalize_buckets(totals)
    sessions[session_key] = {
        "agent": agent,
        "day": day,
        "totals": bucket,
        "fingerprint": fingerprint,
        "last_activity": last_activity,
        "in_raw": bool(in_raw),
        "metrics_only": bool(metrics_only),
    }

    rebuild_aggregates_from_sessions(data)
    data["updated_at"] = _iso_now()
    save_session_tokens(vault, data)
    return True


def emit_session_tokens_sidecar(vault: Path, site_dir: Path) -> None:
    """Write ``site/session-tokens.js`` from the vault usage snapshot."""
    if not site_dir.is_dir():
        return
    data = load_session_tokens(vault)
    payload = json.dumps(data, separators=(",", ":"))
    sidecar = f"window.{SIDECAR_GLOBAL} = {payload};\n"
    out = site_dir / "session-tokens.js"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(sidecar, encoding="utf-8")
