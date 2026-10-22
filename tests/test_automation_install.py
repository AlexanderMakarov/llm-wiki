"""Tests for automation install renderers + status + hook merge.

The three unit renderers are pinned byte-for-byte on the default daily schedule:
an existing install must not silently change shape when the schedule notation does.
"""

from __future__ import annotations

import io
import json
import os
import re
import shlex
import subprocess
import sys
import textwrap
import xml.etree.ElementTree as ET
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from llmwiki import cli
from llmwiki.automation_install import (
    HOOK_MARKER,
    AutomationActivationError,
    activate_scheduler,
    default_scheduler_units_dir,
    merge_claude_session_start_hook,
    merge_cursor_session_start_hook,
    render_launchd_plist,
    render_systemd_service,
    render_systemd_timer,
    render_windows_task,
    render_wrapper_script,
    run_install,
)
from llmwiki.automation_plan import AutomationPlan, LintFail, plan_command, plan_to_status
from llmwiki.automation_status import load_status, status_path
from llmwiki.automation_units import (
    LEGACY_LAUNCHD,
    LEGACY_SYSTEMD,
    DiscoveryResult,
    InstalledUnit,
    WrapperCommand,
    deactivate_unit,
    discover_units,
    is_dev_checkout,
    legacy_unit_serving,
    parse_wrapper,
    removal_steps,
    unit_for_vault,
    unit_names,
    vault_unit_id,
)
from llmwiki.build import render_automation_panel
from llmwiki.claude_path import resolve_claude_path
from llmwiki.config_schedule import default_vault_for_checkout
from llmwiki.cron_spec import parse_cron
from llmwiki.doctor.checks import _orphan_finding
from llmwiki.install_hint import pip_install_command

DAILY = parse_cron("0 8 * * *")
WEEKDAYS = parse_cron("0 8 * * 1-5")

WRAPPER = Path("/opt/wiki/units/llmwiki-maintain.sh")
WORKING_DIR = Path("/opt/wiki")
LOG_PATH = Path("/var/log/llmwiki-automation.log")

# A vault root nobody would choose on purpose, but every character in it is legal in a
# POSIX path and lethal to an XML parser if it reaches the document unescaped.
XML_HOSTILE_DIR = Path("/opt/R&D <wiki>")
XML_HOSTILE_WRAPPER = XML_HOSTILE_DIR / "units" / "llmwiki-maintain.sh"
XML_HOSTILE_LOG = XML_HOSTILE_DIR / "last-automation.log"

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


def test_systemd_timer_includes_vault_hint_when_provided():
    text = render_systemd_timer(spec=DAILY, vault_hint="my-vault")
    assert "vault my-vault" in text
    assert "Persistent=true" in text


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


def test_launchd_plist_escapes_paths_so_the_plist_still_parses():
    """A vault or home directory holding ``&``/``<``/``>`` must not produce a plist
    launchd refuses with an opaque parse error."""
    rendered = render_launchd_plist(
        wrapper=XML_HOSTILE_WRAPPER,
        working_dir=XML_HOSTILE_DIR,
        log_path=XML_HOSTILE_LOG,
        spec=DAILY,
    )
    texts = {element.text for element in ET.fromstring(rendered).iter()}
    assert {str(XML_HOSTILE_WRAPPER), str(XML_HOSTILE_DIR), str(XML_HOSTILE_LOG)} <= texts
    assert "&amp;" in rendered


def test_windows_task_escapes_paths_so_the_task_xml_still_parses():
    rendered = render_windows_task(
        wrapper=XML_HOSTILE_WRAPPER, working_dir=XML_HOSTILE_DIR, spec=DAILY
    )
    texts = {element.text for element in ET.fromstring(rendered).iter()}
    assert {str(XML_HOSTILE_WRAPPER), str(XML_HOSTILE_DIR)} <= texts
    assert "&amp;" in rendered


def test_escaping_leaves_ordinary_paths_byte_identical():
    """Escaping is a no-op on a path with nothing to escape — the pinned renderings above
    stay valid, and this says so explicitly rather than leaving it implied."""
    assert render_launchd_plist(
        wrapper=WRAPPER, working_dir=WORKING_DIR, log_path=LOG_PATH, spec=DAILY
    ) == DAILY_PLIST
    assert render_windows_task(wrapper=WRAPPER, working_dir=WORKING_DIR, spec=DAILY) == DAILY_TASK


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
        "activate": False,
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
    assert status["log_path"] == str(vault / ".llmwiki" / "last-automation.log")
    assert (units / unit_names(tmp_path / "vault").timer).is_file()
    assert (units / unit_names(tmp_path / "vault").wrapper).is_file()
    assert "no-op" in (loaded.get("note") or "")


def test_run_install_accepts_legacy_profile_hour_minute(tmp_path: Path):
    """The un-migrated caller passes a profile letter and clock integers; it must keep working."""
    status, vault, units = _install(tmp_path, profile="B", hour=6, minute=30)
    assert status["job"] == "maintain"
    assert status["schedule"] == "30 6 * * *"
    assert status["hour"] == 6
    assert status["minute"] == 30
    assert "OnCalendar=*-*-* 06:30:00" in (units / unit_names(tmp_path / "vault").timer).read_text(encoding="utf-8")
    expected = plan_command(AutomationPlan(job="maintain"), python_bin="python3", working_dir=tmp_path)
    assert expected in (units / unit_names(tmp_path / "vault").wrapper).read_text(encoding="utf-8")
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
    expected = plan_command(
        plan, python_bin="python3", working_dir=tmp_path, vault=(tmp_path / "vault").resolve()
    )
    wrapper_lines = (units / unit_names(tmp_path / "vault").wrapper).read_text(encoding="utf-8").splitlines()
    command_line = next(line for line in wrapper_lines if line.startswith("{ "))
    assert command_line.startswith(f"{{ rc=0; {expected} || rc=$?; echo \"EXIT:$rc\"; }}")


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


class _TerminalStdin(io.StringIO):
    """A stdin stand-in whose ``isatty`` is true, the way a real wizard run needs."""

    def isatty(self) -> bool:
        return True


def _pretend_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Satisfy the wizard's terminal guard; the answers themselves stay scripted."""
    monkeypatch.setattr(sys, "stdin", _TerminalStdin())


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
    _pretend_tty(monkeypatch)
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


