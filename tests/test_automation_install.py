"""Tests for automation install renderers + status + hook merge.

The three unit renderers are pinned byte-for-byte on the default daily schedule:
an existing install must not silently change shape when the schedule notation does.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

from llmwiki import cli
from llmwiki.automation_install import (
    HOOK_MARKER,
    merge_claude_session_start_hook,
    merge_cursor_session_start_hook,
    render_launchd_plist,
    render_systemd_timer,
    render_windows_task,
    run_install,
)
from llmwiki.automation_plan import AutomationPlan, LintFail, plan_command, plan_to_status
from llmwiki.automation_status import load_status, status_path
from llmwiki.build import render_automation_panel
from llmwiki.cron_spec import parse_cron

DAILY = parse_cron("0 8 * * *")
WEEKDAYS = parse_cron("0 8 * * 1-5")

WRAPPER = Path("/opt/wiki/units/llmwiki-maintain.sh")
WORKING_DIR = Path("/opt/wiki")
LOG_PATH = Path("/var/log/llmwiki-automation.log")

DAILY_TIMER = """[Unit]
Description=llmwiki maintain daily timer

[Timer]
OnCalendar=*-*-* 08:00:00
Persistent=true

[Install]
WantedBy=timers.target
"""

DAILY_PLIST = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.llmwiki.maintain</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>/opt/wiki/units/llmwiki-maintain.sh</string>
  </array>
  <key>WorkingDirectory</key>
  <string>/opt/wiki</string>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>8</integer>
    <key>Minute</key>
    <integer>0</integer>
  </dict>
  <key>StandardOutPath</key>
  <string>/var/log/llmwiki-automation.log</string>
  <key>StandardErrorPath</key>
  <string>/var/log/llmwiki-automation.log</string>
</dict>
</plist>
"""

DAILY_TASK = """<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>llmwiki maintain (managed)</Description>
  </RegistrationInfo>
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>2026-01-01T08:00:00</StartBoundary>
      <Enabled>true</Enabled>
      <ScheduleByDay>
        <DaysInterval>1</DaysInterval>
      </ScheduleByDay>
    </CalendarTrigger>
  </Triggers>
  <Actions>
    <Exec>
      <Command>bash</Command>
      <Arguments>/opt/wiki/units/llmwiki-maintain.sh</Arguments>
      <WorkingDirectory>/opt/wiki</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"""


def test_systemd_timer_persistent_and_time():
    text = render_systemd_timer(spec=DAILY)
    assert "Persistent=true" in text
    assert "08:00:00" in text


def test_daily_systemd_timer_is_byte_identical():
    assert render_systemd_timer(spec=DAILY) == DAILY_TIMER


def test_daily_launchd_plist_is_byte_identical():
    """A one-firing schedule keeps its single ``<dict>``, not a one-element ``<array>``."""
    rendered = render_launchd_plist(
        wrapper=WRAPPER, working_dir=WORKING_DIR, log_path=LOG_PATH, spec=DAILY
    )
    assert rendered == DAILY_PLIST


def test_daily_windows_task_is_byte_identical():
    rendered = render_windows_task(wrapper=WRAPPER, working_dir=WORKING_DIR, spec=DAILY)
    assert rendered == DAILY_TASK


def test_weekday_schedule_renders_systemd_range():
    assert "OnCalendar=Mon-Fri *-*-* 08:00:00\n" in render_systemd_timer(spec=WEEKDAYS)


def test_weekday_schedule_renders_five_launchd_entries():
    rendered = render_launchd_plist(
        wrapper=WRAPPER, working_dir=WORKING_DIR, log_path=LOG_PATH, spec=WEEKDAYS
    )
    assert "<array>" in rendered
    assert [line.strip() for line in rendered.splitlines()].count("<dict>") == 6  # 5 intervals + the outer plist dict
    for weekday in range(1, 6):
        assert f"<key>Weekday</key>\n      <integer>{weekday}</integer>" in rendered


