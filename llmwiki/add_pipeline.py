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

from llmwiki.add_doc import add_sources, expected_source_page, remove_raw_docs
from llmwiki.build import build_site
from llmwiki.config_schedule import _load_sessions_config, active_vault
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
    task_id: str | None = None,
) -> dict[str, Any]:
    """Run the shared add pipeline (caller holds ``pipeline_lock`` when needed).

    Returns a dict with ``exit_code``, ``build_failed``, ``task_id``,
    ``messages``, plus the ``add_sources`` result fields (``written``,
    ``titles``, ``docs``, ``warnings``, ``errors``, ``skipped``).

    ``task_id`` is the queue operation id (``add-sync-<ms>``). MCP mints it
    before the worker starts and passes it in so a timeout response names the
    same row. When omitted (CLI), this function mints one. Every return dict
    includes ``task_id``.

    ``writer`` receives every human-readable progress/diagnostic line (default
    ``print`` to stdout, or stderr for error lines). MCP passes a sink so
    progress never touches JSON-RPC stdout; callers can also read
    ``result["messages"]``.

    A tracking row (``task_type`` ``add_doc_sync``, not a ``TASK_HANDLERS``
    job) is written ``running`` before ``add_sources``. Every return path
    sets ``done`` or ``error`` so the row cannot stay ``running``. ``detail``
    holds vault-relative paths and flags; callers compute ``retry_safe`` from
    that state without stating the vault.
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
    if not task_id:
        now_ts = datetime.now(UTC)
        task_id = f"add-sync-{int(now_ts.timestamp() * 1000)}"
    root = vault_root if vault_root is not None else active_vault()
    # Generic finish line. A more specific rollback reason already stored on
    # the row must survive a later call that passes this sentence.
    generic_error = "add command finished with errors"
    detail: dict[str, Any] = {
        "written": [],
        "errors": [],
        "rolled_back": [],
        "build_failed": False,
        "files_remain": False,
    }
    specific_error = ""
    settled = False

    def _rel(path: Path) -> str:
        try:
            return path.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            return path.name

    def _note_files(
        written: list[Path],
        rolled: list[Path],
        *,
        remain: bool | None = None,
    ) -> None:
        written_rel = [_rel(p) for p in written]
        rolled_rel = [_rel(p) for p in rolled]
        detail["written"] = written_rel
        detail["rolled_back"] = rolled_rel
        if remain is None:
            rolled_set = set(rolled_rel)
            remain = any(path not in rolled_set for path in written_rel)
        detail["files_remain"] = remain

    def _track(status: str, *, result_msg: str = "", error_msg: str = "") -> None:
        stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        snapshot = {
            "written": [str(p) for p in detail["written"]],
            "errors": [str(e) for e in detail["errors"]],
            "rolled_back": [str(p) for p in detail["rolled_back"]],
            "build_failed": bool(detail["build_failed"]),
            "files_remain": bool(detail["files_remain"]),
        }

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
            row["detail"] = snapshot
            if result_msg:
                row["result"] = result_msg
            if error_msg:
                existing = str(row.get("last_error") or "")
                if not (error_msg == generic_error and existing):
                    row["last_error"] = error_msg
            s.setdefault("ops", {})["last_queue_run_at"] = stamp
            return s

        update_state(_mut, state_target)

    def _settle(status: str, *, result_msg: str = "", error_msg: str = "") -> None:
        nonlocal settled
        msg = error_msg
        if msg == generic_error and specific_error:
            msg = specific_error
        _track(status, result_msg=result_msg, error_msg=msg)
        settled = True

    # Visible to a poll during fetch/convert/synth — before any slow work.
    # Dry-run writes nothing, including this queue row. The CLI skips the
    # pipeline lock for the same reason.
    if not dry_run:
        _track("running")
    try:
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
        result["task_id"] = task_id
        detail["errors"] = [str(e) for e in result["errors"]]

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
        _note_files(list(result["written"]), [])

        failed = bool(result["errors"])
        if not result["written"]:
            result["exit_code"] = 2 if failed else 0
            if failed:
                _settle("error", error_msg=generic_error)
            else:
                _settle("done", result_msg="nothing written")
            return result

        # Paths are on the row before synthesize/build, which can outlive the
        # MCP budget. Status stays running until this function returns.
        _track("running", result_msg=f"wrote {len(result['written'])} file(s)")

        rolled: list[Path] = []
        # Opt-in synthesize: when requested, docs must become real wiki pages
        # in THIS invocation. Failure rolls back the just-added raw docs.
        if synthesize:
            backend = resolve_backend(_load_sessions_config())
            raw_dir = root / "raw" / "sessions"
            wiki_sources_dir = root / "wiki" / "sources"
            sources_dir = wiki_sources_dir
            if not backend.is_available():
                removed = remove_raw_docs(result["written"])
                rolled = list(removed)
                msg = (
                    f"  ! backend {backend.name} is not available — cannot "
                    f"synthesize. Rolled back {len(removed)} just-added raw "
                    "doc file(s). Set synthesis.backend in config.json "
                    "(claude / ollama / dummy), or omit --synthesize for "
                    "raw-only add."
                )
                _emit(msg, err=True)
                specific_error = msg.strip()
                detail["errors"].append(specific_error)
                _note_files(list(result["written"]), rolled)
                result["exit_code"] = 2
                _settle("error", error_msg=specific_error)
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
                text = str(err)
                if text not in detail["errors"]:
                    detail["errors"].append(text)
            missing = [
                p
                for p in result["written"]
                if not expected_source_page(p, sources_dir).exists()
            ]
            if missing:
                removed = remove_raw_docs(missing)
                rolled.extend(removed)
                _emit(
                    f"  ! rolled back {len(removed)} raw doc file(s) whose "
                    "synthesis produced no wiki page",
                    err=True,
                )
                failed = True
                specific_error = (
                    f"rolled back {len(removed)} unsynthesized raw doc file(s)"
                )
                if specific_error not in detail["errors"]:
                    detail["errors"].append(specific_error)
                _note_files(list(result["written"]), rolled)
                # Stay ``running`` through the site build. The specific
                # reason is applied once at the end so the generic finish
                # line cannot replace it.

        if build:
            raw_dir_b = root / "raw"
            raw_sessions = raw_dir_b / "sessions"
            wiki_dir = root / "wiki"
            out_dir = root / "site"
            code = build_site(
                out_dir=out_dir,
                raw_sessions=raw_sessions,
                raw_dir=raw_dir_b,
                wiki_dir=wiki_dir,
            )
            if code:
                result["build_failed"] = True
                detail["build_failed"] = True
                _emit(f"  ! site build failed (exit {code})", err=True)

        log_path = root / "wiki" / "log.md"
        if log_path.parent.is_dir():
            day = _date.today().isoformat()
            with log_path.open("a", encoding="utf-8") as fh:
                for rec in result["docs"]:
                    if any(p.exists() for p in rec["paths"]):
                        fh.write(f"\n## [{day}] add | {rec['title']}\n")

        refresh_synth_pending(
            raw_dir=root / "raw" / "sessions",
            docs_dir=root / "raw" / "docs",
            wiki_sources_dir=root / "wiki" / "sources",
            state_file=state_target,
        )

        # ``failed`` is add/synth only. A build-only miss is still ``done``
        # (docs landed); CLI exit_code stays non-zero below.
        if failed:
            _note_files(list(result["written"]), rolled)
            _settle("error", error_msg=generic_error)
        else:
            _note_files(list(result["written"]), rolled)
            if result["build_failed"]:
                _settle(
                    "done",
                    result_msg=f"added {len(result['written'])} file(s); site build failed",
                )
            else:
                _settle("done", result_msg=f"added {len(result['written'])} file(s)")
        result["exit_code"] = 2 if (failed or result["build_failed"]) else 0
        return result
    finally:
        if not dry_run and not settled:
            if specific_error and specific_error not in detail["errors"]:
                detail["errors"].append(specific_error)
            _track(
                "error",
                error_msg=specific_error or "add command failed before finishing",
            )
