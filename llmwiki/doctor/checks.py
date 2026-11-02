"""Live detectors for doctor areas A–O (Slices 3–4).

Detectors emit findings keyed by stable catalog ``id`` — no free-text
guessing. Area I/J lint findings come from :mod:`llmwiki.doctor.lint_fold`
(provenance via lint fold is enough for J). G/H emit only when overdue.
"""

from __future__ import annotations

import platform
import re
import shlex
import sys
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from importlib.util import find_spec
from pathlib import Path
from typing import Any

from llmwiki import __version__, automation_units
from llmwiki.adapters import discover_all, get_available
from llmwiki.automation_plan import schedule_from_status
from llmwiki.automation_status import default_log_path, load_status, vault_automation_log_path
from llmwiki.automation_units import (
    LEGACY_SYSTEMD,
    DiscoveryResult,
    InstalledUnit,
    legacy_unit_serving,
    removal_steps,
    serves_vault,
    unit_for_vault,
)
from llmwiki.candidates import DEFAULT_STALE_DAYS, list_candidates, stale_candidates
from llmwiki.config_schedule import _load_sessions_config
from llmwiki.cron_spec import CronError, cron_interval, parse_cron
from llmwiki.doctor.kb import finding_from_entry, get_entry, load_heal_kb
from llmwiki.doctor.models import Finding
from llmwiki.doctor.runners import install_automation_argv
from llmwiki.install_agent_kit import MANIFEST_NAME, read_manifest
from llmwiki.install_hint import detect_env, install_hint
from llmwiki.migrate_page_kinds import REMOVED_FOLDERS, REMOVED_KINDS, page_kind
from llmwiki.run_outcomes import SCHEDULED_ENV
from llmwiki.state_store import read_state, resolve_state_file
from llmwiki.synth.base import DummySynthesizer, backend_unavailable_message
from llmwiki.synth.pipeline import resolve_backend

#: Catalog ids that detectors in this module may emit (drift test target).
DETECTOR_IDS_A_TO_F: frozenset[str] = frozenset(
    {
        "env.no_package_installer",
        "env.uv_venv_without_uv",
        "env.extra_graph_missing",
        "env.extra_add_missing",
        "adapters.none_available",
        "synth.backend_dummy",
        "synth.backend_unavailable",
    }
)

#: Slice 4 detector ids (G/H/K–O; J comes from lint fold).
DETECTOR_IDS_G_TO_O: frozenset[str] = frozenset(
    {
        "pipeline.backlog_overdue",
        "candidates.review_pending",
        "migrate.schema_drift",
        "automation.unit_missing",
        "automation.points_elsewhere",
        "automation.checkout_missing",
        "automation.check_unavailable",
        "automation.not_active",
        "automation.stale_run",
        "automation.last_run_failed",
        "automation.duplicate_legacy",
        "automation.orphan_unit",
        "automation.setup_outdated",
        "automation.interpreter_missing",
        "automation.program_dir_missing",
        "build.site_stale",
        "agent_kit.outdated",
        "privacy.draft_redaction",
    }
)

DETECTOR_IDS: frozenset[str] = DETECTOR_IDS_A_TO_F | DETECTOR_IDS_G_TO_O

#: Raw/synth backlog is "overdue" after this many days pending.
PIPELINE_OVERDUE_DAYS = 7

#: Candidate review overdue threshold (reuse candidates stale default).
CANDIDATE_OVERDUE_DAYS = DEFAULT_STALE_DAYS


def _finding(entry_id: str, *, message: str | None = None) -> Finding | None:
    entry = get_entry(entry_id)
    if entry is None:
        return None
    return finding_from_entry(entry, message=message)


