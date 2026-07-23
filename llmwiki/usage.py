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
from typing import Any, Iterable, Iterator, Mapping
from urllib.parse import unquote, urlparse

from llmwiki.slugs import project_slug_from_abs_path, project_slug_from_encoded_dir

USAGE_DIRNAME = "usage"
ROLLUP_NAME = "rollup.json"

# ─── Caller attribution (#51) ─────────────────────────────────────────────
# The bucket a call lands in when nothing caller-scoped was available. It is
# never rendered as a project — see build.render_mcp_heaviest_card.
UNATTRIBUTED = "unknown"
# Where a record's attribution came from. Records written before #51 carry no
# source at all and are folded into UNATTRIBUTED at aggregation time: their
# project name is the server's own cwd, not the caller's.
CALLER_PROJECT_DIR = "project-dir-env"
CALLER_CLIENT_ROOT = "client-root"
CALLER_PATH = "path"
CALLER_UNATTRIBUTED = "unattributed"
_TRUSTED_CALLER_SOURCES = frozenset(
    {CALLER_PROJECT_DIR, CALLER_CLIENT_ROOT, CALLER_PATH})
# Env vars an agentic client auto-injects with the caller's workspace path.
# CLAUDE_PROJECT_DIR is set by Claude Code (>= v2.1.139) into every stdio MCP
# server — zero user config, and since Claude Code spawns one server per
# session, it is a stable per-caller signal for that server's whole life.
_PROJECT_DIR_ENV_KEYS = ("CLAUDE_PROJECT_DIR",)
# Bumped when the meaning of an aggregate's project labels changes; a rollup
# without it predates per-call attribution and cannot be trusted.
ATTRIBUTION_VERSION = 1

# Tool arguments that may carry the caller's own working directory.
_CALLER_PATH_KEYS = ("path",)
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


def project_from_client_root(root: str) -> str | None:
    """Project slug for one MCP root (``file:///home/dev/code/my-app``).

    The client reports its own workspace directory, so the path is the
    caller's project by construction. Derived through the shared
    ``project_slug_from_abs_path`` so it matches the slug the ingestion
    adapter assigns the same project (#36) — not the bare basename, which
    diverges for single-word project names."""
    if not isinstance(root, str) or not root.strip():
        return None
    text = root.strip()
    if "://" in text:
        parsed = urlparse(text)
        if parsed.scheme not in ("file", ""):
            return None  # a non-filesystem root tells us nothing about a project
        text = unquote(parsed.path)
    return project_slug_from_abs_path(text) or None


def project_from_path(value: str, content_root: Path | None) -> str | None:
    """Project slug for a path argument, or ``None`` when the path says
    nothing about *who called*.

    Only paths that carry the caller's own working directory count. Agent
    tooling encodes that directory into a single path segment
    (``/tmp/…/-home-dev-code-my-app/<session>/scratchpad/note.md``,
    ``~/.claude/projects/-home-dev-code-my-app/<session>.jsonl``), which is
    the signal read here.

    A path *inside* the wiki — ``wiki/sources/my-app/…`` — names the
    **subject** of a call, not its caller. Attributing on subject would make
    every retrieval look same-project and erase exactly the cross-project
    signal this telemetry exists to measure, so those return ``None``."""
    if not isinstance(value, str) or not value.strip():
        return None
    p = Path(value.strip()).expanduser()
    if not p.is_absolute():
        return None  # relative → resolved against the wiki, i.e. subject
    if content_root is not None:
        try:
            if p.resolve().is_relative_to(Path(content_root).resolve()):
                return None
        except OSError:
            return None
    for part in p.parts:
        if _looks_cwd_encoded(part):
            return project_slug_from_encoded_dir(part) or None
    return None


def _looks_cwd_encoded(segment: str) -> bool:
    """A cwd flattened into one segment: leading separator-turned-hyphen plus
    at least a couple more path components (``-home-dev-code-my-app``)."""
    return segment.startswith("-") and segment.count("-") >= 3


