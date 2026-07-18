"""Local-only MCP usage telemetry (#26).

The MCP server executes tools blind — no record of which tools are
called, how often, by which project, or whether they found anything.
This module is the collection + aggregation layer that fixes that,
with three hard constraints from the issue:

* **Local only.** No network, no third parties — files under
  ``<content_root>/usage/`` that the site build reads.
* **Concurrency-safe across processes.** Several ``llmwiki.mcp`` servers
  run at once (one per editor session). Each writes its *own*
  per-process JSONL file (``mcp-<pid>-<start>.jsonl``); they are merged
  at read time. Zero write contention by construction — no locks on the
  hot path, and telemetry never routes through ``llmwiki-state.json``
  (whose read-modify-write cycle would race).
* **Cheap to keep forever.** Raw logs roll monthly: ``compact`` folds
  whole past months into a kept-forever numeric ``rollup.json`` and
  deletes the raw files, so aggregation stays O(recent) while lifetime
  totals never disappear.

Rendering these numbers on the site is a separate issue (#27); this
module stops at collection, aggregation, and the ``rollup.json`` seam.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator

USAGE_DIRNAME = "usage"
ROLLUP_NAME = "rollup.json"
# Only the primary user-supplied argument is recorded, capped so a record
# stays well under PIPE_BUF — keeps lines tiny and never leaks large blobs.
QUERY_MAX_CHARS = 200
# Arg keys that count as "the thing the caller asked for", in priority order.
_QUERY_KEYS = ("term", "question", "path", "query", "project")

# Tools whose result is a set of retrievable entities/answers. Only these
# contribute to "items returned" — lint/sync/lifecycle/dashboard perform an
# action or report status rather than returning corpus items.
ENTITY_TOOLS = frozenset({
    "wiki_query", "wiki_search", "wiki_list_sources", "wiki_read_page",
    "wiki_entity_search", "wiki_category_browse", "wiki_export", "wiki_confidence",
})


def is_entity_tool(tool: str) -> bool:
    return tool in ENTITY_TOOLS


def usage_dir(content_root: Path) -> Path:
    return Path(content_root) / USAGE_DIRNAME


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _fs_safe(stamp: str) -> str:
    """ISO timestamps carry colons; make them filename-safe."""
    return stamp.replace(":", "-")


def detect_caller_project() -> str:
    """stdio MCP servers inherit the client session's working directory, so
    ``os.getcwd()`` captured once at server start is a workable project
    attribution. Fall back to ``"unknown"``."""
    try:
        name = os.path.basename(os.getcwd())
    except OSError:
        return "unknown"
    return name or "unknown"


def extract_query(args: dict[str, Any]) -> str | None:
    """Pull the primary user argument for a tool call, truncated."""
    for key in _QUERY_KEYS:
        val = args.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()[:QUERY_MAX_CHARS]
    return None


class UsageRecorder:
    """One instance per server process; owns exactly one JSONL file.

    Because no two live processes share a file, appends need no lock and
    no atomicity ceiling — a plain buffered append per line is enough.
    """

    def __init__(
        self,
        content_root: Path,
        *,
        caller_project: str | None = None,
        pid: int | None = None,
        started: str | None = None,
    ) -> None:
        self.dir = usage_dir(content_root)
        self.pid = pid if pid is not None else os.getpid()
        self.started = started or _iso_now()
        self.caller_project = caller_project or detect_caller_project()
        self.path = self.dir / f"mcp-{self.pid}-{_fs_safe(self.started)}.jsonl"

    def record(
        self,
        *,
        tool: str,
        query: str | None = None,
        hits: int | None = None,
        resp_bytes: int = 0,
        duration_ms: int = 0,
        ts: str | None = None,
    ) -> None:
        record = {
            "ts": ts or _iso_now(),
            "tool": tool,
            "query": query,
            "hits": hits,
            "resp_bytes": int(resp_bytes),
            "duration_ms": int(duration_ms),
            "caller_project": self.caller_project,
            "server_pid": self.pid,
            "server_started": self.started,
        }
        line = json.dumps(record, ensure_ascii=False)
        # Telemetry is strictly best-effort: a full disk or a clobbered
        # usage/ path must never break a tool call.
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        except OSError:
            pass


# ─── Reading / merging ─────────────────────────────────────────────────────

def iter_records_file(path: Path) -> Iterator[dict[str, Any]]:
    """Yield records from a single JSONL file. Malformed lines are skipped —
    a half-written final line from a crashed process must not poison the
    whole read."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            yield obj


