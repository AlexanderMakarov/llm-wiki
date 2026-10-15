"""``llmwiki migrate session-tokens`` — backfill usage/session-tokens.json (#325).

Walks existing ``raw/sessions/*.md`` frontmatter and capable adapter origins
so Analytics Tokens and coverage work for sessions sync would fingerprint-skip.
"""
from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from llmwiki._frontmatter import parse_frontmatter
from llmwiki.adapters import REGISTRY
from llmwiki.convert import (
    _session_key_from_records,
    compute_token_totals,
    filter_records,
    first_record_time,
    latest_record_time,
)
from llmwiki.session_tokens_usage import (
    emit_session_tokens_sidecar,
    upsert_session_tokens,
)
from llmwiki.state_store import mtime_to_iso
from llmwiki.viz_tokens import parse_token_totals

_TOKEN_TOTALS_LINE = re.compile(r"^token_totals:\s*.*$", re.MULTILINE)
_TAG_ADAPTER_RE = re.compile(r"^\s*\[([^\]]*)\]\s*$")
_BUCKET_KEYS = ("input", "cache_creation", "cache_read", "output")


def _adapter_name_from_meta(meta: dict[str, Any]) -> str:
    """Map frontmatter ``tags`` to a registry adapter name when possible."""
    raw = meta.get("tags")
    tags: list[str] = []
    if isinstance(raw, list):
        tags = [str(t).strip().strip("'\"") for t in raw]
    elif isinstance(raw, str):
        m = _TAG_ADAPTER_RE.match(raw.strip())
        if m:
            tags = [p.strip().strip("'\"") for p in m.group(1).split(",") if p.strip()]
    for tag in tags:
        candidate = tag.replace("-", "_")
        if candidate in REGISTRY:
            return candidate
    return "claude_code"


def patch_raw_token_totals(text: str, totals: dict[str, int]) -> str:
    """Replace or insert ``token_totals`` in session frontmatter."""
    line = f"token_totals: {json.dumps(totals, sort_keys=False)}"
    if _TOKEN_TOTALS_LINE.search(text):
        return _TOKEN_TOTALS_LINE.sub(line, text, count=1)
    lines = text.splitlines(keepends=True)
    for i, row in enumerate(lines):
        if row.startswith("tool_counts:"):
            lines.insert(i + 1, line + "\n")
            return "".join(lines)
    for i, row in enumerate(lines):
        if row.startswith("---") and i > 0:
            lines.insert(i, line + "\n")
            return "".join(lines)
    return text


def _last_activity_from_meta(meta: dict[str, Any], fallback_mtime: float) -> str:
    for key in ("ended", "started", "date"):
        val = meta.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return datetime.fromtimestamp(fallback_mtime, tz=UTC).isoformat()


def _totals_nonempty(totals: dict[str, int]) -> bool:
    return any(int(totals.get(k) or 0) != 0 for k in _BUCKET_KEYS)


def _upsert_from_raw_file(
    vault: Path,
    raw_path: Path,
    *,
    dry_run: bool,
    report: dict[str, Any],
) -> None:
    text = raw_path.read_text(encoding="utf-8")
    meta, _body = parse_frontmatter(text)
    totals = parse_token_totals(meta)
    session_key = str(meta.get("sessionId") or raw_path.stem).strip()
    agent = _adapter_name_from_meta(meta)
    mtime = raw_path.stat().st_mtime
    last_activity = _last_activity_from_meta(meta, mtime)
    if dry_run:
        report["raw_upserts"] = int(report.get("raw_upserts") or 0) + 1
        return
    if upsert_session_tokens(
        vault,
        session_key=session_key,
        agent=agent,
        totals=totals,
        fingerprint=mtime_to_iso(mtime),
        last_activity=last_activity,
        in_raw=True,
        metrics_only=False,
    ):
        report["raw_upserts"] = int(report.get("raw_upserts") or 0) + 1


def _find_raw_by_session_id(sessions_dir: Path, session_id: str) -> Path | None:
    if not session_id or not sessions_dir.is_dir():
        return None
    needle = f"sessionId: {session_id}"
    for path in sorted(sessions_dir.glob("*.md")):
        try:
            head = path.read_text(encoding="utf-8")[:4000]
        except OSError:
            continue
        if needle in head:
            return path
    return None


