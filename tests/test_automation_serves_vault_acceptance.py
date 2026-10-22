"""Whole-feature acceptance: doctor detects scheduled maintenance that no longer serves the vault.

Drives the real CLI (``main([...])``) and ``run_doctor`` against a Linux
"machine" under ``tmp_path``: HOME points at a scratch dir and the scheduler is
a small stateful fake behind ``run_scheduler_cmd``, so no real
systemctl/launchctl/schtasks is ever called. Slice-level detail lives in
``test_automation_install.py``, ``test_doctor_checks.py``, ``test_doctor_runners.py``
and ``test_doctor_kb_match.py``; this module asserts the cross-cutting flows of
functional-spec.md (R1-R8).

# @layer: e2e
# @spec: context/spec/330-doctor-automation-serves-vault
# @regression
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from io import StringIO
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from llmwiki.automation_install import render_systemd_service, render_wrapper_script
from llmwiki.automation_plan import AutomationPlan
from llmwiki.automation_status import load_status, save_status, status_path, vault_automation_log_path
from llmwiki.automation_units import LEGACY_SYSTEMD, DiscoveryResult, discover_units, unit_names
from llmwiki.cli import main
from llmwiki.doctor import DoctorMode, run_doctor
from llmwiki.doctor import runners as runners_mod
from llmwiki.doctor.checks import check_automation
from llmwiki.install_hint import PythonEnv
from llmwiki.state_store import write_state

_NOW = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)
_POINTS_ELSEWHERE = "automation.points_elsewhere"
_AUTOMATION_IDS = (
    "automation.unit_missing",
    _POINTS_ELSEWHERE,
    "automation.checkout_missing",
    "automation.not_active",
    "automation.stale_run",
)


class Machine:
    """A throwaway Linux box: scratch HOME, stateful fake systemd, real discovery over it."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.home = root / "home"
        self.unit_dir = self.home / ".config" / "systemd" / "user"
        self.unit_dir.mkdir(parents=True)
        self.disabled: set[str] = set()
        self.calls: list[list[str]] = []

    def scheduler(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        """Answer the systemctl calls install and doctor make; ``is-enabled`` reflects files + disables."""
        self.calls.append(list(args))
        verb, target = args[2], args[3] if len(args) > 3 else ""
        if verb == "is-enabled":
            name = target.removesuffix(".timer")
            on = (self.unit_dir / target).is_file() and name not in self.disabled
            return subprocess.CompletedProcess(args, 0 if on else 1, "enabled\n" if on else "disabled\n", "")
        if verb == "disable":
            self.disabled.add(args[-1].removesuffix(".timer"))
        if verb == "enable":
            self.disabled.discard(args[-1].removesuffix(".timer"))
        return subprocess.CompletedProcess(args, 0, "", "")

    def discovery(self, *, probe: bool = True) -> DiscoveryResult:
        return discover_units("linux", home=self.home, run=self.scheduler, probe=probe)

    def install(self, vault: Path, *flags: str) -> int:
        """``llmwiki install-automation`` for ``vault`` through the real CLI."""
        return main([
            "install-automation", "--vault", str(vault), "--units-dir", str(self.root / "staging"),
            "--force-platform", "linux", "--yes", "--job", "maintain", *flags,
        ])

    def legacy_unit(self, checkout: Path, target: Path | None) -> None:
        """The pre-per-vault single ``llmwiki-maintain`` unit, run from ``checkout`` (a worktree)."""
        checkout.mkdir(parents=True, exist_ok=True)
        if target is not None:
            (checkout / "config.json").write_text(json.dumps({"vault": {"default_path": str(target)}}), encoding="utf-8")
        wrapper = self.unit_dir / f"{LEGACY_SYSTEMD}.sh"
        wrapper.write_text(
            render_wrapper_script(
                plan=AutomationPlan(job="maintain", graph="builtin"),
                python_bin="/usr/bin/python3",
                working_dir=checkout,
                log_path=self.root / "legacy.log",
                vault=None,
            ),
            encoding="utf-8",
        )
        (self.unit_dir / f"{LEGACY_SYSTEMD}.service").write_text(
            render_systemd_service(wrapper=wrapper, working_dir=checkout), encoding="utf-8"
        )
        (self.unit_dir / f"{LEGACY_SYSTEMD}.timer").write_text("# timer\n", encoding="utf-8")


@pytest.fixture
def machine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Machine:
    box = Machine(tmp_path / "machine")
    monkeypatch.setenv("HOME", str(box.home))
    monkeypatch.setattr("llmwiki.automation_install.run_scheduler_cmd", box.scheduler)
    monkeypatch.setattr("llmwiki.automation_install.detect_platform", lambda: "linux")
    monkeypatch.setattr("llmwiki.cli.detect_platform", lambda: "linux")
    monkeypatch.setattr("llmwiki.automation_units.discover_local_units", box.discovery)
    return box


def _vault(root: Path) -> Path:
    (root / "wiki").mkdir(parents=True)
    (root / "raw").mkdir(parents=True)
    return root


def _healthy_env() -> PythonEnv:
    return PythonEnv(
        executable="/usr/bin/python3", has_pip=True, uv_managed=False, has_uv=True, project_root=None
    )


@pytest.fixture(autouse=True)
def _healthy_machine(monkeypatch: pytest.MonkeyPatch) -> None:
    """Everything outside area L reads as healthy, so only automation findings can fail doctor."""
    backend = MagicMock()
    backend.is_available.return_value = True
    backend.is_llm = True
    type(backend).__name__ = "ClaudeCLISynthesizer"
    monkeypatch.setattr("llmwiki.doctor.checks.find_spec", lambda name: object())
    monkeypatch.setattr("llmwiki.doctor.checks.discover_all", lambda: None)
    monkeypatch.setattr("llmwiki.doctor.checks.get_available", lambda: {"claude_code": object()})
    monkeypatch.setattr("llmwiki.doctor.checks.resolve_backend", lambda cfg=None: backend)
    monkeypatch.setattr("llmwiki.doctor.checks.detect_env", _healthy_env)


def _doctor(vault: Path, capsys: pytest.CaptureFixture[str], *args: str) -> tuple[int, str]:
    capsys.readouterr()
    code = main(["doctor", "--vault", str(vault), *args])
    return code, capsys.readouterr().out


def _ids(findings: list[Any]) -> list[str]:
    return [f.id for f in findings if f.id.startswith("automation.")]


def _incident(machine: Machine) -> tuple[Path, Path, Path]:
    """Real vault A with a recorded job but no schedule of its own; the legacy unit runs a worktree aimed at a test vault."""
    vault_a = _vault(machine.root / "real-vault")
    test_vault = _vault(machine.root / "throwaway-test-vault")
    assert machine.install(vault_a, "--no-activate") == 0
    worktree = machine.root / "worktrees" / "feat-x"
    machine.legacy_unit(worktree, target=test_vault)
    return vault_a, test_vault, worktree


# ─── R4 + R1 + R2: the incident replay ───


def test_incident_replay_doctor_names_the_schedule_and_the_repair_sticks(
    machine: Machine, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The legacy unit aimed at a test vault is reported as an error with shortened names, and repairing it leaves the test vault's schedule untouched."""
    vault_a, test_vault, _worktree = _incident(machine)
    legacy_files = {p.name: p.read_bytes() for p in machine.unit_dir.iterdir()}

    code, out = _doctor(vault_a, capsys, "--check")
    assert code != 0
    assert _POINTS_ELSEWHERE in out
    assert "serves vault 'throwaway-test-vault', not this vault 'real-vault'" in out
    assert str(machine.root) not in out.split(_POINTS_ELSEWHERE, 1)[1].split("\n\n", 1)[0]
    assert "install-automation" in out

    # Repair through the real heal loop; the runner's subprocess is the in-process CLI.
    ran: list[list[str]] = []

    def in_process(argv: list[str], **_kw: Any) -> subprocess.CompletedProcess[str]:
        assert argv[:3] == [sys.executable, "-m", "llmwiki"]
        ran.append(argv[3:])
        code = main(["install-automation", *argv[4:], "--units-dir", str(machine.root / "staging"),
                     "--force-platform", "linux"])
        return subprocess.CompletedProcess(argv, code, "", "")

    monkeypatch.setattr(runners_mod.subprocess, "run", in_process)
    report = run_doctor(
        vault_a, mode=DoctorMode.HEAL, is_tty=True, confirm_fn=lambda _p: True, stdout=StringIO(),
        cfg={"synthesis": {"backend": "claude"}},
    )
    capsys.readouterr()
    assert len(ran) == 1 and ran[0][0] == "install-automation" and "--force" in ran[0] and "--yes" in ran[0]
    assert not _ids(report.findings)

    names = unit_names(vault_a)
    assert (machine.unit_dir / names.timer).is_file()
    assert all((machine.unit_dir / n).read_bytes() == b for n, b in legacy_files.items())
    assert load_status(vault_a)["target_vault"] == str(vault_a.resolve())
    assert str(test_vault) in (machine.root / "worktrees" / "feat-x" / "config.json").read_text(encoding="utf-8")

    code, out = _doctor(vault_a, capsys, "--check")
    assert "automation." not in out


def test_yes_alone_never_applies_the_schedule_repair(
    machine: Machine, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The repair is a confirm-only change: ``--yes`` on a non-terminal prints the exact command and installs nothing."""
    vault_a, _test_vault, _worktree = _incident(machine)
    capsys.readouterr()
    monkeypatch.setattr(runners_mod.subprocess, "run", lambda *a, **k: pytest.fail("ran the repair"))
    sink = StringIO()
    run_doctor(
        vault_a, mode=DoctorMode.HEAL, yes=True, is_tty=False, stdout=sink,
        cfg={"synthesis": {"backend": "claude"}},
    )
    out = sink.getvalue()
    assert not (machine.unit_dir / unit_names(vault_a).timer).exists()
    assert "skip dangerous (need TTY confirm): automation.points_elsewhere" in out
    assert "will run:" in out and "install-automation" in out


def test_backlog_warning_and_schedule_error_appear_together(
    machine: Machine, capsys: pytest.CaptureFixture[str]
) -> None:
    """R6: with a job recorded and an overdue backlog, one report carries both the hint and the automation error; without a job it reads as before."""
    vault_a, _test_vault, _worktree = _incident(machine)
    old = (datetime.now(UTC) - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    write_state(
        {"synth": {"files": {}, "pending": [{"rel": "sessions/a.md"}], "pending_total": 1, "pending_updated_at": old}},
        vault_a,
    )
    _code, out = _doctor(vault_a, capsys, "--check")
    assert "pipeline.backlog_overdue" in out
    assert "may not be reaching it" in out
    assert _POINTS_ELSEWHERE in out

    vault_b = _vault(machine.root / "never-scheduled")
    write_state(
        {"synth": {"files": {}, "pending": [{"rel": "sessions/a.md"}], "pending_total": 1, "pending_updated_at": old}},
        vault_b,
    )
    _code, out = _doctor(vault_b, capsys, "--check")
    assert "pipeline.backlog_overdue" in out
    assert "may not be reaching it" not in out


# ─── R1: coexistence and legacy adoption ───


def test_two_vaults_coexist_and_legacy_adoption_is_announced(
    machine: Machine, capsys: pytest.CaptureFixture[str]
) -> None:
    """Setting up B keeps A's schedule pointed at A; setting up the vault the legacy unit serves replaces it and says so."""
    vault_a, vault_b = _vault(machine.root / "a"), _vault(machine.root / "b")
    assert machine.install(vault_a) == 0
    assert machine.install(vault_b) == 0
    for vault in (vault_a, vault_b):
        names = unit_names(vault)
        assert str(vault.resolve()) in (machine.unit_dir / names.wrapper).read_text(encoding="utf-8")
        assert (machine.unit_dir / names.timer).is_file()
    assert unit_names(vault_a).base != unit_names(vault_b).base
    assert not _ids(check_automation(vault_a, discovery=machine.discovery()))

    served = _vault(machine.root / "served")
    machine.legacy_unit(machine.root / "old-checkout", target=served)
    capsys.readouterr()
    assert machine.install(served, "--force") == 0
    out = capsys.readouterr().out
    assert "llmwiki-maintain" in out and "replac" in out.lower()
    assert not (machine.unit_dir / f"{LEGACY_SYSTEMD}.service").exists()
    assert (machine.unit_dir / unit_names(served).timer).is_file()
    assert (machine.unit_dir / unit_names(vault_a).timer).is_file()


# ─── R2: setup guard ───


def test_yes_without_force_refuses_a_foreign_checkout_and_force_proceeds_with_warnings(
    machine: Machine, capsys: pytest.CaptureFixture[str]
) -> None:
    """Replacing a schedule that runs from another checkout needs ``--force`` when there is no terminal, and the dev-copy warning still prints."""
    vault = _vault(machine.root / "real-vault")
    machine.legacy_unit(machine.root / "elsewhere-checkout", target=vault)
    before = {p.name: p.read_bytes() for p in machine.unit_dir.iterdir()}

    assert machine.install(vault) == 2
    captured = capsys.readouterr()
    assert "pass --force to replace it" in captured.err
    assert "current schedule runs from:" in captured.out
    assert {p.name: p.read_bytes() for p in machine.unit_dir.iterdir()} == before
    assert load_status(vault) is None

    assert machine.install(vault, "--force") == 0
    out = capsys.readouterr().out
    assert "current schedule runs from:" in out
    assert "warning: installing from a git worktree" in out or "warning: installing from a development checkout" in out
    assert (machine.unit_dir / unit_names(vault).timer).is_file()


# ─── R3 + R4: recorded and live state ───


def test_recorded_inactive_legacy_format_and_live_disabled_are_both_reported(
    machine: Machine, capsys: pytest.CaptureFixture[str]
) -> None:
    """A status in the older ``activated: false`` format and a timer the scheduler reports disabled each give the not-active finding."""
    vault = _vault(machine.root / "real-vault")
    assert machine.install(vault) == 0
    assert not _ids(check_automation(vault, discovery=machine.discovery()))

    machine.disabled.add(unit_names(vault).base)
    found = check_automation(vault, discovery=machine.discovery())
    assert _ids(found) == ["automation.not_active"]
    assert "timer is disabled" in found[0].message

    machine.disabled.clear()
    status = load_status(vault) or {}
    status.pop("scheduler_activated", None)
    status.pop("scheduler_active", None)
    save_status(vault, {**status, "activated": False})
    assert _ids(check_automation(vault, discovery=machine.discovery())) == ["automation.not_active"]


def test_missing_schedule_is_an_error_and_a_vault_without_a_job_is_silent(
    machine: Machine, capsys: pytest.CaptureFixture[str]
) -> None:
    """A recorded job with no unit at all is an error; a vault that never set up a schedule gets no automation findings."""
    vault = _vault(machine.root / "real-vault")
    assert machine.install(vault, "--no-activate") == 0
    code, out = _doctor(vault, capsys, "--check")
    assert code != 0 and "automation.unit_missing" in out

    plain = _vault(machine.root / "plain")
    code, out = _doctor(plain, capsys, "--check")
    assert "automation." not in out


# ─── R5: stale runs ───


def _installed_at(vault: Path, when: datetime) -> None:
    status = load_status(vault) or {}
    save_status(vault, {**status, "installed_at": when.strftime("%Y-%m-%dT%H:%M:%SZ")})


def _stale(machine: Machine, vault: Path) -> list[Any]:
    return [
        f
        for f in check_automation(vault, now=_NOW, discovery=machine.discovery())
        if f.id in ("automation.stale_run", "automation.last_run_failed")
    ]


def test_stale_run_waits_out_the_grace_period_then_warns(machine: Machine) -> None:
    """A fresh schedule that has not run yet is quiet, and warns once it has existed for more than two intervals."""
    vault = _vault(machine.root / "real-vault")
    assert machine.install(vault) == 0
    _installed_at(vault, _NOW - timedelta(days=1))
    assert _stale(machine, vault) == []
    _installed_at(vault, _NOW - timedelta(days=3))
    (found,) = _stale(machine, vault)
    assert found.severity == "warning" and "has not run" in found.message


def test_stale_run_reports_age_and_a_failed_run_names_its_log(machine: Machine) -> None:
    """An old run gives its age; a failed run is its own guided finding naming the log; a usage-limit stop is quiet."""
    vault = _vault(machine.root / "real-vault")
    assert machine.install(vault) == 0
    _installed_at(vault, _NOW - timedelta(days=30))
    log = vault_automation_log_path(vault)
    log.parent.mkdir(parents=True, exist_ok=True)

    def logged(text: str, age: timedelta) -> None:
        log.write_text(text, encoding="utf-8")
        os.utime(log, ((_NOW - age).timestamp(),) * 2)

    logged("done\nEXIT:0\n", timedelta(days=5))
    (found,) = _stale(machine, vault)
    assert "5 days ago" in found.message
    assert found.id == "automation.stale_run"
    logged("boom\nEXIT:3\n", timedelta(hours=2))
    (found,) = _stale(machine, vault)
    assert found.id == "automation.last_run_failed" and found.tier == "guided" and found.runner is None
    assert "last run failed" in found.message and "exit 3" in found.message and str(log) in found.message
    logged("usage limit\nEXIT:75\n", timedelta(hours=2))
    assert _stale(machine, vault) == []
    logged("done\nEXIT:0\n", timedelta(hours=2))
    assert _stale(machine, vault) == []


def test_run_record_in_the_shared_legacy_location_still_counts(
    machine: Machine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A vault still scheduled by the older single unit, with no log of its own, is judged by the shared run log instead of being called never-run."""
    vault = _vault(machine.root / "real-vault")
    machine.legacy_unit(machine.root / "old-checkout", target=vault)
    old = (_NOW - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    save_status(vault, {"job": "maintain", "schedule": "0 3 * * *", "installed_at": old})
    shared = machine.root / "shared.log"
    shared.write_text("done\nEXIT:0\n", encoding="utf-8")
    os.utime(shared, ((_NOW - timedelta(hours=1)).timestamp(),) * 2)
    monkeypatch.setattr("llmwiki.doctor.checks.default_log_path", lambda: shared)
    assert _stale(machine, vault) == []
    shared.unlink()
    assert len(_stale(machine, vault)) == 1


def test_a_fresh_install_is_not_judged_by_an_older_shared_log(
    machine: Machine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Right after (re)installing this vault's own schedule, an old shared run log neither ages nor fails it."""
    vault = _vault(machine.root / "real-vault")
    assert machine.install(vault) == 0
    _installed_at(vault, _NOW - timedelta(hours=1))
    shared = machine.root / "shared.log"
    monkeypatch.setattr("llmwiki.doctor.checks.default_log_path", lambda: shared)
    for text in ("done\nEXIT:0\n", "boom\nEXIT:1\n"):
        shared.write_text(text, encoding="utf-8")
        os.utime(shared, ((_NOW - timedelta(days=40)).timestamp(),) * 2)
        assert _stale(machine, vault) == []


# ─── R7: leftovers ───


def test_leftover_schedule_for_a_gone_vault_is_listed_on_any_vault_with_removal_steps(
    machine: Machine, capsys: pytest.CaptureFixture[str]
) -> None:
    """A schedule left behind for a deleted vault is a warning on unrelated vaults, with home-relative removal steps, and doctor does not remove it."""
    gone = _vault(machine.root / "throwaway-test-vault")
    assert machine.install(gone) == 0
    gone_unit = unit_names(gone)
    shutil.rmtree(gone)

    other = _vault(machine.root / "unrelated")
    code, out = _doctor(other, capsys, "--check")
    assert "automation.orphan_unit" in out
    assert gone_unit.base in out
    assert "systemctl --user disable --now" in out
    assert "~" in out and str(machine.home) not in out
    assert (machine.unit_dir / gone_unit.timer).is_file()


# ─── R8: error lookup ───


@pytest.mark.parametrize(
    ("text", "entry"),
    [
        ("schedule llmwiki-maintain serves vault 'a', not this vault 'b'", _POINTS_ELSEWHERE),
        ("schedule points at another vault", _POINTS_ELSEWHERE),
        ("is recorded for this vault 'v' but no schedule for it is installed", "automation.unit_missing"),
        ("Schedule x serves this vault but runs from a checkout that no longer exists ('w')", "automation.checkout_missing"),
        ("Automation job 'maintain': last run failed (exit 3); see /x/log.", "automation.last_run_failed"),
        ("automation not running", "automation.stale_run"),
        ("Leftover schedules for vaults that no longer exist", "automation.orphan_unit"),
        ("existing schedule runs from a different checkout; pass --force to replace it", "automation.setup_other_checkout"),
        ("installing from a git worktree — the scheduled job will keep using this copy", "automation.setup_dev_checkout"),
        ("Automation job 'maintain' is declared but not active", "automation.not_active"),
    ],
)
def test_error_lookup_recognises_every_new_message(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], text: str, entry: str
) -> None:
    """Each new finding message and symptom phrase pasted into ``doctor --error`` resolves to its own catalog entry, not the unknown-problem path."""
    code, out = _doctor(_vault(tmp_path / "v"), capsys, "--check", "--error", text)
    assert entry in out
    assert "no match" not in out.lower()


def test_error_lookup_still_rejects_unrelated_text(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Text that matches nothing keeps the unknown-problem path rather than being claimed by an automation entry."""
    _code, out = _doctor(_vault(tmp_path / "v"), capsys, "--check", "--error", "completely-unknown-zyx-symptom-999")
    assert "automation." not in out


# ─── Absence of status ───


def test_no_status_means_no_automation_findings_except_leftovers(
    machine: Machine, capsys: pytest.CaptureFixture[str]
) -> None:
    """A vault with no automation status is never told about its schedule, but still hears about leftovers for vanished vaults."""
    vault = _vault(machine.root / "plain")
    assert not status_path(vault).exists()
    machine.legacy_unit(machine.root / "old-checkout", target=machine.root / "vanished-vault")
    found = check_automation(vault, discovery=machine.discovery())
    assert _ids(found) == ["automation.orphan_unit"]
    assert not _ids(check_automation(vault, discovery=DiscoveryResult(units=(), unavailable=None)))
    assert [f for f in found if f.id in _AUTOMATION_IDS[:-1] + ("automation.not_active",)] == []