def iter_records(content_root: Path) -> Iterator[dict[str, Any]]:
    """Yield every telemetry record across all per-process files, merged."""
    d = usage_dir(content_root)
    if not d.exists():
        return
    for p in sorted(d.glob("mcp-*.jsonl")):
        yield from iter_records_file(p)


def _empty_totals() -> dict[str, Any]:
    return {
        "total_calls": 0,
        "total_resp_bytes": 0,
        "total_items_returned": 0,
        "total_server_processes": 0,
        "per_tool": {},
        "per_project": {},
    }


def _finalize_rates(totals: dict[str, Any]) -> dict[str, Any]:
    for stats in totals["per_tool"].values():
        calls = stats["calls"]
        stats["zero_hit_rate"] = (stats["zero_hits"] / calls) if calls else 0.0
    return totals


def aggregate(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Fold raw records into totals: calls + bytes + zero-hit counts per
    tool and per caller_project.

    ``hits == 0`` is the signal that matters — a zero-hit call is a
    knowledge gap or noise (raw material for ``/wiki-reflect``). A missing
    ``hits`` (the tool couldn't report a count) is *unknown*, not a miss,
    so it is never counted as zero-hit.
    """
    totals = _empty_totals()
    proc_sets: dict[str, set] = {}
    for r in records:
        tool = r.get("tool") or "unknown"
        project = r.get("caller_project") or "unknown"
        resp_bytes = int(r.get("resp_bytes") or 0)
        hits = r.get("hits")

        tstat = totals["per_tool"].setdefault(
            tool, {"calls": 0, "zero_hits": 0, "resp_bytes": 0, "items_returned": 0})
        tstat["calls"] += 1
        tstat["resp_bytes"] += resp_bytes
        if hits == 0:
            tstat["zero_hits"] += 1

        pstat = totals["per_project"].setdefault(
            project, {"calls": 0, "resp_bytes": 0, "items_returned": 0, "server_processes": 0})
        pstat["calls"] += 1
        pstat["resp_bytes"] += resp_bytes

        if tool in ENTITY_TOOLS and isinstance(hits, int) and hits > 0:
            tstat["items_returned"] += hits
            pstat["items_returned"] += hits
            totals["total_items_returned"] += hits

        pid = r.get("server_pid")
        started = r.get("server_started")
        if pid is not None and started is not None:
            proc_sets.setdefault(project, set()).add((pid, started))

        totals["total_calls"] += 1
        totals["total_resp_bytes"] += resp_bytes

    for proj, procs in proc_sets.items():
        pstat = totals["per_project"].setdefault(
            proj, {"calls": 0, "resp_bytes": 0, "items_returned": 0, "server_processes": 0})
        pstat["server_processes"] = len(procs)
        totals["total_server_processes"] += len(procs)

    return _finalize_rates(totals)


def merge_aggregates(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    """Sum two aggregate dicts. Used to join a kept-forever ``rollup.json``
    with the freshly-aggregated live logs."""
    out = _empty_totals()
    out["total_calls"] = a.get("total_calls", 0) + b.get("total_calls", 0)
    out["total_resp_bytes"] = (
        a.get("total_resp_bytes", 0) + b.get("total_resp_bytes", 0))
    out["total_items_returned"] = (
        a.get("total_items_returned", 0) + b.get("total_items_returned", 0))
    out["total_server_processes"] = (
        a.get("total_server_processes", 0) + b.get("total_server_processes", 0))
    for side in (a, b):
        for tool, stats in side.get("per_tool", {}).items():
            dst = out["per_tool"].setdefault(
                tool, {"calls": 0, "zero_hits": 0, "resp_bytes": 0, "items_returned": 0})
            dst["calls"] += stats.get("calls", 0)
            dst["zero_hits"] += stats.get("zero_hits", 0)
            dst["resp_bytes"] += stats.get("resp_bytes", 0)
            dst["items_returned"] += stats.get("items_returned", 0)
        for project, stats in side.get("per_project", {}).items():
            dst = out["per_project"].setdefault(
                project, {"calls": 0, "resp_bytes": 0, "items_returned": 0, "server_processes": 0})
            dst["calls"] += stats.get("calls", 0)
            dst["resp_bytes"] += stats.get("resp_bytes", 0)
            dst["items_returned"] += stats.get("items_returned", 0)
            dst["server_processes"] += stats.get("server_processes", 0)
    return _finalize_rates(out)


# ─── Rollup / compaction ───────────────────────────────────────────────────

def _empty_rollup() -> dict[str, Any]:
    return {**_empty_totals(), "folded_files": []}


def load_rollup(content_root: Path) -> dict[str, Any]:
    """The kept-forever numeric totals, plus ``folded_files`` — the basenames
    already accounted for in those totals, so live aggregation can skip them
    even if their raw file wasn't deleted."""
    p = usage_dir(content_root) / ROLLUP_NAME
    if not p.exists():
        return _empty_rollup()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _empty_rollup()
    if not isinstance(data, dict):
        return _empty_rollup()
    # Merge onto an empty base so any missing keys are filled in; carry the
    # folded-file ledger through separately (merge_aggregates only sums the
    # numeric totals).
    out = merge_aggregates(_empty_totals(), data)
    out["folded_files"] = [
        str(x) for x in data.get("folded_files", []) if isinstance(x, str)]
    return out


def save_rollup(content_root: Path, data: dict[str, Any]) -> None:
    """Persist the rollup atomically (temp file + ``os.replace``) so a crash
    or full disk can never leave a truncated ``rollup.json`` — the totals it
    holds are the only durable record of already-deleted raw logs."""
    d = usage_dir(content_root)
    d.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    fd, tmp = tempfile.mkstemp(dir=str(d), prefix=".rollup-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
        os.replace(tmp, d / ROLLUP_NAME)
    finally:
        try:
            if os.path.exists(tmp):
                os.unlink(tmp)
        except OSError:
            pass


def _latest_record_month(path: Path) -> str | None:
    """The ``YYYY-MM`` of the newest record in a file, or ``None`` if it has
    no timestamped records. Eligibility keys off this — the *data*, not the
    filename — so a long-lived server whose file is named last month but is
    still receiving calls this month is never folded out from under it."""
    latest: str | None = None
    for rec in iter_records_file(path):
        ts = rec.get("ts")
        if isinstance(ts, str) and len(ts) >= 7 and ts[4] == "-":
            month = ts[:7]
            if latest is None or month > latest:
                latest = month
    return latest


def compact(content_root: Path, *, now_month: str | None = None) -> dict[str, Any]:
    """Fold every raw file whose newest record is in a *past* month into the
    kept-forever rollup, then best-effort delete it.

    Correctness does not depend on the delete succeeding: a folded file's
    basename is recorded in ``folded_files`` and the rollup is saved
    atomically *before* any unlink, so an interrupted or failed deletion
    can neither lose totals (they're already durable) nor double-count them
    (``folded_files`` excludes the file from live aggregation). Files with a
    current-month record are left untouched — they may still be open for
    append by a live server.
    """
    month = now_month or datetime.now(timezone.utc).strftime("%Y-%m")
    d = usage_dir(content_root)
    rollup = load_rollup(content_root)
    if not d.exists():
        return rollup

    folded: set[str] = set(rollup.get("folded_files", []))
    newly_folded = False
    to_delete: list[Path] = []
    for p in sorted(d.glob("mcp-*.jsonl")):
        if p.name in folded:
            to_delete.append(p)  # already counted; just needs cleanup
            continue
        latest = _latest_record_month(p)
        if latest is None or latest >= month:
            continue  # active this month (or empty/unparseable) → leave alone
        rollup = merge_aggregates(rollup, aggregate(iter_records_file(p)))
        folded.add(p.name)
        rollup["folded_files"] = sorted(folded)
        to_delete.append(p)
        newly_folded = True

    if newly_folded:
        save_rollup(content_root, rollup)  # durable BEFORE any unlink
    for p in to_delete:
        try:
            p.unlink()
        except OSError:
            pass  # correctness holds via folded_files even if this fails
    return rollup


def combined_totals(content_root: Path) -> dict[str, Any]:
    """Lifetime view: kept-forever rollup + live logs not yet folded into it.

    Folded files are excluded from the live side so each record is counted
    exactly once even when a raw file survived a failed deletion."""
    rollup = load_rollup(content_root)
    folded = set(rollup.get("folded_files", []))
    d = usage_dir(content_root)
    live_records: list[dict[str, Any]] = []
    if d.exists():
        for p in sorted(d.glob("mcp-*.jsonl")):
            if p.name in folded:
                continue
            live_records.extend(iter_records_file(p))
    return merge_aggregates(rollup, aggregate(live_records))
