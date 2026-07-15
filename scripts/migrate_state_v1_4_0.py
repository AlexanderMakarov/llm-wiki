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
import re
from pathlib import Path
from typing import Any

from llmwiki.config_schedule import _load_sessions_config
from llmwiki.queue_ops import enqueue_task
from llmwiki.state_store import read_state, resolve_state_file, write_state, mtime_to_iso
from llmwiki.synth.pipeline import refresh_synth_pending


LEGACY_FILES = (
    ".llmwiki-state.json",
    ".llmwiki-synth-state.json",
    ".llmwiki-quarantine.json",
    ".llmwiki-queue.json",
)
LEGACY_PENDING_DIR = ".llmwiki-pending-prompts"

# Backend values dropped in v1.4.0. `resolve_backend` reads any of them as a
# typo and silently falls back to `dummy`, which then writes dummy stubs into
# wiki/sources — so the migration flags them loudly (#23).
REMOVED_BACKENDS = {"agent", "agent-delegate", "agent_delegate"}
SUPPORTED_BACKENDS = ("claude", "ollama", "dummy")

# Unfilled target page left by the agent-delegate backend:
# `<!-- llmwiki-pending: <uuid> -->`, where <uuid> is the pending prompt's stem.
_PENDING_SENTINEL_RE = re.compile(r"<!--\s*llmwiki-pending:\s*([^\s>]+?)\s*-->")


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _sentinel_uuids(wiki_sources: Path) -> set[str]:
    """UUIDs of every source page still carrying a pending sentinel."""
    out: set[str] = set()
    if not wiki_sources.is_dir():
        return out
    for p in wiki_sources.rglob("*.md"):
        try:
            text = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        out.update(_PENDING_SENTINEL_RE.findall(text))
    return out


def _removed_backend_warning(root: Path) -> str | None:
    """Warn when the vault's config still names a backend removed in v1.4.0."""
    vault_config = root / "config.json"
    cfg = _load_sessions_config(vault_config if vault_config.is_file() else None)
    synthesis = cfg.get("synthesis", {})
    if not isinstance(synthesis, dict):
        return None
    backend = str(synthesis.get("backend") or "").strip()
    if backend.lower() not in REMOVED_BACKENDS:
        return None
    return (
        f"synthesis.backend={backend!r} was removed in v1.4.0 — it silently "
        f"falls back to the dummy backend, which writes stub pages into "
        f"wiki/sources. Set it to one of: {', '.join(SUPPORTED_BACKENDS)}."
    )


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
        "warnings": [],
        "pending_prompts_total": 0,
        "pending_prompts_unfilled": 0,
        "synth_request_items_purged": 0,
        "queued_synthesize": 0,
    }
    backend_warning = _removed_backend_warning(root)
    if backend_warning:
        report["warnings"].append(backend_warning)

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

    # Legacy pending prompts are resolved, not re-queued: a prompt whose uuid
    # still has a sentinel page in wiki/sources is unfilled work; one without
    # is already fulfilled and records nothing. The backlog is drained by a
    # single `synthesize` task enqueued below (#23).
    pending_dir = root / LEGACY_PENDING_DIR
    if pending_dir.is_dir():
        sentinels = _sentinel_uuids(root / "wiki" / "sources")
        prompts = sorted(pending_dir.glob("*.md"))
        report["pending_prompts_total"] = len(prompts)
        report["pending_prompts_unfilled"] = sum(
            1 for p in prompts if p.stem in sentinels
        )
        report["migrated"].append(str(pending_dir))

    items = state.get("queue", {}).get("items", [])
    kept = [
        row
        for row in items
        if not (isinstance(row, dict) and row.get("task_type") == "synth_request")
    ]
    report["synth_request_items_purged"] = len(items) - len(kept)
    state["queue"]["items"] = kept

    if target.exists():
        backup = target.with_suffix(target.suffix + ".bak")
        backup.write_bytes(target.read_bytes())

    write_state(state, target)
    pending = refresh_synth_pending(
        raw_dir=root / "raw" / "sessions",
        docs_dir=root / "raw" / "docs",
        wiki_sources_dir=root / "wiki" / "sources",
        state_file=target,
    )
    # One task drains the whole backlog, so a pending one already covers it —
    # re-running the migration must not stack duplicates.
    already_queued = any(
        isinstance(row, dict)
        and row.get("task_type") == "synthesize"
        and row.get("status") == "pending"
        for row in kept
    )
    if pending["pending_total"] > 0 and not already_queued:
        enqueue_task("synthesize", {}, target)
        report["queued_synthesize"] = 1

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
        print_report(report)
    return 0


def print_report(report: dict[str, Any]) -> None:
    """Human-readable migration report (shared with ``llmwiki migrate-state``)."""
    print(f"state file: {report['state_file']}")
    if report.get("migrated"):
        print("migrated:")
        for path in report["migrated"]:
            print(f"  - {path}")
    if report.get("pending_prompts_total"):
        print(
            f"pending prompts: {report['pending_prompts_total']} "
            f"({report['pending_prompts_unfilled']} still unfilled)"
        )
    if report.get("synth_request_items_purged"):
        print(f"purged dead synth_request items: {report['synth_request_items_purged']}")
    if report.get("queued_synthesize"):
        print("enqueued 1 synthesize task — run `llmwiki queue run --vault <path>`")
    for warning in report.get("warnings", []):
        print(f"WARNING: {warning}")
    if report.get("orphan_cleanup_suggestions"):
        print("cleanup suggestions:")
        for cmd in report["orphan_cleanup_suggestions"]:
            print(f"  {cmd}")


if __name__ == "__main__":
    raise SystemExit(main())
