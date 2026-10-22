"""``llmwiki doctor`` — heal the install and vault until sound.

Diagnose (A–O + lint fold) → plan → confirm → run safe/dangerous runners →
re-check. ``--check`` / ``--dry-run`` never mutate; ``--yes`` auto-applies
**safe** tier only.
"""

from __future__ import annotations

import shlex
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, TextIO

from llmwiki import REPO_ROOT
from llmwiki.automation_units import dev_checkout_warning
from llmwiki.doctor.anon import build_unknown_assist
from llmwiki.doctor.checks import (
    collect_env_summary,
    run_checks_a_to_f,
    run_checks_g_to_o,
)
from llmwiki.doctor.kb import (
    HealKB,
    HealKBError,
    finding_from_entry,
    get_entry,
    list_areas,
    load_heal_kb,
    match_symptom,
)
from llmwiki.doctor.lint_fold import run_lint_fold, should_skip_lint
from llmwiki.doctor.models import (
    DoctorMode,
    DoctorReport,
    Finding,
    FixTier,
    sort_findings,
)
from llmwiki.doctor.progress import ProgressFn, make_progress, noop_progress
from llmwiki.doctor.report import render_text
from llmwiki.doctor.runners import dispatch_runner, runner_is_dangerous

__all__ = [
    "DoctorMode",
    "DoctorReport",
    "Finding",
    "FixTier",
    "HealKB",
    "HealKBError",
    "get_entry",
    "list_areas",
    "load_heal_kb",
    "match_symptom",
    "render_text",
    "run_doctor",
    "sort_findings",
    "runnable_findings",
    "guided_findings",
    "ask_to_apply_heals",
    "print_heal_summary",
    "apply_heals",
]


def _normalize_mode(mode: DoctorMode | str) -> DoctorMode:
    if isinstance(mode, DoctorMode):
        return mode
    return DoctorMode(str(mode).strip().lower())


def _vault_unusable_reason(vault: Path | None) -> str | None:
    """Return a user-facing error if ``vault``/``wiki`` cannot be healed, else ``None``."""
    if vault is None:
        return (
            "No vault configured. Pass --vault PATH, or set vault.default_path "
            "in config.json, then ensure the vault has a wiki/ directory."
        )
    try:
        root = vault.expanduser().resolve(strict=False)
    except OSError as exc:
        return f"Cannot resolve vault path: {exc}"
    if not root.exists():
        return f"Vault path does not exist: {root}"
    if not root.is_dir():
        return f"Vault path is not a directory: {root}"
    wiki = root / "wiki"
    if not wiki.is_dir():
        return f"No wiki/ directory under vault: {root}"
    return None


def _exit_for_findings(findings: list[Finding]) -> int:
    """R8: 1 when actionable problems remain, else 0."""
    if any(f.actionable for f in findings):
        return 1
    return 0


def _unknown_finding(symptom: str) -> Finding:
    """Guided finding for unmatched symptoms — never invents a runner."""
    del symptom
    return Finding(
        id="unknown.unmatched_symptom",
        area="O",
        message=(
            "No heal-catalog match for this symptom. "
            "Use the anonymized GitHub issue draft and AI prompt below."
        ),
        fix=(
            "Paste the issue draft or AI prompt; do not run an invented shell "
            "command. Maintainers may add a catalog entry in a later release."
        ),
        actionable=True,
        severity="warning",
        tier=FixTier.GUIDED,
        runner=None,
    )


def _dedupe_findings(findings: list[Finding]) -> list[Finding]:
    seen: set[str] = set()
    out: list[Finding] = []
    for finding in findings:
        if finding.id in seen:
            continue
        seen.add(finding.id)
        out.append(finding)
    return out


def diagnose(
    vault: Path,
    *,
    cfg: dict[str, Any] | None = None,
    skip_lint: bool = False,
    kit_dest: Path | None = None,
    progress: ProgressFn | None = None,
) -> list[Finding]:
    """Run detectors A–O and lint fold (unless skipped)."""
    progress = progress or noop_progress
    progress("checking environment, extras, and synthesis backend")
    early = run_checks_a_to_f(vault, cfg=cfg)
    findings: list[Finding] = list(early)
    lint_skipped = skip_lint or should_skip_lint(
        error_lookup=False, early_findings=early
    )
    if not lint_skipped:
        progress("running wiki lint (can take a while on large vaults)")
        findings.extend(run_lint_fold(vault))
    else:
        progress("skipping lint (blocked by earlier errors or --error lookup)")
    progress("checking pipeline backlog, candidates, and other vault signals")
    findings.extend(run_checks_g_to_o(vault, kit_dest=kit_dest))
    progress("diagnosis complete")
    return sort_findings(_dedupe_findings(findings))


