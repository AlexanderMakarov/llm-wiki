#!/usr/bin/env python3
"""One-time vault state migration for llmwiki v1.4.0.

Migrates legacy dotfiles (``.llmwiki-state.json``, ``.llmwiki-synth-state.json``,
``.llmwiki-queue.json``, ``.llmwiki-quarantine.json``, ``.llmwiki-pending-prompts/``)
into unified ``llmwiki-state.json``.

Usage:
  python3 scripts/migrate_state_v1_4_0.py [--state-file PATH]
  llmwiki migrate-state [--state-file PATH]   # thin CLI wrapper
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from llmwiki.state_store import read_state, resolve_state_file, write_state, mtime_to_iso
from llmwiki.synth.pipeline import refresh_synth_pending


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


def _legacy_mtime_map(data: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in data.items():
        if not isinstance(k, str):
            continue
        if isinstance(v, bool):
            continue
        if isinstance(v, (int, float)):
            out[k] = mtime_to_iso(float(v))
    return out


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
            legacy_files = _legacy_mtime_map(data)
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
            legacy_files = _legacy_mtime_map(data)
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
    refresh_synth_pending(
        raw_dir=root / "raw" / "sessions",
        docs_dir=root / "raw" / "docs",
        wiki_sources_dir=root / "wiki" / "sources",
        state_file=target,
    )

    for rel in (*LEGACY_FILES, LEGACY_PENDING_DIR):
        candidate = root / rel
        if candidate.exists():
            report["orphan_cleanup_suggestions"].append(f"rm -rf {candidate}")
    return report


def main(argv: list[str] | None = None) -> int:
    import argparse
    import json
    import sys
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--state-file", type=Path, default=None,
                   help="Target unified state file or vault root")
    p.add_argument("--json", action="store_true", help="Print report as JSON")
    args = p.parse_args(argv)
    report = run_migration(args.state_file)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"state file: {report['state_file']}")
        if report["migrated"]:
            print("migrated:")
            for path in report["migrated"]:
                print(f"  - {path}")
        if report["orphan_cleanup_suggestions"]:
            print("cleanup suggestions:")
            for cmd in report["orphan_cleanup_suggestions"]:
                print(f"  {cmd}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
