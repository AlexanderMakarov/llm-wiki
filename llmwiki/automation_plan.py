"""Vocabulary for what the scheduled daily job does (stdlib only).

An :class:`AutomationPlan` answers three questions — which job runs, whether the
knowledge graph is built and by which engine, and whether quality findings fail
the run. Everything else derives from it: the shell command the scheduled
wrapper executes, the human label shown by the wizard and the built site, and
the keys written to ``.llmwiki/automation-status.json``.

This module deliberately imports nothing from the rest of ``llmwiki`` so that
``build.py`` can render a label without pulling in the installer.
"""

from __future__ import annotations

import shlex
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Literal, get_args

__all__ = [
    "DEFAULT_SCHEDULE",
    "LEGACY_PROFILE_MAP",
    "AutomationPlan",
    "GraphChoice",
    "Job",
    "LintFail",
    "plan_command",
    "plan_from_status",
    "plan_label",
    "plan_to_status",
    "schedule_from_status",
    "spends_tokens",
]

Job = Literal["ingest", "maintain"]
GraphChoice = Literal["none", "builtin", "graphify"]
LintFail = Literal["never", "errors", "warnings"]

_JOBS: frozenset[str] = frozenset(get_args(Job))
_GRAPH_CHOICES: frozenset[str] = frozenset(get_args(GraphChoice))
_LINT_FAILS: frozenset[str] = frozenset(get_args(LintFail))

#: Cron expression used when a status file carries no schedule at all.
DEFAULT_SCHEDULE = "0 8 * * *"

_GRAPH_LABELS: dict[GraphChoice, str] = {
    "builtin": "built-in",
    "graphify": "graphify",
}


@dataclass(frozen=True, slots=True)
class AutomationPlan:
    """What the scheduled daily job does.

    ``graph`` and ``lint_fail`` describe the maintain job. Any other job runs a
    plain ``sync``, so construction normalises both back to their defaults —
    a plan never carries an extra its job cannot run.
    """

    job: Job = "ingest"
    graph: GraphChoice = "none"
    lint_fail: LintFail = "never"

    def __post_init__(self) -> None:
        """Normalise extras onto the job that can run them.

        Only maintain builds a graph or lints, so any other job resolves to
        ``graph="none"`` / ``lint_fail="never"``. Every derived rendering — the
        command, the label, the status file, the site panel — then describes the
        same job. The CLI tells the user which flag it dropped and why.
        """
        if self.job != "maintain":
            object.__setattr__(self, "graph", "none")
            object.__setattr__(self, "lint_fail", "never")


#: The wizard letters accepted before plans existed. ``B`` and ``C`` both land on
#: maintain: the only thing ``C`` did differently was hardcode ``--skip-graph``,
#: which is the ``graph="none"`` default. Every letter-to-plan translation —
#: ``--profile``, wizard input, status back-compat — goes through this map.
LEGACY_PROFILE_MAP: dict[str, AutomationPlan] = {
    "A": AutomationPlan(job="ingest"),
    "B": AutomationPlan(job="maintain"),
    "C": AutomationPlan(job="maintain"),
}


def plan_command(
    plan: AutomationPlan,
    *,
    python_bin: str,
    working_dir: Path | str,
    vault: Path | str | None = None,
) -> str:
    """Compose the shell command line the scheduled wrapper runs.

    The line changes directory into ``working_dir`` first, so the command works
    from whatever cwd the scheduler happens to use. Flag order is fixed, which
    lets callers and tests compare the result as an exact string.

    ``vault`` names the vault the scheduled run must operate on, appended as a
    trailing ``--vault``. Pass it only when the job targets a vault other than
    the one ``vault.default_path`` resolves to; leaving it ``None`` emits the
    command unchanged and lets the run read its vault from config.
    """
    py = shlex.quote(python_bin)
    root = shlex.quote(str(working_dir))
    prefix = f"cd {root} && {py} -m llmwiki"
    suffix = f" --vault {shlex.quote(str(vault))}" if vault is not None else ""
    if plan.job != "maintain":
        return f"{prefix} sync{suffix}"
    parts = [f"{prefix} all"]
    if plan.graph == "none":
        parts.append("--skip-graph")
    else:
        parts.append(f"--graph-engine {plan.graph}")
    if plan.lint_fail != "never":
        parts.append(f"--lint-fail {plan.lint_fail}")
    return " ".join(parts) + suffix