def test_hook_merge_idempotent():
    settings: dict = {"hooks": {}}
    cmd = "python3 -m llmwiki sync"
    once = merge_claude_session_start_hook(settings, cmd, install=True)
    twice = merge_claude_session_start_hook(once, cmd, install=True)
    blob = json.dumps(twice)
    assert blob.count(HOOK_MARKER) == 1
    removed = merge_claude_session_start_hook(twice, cmd, install=False)
    assert HOOK_MARKER not in json.dumps(removed)


def test_cursor_hook_merge_idempotent():
    hooks = {"version": 1, "hooks": {}}
    cmd = "python3 -m llmwiki sync"
    once = merge_cursor_session_start_hook(hooks, cmd, install=True)
    twice = merge_cursor_session_start_hook(once, cmd, install=True)
    assert json.dumps(twice).count(HOOK_MARKER) == 1


def _install(tmp_path: Path, **overrides) -> tuple[dict, Path, Path]:
    """Run an install into a throwaway vault, returning (status, vault, units dir)."""
    vault = tmp_path / "vault"
    vault.mkdir(exist_ok=True)
    units = tmp_path / "units"
    config = {
        "working_dir": tmp_path,
        "python_bin": "python3",
        "vault_root": vault,
        "write_units_dir": units,
        "force_platform": "linux",
        "synth_backend": "dummy",
    }
    config.update(overrides)
    return run_install(config), vault, units


def test_run_install_writes_status_and_units(tmp_path: Path):
    status, vault, units = _install(tmp_path, plan=AutomationPlan(job="ingest"), schedule="0 8 * * *")
    assert status["job"] == "ingest"
    assert status["profile"] == "A"
    loaded = load_status(vault)
    assert loaded is not None
    assert loaded["hour"] == 8
    assert (units / "llmwiki-maintain.timer").is_file()
    assert (units / "llmwiki-maintain.sh").is_file()
    assert "no-op" in (loaded.get("note") or "")


def test_run_install_accepts_legacy_profile_hour_minute(tmp_path: Path):
    """The un-migrated caller passes a profile letter and clock integers; it must keep working."""
    status, vault, units = _install(tmp_path, profile="B", hour=6, minute=30)
    assert status["job"] == "maintain"
    assert status["schedule"] == "30 6 * * *"
    assert status["hour"] == 6
    assert status["minute"] == 30
    assert "OnCalendar=*-*-* 06:30:00" in (units / "llmwiki-maintain.timer").read_text(encoding="utf-8")
    expected = plan_command(AutomationPlan(job="maintain"), python_bin="python3", working_dir=tmp_path)
    assert expected in (units / "llmwiki-maintain.sh").read_text(encoding="utf-8")
    assert load_status(vault) is not None


def test_run_install_defaults_to_ingest_at_eight(tmp_path: Path):
    """No plan and no schedule in the config is the documented daily ingest install."""
    status, _vault, _units = _install(tmp_path)
    assert status["job"] == "ingest"
    assert status["schedule"] == "0 8 * * *"


@pytest.mark.parametrize(
    "plan",
    [
        AutomationPlan(job="ingest"),
        AutomationPlan(job="maintain"),
        AutomationPlan(job="maintain", graph="builtin"),
        AutomationPlan(job="maintain", graph="graphify", lint_fail="warnings"),
    ],
)
def test_wrapper_command_line_is_plan_command(tmp_path: Path, plan: AutomationPlan):
    _status, _vault, units = _install(tmp_path, plan=plan)
    expected = plan_command(plan, python_bin="python3", working_dir=tmp_path)
    wrapper_lines = (units / "llmwiki-maintain.sh").read_text(encoding="utf-8").splitlines()
    command_line = next(line for line in wrapper_lines if line.startswith("{ "))
    assert command_line.startswith(f"{{ {expected} ; echo EXIT:$?; }}")


def test_status_carries_new_and_legacy_keys(tmp_path: Path):
    plan = AutomationPlan(job="maintain", graph="builtin", lint_fail="errors")
    _status, vault, _units = _install(tmp_path, plan=plan, schedule="0 8 * * 1-5")
    loaded = load_status(vault)
    assert loaded is not None
    assert loaded["job"] == "maintain"
    assert loaded["graph"] == "builtin"
    assert loaded["lint_fail"] == "errors"
    assert loaded["schedule"] == "0 8 * * 1-5"
    assert loaded["schedule_label"] == "Weekdays at 08:00"
    assert loaded["label"] == "Maintain + graph (built-in) + fail on errors"
    # Legacy keys stay so an older llmwiki reading this file still renders a profile and a time.
    assert loaded["profile"] == "B"
    assert loaded["hour"] == 8
    assert loaded["minute"] == 0


