"""Scheduler unit naming and the scheduler subprocess seam (stdlib only).

Every OS job llmwiki installs carries a stable per-vault id derived from the
resolved vault path, so two vaults never share (or overwrite) one schedule. The
legacy single-unit names are kept here so install and doctor can recognise a
schedule written before units became per vault.
"""

from __future__ import annotations

import csv
import hashlib
import io
import os
import platform as _platform
import plistlib
import re
import shlex
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from xml.parsers.expat import ExpatError

from llmwiki.config_schedule import default_vault_for_checkout

LEGACY_SYSTEMD = "llmwiki-maintain"
LEGACY_LAUNCHD = "com.llmwiki.maintain"

_SLUG_MAX = 24
_HASH_LEN = 8
_NON_SLUG = re.compile(r"[^a-z0-9]+")


def _slug(name: str) -> str:
    slug = _NON_SLUG.sub("-", name.lower()).strip("-")[:_SLUG_MAX].rstrip("-")
    return slug or "vault"


def vault_unit_id(vault: Path) -> str:
    """Stable id for ``vault``: slug of its basename plus a short hash of its resolved path."""
    resolved = Path(vault).expanduser().resolve()
    key = str(resolved)
    if sys.platform == "darwin" or os.name == "nt":
        key = os.path.normcase(key)
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:_HASH_LEN]
    return f"{_slug(resolved.name)}-{digest}"


@dataclass(frozen=True)
class UnitNames:
    """Every OS scheduler name and file name for one vault's unit."""

    base: str
    launchd_label: str
    wrapper: str
    service: str
    timer: str
    plist: str
    task_xml: str
    task_name: str


def unit_names(vault: Path) -> UnitNames:
    """Per-vault scheduler names for ``vault`` on every platform."""
    unit_id = vault_unit_id(vault)
    base = f"{LEGACY_SYSTEMD}-{unit_id}"
    label = f"{LEGACY_LAUNCHD}.{unit_id}"
    return UnitNames(
        base=base,
        launchd_label=label,
        wrapper=f"{base}.sh",
        service=f"{base}.service",
        timer=f"{base}.timer",
        plist=f"{label}.plist",
        task_xml=f"{base}-task.xml",
        task_name=base,
    )


def run_scheduler_cmd(args: list[str]) -> subprocess.CompletedProcess[str]:
    """Run one scheduler command (systemctl / launchctl / schtasks) without raising on failure."""
    return subprocess.run(
        args,
        check=False,
        capture_output=True,
        text=True,
        errors="replace",
    )


def is_dev_checkout(root: Path) -> Literal["worktree", "checkout"] | None:
    """``"worktree"`` when ``root/.git`` is a file, ``"checkout"`` when a directory, else ``None``."""
    git = Path(root) / ".git"
    if git.is_file():
        return "worktree"
    if git.is_dir():
        return "checkout"
    return None


DEV_CHECKOUT_WARNINGS: dict[str, str] = {
    "worktree": (
        "installing from a git worktree — the scheduled job will keep using this copy "
        "at {root} and stops working when the worktree is removed."
    ),
    "checkout": (
        "installing from a development checkout — the scheduled job will keep using this "
        "copy at {root}; deleting or switching it breaks the schedule."
    ),
}


def dev_checkout_warning(root: Path) -> str | None:
    """The warning for scheduling a job from ``root`` when it is a git checkout, else ``None``."""
    kind = is_dev_checkout(root)
    if kind is None:
        return None
    return DEV_CHECKOUT_WARNINGS[kind].format(root=root)


# ─── Discovery of installed units ──────────────────────────────────────

SchedulerRun = Callable[[list[str]], subprocess.CompletedProcess[str]]

_TASK_NS = {"t": "http://schemas.microsoft.com/windows/2004/02/mit/task"}
_XML_DECL = re.compile(r"^\s*<\?xml[^>]*\?>")


@dataclass(frozen=True)
class WrapperCommand:
    """What one wrapper script's ``-m llmwiki`` line runs: checkout, vault and log."""

    working_dir: Path | None
    vault: Path | None
    log_path: Path | None


@dataclass(frozen=True)
class InstalledUnit:
    """One llmwiki job found in the OS scheduler, and the vault it really serves.

    ``target_vault`` is ``None`` (with ``reason_unknown`` saying why) whenever the
    target cannot be read off the unit; it is never guessed. ``enabled`` is
    ``None`` when the scheduler could not be asked.
    """

    name: str
    platform: str
    legacy: bool
    wrapper_path: Path | None
    working_dir: Path | None
    target_vault: Path | None
    log_path: Path | None
    enabled: bool | None
    reason_unknown: str | None


