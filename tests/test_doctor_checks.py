"""Slice 3: live detectors A–F + env summary + check-mode mapping.

# @spec: 327-doctor
"""

from __future__ import annotations

import json
import os
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from llmwiki.automation_status import save_status, status_path, vault_automation_log_path
from llmwiki.automation_units import DiscoveryResult, InstalledUnit, unit_names
from llmwiki.cli import main
from llmwiki.doctor import DoctorMode, run_doctor
from llmwiki.doctor.checks import (
    DETECTOR_IDS_A_TO_F,
    check_automation,
    collect_env_summary,
    run_checks_a_to_f,
    run_checks_g_to_o,
)
from llmwiki.doctor.kb import load_heal_kb
from llmwiki.doctor.models import Finding
from llmwiki.doctor.runners import install_automation_argv
from llmwiki.install_hint import PythonEnv
from llmwiki.synth.base import DummySynthesizer


def _scaffold_vault(root: Path) -> Path:
    (root / "wiki").mkdir(parents=True)
    (root / "raw").mkdir(parents=True)
    return root


def _available_non_dummy() -> Any:
    backend = MagicMock()
    backend.is_available.return_value = True
    backend.is_llm = True
    type(backend).__name__ = "ClaudeCLISynthesizer"
    return backend


def _healthy_env() -> PythonEnv:
    return PythonEnv(
        executable="/usr/bin/python3",
        has_pip=True,
        uv_managed=False,
        has_uv=True,
        project_root=None,
    )