def _default_is_tty() -> bool:
    return bool(getattr(sys.stdin, "isatty", lambda: False)())


def _print_runner_plan(finding: Finding, *, stdout: TextIO) -> None:
    """Print the exact command a runner executes and, for automation, where it runs from."""
    if finding.runner_argv is None:
        print(f"  will run: {finding.runner} ({finding.tier})", file=stdout)
        return
    cmd = shlex.join([sys.executable, "-m", "llmwiki", *finding.runner_argv])
    print(f"  will run: {cmd} ({finding.tier})", file=stdout)
    if finding.runner != "install_automation":
        return
    print(f"  runs from: {REPO_ROOT}", file=stdout)
    warning = dev_checkout_warning(REPO_ROOT)
    if warning is not None:
        print(f"  warning: {warning}", file=stdout)


def _confirm_finding(
    finding: Finding,
    *,
    yes: bool,
    is_tty: bool,
    confirm_fn: Callable[[str], bool] | None,
    stdout: TextIO,
) -> bool:
    """Return True when this finding's runner should execute."""
    if finding.runner is None or finding.tier == FixTier.GUIDED:
        return False
    dangerous = finding.tier == FixTier.DANGEROUS or runner_is_dangerous(finding.runner)
    if yes and not dangerous:
        return True
    if yes and dangerous and not is_tty:
        print(
            f"skip dangerous (need TTY confirm): {finding.id} runner={finding.runner}",
            file=stdout,
        )
        if finding.runner_argv is not None:
            _print_runner_plan(finding, stdout=stdout)
        return False
    if not is_tty and not yes:
        return False
    if not is_tty:
        return False
    print(f"\n[{finding.severity}] {finding.id}", file=stdout)
    print(f"  {finding.message}", file=stdout)
    print(f"  how to fix: {finding.fix}", file=stdout)
    _print_runner_plan(finding, stdout=stdout)
    prompt = "Apply this fix now? [y/N] "
    if confirm_fn is not None:
        return bool(confirm_fn(prompt))
    try:
        answer = input(prompt)
    except EOFError:
        return False
    return answer.strip().casefold() in {"y", "yes"}


def _heal_loop(
    vault: Path,
    findings: list[Finding],
    *,
    yes: bool,
    is_tty: bool,
    cfg: dict[str, Any] | None,
    kit_dest: Path | None,
    confirm_fn: Callable[[str], bool] | None,
    stdout: TextIO,
    progress: ProgressFn | None = None,
    max_passes: int = 3,
) -> list[Finding]:
    """Confirm → run → re-check until stable or max passes."""
    progress = progress or noop_progress
    current = sort_findings(list(findings))
    guided = [
        f for f in current
        if f.actionable and (not f.runner or f.tier == FixTier.GUIDED)
    ]
    runnable = runnable_findings(current)
    if is_tty:
        print(
            f"\nApplying automatic fixes only ({len(runnable)}). "
            f"{len(guided)} manual/guided finding(s) were listed in the report "
            "above — skip those for now.",
            file=stdout,
        )
    for pass_i in range(max_passes):
        applied_any = False
        runnable = runnable_findings(current)
        if not runnable:
            break
        if is_tty and not yes:
            print(
                f"\nHeal pass {pass_i + 1}: confirm each of {len(runnable)} "
                "automatic fix(es).",
                file=stdout,
            )
        for finding in runnable:
            if not _confirm_finding(
                finding,
                yes=yes,
                is_tty=is_tty,
                confirm_fn=confirm_fn,
                stdout=stdout,
            ):
                continue
            print(
                f"running {finding.runner} for {finding.id}...",
                file=stdout,
                flush=True,
            )
            result = dispatch_runner(finding.runner, vault, kit_dest=kit_dest)
            print(f"  {result.message}", file=stdout)
            if result.refused_elevation:
                continue
            if result.ok:
                applied_any = True
        if not applied_any:
            break
        progress("re-checking after applied fixes")
        current = diagnose(vault, cfg=cfg, kit_dest=kit_dest, progress=progress)
    return sort_findings(current)