def test_wizard_enter_through_defaults_to_maintain_with_no_extras(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """Pressing Enter at every question installs Maintain with no extras."""
    code, config, prompts = _run_wizard(
        monkeypatch, tmp_path, [ENTER, ENTER, ENTER, ENTER, ENTER, ENTER, ENTER, ENTER, "y"]
    )
    assert code == 0
    assert config["plan"] == AutomationPlan(job="maintain")
    assert config["schedule"] == "0 8 * * *"
    asked = " ".join(prompts)
    assert "Extras" in asked


def test_wizard_explicit_ingest_skips_maintain_questions(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """Choosing 1 installs the free, no-provider daily job without extras."""
    code, config, prompts = _run_wizard(
        monkeypatch, tmp_path, ["1", ENTER, ENTER, ENTER, ENTER, ENTER, ENTER, "y"]
    )
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
        monkeypatch, tmp_path, ["B", ENTER, ENTER, ENTER, ENTER, ENTER, ENTER, ENTER, "y"]
    )
    assert config["plan"] == AutomationPlan(job="maintain")


def test_wizard_reasks_instead_of_defaulting_on_an_unrecognised_answer(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    _code, config, prompts = _run_wizard(
        monkeypatch, tmp_path, ["banana", "2", ENTER, ENTER, ENTER, ENTER, ENTER, ENTER, ENTER, "y"]
    )
    assert prompts.count("Choice [2]: ") == 2
    assert "is not one of" in capsys.readouterr().out
    assert config["plan"].job == "maintain"


def test_wizard_both_failure_policies_resolve_to_the_stricter_one(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    _code, config, prompts = _run_wizard(
        monkeypatch, tmp_path, ["2", "2,3", ENTER, ENTER, ENTER, ENTER, ENTER, ENTER, "y"]
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
    assert pip_install_command("graph") in out


def test_wizard_weekday_preset_produces_a_weekday_cron(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    _code, config, _prompts = _run_wizard(
        monkeypatch, tmp_path, ["1", "2", "07:30", ENTER, ENTER, ENTER, ENTER, "y"]
    )
    assert config["schedule"] == "30 7 * * 1-5"


def test_wizard_weekly_preset_asks_for_a_day(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    _code, config, prompts = _run_wizard(
        monkeypatch, tmp_path, ["1", "3", "3", "18:00", ENTER, ENTER, ENTER, ENTER, "y"]
    )
    assert config["schedule"] == "0 18 * * 3"
    assert "Day [1]: " in prompts


def test_wizard_reasks_a_cron_expression_it_cannot_translate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    _code, config, prompts = _run_wizard(
        monkeypatch, tmp_path, ["1", "4", "@daily", "0 9 * * 6", ENTER, ENTER, ENTER, ENTER, "y"]
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
    _pretend_tty(monkeypatch)
    vault = tmp_path / "vault"
    vault.mkdir()
    _script_input(monkeypatch, ["2", ENTER, ENTER, ENTER, "ollama", ENTER, ENTER, ENTER, "n"])
    args = cli.build_parser().parse_args(["install-automation", "--vault", str(vault)])
    assert cli.cmd_install_automation(args) == 0
    assert "Skipped install-automation" in capsys.readouterr().out
    assert load_status(vault) is None
    assert not (tmp_path / ".llmwiki").exists()
    assert not (tmp_path / "config.json").exists()


def test_wizard_confirmation_never_answers_itself_when_stdin_ends(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    """Ctrl-D at the confirmation is a decline: consent has to be typed, never assumed."""
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    _pretend_tty(monkeypatch)
    vault = tmp_path / "vault"
    vault.mkdir()
    # Seven answers reach the last informational question, so stdin ends at the confirmation.
    _script_input(monkeypatch, [ENTER] * 7)
    args = cli.build_parser().parse_args(["install-automation", "--vault", str(vault)])
    assert cli.cmd_install_automation(args) == 0
    assert "Skipped install-automation" in capsys.readouterr().out
    assert load_status(vault) is None
    assert not (tmp_path / "config.json").exists()


def test_a_non_terminal_stdin_refuses_to_install_without_yes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    """A piped stdin cannot consent, so the wizard exits 2 without asking or writing anything."""
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(sys, "stdin", io.StringIO())  # a plain StringIO is not a terminal

    def refuse(prompt: str = "") -> str:
        raise AssertionError(f"the wizard asked {prompt!r} on a non-terminal stdin")

    monkeypatch.setattr("builtins.input", refuse)
    vault = tmp_path / "vault"
    vault.mkdir()
    args = cli.build_parser().parse_args(["install-automation", "--vault", str(vault)])
    assert cli.cmd_install_automation(args) == 2
    err = capsys.readouterr().err
    assert "needs a terminal" in err
    assert "--yes" in err
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
        "--no-activate",
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
    assert expected in (units / unit_names(tmp_path / "vault").wrapper).read_text(encoding="utf-8")
    assert "OnCalendar=Mon-Fri *-*-* 08:00:00" in (units / unit_names(tmp_path / "vault").timer).read_text(encoding="utf-8")


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


def test_yes_installs_with_a_non_terminal_stdin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """The unattended path is the one a pipe is allowed to take."""
    monkeypatch.setattr(sys, "stdin", io.StringIO())
    code, vault, units = _install_via_flags(tmp_path, monkeypatch, "--job", "ingest")
    assert code == 0
    assert load_status(vault) is not None
    assert (units / unit_names(tmp_path / "vault").wrapper).is_file()


def test_extras_flags_are_noted_as_ignored_for_an_ingest_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """`--graph` / `--lint-fail` describe maintain, so an ingest install says it drops them."""
    code, vault, _units = _install_via_flags(
        tmp_path, monkeypatch, "--job", "ingest", "--graph", "builtin", "--lint-fail", "errors"
    )
    assert code == 0
    err = capsys.readouterr().err
    assert "--graph builtin is ignored for --job ingest" in err
    assert "builds no graph" in err
    assert "--lint-fail errors is ignored for --job ingest" in err
    assert "no lint step" in err
    status = load_status(vault)
    assert status is not None and status["job"] == "ingest"


def test_an_ingest_install_records_none_of_the_extras_it_will_not_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """The status file, the label, the command and the Home panel must all describe the
    job that was actually installed — an ingest job runs no lint step, so nothing may
    advertise a failure policy for it."""
    _code, vault, units = _install_via_flags(
        tmp_path, monkeypatch, "--job", "ingest", "--graph", "builtin", "--lint-fail", "errors"
    )
    status = load_status(vault)
    assert status is not None
    assert (status["graph"], status["lint_fail"]) == ("none", "never")
    assert status["label"] == "Ingest only"
    wrapper = (units / unit_names(tmp_path / "vault").wrapper).read_text(encoding="utf-8")
    assert "--lint-fail" not in wrapper and "--graph-engine" not in wrapper
    assert "mark the scheduled run as failed" not in render_automation_panel(vault)


@pytest.mark.parametrize("default_is_target", [False, True], ids=["other-default", "same-default"])
def test_the_scheduled_command_always_names_its_vault(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, default_is_target: bool
):
    """The wrapper pins ``--vault`` even when the install targets ``vault.default_path``,
    so the run never resolves its target from the checkout's config at run time."""
    default = tmp_path / ("vault" if default_is_target else "default-vault")
    monkeypatch.setattr(cli, "load_default_vault_path", lambda: default)
    _code, vault, units = _install_via_flags(tmp_path, monkeypatch, "--job", "ingest")
    wrapper = (units / unit_names(vault).wrapper).read_text(encoding="utf-8")
    expected = plan_command(
        AutomationPlan(job="ingest"),
        python_bin=sys.executable,
        working_dir=tmp_path,
        vault=vault.resolve(),
    )
    assert expected.endswith(f"--vault {shlex.quote(str(vault.resolve()))}")
    assert f"{{ rc=0; {expected} || rc=$?; echo \"EXIT:$rc\"; }}" in wrapper


def test_extras_flags_are_not_noted_for_a_maintain_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    code, vault, _units = _install_via_flags(
        tmp_path, monkeypatch, "--job", "maintain", "--graph", "builtin"
    )
    assert code == 0
    assert "ignored" not in capsys.readouterr().err
    status = load_status(vault)
    assert status is not None and status["graph"] == "builtin"


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
    assert "this step may spend money" in panel
    assert "llmwiki synth --estimate" in panel


def test_panel_states_that_ingest_cannot_spend_money(tmp_path: Path):
    panel = _panel(tmp_path, plan_to_status(AutomationPlan(job="ingest")))
    assert "does not spend money" in panel


@pytest.mark.parametrize("lint_fail", ["never", "errors", "warnings"])
def test_panel_never_shows_the_lint_fail_reminder(tmp_path: Path, lint_fail: LintFail):
    """#234 R5: Automation is settings-only — no ``--lint-fail`` policy reminder."""
    plan = AutomationPlan(job="maintain", lint_fail=lint_fail)
    panel = _panel(tmp_path, plan_to_status(plan))
    assert "mark the scheduled run as failed" not in panel
    assert "--lint-fail" not in panel


def test_panel_does_not_advertise_a_failure_policy_for_an_ingest_job(tmp_path: Path):
    """An ingest job runs no lint step; the panel must not promise findings can fail it."""
    panel = _panel(tmp_path, plan_to_status(AutomationPlan(job="ingest", lint_fail="errors")))
    assert "Ingest only" in panel
    assert "mark the scheduled run as failed" not in panel


def test_panel_merges_cost_with_backend_and_hooks_with_watch(tmp_path: Path):
    """#234 R5: short synth-backend line; hooks and watch on separate lines; no Updated."""
    status = {
        **plan_to_status(AutomationPlan(job="maintain")),
        "synth_backend": "ollama",
        "watch_enabled": True,
        "hooks": ["SessionStart"],
        "log_path": "/tmp/last-automation.log",
        "updated_at": "2026-09-08T12:00:00Z",
        "note": "should not appear for maintain",
    }
    panel = _panel(tmp_path, status)
    assert "Synth backend: <code>ollama</code>" in panel
    assert "this step may spend money" in panel
    assert "llmwiki synth --estimate" in panel
    assert "what that costs" in panel
    assert "Cost / synth backend:" not in panel
    assert "Agent hooks: SessionStart</li>" in panel
    assert "(recommended)" not in panel
    assert "Watch (near-real-time maintain): <strong>on</strong>" in panel
    assert "Updated:" not in panel
    assert "Last sync" not in panel
    assert "Last synth" not in panel
    assert "Last build" not in panel
    assert "Last lint" not in panel
    assert "Maintain refreshes the site once after summarization." in panel
    assert "should not appear for maintain" not in panel


def test_panel_ingest_keeps_status_note_without_maintain_contract(tmp_path: Path):
    """Ingest is unchanged: status note stays; no Maintain site-once clause."""
    status = {
        **plan_to_status(AutomationPlan(job="ingest")),
        "synth_backend": "dummy",
        "watch_enabled": False,
        "hooks": [],
        "note": "Scheduled runs with no new sessions are a no-op.",
    }
    panel = _panel(tmp_path, status)
    assert "Synth backend: <code>dummy</code>" in panel
    assert "does not spend money" in panel
    assert "Scheduled runs with no new sessions are a no-op." in panel
    assert "Maintain refreshes the site once after summarization." not in panel
    assert "Agent hooks: none</li>" in panel
    assert "(recommended)" not in panel
    assert "Watch (near-real-time maintain): <strong>off</strong>" in panel


def test_panel_survives_a_malformed_status_file(tmp_path: Path):
    """A truncated or hand-edited status file degrades to readable wording, never an exception."""
    assert "No automation configured" in _panel(tmp_path, {})
    panel = _panel(tmp_path, {"profile": "Z", "schedule": "@daily", "hour": "eight"})
    assert "Ingest only" in panel
    assert "Every day at 08:00" in panel


# ─── Scheduler activation ───────────────────────────────────────────────


def _fake_systemctl(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, fail_enable: bool = False) -> Path:
    """Install a fake ``systemctl`` on PATH and point HOME at a throwaway directory."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = bin_dir / "systemctl.log"
    script = textwrap.dedent(f"""\
        #!/bin/sh
        echo "$@" >> "{log}"
        case "$2" in
          is-enabled)
            echo enabled
            exit 0
            ;;
          enable)
            {"exit 1" if fail_enable else "exit 0"}
            ;;
        esac
        exit 0
        """)
    systemctl = bin_dir / "systemctl"
    systemctl.write_text(script, encoding="utf-8")
    systemctl.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    return log


def test_activate_scheduler_linux_copies_units_and_enables_timer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    units = tmp_path / "units"
    units.mkdir()
    names = unit_names(tmp_path / "vault")
    staging_wrapper = units / names.wrapper
    staging_wrapper.write_text("# wrapper\n", encoding="utf-8")
    (units / names.service).write_text(
        render_systemd_service(wrapper=staging_wrapper, working_dir=tmp_path),
        encoding="utf-8",
    )
    (units / names.timer).write_text("# timer\n", encoding="utf-8")
    log = _fake_systemctl(tmp_path, monkeypatch)

    result = activate_scheduler(
        platform="linux", units_source_dir=units, working_dir=tmp_path, names=names
    )

    dest = default_scheduler_units_dir("linux")
    assert result["scheduler_activated"] is True
    assert result["scheduler_backend"] == "systemd"
    assert result["scheduler_active"] is True
    assert result["scheduler_error"] is None
    installed_service = (dest / names.service).read_text(encoding="utf-8")
    assert str(dest / names.wrapper) in installed_service
    assert str(staging_wrapper) not in installed_service
    assert (dest / names.timer).read_text(encoding="utf-8") == "# timer\n"
    logged = log.read_text(encoding="utf-8")
    assert "--user daemon-reload" in logged
    assert f"enable --now {names.timer}" in logged
    assert f"is-enabled {names.timer}" in logged


def test_run_install_with_activate_records_scheduler_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _fake_systemctl(tmp_path, monkeypatch)
    vault = tmp_path / "vault"
    vault.mkdir()
    units = tmp_path / "units"
    status = run_install({
        "working_dir": tmp_path,
        "python_bin": "python3",
        "vault_root": vault,
        "write_units_dir": units,
        "force_platform": "linux",
        "activate": True,
    })
    assert status["scheduler_activated"] is True
    assert status["scheduler_backend"] == "systemd"
    assert status["scheduler_active"] is True
    loaded = load_status(vault)
    assert loaded is not None
    assert loaded["scheduler_activated"] is True


def test_run_install_activate_failure_sets_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _fake_systemctl(tmp_path, monkeypatch, fail_enable=True)
    vault = tmp_path / "vault"
    vault.mkdir()
    units = tmp_path / "units"
    with pytest.raises(AutomationActivationError):
        run_install({
            "working_dir": tmp_path,
            "python_bin": "python3",
            "vault_root": vault,
            "write_units_dir": units,
            "force_platform": "linux",
            "activate": True,
        })
    loaded = load_status(vault)
    assert loaded is not None
    assert loaded.get("scheduler_error")
    assert loaded.get("scheduler_activated") is False


# ─── One schedule per vault (@spec: 330-doctor-automation-serves-vault) ───


def _activated_install(tmp_path: Path, vault: Path, units: Path) -> dict[str, Any]:
    return run_install({
        "working_dir": tmp_path,
        "python_bin": "python3",
        "vault_root": vault,
        "write_units_dir": units,
        "force_platform": "linux",
        "activate": True,
    })


def test_two_vaults_get_two_unit_sets_and_each_wrapper_keeps_its_vault(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Installing for B after A must not overwrite A's schedule or re-point it at B."""
    log = _fake_systemctl(tmp_path, monkeypatch)
    units = tmp_path / "units"
    vault_a, vault_b = tmp_path / "a" / "wiki", tmp_path / "b" / "wiki"
    vault_a.mkdir(parents=True)
    vault_b.mkdir(parents=True)
    _activated_install(tmp_path, vault_a, units)
    _activated_install(tmp_path, vault_b, units)

    names_a, names_b = unit_names(vault_a), unit_names(vault_b)
    assert names_a.base != names_b.base
    dest = default_scheduler_units_dir("linux")
    for names in (names_a, names_b):
        for name in (names.wrapper, names.service, names.timer):
            assert (units / name).is_file()
            assert (dest / name).is_file()
    for name in ("llmwiki-maintain.sh", "llmwiki-maintain.service", "llmwiki-maintain.timer"):
        assert not (units / name).exists()
        assert not (dest / name).exists()
    wrapper_a = (dest / names_a.wrapper).read_text(encoding="utf-8")
    assert f"--vault {shlex.quote(str(vault_a.resolve()))}" in wrapper_a
    assert str(vault_b) not in wrapper_a
    assert str(dest / names_a.wrapper) in (dest / names_a.service).read_text(encoding="utf-8")
    logged = log.read_text(encoding="utf-8")
    assert f"enable --now {names_a.timer}" in logged
    assert f"enable --now {names_b.timer}" in logged
    assert load_status(vault_a)["scheduler_unit"] == names_a.base
    assert load_status(vault_b)["scheduler_unit"] == names_b.base


def test_activation_records_unit_checkout_and_target_vault(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _fake_systemctl(tmp_path, monkeypatch)
    vault = tmp_path / "vault"
    vault.mkdir()
    _activated_install(tmp_path, vault, tmp_path / "units")
    loaded = load_status(vault)
    assert loaded is not None
    assert loaded["scheduler_unit"] == unit_names(vault).base
    assert loaded["working_dir"] == str(tmp_path)
    assert loaded["target_vault"] == str(vault.resolve())
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", loaded["installed_at"])


def test_installed_at_is_reset_by_activation_and_kept_without_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """A successful (re-)activation resets ``installed_at``; ``--no-activate`` keeps the old one."""
    _fake_systemctl(tmp_path, monkeypatch)
    vault = tmp_path / "vault"
    vault.mkdir()
    units = tmp_path / "units"
    path = status_path(vault)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"installed_at": "2000-01-01T00:00:00Z"}), encoding="utf-8")

    _status, _vault, _units = _install(tmp_path)
    assert load_status(vault)["installed_at"] == "2000-01-01T00:00:00Z"

    _activated_install(tmp_path, vault, units)
    assert load_status(vault)["installed_at"] != "2000-01-01T00:00:00Z"


def test_no_activate_install_records_no_installed_at(tmp_path: Path):
    _status, vault, _units = _install(tmp_path)
    loaded = load_status(vault)
    assert loaded is not None
    assert "installed_at" not in loaded
    assert loaded["scheduler_unit"] == unit_names(vault).base


def _scripted_scheduler(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    calls: list[list[str]] = []

    def fake(args: list[str]) -> Any:
        calls.append(list(args))
        return type("Proc", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    monkeypatch.setattr("llmwiki.automation_install.run_scheduler_cmd", fake)
    return calls


def test_macos_install_uses_the_vault_label(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setattr("llmwiki.automation_install.detect_platform", lambda: "macos")
    calls = _scripted_scheduler(monkeypatch)
    status, vault, units = _install(tmp_path, force_platform="macos", activate=True)
    names = unit_names(vault)
    assert status["scheduler_activated"] is True
    plist = default_scheduler_units_dir("macos") / names.plist
    assert f"<string>{names.launchd_label}</string>" in (units / names.plist).read_text(encoding="utf-8")
    assert f"<string>{names.launchd_label}</string>" in plist.read_text(encoding="utf-8")
    assert (default_scheduler_units_dir("macos") / names.wrapper).is_file()
    assert calls[0][:2] == ["launchctl", "bootout"] and calls[0][-1] == names.launchd_label
    assert calls[1][:2] == ["launchctl", "bootstrap"] and calls[1][-1] == str(plist)


def test_windows_install_creates_the_vault_task(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("llmwiki.automation_install.detect_platform", lambda: "windows")
    calls = _scripted_scheduler(monkeypatch)
    status, vault, units = _install(tmp_path, force_platform="windows", activate=True)
    names = unit_names(vault)
    assert status["scheduler_activated"] is True
    assert (units / names.task_xml).is_file()
    assert calls[0] == [
        "schtasks", "/Create", "/TN", names.task_name, "/XML", str(units / names.task_xml), "/F"
    ]


@pytest.mark.parametrize("plat", ["linux", "macos", "windows"])
def test_manual_activation_steps_name_the_vault_units(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], plat: str
):
    vault = tmp_path / "vault"
    names = unit_names(vault)
    cli._print_manual_scheduler_activation(tmp_path / "units", plat, vault)  # noqa: SLF001
    out = capsys.readouterr().out
    expected = {"linux": names.timer, "macos": names.plist, "windows": names.task_name}[plat]
    assert expected in out
    assert "llmwiki-maintain.timer" not in out and "com.llmwiki.maintain.plist" not in out


# ─── Discovery of installed units (@spec: 330-doctor-automation-serves-vault) ───

# Every character here is legal in a POSIX path and breaks naive shell splitting or XML.
HOSTILE = "R&D \"q\" it's"
MAINTAIN = AutomationPlan(job="maintain", graph="builtin")
Responses = dict[tuple[str, ...], tuple[int, str, str]]


def _fake_run(responses: Responses, calls: list[list[str]] | None = None):
    """Scheduler seam answering each argv from ``responses``; unknown argv is a test bug."""

    def run(args: list[str]) -> subprocess.CompletedProcess[str]:
        if calls is not None:
            calls.append(list(args))
        rc, out, err = responses[tuple(args)]
        return subprocess.CompletedProcess(args, rc, out, err)

    return run


def _missing_binary(args: list[str]) -> subprocess.CompletedProcess[str]:
    raise FileNotFoundError(args[0])


def _write_wrapper(path: Path, *, working_dir: Path, log: Path, vault: Path | None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        render_wrapper_script(
            plan=MAINTAIN, python_bin="/usr/bin/python3", working_dir=working_dir, log_path=log, vault=vault
        ),
        encoding="utf-8",
    )
    return path


def _systemd_unit(home: Path, name: str, *, working_dir: Path, log: Path, vault: Path | None) -> Path:
    unit_dir = home / ".config" / "systemd" / "user"
    wrapper = _write_wrapper(unit_dir / f"{name}.sh", working_dir=working_dir, log=log, vault=vault)
    (unit_dir / f"{name}.service").write_text(
        render_systemd_service(wrapper=wrapper, working_dir=working_dir), encoding="utf-8"
    )
    return wrapper


def _is_enabled(name: str) -> tuple[str, ...]:
    return ("systemctl", "--user", "is-enabled", f"{name}.timer")


@pytest.mark.parametrize("with_vault", [True, False])
def test_parse_wrapper_round_trips_hostile_paths(tmp_path: Path, with_vault: bool):
    working_dir = tmp_path / f"checkout {HOSTILE}"
    vault = tmp_path / f"vault {HOSTILE}"
    log = tmp_path / f"logs {HOSTILE}" / "last.log"
    wrapper = _write_wrapper(
        tmp_path / "w.sh", working_dir=working_dir, log=log, vault=vault if with_vault else None
    )
    parsed = parse_wrapper(wrapper.read_text(encoding="utf-8"))
    assert parsed == WrapperCommand(
        working_dir=working_dir, vault=vault if with_vault else None, log_path=log
    )


def test_parse_wrapper_without_an_llmwiki_line_is_none():
    assert parse_wrapper("#!/usr/bin/env bash\necho hi\n") is None


def test_linux_discovers_per_vault_and_legacy_units(tmp_path: Path):
    home = tmp_path / "home"
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    vault_a, vault_b = tmp_path / f"a {HOSTILE}", tmp_path / "b"
    names_a = unit_names(vault_a)
    _systemd_unit(home, names_a.base, working_dir=checkout, log=tmp_path / "a.log", vault=vault_a)
    _systemd_unit(home, LEGACY_SYSTEMD, working_dir=checkout, log=tmp_path / "b.log", vault=vault_b)
    run = _fake_run({
        _is_enabled(names_a.base): (0, "enabled\n", ""),
        _is_enabled(LEGACY_SYSTEMD): (1, "disabled\n", ""),
    })

    result = discover_units("linux", home=home, run=run)

    assert result.unavailable is None
    by_name = {unit.name: unit for unit in result.units}
    per_vault, legacy = by_name[names_a.base], by_name[LEGACY_SYSTEMD]
    assert (per_vault.legacy, per_vault.enabled, per_vault.target_vault) == (False, True, vault_a)
    assert per_vault.working_dir == checkout
    assert per_vault.log_path == tmp_path / "a.log"
    assert per_vault.wrapper_path == home / ".config/systemd/user" / names_a.wrapper
    assert (legacy.legacy, legacy.enabled, legacy.target_vault) == (True, False, vault_b)
    assert legacy.reason_unknown is None and legacy.platform == "linux"


def test_legacy_wrapper_without_vault_reads_the_checkout_config(tmp_path: Path):
    home = tmp_path / "home"
    checkout = tmp_path / "checkout"
    (checkout / "examples").mkdir(parents=True)
    (checkout / "examples" / "sessions_config.json").write_text(
        json.dumps({"vault": {"default_path": str(tmp_path / "shipped")}}), encoding="utf-8"
    )
    (checkout / "config.json").write_text(
        json.dumps({"vault": {"default_path": str(tmp_path / "configured")}}), encoding="utf-8"
    )
    _systemd_unit(home, LEGACY_SYSTEMD, working_dir=checkout, log=tmp_path / "l.log", vault=None)
    run = _fake_run({_is_enabled(LEGACY_SYSTEMD): (0, "enabled\n", "")})

    (unit,) = discover_units("linux", home=home, run=run).units

    assert unit.target_vault == tmp_path / "configured"
    assert unit.reason_unknown is None


def test_default_vault_for_checkout_precedence_and_relative_paths(tmp_path: Path):
    (tmp_path / "examples").mkdir()
    shipped = tmp_path / "examples" / "sessions_config.json"
    assert default_vault_for_checkout(tmp_path) is None
    shipped.write_text(json.dumps({"vault": {"default_path": "rel/wiki"}}), encoding="utf-8")
    assert default_vault_for_checkout(tmp_path) == tmp_path / "rel" / "wiki"
    (tmp_path / "config.json").write_text(json.dumps({"vault": {"default_path": "~/w"}}), encoding="utf-8")
    assert default_vault_for_checkout(tmp_path) == Path("~/w").expanduser()


def test_legacy_wrapper_without_vault_and_without_config_targets_the_checkout_itself(tmp_path: Path):
    home = tmp_path / "home"
    checkout = tmp_path / "checkout"
    (checkout / "llmwiki").mkdir(parents=True)
    (checkout / "llmwiki" / "__init__.py").write_text("", encoding="utf-8")
    _systemd_unit(home, LEGACY_SYSTEMD, working_dir=checkout, log=tmp_path / "l.log", vault=None)
    run = _fake_run({_is_enabled(LEGACY_SYSTEMD): (0, "enabled\n", "")})

    (unit,) = discover_units("linux", home=home, run=run).units

    assert unit.target_vault == checkout


def test_gone_checkout_without_vault_is_unknown_not_guessed(tmp_path: Path):
    home = tmp_path / "home"
    _systemd_unit(home, LEGACY_SYSTEMD, working_dir=tmp_path / "gone", log=tmp_path / "l.log", vault=None)
    run = _fake_run({_is_enabled(LEGACY_SYSTEMD): (0, "enabled\n", "")})

    (unit,) = discover_units("linux", home=home, run=run).units

    assert unit.target_vault is None
    assert unit.reason_unknown == "checkout gone no longer exists"
    assert unit.working_dir == tmp_path / "gone"


def test_gone_checkout_with_vault_keeps_the_pinned_target(tmp_path: Path):
    home = tmp_path / "home"
    vault = tmp_path / "vault"
    _systemd_unit(home, unit_names(vault).base, working_dir=tmp_path / "gone", log=tmp_path / "l.log", vault=vault)
    run = _fake_run({_is_enabled(unit_names(vault).base): (0, "enabled\n", "")})

    (unit,) = discover_units("linux", home=home, run=run).units

    assert (unit.target_vault, unit.reason_unknown) == (vault, None)


def test_missing_wrapper_is_unknown_and_keeps_the_unit_checkout(tmp_path: Path):
    home = tmp_path / "home"
    checkout = tmp_path / "checkout"
    wrapper = _systemd_unit(home, LEGACY_SYSTEMD, working_dir=checkout, log=tmp_path / "l.log", vault=None)
    wrapper.unlink()
    run = _fake_run({_is_enabled(LEGACY_SYSTEMD): (0, "enabled\n", "")})

    (unit,) = discover_units("linux", home=home, run=run).units

    assert unit.target_vault is None
    assert unit.reason_unknown == f"wrapper {wrapper.name} is missing or unreadable"
    assert unit.working_dir == checkout


@pytest.mark.parametrize(
    "run",
    [
        _missing_binary,
        _fake_run({_is_enabled(LEGACY_SYSTEMD): (1, "", "Failed to connect to bus: No medium found\n")}),
    ],
    ids=["no-systemctl", "no-user-bus"],
)
def test_linux_without_a_user_bus_is_unavailable(tmp_path: Path, run):
    home = tmp_path / "home"
    vault = tmp_path / "vault"
    _systemd_unit(home, LEGACY_SYSTEMD, working_dir=tmp_path, log=tmp_path / "l.log", vault=vault)

    result = discover_units("linux", home=home, run=run)

    assert result.unavailable
    (unit,) = result.units
    assert unit.enabled is None
    assert unit.target_vault == vault


def test_linux_with_no_units_finds_nothing(tmp_path: Path):
    result = discover_units("linux", home=tmp_path, run=_fake_run({}))
    assert result == DiscoveryResult(units=(), unavailable=None)


def _launch_agent(home: Path, vault: Path, *, label: str, log: Path) -> Path:
    agents = home / "Library" / "LaunchAgents"
    wrapper = _write_wrapper(agents / f"{label}.sh", working_dir=home / "co", log=log, vault=vault)
    (agents / f"{label}.plist").write_text(
        render_launchd_plist(wrapper=wrapper, working_dir=home / "co", log_path=log, spec=DAILY, label=label),
        encoding="utf-8",
    )
    return wrapper


@pytest.mark.parametrize(
    ("answer", "enabled"),
    [
        ((0, "state = not running\n", ""), True),
        ((113, "", 'Could not find service "x" in domain for uid: 501\n'), False),
        ((5, "", "Input/output error\n"), None),
    ],
)
def test_macos_reads_the_plist_and_asks_launchctl(
    tmp_path: Path, answer: tuple[int, str, str], enabled: bool | None
):
    home = tmp_path / f"home {HOSTILE}"
    vault = tmp_path / f"vault {HOSTILE}"
    label = unit_names(vault).launchd_label
    wrapper = _launch_agent(home, vault, label=label, log=tmp_path / "m.log")
    calls: list[list[str]] = []
    run = _fake_run({("launchctl", "print", f"gui/501/{label}"): answer}, calls)

    result = discover_units("macos", home=home, run=run, uid=501)

    (unit,) = result.units
    assert result.unavailable is None
    assert calls == [["launchctl", "print", f"gui/501/{label}"]]
    assert (unit.name, unit.legacy, unit.platform) == (label, False, "macos")
    assert (unit.wrapper_path, unit.working_dir, unit.target_vault) == (wrapper, home / "co", vault)
    assert unit.log_path == tmp_path / "m.log"
    assert unit.enabled is enabled


def test_macos_legacy_label_is_legacy(tmp_path: Path):
    home = tmp_path / "home"
    _launch_agent(home, tmp_path / "v", label=LEGACY_LAUNCHD, log=tmp_path / "m.log")
    run = _fake_run({("launchctl", "print", f"gui/7/{LEGACY_LAUNCHD}"): (0, "", "")})
    (unit,) = discover_units("macos", home=home, run=run, uid=7).units
    assert unit.legacy is True


def test_macos_unparsable_plist_is_unknown(tmp_path: Path):
    agents = tmp_path / "Library" / "LaunchAgents"
    agents.mkdir(parents=True)
    (agents / f"{LEGACY_LAUNCHD}.plist").write_text("<plist><dict>", encoding="utf-8")
    (unit,) = discover_units("macos", home=tmp_path, run=_fake_run({}), uid=1).units
    assert unit.target_vault is None and unit.reason_unknown


def _task_answers(tmp_path: Path, vault: Path) -> tuple[Responses, str, Path]:
    names = unit_names(vault)
    working_dir = tmp_path / f"co {HOSTILE}"
    wrapper = _write_wrapper(
        tmp_path / "units" / names.wrapper, working_dir=working_dir, log=tmp_path / "w.log", vault=vault
    )
    xml = render_windows_task(wrapper=wrapper, working_dir=working_dir, spec=DAILY)
    task = f"\\{names.task_name}"
    listing = (
        f'"{task}","10/23/2026 8:00:00 AM","Ready"\r\n'
        f'"{task}","10/24/2026 8:00:00 AM","Ready"\r\n'
        '"\\Other task","N/A","Ready"\r\n'
    )
    responses: Responses = {
        ("schtasks", "/Query", "/FO", "CSV", "/NH"): (0, listing, ""),
        ("schtasks", "/Query", "/TN", task, "/XML"): (0, xml, ""),
    }
    return responses, names.task_name, wrapper


def test_windows_reads_the_task_list_and_task_xml(tmp_path: Path):
    vault = tmp_path / f"vault {HOSTILE}"
    responses, name, wrapper = _task_answers(tmp_path, vault)
    calls: list[list[str]] = []

    result = discover_units("windows", home=tmp_path, run=_fake_run(responses, calls))

    assert result.unavailable is None
    (unit,) = result.units
    assert len(calls) == 2
    assert (unit.name, unit.legacy, unit.enabled) == (name, False, True)
    assert (unit.wrapper_path, unit.target_vault) == (wrapper, vault)
    assert unit.working_dir == tmp_path / f"co {HOSTILE}"


@pytest.mark.parametrize("broken", ["listing", "xml-rc", "xml-parse"])
def test_windows_query_failures_are_unavailable(tmp_path: Path, broken: str):
    responses, name, _wrapper = _task_answers(tmp_path, tmp_path / "vault")
    listing_key = ("schtasks", "/Query", "/FO", "CSV", "/NH")
    xml_key = ("schtasks", "/Query", "/TN", f"\\{name}", "/XML")
    if broken == "listing":
        responses[listing_key] = (1, "", "ERROR: Access is denied.")
    elif broken == "xml-rc":
        responses[xml_key] = (1, "", "ERROR: The system cannot find the file specified.")
    else:
        responses[xml_key] = (0, "<Task><Actions>", "")

    result = discover_units("windows", home=tmp_path, run=_fake_run(responses))

    assert result.unavailable
    assert result.units == ()


def test_windows_without_schtasks_is_unavailable(tmp_path: Path):
    result = discover_units("windows", home=tmp_path, run=_missing_binary)
    assert result.unavailable and result.units == ()


def test_relative_vault_in_a_legacy_wrapper_is_anchored_to_its_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """``--vault demo`` is the checkout's demo/, not a folder named demo in the doctor's cwd."""
    home = tmp_path / "home"
    checkout = tmp_path / "checkout"
    demo = checkout / "demo"
    demo.mkdir(parents=True)
    _systemd_unit(home, LEGACY_SYSTEMD, working_dir=checkout, log=tmp_path / "l.log", vault=Path("demo"))
    monkeypatch.chdir(tmp_path)
    run = _fake_run({_is_enabled(LEGACY_SYSTEMD): (0, "enabled\n", "")})

    (unit,) = discover_units("linux", home=home, run=run).units

    assert unit.target_vault == checkout / "demo"
    discovery = DiscoveryResult((unit,), None)
    assert _orphan_finding(discovery) is None
    assert legacy_unit_serving(checkout / "demo", discovery) is unit


def test_discovery_skips_names_that_only_share_the_maintain_prefix(tmp_path: Path):
    home = tmp_path / "home"
    checkout = tmp_path / "co"
    checkout.mkdir()
    vault = tmp_path / "vault"
    _systemd_unit(home, LEGACY_SYSTEMD, working_dir=checkout, log=tmp_path / "l.log", vault=vault)
    unit_dir = home / ".config" / "systemd" / "user"
    (unit_dir / "llmwiki-maintainer.service").write_text("[Service]\nExecStart=/bin/true\n", encoding="utf-8")
    linux = discover_units(
        "linux", home=home, run=_fake_run({_is_enabled(LEGACY_SYSTEMD): (0, "enabled\n", "")})
    )
    assert [unit.name for unit in linux.units] == [LEGACY_SYSTEMD]

    _launch_agent(home, vault, label=LEGACY_LAUNCHD, log=tmp_path / "m.log")
    agents = home / "Library" / "LaunchAgents"
    (agents / "com.llmwiki.maintainer.plist").write_text("<plist/>", encoding="utf-8")
    mac = discover_units(
        "macos",
        home=home,
        run=_fake_run({("launchctl", "print", f"gui/7/{LEGACY_LAUNCHD}"): (0, "", "")}),
        uid=7,
    )
    assert [unit.name for unit in mac.units] == [LEGACY_LAUNCHD]

    responses, name, _wrapper = _task_answers(tmp_path, vault)
    listing_key = ("schtasks", "/Query", "/FO", "CSV", "/NH")
    rc, listing, err = responses[listing_key]
    responses[listing_key] = (rc, listing + '"\\llmwiki-maintainer","N/A","Ready"\r\n', err)
    windows = discover_units("windows", home=home, run=_fake_run(responses))
    assert [unit.name for unit in windows.units] == [name]


def test_windows_enabled_comes_from_task_xml_not_the_localized_status(tmp_path: Path):
    vault = tmp_path / "vault"
    responses, _name, _wrapper = _task_answers(tmp_path, vault)
    xml_key = next(key for key in responses if key[:3] == ("schtasks", "/Query", "/TN"))
    _rc, xml, _err = responses[xml_key]
    xml = xml.replace(
        "  <Actions>",
        "  <Settings>\n    <Enabled>false</Enabled>\n  </Settings>\n  <Actions>",
        1,
    )
    responses[xml_key] = (0, xml, "")
    listing_key = ("schtasks", "/Query", "/FO", "CSV", "/NH")
    rc, listing, err = responses[listing_key]
    responses[listing_key] = (rc, listing.replace("Ready", "Prêt"), err)

    (unit,) = discover_units("windows", home=tmp_path, run=_fake_run(responses)).units

    assert unit.enabled is False


def test_deactivation_leaves_a_wrapper_that_is_not_this_units_script(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("HOME", str(tmp_path))
    agents = tmp_path / "Library" / "LaunchAgents"
    agents.mkdir(parents=True)
    own = agents / f"{LEGACY_SYSTEMD}.sh"
    own.write_text("#!/bin/sh\n", encoding="utf-8")
    plist = agents / f"{LEGACY_LAUNCHD}.plist"
    plist.write_text("plist", encoding="utf-8")
    foreign = tmp_path / "elsewhere" / "other.sh"
    foreign.parent.mkdir()
    foreign.write_text("keep", encoding="utf-8")
    bootout = ("launchctl", "bootout", "gui/7", LEGACY_LAUNCHD)

    owned = replace(
        _unit(LEGACY_LAUNCHD, legacy=True),
        platform="macos",
        wrapper_path=own,
    )
    assert deactivate_unit(owned, home=tmp_path, run=_fake_run({bootout: (0, "", "")}), uid=7) is None
    assert not own.exists() and not plist.exists()

    plist.write_text("plist", encoding="utf-8")
    stray = replace(owned, wrapper_path=foreign)
    note = deactivate_unit(stray, home=tmp_path, run=_fake_run({bootout: (0, "", "")}), uid=7)
    assert foreign.read_text(encoding="utf-8") == "keep"
    assert note is not None and str(foreign) in note
    assert not plist.exists()

    staging = tmp_path / ".automation"
    staging.mkdir()
    win_wrapper = staging / f"{LEGACY_SYSTEMD}.sh"
    win_wrapper.write_text("#!/bin/sh\n", encoding="utf-8")
    task_xml = staging / f"{LEGACY_SYSTEMD}-task.xml"
    task_xml.write_text("<Task/>", encoding="utf-8")
    delete = ("schtasks", "/Delete", "/TN", LEGACY_SYSTEMD, "/F")
    windows = replace(
        _unit(LEGACY_SYSTEMD, legacy=True),
        platform="windows",
        wrapper_path=win_wrapper,
    )
    assert deactivate_unit(windows, home=tmp_path, run=_fake_run({delete: (0, "", "")})) is None
    assert not win_wrapper.exists() and not task_xml.exists()

    alien = tmp_path / "alien" / "payload.sh"
    alien.parent.mkdir()
    alien.write_text("keep", encoding="utf-8")
    planted = replace(windows, wrapper_path=alien)
    note = deactivate_unit(planted, home=tmp_path, run=_fake_run({delete: (0, "", "")}))
    assert alien.read_text(encoding="utf-8") == "keep"
    assert note is not None and str(alien) in note


def test_unknown_platform_is_unavailable(tmp_path: Path):
    result = discover_units("unknown", home=tmp_path, run=_fake_run({}))
    assert result == DiscoveryResult(units=(), unavailable="unsupported platform: unknown")


def _unit(name: str, *, legacy: bool, target: Path | None = None) -> InstalledUnit:
    return InstalledUnit(
        name=name,
        platform="linux",
        legacy=legacy,
        wrapper_path=None,
        working_dir=None,
        target_vault=target,
        log_path=None,
        enabled=True,
        reason_unknown=None,
    )


def test_unit_for_vault_prefers_the_vault_unit_then_the_legacy_unit(tmp_path: Path):
    vault = tmp_path / "vault"
    names = unit_names(vault)
    legacy = _unit(LEGACY_SYSTEMD, legacy=True, target=tmp_path / "elsewhere")
    own = _unit(names.base, legacy=False, target=vault)
    other = _unit(unit_names(tmp_path / "other").base, legacy=False)
    mac_own = _unit(names.launchd_label, legacy=False)

    assert unit_for_vault(vault, DiscoveryResult((legacy, other, own), None)) is own
    assert unit_for_vault(vault, DiscoveryResult((legacy, mac_own), None)) is mac_own
    assert unit_for_vault(vault, DiscoveryResult((other, legacy), None)) is legacy
    assert unit_for_vault(vault, DiscoveryResult((other,), None)) is None


_LABEL = "com.llmwiki.maintain.gone-1234abcd"
_TASK = "llmwiki-maintain-gone-1234abcd"


@pytest.mark.parametrize(
    ("platform", "name", "wrapper", "expected"),
    [
        pytest.param(
            "linux",
            _TASK,
            None,
            [
                f"systemctl --user disable --now {_TASK}.timer",
                f"rm ~/.config/systemd/user/{_TASK}.sh ~/.config/systemd/user/{_TASK}.service ~/.config/systemd/user/{_TASK}.timer",
                "systemctl --user daemon-reload",
            ],
            id="systemd",
        ),
        pytest.param(
            "macos",
            _LABEL,
            None,
            [
                f"launchctl bootout gui/$(id -u) {_LABEL}",
                f"rm ~/Library/LaunchAgents/{_LABEL}.plist ~/Library/LaunchAgents/{_LABEL}.sh",
            ],
            id="launchd-default-wrapper",
        ),
        pytest.param(
            "macos",
            _LABEL,
            ("staging dir", f"{_LABEL}.sh"),
            [
                f"launchctl bootout gui/$(id -u) {_LABEL}",
                f"rm ~/Library/LaunchAgents/{_LABEL}.plist ~/'staging dir/{_LABEL}.sh'",
            ],
            id="launchd-recorded-wrapper",
        ),
        pytest.param(
            "windows",
            _TASK,
            (".automation", f"{_TASK}.sh"),
            [
                f'schtasks /Delete /TN "{_TASK}" /F',
                f'Remove-Item "~\\.automation\\{_TASK}.sh", "~\\.automation\\{_TASK}-task.xml"',
            ],
            id="windows",
        ),
    ],
)
def test_removal_steps_per_platform_are_home_relative(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    platform: str,
    name: str,
    wrapper: tuple[str, ...] | None,
    expected: list[str],
):
    monkeypatch.setenv("HOME", str(tmp_path))
    unit = replace(
        _unit(name, legacy=False, target=tmp_path / "gone"),
        platform=platform,
        wrapper_path=tmp_path.joinpath(*wrapper) if wrapper else None,
    )

    steps = removal_steps(unit)

    assert steps == expected
    assert not any(str(tmp_path) in step for step in steps)


# ─── #275: pin synthesis.claude.path at install for systemd catch-up ───


def _fake_claude_on_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a throwaway ``claude`` under ``tmp_path/.local/bin`` and put it on PATH."""
    local_bin = tmp_path / ".local" / "bin"
    local_bin.mkdir(parents=True)
    claude = local_bin / "claude"
    claude.write_text("#!/bin/sh\n", encoding="utf-8")
    claude.chmod(0o755)
    monkeypatch.setenv("PATH", f"{local_bin}{os.pathsep}/usr/bin{os.pathsep}/bin")
    return claude


def test_yes_claude_pins_absolute_path_usable_under_minimal_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Install-time PATH finds ~/.local/bin/claude; the pin survives systemd-style PATH (#275)."""
    claude = _fake_claude_on_path(tmp_path, monkeypatch)
    code, _vault, _units = _install_via_flags(
        tmp_path, monkeypatch, "--job", "maintain", "--synth-backend", "claude",
    )
    assert code == 0
    cfg = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
    pinned = cfg["synthesis"]["claude"]["path"]
    assert Path(pinned) == claude.resolve()
    assert Path(pinned).is_absolute()

    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    assert resolve_claude_path(None) is None
    assert resolve_claude_path(pinned) == claude.resolve()


def test_yes_claude_does_not_overwrite_explicit_nested_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    explicit = tmp_path / "already-pinned"
    explicit.write_text("#!/bin/sh\n", encoding="utf-8")
    explicit.chmod(0o755)
    (tmp_path / "config.json").write_text(
        json.dumps({
            "synthesis": {
                "backend": "claude",
                "claude": {"path": str(explicit), "model": "sonnet"},
            },
        })
        + "\n",
        encoding="utf-8",
    )
    other = _fake_claude_on_path(tmp_path, monkeypatch)
    code, _vault, _units = _install_via_flags(
        tmp_path, monkeypatch, "--job", "maintain", "--synth-backend", "claude",
    )
    assert code == 0
    cfg = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
    assert cfg["synthesis"]["claude"]["path"] == str(explicit)
    assert cfg["synthesis"]["claude"]["model"] == "sonnet"
    assert cfg["synthesis"]["claude"]["path"] != str(other.resolve())


def test_yes_claude_does_not_overwrite_explicit_flat_claude_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    explicit = tmp_path / "flat-pinned"
    explicit.write_text("#!/bin/sh\n", encoding="utf-8")
    explicit.chmod(0o755)
    (tmp_path / "config.json").write_text(
        json.dumps({"synthesis": {"backend": "claude", "claude_path": str(explicit)}}) + "\n",
        encoding="utf-8",
    )
    _fake_claude_on_path(tmp_path, monkeypatch)
    code, _vault, _units = _install_via_flags(
        tmp_path, monkeypatch, "--job", "maintain", "--synth-backend", "claude",
    )
    assert code == 0
    cfg = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
    assert cfg["synthesis"]["claude_path"] == str(explicit)
    assert "path" not in (cfg["synthesis"].get("claude") or {})


def test_yes_claude_warns_when_cli_missing_but_still_installs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    code, vault, units = _install_via_flags(
        tmp_path, monkeypatch, "--job", "maintain", "--synth-backend", "claude",
    )
    assert code == 0
    assert load_status(vault) is not None
    assert (units / unit_names(tmp_path / "vault").wrapper).is_file()
    cfg = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
    assert cfg["synthesis"]["backend"] == "claude"
    assert "path" not in (cfg["synthesis"].get("claude") or {})
    err = capsys.readouterr().err
    assert "claude CLI not found" in err
    assert "synthesis.claude.path" in err


# ─── Per-vault scheduler unit names (@spec: 330-doctor-automation-serves-vault) ───


def test_vault_unit_id_is_stable_across_calls_and_symlinks(tmp_path: Path):
    vault = tmp_path / "My Vault"
    vault.mkdir()
    link = tmp_path / "link"
    link.symlink_to(vault)
    first = vault_unit_id(vault)
    assert first == vault_unit_id(vault)
    assert first == vault_unit_id(link)
    assert re.fullmatch(r"my-vault-[0-9a-f]{8}", first)


def test_vault_unit_id_differs_for_same_basename_in_different_dirs(tmp_path: Path):
    a = tmp_path / "a" / "wiki"
    b = tmp_path / "b" / "wiki"
    a.mkdir(parents=True)
    b.mkdir(parents=True)
    id_a, id_b = vault_unit_id(a), vault_unit_id(b)
    assert id_a != id_b
    assert id_a.startswith("wiki-") and id_b.startswith("wiki-")


@pytest.mark.parametrize(
    ("name", "slug"),
    [
        ("Вики", "vault"),
        ("my  notes & stuff", "my-notes-stuff"),
        ("UPPER", "upper"),
        ("--edge--", "edge"),
        ("a" * 30, "a" * 24),
        ("abcdefghijklmnopqrstuvw-xyz", "abcdefghijklmnopqrstuvw"),
    ],
)
def test_vault_unit_id_slug_edge_cases(tmp_path: Path, name: str, slug: str):
    unit_id = vault_unit_id(tmp_path / name)
    prefix, _, digest = unit_id.rpartition("-")
    assert prefix == slug
    assert re.fullmatch(r"[0-9a-f]{8}", digest)


def test_unit_names_cover_every_platform(tmp_path: Path):
    vault = tmp_path / "vault"
    unit_id = vault_unit_id(vault)
    names = unit_names(vault)
    base = f"{LEGACY_SYSTEMD}-{unit_id}"
    label = f"{LEGACY_LAUNCHD}.{unit_id}"
    assert names.base == base
    assert names.launchd_label == label
    assert names.wrapper == f"{base}.sh"
    assert names.service == f"{base}.service"
    assert names.timer == f"{base}.timer"
    assert names.plist == f"{label}.plist"
    assert names.task_xml == f"{base}-task.xml"
    assert names.task_name == base
    with pytest.raises(AttributeError):
        names.base = "other"  # type: ignore[misc]


def test_is_dev_checkout_tells_worktree_checkout_and_install(tmp_path: Path):
    worktree = tmp_path / "wt"
    worktree.mkdir()
    (worktree / ".git").write_text("gitdir: /elsewhere\n", encoding="utf-8")
    checkout = tmp_path / "co"
    (checkout / ".git").mkdir(parents=True)
    installed = tmp_path / "site-packages"
    installed.mkdir()
    assert is_dev_checkout(worktree) == "worktree"
    assert is_dev_checkout(checkout) == "checkout"
    assert is_dev_checkout(installed) is None


# ─── Adopting the legacy single unit (@spec: 330-doctor-automation-serves-vault, R1 AC3/AC4) ───

LEGACY_TASK = f"\\{LEGACY_SYSTEMD}"


def _adoption_scheduler(monkeypatch: pytest.MonkeyPatch, answers: Responses | None = None) -> list[list[str]]:
    """Scheduler seam for ``run_install``: records every argv, answers ``answers`` or ``(0, "", "")``."""
    calls: list[list[str]] = []
    scripted = answers or {}

    def fake(args: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(list(args))
        rc, out, err = scripted.get(tuple(args), (0, "", ""))
        return subprocess.CompletedProcess(args, rc, out, err)

    monkeypatch.setattr("llmwiki.automation_install.run_scheduler_cmd", fake)
    return calls


def _legacy_unit(plat: str, tmp_path: Path, home: Path, target: Path | None) -> tuple[list[Path], Responses]:
    """Write the legacy unit's files for ``plat`` serving ``target``; return them and discovery answers."""
    checkout = tmp_path / "old-checkout"
    log = tmp_path / "legacy.log"
    if plat == "linux":
        _systemd_unit(home, LEGACY_SYSTEMD, working_dir=checkout, log=log, vault=target)
        unit_dir = home / ".config" / "systemd" / "user"
        (unit_dir / f"{LEGACY_SYSTEMD}.timer").write_text("# timer\n", encoding="utf-8")
        return [unit_dir / f"{LEGACY_SYSTEMD}{ext}" for ext in (".sh", ".service", ".timer")], {}
    if plat == "macos":
        agents = home / "Library" / "LaunchAgents"
        wrapper = _write_wrapper(agents / f"{LEGACY_SYSTEMD}.sh", working_dir=checkout, log=log, vault=target)
        (agents / f"{LEGACY_LAUNCHD}.plist").write_text(
            render_launchd_plist(wrapper=wrapper, working_dir=checkout, log_path=log, spec=DAILY), encoding="utf-8"
        )
        return [agents / f"{LEGACY_LAUNCHD}.plist", wrapper], {}
    staging = tmp_path / "units"
    wrapper = _write_wrapper(staging / f"{LEGACY_SYSTEMD}.sh", working_dir=checkout, log=log, vault=target)
    xml = render_windows_task(wrapper=wrapper, working_dir=checkout, spec=DAILY)
    task_xml = staging / f"{LEGACY_SYSTEMD}-task.xml"
    task_xml.write_text(xml, encoding="utf-8")
    answers: Responses = {
        ("schtasks", "/Query", "/FO", "CSV", "/NH"): (0, f'"{LEGACY_TASK}","N/A","Ready"\r\n', ""),
        ("schtasks", "/Query", "/TN", LEGACY_TASK, "/XML"): (0, xml, ""),
    }
    return [wrapper, task_xml], answers


def _deactivation_calls(plat: str) -> list[list[str]]:
    return {
        "linux": [
            ["systemctl", "--user", "disable", "--now", f"{LEGACY_SYSTEMD}.timer"],
            ["systemctl", "--user", "daemon-reload"],
        ],
        "macos": [["launchctl", "bootout", f"gui/{os.getuid()}", LEGACY_LAUNCHD]],
        "windows": [["schtasks", "/Delete", "/TN", LEGACY_SYSTEMD, "/F"]],
    }[plat]


def _home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, plat: str) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr("llmwiki.automation_install.detect_platform", lambda: plat)
    return home


@pytest.mark.parametrize("plat", ["linux", "macos", "windows"])
def test_install_switches_off_the_legacy_unit_serving_this_vault(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, plat: str
):
    home = _home(tmp_path, monkeypatch, plat)
    vault = tmp_path / "vault"
    vault.mkdir()
    legacy_files, answers = _legacy_unit(plat, tmp_path, home, vault)
    calls = _adoption_scheduler(monkeypatch, answers)

    status, _vault, _units = _install(tmp_path, force_platform=plat, activate=True)

    expected = _deactivation_calls(plat)
    assert calls[-len(expected):] == expected
    assert [path for path in legacy_files if path.exists()] == []
    assert (status["adopted_legacy"], status["legacy_adopt_error"]) == (True, None)
    assert load_status(vault)["adopted_legacy"] is True


@pytest.mark.parametrize("plat", ["linux", "macos", "windows"])
def test_install_leaves_a_legacy_unit_serving_another_vault_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, plat: str
):
    home = _home(tmp_path, monkeypatch, plat)
    other = tmp_path / "other-vault"
    other.mkdir()
    legacy_files, answers = _legacy_unit(plat, tmp_path, home, other)
    calls = _adoption_scheduler(monkeypatch, answers)

    status, _vault, _units = _install(tmp_path, force_platform=plat, activate=True)

    assert _deactivation_calls(plat)[0] not in calls
    assert all(path.is_file() for path in legacy_files)
    assert (status["adopted_legacy"], status["legacy_adopt_error"]) == (False, None)


def test_install_leaves_a_legacy_unit_with_an_unknown_target_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    # No --vault and a checkout that no longer exists: the legacy target cannot be read.
    home = _home(tmp_path, monkeypatch, "linux")
    legacy_files, _answers = _legacy_unit("linux", tmp_path, home, None)
    calls = _adoption_scheduler(monkeypatch)

    status, _vault, _units = _install(tmp_path, activate=True)

    assert _deactivation_calls("linux")[0] not in calls
    assert all(path.is_file() for path in legacy_files)
    assert status["adopted_legacy"] is False


def test_a_failed_legacy_switch_off_does_not_fail_the_install(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    home = _home(tmp_path, monkeypatch, "linux")
    vault = tmp_path / "vault"
    vault.mkdir()
    legacy_files, _answers = _legacy_unit("linux", tmp_path, home, vault)
    disable = tuple(_deactivation_calls("linux")[0])
    _adoption_scheduler(monkeypatch, {disable: (1, "", "Failed to disable unit")})

    status, _vault, _units = _install(tmp_path, activate=True)

    assert status["scheduler_activated"] is True
    assert status["adopted_legacy"] is False
    assert "disable --now" in status["legacy_adopt_error"]
    assert "Failed to disable unit" in status["legacy_adopt_error"]
    assert all(path.is_file() for path in legacy_files)
    assert load_status(vault)["legacy_adopt_error"] == status["legacy_adopt_error"]


def test_no_activate_install_never_touches_the_legacy_unit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    home = _home(tmp_path, monkeypatch, "linux")
    vault = tmp_path / "vault"
    vault.mkdir()
    legacy_files, _answers = _legacy_unit("linux", tmp_path, home, vault)
    calls = _adoption_scheduler(monkeypatch)

    status, _vault, _units = _install(tmp_path)

    assert calls == []
    assert all(path.is_file() for path in legacy_files)
    assert status["adopted_legacy"] is False


@pytest.mark.parametrize("fail", [False, True])
def test_cli_says_the_legacy_schedule_was_replaced_or_how_to_remove_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], fail: bool
):
    home = _home(tmp_path, monkeypatch, "linux")
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    vault = tmp_path / "vault"
    vault.mkdir()
    _legacy_unit("linux", tmp_path, home, vault)
    disable = tuple(_deactivation_calls("linux")[0])
    _adoption_scheduler(monkeypatch, {disable: (1, "", "Failed to disable unit")} if fail else None)

    code = cli.main([
        "install-automation", "--yes",
        "--units-dir", str(tmp_path / "units"),
        "--vault", str(vault),
        "--force-platform", "linux",
    ])

    out = capsys.readouterr().out
    assert code == 0
    replaced = "Replaced the earlier single llmwiki-maintain schedule with this vault's own schedule."
    assert (replaced in out) is not fail
    assert ("Failed to disable unit" in out) is fail
    assert (f"systemctl --user disable --now {LEGACY_SYSTEMD}.timer" in out) is fail


# ─── Setup guard and dev-checkout warning (@spec: 330-doctor-automation-serves-vault, R2) ───

_GUARD_ERROR = "install-automation: existing schedule runs from a different checkout; pass --force to replace it"
_WIZARD_YES = [ENTER, ENTER, ENTER, ENTER, ENTER, ENTER, ENTER, ENTER, "y"]


def _serving_unit(vault: Path, working_dir: Path, *, legacy: bool = False, target: Path | None = None) -> InstalledUnit:
    """A discovered unit for ``vault`` (per-vault named unless ``legacy``) running from ``working_dir``."""
    return InstalledUnit(
        name=LEGACY_SYSTEMD if legacy else unit_names(vault).base,
        platform="linux",
        legacy=legacy,
        wrapper_path=None,
        working_dir=working_dir,
        target_vault=target if legacy else vault,
        log_path=None,
        enabled=True,
        reason_unknown=None,
    )


def _discovers(monkeypatch: pytest.MonkeyPatch, *units: InstalledUnit, unavailable: str | None = None) -> None:
    monkeypatch.setattr(
        "llmwiki.automation_units.discover_local_units",
        lambda **_: DiscoveryResult(units=units, unavailable=unavailable),
    )


@pytest.mark.parametrize(("answer", "installs"), [("y", True), ("n", False), (ENTER, False)])
def test_wizard_asks_before_replacing_a_schedule_from_another_checkout(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    answer: str,
    installs: bool,
):
    """On a terminal, a schedule running another checkout is shown and only replaced on y."""
    other = tmp_path / "other-checkout"
    _discovers(monkeypatch, _serving_unit(tmp_path / "vault", other))
    code, config, prompts = _run_wizard(monkeypatch, tmp_path, [*_WIZARD_YES, answer])
    out = capsys.readouterr().out
    assert code == 0
    assert any("Replace it? [y/N]" in p for p in prompts)
    assert f"current schedule runs from: {other}" in out
    assert f"new schedule would run from: {tmp_path}" in out
    assert bool(config) is installs
    assert ("Kept the existing schedule" in out) is not installs


def test_yes_without_force_refuses_to_replace_a_schedule_from_another_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    _discovers(monkeypatch, _serving_unit(tmp_path / "vault", tmp_path / "other-checkout"))
    code, vault, units = _install_via_flags(tmp_path, monkeypatch, "--job", "ingest")
    captured = capsys.readouterr()
    assert code == 2
    assert _GUARD_ERROR in captured.err
    assert "current schedule runs from:" in captured.out
    assert load_status(vault) is None
    assert not units.exists()


def test_force_replaces_a_schedule_from_another_checkout_without_asking(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    other = tmp_path / "other-checkout"
    monkeypatch.setattr(sys, "stdin", io.StringIO())
    _discovers(monkeypatch, _serving_unit(tmp_path / "vault", other))
    code, vault, _units = _install_via_flags(tmp_path, monkeypatch, "--job", "ingest", "--force")
    out = capsys.readouterr().out
    assert code == 0
    assert load_status(vault) is not None
    assert f"current schedule runs from: {other}" in out
    assert f"new schedule would run from: {tmp_path}" in out


def test_guard_reads_unit_files_when_the_scheduler_cannot_be_asked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    other = tmp_path / "other-checkout"
    _discovers(
        monkeypatch,
        _serving_unit(tmp_path / "vault", other),
        unavailable="no systemd user session to ask (Failed to connect to bus)",
    )
    code, vault, _units = _install_via_flags(tmp_path, monkeypatch, "--job", "ingest")
    captured = capsys.readouterr()
    assert code == 2
    assert _GUARD_ERROR in captured.err
    assert f"current schedule runs from: {other}" in captured.out
    assert load_status(vault) is None


@pytest.mark.parametrize(
    "case",
    ["same_checkout", "legacy_for_another_vault", "legacy_unknown_target", "unknown_checkout"],
)
def test_guard_stays_quiet_when_no_schedule_from_another_checkout_serves_this_vault(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], case: str
):
    vault = tmp_path / "vault"
    other = tmp_path / "other-checkout"
    if case == "same_checkout":
        _discovers(monkeypatch, _serving_unit(vault, tmp_path))
    elif case == "legacy_for_another_vault":
        _discovers(monkeypatch, _serving_unit(vault, other, legacy=True, target=tmp_path / "elsewhere"))
    elif case == "legacy_unknown_target":
        _discovers(monkeypatch, _serving_unit(vault, other, legacy=True, target=None))
    else:
        unit = _serving_unit(vault, other)
        _discovers(monkeypatch, InstalledUnit(**{**unit.__dict__, "working_dir": None}))
    code, vault, _units = _install_via_flags(tmp_path, monkeypatch, "--job", "ingest")
    captured = capsys.readouterr()
    assert code == 0
    assert load_status(vault) is not None
    assert "schedule runs from" not in captured.out
    assert _GUARD_ERROR not in captured.err


def test_legacy_unit_serving_this_vault_from_another_checkout_is_guarded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    vault = tmp_path / "vault"
    _discovers(monkeypatch, _serving_unit(vault, tmp_path / "other-checkout", legacy=True, target=vault))
    code, _vault, _units = _install_via_flags(tmp_path, monkeypatch, "--job", "ingest")
    assert code == 2
    assert _GUARD_ERROR in capsys.readouterr().err


@pytest.mark.parametrize("flags", [(), ("--force",)])
@pytest.mark.parametrize(
    ("git_kind", "stem"),
    [
        ("file", "warning: installing from a git worktree — the scheduled job will keep using this copy at {root} and stops working when the worktree is removed."),
        ("dir", "warning: installing from a development checkout — the scheduled job will keep using this copy at {root}; deleting or switching it breaks the schedule."),
        (None, None),
    ],
)
def test_installing_from_a_git_checkout_warns_that_the_job_keeps_using_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    flags: tuple[str, ...],
    git_kind: str | None,
    stem: str | None,
):
    if git_kind == "file":
        (tmp_path / ".git").write_text("gitdir: /elsewhere\n", encoding="utf-8")
    elif git_kind == "dir":
        (tmp_path / ".git").mkdir()
    if flags:
        _discovers(monkeypatch, _serving_unit(tmp_path / "vault", tmp_path / "other-checkout"))
    code, _vault, _units = _install_via_flags(tmp_path, monkeypatch, "--job", "ingest", *flags)
    out = capsys.readouterr().out
    assert code == 0
    if stem is None:
        assert "warning: installing from" not in out
    else:
        assert stem.format(root=tmp_path) in out


def test_wizard_prints_the_dev_checkout_warning_before_asking_to_replace(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    (tmp_path / ".git").mkdir()
    _discovers(monkeypatch, _serving_unit(tmp_path / "vault", tmp_path / "other-checkout"))
    shown: list[str] = []

    def fake_input(prompt: str = "") -> str:
        shown.append(capsys.readouterr().out)
        return ([*_WIZARD_YES, "n"])[len(shown) - 1]

    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    _pretend_tty(monkeypatch)
    monkeypatch.setattr(cli, "run_install", lambda config: pytest.fail("installed after a no"))
    monkeypatch.setattr("builtins.input", fake_input)
    args = cli.build_parser().parse_args(["install-automation", "--vault", str(tmp_path / "vault")])
    assert cli.cmd_install_automation(args) == 0
    assert "warning: installing from a development checkout" in shown[-1]


def test_discovery_without_probe_reads_unit_files_but_never_asks_systemctl(tmp_path: Path):
    home = tmp_path / "home"
    vault = tmp_path / "vault"
    _systemd_unit(home, unit_names(vault).base, working_dir=tmp_path, log=tmp_path / "v.log", vault=vault)

    def _no_scheduler(args: list[str]) -> subprocess.CompletedProcess[str]:
        raise AssertionError(f"scheduler asked: {args}")

    (unit,) = discover_units("linux", home=home, run=_no_scheduler, probe=False).units

    assert unit.target_vault == vault
    assert unit.enabled is None


def test_removal_steps_quote_a_unit_name_with_shell_metacharacters(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    unit = InstalledUnit(
        name="llmwiki-maintain-x;rm -rf ~",
        platform="linux",
        legacy=False,
        wrapper_path=None,
        working_dir=None,
        target_vault=None,
        log_path=None,
        enabled=None,
        reason_unknown=None,
    )

    disable, remove, _reload = removal_steps(unit)

    assert shlex.split(disable)[-1] == "llmwiki-maintain-x;rm -rf ~.timer"
    assert [Path(p).name for p in shlex.split(remove)[1:]] == [
        "llmwiki-maintain-x;rm -rf ~.sh",
        "llmwiki-maintain-x;rm -rf ~.service",
        "llmwiki-maintain-x;rm -rf ~.timer",
    ]


def test_reinstall_without_hooks_keeps_the_hooks_the_status_records(tmp_path: Path):
    base = {
        "working_dir": tmp_path,
        "python_bin": "python3",
        "vault_root": tmp_path / "vault",
        "job": "ingest",
        "activate": False,
    }
    assert run_install({**base, "hooks": ["claude", "cursor"]})["hooks"] == ["claude", "cursor"]
    assert run_install(base)["hooks"] == ["claude", "cursor"]
    assert run_install({**base, "hooks": []})["hooks"] == []
