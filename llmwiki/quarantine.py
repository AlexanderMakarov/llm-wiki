"""Convert-error quarantine (G-14 · #300).

When ``llmwiki sync`` hits a converter exception we used to just print
``error: <file>: <reason>`` to stderr and move on — one bad source was
enough to silently drop a session from the corpus with no audit trail.

This module introduces a persistent quarantine file
(``.llmwiki-quarantine.json``) so:

1. Every failing source gets recorded once with the error, adapter, and
   both first/last-seen timestamps.
2. ``llmwiki quarantine list`` surfaces the queue so operators can see
   what didn't sync and why.
3. ``llmwiki quarantine clear --all|<path>`` wipes entries after the
   underlying bug is fixed so the next sync retries them.
4. ``llmwiki quarantine retry`` prints a plan for targeted re-sync.
5. ``llmwiki sync --status`` (G-03 · #289) reads the same file.

Stdlib-only and schema-versioned (``"version": 1``) so future changes
stay backwards-compatible.  File format is deterministic — entries are
sorted by ``adapter, source`` so diffs stay small and git-friendly if a
user ever chooses to commit the file (the repo ``.gitignore`` keeps it
local by default).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

from llmwiki.state_store import read_state, resolve_state_file, update_state

DEFAULT_QUARANTINE_FILE = resolve_state_file()
SCHEMA_VERSION = 1


@dataclass
class QuarantineEntry:
    """One record in ``.llmwiki-quarantine.json``.

    Equality is by ``(adapter, source)`` — the pair uniquely identifies
    a failing source regardless of when it failed.
    """

    adapter: str
    source: str
    error: str
    first_seen: str  # ISO-8601 UTC
    last_seen: str   # ISO-8601 UTC
    attempts: int = 1
    extra: dict[str, Any] = field(default_factory=dict)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, QuarantineEntry):
            return NotImplemented
        return (self.adapter, self.source) == (other.adapter, other.source)

    def __hash__(self) -> int:
        return hash((self.adapter, self.source))


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load(path: Optional[Path] = None) -> list[QuarantineEntry]:
    """Load the quarantine file. Returns ``[]`` on missing/corrupt file.

    Never raises — the caller treats the quarantine as best-effort UI.
    Malformed entries are skipped individually so one bad row doesn't
    blow up the whole file.

    #py-m7 (#593): default-arg ``DEFAULT_QUARANTINE_FILE`` was captured
    at module-load time, breaking ``monkeypatch.setattr(quarantine,
    "DEFAULT_QUARANTINE_FILE", tmp)`` in tests because the parameter
    default still pointed at the original constant. Resolve at call
    time instead.
    """
    target = path or DEFAULT_QUARANTINE_FILE
    raw_entries: list[Any] = []
    if target.exists():
        try:
            raw = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raw = None
        if isinstance(raw, dict):
            if "queue" in raw or "sync" in raw:
                raw_entries = raw.get("quarantine", {}).get("entries", [])
            elif "entries" in raw:
                raw_entries = raw.get("entries", [])
    if not raw_entries:
        data = read_state(target).get("quarantine", {})
        raw_entries = data.get("entries", []) if isinstance(data, dict) else []
    if not isinstance(raw_entries, list):
        return []
    out: list[QuarantineEntry] = []
    for row in raw_entries:
        if not isinstance(row, dict):
            continue
        try:
            out.append(
                QuarantineEntry(
                    adapter=str(row["adapter"]),
                    source=str(row["source"]),
                    error=str(row.get("error", "")),
                    first_seen=str(row.get("first_seen", _now_utc_iso())),
                    last_seen=str(row.get("last_seen", _now_utc_iso())),
                    attempts=int(row.get("attempts", 1)),
                    extra=row.get("extra", {}) or {},
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return out


def save(
    entries: Iterable[QuarantineEntry],
    path: Optional[Path] = None,
) -> Path:
    """Write the quarantine file. Sorts deterministically for stable diffs.

    #py-m7 (#593): default resolved at call time so tests that
    monkeypatch DEFAULT_QUARANTINE_FILE see the override.
    """
    target = path or DEFAULT_QUARANTINE_FILE
    items = sorted(set(entries), key=lambda e: (e.adapter, e.source))
    rows = [asdict(e) for e in items]
    def _mut(state: dict) -> dict:
        q = state.setdefault("quarantine", {})
        q["version"] = SCHEMA_VERSION
        q["updated"] = _now_utc_iso()
        q["entries"] = rows
        return state
    update_state(_mut, target)
    return target


def add_entry(
    adapter: str,
    source: str,
    error: str,
    *,
    path: Optional[Path] = None,
    extra: Optional[dict[str, Any]] = None,
) -> QuarantineEntry:
    """Add or refresh a quarantine entry.

    #py-m7 (#593): default resolved at call time.

    If ``(adapter, source)`` already exists the call bumps ``attempts``,
    updates ``last_seen`` + ``error``, and merges ``extra`` — callers
    can retry a failing source and each failure is counted without
    creating duplicate rows.
    """
    if not adapter or not source:
        raise ValueError("adapter and source are required")
    now = _now_utc_iso()
    entries = load(path)
    by_key = {(e.adapter, e.source): e for e in entries}
    key = (adapter, source)
    if key in by_key:
        e = by_key[key]
        e.attempts += 1
        e.last_seen = now
        e.error = error or e.error
        if extra:
            e.extra = {**(e.extra or {}), **extra}
        updated = e
    else:
        updated = QuarantineEntry(
            adapter=adapter,
            source=source,
            error=error,
            first_seen=now,
            last_seen=now,
            attempts=1,
            extra=dict(extra or {}),
        )
        entries.append(updated)
    save(entries, path)
    return updated


def clear_entry(
    source: str,
    *,
    adapter: Optional[str] = None,
    path: Optional[Path] = None,
) -> int:
    """Remove matching entries.  Returns count removed.

    If ``adapter`` is ``None`` every entry whose ``source`` matches is
    removed (useful when the operator passes an absolute path without
    remembering which adapter produced it).

    #py-m7 (#593): default resolved at call time.
    """
    target = path or DEFAULT_QUARANTINE_FILE
    entries = load(target)
    keep: list[QuarantineEntry] = []
    removed = 0
    for e in entries:
        match_adapter = adapter is None or e.adapter == adapter
        if match_adapter and e.source == source:
            removed += 1
            continue
        keep.append(e)
    if removed:
        save(keep, target)
    return removed


def clear_all(path: Optional[Path] = None) -> int:
    """Drop every entry. Returns count removed."""
    target = path or DEFAULT_QUARANTINE_FILE
    entries = load(target)
    n = len(entries)
    if n:
        save([], target)
    return n


def list_entries(
    path: Optional[Path] = None,
    *,
    adapter: Optional[str] = None,
) -> list[QuarantineEntry]:
    """Return entries filtered by adapter (stable ordering)."""
    out = load(path or DEFAULT_QUARANTINE_FILE)
    if adapter:
        out = [e for e in out if e.adapter == adapter]
    return sorted(out, key=lambda e: (e.adapter, e.last_seen), reverse=False)


def format_table(entries: list[QuarantineEntry]) -> str:
    """Human-readable table — used by the CLI + ``sync --status``."""
    if not entries:
        return "No quarantined sources."
    widths = {
        "adapter": max(8, max(len(e.adapter) for e in entries)),
        "error": 48,
        "source": max(20, max(len(Path(e.source).name) for e in entries)),
    }
    header = (
        f"  {'adapter':<{widths['adapter']}}  "
        f"{'source':<{widths['source']}}  "
        f"{'attempts':>8}  {'last_seen':<20}  error"
    )
    sep = "  " + "-" * (widths["adapter"] + widths["source"] + 8 + 20 + 48 + 10)
    rows = [header, sep]
    for e in entries:
        err = e.error
        if len(err) > widths["error"]:
            err = err[: widths["error"] - 3] + "..."
        rows.append(
            f"  {e.adapter:<{widths['adapter']}}  "
            f"{Path(e.source).name:<{widths['source']}}  "
            f"{e.attempts:>8}  {e.last_seen:<20}  {err}"
        )
    return "\n".join(rows)


def count_by_adapter(
    path: Optional[Path] = None,
) -> dict[str, int]:
    """Aggregate helper for ``llmwiki sync --status``."""
    out: dict[str, int] = {}
    for e in load(path or DEFAULT_QUARANTINE_FILE):
        out[e.adapter] = out.get(e.adapter, 0) + 1
    return out