def collect_env_summary(
    vault: Path | None = None,
    *,
    cfg: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Short environment context printed with every doctor report."""
    env = detect_env()
    summary: dict[str, Any] = {
        "llmwiki_version": __version__,
        "python": sys.version.split()[0],
        "executable": env.executable,
        "os": platform.system() or "unknown",
        "has_pip": env.has_pip,
        "has_uv": env.has_uv,
        "uv_managed": env.uv_managed,
        "catalog_version": load_heal_kb().version,
        "extra_add": find_spec("markitdown") is not None,
        "extra_graph": find_spec("graphify") is not None,
    }
    if env.project_root is not None:
        summary["install_mode"] = "editable-checkout"
    else:
        summary["install_mode"] = "distribution"

    if vault is not None:
        summary["vault"] = str(vault.expanduser())

    try:
        loaded = cfg if cfg is not None else _load_sessions_config()
        backend = resolve_backend(loaded)
        summary["synthesis_backend"] = type(backend).__name__
        summary["synthesis_backend_available"] = bool(backend.is_available())
        synth_cfg = (loaded.get("synthesis") or {}) if isinstance(loaded, dict) else {}
        summary["synthesis_backend_config"] = str(
            synth_cfg.get("backend") or "dummy"
        ).strip().lower()
    except Exception:  # noqa: BLE001 — env summary must not crash doctor
        summary["synthesis_backend"] = "unknown"
        summary["synthesis_backend_available"] = False
        summary["synthesis_backend_config"] = "unknown"

    return summary


def check_install_interpreter() -> list[Finding]:
    """Area A — installer / interpreter readiness."""
    findings: list[Finding] = []
    env = detect_env()
    if not env.has_pip and not env.has_uv:
        f = _finding("env.no_package_installer")
        if f is not None:
            findings.append(f)
    elif env.uv_managed and not env.has_uv:
        f = _finding("env.uv_venv_without_uv")
        if f is not None:
            findings.append(f)
    return findings


def check_optional_extras() -> list[Finding]:
    """Area B — optional ``[graph]`` (and related) extras."""
    findings: list[Finding] = []
    if find_spec("graphify") is None:
        f = _finding(
            "env.extra_graph_missing",
            message=(
                "Optional [graph] extra is missing — graphify is not importable. "
                f"Install with: {install_hint('graph')}"
            ),
        )
        if f is not None:
            findings.append(f)
    return findings


def check_adapters() -> list[Finding]:
    """Area D — session adapters present / stores visible."""
    findings: list[Finding] = []
    try:
        discover_all()
        available = get_available()
    except Exception:  # noqa: BLE001
        available = {}
    if not available:
        f = _finding("adapters.none_available")
        if f is not None:
            findings.append(f)
    return findings


def check_add_readiness() -> list[Finding]:
    """Area E — ``llmwiki add`` converter readiness (``[add]`` / markitdown)."""
    findings: list[Finding] = []
    if find_spec("markitdown") is None:
        f = _finding(
            "env.extra_add_missing",
            message=(
                "Optional [add] extra is missing — markitdown is not importable, "
                "so PDF/DOCX ingest will fail. "
                f"Install with: {install_hint('add')}"
            ),
        )
        if f is not None:
            findings.append(f)
    return findings


def check_synthesis_backend(cfg: dict[str, Any] | None = None) -> list[Finding]:
    """Area F — configured synthesis backend vs availability."""
    findings: list[Finding] = []
    try:
        loaded = cfg if cfg is not None else _load_sessions_config()
        backend = resolve_backend(loaded)
    except Exception as exc:  # noqa: BLE001
        f = _finding(
            "synth.backend_unavailable",
            message=f"Could not resolve synthesis backend: {type(exc).__name__}",
        )
        if f is not None:
            findings.append(f)
        return findings

    if isinstance(backend, DummySynthesizer):
        f = _finding("synth.backend_dummy")
        if f is not None:
            findings.append(f)
        return findings

    if not backend.is_available():
        f = _finding(
            "synth.backend_unavailable",
            message=f"Configured synthesis {backend_unavailable_message(backend)}.",
        )
        if f is not None:
            findings.append(f)
    return findings


def run_checks_a_to_f(
    vault: Path | None = None,
    *,
    cfg: dict[str, Any] | None = None,
) -> list[Finding]:
    """Run live detectors for areas A–F in heal order.

    ``vault`` is accepted for API stability (C is handled as a hard stop in
    :func:`run_doctor` before these checks). Area C does not emit additional
    findings here beyond the unusable-vault path.
    """
    del vault  # hard-stop handled by run_doctor
    findings: list[Finding] = []
    findings.extend(check_install_interpreter())
    findings.extend(check_optional_extras())
    findings.extend(check_adapters())
    findings.extend(check_add_readiness())
    findings.extend(check_synthesis_backend(cfg))
    return findings


def _parse_iso_age_days(stamp: str, *, now: datetime) -> int | None:
    raw = (stamp or "").strip()
    if not raw:
        return None
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        when = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    return max(0, (now - when.astimezone(UTC)).days)


def check_pipeline_backlog(
    vault: Path,
    *,
    now: datetime | None = None,
    overdue_days: int = PIPELINE_OVERDUE_DAYS,
) -> list[Finding]:
    """Area G — emit only when *unsynthesized* work has been waiting too long.

    Uses ``synth.pending`` / ``pending_total`` from vault state (the same queue
    ``llmwiki synth`` drains). Does **not** use “oldest file under raw/” — an
    already-synthesized session from months ago still sits in ``raw/`` forever
    and must not look like a synth backlog. Harvestable wikilink targets
    (``summarize_backlog``) are also not a synth queue; they feed candidate
    harvest, not this finding.
    """
    clock = now or datetime.now(UTC)
    if clock.tzinfo is None:
        clock = clock.replace(tzinfo=UTC)

    state = read_state(resolve_state_file(Path(vault)))
    synth = state.get("synth") if isinstance(state, dict) else {}
    if not isinstance(synth, dict):
        return []

    pending_list = synth.get("pending") if isinstance(synth.get("pending"), list) else []
    pending_total = int(synth.get("pending_total") or 0)
    count = pending_total or len(pending_list)
    if count <= 0:
        return []

    # Prefer age of the oldest still-pending item (mtime on the pending row).
    # Fall back to pending_updated_at only when rows lack mtimes.
    ages: list[int] = []
    for item in pending_list:
        if not isinstance(item, dict):
            continue
        age = _parse_iso_age_days(str(item.get("mtime") or ""), now=clock)
        if age is not None:
            ages.append(age)
    if not ages:
        stamp_age = _parse_iso_age_days(
            str(synth.get("pending_updated_at") or ""), now=clock
        )
        if stamp_age is not None:
            ages.append(stamp_age)
    oldest = max(ages) if ages else 0
    if oldest < overdue_days:
        return []

    message = (
        f"Synth queue still has {count} unsynthesized raw/doc item(s); "
        f"oldest pending item is {oldest}d old (threshold {overdue_days}d). "
        "This is not “oldest file in raw/” — already-synthesized sessions stay "
        "in raw/ forever and do not count."
    )
    if (load_status(Path(vault)) or {}).get("job"):
        message += (
            " Scheduled maintenance is recorded for this vault but may not be reaching it"
            " — see the automation findings in this report."
        )
    f = _finding("pipeline.backlog_overdue", message=message)
    return [f] if f is not None else []


def check_candidates_review(
    vault: Path,
    *,
    now: datetime | None = None,
    overdue_days: int = CANDIDATE_OVERDUE_DAYS,
) -> list[Finding]:
    """Area H — emit only when pending candidates are overdue for review."""
    wiki_dir = Path(vault) / "wiki"
    # Touch list_candidates so the reuse contract stays explicit for tests.
    _ = list_candidates(wiki_dir, now=now)
    stale = stale_candidates(wiki_dir, threshold_days=overdue_days, now=now)
    if not stale:
        return []
    f = _finding(
        "candidates.review_pending",
        message=(
            f"{len(stale)} candidate stub(s) overdue for review "
            f"(≥{overdue_days}d)."
        ),
    )
    return [f] if f is not None else []


def check_migrate_hints(vault: Path) -> list[Finding]:
    """Area K — thin schema-drift hints (legacy folders / removed page kinds)."""
    wiki_dir = Path(vault) / "wiki"
    if not wiki_dir.is_dir():
        return []
    reasons: list[str] = []
    for folder in REMOVED_FOLDERS:
        path = wiki_dir / folder
        if path.is_dir() and any(path.rglob("*.md")):
            reasons.append(f"legacy folder wiki/{folder}/")
    for path in wiki_dir.rglob("*.md"):
        if path.name == "_context.md":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        kind = page_kind(text)
        if kind in REMOVED_KINDS:
            reasons.append(f"page type {kind!r} on {path.name}")
            break
    archive_reasons = Path(vault) / "wiki" / "archive" / "candidates"
    if archive_reasons.is_dir() and any(archive_reasons.rglob("*.reason.txt")):
        reasons.append("legacy archive *.reason.txt (dismissal ledger migrate)")
    if not reasons:
        return []
    f = _finding(
        "migrate.schema_drift",
        message="Vault shape needs migrate: " + "; ".join(reasons[:3]),
    )
    return [f] if f is not None else []


_LIVE_INACTIVE = {
    "linux": "timer is disabled",
    "macos": "job is not loaded",
    "windows": "task is disabled",
}


def _gone_part(unit: InstalledUnit) -> str | None:
    """What of ``unit``'s runtime no longer exists on disk (basename only), or ``None``."""
    if unit.working_dir is not None and not Path(unit.working_dir).is_dir():
        return f"runs from a checkout that no longer exists ('{Path(unit.working_dir).name}')"
    if unit.wrapper_path is None or not Path(unit.wrapper_path).is_file():
        label = Path(unit.wrapper_path).name if unit.wrapper_path else "none named"
        return f"its wrapper script is gone ('{label}')"
    return None


def _distinct_labels(a: Path, b: Path, *, cap: int = 3) -> tuple[str, str]:
    """Shortest trailing-component suffixes (at most ``cap``) that tell ``a`` and ``b`` apart."""
    for depth in range(1, cap + 1):
        label_a = "/".join(a.parts[-depth:])
        label_b = "/".join(b.parts[-depth:])
        if label_a != label_b:
            break
    return label_a, label_b


def _schedule_cause(
    root: Path, job: Any, discovery: DiscoveryResult
) -> tuple[Finding | None, str | None, InstalledUnit | None]:
    """``(cause finding, could-not-check reason, unit serving this vault)``."""
    unit = unit_for_vault(root, discovery)
    if unit is None:
        if discovery.unavailable:
            return None, discovery.unavailable, None
        return (
            _finding(
                "automation.unit_missing",
                message=(
                    f"Automation job {job!r} is recorded for this vault '{root.name}' "
                    "but no schedule for it is installed."
                ),
            ),
            None,
            None,
        )
    if not serves_vault(unit, root):
        if unit.target_vault is None:
            return None, unit.reason_unknown or f"schedule {unit.name} names no vault", None
        other = Path(unit.target_vault).expanduser().resolve()
        other_label, root_label = _distinct_labels(other, root)
        return (
            _finding(
                "automation.points_elsewhere",
                message=f"schedule {unit.name} serves vault '{other_label}', not this vault '{root_label}'",
            ),
            None,
            None,
        )
    gone = _gone_part(unit)
    if gone is not None:
        return (
            _finding(
                "automation.checkout_missing",
                message=f"Schedule {unit.name} serves this vault but {gone}.",
            ),
            None,
            None,
        )
    return None, discovery.unavailable, unit


def _orphan_finding(discovery: DiscoveryResult) -> Finding | None:
    """One finding naming every unit whose known target vault no longer exists, with removal steps."""
    if discovery.unavailable:
        return None
    orphans = [
        unit
        for unit in discovery.units
        if unit.target_vault is not None and not Path(unit.target_vault).expanduser().is_dir()
    ]
    if not orphans:
        return None
    lines = ["Leftover schedules for vaults that no longer exist (doctor does not remove them):"]
    for unit in orphans:
        lines.append(f"  {unit.name} (vault '{Path(unit.target_vault).name}') — remove it with:")
        lines.extend(f"    {step}" for step in removal_steps(unit))
    return _finding("automation.orphan_unit", message="\n".join(lines))


def check_automation(
    vault: Path,
    *,
    now: datetime | None = None,
    discovery: DiscoveryResult | None = None,
) -> list[Finding]:
    """Area L — leftover schedules, and declared automation that is missing, misdirected, broken or not active.

    ``discovery`` is the scheduler inspection to judge against (default:
    :func:`automation_units.discover_local_units`, read once per call; the
    scheduler is asked whether units are enabled only when this vault declares a
    job). Leftover schedules for vaults that no longer exist are reported on any
    vault; everything else only when this vault's status declares a job. ``now``
    (default: UTC now) is the clock run ages are judged against.
    """
    status = load_status(Path(vault)) or {}
    job = status.get("job")
    if discovery is None:
        discovery = automation_units.discover_local_units(probe=bool(job))
    orphan = _orphan_finding(discovery)
    leftovers = [orphan] if orphan is not None else []
    if not job:
        return leftovers
    return _job_findings(vault, job, status, discovery, now) + leftovers


def _job_findings(
    vault: Path,
    job: Any,
    status: dict[str, Any],
    discovery: DiscoveryResult,
    now: datetime | None,
) -> list[Finding]:
    """Findings about the job this vault's status declares."""
    root = Path(vault).expanduser().resolve()
    cause, unavailable, unit = _schedule_cause(root, job, discovery)
    if cause is not None:
        return _with_runner_argv([cause], root, status)
    findings: list[Finding] = []
    if unavailable:
        f = _finding(
            "automation.check_unavailable",
            message=f"Could not check the installed schedule for this vault: {unavailable}.",
        )
        if f is not None:
            findings.append(f)
    # Installer writes scheduler_*; legacy activated/active only when absent.
    # None means "not probed", never inactive.
    activated = status.get("scheduler_activated", status.get("activated"))
    active = status.get("scheduler_active", status.get("active"))
    note = str(status.get("note") or "")
    recorded_inactive = (
        activated is False
        or active is False
        or "not active" in note.casefold()
        or "skipped" in note.casefold()
    )
    message: str | None = None
    if unit is not None and unit.enabled is False:
        live = _LIVE_INACTIVE.get(unit.platform, "job is disabled")
        message = f"Automation job {job!r} is declared but not active: {live}."
    elif recorded_inactive:
        message = f"Automation job {job!r} is declared but not active."
    if message is not None:
        f = _finding("automation.not_active", message=message)
        if f is not None:
            findings.append(f)
    duplicate = _duplicate_legacy_finding(root, unit, discovery)
    if duplicate is not None:
        findings.append(duplicate)
    findings.extend(_runtime_findings(unit, status))
    run_issue = _run_issue(root, job, status, unit, now or datetime.now(UTC))
    if run_issue is not None:
        f = _finding(run_issue[0], message=run_issue[1])
        if f is not None:
            findings.append(f)
    return _with_runner_argv(findings, root, status)


def _wrapper_interpreter(text: str) -> str | None:
    """The interpreter the wrapper's ``… -m llmwiki …`` line runs, or ``None``."""
    for line in text.splitlines():
        if " -m llmwiki" not in line:
            continue
        try:
            tokens = shlex.split(line.replace("{", " ").replace("}", " "))
        except ValueError:
            return None
        for i, token in enumerate(tokens[1:], start=1):
            if token == "-m" and tokens[i + 1:i + 2] == ["llmwiki"]:
                return tokens[i - 1]
    return None


def _runtime_findings(unit: InstalledUnit | None, status: dict[str, Any]) -> list[Finding]:
    """What the installed job needs at run time but lacks (#374).

    The wrapper predates run stamping (Home could not notice a missed run),
    its interpreter is gone, or a program folder recorded at install is gone.
    """
    findings: list[Finding] = []
    text = ""
    if unit is not None and unit.wrapper_path is not None:
        try:
            text = Path(unit.wrapper_path).read_text(encoding="utf-8")
        except OSError:
            text = ""
    if text and f"export {SCHEDULED_ENV}=1" not in text:
        f = _finding(
            "automation.setup_outdated",
            message=f"Schedule {unit.name} was installed by an older llmwiki that does not "
            "record its runs, so a missed run would not show on Home.",
        )
        if f is not None:
            findings.append(f)
    interpreter = _wrapper_interpreter(text) if text else None
    if interpreter and Path(interpreter).is_absolute() and not Path(interpreter).exists():
        f = _finding(
            "automation.interpreter_missing",
            message=f"Schedule {unit.name} runs Python '{interpreter}', which no longer exists, "
            "so no scheduled run can start.",
        )
        if f is not None:
            findings.append(f)
    gone = [d for d in status.get("program_dirs") or [] if not Path(str(d)).is_dir()]
    if gone:
        f = _finding(
            "automation.program_dir_missing",
            message="Folders the scheduled job looks in for its programs no longer exist: "
            + ", ".join(f"'{d}'" for d in gone) + ".",
        )
        if f is not None:
            findings.append(f)
    return findings


def _duplicate_legacy_finding(
    root: Path, unit: InstalledUnit | None, discovery: DiscoveryResult
) -> Finding | None:
    """The legacy single unit still running for this vault beside its own per-vault unit."""
    if unit is None or unit.legacy:
        return None
    legacy = legacy_unit_serving(root, discovery)
    if legacy is None:
        return None
    lines = [
        f"This vault is also scheduled by the earlier single {LEGACY_SYSTEMD} schedule "
        f"({legacy.name}), so two jobs run against it. Remove the old one with:"
    ]
    lines.extend(f"  {step}" for step in removal_steps(legacy))
    return _finding("automation.duplicate_legacy", message="\n".join(lines))


# A log with no EXIT line yet, written this recently, is a run still in progress.
_IN_PROGRESS = timedelta(hours=6)
_EXIT_LINE = re.compile(r"^EXIT:(-?\d+)\s*$", re.MULTILINE)


def _humanise(age: timedelta) -> str:
    """``age`` as "3 days" / "5 hours" / "10 minutes" (largest whole unit)."""
    seconds = max(0, int(age.total_seconds()))
    for size, unit in ((86400, "day"), (3600, "hour"), (60, "minute")):
        if seconds >= size:
            count = seconds // size
            return f"{count} {unit}{'' if count == 1 else 's'}"
    return "less than a minute"


def _parse_stamp(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        when = datetime.fromisoformat(raw.strip())
    except ValueError:
        return None
    return when if when.tzinfo is not None else when.replace(tzinfo=UTC)


# The wrapper keeps the job's exit code: 75 is a provider usage-limit stop, not a failure.
_SOFT_STOP_EXITS = frozenset({0, 75})


def _run_log(
    root: Path, status: dict[str, Any], unit: InstalledUnit | None, since: datetime | None
) -> Path | None:
    """First run log written by this schedule: unit wrapper's, status ``log_path``, per-vault.

    The legacy global log counts only for the legacy unit, or when the serving
    unit names no log of its own. A log last written before ``since`` (the
    schedule's ``installed_at``) belongs to an earlier schedule and is skipped.
    """
    candidates: list[Path] = []
    if unit is not None and unit.log_path is not None:
        candidates.append(Path(unit.log_path))
    if isinstance(status.get("log_path"), str) and status["log_path"].strip():
        candidates.append(Path(status["log_path"].strip()).expanduser())
    candidates.append(vault_automation_log_path(root))
    if unit is None or unit.legacy or unit.log_path is None:
        candidates.append(default_log_path())
    for path in candidates:
        try:
            mtime = datetime.fromtimestamp(path.stat().st_mtime, UTC)
        except OSError:
            continue
        if path.is_file() and (since is None or mtime >= since):
            return path
    return None


def _run_issue(
    root: Path, job: Any, status: dict[str, Any], unit: InstalledUnit | None, now: datetime
) -> tuple[str, str] | None:
    """``(finding id, message)`` when this vault's schedule has stopped completing runs."""
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    try:
        threshold = 2 * cron_interval(parse_cron(schedule_from_status(status)))
    except CronError:
        return None
    installed_at = _parse_stamp(status.get("installed_at"))
    log = _run_log(root, status, unit, installed_at)
    if log is None:
        since = installed_at or _parse_stamp(status.get("updated_at"))
        if since is None or now - since <= threshold:
            return None
        return (
            "automation.stale_run",
            f"Automation job {job!r} has not run since it was set up {_humanise(now - since)} ago.",
        )
    try:
        last_run = datetime.fromtimestamp(log.stat().st_mtime, UTC)
        text = log.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    exits = _EXIT_LINE.findall(text)
    if exits and int(exits[-1]) not in _SOFT_STOP_EXITS:
        return (
            "automation.last_run_failed",
            f"Automation job {job!r}: last run failed (exit {exits[-1]}); see {log}.",
        )
    age = now - last_run
    if not exits and age < _IN_PROGRESS:
        return None
    if age > threshold:
        return ("automation.stale_run", f"Automation job {job!r}: last run was {_humanise(age)} ago.")
    return None


def _with_runner_argv(
    findings: list[Finding], root: Path, status: dict[str, Any]
) -> list[Finding]:
    """Attach the reinstall command to ``install_automation`` findings, so display and dispatch agree."""
    argv = tuple(install_automation_argv(root, status))
    return [replace(f, runner_argv=argv) if f.runner == "install_automation" else f for f in findings]


def check_site_freshness(vault: Path) -> list[Finding]:
    """Area M — site/ skew vs wiki/."""
    root = Path(vault)
    wiki_dir = root / "wiki"
    site_index = root / "site" / "index.html"
    if not wiki_dir.is_dir():
        return []
    wiki_mtime = 0.0
    for path in wiki_dir.rglob("*.md"):
        try:
            wiki_mtime = max(wiki_mtime, path.stat().st_mtime)
        except OSError:
            continue
    if wiki_mtime <= 0:
        return []
    if not site_index.is_file():
        f = _finding(
            "build.site_stale",
            message="site/index.html is missing while wiki/ has pages — run llmwiki build.",
        )
        return [f] if f is not None else []
    try:
        site_mtime = site_index.stat().st_mtime
    except OSError:
        site_mtime = 0.0
    # Allow a small skew for near-simultaneous writes.
    if wiki_mtime <= site_mtime + 1.0:
        return []
    f = _finding(
        "build.site_stale",
        message="wiki/ is newer than site/index.html — rebuild the site.",
    )
    return [f] if f is not None else []


def check_agent_kit(
    vault: Path | None = None,
    *,
    kit_dest: Path | None = None,
) -> list[Finding]:
    """Area N — outdated agent-kit manifest when a dest is inspectable."""
    del vault  # dest is explicit or absent; never invent a personal path
    if kit_dest is None:
        return []
    dest = Path(kit_dest)
    if not (dest / MANIFEST_NAME).is_file() and not dest.is_dir():
        return []
    manifest = read_manifest(dest)
    if manifest is None:
        return []
    installed = str(manifest.get("version") or "").strip()
    if not installed or installed == __version__:
        return []
    f = _finding(
        "agent_kit.outdated",
        message=(
            f"Agent kit at {dest.name}/ reports version {installed}; "
            f"package is {__version__}."
        ),
    )
    return [f] if f is not None else []


def check_privacy_posture(*, emit_info: bool = False) -> list[Finding]:
    """Area O — non-actionable redaction posture reminder (drafts only).

    Default is silent: drafts already use placeholders. Opt-in ``emit_info``
    for explicit posture listing; never fails the exit code (actionable=false).
    """
    if not emit_info:
        return []
    f = _finding("privacy.draft_redaction")
    return [f] if f is not None else []


def run_checks_g_to_o(
    vault: Path,
    *,
    now: datetime | None = None,
    kit_dest: Path | None = None,
) -> list[Finding]:
    """Run thin live detectors for areas G/H/K–O (J via lint fold)."""
    findings: list[Finding] = []
    findings.extend(check_pipeline_backlog(vault, now=now))
    findings.extend(check_candidates_review(vault, now=now))
    findings.extend(check_migrate_hints(vault))
    findings.extend(check_automation(vault, now=now))
    findings.extend(check_site_freshness(vault))
    findings.extend(check_agent_kit(vault, kit_dest=kit_dest))
    findings.extend(check_privacy_posture())
    return findings

