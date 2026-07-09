"""Pending ingest queue (v1.0 · #148).

Tracks files that have been converted to raw/ but not yet ingested
into wiki/. The SessionStart hook adds files here after conversion;
``/wiki-sync`` processes and clears the queue.

State is stored in ``.llmwiki-queue.json`` — a simple JSON array of
file paths relative to the repo root.

Usage::

    from llmwiki.ingest_queue import enqueue, dequeue, peek, clear, queue_path

    # Hook adds after conversion
    enqueue(["raw/sessions/2026-04-16T10-30-proj-slug.md"])

    # /wiki-sync reads and processes
    pending = dequeue()   # returns list and clears queue
    for path in pending:
        ingest(path)

    # Or peek without consuming
    pending = peek()
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from llmwiki.state_store import read_state, resolve_state_file, update_state


def _load(queue_file: Optional[Path] = None) -> list[str]:
    """Load legacy ingest-pending paths from unified state (or flat JSON array)."""
    qf = resolve_state_file(queue_file)
    if not qf.exists():
        return []
    try:
        raw = json.loads(qf.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(raw, list):
        return sorted({str(p) for p in raw if isinstance(p, str)})
    if not isinstance(raw, dict):
        return []
    rows = raw.get("queue", {}).get("legacy_pending_paths", [])
    if isinstance(rows, list) and rows:
        return sorted({str(p) for p in rows if isinstance(p, str)})
    state = read_state(qf)
    rows = state.get("queue", {}).get("legacy_pending_paths", [])
    if not isinstance(rows, list):
        return []
    return sorted({str(p) for p in rows if isinstance(p, str)})


def _save(items: list[str], queue_file: Optional[Path] = None) -> None:
    """Save legacy ingest-pending paths into unified state."""
    qf = resolve_state_file(queue_file)
    deduped = sorted(set(items))
    def _mut(state: dict) -> dict:
        state.setdefault("queue", {})["legacy_pending_paths"] = deduped
        return state
    update_state(_mut, qf)


def enqueue(
    paths: list[str],
    *,
    queue_file: Optional[Path] = None,
) -> int:
    """Add paths to the pending ingest queue.

    Deduplicates automatically. Returns the new queue length.
    """
    current = _load(queue_file)
    combined = list(set(current) | set(paths))
    _save(combined, queue_file)
    return len(combined)


def dequeue(*, queue_file: Optional[Path] = None) -> list[str]:
    """Return all pending paths and clear the queue.

    This is the consume operation — after calling this, the queue
    is empty. Process the returned paths, then they're done.
    """
    items = _load(queue_file)
    _save([], resolve_state_file(queue_file))
    return items


def peek(*, queue_file: Optional[Path] = None) -> list[str]:
    """Return pending paths without consuming them."""
    return _load(queue_file)


def clear(*, queue_file: Optional[Path] = None) -> None:
    """Clear the queue without reading."""
    _save([], resolve_state_file(queue_file))


def queue_size(*, queue_file: Optional[Path] = None) -> int:
    """Return the number of pending items."""
    return len(_load(queue_file))
