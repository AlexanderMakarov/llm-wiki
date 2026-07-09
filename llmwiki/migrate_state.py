from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from llmwiki import REPO_ROOT
from llmwiki.state_store import read_state, resolve_state_file, write_state


LEGACY_FILES = (
    ".llmwiki-state.json",
    ".llmwiki-synth-state.json",
    ".llmwiki-quarantine.json",
    ".llmwiki-queue.json",
)
LEGACY_PENDING_DIR = ".llmwiki-pending-prompts"


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def run_migration(state_file: Path | None = None) -> dict[str, Any]:
    target = resolve_state_file(state_file)
    root = target.parent
    state = read_state(target)
    report: dict[str, Any] = {
        "state_file": str(target),
        "migrated": [],
        "orphan_cleanup_suggestions": [],
    }

    legacy_sync = root / ".llmwiki-state.json"
    if legacy_sync.exists():
        data = _read_json(legacy_sync)
        if isinstance(data, dict):
            legacy_files = {
                k: v for k, v in data.items()
                if isinstance(k, str) and isinstance(v, (int, float))
            }
            merged = dict(state.get("sync", {}).get("files", {}))
            merged.update(legacy_files)
            state["sync"]["files"] = merged
            if isinstance(data.get("_meta"), dict):
                state["sync"]["meta"] = data["_meta"]
            if isinstance(data.get("_counters"), dict):
                state["sync"]["counters"] = data["_counters"]
            report["migrated"].append(str(legacy_sync))

    legacy_synth = root / ".llmwiki-synth-state.json"
    if legacy_synth.exists():
        data = _read_json(legacy_synth)
        if isinstance(data, dict):
            legacy_files = {
                k: v for k, v in data.items()
                if isinstance(k, str) and isinstance(v, (int, float))
            }
            merged = dict(state.get("synth", {}).get("files", {}))
            merged.update(legacy_files)
            state["synth"]["files"] = merged
            report["migrated"].append(str(legacy_synth))

    legacy_quarantine = root / ".llmwiki-quarantine.json"
    if legacy_quarantine.exists():
        data = _read_json(legacy_quarantine)
        if isinstance(data, dict) and isinstance(data.get("entries"), list):
            existing = state.get("quarantine", {}).get("entries", [])
            existing_set = {json.dumps(x, sort_keys=True) for x in existing if isinstance(x, dict)}
            for row in data["entries"]:
                if isinstance(row, dict):
                    key = json.dumps(row, sort_keys=True)
                    if key not in existing_set:
                        existing.append(row)
                        existing_set.add(key)
            state["quarantine"]["entries"] = existing
            report["migrated"].append(str(legacy_quarantine))

    legacy_queue = root / ".llmwiki-queue.json"
    if legacy_queue.exists():
        data = _read_json(legacy_queue)
        if isinstance(data, list):
            existing = set(state.get("queue", {}).get("legacy_pending_paths", []))
            existing.update(x for x in data if isinstance(x, str))
            state["queue"]["legacy_pending_paths"] = sorted(existing)
            report["migrated"].append(str(legacy_queue))

    pending_dir = root / LEGACY_PENDING_DIR
    if pending_dir.is_dir():
        prompt_items = []
        for p in sorted(pending_dir.glob("*.md")):
            prompt_items.append(
                {
                    "id": p.stem,
                    "task_type": "synth_request",
                    "status": "pending",
                    "created_at": "",
                    "source_file": str(p),
                }
            )
        existing_ids = {
            str(row.get("id"))
            for row in state.get("queue", {}).get("items", [])
            if isinstance(row, dict) and row.get("id")
        }
        for row in prompt_items:
            if row["id"] not in existing_ids:
                state["queue"]["items"].append(row)
        report["migrated"].append(str(pending_dir))

    if target.exists():
        backup = target.with_suffix(target.suffix + ".bak")
        backup.write_bytes(target.read_bytes())

    write_state(state, target)

    for rel in (*LEGACY_FILES, LEGACY_PENDING_DIR):
        candidate = root / rel
        if candidate.exists():
            report["orphan_cleanup_suggestions"].append(f"rm -rf {candidate}")
    return report