def resolve_caller(
    args: dict[str, Any],
    *,
    client_roots: Iterable[str] = (),
    env: Mapping[str, str] | None = None,
    content_root: Path | None = None,
) -> tuple[str, str]:
    """Resolve ``(project, source)`` for one tool call, best signal first.

    1. **Auto-injected workspace env** — the path a client sets into the
       server's environment (``CLAUDE_PROJECT_DIR``). Zero user config, no
       round-trip, and — because such clients spawn one server per session —
       a stable per-caller signal available at the very first call.
    2. **MCP roots** — the client's own workspace directories, obtained via a
       ``roots/list`` request; the standard fallback for compliant clients.
       A client reporting several roots is attributed to the first.
    3. **A cwd-encoded path argument** — a per-call hint for clients that
       offer neither of the above.
    4. **Nothing** — ``("unknown", "unattributed")``.

    The server's own ``os.getcwd()`` is deliberately absent: a client may
    launch the server anywhere (Claude Code's desktop app uses ``$HOME``, and
    a fixed-dir install uses that dir), so it is unrelated to the caller's
    project — stamping its name on a record publishes a guess as a fact
    (#51). ``env`` defaults to ``os.environ``; read per call so nothing is
    frozen at construction."""
    environ = os.environ if env is None else env
    for key in _PROJECT_DIR_ENV_KEYS:
        value = environ.get(key)
        if isinstance(value, str) and value.strip():
            name = project_slug_from_abs_path(value.strip())
            if name:
                return name, CALLER_PROJECT_DIR
    for root in client_roots:
        name = project_from_client_root(root)
        if name:
            return name, CALLER_CLIENT_ROOT
    for key in _CALLER_PATH_KEYS:
        name = project_from_path(args.get(key), content_root)  # type: ignore[arg-type]
        if name:
            return name, CALLER_PATH
    return UNATTRIBUTED, CALLER_UNATTRIBUTED


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
        pid: int | None = None,
        started: str | None = None,
    ) -> None:
        self.dir = usage_dir(content_root)
        self.pid = pid if pid is not None else os.getpid()
        self.started = started or _iso_now()
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
        caller_project: str | None = None,
        caller_source: str | None = None,
    ) -> None:
        """Append one call. Attribution is a *per-call* argument: one process
        serves many sessions over its lifetime, so a value fixed at
        construction cannot tell them apart (#51)."""
        record = {
            "ts": ts or _iso_now(),
            "tool": tool,
            "query": query,
            "hits": hits,
            "resp_bytes": int(resp_bytes),
            "duration_ms": int(duration_ms),
            "caller_project": caller_project or UNATTRIBUTED,
            "caller_source": caller_source or CALLER_UNATTRIBUTED,
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
        "per_project_tool": {},
    }


def _finalize_rates(totals: dict[str, Any]) -> dict[str, Any]:
    for stats in totals["per_tool"].values():
        calls = stats["calls"]
        stats["zero_hit_rate"] = (stats["zero_hits"] / calls) if calls else 0.0
    return totals


def attributed_project(record: dict[str, Any]) -> str:
    """The project a record may be counted against.

    A record only keeps its ``caller_project`` when it also says where that
    name came from and the source is caller-scoped. Records written before
    #51 carry no ``caller_source``: their project name is the server
    process's own working directory, so counting them under it would
    republish the bug's output as fact."""
    if record.get("caller_source") in _TRUSTED_CALLER_SOURCES:
        return str(record.get("caller_project") or UNATTRIBUTED)
    return UNATTRIBUTED


def aggregate(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Fold raw records into totals: calls + bytes + zero-hit counts per
    tool and per attributed caller project.

    ``hits == 0`` is the signal that matters — a zero-hit call is a
    knowledge gap or noise (raw material for ``/wiki-reflect``). A missing
    ``hits`` (the tool couldn't report a count) is *unknown*, not a miss,
    so it is never counted as zero-hit.
    """
    totals = _empty_totals()
    proc_sets: dict[str, set] = {}
    for r in records:
        tool = r.get("tool") or "unknown"
        project = attributed_project(r)
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

        pt = totals["per_project_tool"].setdefault(project, {}).setdefault(
            tool, {"calls": 0, "items_returned": 0})
        pt["calls"] += 1
        if tool in ENTITY_TOOLS and isinstance(hits, int) and hits > 0:
            pt["items_returned"] += hits

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
        for project, tools in side.get("per_project_tool", {}).items():
            dproj = out["per_project_tool"].setdefault(project, {})
            for tool, stats in tools.items():
                dt = dproj.setdefault(tool, {"calls": 0, "items_returned": 0})
                dt["calls"] += stats.get("calls", 0)
                dt["items_returned"] += stats.get("items_returned", 0)
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
    version = data.get("attribution_version")
    if not isinstance(version, int) or version < ATTRIBUTION_VERSION:
        # Compaction deletes the raw records, so this rollup is the only
        # surviving copy of totals that were mis-attributed when written —
        # the labels can't be recomputed, only retracted (#51).
        _collapse_to_unattributed(out)
    out["attribution_version"] = ATTRIBUTION_VERSION
    return out


def _collapse_to_unattributed(totals: dict[str, Any]) -> None:
    """Relabel every per-project total as unattributed, in place. Call counts
    and item counts are unaffected — only the project they were filed under."""
    if totals["per_project"]:
        merged = {"calls": 0, "resp_bytes": 0, "items_returned": 0,
                  "server_processes": 0}
        for stats in totals["per_project"].values():
            for key in merged:
                merged[key] += int(stats.get(key, 0) or 0)
        totals["per_project"] = {UNATTRIBUTED: merged}
    if totals["per_project_tool"]:
        merged_tools: dict[str, dict[str, int]] = {}
        for tools in totals["per_project_tool"].values():
            for tool, stats in tools.items():
                dst = merged_tools.setdefault(
                    tool, {"calls": 0, "items_returned": 0})
                dst["calls"] += int(stats.get("calls", 0) or 0)
                dst["items_returned"] += int(stats.get("items_returned", 0) or 0)
        totals["per_project_tool"] = {UNATTRIBUTED: merged_tools}


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
        # merge_aggregates only carries numeric totals; re-stamp the label
        # semantics so the next load doesn't re-collapse already-clean data.
        rollup["attribution_version"] = ATTRIBUTION_VERSION
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