def runnable_findings(findings: list[Finding]) -> list[Finding]:
    """Findings doctor can execute (have a runner, not guided-only)."""
    return [
        f for f in findings
        if f.actionable and f.runner and f.tier != FixTier.GUIDED
    ]


def guided_findings(findings: list[Finding]) -> list[Finding]:
    """Findings the user must handle manually (no auto runner)."""
    run_ids = {f.id for f in runnable_findings(findings)}
    return [f for f in findings if f.id not in run_ids]


def print_heal_summary(
    findings: list[Finding],
    *,
    stdout: TextIO | None = None,
) -> bool:
    """Print automatic-vs-manual counts; return True when any runnable fix exists.

    Does **not** ask a yes/no question — per-finding confirms happen in the heal
    loop (:func:`_confirm_finding`).
    """
    out = stdout if stdout is not None else sys.stdout
    runnable = runnable_findings(findings)
    guided = guided_findings(findings)
    if not runnable:
        return False
    print(
        f"\nSummary: {len(runnable)} fix(es) doctor can apply automatically "
        f"(confirm each next); "
        f"{len(guided)} finding(s) stay manual/guided (doctor will not run those).",
        file=out,
    )
    return True


def ask_to_apply_heals(
    findings: list[Finding],
    *,
    confirm_fn: Callable[[str], bool] | None = None,
    stdout: TextIO | None = None,
) -> bool:
    """Compatibility wrapper: print the heal summary (no outer yes/no prompt).

    ``confirm_fn`` is ignored — kept so older call sites/tests keep working.
    Per-item consent is :func:`_confirm_finding` inside :func:`apply_heals`.
    """
    del confirm_fn
    return print_heal_summary(findings, stdout=stdout)


def apply_heals(
    vault: Path | str,
    findings: list[Finding],
    *,
    yes: bool = False,
    cfg: dict[str, Any] | None = None,
    kit_dest: Path | str | None = None,
    is_tty: bool | None = None,
    confirm_fn: Callable[[str], bool] | None = None,
    stdout: TextIO | None = None,
    progress: ProgressFn | None = None,
) -> DoctorReport:
    """Run the consent heal loop on an existing diagnose result (no re-prompt before)."""
    vault_path = Path(vault)
    out = stdout if stdout is not None else sys.stdout
    tty = _default_is_tty() if is_tty is None else bool(is_tty)
    kit_path = Path(kit_dest) if kit_dest is not None else None
    progress_fn = progress if progress is not None else make_progress()
    env = collect_env_summary(vault_path, cfg=cfg)

    if not tty and not yes:
        return DoctorReport(
            findings=sort_findings(list(findings)),
            exit_code=_exit_for_findings(findings),
            mode=DoctorMode.HEAL,
            env_summary=env,
        )

    healed = _heal_loop(
        vault_path,
        findings,
        yes=yes,
        is_tty=tty,
        cfg=cfg,
        kit_dest=kit_path,
        confirm_fn=confirm_fn,
        stdout=out,
        progress=progress_fn,
    )
    return DoctorReport(
        findings=sort_findings(healed),
        exit_code=_exit_for_findings(healed),
        mode=DoctorMode.HEAL,
        env_summary=env,
    )


