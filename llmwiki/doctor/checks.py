"""Live detectors for doctor areas A–O (Slices 3–4).

Detectors emit findings keyed by stable catalog ``id`` — no free-text
guessing. Area I/J lint findings come from :mod:`llmwiki.doctor.lint_fold`
(provenance via lint fold is enough for J). G/H emit only when overdue.
"""

from __future__ import annotations

import platform
import sys
from datetime import UTC, datetime
from importlib.util import find_spec
from pathlib import Path
from typing import Any

from llmwiki import __version__
from llmwiki.adapters import discover_all, get_available
from llmwiki.automation_status import load_status
from llmwiki.candidates import DEFAULT_STALE_DAYS, list_candidates, stale_candidates
from llmwiki.config_schedule import _load_sessions_config
from llmwiki.doctor.kb import finding_from_entry, get_entry, load_heal_kb
from llmwiki.doctor.models import Finding
from llmwiki.install_agent_kit import MANIFEST_NAME, read_manifest
from llmwiki.install_hint import detect_env, install_hint
from llmwiki.migrate_page_kinds import REMOVED_FOLDERS, REMOVED_KINDS, page_kind
from llmwiki.state_store import read_state, resolve_state_file
from llmwiki.synth.base import DummySynthesizer
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
        "automation.not_active",
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
            message=(
                f"Configured synthesis backend {type(backend).__name__} "
                "is not available in this environment."
            ),
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


def check_automation(vault: Path) -> list[Finding]:
    """Area L — declared automation that is not active."""
    status = load_status(Path(vault))
    if not status:
        return []
    job = status.get("job")
    if not job:
        return []
    activated = status.get("activated")
    active = status.get("active")
    note = str(status.get("note") or "")
    inactive = (
        activated is False
        or active is False
        or "not active" in note.casefold()
        or "skipped" in note.casefold()
    )
    if not inactive:
        return []
    f = _finding(
        "automation.not_active",
        message=f"Automation job {job!r} is declared but not active.",
    )
    return [f] if f is not None else []


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
    findings.extend(check_automation(vault))
    findings.extend(check_site_freshness(vault))
    findings.extend(check_agent_kit(vault, kit_dest=kit_dest))
    findings.extend(check_privacy_posture())
    return findings

