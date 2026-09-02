"""Tests for automation install renderers + status + hook merge.

The three unit renderers are pinned byte-for-byte on the default daily schedule:
an existing install must not silently change shape when the schedule notation does.
"""

from __future__ import annotations

import io
import json
import os
import shlex
import subprocess
import sys
import textwrap
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import pytest

from llmwiki import automation_install as ai_module
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
    resolve_main_worktree,
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


# ─── Main worktree resolution (#206) ───────────────────────────────────


def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    )


def test_resolve_main_worktree_returns_path_unchanged_when_not_a_git_repo(tmp_path: Path):
    """Installed packages and other non-git checkouts keep today's behavior."""
    not_a_repo = tmp_path / "plain-dir"
    not_a_repo.mkdir()
    assert resolve_main_worktree(not_a_repo) == not_a_repo.resolve()


def test_resolve_main_worktree_returns_itself_for_the_main_worktree(tmp_path: Path):
    main = tmp_path / "main"
    main.mkdir()
    _git("init", "-q", cwd=main)
    _git("-c", "user.email=t@example.com", "-c", "user.name=t", "commit", "--allow-empty", "-q", "-m", "init", cwd=main)
    assert resolve_main_worktree(main) == main.resolve()


def test_resolve_main_worktree_returns_main_for_a_linked_worktree(tmp_path: Path):
    """The #206 case: installing from a linked worktree must resolve back to main."""
    main = tmp_path / "main"
    main.mkdir()
    _git("init", "-q", cwd=main)
    _git("-c", "user.email=t@example.com", "-c", "user.name=t", "commit", "--allow-empty", "-q", "-m", "init", cwd=main)
    linked = tmp_path / "linked"
    _git("worktree", "add", "-q", str(linked), "-b", "feature", cwd=main)
    assert resolve_main_worktree(linked) == main.resolve()
    # The linked worktree's own config.json (if any) is what #206 says must be bypassed.
    assert resolve_main_worktree(linked) != linked.resolve()


def test_resolve_main_worktree_falls_back_with_a_warning_on_detection_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """A git that reports being inside a work tree but then fails to list worktrees
    must not raise — it falls back to the given path and warns on stderr."""
    real_run = subprocess.run

    def fake_run(args, **kwargs):
        if args[1:3] == ["-C", str(tmp_path.resolve())] and args[3:] == ["rev-parse", "--is-inside-work-tree"]:
            return subprocess.CompletedProcess(args, 0, stdout="true\n", stderr="")
        if "worktree" in args and "list" in args:
            return subprocess.CompletedProcess(args, 128, stdout="", stderr="fatal: not a git repository")
        return real_run(args, **kwargs)

    monkeypatch.setattr(ai_module.subprocess, "run", fake_run)
    result = resolve_main_worktree(tmp_path)
    assert result == tmp_path.resolve()
    err = capsys.readouterr().err
    assert "could not resolve the git main worktree" in err
    assert "worktree-local config.json" in err


def test_resolve_main_worktree_returns_path_unchanged_when_git_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(ai_module.shutil, "which", lambda _name: None)
    assert resolve_main_worktree(tmp_path) == tmp_path.resolve()


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
    assert "pip install llm-wiki[graph]" in out


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


def test_yes_installs_with_a_non_terminal_stdin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """The unattended path is the one a pipe is allowed to take."""
    monkeypatch.setattr(sys, "stdin", io.StringIO())
    code, vault, units = _install_via_flags(tmp_path, monkeypatch, "--job", "ingest")
    assert code == 0
    assert load_status(vault) is not None
    assert (units / "llmwiki-maintain.sh").is_file()


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
    wrapper = (units / "llmwiki-maintain.sh").read_text(encoding="utf-8")
    assert "--lint-fail" not in wrapper and "--graph-engine" not in wrapper
    assert "mark the scheduled run as failed" not in render_automation_panel(vault)


def test_a_non_default_vault_is_named_in_the_scheduled_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Installing against a vault other than ``vault.default_path`` must schedule a command
    that names it, or the run would work on the default vault while its status file sits in
    the installed one."""
    monkeypatch.setattr(cli, "load_default_vault_path", lambda: tmp_path / "default-vault")
    _code, vault, units = _install_via_flags(tmp_path, monkeypatch, "--job", "ingest")
    wrapper = (units / "llmwiki-maintain.sh").read_text(encoding="utf-8")
    assert f"--vault {shlex.quote(str(vault))}" in wrapper
    expected = plan_command(
        AutomationPlan(job="ingest"), python_bin=sys.executable, working_dir=tmp_path, vault=vault
    )
    assert expected in wrapper


def test_the_default_vault_leaves_the_scheduled_command_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """When the install targets the configured default, the command stays byte-identical
    and resolves its vault from config the way it always did."""
    vault_root = tmp_path / "vault"
    monkeypatch.setattr(cli, "load_default_vault_path", lambda: vault_root)
    _code, _vault, units = _install_via_flags(tmp_path, monkeypatch, "--job", "ingest")
    wrapper = (units / "llmwiki-maintain.sh").read_text(encoding="utf-8")
    assert "--vault" not in wrapper
    expected = plan_command(AutomationPlan(job="ingest"), python_bin=sys.executable, working_dir=tmp_path)
    assert f"{{ {expected} ; echo EXIT:$?; }}" in wrapper


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


def test_panel_does_not_advertise_a_failure_policy_for_an_ingest_job(tmp_path: Path):
    """An ingest job runs no lint step; the panel must not promise findings can fail it."""
    panel = _panel(tmp_path, plan_to_status(AutomationPlan(job="ingest", lint_fail="errors")))
    assert "Ingest only" in panel
    assert "mark the scheduled run as failed" not in panel


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
    staging_wrapper = units / "llmwiki-maintain.sh"
    staging_wrapper.write_text("# wrapper\n", encoding="utf-8")
    (units / "llmwiki-maintain.service").write_text(
        render_systemd_service(wrapper=staging_wrapper, working_dir=tmp_path),
        encoding="utf-8",
    )
    (units / "llmwiki-maintain.timer").write_text("# timer\n", encoding="utf-8")
    log = _fake_systemctl(tmp_path, monkeypatch)

    result = activate_scheduler(platform="linux", units_source_dir=units, working_dir=tmp_path)

    dest = default_scheduler_units_dir("linux")
    assert result["scheduler_activated"] is True
    assert result["scheduler_backend"] == "systemd"
    assert result["scheduler_active"] is True
    assert result["scheduler_error"] is None
    installed_service = (dest / "llmwiki-maintain.service").read_text(encoding="utf-8")
    assert str(dest / "llmwiki-maintain.sh") in installed_service
    assert str(staging_wrapper) not in installed_service
    assert (dest / "llmwiki-maintain.timer").read_text(encoding="utf-8") == "# timer\n"
    logged = log.read_text(encoding="utf-8")
    assert "--user daemon-reload" in logged
    assert "enable --now llmwiki-maintain.timer" in logged
    assert "is-enabled llmwiki-maintain.timer" in logged


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
