"""Latest outcome of each pipeline part, for the Home problems banner (#374).

Every part of a run — ``sync``, ``synth``, ``build``, and ``run`` for a run
that failed as a whole — keeps at most one entry in the vault state's
``outcomes.parts``: its latest failure. A clean finish of that part deletes
the entry. Each write goes through :func:`llmwiki.state_store.update_state`
(which rewrites ``llmwiki-state.js``) and is then copied into ``site/``, so a
browser refresh shows it without a rebuild — the route lint notes take.

Summary strings are built only here, so the banner, tests and docs agree on
the wording.
"""

from __future__ import annotations

import os
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from llmwiki import quarantine
from llmwiki.automation_status import load_status, vault_automation_log_path
from llmwiki.state_store import (
    copy_state_sidecar_to_site,
    read_state,
    resolve_state_file,
    update_state,
)
from llmwiki.synth.base import BaseSynthesizer, backend_unavailable_message

#: Parts a run records; the banner shows them in this order after Schedule.
PARTS = ("sync", "synth", "build", "run")

#: Stored detail is capped: the whole state is inlined into the site sidecar.
DETAIL_MAX_CHARS = 8192

#: Set by the scheduled job's wrapper so a run knows it is the scheduled one.
SCHEDULED_ENV = "LLMWIKI_SCHEDULED_RUN"

#: Slack after one schedule interval before Home calls the scheduled run overdue.
SCHEDULE_GRACE_S = 2 * 3600

#: Bumped when the wrapper's contract with this module changes; a schedule
#: recorded without it predates run stamping and must be reinstalled.
SCHEDULE_MARKER = 1


@dataclass(frozen=True)
class Failure:
    """One part's failure: ``entire`` (it could not do its job) or ``partial``."""

    scope: str
    summary: str
    detail: str = ""
    done: int | None = None
    total: int | None = None
    items: tuple[str, ...] = field(default_factory=tuple)


def is_scheduled_run() -> bool:
    """True inside a run started by the installed schedule's wrapper."""
    return os.environ.get(SCHEDULED_ENV) == "1"


def utc_now() -> str:
    """Now as the ISO-8601 UTC second the state store and quarantine use."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _log_path(state_file: Path) -> str:
    """The scheduled job's log for this vault; manual runs log to the terminal."""
    if not is_scheduled_run():
        return ""
    return str(vault_automation_log_path(state_file.parent))


def _clip(text: str) -> str:
    text = text.strip()
    if len(text) <= DETAIL_MAX_CHARS:
        return text
    return text[:DETAIL_MAX_CHARS].rstrip() + "\n…"


def record_failure(
    part: str,
    failure: Failure,
    *,
    state_file: Path | None = None,
    site_dir: Path | None = None,
    when: str | None = None,
) -> None:
    """Store ``failure`` as ``part``'s latest outcome and refresh the site sidecar."""
    target = resolve_state_file(state_file)
    entry: dict[str, Any] = {
        "scope": failure.scope,
        "summary": failure.summary,
        "detail": _clip(failure.detail),
        "at": when or utc_now(),
        "log_path": _log_path(target),
        "done": failure.done,
        "total": failure.total,
        "items": list(failure.items),
    }

    def _mut(state: dict[str, Any]) -> dict[str, Any]:
        state.setdefault("outcomes", {}).setdefault("parts", {})[part] = entry
        return state

    update_state(_mut, target)
    copy_state_sidecar_to_site(target.parent, site_dir=site_dir)


def record_clean(
    part: str,
    *,
    state_file: Path | None = None,
    site_dir: Path | None = None,
) -> None:
    """Drop ``part``'s failure entry after a clean finish; no write when there is none."""
    target = resolve_state_file(state_file)
    if part not in read_state(target).get("outcomes", {}).get("parts", {}):
        return

    def _mut(state: dict[str, Any]) -> dict[str, Any]:
        state.get("outcomes", {}).get("parts", {}).pop(part, None)
        return state

    update_state(_mut, target)
    copy_state_sidecar_to_site(target.parent, site_dir=site_dir)


def record(
    part: str,
    failure: Failure | None,
    *,
    state_file: Path | None = None,
    site_dir: Path | None = None,
) -> bool:
    """``record_failure`` when ``failure`` is set, else ``record_clean``; True when it failed."""
    if failure is None:
        record_clean(part, state_file=state_file, site_dir=site_dir)
        return False
    record_failure(part, failure, state_file=state_file, site_dir=site_dir)
    return True


def _first_lines(lines: Iterable[str], limit: int = 20) -> str:
    out = [line for line in lines if line.strip()]
    if len(out) > limit:
        out = out[:limit] + [f"… and {len(out) - limit} more"]
    return "\n".join(out)