# ─── The setup wizard ──────────────────────────────────────────────────

ENTER = ""


def _script_input(monkeypatch: pytest.MonkeyPatch, answers: list[str]) -> list[str]:
    """Answer ``input()`` from a script, returning the list prompts accumulate into.

    Running out of answers raises ``EOFError`` — the same thing a piped stdin
    does — so a question the wizard should not have asked cannot hang the test.
    """
    prompts: list[str] = []
    remaining = list(answers)

    def fake_input(prompt: str = "") -> str:
        prompts.append(prompt)
        if not remaining:
            raise EOFError
        return remaining.pop(0)

    monkeypatch.setattr("builtins.input", fake_input)
    return prompts


def _run_wizard(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    answers: list[str],
    *,
    flags: tuple[str, ...] = (),
) -> tuple[int, dict, list[str]]:
    """Drive the interactive wizard with scripted answers.

    Returns the exit code, the config the wizard handed to ``run_install``, and
    every prompt that was displayed. ``REPO_ROOT`` is redirected at ``tmp_path``
    so nothing the wizard writes can land in the repo.
    """
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    captured: dict = {}

    def fake_run_install(config: dict) -> dict:
        captured.update(config)
        return {"log_path": str(tmp_path / "automation.log"), "units_written": []}

    monkeypatch.setattr(cli, "run_install", fake_run_install)
    prompts = _script_input(monkeypatch, answers)
    args = cli.build_parser().parse_args(
        ["install-automation", "--vault", str(tmp_path / "vault"), *flags]
    )
    return cli.cmd_install_automation(args), captured, prompts


