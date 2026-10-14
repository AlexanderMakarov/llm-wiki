"""Data models for ``llmwiki doctor`` (heal loop)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class FixTier(StrEnum):
    """How aggressively doctor may apply a fix when the user consents."""

    SAFE = "safe"
    DANGEROUS = "dangerous"
    GUIDED = "guided"


class DoctorMode(StrEnum):
    """Public run modes for :func:`llmwiki.doctor.run_doctor`."""

    HEAL = "heal"  # default: diagnose → confirm → apply → re-check
    CHECK = "check"  # diagnose only (--check / --dry-run)
    ERROR = "error"  # look up one pasted symptom (--error)


Severity = str  # "error" | "warning" | "info" — kept loose for KB JSON

_SEVERITY_RANK = {"error": 0, "warning": 1, "info": 2}


def severity_rank(severity: str) -> int:
    """Sort key: error first, then warning, then info, then unknown."""
    return _SEVERITY_RANK.get(str(severity).casefold(), 9)


@dataclass(frozen=True)
class Finding:
    """One diagnosed problem, keyed by a stable heal-catalog ``id``."""

    id: str
    area: str
    message: str
    fix: str
    actionable: bool
    severity: Severity
    tier: FixTier
    runner: str | None = None


def sort_findings(findings: list[Finding]) -> list[Finding]:
    """Stable severity order (error → warning → info), then id."""
    return sorted(findings, key=lambda f: (severity_rank(f.severity), f.id))


@dataclass
class DoctorReport:
    """Result of a doctor run: env context, findings, and scripting exit code."""

    findings: list[Finding] = field(default_factory=list)
    exit_code: int = 0
    mode: DoctorMode = DoctorMode.HEAL
    env_summary: dict[str, Any] = field(default_factory=dict)
    vault_error: str | None = None
    #: R5 drafts when ``--error`` did not match the catalog (``runner`` stays null).
    unknown_assist: dict[str, str] | None = None