def _patch_healthy_deps(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("llmwiki.doctor.checks.find_spec", lambda name: object())
    monkeypatch.setattr("llmwiki.doctor.checks.discover_all", lambda: None)
    monkeypatch.setattr(
        "llmwiki.doctor.checks.get_available",
        lambda: {"claude_code": object()},
    )
    monkeypatch.setattr(
        "llmwiki.doctor.checks.resolve_backend",
        lambda cfg=None: _available_non_dummy(),
    )
    monkeypatch.setattr("llmwiki.doctor.checks.detect_env", _healthy_env)


def test_detector_ids_subset_of_heal_kb() -> None:
    kb = load_heal_kb()
    catalog_ids = {e["id"] for e in kb.entries}
    missing = DETECTOR_IDS_A_TO_F - catalog_ids
    assert not missing, f"detector ids missing from heal_kb.json: {sorted(missing)}"


def test_missing_add_extra_emits_catalog_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault = _scaffold_vault(tmp_path / "vault")

    def _fake_find_spec(name: str) -> Any:
        if name == "markitdown":
            return None
        if name == "graphify":
            return object()
        return object()

    monkeypatch.setattr("llmwiki.doctor.checks.find_spec", _fake_find_spec)
    monkeypatch.setattr(
        "llmwiki.doctor.checks.resolve_backend",
        lambda cfg=None: _available_non_dummy(),
    )
    monkeypatch.setattr(
        "llmwiki.doctor.checks.get_available",
        lambda: {"claude_code": object()},
    )
    monkeypatch.setattr("llmwiki.doctor.checks.discover_all", lambda: None)
    monkeypatch.setattr("llmwiki.doctor.checks.detect_env", _healthy_env)

    findings = run_checks_a_to_f(vault, cfg={"synthesis": {"backend": "claude"}})
    ids = {f.id for f in findings}
    assert "env.extra_add_missing" in ids
    assert "env.extra_graph_missing" not in ids


def test_dummy_backend_finding(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    vault = _scaffold_vault(tmp_path / "vault")
    monkeypatch.setattr("llmwiki.doctor.checks.find_spec", lambda name: object())
    monkeypatch.setattr("llmwiki.doctor.checks.discover_all", lambda: None)
    monkeypatch.setattr(
        "llmwiki.doctor.checks.get_available",
        lambda: {"claude_code": object()},
    )
    monkeypatch.setattr(
        "llmwiki.doctor.checks.resolve_backend",
        lambda cfg=None: DummySynthesizer(),
    )
    monkeypatch.setattr("llmwiki.doctor.checks.detect_env", _healthy_env)

    report = run_doctor(
        vault,
        mode=DoctorMode.CHECK,
        cfg={"synthesis": {"backend": "dummy"}},
    )
    ids = {f.id for f in report.findings}
    assert "synth.backend_dummy" in ids
    assert report.exit_code == 1


def test_good_vault_smoke_exit_0(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault = _scaffold_vault(tmp_path / "vault")
    _patch_healthy_deps(monkeypatch)

    report = run_doctor(
        vault,
        mode=DoctorMode.CHECK,
        cfg={"synthesis": {"backend": "claude"}},
    )
    assert report.exit_code == 0
    assert not any(f.actionable for f in report.findings)
    assert "python" in report.env_summary
    assert "synthesis_backend" in report.env_summary or "catalog_version" in report.env_summary


def test_env_summary_keys(tmp_path: Path) -> None:
    vault = _scaffold_vault(tmp_path / "vault")
    summary = collect_env_summary(vault, cfg={"synthesis": {"backend": "dummy"}})
    for key in (
        "llmwiki_version",
        "python",
        "os",
        "catalog_version",
        "extra_add",
        "extra_graph",
        "synthesis_backend_config",
    ):
        assert key in summary


def test_cli_check_shows_environment(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    vault = _scaffold_vault(tmp_path / "vault")
    _patch_healthy_deps(monkeypatch)
    code = main(["doctor", "--check", "--vault", str(vault)])
    assert code == 0
    out = capsys.readouterr().out
    assert "environment:" in out
    assert "llmwiki_version:" in out


@pytest.mark.parametrize(
    "status",
    [
        pytest.param(
            {"job": "llmwiki-maintain", "scheduler_activated": False, "scheduler_active": False},
            id="new-keys-false",
        ),
        pytest.param({"job": "llmwiki-maintain", "activated": False}, id="legacy-activated-false"),
        pytest.param(
            {"job": "llmwiki-maintain", "scheduler_activated": True, "note": "activation skipped"},
            id="note-skipped",
        ),
    ],
)
def test_check_automation_flags_inactive(tmp_path: Path, status: dict[str, Any]) -> None:
    vault = _scaffold_vault(tmp_path / "vault")
    save_status(vault, status)
    found = check_automation(vault, discovery=_discovery(_own_unit(vault)))
    assert [f.id for f in found] == ["automation.not_active"]


@pytest.mark.parametrize(
    "status",
    [
        pytest.param(
            {"job": "llmwiki-maintain", "scheduler_activated": True, "scheduler_active": True},
            id="healthy-active",
        ),
        pytest.param(
            {"job": "llmwiki-maintain", "scheduler_activated": True, "scheduler_active": None},
            id="active-unprobed",
        ),
        pytest.param(
            {"job": "llmwiki-maintain", "scheduler_activated": True, "activated": False},
            id="new-key-wins-over-legacy",
        ),
    ],
)
def test_check_automation_quiet_when_active(tmp_path: Path, status: dict[str, Any]) -> None:
    vault = _scaffold_vault(tmp_path / "vault")
    save_status(vault, status)
    assert check_automation(vault, discovery=_discovery(_own_unit(vault))) == []


# ─── Installed schedule vs this vault (@spec: 330-doctor-automation-serves-vault) ───

_JOB_STATUS: dict[str, Any] = {
    "job": "llmwiki-maintain",
    "scheduler_activated": True,
    "scheduler_active": True,
}


def _unit(
    *,
    name: str,
    checkout: Path,
    target: Path | None,
    legacy: bool = False,
    enabled: bool | None = True,
    platform: str = "linux",
    reason: str | None = None,
    make_files: bool = True,
) -> InstalledUnit:
    wrapper = checkout / f"{name}.sh"
    if make_files:
        checkout.mkdir(parents=True, exist_ok=True)
        wrapper.write_text("#!/bin/bash\n", encoding="utf-8")
    return InstalledUnit(
        name=name,
        platform=platform,
        legacy=legacy,
        wrapper_path=wrapper,
        working_dir=checkout,
        target_vault=target,
        log_path=None,
        enabled=enabled,
        reason_unknown=reason,
    )


def _own_unit(vault: Path, **kwargs: Any) -> InstalledUnit:
    """Per-vault unit for ``vault`` (liveness unprobed unless overridden)."""
    kwargs.setdefault("enabled", None)
    return _unit(
        name=unit_names(vault).base,
        checkout=vault.parent / "checkout",
        target=vault,
        **kwargs,
    )


def _discovery(*units: InstalledUnit, unavailable: str | None = None) -> DiscoveryResult:
    return DiscoveryResult(units=units, unavailable=unavailable)


def _job_vault(tmp_path: Path, status: dict[str, Any] | None = None) -> Path:
    vault = _scaffold_vault(tmp_path / "real-vault")
    save_status(vault, dict(status or _JOB_STATUS))
    return vault


def test_unit_missing_when_scheduler_holds_nothing(tmp_path: Path) -> None:
    vault = _job_vault(tmp_path)
    (found,) = check_automation(vault, discovery=_discovery())
    assert found.id == "automation.unit_missing"
    assert found.severity == "error"
    assert found.runner == "install_automation"
    assert "real-vault" in found.message


def test_install_automation_finding_carries_reinstall_argv(tmp_path: Path) -> None:
    status = {"job": "maintain", "graph": "builtin", "schedule": "0 6 * * *", "synth_backend": "ollama"}
    vault = _job_vault(tmp_path, status)
    (found,) = check_automation(vault, discovery=_discovery())
    assert found.runner_argv == tuple(install_automation_argv(vault, status))
    assert "--yes" in found.runner_argv


def test_guided_automation_finding_has_no_runner_argv(tmp_path: Path) -> None:
    vault = _job_vault(tmp_path)
    (found,) = check_automation(vault, discovery=_discovery(unavailable="no user bus"))
    assert found.id == "automation.check_unavailable"
    assert found.runner_argv is None


def test_own_unit_for_this_vault_is_quiet(tmp_path: Path) -> None:
    vault = _job_vault(tmp_path)
    assert check_automation(vault, discovery=_discovery(_own_unit(vault, enabled=True))) == []


def test_legacy_unit_aimed_at_other_vault_points_elsewhere(tmp_path: Path) -> None:
    """The incident: the legacy unit, reinstalled from a worktree, serves a test vault."""
    vault = _job_vault(tmp_path)
    test_vault = _scaffold_vault(tmp_path / "worktree" / ".worktree-vault")
    legacy = _unit(
        name="llmwiki-maintain",
        checkout=tmp_path / "worktree",
        target=test_vault,
        legacy=True,
    )
    (found,) = check_automation(vault, discovery=_discovery(legacy))
    assert found.id == "automation.points_elsewhere"
    assert found.severity == "error"
    assert found.tier == "dangerous"
    assert found.message == (
        "schedule llmwiki-maintain serves vault '.worktree-vault', not this vault 'real-vault'"
    )
    assert str(tmp_path) not in found.message


def test_points_elsewhere_names_parents_when_vault_basenames_match(tmp_path: Path) -> None:
    """Two worktrees each holding ``.worktree-vault``: the parent tells them apart."""
    vault = _scaffold_vault(tmp_path / "checkout-a" / ".worktree-vault")
    save_status(vault, dict(_JOB_STATUS))
    other = _scaffold_vault(tmp_path / "checkout-b" / ".worktree-vault")
    legacy = _unit(
        name="llmwiki-maintain",
        checkout=tmp_path / "checkout-b",
        target=other,
        legacy=True,
    )
    (found,) = check_automation(vault, discovery=_discovery(legacy))
    assert found.id == "automation.points_elsewhere"
    assert found.message == (
        "schedule llmwiki-maintain serves vault 'checkout-b/.worktree-vault', "
        "not this vault 'checkout-a/.worktree-vault'"
    )
    assert str(tmp_path) not in found.message


def test_legacy_unit_aimed_at_this_vault_is_quiet(tmp_path: Path) -> None:
    vault = _job_vault(tmp_path)
    legacy = _unit(
        name="llmwiki-maintain",
        checkout=tmp_path / "checkout",
        target=vault,
        legacy=True,
    )
    assert check_automation(vault, discovery=_discovery(legacy)) == []


def test_own_unit_wins_over_legacy_elsewhere(tmp_path: Path) -> None:
    vault = _job_vault(tmp_path)
    legacy = _unit(
        name="llmwiki-maintain",
        checkout=tmp_path / "worktree",
        target=_scaffold_vault(tmp_path / "other-vault"),
        legacy=True,
    )
    discovery = _discovery(legacy, _own_unit(vault, enabled=True))
    assert check_automation(vault, discovery=discovery) == []


@pytest.mark.parametrize("gone", ["checkout", "wrapper"])
def test_checkout_missing_when_runtime_is_gone(tmp_path: Path, gone: str) -> None:
    vault = _job_vault(tmp_path)
    unit = _own_unit(vault, enabled=True)
    unit.wrapper_path.unlink()
    if gone == "checkout":
        unit.working_dir.rmdir()
    (found,) = check_automation(vault, discovery=_discovery(unit))
    assert found.id == "automation.checkout_missing"
    assert found.severity == "error"
    assert found.runner == "install_automation"
    assert str(tmp_path) not in found.message


def test_check_unavailable_when_scheduler_cannot_be_asked(tmp_path: Path) -> None:
    vault = _job_vault(tmp_path)
    found = check_automation(
        vault, discovery=_discovery(unavailable="systemctl is not installed")
    )
    assert [f.id for f in found] == ["automation.check_unavailable"]
    assert found[0].severity == "info"
    assert found[0].runner is None
    assert not found[0].actionable
    assert "systemctl is not installed" in found[0].message


def test_check_unavailable_when_legacy_target_unknown(tmp_path: Path) -> None:
    vault = _job_vault(tmp_path)
    legacy = _unit(
        name="llmwiki-maintain",
        checkout=tmp_path / "checkout",
        target=None,
        legacy=True,
        reason="checkout names no vault in its config",
    )
    found = check_automation(vault, discovery=_discovery(legacy))
    assert [f.id for f in found] == ["automation.check_unavailable"]
    assert "checkout names no vault in its config" in found[0].message


@pytest.mark.parametrize(
    ("platform", "live"),
    [("linux", "timer is disabled"), ("macos", "job is not loaded")],
)
def test_not_active_names_live_state(tmp_path: Path, platform: str, live: str) -> None:
    vault = _job_vault(tmp_path)
    unit = _own_unit(vault, enabled=False, platform=platform)
    (found,) = check_automation(vault, discovery=_discovery(unit))
    assert found.id == "automation.not_active"
    assert live in found.message


def test_live_enabled_unit_is_not_flagged(tmp_path: Path) -> None:
    vault = _job_vault(tmp_path)
    unit = _own_unit(vault, enabled=True)
    assert [f.id for f in check_automation(vault, discovery=_discovery(unit))] == []


@pytest.mark.parametrize("cause", ["unit_missing", "points_elsewhere", "checkout_missing"])
def test_cause_finding_suppresses_not_active(tmp_path: Path, cause: str) -> None:
    vault = _job_vault(tmp_path, {"job": "llmwiki-maintain", "scheduler_activated": False})
    if cause == "unit_missing":
        discovery = _discovery()
    elif cause == "points_elsewhere":
        discovery = _discovery(
            _unit(
                name="llmwiki-maintain",
                checkout=tmp_path / "worktree",
                target=_scaffold_vault(tmp_path / "other-vault"),
                legacy=True,
                enabled=False,
            )
        )
    else:
        unit = _own_unit(vault, enabled=False)
        unit.wrapper_path.unlink()
        discovery = _discovery(unit)
    assert [f.id for f in check_automation(vault, discovery=discovery)] == [f"automation.{cause}"]


# ─── Stale runs (@spec: 330-doctor-automation-serves-vault R5) ───

_NOW = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)


def _stamp(when: datetime) -> str:
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")


def _stale_vault(tmp_path: Path, **extra: Any) -> Path:
    """Job vault whose status is written verbatim (no ``updated_at`` added)."""
    vault = _scaffold_vault(tmp_path / "real-vault")
    path = status_path(vault)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({**_JOB_STATUS, **extra}), encoding="utf-8")
    return vault


def _write_log(path: Path, text: str, age: timedelta) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    stamp = (_NOW - age).timestamp()
    os.utime(path, (stamp, stamp))
    return path


def _stale_findings(vault: Path, *units: InstalledUnit) -> list[Finding]:
    found = check_automation(vault, now=_NOW, discovery=_discovery(*(units or (_own_unit(vault, enabled=True),))))
    return [f for f in found if f.id in ("automation.stale_run", "automation.last_run_failed")]


def test_stale_run_never_ran_past_grace_warns(tmp_path: Path) -> None:
    vault = _stale_vault(tmp_path, installed_at=_stamp(_NOW - timedelta(days=3)))
    (found,) = _stale_findings(vault)
    assert found.severity == "warning"
    assert found.runner_argv == tuple(install_automation_argv(vault.resolve(), json.loads(status_path(vault).read_text())))
    assert "has not run since it was set up 3 days ago" in found.message


def test_stale_run_never_ran_within_grace_is_quiet(tmp_path: Path) -> None:
    vault = _stale_vault(tmp_path, installed_at=_stamp(_NOW - timedelta(days=1)))
    assert _stale_findings(vault) == []


def test_stale_run_old_last_run_gives_age(tmp_path: Path) -> None:
    vault = _stale_vault(tmp_path, installed_at=_stamp(_NOW - timedelta(days=30)))
    _write_log(vault_automation_log_path(vault), "ok\nEXIT:0\n", timedelta(days=3, hours=2))
    (found,) = _stale_findings(vault)
    assert "last run was 3 days ago" in found.message


def test_stale_run_fresh_successful_run_is_quiet(tmp_path: Path) -> None:
    vault = _stale_vault(tmp_path, installed_at=_stamp(_NOW - timedelta(days=30)))
    _write_log(vault_automation_log_path(vault), "ok\nEXIT:0\n", timedelta(hours=5))
    assert _stale_findings(vault) == []


def test_stale_run_failed_run_names_log(tmp_path: Path) -> None:
    vault = _stale_vault(tmp_path, installed_at=_stamp(_NOW - timedelta(days=30)))
    log = _write_log(vault_automation_log_path(vault), "EXIT:0\nboom\nEXIT:1\n", timedelta(hours=1))
    (found,) = _stale_findings(vault)
    assert found.id == "automation.last_run_failed"
    assert (found.severity, found.tier, found.runner) == ("warning", "guided", None)
    assert f"last run failed (exit 1); see {log}" in found.message


def test_stale_run_usage_limit_stop_is_not_a_failure(tmp_path: Path) -> None:
    vault = _stale_vault(tmp_path, installed_at=_stamp(_NOW - timedelta(days=30)))
    _write_log(vault_automation_log_path(vault), "usage limit reached\nEXIT:75\n", timedelta(hours=1))
    assert _stale_findings(vault) == []


def test_stale_run_ignores_a_log_older_than_the_schedule(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    vault = _stale_vault(tmp_path, installed_at=_stamp(_NOW - timedelta(hours=1)))
    _write_log(tmp_path / "state" / "llmwiki" / "last-automation.log", "EXIT:1\n", timedelta(days=40))
    _write_log(vault_automation_log_path(vault), "EXIT:0\n", timedelta(days=40))
    assert _stale_findings(vault) == []


def test_stale_run_skips_the_shared_log_when_the_unit_names_its_own(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    vault = _stale_vault(tmp_path, installed_at=_stamp(_NOW - timedelta(days=30)))
    _write_log(tmp_path / "state" / "llmwiki" / "last-automation.log", "EXIT:0\n", timedelta(hours=1))
    unit = replace(_own_unit(vault, enabled=True), log_path=tmp_path / "unit-logs" / "never-written.log")
    (found,) = _stale_findings(vault, unit)
    assert "has not run since" in found.message


def test_stale_run_in_progress_is_quiet(tmp_path: Path) -> None:
    vault = _stale_vault(tmp_path, installed_at=_stamp(_NOW - timedelta(days=30)))
    _write_log(vault_automation_log_path(vault), "syncing...\n", timedelta(hours=1))
    assert _stale_findings(vault) == []


def test_stale_run_unfinished_old_log_judged_by_age(tmp_path: Path) -> None:
    vault = _stale_vault(tmp_path, installed_at=_stamp(_NOW - timedelta(days=30)))
    _write_log(vault_automation_log_path(vault), "syncing...\n", timedelta(days=5))
    (found,) = _stale_findings(vault)
    assert "last run was 5 days ago" in found.message


def test_stale_run_unit_log_wins_over_vault_log(tmp_path: Path) -> None:
    vault = _stale_vault(tmp_path, installed_at=_stamp(_NOW - timedelta(days=30)))
    _write_log(vault_automation_log_path(vault), "EXIT:2\n", timedelta(hours=1))
    unit_log = _write_log(tmp_path / "unit-logs" / "run.log", "EXIT:0\n", timedelta(hours=1))
    unit = replace(_own_unit(vault, enabled=True), log_path=unit_log)
    assert _stale_findings(vault, unit) == []


@pytest.mark.parametrize(
    ("vault_log_age", "expect"),
    [pytest.param(None, ["automation.stale_run"], id="legacy-used"), pytest.param(timedelta(hours=1), [], id="vault-log-wins")],
)
def test_stale_run_legacy_global_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, vault_log_age: timedelta | None, expect: list[str]
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    vault = _stale_vault(tmp_path, installed_at=_stamp(_NOW - timedelta(days=30)))
    _write_log(tmp_path / "state" / "llmwiki" / "last-automation.log", "EXIT:0\n", timedelta(days=4))
    if vault_log_age is not None:
        _write_log(vault_automation_log_path(vault), "EXIT:0\n", vault_log_age)
    found = _stale_findings(vault)
    assert [f.id for f in found] == expect
    if expect:
        assert "last run was 4 days ago" in found[0].message


@pytest.mark.parametrize(
    ("age_days", "warns"), [pytest.param(10, False, id="within-14d"), pytest.param(15, True, id="past-14d")]
)
def test_stale_run_weekly_schedule_uses_two_weeks(tmp_path: Path, age_days: int, warns: bool) -> None:
    vault = _stale_vault(tmp_path, schedule="0 6 * * 1", installed_at=_stamp(_NOW - timedelta(days=60)))
    _write_log(vault_automation_log_path(vault), "EXIT:0\n", timedelta(days=age_days))
    assert bool(_stale_findings(vault)) is warns


def test_stale_run_suppressed_by_points_elsewhere(tmp_path: Path) -> None:
    vault = _stale_vault(tmp_path, installed_at=_stamp(_NOW - timedelta(days=30)))
    other = _scaffold_vault(tmp_path / "other-vault")
    legacy = _unit(name="llmwiki-maintain", checkout=tmp_path / "worktree", target=other, legacy=True)
    found = check_automation(vault, now=_NOW, discovery=_discovery(legacy))
    assert [f.id for f in found] == ["automation.points_elsewhere"]


@pytest.mark.parametrize(
    ("extra", "warns"),
    [
        pytest.param({"updated_at": _stamp(_NOW - timedelta(days=3))}, True, id="updated-at-fallback"),
        pytest.param({}, False, id="no-stamp-skips"),
    ],
)
def test_stale_run_never_ran_without_installed_at(tmp_path: Path, extra: dict[str, Any], warns: bool) -> None:
    vault = _stale_vault(tmp_path, **extra)
    assert bool(_stale_findings(vault)) is warns


# ─── Leftover schedules for vanished vaults (@spec: 330-doctor-automation-serves-vault, R7) ───


def _orphan_findings(vault: Path, *units: InstalledUnit, unavailable: str | None = None) -> list[Finding]:
    found = check_automation(vault, discovery=_discovery(*units, unavailable=unavailable))
    return [f for f in found if f.id == "automation.orphan_unit"]


def test_orphan_unit_lists_the_leftover_with_its_removal_steps(tmp_path: Path) -> None:
    vault = _scaffold_vault(tmp_path / "vault")
    gone = tmp_path / "throwaway-vault"
    leftover = _unit(name=unit_names(gone).base, checkout=tmp_path / "checkout", target=gone)

    (found,) = _orphan_findings(vault, leftover)

    assert found.severity == "warning"
    assert (found.tier, found.runner) == ("guided", None)
    assert f"{leftover.name} (vault 'throwaway-vault')" in found.message
    assert f"systemctl --user disable --now {leftover.name}.timer" in found.message
    assert f"rm ~/.config/systemd/user/{leftover.name}.sh ~/.config/systemd/user/{leftover.name}.service" in found.message


@pytest.mark.parametrize("target", ["existing", None], ids=["target-exists", "target-unknown"])
def test_orphan_unit_quiet_unless_the_target_is_known_and_gone(tmp_path: Path, target: str | None) -> None:
    vault = _scaffold_vault(tmp_path / "vault")
    other = _scaffold_vault(tmp_path / "other-vault") if target else None
    unit = _unit(name="llmwiki-maintain-x", checkout=tmp_path / "checkout", target=other, reason="unknown")
    assert _orphan_findings(vault, unit) == []


def test_orphan_units_aggregate_into_one_finding(tmp_path: Path) -> None:
    vault = _scaffold_vault(tmp_path / "vault")
    first = _unit(name="llmwiki-maintain-a", checkout=tmp_path / "co", target=tmp_path / "gone-a")
    second = _unit(name="llmwiki-maintain-b", checkout=tmp_path / "co", target=tmp_path / "gone-b")

    (found,) = _orphan_findings(vault, first, second)

    assert "llmwiki-maintain-a (vault 'gone-a')" in found.message
    assert "llmwiki-maintain-b (vault 'gone-b')" in found.message


def test_orphan_unit_not_reported_when_scheduler_unavailable(tmp_path: Path) -> None:
    vault = _scaffold_vault(tmp_path / "vault")
    leftover = _unit(name="llmwiki-maintain-a", checkout=tmp_path / "co", target=tmp_path / "gone")
    assert _orphan_findings(vault, leftover, unavailable="no user bus") == []


def test_orphan_unit_is_independent_of_cause_suppression(tmp_path: Path) -> None:
    vault = _job_vault(tmp_path)
    legacy = _unit(name="llmwiki-maintain", checkout=tmp_path / "co", target=tmp_path / "gone", legacy=True)
    found = check_automation(vault, discovery=_discovery(legacy))
    assert [f.id for f in found] == ["automation.points_elsewhere", "automation.orphan_unit"]


def test_orphan_steps_are_home_relative(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    vault = _scaffold_vault(tmp_path / "vault")
    label = "com.llmwiki.maintain.gone-1234abcd"
    leftover = _unit(
        name=label, checkout=home / "Library" / "LaunchAgents", target=tmp_path / "gone", platform="macos"
    )
    leftover = replace(leftover, wrapper_path=home / "Library" / "LaunchAgents" / f"{label}.sh")

    (found,) = _orphan_findings(vault, leftover)

    assert f"launchctl bootout gui/$(id -u) {label}" in found.message
    assert f"rm ~/Library/LaunchAgents/{label}.plist ~/Library/LaunchAgents/{label}.sh" in found.message
    assert str(tmp_path) not in found.message


@pytest.mark.parametrize("status", [None, {"scheduler_activated": False}], ids=["no-status", "no-job"])
def test_without_a_job_only_leftovers_are_reported_and_the_scheduler_is_asked_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, status: dict[str, Any] | None
) -> None:
    """Doctor asks the scheduler once, for leftovers; nothing about this vault's own schedule fires."""
    vault = _scaffold_vault(tmp_path / "vault")
    if status is not None:
        save_status(vault, status)
    own = _own_unit(vault, enabled=False)
    elsewhere = _unit(name="llmwiki-maintain", checkout=tmp_path / "co", target=None, legacy=True, reason="x")
    leftover = _unit(name="llmwiki-maintain-a", checkout=tmp_path / "co", target=tmp_path / "gone")
    calls: list[None] = []

    def _probe(**_: object) -> DiscoveryResult:
        calls.append(None)
        return _discovery(own, elsewhere, leftover)

    monkeypatch.setattr("llmwiki.automation_units.discover_local_units", _probe)

    found = [f for f in run_checks_g_to_o(vault) if f.id.startswith("automation.")]

    assert [f.id for f in found] == ["automation.orphan_unit"]
    assert len(calls) == 1


def test_duplicate_legacy_unit_serving_this_vault_is_reported(tmp_path: Path) -> None:
    vault = _job_vault(tmp_path)
    legacy = _unit(name="llmwiki-maintain", checkout=tmp_path / "old", target=vault, legacy=True)
    found = check_automation(vault, now=_NOW, discovery=_discovery(_own_unit(vault, enabled=True), legacy))
    (dup,) = [f for f in found if f.id == "automation.duplicate_legacy"]
    assert (dup.severity, dup.tier, dup.runner) == ("warning", "guided", None)
    assert "two jobs run against it" in dup.message
    assert "systemctl --user disable --now llmwiki-maintain.timer" in dup.message


@pytest.mark.parametrize("target", ["other", None])
def test_duplicate_legacy_quiet_unless_the_legacy_unit_serves_this_vault(tmp_path: Path, target: str | None) -> None:
    vault = _job_vault(tmp_path)
    other = _scaffold_vault(tmp_path / "other")
    legacy = _unit(
        name="llmwiki-maintain",
        checkout=tmp_path / "old",
        target=other if target else None,
        legacy=True,
        reason=None if target else "unknown",
    )
    found = check_automation(vault, now=_NOW, discovery=_discovery(_own_unit(vault, enabled=True), legacy))
    assert "automation.duplicate_legacy" not in [f.id for f in found]


@pytest.mark.parametrize(("job", "probe"), [(False, False), (True, True)])
def test_scheduler_is_asked_about_liveness_only_when_a_job_is_recorded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, job: bool, probe: bool
) -> None:
    vault = _job_vault(tmp_path) if job else _scaffold_vault(tmp_path / "plain")
    seen: list[bool] = []

    def _probe(*, probe: bool = True) -> DiscoveryResult:
        seen.append(probe)
        return _discovery()

    monkeypatch.setattr("llmwiki.automation_units.discover_local_units", _probe)
    check_automation(vault, now=_NOW)
    assert seen == [probe]
