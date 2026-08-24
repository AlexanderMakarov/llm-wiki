"""OS scheduler + agent-hook install helpers (stdlib only).

Profiles:
  A — sync (auto-build)
  B — sync --no-auto-build && synth && build
  C — all --with-sync --with-synth --skip-graph

Unit names are fixed (``llmwiki-maintain`` / ``com.llmwiki.maintain``) for
idempotent re-install. Daily timer uses Persistent=true (catch-up after boot).
"""

from __future__ import annotations

import json
import platform
import shlex
from pathlib import Path
from typing import Any

from llmwiki.automation_status import default_log_path, save_status

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


def profile_command(profile: str, python_bin: str, working_dir: Path) -> str:
    """Shell command line for the chosen profile (cwd = working_dir)."""
    py = shlex.quote(python_bin)
    root = shlex.quote(str(working_dir))
    prefix = f"cd {root} && {py} -m llmwiki"
    key = (profile or "A").upper()
    if key == "B":
        return (
            f"{prefix} sync --no-auto-build && "
            f"{py} -m llmwiki synth && "
            f"{py} -m llmwiki build"
        )
    if key == "C":
        return f"{prefix} all --with-sync --with-synth --skip-graph"
    return f"{prefix} sync"


def render_wrapper_script(
    *,
    profile: str,
    python_bin: str,
    working_dir: Path,
    log_path: Path,
) -> str:
    """Bash wrapper that truncates the log each run."""
    cmd = profile_command(profile, python_bin, working_dir)
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


def render_systemd_timer(*, hour: int, minute: int) -> str:
    return (
        "[Unit]\n"
        "Description=llmwiki maintain daily timer\n"
        "\n"
        "[Timer]\n"
        f"OnCalendar=*-*-* {hour:02d}:{minute:02d}:00\n"
        "Persistent=true\n"
        "\n"
        "[Install]\n"
        "WantedBy=timers.target\n"
    )


def render_launchd_plist(
    *,
    wrapper: Path,
    working_dir: Path,
    log_path: Path,
    hour: int,
    minute: int,
) -> str:
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
    <string>{wrapper}</string>
  </array>
  <key>WorkingDirectory</key>
  <string>{working_dir}</string>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>{hour}</integer>
    <key>Minute</key>
    <integer>{minute}</integer>
  </dict>
  <key>StandardOutPath</key>
  <string>{log_path}</string>
  <key>StandardErrorPath</key>
  <string>{log_path}</string>
</dict>
</plist>
"""


def render_windows_task(
    *,
    wrapper: Path,
    working_dir: Path,
    hour: int,
    minute: int,
) -> str:
    # Minimal Task Scheduler XML; user imports via schtasks.
    start = f"2026-01-01T{hour:02d}:{minute:02d}:00"
    return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>llmwiki maintain (managed)</Description>
  </RegistrationInfo>
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>{start}</StartBoundary>
      <Enabled>true</Enabled>
      <ScheduleByDay>
        <DaysInterval>1</DaysInterval>
      </ScheduleByDay>
    </CalendarTrigger>
  </Triggers>
  <Actions>
    <Exec>
      <Command>bash</Command>
      <Arguments>{wrapper}</Arguments>
      <WorkingDirectory>{working_dir}</WorkingDirectory>
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
    """Non-interactive install API for tests and setup.sh.

    Required keys: profile (A|B|C), hour, minute, working_dir, python_bin,
    vault_root (for status file). Optional: watch_enabled, hooks (list),
    synth_backend, log_path, write_units_dir (Path to write unit files).
    """
    working_dir = Path(config["working_dir"])
    python_bin = str(config.get("python_bin") or "python3")
    profile = str(config.get("profile") or "A").upper()
    hour = int(config.get("hour", 8))
    minute = int(config.get("minute", 0))
    log_path = Path(config.get("log_path") or default_log_path())
    vault_root = Path(config.get("vault_root") or working_dir)
    write_dir = Path(config["write_units_dir"]) if config.get("write_units_dir") else None

    wrapper_text = render_wrapper_script(
        profile=profile,
        python_bin=python_bin,
        working_dir=working_dir,
        log_path=log_path,
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
            tim.write_text(
                render_systemd_timer(hour=hour, minute=minute),
                encoding="utf-8",
            )
            written.extend([str(svc), str(tim)])
        elif plat == "macos" or config.get("force_platform") == "macos":
            plist = write_dir / f"{LAUNCHD_LABEL}.plist"
            plist.write_text(
                render_launchd_plist(
                    wrapper=wrapper,
                    working_dir=working_dir,
                    log_path=log_path,
                    hour=hour,
                    minute=minute,
                ),
                encoding="utf-8",
            )
            written.append(str(plist))
        elif plat == "windows" or config.get("force_platform") == "windows":
            xml = write_dir / f"{UNIT_BASENAME}-task.xml"
            xml.write_text(
                render_windows_task(
                    wrapper=wrapper, working_dir=working_dir,
                    hour=hour, minute=minute,
                ),
                encoding="utf-8",
            )
            written.append(str(xml))

    status = {
        "profile": profile,
        "hour": hour,
        "minute": minute,
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
