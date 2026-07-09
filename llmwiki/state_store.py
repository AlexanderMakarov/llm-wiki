from __future__ import annotations

import fcntl
import json
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from llmwiki import REPO_ROOT
from llmwiki.config_schedule import load_default_vault_path


SCHEMA_VERSION = 1
DEFAULT_BOUNDED_COMPLETED = 500


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def mtime_to_iso(value: float) -> str:
    return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat(
        timespec="microseconds"
    ).replace("+00:00", "Z")


def mtime_from_state(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        try:
            if raw.endswith("Z"):
                raw = raw[:-1] + "+00:00"
            return datetime.fromisoformat(raw).timestamp()
        except ValueError:
            return None
    return None


def default_state() -> dict[str, Any]:
    return {
        "queue": {
            "items": [],
            "legacy_pending_paths": [],
        },
        "sync": {"files": {}, "meta": {}, "counters": {}},
        "synth": {
            "files": {},
            "pending": [],
            "pending_total": 0,
            "pending_updated_at": "",
            "estimate": {},
        },
        "quarantine": {"entries": []},
        "ops": {
            "last_queue_run_at": "",
            "last_lint_run_at": "",
            "last_reflect_run_at": "",
        },
        "meta": {
            "schema_version": SCHEMA_VERSION,
            "updated_at": "",
            "revision": 0,
            "compaction": {
                "max_completed": DEFAULT_BOUNDED_COMPLETED,
                "last_compacted_at": "",
            },
        },
    }


def resolve_state_file(explicit: Path | None = None) -> Path:
    """Return canonical ``<vault>/llmwiki-state.json``.

    ``explicit`` may be a vault root directory or the state file itself.
    """
    if explicit is not None:
        p = Path(explicit).expanduser().resolve()
        if p.is_dir():
            return p / "llmwiki-state.json"
        return p
    vault = load_default_vault_path()
    if vault:
        return Path(vault).expanduser().resolve() / "llmwiki-state.json"
    return REPO_ROOT / "llmwiki-state.json"


def resolve_sidecar_file(state_file: Path) -> Path:
    return state_file.parent / "llmwiki-state.js"


def _ensure_shape(raw: dict[str, Any]) -> dict[str, Any]:
    base = default_state()
    out = deepcopy(base)
    for key in ("queue", "sync", "synth", "quarantine", "ops", "meta"):
        if isinstance(raw.get(key), dict):
            out[key].update(raw[key])
    if not isinstance(out["queue"].get("items"), list):
        out["queue"]["items"] = []
    if not isinstance(out["queue"].get("legacy_pending_paths"), list):
        out["queue"]["legacy_pending_paths"] = []
    if not isinstance(out["sync"].get("files"), dict):
        out["sync"]["files"] = {}
    else:
        normalized_sync: dict[str, str] = {}
        for k, v in out["sync"]["files"].items():
            if not isinstance(k, str):
                continue
            parsed = mtime_from_state(v)
            if parsed is None:
                continue
            normalized_sync[k] = mtime_to_iso(parsed)
        out["sync"]["files"] = normalized_sync
    if not isinstance(out["sync"].get("meta"), dict):
        out["sync"]["meta"] = {}
    if not isinstance(out["sync"].get("counters"), dict):
        out["sync"]["counters"] = {}
    if not isinstance(out["synth"].get("files"), dict):
        out["synth"]["files"] = {}
    else:
        normalized_synth: dict[str, str] = {}
        for k, v in out["synth"]["files"].items():
            if not isinstance(k, str):
                continue
            parsed = mtime_from_state(v)
            if parsed is None:
                continue
            normalized_synth[k] = mtime_to_iso(parsed)
        out["synth"]["files"] = normalized_synth
    if not isinstance(out["synth"].get("pending"), list):
        out["synth"]["pending"] = []
    if not isinstance(out["synth"].get("pending_total"), int):
        out["synth"]["pending_total"] = 0
    if not isinstance(out["synth"].get("pending_updated_at"), str):
        out["synth"]["pending_updated_at"] = ""
    if not isinstance(out["synth"].get("estimate"), dict):
        out["synth"]["estimate"] = {}
    if not isinstance(out["quarantine"].get("entries"), list):
        out["quarantine"]["entries"] = []
    out["meta"]["schema_version"] = SCHEMA_VERSION
    return out


@contextmanager
def _locked(lock_path: Path) -> Iterator[None]:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("w", encoding="utf-8") as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def _atomic_write(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(payload, encoding="utf-8")
    tmp.replace(path)


def _compact_queue_items(state: dict[str, Any]) -> None:
    max_completed = (
        state.get("meta", {})
        .get("compaction", {})
        .get("max_completed", DEFAULT_BOUNDED_COMPLETED)
    )
    if not isinstance(max_completed, int) or max_completed < 1:
        max_completed = DEFAULT_BOUNDED_COMPLETED
    items = state["queue"].get("items", [])
    if not isinstance(items, list):
        state["queue"]["items"] = []
        return
    completed = [x for x in items if isinstance(x, dict) and x.get("status") == "done"]
    if len(completed) <= max_completed:
        return
    drop = len(completed) - max_completed
    kept: list[dict[str, Any]] = []
    for row in items:
        if (
            drop > 0
            and isinstance(row, dict)
            and row.get("status") == "done"
        ):
            drop -= 1
            continue
        if isinstance(row, dict):
            kept.append(row)
    state["queue"]["items"] = kept
    state["meta"]["compaction"]["last_compacted_at"] = _utc_now()


def read_state(state_file: Path | None = None) -> dict[str, Any]:
    target = resolve_state_file(state_file)
    if not target.exists():
        return default_state()
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default_state()
    if not isinstance(raw, dict):
        return default_state()
    return _ensure_shape(raw)


def write_state(state: dict[str, Any], state_file: Path | None = None) -> dict[str, Any]:
    target = resolve_state_file(state_file)
    lock_path = target.with_suffix(target.suffix + ".lock")
    with _locked(lock_path):
        normalized = _ensure_shape(state)
        normalized["meta"]["updated_at"] = _utc_now()
        revision = normalized["meta"].get("revision", 0)
        normalized["meta"]["revision"] = int(revision) + 1
        _compact_queue_items(normalized)
        payload = json.dumps(normalized, indent=2, sort_keys=True) + "\n"
        _atomic_write(target, payload)
        sidecar = (
            "window.LLMWIKI_STATE_SNAPSHOT = "
            + json.dumps(normalized, separators=(",", ":"))
            + ";\n"
        )
        _atomic_write(resolve_sidecar_file(target), sidecar)
        return normalized


def update_state(mutator, state_file: Path | None = None) -> dict[str, Any]:
    target = resolve_state_file(state_file)
    lock_path = target.with_suffix(target.suffix + ".lock")
    with _locked(lock_path):
        current = read_state(target)
        updated = mutator(deepcopy(current)) or current
        normalized = _ensure_shape(updated)
        normalized["meta"]["updated_at"] = _utc_now()
        revision = normalized["meta"].get("revision", 0)
        normalized["meta"]["revision"] = int(revision) + 1
        _compact_queue_items(normalized)
        payload = json.dumps(normalized, indent=2, sort_keys=True) + "\n"
        _atomic_write(target, payload)
        sidecar = (
            "window.LLMWIKI_STATE_SNAPSHOT = "
            + json.dumps(normalized, separators=(",", ":"))
            + ";\n"
        )
        _atomic_write(resolve_sidecar_file(target), sidecar)
        return normalized
