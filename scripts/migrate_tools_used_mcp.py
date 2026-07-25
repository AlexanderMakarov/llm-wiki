#!/usr/bin/env python3
"""Expand CallMcpTool / GetMcpTools in raw session frontmatter from origin stores.

Rewrites ``tools_used`` and ``tool_counts`` in ``raw/sessions/*.md`` when the
originating agent session file still exists on disk. Re-reads records through
the session adapter and applies the same ``tool_use_recorded_names`` expansion
``llmwiki sync`` uses today.

Does **not**:

- call the LLM / enqueue ``synthesize``
- touch ``wiki/``
- invent MCP tool names when the origin store is gone (TTL / deleted)

Usage:
  python3 scripts/migrate_tools_used_mcp.py --vault /path/to/vault
  python3 scripts/migrate_tools_used_mcp.py --vault /path/to/vault --dry-run
  llmwiki migrate-tools-used --vault /path/to/vault
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from llmwiki._frontmatter import parse_frontmatter
from llmwiki.adapters import REGISTRY, discover_adapters, resolve_adapter_name
from llmwiki.convert import (
    _MCP_TOOL_WRAPPERS,
    _resolve_convert_config,
    _source_hash8,
    compute_tool_counts,
    extract_tools_used,
    filter_records,
    first_field,
    load_state,
)
from llmwiki.lint.rules._helpers import _normalise_tools_used
from llmwiki.state_store import resolve_state_file

_DISAMBIG_RE = re.compile(r"--([0-9a-f]{8})\.md$", re.IGNORECASE)


def _sessions_dir(vault: Path) -> Path:
    return vault / "raw" / "sessions"


def _infer_adapter_name(meta: dict[str, Any]) -> str:
    tags = meta.get("tags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    skip = {"session-transcript", "raw-doc", "wiki-add"}
    for tag in tags:
        raw = str(tag).strip()
        if not raw or raw in skip:
            continue
        for candidate in (raw.replace("-", "_"), raw):
            canon = resolve_adapter_name(candidate)
            if canon:
                return canon
    return "claude_code"


def _state_key_to_path(key: str) -> tuple[str, Path] | None:
    if "::" not in key:
        return None
    adapter, rel = key.split("::", 1)
    adapter = adapter.strip()
    rel = rel.strip()
    if not adapter or not rel:
        return None
    return adapter, Path.home() / rel


def _disambig_from_filename(name: str) -> str | None:
    match = _DISAMBIG_RE.search(name)
    return match.group(1).lower() if match else None


def _needs_mcp_expansion(meta: dict[str, Any]) -> bool:
    tools = _normalise_tools_used(meta.get("tools_used"))
    return bool(tools & _MCP_TOOL_WRAPPERS)


def _records_session_id(
    records: list[dict[str, Any]], path: Path
) -> str:
    return first_field(records, "sessionId") or path.stem


def _load_filtered_records(adapter: Any, path: Path, config: dict[str, Any]) -> list[dict[str, Any]]:
    drop_types = config.get("filters", {}).get("drop_record_types", [])
    records = adapter.load_records(path)
    records = adapter.normalize_records(records)
    return filter_records(records, drop_types)


def _verify_origin(
    adapter: Any,
    path: Path,
    session_id: str,
    config: dict[str, Any],
) -> list[dict[str, Any]] | None:
    try:
        records = _load_filtered_records(adapter, path, config)
    except (OSError, json.JSONDecodeError, ValueError):
        return None
    if not records:
        return None
    if _records_session_id(records, path) != session_id:
        return None
    return records


def resolve_origin_path(
    *,
    session_id: str,
    adapter_name: str,
    state_file: Path,
    disambig_hash: str | None,
    config: dict[str, Any],
) -> Path | None:
    """Return the on-disk origin session path, or None when unavailable."""
    if not session_id:
        return None

    discover_adapters()
    adapter_cls = REGISTRY.get(adapter_name)
    if adapter_cls is None:
        return None
    adapter = adapter_cls(config)

    candidates: list[Path] = []
    state = load_state(state_file, [adapter_name])
    for key in state:
        parsed = _state_key_to_path(key)
        if parsed is None:
            continue
        ad, path = parsed
        if ad != adapter_name or not path.is_file():
            continue
        candidates.append(path)

    if disambig_hash:
        for path in candidates:
            if _source_hash8(path) == disambig_hash:
                if _verify_origin(adapter, path, session_id, config):
                    return path

    for path in candidates:
        if path.stem == session_id and _verify_origin(adapter, path, session_id, config):
            return path

    for path in candidates:
        if _verify_origin(adapter, path, session_id, config):
            return path

    stores = adapter.session_store_path
    if isinstance(stores, Path):
        stores = [stores]
    for store in stores:
        store = Path(store).expanduser()
        if not store.is_dir():
            continue
        for path in store.rglob(f"{session_id}.jsonl"):
            if path.is_file() and _verify_origin(adapter, path, session_id, config):
                return path

    return None


def _format_tools_used(tools_used: list[str]) -> str:
    return f"tools_used: [{', '.join(tools_used)}]"


def _format_tool_counts(tool_counts: dict[str, int]) -> str:
    return f"tool_counts: {json.dumps(tool_counts, sort_keys=False)}"


def _update_tools_frontmatter(
    text: str,
    *,
    tools_used: list[str],
    tool_counts: dict[str, int],
) -> str:
    tools_line = _format_tools_used(tools_used)
    counts_line = _format_tool_counts(tool_counts)
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    saw_tools = saw_counts = False
    for line in lines:
        if line.startswith("tools_used:"):
            out.append(
                tools_line + ("\n" if line.endswith("\n") else "")
            )
            saw_tools = True
        elif line.startswith("tool_counts:"):
            out.append(
                counts_line + ("\n" if line.endswith("\n") else "")
            )
            saw_counts = True
        else:
            out.append(line)
    if not saw_tools or not saw_counts:
        return text
    return "".join(out)


def migrate_session_text(
    text: str,
    *,
    path: Path,
    vault: Path,
    config: dict[str, Any],
    state_file: Path,
) -> tuple[str, str]:
    """Return ``(updated_text, status)`` where status is rewritten/unchanged/skipped."""
    meta, _body = parse_frontmatter(text)
    if not meta:
        return text, "unchanged"
    if not _needs_mcp_expansion(meta):
        return text, "unchanged"

    session_id = str(meta.get("sessionId") or "").strip()
    adapter_name = _infer_adapter_name(meta)
    disambig = _disambig_from_filename(path.name)
    origin = resolve_origin_path(
        session_id=session_id,
        adapter_name=adapter_name,
        state_file=state_file,
        disambig_hash=disambig,
        config=config,
    )
    if origin is None:
        return text, "skipped_missing_origin"

    records = _load_filtered_records(
        REGISTRY[adapter_name](config), origin, config
    )
    tools_used = extract_tools_used(records)
    tool_counts = compute_tool_counts(records)
    updated = _update_tools_frontmatter(
        text,
        tools_used=tools_used,
        tool_counts=tool_counts,
    )
    if updated == text:
        return text, "unchanged"
    return updated, "rewritten"


def run_migration(
    *,
    vault: Path,
    dry_run: bool = False,
    config_file: Path | None = None,
) -> dict[str, Any]:
    """Rewrite ``vault/raw/sessions/**/*.md`` in place. Returns a report dict."""
    vault = vault.expanduser().resolve()
    config = _resolve_convert_config(config_file)
    state_file = resolve_state_file(vault)
    sessions = _sessions_dir(vault)
    report: dict[str, Any] = {
        "vault": str(vault),
        "sessions_dir": str(sessions),
        "state_file": str(state_file),
        "dry_run": dry_run,
        "scanned": 0,
        "rewritten": 0,
        "unchanged": 0,
        "skipped_missing_origin": 0,
        "errors": [],
        "files": [],
    }
    if not sessions.is_dir():
        report["errors"].append(f"missing sessions dir: {sessions}")
        return report

    for path in sorted(sessions.rglob("*.md")):
        report["scanned"] += 1
        try:
            original = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            report["errors"].append(f"{path}: {exc}")
            continue
        try:
            updated, status = migrate_session_text(
                original,
                path=path,
                vault=vault,
                config=config,
                state_file=state_file,
            )
        except Exception as exc:  # noqa: BLE001 — migration reports, never aborts vault
            report["errors"].append(f"{path}: {exc}")
            continue
        if status == "rewritten":
            report["rewritten"] += 1
            report["files"].append(str(path.relative_to(vault)))
            if not dry_run:
                path.write_text(updated, encoding="utf-8")
        elif status == "skipped_missing_origin":
            report["skipped_missing_origin"] += 1
        else:
            report["unchanged"] += 1
    return report


def print_report(report: dict[str, Any]) -> None:
    print(f"vault:                  {report['vault']}")
    print(f"sessions:               {report['sessions_dir']}")
    print(f"state:                  {report['state_file']}")
    print(f"dry_run:                {report['dry_run']}")
    print(f"scanned:                {report['scanned']}")
    print(f"rewritten:              {report['rewritten']}")
    print(f"unchanged:              {report['unchanged']}")
    print(f"skipped_missing_origin: {report['skipped_missing_origin']}")
    if report["errors"]:
        print(f"errors:                 {len(report['errors'])}")
        for err in report["errors"][:10]:
            print(f"  ! {err}")
    if report["files"] and (report["dry_run"] or report["rewritten"] <= 20):
        print("files:")
        for rel in report["files"][:50]:
            print(f"  - {rel}")
        if len(report["files"]) > 50:
            print(f"  … +{len(report['files']) - 50} more")
    print(
        "note: wiki/ untouched; no synthesize queued. "
        "Missing origins are left unchanged — never invent MCP names. "
        "Run `llmwiki build --vault …` afterwards so site/ picks up changes."
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=(
            "Expand CallMcpTool/GetMcpTools frontmatter in raw/sessions "
            "from still-available origin session stores."
        )
    )
    p.add_argument(
        "--vault",
        type=Path,
        required=True,
        help="Vault root (contains raw/sessions/)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Report files that would change; write nothing",
    )
    p.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Optional sessions_config.json override",
    )
    args = p.parse_args(argv)
    report = run_migration(
        vault=args.vault,
        dry_run=args.dry_run,
        config_file=args.config,
    )
    print_report(report)
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