@dataclass(frozen=True)
class DiscoveryResult:
    """Every unit found, plus why the scheduler itself could not be inspected (if so)."""

    units: tuple[InstalledUnit, ...]
    unavailable: str | None


def _token_after(tokens: list[str], marker: str) -> str | None:
    try:
        return tokens[tokens.index(marker) + 1]
    except (ValueError, IndexError):
        return None


def parse_wrapper(text: str) -> WrapperCommand | None:
    """Parse wrapper script ``text`` as rendered by ``render_wrapper_script``.

    The line holding ``-m llmwiki`` is shell-split: the working dir is the token
    after ``cd``, the vault the token after ``--vault`` and the log the redirect
    target after ``>``. Returns ``None`` when no such line exists or it does not split.
    """
    line = next((ln for ln in text.splitlines() if "-m llmwiki" in ln), None)
    if line is None:
        return None
    lexer = shlex.shlex(line, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    try:
        tokens = list(lexer)
    except ValueError:
        return None
    found = [_token_after(tokens, marker) for marker in ("cd", "--vault", ">")]
    working_dir, vault, log = (Path(tok) if tok else None for tok in found)
    return WrapperCommand(working_dir=working_dir, vault=vault, log_path=log)


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def _checkout_target(working_dir: Path) -> tuple[Path | None, str | None]:
    """Vault a wrapper without ``--vault`` resolves when it runs from ``working_dir``."""
    if not working_dir.is_dir():
        return None, f"checkout {working_dir.name} no longer exists"
    configured = default_vault_for_checkout(working_dir)
    if configured is not None:
        return configured, None
    if (working_dir / "llmwiki" / "__init__.py").is_file():
        # No configured default: the checkout's own llmwiki uses the checkout as vault.
        return working_dir, None
    return None, f"checkout {working_dir.name} names no vault in its config"


def _build_unit(
    *,
    name: str,
    platform: str,
    legacy: bool,
    wrapper_path: Path | None,
    unit_working_dir: Path | None,
    unit_log_path: Path | None = None,
    enabled: bool | None,
) -> InstalledUnit:
    """Read the wrapper and combine it with what the scheduler unit itself declares."""
    parsed: WrapperCommand | None = None
    reason: str | None = None
    if wrapper_path is None:
        reason = "unit names no wrapper script"
    else:
        try:
            parsed = parse_wrapper(wrapper_path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            reason = f"wrapper {wrapper_path.name} is missing or unreadable"
        else:
            if parsed is None:
                reason = f"wrapper {wrapper_path.name} runs no llmwiki command"
    working_dir = (parsed.working_dir if parsed else None) or unit_working_dir
    target: Path | None = parsed.vault if parsed else None
    if parsed is not None and target is None:
        if working_dir is None:
            reason = f"wrapper {wrapper_path.name if wrapper_path else name} names no checkout"
        else:
            target, reason = _checkout_target(working_dir)
    return InstalledUnit(
        name=name,
        platform=platform,
        legacy=legacy,
        wrapper_path=wrapper_path,
        working_dir=working_dir,
        target_vault=target,
        log_path=(parsed.log_path if parsed else None) or unit_log_path,
        enabled=enabled,
        reason_unknown=reason,
    )


def _systemd_fields(service: Path) -> tuple[Path | None, Path | None]:
    """``(wrapper, WorkingDirectory)`` from a rendered ``.service`` file."""
    wrapper: Path | None = None
    working_dir: Path | None = None
    for line in service.read_text(encoding="utf-8", errors="replace").splitlines():
        key, sep, value = line.partition("=")
        if not sep:
            continue
        if key.strip() == "ExecStart":
            # ``/bin/bash <wrapper>``: the wrapper is everything after the interpreter.
            parts = value.strip().split(maxsplit=1)
            if len(parts) == 2:
                wrapper = Path(_strip_quotes(parts[1]))
        elif key.strip() == "WorkingDirectory" and value.strip():
            working_dir = Path(_strip_quotes(value))
    return wrapper, working_dir


def _discover_linux(home: Path, run: SchedulerRun, probe: bool) -> DiscoveryResult:
    units: list[InstalledUnit] = []
    unavailable: str | None = None
    unit_dir = home / ".config" / "systemd" / "user"
    for service in sorted(unit_dir.glob(f"{LEGACY_SYSTEMD}*.service")):
        name = service.stem
        enabled: bool | None = None
        if probe and unavailable is None:
            try:
                proc = run(["systemctl", "--user", "is-enabled", f"{name}.timer"])
            except FileNotFoundError:
                unavailable = "systemctl is not installed"
            else:
                output = f"{proc.stdout}\n{proc.stderr}"
                if proc.returncode != 0 and "Failed to connect" in output:
                    unavailable = "no systemd user session to ask (Failed to connect to bus)"
                else:
                    enabled = proc.returncode == 0 and proc.stdout.strip() in {
                        "enabled",
                        "enabled-runtime",
                    }
        try:
            wrapper, working_dir = _systemd_fields(service)
        except OSError:
            wrapper, working_dir = None, None
        units.append(
            _build_unit(
                name=name,
                platform="linux",
                legacy=name == LEGACY_SYSTEMD,
                wrapper_path=wrapper,
                unit_working_dir=working_dir,
                enabled=enabled,
            )
        )
    return DiscoveryResult(units=tuple(units), unavailable=unavailable)


def _discover_macos(home: Path, run: SchedulerRun, uid: int | None, probe: bool) -> DiscoveryResult:
    units: list[InstalledUnit] = []
    unavailable: str | None = None
    domain_uid = os.getuid() if uid is None else uid
    agents = home / "Library" / "LaunchAgents"
    for plist_file in sorted(agents.glob(f"{LEGACY_LAUNCHD}*.plist")):
        try:
            with plist_file.open("rb") as fh:
                data = plistlib.load(fh)
        except (OSError, ValueError, ExpatError) as exc:
            units.append(
                InstalledUnit(
                    name=plist_file.stem,
                    platform="macos",
                    legacy=plist_file.stem == LEGACY_LAUNCHD,
                    wrapper_path=None,
                    working_dir=None,
                    target_vault=None,
                    log_path=None,
                    enabled=None,
                    reason_unknown=f"plist {plist_file.name} is unreadable: {exc}",
                )
            )
            continue
        label = str(data.get("Label") or plist_file.stem)
        args = data.get("ProgramArguments")
        wrapper = Path(str(args[1])) if isinstance(args, list) and len(args) > 1 else None
        working_dir = Path(str(data["WorkingDirectory"])) if data.get("WorkingDirectory") else None
        log_path = Path(str(data["StandardOutPath"])) if data.get("StandardOutPath") else None
        enabled: bool | None = None
        if probe and unavailable is None:
            try:
                proc = run(["launchctl", "print", f"gui/{domain_uid}/{label}"])
            except FileNotFoundError:
                unavailable = "launchctl is not installed"
            else:
                if proc.returncode == 0:
                    enabled = True
                elif "Could not find service" in f"{proc.stdout}\n{proc.stderr}":
                    enabled = False
        units.append(
            _build_unit(
                name=label,
                platform="macos",
                legacy=label == LEGACY_LAUNCHD,
                wrapper_path=wrapper,
                unit_working_dir=working_dir,
                unit_log_path=log_path,
                enabled=enabled,
            )
        )
    return DiscoveryResult(units=tuple(units), unavailable=unavailable)


def _task_fields(xml_text: str) -> tuple[Path | None, Path | None]:
    """``(wrapper, WorkingDirectory)`` from ``schtasks /Query /XML`` output."""
    root = ET.fromstring(_XML_DECL.sub("", xml_text, count=1))
    exec_el = root.find("t:Actions/t:Exec", _TASK_NS)
    if exec_el is None:
        return None, None
    arguments = exec_el.findtext("t:Arguments", default="", namespaces=_TASK_NS).strip()
    working = exec_el.findtext("t:WorkingDirectory", default="", namespaces=_TASK_NS).strip()
    return (
        Path(_strip_quotes(arguments)) if arguments else None,
        Path(_strip_quotes(working)) if working else None,
    )


def _discover_windows(run: SchedulerRun) -> DiscoveryResult:
    try:
        listing = run(["schtasks", "/Query", "/FO", "CSV", "/NH"])
    except OSError as exc:
        return DiscoveryResult(units=(), unavailable=f"schtasks could not run: {exc}")
    if listing.returncode != 0:
        detail = (listing.stderr or listing.stdout or "").strip()
        return DiscoveryResult(units=(), unavailable=f"schtasks /Query failed: {detail}")
    states: dict[str, str] = {}
    for row in csv.reader(io.StringIO(listing.stdout)):
        if row and row[0].startswith(f"\\{LEGACY_SYSTEMD}"):
            states.setdefault(row[0], row[2] if len(row) > 2 else "")
    units: list[InstalledUnit] = []
    for full_name, state in states.items():
        try:
            proc = run(["schtasks", "/Query", "/TN", full_name, "/XML"])
        except OSError as exc:
            return DiscoveryResult(units=tuple(units), unavailable=f"schtasks could not run: {exc}")
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip()
            return DiscoveryResult(
                units=tuple(units), unavailable=f"schtasks /Query /TN {full_name} failed: {detail}"
            )
        try:
            wrapper, working_dir = _task_fields(proc.stdout)
        except ET.ParseError as exc:
            return DiscoveryResult(
                units=tuple(units), unavailable=f"task {full_name} XML does not parse: {exc}"
            )
        name = full_name.lstrip("\\")
        units.append(
            _build_unit(
                name=name,
                platform="windows",
                legacy=name == LEGACY_SYSTEMD,
                wrapper_path=wrapper,
                unit_working_dir=working_dir,
                enabled=state.strip().lower() != "disabled",
            )
        )
    return DiscoveryResult(units=tuple(units), unavailable=None)


def discover_units(
    platform: str,
    *,
    home: Path,
    run: SchedulerRun = run_scheduler_cmd,
    uid: int | None = None,
    probe: bool = True,
) -> DiscoveryResult:
    """Every llmwiki unit (per-vault and legacy) installed for ``platform`` under ``home``.

    ``platform`` is ``linux`` / ``macos`` / ``windows`` (as ``detect_platform``
    returns it); anything else yields an empty result with ``unavailable`` set.
    ``run`` is the scheduler subprocess seam and ``uid`` the launchd GUI domain
    (default: the current user). ``probe=False`` reads the unit files only and
    leaves ``enabled`` as ``None`` (Windows still lists and reads its tasks,
    since the task store is the only source of their targets).
    """
    if platform == "linux":
        return _discover_linux(Path(home), run, probe)
    if platform == "macos":
        return _discover_macos(Path(home), run, uid, probe)
    if platform == "windows":
        return _discover_windows(run)
    return DiscoveryResult(units=(), unavailable=f"unsupported platform: {platform}")


def detect_platform() -> str:
    """``linux`` / ``macos`` / ``windows`` for this machine, else ``unknown``."""
    system = _platform.system().lower()
    if system == "darwin":
        return "macos"
    if system in ("linux", "windows"):
        return system
    return "unknown"


def discover_local_units(*, probe: bool = True) -> DiscoveryResult:
    """Every llmwiki unit this machine's scheduler holds for the current user.

    The one seam install and doctor share; ``probe`` is as for :func:`discover_units`.
    """
    return discover_units(detect_platform(), home=Path.home(), probe=probe)


def serves_vault(unit: InstalledUnit, vault: Path) -> bool:
    """Whether ``unit`` runs against ``vault`` (compared resolved).

    A known target decides. With the target unreadable, only the vault's own
    per-vault unit counts, since its name pins the vault; a legacy unit does not.
    """
    root = Path(vault).expanduser().resolve()
    if unit.target_vault is not None:
        return Path(unit.target_vault).expanduser().resolve() == root
    names = unit_names(root)
    return unit.name in (names.base, names.launchd_label)


def legacy_unit_serving(vault: Path, discovery: DiscoveryResult) -> InstalledUnit | None:
    """The legacy single unit when its known target is ``vault``, else ``None``."""
    return next(
        (unit for unit in discovery.units if unit.legacy and unit.target_vault is not None and serves_vault(unit, vault)),
        None,
    )


def unit_for_vault(vault: Path, discovery: DiscoveryResult) -> InstalledUnit | None:
    """The unit that schedules ``vault``: its own per-vault unit, else the legacy one."""
    names = unit_names(vault)
    for unit in discovery.units:
        if unit.name in (names.base, names.launchd_label):
            return unit
    return next((unit for unit in discovery.units if unit.legacy), None)


# ─── Deactivating a unit ───────────────────────────────────────────────

# launchctl's answers for a job that is not loaded: nothing left to boot out.
_LAUNCHD_NOT_LOADED = ("Could not find service", "No such process")


def _cmd_error(args: list[str], proc: subprocess.CompletedProcess[str]) -> str:
    detail = (proc.stderr or proc.stdout or "").strip()
    return f"{shlex.join(args)} failed" + (f": {detail}" if detail else "")


def _unlink_all(paths: list[Path]) -> str | None:
    for path in paths:
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            return f"could not remove {path.name}: {exc.strerror or exc}"
    return None


def deactivate_unit(
    unit: InstalledUnit,
    *,
    home: Path,
    run: SchedulerRun = run_scheduler_cmd,
    uid: int | None = None,
) -> str | None:
    """Switch ``unit`` off in its scheduler and remove its files; return error text or ``None``.

    systemd: ``disable --now`` the timer, remove ``<name>.sh/.service/.timer`` from
    the user unit dir, then ``daemon-reload``. launchd: ``bootout`` the label (a job
    that is not loaded counts as done), then remove ``<label>.plist`` and the wrapper.
    Windows: ``schtasks /Delete`` the task, then remove the wrapper and the
    ``<name>-task.xml`` beside it. Files already gone are not errors; a failed
    command stops before any file is removed.
    """
    try:
        if unit.platform == "linux":
            unit_dir = Path(home) / ".config" / "systemd" / "user"
            args = ["systemctl", "--user", "disable", "--now", f"{unit.name}.timer"]
            proc = run(args)
            if proc.returncode != 0:
                return _cmd_error(args, proc)
            error = _unlink_all([unit_dir / f"{unit.name}{ext}" for ext in (".sh", ".service", ".timer")])
            if error:
                return error
            args = ["systemctl", "--user", "daemon-reload"]
            proc = run(args)
            return _cmd_error(args, proc) if proc.returncode != 0 else None
        if unit.platform == "macos":
            agents = Path(home) / "Library" / "LaunchAgents"
            domain_uid = os.getuid() if uid is None else uid
            args = ["launchctl", "bootout", f"gui/{domain_uid}", unit.name]
            proc = run(args)
            output = f"{proc.stdout}\n{proc.stderr}"
            if proc.returncode != 0 and not any(text in output for text in _LAUNCHD_NOT_LOADED):
                return _cmd_error(args, proc)
            paths = [agents / f"{unit.name}.plist"]
            if unit.wrapper_path is not None:
                paths.append(unit.wrapper_path)
            return _unlink_all(paths)
        if unit.platform == "windows":
            args = ["schtasks", "/Delete", "/TN", unit.name, "/F"]
            proc = run(args)
            if proc.returncode != 0:
                return _cmd_error(args, proc)
            if unit.wrapper_path is None:
                return None
            return _unlink_all([unit.wrapper_path, unit.wrapper_path.parent / f"{unit.name}-task.xml"])
    except OSError as exc:
        return f"scheduler command could not run: {exc}"
    return f"unsupported platform: {unit.platform}"


# ─── Manual removal steps ──────────────────────────────────────────────


def _home_relative(path: Path, *, sep: str = "/") -> str:
    """``path`` as ``~``-relative text when it lies under the home directory, else unchanged."""
    try:
        rel = Path(path).relative_to(Path.home())
    except ValueError:
        return str(path)
    return sep.join(("~", *rel.parts))


def _shell_path(text: str) -> str:
    """Shell-quote ``text`` while leaving a leading ``~/`` outside the quotes so it still expands."""
    if text.startswith("~/"):
        return "~/" + shlex.quote(text[2:])
    return shlex.quote(text)


def removal_steps(unit: InstalledUnit) -> list[str]:
    """Copy-pasteable commands that switch ``unit`` off and delete its files, for its platform.

    Paths under the home directory are written ``~``-relative. The launchd and
    Windows wrapper is the one the unit records; launchd falls back to the
    wrapper beside its plist when the unit records none.
    """
    if unit.platform == "linux":
        files = " ".join(
            _shell_path(f"~/.config/systemd/user/{unit.name}.{ext}") for ext in ("sh", "service", "timer")
        )
        return [
            f"systemctl --user disable --now {shlex.quote(unit.name + '.timer')}",
            f"rm {files}",
            "systemctl --user daemon-reload",
        ]
    if unit.platform == "macos":
        agents = "~/Library/LaunchAgents"
        plist = f"{agents}/{unit.name}.plist"
        wrapper = _home_relative(unit.wrapper_path) if unit.wrapper_path else f"{agents}/{unit.name}.sh"
        return [
            f"launchctl bootout gui/$(id -u) {shlex.quote(unit.name)}",
            f"rm {_shell_path(plist)} {_shell_path(wrapper)}",
        ]
    if unit.platform == "windows":
        steps = [f'schtasks /Delete /TN "{unit.name}" /F']
        if unit.wrapper_path is not None:
            wrapper = Path(unit.wrapper_path)
            task_xml = wrapper.parent / f"{unit.name}-task.xml"
            files = ", ".join(f'"{_home_relative(p, sep=chr(92))}"' for p in (wrapper, task_xml))
            steps.append(f"Remove-Item {files}")
        else:
            steps.append(f"Delete the {unit.name} wrapper script and {unit.name}-task.xml beside it.")
        return steps
    return [f"Remove the {unit.name} schedule with your operating system's scheduler tools."]
