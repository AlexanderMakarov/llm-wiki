"""The scheduled job stamps its runs so Home can tell a missed run (and an outdated setup).

# @spec: 374-no-silent-automation-failure
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from llmwiki import automation_install, cli, pipeline, run_outcomes
from llmwiki.automation_install import render_wrapper_script, run_install
from llmwiki.automation_plan import AutomationPlan
from llmwiki.automation_status import save_status
from llmwiki.cli import build_parser
from llmwiki.state_store import read_state


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    root = tmp_path / "vault"
    for sub in ("raw/sessions", "raw/docs", "wiki", "site"):
        (root / sub).mkdir(parents=True)
    return root


def _outcomes(vault: Path) -> dict:
    return read_state(vault / "llmwiki-state.json")["outcomes"]


def _activated(vault: Path) -> None:
    save_status(vault, {"job": "maintain", "schedule": "0 9 * * *", "scheduler_activated": True})


def _configure(vault: Path) -> None:
    run_outcomes.configure_schedule(
        interval_s=86400, installed_at="2026-10-23T05:22:41Z",
        log_path=str(vault / ".llmwiki" / "last-automation.log"),
        state_file=vault / "llmwiki-state.json",
    )


def _run_all(vault: Path, *, raises: BaseException | None = None) -> int:
    args = build_parser().parse_args(
        ["all", "--no-sync", "--no-synth", "--skip-graph", "--skip-lint", "--vault", str(vault)]
    )
    build = MagicMock(side_effect=raises) if raises else MagicMock(return_value=0)
    with patch.object(pipeline, "build_site", build):
        return cli.cmd_all(args)


# ─── wrapper and install ──────────────────────────────────────────────────


def test_the_wrapper_marks_its_runs_as_scheduled(tmp_path: Path):
    text = render_wrapper_script(
        plan=AutomationPlan(job="maintain"), python_bin="/usr/bin/python3",
        working_dir=tmp_path, log_path=tmp_path / "log", vault=tmp_path,
    )
    lines = text.splitlines()
    assert "export LLMWIKI_SCHEDULED_RUN=1" in lines
    assert lines.index("export LLMWIKI_SCHEDULED_RUN=1") < next(
        i for i, line in enumerate(lines) if "-m llmwiki" in line
    )


def test_an_activated_install_records_the_schedule_for_home(vault: Path, tmp_path: Path):
    with patch.object(automation_install, "activate_scheduler",
                      return_value={"scheduler_activated": True, "scheduler_active": True}):
        run_install({
            "working_dir": tmp_path, "python_bin": "python3", "vault_root": vault,
            "write_units_dir": tmp_path / "units", "force_platform": "linux",
            "activate": True, "schedule": "0 9 * * *",
        })
    scheduled = _outcomes(vault)["scheduled"]
    assert scheduled["marker"] == run_outcomes.SCHEDULE_MARKER
    assert scheduled["interval_s"] == 86400
    assert scheduled["grace_s"] == 7200
    assert scheduled["installed_at"]
    assert scheduled["log_path"] == str(vault / ".llmwiki" / "last-automation.log")


def test_an_install_without_activation_records_no_schedule(vault: Path, tmp_path: Path):
    run_install({
        "working_dir": tmp_path, "python_bin": "python3", "vault_root": vault,
        "write_units_dir": tmp_path / "units", "force_platform": "linux", "activate": False,
    })
    assert "scheduled" not in _outcomes(vault)


def test_reinstalling_keeps_the_last_run_and_clears_setup_outdated(vault: Path):
    state_file = vault / "llmwiki-state.json"
    _activated(vault)
    run_outcomes.check_schedule_setup(vault, state_file=state_file)
    run_outcomes.stamp_scheduled_run(exit_code=0, state_file=state_file, when="2026-10-30T05:03:00Z")
    _configure(vault)
    outcomes = _outcomes(vault)
    assert "setup_outdated" not in outcomes
    assert outcomes["scheduled"]["last_run_at"] == "2026-10-30T05:03:00Z"


# ─── stamping runs ────────────────────────────────────────────────────────


def test_a_scheduled_all_stamps_its_end(vault: Path, monkeypatch):
    _activated(vault)
    _configure(vault)
    monkeypatch.setenv(run_outcomes.SCHEDULED_ENV, "1")
    assert _run_all(vault) == 0
    scheduled = _outcomes(vault)["scheduled"]
    assert scheduled["exit_code"] == 0
    assert scheduled["last_run_at"]


def test_a_manual_all_does_not_stamp(vault: Path, monkeypatch):
    _activated(vault)
    _configure(vault)
    monkeypatch.delenv(run_outcomes.SCHEDULED_ENV, raising=False)
    _run_all(vault)
    assert _outcomes(vault)["scheduled"]["last_run_at"] is None


def test_a_scheduled_run_that_crashes_still_stamps_a_failure(vault: Path, monkeypatch):
    _activated(vault)
    _configure(vault)
    monkeypatch.setenv(run_outcomes.SCHEDULED_ENV, "1")
    with pytest.raises(OSError):
        _run_all(vault, raises=OSError("disk full"))
    assert _outcomes(vault)["scheduled"]["exit_code"] == 1


def test_a_scheduled_sync_job_stamps_its_end(vault: Path, monkeypatch):
    _activated(vault)
    _configure(vault)
    monkeypatch.setenv(run_outcomes.SCHEDULED_ENV, "1")
    args = build_parser().parse_args(["sync", "--no-auto-build", "--vault", str(vault)])
    with patch("llmwiki.cli.convert_all", return_value=0), \
         patch("llmwiki.cli.refresh_synth_pending"), \
         patch("llmwiki.cli.plan_reindex", return_value=None):
        assert cli.cmd_sync(args) == 0
    assert _outcomes(vault)["scheduled"]["exit_code"] == 0


# ─── outdated setup ───────────────────────────────────────────────────────


def test_a_schedule_installed_before_run_stamping_is_flagged(vault: Path):
    _activated(vault)
    _run_all(vault)
    note = _outcomes(vault)["setup_outdated"]
    assert "Re-run `llmwiki install-automation`" in note["detail"]


def test_a_current_schedule_is_not_flagged(vault: Path):
    _activated(vault)
    _configure(vault)
    _run_all(vault)
    assert "setup_outdated" not in _outcomes(vault)


def test_without_an_activated_schedule_the_schedule_records_go_away(vault: Path):
    _configure(vault)
    _run_all(vault)
    outcomes = _outcomes(vault)
    assert "scheduled" not in outcomes
    assert "setup_outdated" not in outcomes


def test_a_clean_scheduled_sync_clears_an_earlier_crash(vault: Path, monkeypatch):
    """The ingest schedule runs `sync`; once it finishes cleanly its crash entry goes away."""
    _activated(vault)
    _configure(vault)
    monkeypatch.setenv(run_outcomes.SCHEDULED_ENV, "1")
    args = build_parser().parse_args(["sync", "--no-auto-build", "--vault", str(vault)])
    with patch("llmwiki.cli.refresh_synth_pending"), \
         patch("llmwiki.cli.plan_reindex", return_value=None):
        with patch("llmwiki.cli.convert_all", side_effect=OSError("disk full")), \
             pytest.raises(OSError):
            cli.cmd_sync(args)
        assert "run" in _outcomes(vault)["parts"]
        with patch("llmwiki.cli.convert_all", return_value=0):
            assert cli.cmd_sync(args) == 0
    assert "run" not in _outcomes(vault)["parts"]
