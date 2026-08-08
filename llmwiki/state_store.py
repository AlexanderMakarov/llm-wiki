from __future__ import annotations

import fcntl
import json
from collections.abc import Iterator
from contextlib import contextmanager
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from llmwiki import REPO_ROOT

SCHEMA_VERSION = 1
DEFAULT_BOUNDED_COMPLETED = 500
_ACTIVE_STATE_FILE: Path | None = None


def _utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def mtime_to_iso(value: float) -> str:
    return datetime.fromtimestamp(float(value), tz=UTC).isoformat(
        timespec="microseconds"
    ).replace("+00:00", "Z")


def mtime_from_state(value: Any) -> float | None:
    """Parse a state mtime.

    On-disk unified state stores ISO-8601 strings only. In-memory convert
    helpers and one-shot legacy migrations may still pass numeric mtimes;
    accept those so callers don't silently drop keys before ``mtime_to_iso``.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
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
            # ``pipeline`` is intentionally absent here. Pre-v1.5 vaults and a
            # fresh default lack it; ``synth_pipeline_shape_ok`` detects that so
            # ``build`` can one-shot backfill (#70). Do not invent an empty
            # pipeline in defaults — that would skip the backfill forever.
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


def synth_pipeline_shape_ok(synth: Any) -> bool:
    """Return True when ``synth.pipeline`` matches the Home State widget shape.

    v1.5.0 introduced ``synth.pipeline`` (``stages`` + ``rows``). Older state
    files omit it; ``build`` uses this check to decide whether a one-shot
    ``refresh_synth_pending`` is needed (#70). A present but empty ``rows``
    list is valid (genuinely empty vault after sync/estimate).
    """
    if not isinstance(synth, dict):
        return False
    pipeline = synth.get("pipeline")
    if not isinstance(pipeline, dict):
        return False
    return isinstance(pipeline.get("rows"), list)


def pipeline_rows_missing_on_disk(synth: Any) -> bool:
    """Return True when persisted pipeline rows need an #81 ``on_disk`` backfill.

    Home reads ``pipeline.rows[*].on_disk`` (not ``estimate.source_pages_*``).
    Pre-#81 snapshots have valid shape but omit the key — JS coerces missing to
    0. Also treat empty ``rows`` as stale when ``estimate.source_pages_on_disk``
    is already > 0 (disk has pages the snapshot never attributed).
    """
    if not isinstance(synth, dict):
        return False
    pipeline = synth.get("pipeline")
    if not isinstance(pipeline, dict):
        return False
    rows = pipeline.get("rows")
    if not isinstance(rows, list):
        return False
    if not rows:
        estimate = synth.get("estimate")
        if not isinstance(estimate, dict):
            return False
        try:
            pages = int(estimate.get("source_pages_on_disk") or 0)
        except (TypeError, ValueError):
            pages = 0
        return pages > 0
    for row in rows:
        if isinstance(row, dict) and "on_disk" not in row:
            return True
    return False


class IncompatibleStateError(RuntimeError):
    """A sync cannot safely reconcile with the on-disk state file.

    Raised when the state file is present but unreadable, or was written by
    a newer schema than this engine understands. Reading it as an empty
    dict would silently reconvert the whole corpus and duplicate ``raw/``
    (#29), so we hard-stop instead and require an explicit ``--force-resync``.
    """


_FORCE_RESYNC_HINT = (
    "Upgrade llmwiki, or pass --force-resync to reconvert from scratch "
    "(this re-slugs and may duplicate an already-populated raw/)."
)


def state_incompatibility_reason(raw_text: str | None) -> str | None:
    """Decide whether an on-disk state blob is unsafe to sync against.

    ``raw_text`` is the verbatim contents of ``llmwiki-state.json``, or
    ``None`` when the file does not exist. Return a short human-readable
    reason string when a sync must NOT proceed (it would otherwise treat
    the state as empty and full-reconvert), or ``None`` when the state is
    a safe, understood, same-or-older-schema file.

    The three cases that must block are:
      * present but not valid JSON (half-written / corrupt);
      * valid JSON but not a state object (e.g. a bare list);
      * ``meta.schema_version`` greater than this engine's ``SCHEMA_VERSION``.

    An empty / whitespace-only file is treated as compatible: it carries no
    data to lose (usually a ``touch``ed artifact or an interrupted first
    write), so blocking on it would only annoy a genuine first sync.
    """
    if raw_text is None:
        return None
    if not raw_text.strip():
        return None
    try:
        parsed = json.loads(raw_text)
    except ValueError:
        return "state file is present but unreadable (corrupt JSON)"
    if not isinstance(parsed, dict):
        return "state file is present but is not a state object"
    meta = parsed.get("meta")
    version = meta.get("schema_version") if isinstance(meta, dict) else None
    if version is not None and not isinstance(version, bool):
        # Fail closed: a numeric version above ours, or a present-but-non-numeric
        # version (a foreign/unknown format), both mean "don't reconvert blindly".
        if isinstance(version, (int, float)):
            if version > SCHEMA_VERSION:
                return (
                    f"state file was written by a newer llmwiki "
                    f"(schema_version={version} > {SCHEMA_VERSION})"
                )
        else:
            return (
                f"state file has an unrecognized schema_version "
                f"({version!r}); assuming a newer or foreign format"
            )
    return None


def check_sync_state_compatible(
    state_file: Path | None = None, *, force_resync: bool = False
) -> None:
    """Hard-stop a sync when the vault's state file is unsafe to reconcile.

    Border check for ``cmd_sync``: raises :class:`IncompatibleStateError`
    unless ``force_resync`` is set. A missing file is always fine — that is
    a genuine first sync.
    """
    if force_resync:
        return
    target = resolve_state_file(state_file)
    raw_text: str | None = None
    if target.exists():
        try:
            raw_text = target.read_text(encoding="utf-8")
        except OSError as exc:
            raise IncompatibleStateError(
                f"{target}: cannot read state file ({exc}). {_FORCE_RESYNC_HINT}"
            ) from exc
    reason = state_incompatibility_reason(raw_text)
    if reason is not None:
        raise IncompatibleStateError(f"{target}: {reason}. {_FORCE_RESYNC_HINT}")


def _normalize_state_path(explicit: Path) -> Path:
    """Map a vault root or state file path to ``…/llmwiki-state.json``."""
    p = Path(explicit).expanduser().resolve()
    if p.is_dir():
        return p / "llmwiki-state.json"
    return p


def configure_state_file(explicit: Path | None) -> Path:
    """Set the process-wide active state file (CLI border only).

    ``explicit`` may be a vault root directory or the state file itself.
    Library code should not call this — use ``resolve_state_file`` with an
    explicit path for one-off overrides.
    """
    global _ACTIVE_STATE_FILE
    if explicit is None:
        _ACTIVE_STATE_FILE = REPO_ROOT / "llmwiki-state.json"
    else:
        _ACTIVE_STATE_FILE = _normalize_state_path(explicit)
    return _ACTIVE_STATE_FILE


def get_state_file() -> Path:
    """Return the active state file for this process."""
    if _ACTIVE_STATE_FILE is not None:
        return _ACTIVE_STATE_FILE
    return REPO_ROOT / "llmwiki-state.json"


def resolve_state_file(explicit: Path | None = None) -> Path:
    """Return canonical ``<vault>/llmwiki-state.json``.

  ``explicit`` overrides the active default for this call only.
  When omitted, returns the process-wide active file from
  ``configure_state_file`` (or ``REPO_ROOT/llmwiki-state.json``).
    """
    if explicit is not None:
        return _normalize_state_path(explicit)
    return get_state_file()


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
