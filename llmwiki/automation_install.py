"""OS scheduler + agent-hook install helpers (stdlib only).

Turns an :class:`~llmwiki.automation_plan.AutomationPlan` and a cron schedule into
the files a scheduler consumes: a bash wrapper that runs the job and truncates its
log, plus a systemd service/timer pair, a launchd plist, or a Windows Task
Scheduler XML depending on the platform. The job's command line comes from
``automation_plan.plan_command`` and the schedule is rendered per backend by
``cron_spec``; nothing about either is decided here.

The same module merges llmwiki's managed SessionStart hook into Claude Code and
Cursor settings, and records what was installed in the vault's automation status
file.

Unit names are fixed (``llmwiki-maintain`` / ``com.llmwiki.maintain``) for
idempotent re-install. The systemd timer uses Persistent=true (catch-up after boot).
"""

from __future__ import annotations

import json
import platform
import shlex
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from llmwiki.automation_plan import AutomationPlan, plan_command, plan_from_status, plan_to_status, schedule_from_status
from llmwiki.automation_status import default_log_path, save_status
from llmwiki.cron_spec import (
    CronSpec,
    describe,
    parse_cron,
    to_launchd_intervals,
    to_systemd_oncalendar,
    to_windows_trigger,
)

HOOK_MARKER = "llmwiki-managed-sync"
UNIT_BASENAME = "llmwiki-maintain"
LAUNCHD_LABEL = "com.llmwiki.maintain"


def detect_platform() -> str:
    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    if system == "linux":
        return "linux"
    if system == "windows":
        return "windows"
    return "unknown"


def render_wrapper_script(
    *,
    plan: AutomationPlan,
    python_bin: str,
    working_dir: Path,
    log_path: Path,
    vault: Path | None = None,
) -> str:
    """Bash wrapper running the plan's command line, truncating the log each run.

    ``vault`` is forwarded to :func:`~llmwiki.automation_plan.plan_command`, which
    appends it as ``--vault`` when the scheduled run must not resolve its vault
    from config.
    """
    cmd = plan_command(plan, python_bin=python_bin, working_dir=working_dir, vault=vault)
    log = shlex.quote(str(log_path))
    return (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        f"mkdir -p \"$(dirname {log})\"\n"
        f"{{ {cmd} ; echo EXIT:$?; }} >{log} 2>&1\n"
    )


def render_systemd_service(*, wrapper: Path, working_dir: Path) -> str:
    return (
        "[Unit]\n"
        "Description=llmwiki maintain (managed by install-automation)\n"
        "After=network-online.target\n"
        "\n"
        "[Service]\n"
        "Type=oneshot\n"
        f"WorkingDirectory={working_dir}\n"
        f"ExecStart=/bin/bash {wrapper}\n"
        "\n"
        "[Install]\n"
        "WantedBy=default.target\n"
    )


def render_systemd_timer(*, spec: CronSpec) -> str:
    """systemd ``.timer`` unit firing on the schedule, catching up after a missed boot."""
    return (
        "[Unit]\n"
        "Description=llmwiki maintain daily timer\n"
        "\n"
        "[Timer]\n"
        f"OnCalendar={to_systemd_oncalendar(spec)}\n"
        "Persistent=true\n"
        "\n"
        "[Install]\n"
        "WantedBy=timers.target\n"
    )


def _plist_calendar_dict(interval: dict[str, int], indent: str) -> str:
    """Render one launchd calendar dict. Keys are sorted so the output is stable."""
    lines = [f"{indent}<dict>"]
    for key, value in sorted(interval.items()):
        lines.append(f"{indent}  <key>{key}</key>")
        lines.append(f"{indent}  <integer>{value}</integer>")
    lines.append(f"{indent}</dict>")
    return "\n".join(lines)


def _plist_calendar_value(spec: CronSpec) -> str:
    """Render the value of ``StartCalendarInterval``: one dict, or an array of them.

    launchd accepts either shape, and a schedule that expands to a single firing
    pattern reads better as a bare dict.
    """
    intervals = to_launchd_intervals(spec)
    if len(intervals) == 1:
        return _plist_calendar_dict(intervals[0], "  ")
    entries = "\n".join(_plist_calendar_dict(interval, "    ") for interval in intervals)
    return f"  <array>\n{entries}\n  </array>"