def synth_unavailable(backend: BaseSynthesizer) -> Failure:
    """Synth could not run because its backend program or server is missing."""
    return Failure(
        scope="entire",
        summary=f"did not run: backend {backend.name} is not available",
        detail=backend_unavailable_message(backend),
    )


def synth_failure(summary: Mapping[str, Any]) -> Failure | None:
    """Classify a ``synthesize_new_sessions`` summary; ``None`` when it was clean.

    A usage-limit or Ctrl+C stop, or any source that failed, is a partial
    failure that says how many sources landed out of how many were queued.
    """
    errors = [str(e) for e in summary.get("errors") or []]
    done = int(summary.get("synthesized") or 0)
    total = done + len(errors) + int(summary.get("deferred") or 0)
    names = tuple(e.split(":", 1)[0].strip() for e in errors)
    if summary.get("usage_limit") is not None:
        reset = (summary.get("usage_limit") or {}).get("reset")
        lead = f"the provider's usage limit resets {reset}" if reset else ""
        return Failure(
            scope="partial",
            summary=f"stopped at the AI provider's usage limit after {done} of {total} sources",
            detail=_first_lines([lead, *errors]),
            done=done, total=total, items=names,
        )
    if summary.get("interrupted"):
        return Failure(
            scope="partial",
            summary=f"interrupted after {done} of {total} sources",
            detail=_first_lines(errors),
            done=done, total=total, items=names,
        )
    if errors:
        return Failure(
            scope="partial",
            summary=f"{len(errors)} of {total} sources failed",
            detail=_first_lines(errors),
            done=done, total=total, items=names,
        )
    return None


def harvest_failure(rc: int) -> Failure:
    """The candidate harvest that ends a synth run exited non-zero."""
    return Failure(
        scope="entire",
        summary=f"candidate harvest failed (exit {rc})",
        detail="Sources were written; harvesting candidate pages from them failed. "
        "Re-run `llmwiki synth --candidates-only` to see the error.",
    )


def sync_failure(rc: int, *, state_file: Path, started_at: str) -> Failure | None:
    """Classify a ``convert_all`` run; ``None`` when every session source converted.

    When this run saved its per-adapter counters (``sync.meta.last_sync`` is
    not older than ``started_at``; ``save_sync_meta`` replaces them each run),
    the ``errored`` counts decide: per-file errors are a partial failure,
    whatever ``--fail-on-errors`` made of the exit code. Without fresh
    counters a non-zero ``rc`` means sync could not start (bad adapter
    selection, no stores).
    """
    sync = read_state(state_file).get("sync", {})
    fresh = str(sync.get("meta", {}).get("last_sync") or "") >= started_at
    if not fresh:
        if rc == 0:
            return None
        return Failure(
            scope="entire",
            summary=f"did not run (exit {rc})",
            detail="Sync could not start: check the adapter selection and that at "
            "least one session store exists. The full message is in the run's output.",
        )
    counters = sync.get("counters", {})
    adapters = sorted(name for name, c in counters.items() if isinstance(c, dict))
    failed = [name for name in adapters if int(counters[name].get("errored") or 0) > 0]
    if not failed:
        return None
    rows = [
        e for e in quarantine.load(state_file)
        if e.adapter in failed and e.last_seen >= started_at
    ]
    files = sum(int(counters[name].get("errored") or 0) for name in failed)
    return Failure(
        scope="partial",
        summary=f"{len(failed)} of {len(adapters)} session sources failed ({', '.join(failed)})",
        detail=_first_lines(
            [f"{files} file(s) could not be converted."]
            + [f"{e.adapter}: {e.source}: {e.error}" for e in rows]
        ),
        done=len(adapters) - len(failed),
        total=len(adapters),
        items=tuple(failed),
    )


def build_failure(rc: int) -> Failure | None:
    """``build_site`` returned ``rc``; ``None`` when it was 0."""
    if rc == 0:
        return None
    return Failure(
        scope="entire",
        summary=f"failed (exit {rc})",
        detail="The site was not rebuilt. The full message is in the run's output.",
    )


def _exception_line(exc: BaseException) -> str:
    text = str(exc).strip()
    return f"{type(exc).__name__}: {text}" if text else type(exc).__name__


def build_crashed(exc: BaseException) -> Failure:
    """``build_site`` raised; the site was left as the previous build made it."""
    return Failure(scope="entire", summary="failed", detail=_exception_line(exc))


def run_crashed(exc: BaseException) -> Failure:
    """The run stopped on an exception no part caught (lock timeout, config error, …)."""
    return Failure(
        scope="entire",
        summary="run failed: it stopped on an unexpected error",
        detail=_exception_line(exc),
    )