def plan_label(plan: AutomationPlan) -> str:
    """Human name for a plan, e.g. ``Maintain + graph (built-in)``.

    Never returns a bare profile letter — this is the wording the wizard
    summary, the site Home panel, and the status file's ``label`` key all share.
    """
    if plan.job != "maintain":
        return "Ingest only"
    label = "Maintain"
    graph_name = _GRAPH_LABELS.get(plan.graph)
    if graph_name:
        label += f" + graph ({graph_name})"
    if plan.lint_fail != "never":
        label += f" + fail on {plan.lint_fail}"
    return label


def spends_tokens(plan: AutomationPlan) -> bool:
    """Whether the job can call a synthesis backend and so cost money."""
    return plan.job == "maintain"


def plan_to_status(plan: AutomationPlan) -> dict[str, Any]:
    """Status-file keys describing a plan.

    Carries the legacy ``profile`` letter alongside the named keys so an older
    llmwiki reading a newer status file still recognises the job.
    """
    return {
        "job": plan.job,
        "graph": plan.graph,
        "lint_fail": plan.lint_fail,
        "label": plan_label(plan),
        "profile": "B" if plan.job == "maintain" else "A",
    }


def plan_from_status(status: Any) -> AutomationPlan:
    """Read a plan back out of a status dict, never raising.

    Resolution order: the named ``job`` key (with ``graph`` / ``lint_fail``),
    then the legacy ``profile`` letter through :data:`LEGACY_PROFILE_MAP`, then
    the default ingest plan. A site build calls this, so a malformed or
    truncated status file degrades to the default instead of failing the build.
    """
    if not isinstance(status, dict):
        return AutomationPlan()
    job = status.get("job")
    if isinstance(job, str) and job in _JOBS:
        graph = status.get("graph")
        lint_fail = status.get("lint_fail")
        return AutomationPlan(
            job=job,  # type: ignore[arg-type]
            graph=graph if isinstance(graph, str) and graph in _GRAPH_CHOICES else "none",  # type: ignore[arg-type]
            lint_fail=lint_fail if isinstance(lint_fail, str) and lint_fail in _LINT_FAILS else "never",  # type: ignore[arg-type]
        )
    profile = status.get("profile")
    if isinstance(profile, str):
        legacy = LEGACY_PROFILE_MAP.get(profile.strip().upper())
        if legacy is not None:
            return replace(legacy)
    return AutomationPlan()


def schedule_from_status(status: Any) -> str:
    """Read the cron expression out of a status dict, never raising.

    Uses the ``schedule`` key when present, otherwise synthesises
    ``"{minute} {hour} * * *"`` from the legacy integer ``hour`` / ``minute``
    keys, otherwise :data:`DEFAULT_SCHEDULE`. Callers read schedules through
    this helper rather than inspecting raw status keys themselves.
    """
    if not isinstance(status, dict):
        return DEFAULT_SCHEDULE
    schedule = status.get("schedule")
    if isinstance(schedule, str) and schedule.strip():
        return schedule.strip()
    hour = _clamped_int(status.get("hour"), high=23, default=8)
    minute = _clamped_int(status.get("minute"), high=59, default=0)
    return f"{minute} {hour} * * *"


def _clamped_int(value: Any, *, high: int, default: int) -> int:
    """Coerce a legacy status integer into range, falling back to ``default``."""
    if isinstance(value, bool) or not isinstance(value, int):
        return default
    return value if 0 <= value <= high else default