def render_launchd_plist(
    *,
    wrapper: Path,
    working_dir: Path,
    log_path: Path,
    spec: CronSpec,
) -> str:
    """launchd agent plist running the wrapper on the schedule, logging to ``log_path``.

    Every interpolated path is XML-escaped, so a vault or home directory holding
    ``&``, ``<`` or ``>`` still yields a plist launchd can parse.
    """
    wrapper_xml = escape(str(wrapper))
    working_dir_xml = escape(str(working_dir))
    log_path_xml = escape(str(log_path))
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>{LAUNCHD_LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>{wrapper_xml}</string>
  </array>
  <key>WorkingDirectory</key>
  <string>{working_dir_xml}</string>
  <key>StartCalendarInterval</key>
{_plist_calendar_value(spec)}
  <key>StandardOutPath</key>
  <string>{log_path_xml}</string>
  <key>StandardErrorPath</key>
  <string>{log_path_xml}</string>
</dict>
</plist>
"""


def render_windows_task(
    *,
    wrapper: Path,
    working_dir: Path,
    spec: CronSpec,
) -> str:
    """Task Scheduler XML running the wrapper on the schedule; the user imports it via schtasks.

    Every interpolated path is XML-escaped, so a path holding ``&``, ``<`` or
    ``>`` still yields a task file Task Scheduler can parse.
    """
    wrapper_xml = escape(str(wrapper))
    working_dir_xml = escape(str(working_dir))
    return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>llmwiki maintain (managed)</Description>
  </RegistrationInfo>
  <Triggers>
{to_windows_trigger(spec)}
  </Triggers>
  <Actions>
    <Exec>
      <Command>bash</Command>
      <Arguments>{wrapper_xml}</Arguments>
      <WorkingDirectory>{working_dir_xml}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"""


def merge_claude_session_start_hook(
    settings: dict[str, Any],
    command: str,
    *,
    install: bool,
) -> dict[str, Any]:
    """Idempotently merge/remove a managed SessionStart hook."""
    out = json.loads(json.dumps(settings))  # deep-ish copy via JSON
    hooks = out.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        hooks = {}
        out["hooks"] = hooks
    entries = hooks.get("SessionStart")
    if not isinstance(entries, list):
        entries = []
    # Drop previous managed entries
    cleaned: list[Any] = []
    for block in entries:
        if not isinstance(block, dict):
            cleaned.append(block)
            continue
        inner = block.get("hooks")
        if not isinstance(inner, list):
            cleaned.append(block)
            continue
        kept = [
            h for h in inner
            if not (
                isinstance(h, dict)
                and HOOK_MARKER in str(h.get("command", ""))
            )
        ]
        if kept:
            cleaned.append({**block, "hooks": kept})
        # else drop empty block
    if install:
        cleaned.append({
            "matcher": "*",
            "hooks": [{
                "type": "command",
                "command": f"# {HOOK_MARKER}\n{command}",
            }],
        })
    if cleaned:
        hooks["SessionStart"] = cleaned
    elif "SessionStart" in hooks:
        del hooks["SessionStart"]
    return out


def merge_cursor_session_start_hook(
    hooks_json: dict[str, Any],
    command: str,
    *,
    install: bool,
) -> dict[str, Any]:
    """Idempotently merge/remove managed Cursor sessionStart hook."""
    out = json.loads(json.dumps(hooks_json))
    out.setdefault("version", 1)
    hooks = out.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        hooks = {}
        out["hooks"] = hooks
    entries = hooks.get("sessionStart")
    if not isinstance(entries, list):
        entries = []
    cleaned = [
        e for e in entries
        if not (
            isinstance(e, dict)
            and HOOK_MARKER in str(e.get("command", e.get("script", "")))
        )
    ]
    if install:
        cleaned.append({
            "command": f"# {HOOK_MARKER}\n{command}",
        })
    if cleaned:
        hooks["sessionStart"] = cleaned
    elif "sessionStart" in hooks:
        del hooks["sessionStart"]
    return out


def run_install(config: dict[str, Any]) -> dict[str, Any]:
    """Non-interactive install API for the CLI, tests and ``setup.sh``.

    Required keys: ``working_dir``, ``python_bin``, ``vault_root`` (where the status
    file lands). The job is taken from an :class:`AutomationPlan` under ``plan``,
    otherwise read from ``job`` / ``graph`` / ``lint_fail`` or the legacy ``profile``
    letter; the schedule from the cron expression under ``schedule``, otherwise from
    the legacy ``hour`` / ``minute`` integers. Optional: ``watch_enabled``, ``hooks``
    (list), ``synth_backend``, ``log_path``, ``write_units_dir`` (Path to write unit
    files into), ``force_platform``, and ``command_vault`` — the vault the scheduled
    command names with ``--vault``, which callers set when the install targets a vault
    other than the configured default, so the job runs against the same vault whose
    status file records it.

    Raises:
        CronError: when the schedule is not an expression ``cron_spec`` can translate.
    """
    working_dir = Path(config["working_dir"])
    python_bin = str(config.get("python_bin") or "python3")
    supplied = config.get("plan")
    plan = supplied if isinstance(supplied, AutomationPlan) else plan_from_status(config)
    schedule = schedule_from_status(config)
    spec = parse_cron(schedule)
    log_path = Path(config.get("log_path") or default_log_path())
    vault_root = Path(config.get("vault_root") or working_dir)
    command_vault = Path(config["command_vault"]) if config.get("command_vault") else None
    write_dir = Path(config["write_units_dir"]) if config.get("write_units_dir") else None

    wrapper_text = render_wrapper_script(
        plan=plan,
        python_bin=python_bin,
        working_dir=working_dir,
        log_path=log_path,
        vault=command_vault,
    )
    written: list[str] = []
    if write_dir is not None:
        write_dir.mkdir(parents=True, exist_ok=True)
        wrapper = write_dir / f"{UNIT_BASENAME}.sh"
        wrapper.write_text(wrapper_text, encoding="utf-8")
        wrapper.chmod(0o755)
        written.append(str(wrapper))
        plat = detect_platform()
        if plat == "linux" or config.get("force_platform") == "linux":
            svc = write_dir / f"{UNIT_BASENAME}.service"
            tim = write_dir / f"{UNIT_BASENAME}.timer"
            svc.write_text(
                render_systemd_service(wrapper=wrapper, working_dir=working_dir),
                encoding="utf-8",
            )
            tim.write_text(render_systemd_timer(spec=spec), encoding="utf-8")
            written.extend([str(svc), str(tim)])
        elif plat == "macos" or config.get("force_platform") == "macos":
            plist = write_dir / f"{LAUNCHD_LABEL}.plist"
            plist.write_text(
                render_launchd_plist(
                    wrapper=wrapper,
                    working_dir=working_dir,
                    log_path=log_path,
                    spec=spec,
                ),
                encoding="utf-8",
            )
            written.append(str(plist))
        elif plat == "windows" or config.get("force_platform") == "windows":
            xml = write_dir / f"{UNIT_BASENAME}-task.xml"
            xml.write_text(
                render_windows_task(wrapper=wrapper, working_dir=working_dir, spec=spec),
                encoding="utf-8",
            )
            written.append(str(xml))

    status = {
        **plan_to_status(plan),
        "schedule": schedule,
        "schedule_label": describe(spec),
        # Legacy integers, kept so an older llmwiki reading this file still shows a time.
        "hour": spec.hours[0] if spec.hours else 0,
        "minute": spec.minutes[0] if spec.minutes else 0,
        "watch_enabled": bool(config.get("watch_enabled", False)),
        "hooks": list(config.get("hooks") or []),
        "synth_backend": str(config.get("synth_backend") or "dummy"),
        "log_path": str(log_path),
        "units_written": written,
        "note": (
            "Scheduled runs with no new/changed sessions are a no-op "
            "(sync converts nothing; synth/build exit quickly)."
        ),
    }
    save_status(vault_root, status)
    return status