def run_doctor(
    vault: Path | str | None,
    *,
    mode: DoctorMode | str = DoctorMode.HEAL,
    error_text: str | None = None,
    yes: bool = False,
    cfg: dict[str, Any] | None = None,
    kit_dest: Path | str | None = None,
    is_tty: bool | None = None,
    confirm_fn: Callable[[str], bool] | None = None,
    stdout: TextIO | None = None,
    progress: ProgressFn | None = None,
    apply: bool | None = None,
) -> DoctorReport:
    """Run doctor diagnose and optionally the consent heal loop.

    Parameters
    ----------
    vault:
        Vault root, or ``None`` when unset. Missing/unusable vault or wiki →
        exit code **2**.
    mode:
        ``heal`` (default), ``check`` / diagnose-only, or ``error`` lookup.
    error_text:
        Pasted symptom for ``--error``.
    yes:
        Auto-apply **safe** fixes only; dangerous still needs TTY confirm.
    cfg:
        Optional sessions config override (tests); default loads from disk.
    kit_dest:
        Optional agent-kit destination for area N / install_agent_kit runner.
    is_tty:
        Override TTY detection (tests). Default: ``sys.stdin.isatty()``.
    confirm_fn:
        Optional ``prompt -> bool`` for interactive confirms (tests).
    stdout:
        Where heal-loop progress lines go (default ``sys.stdout``).
    progress:
        Stage logger (default: ``doctor: …`` lines on stderr). Pass
        ``noop_progress`` in tests to silence.
    apply:
        When ``False``, diagnose only (CLI prints the report, then may call
        :func:`apply_heals`). When ``None`` (default): apply for ``heal`` if
        TTY or ``--yes``; never apply for ``check``.
    """
    resolved_mode = _normalize_mode(mode)
    out = stdout if stdout is not None else sys.stdout
    tty = _default_is_tty() if is_tty is None else bool(is_tty)
    kit_path = Path(kit_dest) if kit_dest is not None else None
    progress_fn = progress if progress is not None else make_progress()
    if apply is None:
        # ERROR matches may heal when TTY or --yes (same consent as heal mode).
        apply_now = resolved_mode in {DoctorMode.HEAL, DoctorMode.ERROR} and (
            tty or yes
        )
    else:
        apply_now = bool(apply) and resolved_mode != DoctorMode.CHECK

    vault_path: Path | None
    if vault is None:
        vault_path = None
    else:
        vault_path = Path(vault)

    progress_fn("loading heal catalog")
    load_heal_kb()

    reason = _vault_unusable_reason(vault_path)
    if reason is not None:
        env = collect_env_summary(vault_path, cfg=cfg)
        entry = get_entry("vault.missing_or_unusable") or {}
        finding = Finding(
            id="vault.missing_or_unusable",
            area="C",
            message=reason,
            fix=str(
                entry.get(
                    "fix",
                    "Pass --vault PATH or run llmwiki init --vault PATH.",
                )
            ),
            actionable=True,
            severity="error",
            tier=FixTier.GUIDED,
            runner=None,
        )
        return DoctorReport(
            findings=[finding],
            exit_code=2,
            mode=resolved_mode,
            env_summary=env,
            vault_error=reason,
        )

    assert vault_path is not None
    progress_fn("collecting environment summary")
    env = collect_env_summary(vault_path, cfg=cfg)

    # --error: KB lookup only (no full lint; detectors deferred until heal continues).
    if resolved_mode == DoctorMode.ERROR or (
        error_text is not None and str(error_text).strip()
    ):
        symptom = str(error_text or "").strip()
        if not symptom:
            return DoctorReport(
                findings=[],
                exit_code=0,
                mode=DoctorMode.ERROR,
                env_summary=env,
            )
        progress_fn("matching pasted error against heal catalog")
        matched = match_symptom(symptom)
        if matched.entry is not None:
            finding = finding_from_entry(matched.entry)
            findings = [finding]
            # Honor apply=False (CLI diagnose-then-ask) and --check/--dry-run.
            # Heal only when apply_now is true (library callers with apply=True
            # or apply=None on a TTY/--yes heal path).
            if apply_now:
                findings = _heal_loop(
                    vault_path,
                    findings,
                    yes=yes,
                    is_tty=tty,
                    cfg=cfg,
                    kit_dest=kit_path,
                    confirm_fn=confirm_fn,
                    stdout=out,
                    progress=progress_fn,
                )
            return DoctorReport(
                findings=sort_findings(findings),
                exit_code=_exit_for_findings(findings),
                mode=DoctorMode.ERROR,
                env_summary=env,
            )
        assist = build_unknown_assist(symptom, env_summary=env)
        unknown = _unknown_finding(symptom)
        return DoctorReport(
            findings=[unknown],
            exit_code=1,
            mode=DoctorMode.ERROR,
            env_summary=env,
            unknown_assist=assist,
        )

    findings = diagnose(
        vault_path, cfg=cfg, kit_dest=kit_path, progress=progress_fn
    )

    if not apply_now:
        return DoctorReport(
            findings=findings,
            exit_code=_exit_for_findings(findings),
            mode=resolved_mode,
            env_summary=env,
        )

    findings = _heal_loop(
        vault_path,
        findings,
        yes=yes,
        is_tty=tty,
        cfg=cfg,
        kit_dest=kit_path,
        confirm_fn=confirm_fn,
        stdout=out,
        progress=progress_fn,
    )
    return DoctorReport(
        findings=sort_findings(findings),
        exit_code=_exit_for_findings(findings),
        mode=DoctorMode.HEAL,
        env_summary=env,
    )
