"""Copy packaged slash commands and skills into an agent directory (#109).

The kit lives at ``llmwiki/agent_kit/{commands,skills}/`` and ships inside
the installable package. ``llmwiki install-agent-kit --dest PATH`` copies
those two folders beneath ``PATH`` (so ``--dest .claude`` lands files where
Claude Code looks) and reports every path it writes.

A destination file whose content already matches the kit is left alone. A
destination file that differs is copied to ``<name>.bak`` beside it before
the kit version is written, so a customisation is never overwritten silently.
``--dry-run`` prints the same report and writes nothing.

Usage::

    llmwiki install-agent-kit --dest .claude --dry-run
    llmwiki install-agent-kit --dest .claude
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from llmwiki.agent_kit import COMMANDS_DIR, KIT_ROOT, SKILLS_DIR

_SKIP_NAMES = {"__pycache__"}
_SKIP_SUFFIXES = {".pyc", ".pyo"}


def kit_files() -> list[tuple[str, Path]]:
    """Return ``(dest-relative posix path, source path)`` for every kit file."""
    pairs: list[tuple[str, Path]] = []
    for folder, src_root in (("commands", COMMANDS_DIR), ("skills", SKILLS_DIR)):
        if not src_root.is_dir():
            continue
        for path in sorted(src_root.rglob("*")):
            if not path.is_file():
                continue
            if path.name in _SKIP_NAMES or path.suffix in _SKIP_SUFFIXES:
                continue
            rel = f"{folder}/{path.relative_to(src_root).as_posix()}"
            pairs.append((rel, path))
    return pairs


def _bak_path(dest_file: Path) -> Path:
    return dest_file.parent / f"{dest_file.name}.bak"


def run_install(*, dest: Path, dry_run: bool = False) -> dict[str, Any]:
    """Copy the packaged kit beneath ``dest``.

    Returns a report dict. ``changed`` is ``False`` when every destination
    file already matches the kit (or the kit is empty).
    """
    dest = Path(dest).expanduser()
    report: dict[str, Any] = {
        "dest": str(dest),
        "kit": str(KIT_ROOT),
        "dry_run": dry_run,
        "written": [],
        "unchanged": [],
        "backed_up": [],
        "errors": [],
        "changed": False,
    }
    files = kit_files()
    if not files:
        report["errors"].append(
            f"agent kit missing or empty: {KIT_ROOT} — reinstall the llm-wiki package"
        )
        return report
    if dest.exists() and not dest.is_dir():
        report["errors"].append(f"--dest is not a directory: {dest}")
        return report

    for rel, src in files:
        target = dest / rel
        try:
            new_bytes = src.read_bytes()
        except OSError as exc:
            report["errors"].append(f"{rel}: {exc}")
            continue
        if target.is_file():
            try:
                existing = target.read_bytes()
            except OSError as exc:
                report["errors"].append(f"{rel}: {exc}")
                continue
            if existing == new_bytes:
                report["unchanged"].append(rel)
                continue
            bak = _bak_path(target)
            report["backed_up"].append(f"{rel}.bak")
            if not dry_run:
                try:
                    bak.write_bytes(existing)
                except OSError as exc:
                    report["errors"].append(f"{rel}.bak: {exc}")
                    continue
        if not dry_run:
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(new_bytes)
            except OSError as exc:
                report["errors"].append(f"{rel}: {exc}")
                continue
        report["written"].append(rel)

    report["changed"] = bool(report["written"] or report["backed_up"])
    return report


def print_report(report: dict[str, Any]) -> None:
    """Print every path written, every ``.bak``, and a count of no-ops."""
    prefix = "[dry-run] " if report["dry_run"] else ""
    print(f"{prefix}dest:      {report['dest']}")
    print(f"{prefix}written:   {len(report['written'])}")
    print(f"{prefix}unchanged: {len(report['unchanged'])}")
    print(f"{prefix}backed_up: {len(report['backed_up'])}")
    for rel in report["written"]:
        print(f"{prefix}  wrote     {rel}")
    for rel in report["backed_up"]:
        print(f"{prefix}  backup    {rel}")
    for rel in report["unchanged"]:
        print(f"{prefix}  unchanged {rel}")
    if report["errors"]:
        print(f"{prefix}errors:    {len(report['errors'])}")
        for err in report["errors"][:10]:
            print(f"{prefix}  ! {err}")
    if not report["changed"] and not report["errors"]:
        print(f"{prefix}nothing to write: every file already matches the kit")
