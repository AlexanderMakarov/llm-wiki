"""Shared ``add`` orchestration for CLI and MCP (#273).

Owns the post-``pipeline_lock`` body formerly in ``cli._cmd_add_locked``:
convert/write via :func:`add_sources`, optional synthesize, optional site
build, ``wiki/log.md`` lines, ``refresh_synth_pending``, and queue/state
row updates.

Defaults (product flip vs historical CLI): synthesize **off** unless
requested; site rebuild **on** unless skipped.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from datetime import UTC, datetime
from datetime import date as _date
from pathlib import Path
from typing import Any

from llmwiki import REPO_ROOT
from llmwiki.add_doc import add_sources, expected_source_page, remove_raw_docs
from llmwiki.build import RAW_DIR, RAW_SESSIONS, build_site
from llmwiki.config_schedule import _load_sessions_config
from llmwiki.state_store import resolve_state_file, update_state
from llmwiki.synth.pipeline import (
    refresh_synth_pending,
    resolve_backend,
    synthesize_new_sessions,
)

__all__ = ["run_add"]


def run_add(
    sources: list[str],
    docs_dir: Path,
    *,
    vault_root: Path | None = None,
    title: str | None = None,
    project: str | None = None,
    tags: tuple[str, ...] = (),
    note: str | None = None,
    render: str = "auto",
    dry_run: bool = False,
    force_new: bool = False,
    synthesize: bool = False,
    build: bool = True,
    stdin_text: str | None = None,
    writer: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Run the shared add pipeline (caller holds ``pipeline_lock`` when needed).

    Returns a dict with ``exit_code``, ``build_failed``, ``messages``, plus the
    ``add_sources`` result fields (``written``, ``titles``, ``docs``,
    ``warnings``, ``errors``, ``skipped``).

    ``writer`` receives every human-readable progress/diagnostic line (default
    ``print`` to stdout, or stderr for error lines). MCP passes a sink so
    progress never touches JSON-RPC stdout; callers can also read
    ``result["messages"]``.
    """
    messages: list[str] = []

    def _emit(line: str, *, err: bool = False) -> None:
        messages.append(line)
        if writer is not None:
            writer(line)
        elif err:
            print(line, file=sys.stderr)
        else:
            print(line)

    state_target = resolve_state_file()
    now_ts = datetime.now(UTC)
    task_id = f"add-sync-{int(now_ts.timestamp() * 1000)}"

    def _track(status: str, *, result_msg: str = "", error_msg: str = "") -> None:
        stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

        def _mut(s: dict[str, Any]) -> dict[str, Any]:
            items = s.setdefault("queue", {}).setdefault("items", [])
            row = None
            for it in items:
                if isinstance(it, dict) and it.get("id") == task_id:
                    row = it
                    break
            if row is None:
                row = {
                    "id": task_id,
                    "task_type": "add_doc_sync",
                    "payload": {"sources": list(sources)},
                    "created_at": stamp,
                    "attempts": 1,
                }
                items.append(row)
            row["status"] = status
            row["updated_at"] = stamp
            if result_msg:
                row["result"] = result_msg
            if error_msg:
                row["last_error"] = error_msg
            s.setdefault("ops", {})["last_queue_run_at"] = stamp
            return s

        update_state(_mut, state_target)

    result = add_sources(
        list(sources),
        docs_dir,
        title=title,
        project=project,
        tags=tags,
        note=note,
        render=render,
        dry_run=dry_run,
        force_new=force_new,
        stdin_text=stdin_text,
    )
    result["messages"] = messages
    result["build_failed"] = False

    for title_line in result["titles"]:
        _emit(f"  + {title_line}")
    for w in result["warnings"]:
        _emit(f"  ~ {w}")
    for e in result["errors"]:
        _emit(f"  ! {e}", err=True)
    if dry_run:
        result["exit_code"] = 2 if result["errors"] else 0
        return result
    _emit(f"  wrote {len(result['written'])} file(s) under {docs_dir}")
    _track("running", result_msg=f"wrote {len(result['written'])} file(s)")

    failed = bool(result["errors"])
    if not result["written"]:
        result["exit_code"] = 2 if failed else 0
        return result

    # Opt-in synthesize: when requested, docs must become real wiki pages
    # in THIS invocation. Failure rolls back the just-added raw docs.
    if synthesize:
        backend = resolve_backend(_load_sessions_config())
        raw_dir = wiki_sources_dir = None
        sources_dir = REPO_ROOT / "wiki" / "sources"
        if vault_root:
            raw_dir = vault_root / "raw" / "sessions"
            wiki_sources_dir = vault_root / "wiki" / "sources"
            sources_dir = wiki_sources_dir
        if not backend.is_available():
            removed = remove_raw_docs(result["written"])
            msg = (
                f"  ! backend {backend.name} is not available — cannot "
                f"synthesize. Rolled back {len(removed)} just-added raw "
                "doc file(s). Set synthesis.backend in config.json "
                "(claude / ollama / dummy), or omit --synthesize for "
                "raw-only add."
            )
            _emit(msg, err=True)
            result["exit_code"] = 2
            return result
        _emit(f"Synthesizing with backend: {backend.name}")
        summary = synthesize_new_sessions(
            backend=backend,
            raw_dir=raw_dir,
            wiki_sources_dir=wiki_sources_dir,
            only_paths=set(result["written"]),
        )
        _emit(
            f"  synthesized {summary['synthesized']}, "
            f"skipped {summary['skipped']}"
        )
        for err in summary["errors"]:
            _emit(f"  ! {err}", err=True)
        missing = [
            p
            for p in result["written"]
            if not expected_source_page(p, sources_dir).exists()
        ]
        if missing:
            removed = remove_raw_docs(missing)
            _emit(
                f"  ! rolled back {len(removed)} raw doc file(s) whose "
                "synthesis produced no wiki page",
                err=True,
            )
            failed = True
            _track(
                "error",
                error_msg=(
                    f"rolled back {len(removed)} unsynthesized raw doc file(s)"
                ),
            )

    if build:
        raw_sessions, raw_dir_b = RAW_SESSIONS, RAW_DIR
        wiki_dir = REPO_ROOT / "wiki"
        out_dir = REPO_ROOT / "site"
        if vault_root:
            raw_dir_b = vault_root / "raw"
            raw_sessions = raw_dir_b / "sessions"
            wiki_dir = vault_root / "wiki"
            out_dir = vault_root / "site"
        code = build_site(
            out_dir=out_dir,
            raw_sessions=raw_sessions,
            raw_dir=raw_dir_b,
            wiki_dir=wiki_dir,
        )
        if code:
            result["build_failed"] = True
            _emit(f"  ! site build failed (exit {code})", err=True)

    log_path = (vault_root or REPO_ROOT) / "wiki" / "log.md"
    if log_path.parent.is_dir():
        day = _date.today().isoformat()
        with log_path.open("a", encoding="utf-8") as fh:
            for rec in result["docs"]:
                if any(p.exists() for p in rec["paths"]):
                    fh.write(f"\n## [{day}] add | {rec['title']}\n")

    refresh_synth_pending(
        raw_dir=(vault_root / "raw" / "sessions") if vault_root else None,
        docs_dir=(vault_root / "raw" / "docs") if vault_root else None,
        wiki_sources_dir=(vault_root / "wiki" / "sources") if vault_root else None,
        state_file=state_target,
    )

    # ``failed`` is add/synth only; ``build_failed`` is recorded separately so
    # MCP can return success when the doc landed and only the site build failed.
    if failed or result["build_failed"]:
        _track("error", error_msg="add command finished with errors")
    else:
        _track("done", result_msg=f"added {len(result['written'])} file(s)")
    result["exit_code"] = 2 if (failed or result["build_failed"]) else 0
    return result