def run_failure(rc: int, unexplained: list[str], *, explained: bool) -> Failure | None:
    """A run-level entry for a non-zero ``rc`` nothing else on Home explains.

    ``unexplained`` lists causes no part records (graph step, lint that could
    not run, a build into a custom ``--out``). ``explained`` is True when a
    Sync / Synth / Build entry or the lint policy already accounts for the
    exit code. With neither, the run still gets an entry: it failed, and the
    banner must say so.
    """
    if rc == 0 or (explained and not unexplained):
        return None
    return Failure(
        scope="entire",
        summary=f"run failed (exit {rc})",
        detail=_first_lines(unexplained) or "No step reported an error; see the run's output.",
    )


# ─── The scheduled job ────────────────────────────────────────────────────


def schedule_installed(status: Mapping[str, Any] | None) -> bool:
    """True when ``automation-status.json`` records an activated schedule."""
    return bool(status) and status.get("scheduler_activated") is True


def configure_schedule(
    *,
    interval_s: int,
    installed_at: str,
    log_path: str,
    state_file: Path | None = None,
    site_dir: Path | None = None,
    grace_s: int = SCHEDULE_GRACE_S,
) -> None:
    """Record the installed schedule so Home can tell when its run is overdue.

    Written by ``install-automation`` after the scheduler accepted the job.
    Keeps the last run stamp of an earlier install and clears the
    "setup outdated" entry this install resolves.
    """
    target = resolve_state_file(state_file)

    def _mut(state: dict[str, Any]) -> dict[str, Any]:
        outcomes = state.setdefault("outcomes", {})
        previous = outcomes.get("scheduled") or {}
        outcomes["scheduled"] = {
            "marker": SCHEDULE_MARKER,
            "interval_s": int(interval_s),
            "grace_s": int(grace_s),
            "installed_at": installed_at,
            "log_path": log_path,
            "last_run_at": previous.get("last_run_at"),
            "exit_code": previous.get("exit_code"),
        }
        outcomes.pop("setup_outdated", None)
        return state

    update_state(_mut, target)
    copy_state_sidecar_to_site(target.parent, site_dir=site_dir)


def clear_schedule(*, state_file: Path | None = None, site_dir: Path | None = None) -> None:
    """Forget the schedule: with no job installed, Home shows no Schedule entry."""
    target = resolve_state_file(state_file)
    outcomes = read_state(target).get("outcomes", {})
    if "scheduled" not in outcomes and "setup_outdated" not in outcomes:
        return

    def _mut(state: dict[str, Any]) -> dict[str, Any]:
        state.get("outcomes", {}).pop("scheduled", None)
        state.get("outcomes", {}).pop("setup_outdated", None)
        return state

    update_state(_mut, target)
    copy_state_sidecar_to_site(target.parent, site_dir=site_dir)


def stamp_scheduled_run(
    *,
    exit_code: int,
    state_file: Path | None = None,
    site_dir: Path | None = None,
    when: str | None = None,
) -> None:
    """Record the end of a scheduled run: its time and exit code, together.

    Called once, as the run finishes. A run killed before this keeps the
    previous stamp, so Home reports it as overdue instead of looking fresh.
    """
    target = resolve_state_file(state_file)
    stamp = when or utc_now()

    def _mut(state: dict[str, Any]) -> dict[str, Any]:
        scheduled = state.setdefault("outcomes", {}).setdefault("scheduled", {})
        scheduled["last_run_at"] = stamp
        scheduled["exit_code"] = int(exit_code)
        return state

    update_state(_mut, target)
    copy_state_sidecar_to_site(target.parent, site_dir=site_dir)


def check_schedule_setup(
    vault_root: Path,
    *,
    state_file: Path | None = None,
    site_dir: Path | None = None,
) -> None:
    """Flag a schedule installed before run stamping; forget one that was removed.

    An activated schedule whose state lacks :data:`SCHEDULE_MARKER` runs a
    wrapper that never stamps its runs, so Home could not notice it stopping:
    record "setup outdated" until ``install-automation`` is re-run. With no
    activated schedule, drop the schedule records so no Schedule entry shows.
    """
    target = resolve_state_file(state_file)
    if not schedule_installed(load_status(vault_root)):
        clear_schedule(state_file=target, site_dir=site_dir)
        return
    outcomes = read_state(target).get("outcomes", {})
    if (outcomes.get("scheduled") or {}).get("marker") == SCHEDULE_MARKER:
        return
    if "setup_outdated" in outcomes:
        return
    note = {
        "at": utc_now(),
        "detail": "This vault's scheduled job was installed by an older llmwiki that "
        "does not record its runs, so a missed run would go unnoticed. Re-run "
        "`llmwiki install-automation` once to update it.",
    }

    def _mut(state: dict[str, Any]) -> dict[str, Any]:
        state.setdefault("outcomes", {})["setup_outdated"] = note
        return state

    update_state(_mut, target)
    copy_state_sidecar_to_site(target.parent, site_dir=site_dir)