def _backfill_capable_adapter(
    vault: Path,
    sessions_dir: Path,
    adapter_name: str,
    *,
    config: dict[str, Any],
    dry_run: bool,
    report: dict[str, Any],
) -> None:
    cls = REGISTRY.get(adapter_name)
    if cls is None:
        return
    adapter = cls(config)
    discover = getattr(adapter, "discover_sessions", None)
    if not callable(discover):
        return
    drop_types = config.get("filters", {}).get("drop_record_types", [])
    for path in discover():
        path = Path(path)
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        try:
            records = adapter.load_records(path)
        except OSError:
            report["errors"] = int(report.get("errors") or 0) + 1
            continue
        records = adapter.normalize_records(records)
        records = filter_records(records, drop_types)
        if not records:
            continue
        totals = compute_token_totals(records)
        session_key = _session_key_from_records(records, path)
        raw_path = _find_raw_by_session_id(sessions_dir, session_key)
        if raw_path is not None and totals != {k: 0 for k in _BUCKET_KEYS}:
            text = raw_path.read_text(encoding="utf-8")
            meta, _ = parse_frontmatter(text)
            existing = parse_token_totals(meta)
            if existing != totals:
                report["raw_patched"] = int(report.get("raw_patched") or 0) + 1
                if not dry_run:
                    raw_path.write_text(patch_raw_token_totals(text, totals), encoding="utf-8")
        ended = latest_record_time(records) or first_record_time(records)
        last_activity = (
            ended.isoformat()
            if ended is not None
            else datetime.fromtimestamp(mtime, tz=UTC).isoformat()
        )
        in_raw = raw_path is not None
        metrics_only = not in_raw and _totals_nonempty(totals)
        if dry_run:
            report["origin_upserts"] = int(report.get("origin_upserts") or 0) + 1
            continue
        if upsert_session_tokens(
            vault,
            session_key=session_key,
            agent=adapter_name,
            totals=totals,
            fingerprint=mtime_to_iso(mtime),
            last_activity=last_activity,
            in_raw=in_raw,
            metrics_only=metrics_only,
        ):
            report["origin_upserts"] = int(report.get("origin_upserts") or 0) + 1


def run_migration(
    *,
    vault: Path,
    dry_run: bool = False,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Backfill ``usage/session-tokens.json`` and optional raw ``token_totals``."""
    vault = Path(vault)
    sessions_dir = vault / "raw" / "sessions"
    cfg = config if isinstance(config, dict) else {}
    report: dict[str, Any] = {
        "vault": str(vault),
        "dry_run": dry_run,
        "raw_upserts": 0,
        "raw_patched": 0,
        "origin_upserts": 0,
        "errors": 0,
    }
    if sessions_dir.is_dir():
        for raw_path in sorted(sessions_dir.glob("*.md")):
            try:
                _upsert_from_raw_file(vault, raw_path, dry_run=dry_run, report=report)
            except OSError:
                report["errors"] = int(report.get("errors") or 0) + 1

    for adapter_name in ("cursor_cli", "claude_code", "codex_cli"):
        if adapter_name in REGISTRY:
            _backfill_capable_adapter(
                vault,
                sessions_dir,
                adapter_name,
                config=cfg,
                dry_run=dry_run,
                report=report,
            )

    site_dir = vault / "site"
    changed = int(report.get("raw_upserts") or 0) + int(report.get("origin_upserts") or 0)
    if not dry_run and site_dir.is_dir() and changed > 0:
        emit_session_tokens_sidecar(vault, site_dir)
    return report


def print_report(report: dict[str, Any]) -> None:
    mode = "dry-run" if report.get("dry_run") else "apply"
    print(f"session-tokens migrate ({mode}) — vault {report.get('vault')}")
    print(f"  raw frontmatter upserts: {report.get('raw_upserts', 0)}")
    print(f"  raw token_totals patched: {report.get('raw_patched', 0)}")
    print(f"  origin re-read upserts: {report.get('origin_upserts', 0)}")
    if report.get("errors"):
        print(f"  errors: {report['errors']}")
