"""Text rendering for doctor reports."""

from __future__ import annotations

from llmwiki.doctor.models import DoctorReport, Finding, FixTier, sort_findings

#: Env keys shown first (stable order); remaining keys follow sorted.
_ENV_PRIORITY = (
    "llmwiki_version",
    "python",
    "executable",
    "os",
    "install_mode",
    "has_pip",
    "has_uv",
    "uv_managed",
    "extra_add",
    "extra_graph",
    "synthesis_backend_config",
    "synthesis_backend",
    "synthesis_backend_available",
    "catalog_version",
    "vault",
)


def render_finding(finding: Finding) -> str:
    """One finding as a short multi-line block."""
    lines = [
        f"[{finding.severity}] {finding.id} (area {finding.area}, tier={finding.tier})",
        f"  {finding.message}",
    ]
    if finding.fix:
        lines.append(f"  how to fix: {finding.fix}")
    if finding.runner:
        lines.append(f"  doctor can run: {finding.runner}")
    return "\n".join(lines)


def _partition(findings: list[Finding]) -> tuple[list[Finding], list[Finding]]:
    """Split into (doctor-can-run, guided/manual)."""
    runnable: list[Finding] = []
    guided: list[Finding] = []
    for finding in findings:
        if finding.runner and finding.tier != FixTier.GUIDED:
            runnable.append(finding)
        else:
            guided.append(finding)
    return sort_findings(runnable), sort_findings(guided)


def render_text(report: DoctorReport) -> str:
    """Render env summary + severity-sorted findings (+ unknown assist)."""
    lines: list[str] = ["llmwiki doctor"]
    mode = report.mode.value if hasattr(report.mode, "value") else str(report.mode)
    lines.append(f"mode: {mode}")

    env = report.env_summary or {}
    if env:
        lines.append("environment:")
        seen: set[str] = set()
        for key in _ENV_PRIORITY:
            if key in env:
                lines.append(f"  {key}: {env[key]}")
                seen.add(key)
        for key in sorted(env):
            if key not in seen:
                lines.append(f"  {key}: {env[key]}")

    if report.vault_error:
        lines.append(f"error: {report.vault_error}")

    findings = sort_findings(list(report.findings))
    if findings:
        n_err = sum(1 for f in findings if f.severity == "error")
        n_warn = sum(1 for f in findings if f.severity == "warning")
        n_info = sum(1 for f in findings if f.severity == "info")
        lines.append(
            f"findings ({len(findings)}): "
            f"{n_err} error(s), {n_warn} warning(s), {n_info} info — "
            "sorted by severity"
        )
        runnable, guided = _partition(findings)
        if runnable:
            lines.append("— doctor can apply (with consent) —")
            for finding in runnable:
                lines.append(render_finding(finding))
        if guided:
            lines.append("— manual / guided (doctor will not auto-run these) —")
            for finding in guided:
                lines.append(render_finding(finding))
        if runnable:
            lines.append(
                "hint: after this report, doctor may ask to apply the automatic "
                "fixes (or use --yes without --check for safe runners only)."
            )
    elif report.exit_code == 0:
        lines.append("findings: none — install and vault look sound")
    else:
        lines.append("findings: none")

    if report.unknown_assist:
        assist = report.unknown_assist
        lines.append("unknown assist (runner is null — do not invent a fix):")
        if assist.get("kb_url"):
            lines.append(f"  heal_kb: {assist['kb_url']}")
        if assist.get("agents_url"):
            lines.append(f"  AGENTS.md: {assist['agents_url']}")
        lines.append("--- GitHub issue draft ---")
        lines.append(assist.get("issue_body", "").rstrip())
        lines.append("--- AI investigation prompt ---")
        lines.append(assist.get("ai_prompt", "").rstrip())

    lines.append(f"exit: {report.exit_code}")
    return "\n".join(lines) + "\n"