def test_wizard_enter_through_yields_ingest_and_skips_the_maintain_questions(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """Pressing Enter at every question installs the free, no-provider daily job."""
    code, config, prompts = _run_wizard(monkeypatch, tmp_path, [ENTER] * 8)
    assert code == 0
    assert config["plan"] == AutomationPlan(job="ingest")
    assert config["schedule"] == "0 8 * * *"
    asked = " ".join(prompts)
    assert "Extras" not in asked
    assert "Builder" not in asked


def test_wizard_maintain_with_extras_produces_the_expected_plan_and_command(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    code, config, _prompts = _run_wizard(
        monkeypatch,
        tmp_path,
        ["2", "1,2", "1", "1", "09:15", ENTER, ENTER, ENTER, ENTER, "y"],
    )
    expected = AutomationPlan(job="maintain", graph="builtin", lint_fail="errors")
    assert code == 0
    assert config["plan"] == expected
    assert config["schedule"] == "15 9 * * *"
    out = capsys.readouterr().out
    assert plan_command(expected, python_bin=sys.executable, working_dir=tmp_path) in out
    assert "Maintain + graph (built-in) + fail on errors" in out
    assert "Every day at 09:15" in out
    assert "synth --estimate" in out


def test_wizard_accepts_the_legacy_profile_letters(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    _code, config, _prompts = _run_wizard(
        monkeypatch, tmp_path, ["B", ENTER, ENTER, ENTER, ENTER, ENTER, ENTER, "y"]
    )
    assert config["plan"] == AutomationPlan(job="maintain")


def test_wizard_reasks_instead_of_defaulting_on_an_unrecognised_answer(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    _code, config, prompts = _run_wizard(
        monkeypatch, tmp_path, ["banana", "2", ENTER, ENTER, ENTER, ENTER, ENTER, ENTER, "y"]
    )
    assert prompts.count("Choice [1]: ") == 2
    assert "is not one of" in capsys.readouterr().out
    assert config["plan"].job == "maintain"


def test_wizard_both_failure_policies_resolve_to_the_stricter_one(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    _code, config, prompts = _run_wizard(
        monkeypatch, tmp_path, ["2", "2,3", ENTER, ENTER, ENTER, ENTER, ENTER, "y"]
    )
    assert config["plan"] == AutomationPlan(job="maintain", lint_fail="warnings")
    assert "stricter" in capsys.readouterr().out
    # The graph extra was not chosen, so the builder question stays away.
    assert not [p for p in prompts if p.startswith("Builder")]


def test_wizard_warns_but_continues_when_graphify_is_not_installed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    monkeypatch.setattr(cli, "is_available", lambda: False)
    _code, config, _prompts = _run_wizard(
        monkeypatch, tmp_path, ["2", "1", "2", ENTER, ENTER, ENTER, ENTER, ENTER, ENTER, "y"]
    )
    out = capsys.readouterr().out
    assert config["plan"] == AutomationPlan(job="maintain", graph="graphify")
    assert "falls back to the built-in builder" in out
    assert "pip install llm-wiki[graph]" in out


def test_wizard_weekday_preset_produces_a_weekday_cron(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    _code, config, _prompts = _run_wizard(
        monkeypatch, tmp_path, [ENTER, "2", "07:30", ENTER, ENTER, ENTER, ENTER, "y"]
    )
    assert config["schedule"] == "30 7 * * 1-5"


def test_wizard_weekly_preset_asks_for_a_day(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    _code, config, prompts = _run_wizard(
        monkeypatch, tmp_path, [ENTER, "3", "3", "18:00", ENTER, ENTER, ENTER, ENTER, "y"]
    )
    assert config["schedule"] == "0 18 * * 3"
    assert "Day [1]: " in prompts


def test_wizard_reasks_a_cron_expression_it_cannot_translate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    _code, config, prompts = _run_wizard(
        monkeypatch, tmp_path, [ENTER, "4", "@daily", "0 9 * * 6", ENTER, ENTER, ENTER, ENTER, "y"]
    )
    out = capsys.readouterr().out
    assert config["schedule"] == "0 9 * * 6"
    assert prompts.count("Cron expression [0 8 * * *]: ") == 2
    assert "@daily" in out and "Nicknames" in out


def test_wizard_declining_the_confirmation_writes_nothing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    """No status file, no unit files, and no config.json change when the user says no."""
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    vault = tmp_path / "vault"
    vault.mkdir()
    _script_input(monkeypatch, ["2", ENTER, ENTER, ENTER, "ollama", ENTER, ENTER, ENTER, "n"])
    args = cli.build_parser().parse_args(["install-automation", "--vault", str(vault)])
    assert cli.cmd_install_automation(args) == 0
    assert "Nothing written" in capsys.readouterr().out
    assert load_status(vault) is None
    assert not (tmp_path / ".llmwiki").exists()
    assert not (tmp_path / "config.json").exists()


# ─── Non-interactive flags ─────────────────────────────────────────────


def _install_via_flags(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *flags: str) -> tuple[int, Path, Path]:
    """Run a `--yes` install into a throwaway vault, returning (exit code, vault, units dir)."""
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    vault = tmp_path / "vault"
    vault.mkdir(exist_ok=True)
    units = tmp_path / "units"
    code = cli.main([
        "install-automation", "--yes",
        "--units-dir", str(units),
        "--vault", str(vault),
        "--force-platform", "linux",
        *flags,
    ])
    return code, vault, units


def test_flags_produce_the_same_install_as_the_wizard_answers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    code, vault, units = _install_via_flags(
        tmp_path, monkeypatch,
        "--job", "maintain", "--graph", "builtin", "--lint-fail", "errors",
        "--schedule", "0 8 * * 1-5",
    )
    assert code == 0
    status = load_status(vault)
    assert status is not None
    assert (status["job"], status["graph"], status["lint_fail"]) == ("maintain", "builtin", "errors")
    assert status["schedule"] == "0 8 * * 1-5"
    expected = plan_command(
        AutomationPlan(job="maintain", graph="builtin", lint_fail="errors"),
        python_bin=sys.executable,
        working_dir=tmp_path,
    )
    assert expected in (units / "llmwiki-maintain.sh").read_text(encoding="utf-8")
    assert "OnCalendar=Mon-Fri *-*-* 08:00:00" in (units / "llmwiki-maintain.timer").read_text(encoding="utf-8")


def test_deprecated_profile_flag_still_installs_and_names_its_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    code, vault, _units = _install_via_flags(tmp_path, monkeypatch, "--profile", "B")
    status = load_status(vault)
    assert code == 0
    assert status is not None and status["job"] == "maintain"
    assert "--profile is deprecated" in capsys.readouterr().err


def test_deprecated_hour_and_minute_become_a_daily_cron(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    code, vault, _units = _install_via_flags(tmp_path, monkeypatch, "--hour", "6", "--minute", "30")
    status = load_status(vault)
    assert code == 0
    assert status is not None and status["schedule"] == "30 6 * * *"
    assert "--hour/--minute are deprecated" in capsys.readouterr().err


def test_schedule_wins_over_the_deprecated_clock_flags(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    code, vault, _units = _install_via_flags(
        tmp_path, monkeypatch, "--schedule", "0 9 * * *", "--hour", "6"
    )
    status = load_status(vault)
    assert code == 0
    assert status is not None and status["schedule"] == "0 9 * * *"
    assert "--hour/--minute are ignored" in capsys.readouterr().err


def test_job_wins_over_profile_with_a_note(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    code, vault, _units = _install_via_flags(tmp_path, monkeypatch, "--job", "ingest", "--profile", "B")
    status = load_status(vault)
    assert code == 0
    assert status is not None and status["job"] == "ingest"
    assert "--profile is ignored" in capsys.readouterr().err


def test_an_untranslatable_schedule_exits_two_with_the_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    code, vault, units = _install_via_flags(tmp_path, monkeypatch, "--schedule", "@daily")
    assert code == 2
    assert "@daily" in capsys.readouterr().err
    assert not units.exists()
    assert load_status(vault) is None


# ─── The Home Automation panel ─────────────────────────────────────────


def _panel(vault: Path, status: dict[str, Any]) -> str:
    """Render the Home Automation panel for a vault whose status file holds ``status``."""
    path = status_path(vault)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(status), encoding="utf-8")
    return render_automation_panel(vault)


def test_panel_names_the_job_and_the_schedule_in_words(tmp_path: Path):
    plan = AutomationPlan(job="maintain", graph="builtin")
    panel = _panel(tmp_path, {**plan_to_status(plan), "schedule": "0 8 * * 1-5", "schedule_label": "Weekdays at 08:00"})
    assert "Maintain + graph (built-in)" in panel
    assert "Weekdays at 08:00" in panel


def test_panel_reads_a_legacy_letter_only_status_as_words(tmp_path: Path):
    panel = _panel(tmp_path, {"profile": "B", "hour": 8, "minute": 0})
    assert "Maintain" in panel
    assert "Every day at 08:00" in panel
    # The letter itself never reaches the page.
    assert "Scheduler profile" not in panel
    assert "<strong>B</strong>" not in panel


def test_panel_states_that_maintain_can_spend_money(tmp_path: Path):
    panel = _panel(tmp_path, plan_to_status(AutomationPlan(job="maintain")))
    assert "can spend money at your AI provider" in panel
    assert "llmwiki synth --estimate" in panel


def test_panel_states_that_ingest_cannot_spend_money(tmp_path: Path):
    panel = _panel(tmp_path, plan_to_status(AutomationPlan(job="ingest")))
    assert "cannot spend money at your AI provider" in panel


@pytest.mark.parametrize(
    ("lint_fail", "expected"),
    [("never", False), ("errors", True), ("warnings", True)],
)
def test_panel_mentions_the_failure_policy_only_when_one_is_set(tmp_path: Path, lint_fail: LintFail, expected: bool):
    plan = AutomationPlan(job="maintain", lint_fail=lint_fail)
    panel = _panel(tmp_path, plan_to_status(plan))
    assert ("mark the scheduled run as failed" in panel) is expected


def test_panel_survives_a_malformed_status_file(tmp_path: Path):
    """A truncated or hand-edited status file degrades to readable wording, never an exception."""
    assert "No automation configured" in _panel(tmp_path, {})
    panel = _panel(tmp_path, {"profile": "Z", "schedule": "@daily", "hour": "eight"})
    assert "Ingest only" in panel
    assert "Every day at 08:00" in panel
