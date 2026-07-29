from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from llmwiki.add_doc import add_sources
from llmwiki.build import build_site
from llmwiki.config_schedule import _load_sessions_config
from llmwiki.convert import convert_all
from llmwiki.state_store import read_state, resolve_state_file, update_state
from llmwiki.synth.pipeline import resolve_backend, synthesize_new_sessions


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def enqueue_task(task_type: str, payload: dict[str, Any], state_file: Path | None = None) -> dict[str, Any]:
    if task_type not in TASK_HANDLERS:
        known = ", ".join(sorted(TASK_HANDLERS))
        raise ValueError(f"unknown task_type: {task_type} (known: {known})")
    task = {
        "id": f"{task_type}-{int(datetime.now(UTC).timestamp() * 1000)}",
        "task_type": task_type,
        "payload": payload,
        "status": "pending",
        "attempts": 0,
        "created_at": _now(),
        "updated_at": _now(),
        "last_error": "",
    }

    def _mut(state: dict[str, Any]) -> dict[str, Any]:
        state.setdefault("queue", {}).setdefault("items", []).append(task)
        return state

    update_state(_mut, resolve_state_file(state_file))
    return task


def queue_status(state_file: Path | None = None) -> dict[str, Any]:
    state = read_state(resolve_state_file(state_file))
    items = state.get("queue", {}).get("items", [])
    counts: dict[str, int] = {"pending": 0, "running": 0, "done": 0, "error": 0}
    oldest_pending = ""
    for row in items:
        if not isinstance(row, dict):
            continue
        status = str(row.get("status", "pending"))
        counts[status] = counts.get(status, 0) + 1
        if status == "pending":
            created = str(row.get("created_at", ""))
            if created and (not oldest_pending or created < oldest_pending):
                oldest_pending = created
    return {"counts": counts, "oldest_pending": oldest_pending, "total": len(items)}


def _handle_session_sync(payload: dict[str, Any], vault: Path) -> str:
    rc = convert_all(
        out_dir=vault / "raw" / "sessions",
        state_file=vault / "llmwiki-state.json",
    )
    if rc != 0:
        raise RuntimeError(f"sync failed with exit code {rc}")
    return "session sync complete"


def _handle_synthesize(payload: dict[str, Any], vault: Path) -> str:
    """Synthesize wiki source pages.

    Payload is optional and makes a queued task self-contained:
    ``paths`` (list of raw file paths) restricts the run to those sources,
    ``force`` re-synthesizes them. Without a payload the task drains the
    whole backlog.
    """

    backend = resolve_backend(_load_sessions_config())
    if not backend.is_available():
        raise RuntimeError(f"backend {backend.name} is not available")
    raw_paths = payload.get("paths") or []
    only_paths = {str(p) for p in raw_paths} if isinstance(raw_paths, list) and raw_paths else None
    summary = synthesize_new_sessions(
        backend=backend,
        raw_dir=vault / "raw" / "sessions",
        wiki_sources_dir=vault / "wiki" / "sources",
        state_file=vault / "llmwiki-state.json",
        docs_dir=vault / "raw" / "docs",
        only_paths=only_paths,
        force=bool(payload.get("force", False)),
    )
    if summary["errors"]:
        raise RuntimeError("; ".join(summary["errors"][:2]))
    return f"synthesized {summary['synthesized']} sources"


def _handle_build(payload: dict[str, Any], vault: Path) -> str:
    rc = build_site(
        out_dir=vault / "site",
        raw_sessions=vault / "raw" / "sessions",
        raw_dir=vault / "raw",
        wiki_dir=vault / "wiki",
    )
    if rc != 0:
        raise RuntimeError(f"build failed with exit code {rc}")
    return "site build complete"


def _handle_add_doc(payload: dict[str, Any], vault: Path) -> str:
    source = str(payload.get("source", ""))
    if not source:
        raise RuntimeError("missing add_doc payload.source")
    result = add_sources([source], vault / "raw" / "docs", dry_run=False)
    if result.get("errors"):
        raise RuntimeError(str(result["errors"][0]))
    return f"added {source}"


# Single source of truth for the task types the queue supports: `enqueue_task`
# validates against it and `_run_one` dispatches through it, so a producer can
# never enqueue work the runner cannot process (#23).
TASK_HANDLERS: dict[str, Callable[[dict[str, Any], Path], str]] = {
    "add_doc": _handle_add_doc,
    "session_sync": _handle_session_sync,
    "synthesize": _handle_synthesize,
    "build": _handle_build,
}


def _run_one(task: dict[str, Any], vault: Path) -> str:
    t = str(task.get("task_type") or "")
    payload = task.get("payload", {}) if isinstance(task.get("payload"), dict) else {}
    handler = TASK_HANDLERS.get(t)
    if handler is None:
        known = ", ".join(sorted(TASK_HANDLERS))
        raise RuntimeError(f"unknown task_type: {t} (known: {known})")
    return handler(payload, vault)


def run_queue(limit: int, vault: Path, state_file: Path | None = None) -> dict[str, Any]:
    target = resolve_state_file(state_file)
    processed = 0
    errors: list[str] = []

    for _ in range(max(limit, 0)):
        current = read_state(target)
        items = current.get("queue", {}).get("items", [])
        idx = -1
        for i, row in enumerate(items):
            if isinstance(row, dict) and row.get("status") == "pending":
                idx = i
                break
        if idx < 0:
            break
        task = items[idx]

        def _mark_running(state: dict[str, Any], idx=idx) -> dict[str, Any]:
            qitems = state.setdefault("queue", {}).setdefault("items", [])
            qitems[idx]["status"] = "running"
            qitems[idx]["updated_at"] = _now()
            qitems[idx]["attempts"] = int(qitems[idx].get("attempts", 0)) + 1
            return state

        update_state(_mark_running, target)
        try:
            result = _run_one(task, vault)
            def _mark_done(state: dict[str, Any], idx=idx, result=result) -> dict[str, Any]:
                qitems = state.setdefault("queue", {}).setdefault("items", [])
                qitems[idx]["status"] = "done"
                qitems[idx]["result"] = result
                qitems[idx]["updated_at"] = _now()
                return state

            update_state(_mark_done, target)
            processed += 1
        except Exception as exc:  # pragma: no cover - defensive for CLI flow
            msg = str(exc)
            errors.append(msg)
            def _mark_error(state: dict[str, Any], idx=idx, msg=msg) -> dict[str, Any]:
                qitems = state.setdefault("queue", {}).setdefault("items", [])
                qitems[idx]["status"] = "error"
                qitems[idx]["last_error"] = msg
                qitems[idx]["updated_at"] = _now()
                return state

            update_state(_mark_error, target)

    def _mark_ops(state: dict[str, Any]) -> dict[str, Any]:
        state.setdefault("ops", {})["last_queue_run_at"] = _now()
        return state
    update_state(_mark_ops, target)
    return {"processed": processed, "errors": errors}
