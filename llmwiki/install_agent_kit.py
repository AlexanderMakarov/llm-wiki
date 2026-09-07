"""Copy packaged slash commands and skills into an agent directory (#109).

The kit lives at ``llmwiki/agent_kit/{commands,skills}/`` and ships inside
the installable package. ``llmwiki install-agent-kit --dest PATH`` copies
those two folders beneath ``PATH`` (so ``--dest .claude`` lands files where
Claude Code looks) and reports every path it writes.

A destination file whose content already matches the kit is left alone. A
destination file that differs is copied to ``<name>.bak`` beside it before
the kit version is written, so a customisation is never overwritten silently.
``--dry-run`` prints the same report and writes nothing.

The install also prunes (#214), and pruning is gated on content, not on the
name. A file is deleted only when it still hashes to something llmwiki is
known to have written at that path. Two sources supply those digests:

* ``llmwiki.agent_kit.RETIRED_PATHS`` — retired commands and skills mapped
  to the digests of every revision the package shipped for them, which
  reaches destinations populated before any tracking existed.
* ``dest/.llmwiki-agent-kit.json`` — a manifest of the llmwiki version and
  a ``path -> sha256`` record of what this tool installed, written after a
  pass. A later install prunes any manifest path the kit no longer ships,
  so future removals need no list.

A file this tool never installed is therefore never touched, whatever it is
named: an unrecognised digest means the file stays and is reported under
``kept``, which is also what happens to a retired command the user edited.
Because only bytes we ourselves wrote are ever removed, a prune makes no
backup. Every manifest entry is validated first — an absolute path, a ``..``
segment, a path outside ``commands/``/``skills/``, or one that resolves
outside ``dest`` is ignored, as is a manifest that is missing, unreadable,
or written in a shape that carries no digests. Only files are removed,
never directories.

Usage::

    llmwiki install-agent-kit --dest .claude --dry-run
    llmwiki install-agent-kit --dest .claude
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from llmwiki import __version__
from llmwiki.agent_kit import COMMANDS_DIR, KIT_ROOT, RETIRED_PATHS, SKILLS_DIR

MANIFEST_NAME = ".llmwiki-agent-kit.json"

_SKIP_NAMES = {"__pycache__"}
_SKIP_SUFFIXES = {".pyc", ".pyo"}
_KIT_FOLDERS = ("commands/", "skills/")


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


def digest(payload: bytes) -> str:
    """Return the sha256 hex digest of ``payload``."""
    return hashlib.sha256(payload).hexdigest()


def _file_digest(path: Path) -> str | None:
    try:
        return digest(path.read_bytes())
    except OSError:
        return None


# ─── Manifest ─────────────────────────────────────────────────────────


def manifest_path(dest: Path) -> Path:
    """Return the install manifest path for ``dest``."""
    return dest / MANIFEST_NAME


def _safe_target(rel: str, *, dest: Path) -> Path | None:
    """Return the file ``rel`` names under ``dest``, or ``None`` if unsafe.

    A path is eligible only when it is relative, free of ``..``, under
    ``commands/`` or ``skills/``, and resolves inside ``dest``.
    """
    if not isinstance(rel, str) or not rel.strip():
        return None
    if not rel.startswith(_KIT_FOLDERS):
        return None
    if rel.startswith(("/", "\\")) or PureWindowsPath(rel).is_absolute():
        return None
    pure = PurePosixPath(rel)
    if pure.is_absolute() or ".." in pure.parts:
        return None
    target = dest / pure
    try:
        resolved = target.resolve()
        root = dest.resolve()
    except (OSError, ValueError):
        return None
    if resolved == root or not resolved.is_relative_to(root):
        return None
    return target


def read_manifest(dest: Path) -> dict[str, Any] | None:
    """Return the parsed manifest under ``dest``, or ``None`` when unusable."""
    try:
        raw = manifest_path(dest).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    try:
        data = json.loads(raw)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _manifest_digests(dest: Path) -> dict[str, str]:
    """Return the manifest's ``path -> sha256`` record.

    A manifest whose ``paths`` is not a mapping carries no digest for any
    path, so it contributes nothing and nothing it names is prunable.
    """
    data = read_manifest(dest) or {}
    entries = data.get("paths")
    if not isinstance(entries, dict):
        return {}
    return {
        rel: value
        for rel, value in entries.items()
        if isinstance(rel, str) and isinstance(value, str)
    }


def known_digests(*, dest: Path, shipped: set[str]) -> dict[str, frozenset[str]]:
    """Return ``path -> digests llmwiki wrote there`` for paths it no longer ships."""
    known: dict[str, set[str]] = {}
    for rel, digests in RETIRED_PATHS.items():
        known.setdefault(rel, set()).update(digests)
    for rel, recorded in _manifest_digests(dest).items():
        known.setdefault(rel, set()).add(recorded)
    return {
        rel: frozenset(digests)
        for rel, digests in known.items()
        if rel not in shipped
    }


def stale_paths(*, dest: Path, shipped: set[str]) -> tuple[list[str], list[str]]:
    """Return ``(prunable, kept)`` dest-relative paths.

    ``prunable`` still holds content llmwiki wrote there. ``kept`` exists on
    disk under a path the kit dropped but no longer matches any digest we
    shipped, so it is somebody else's file and stays.
    """
    prunable: list[str] = []
    kept: list[str] = []
    for rel, digests in sorted(known_digests(dest=dest, shipped=shipped).items()):
        target = _safe_target(rel, dest=dest)
        if target is None or not target.is_file():
            continue
        if _file_digest(target) in digests:
            prunable.append(rel)
        else:
            kept.append(rel)
    return prunable, kept


def _write_manifest(dest: Path, *, installed: dict[str, str]) -> str | None:
    """Record version and installed ``path -> sha256``. Return an error, or ``None``."""
    payload = json.dumps(
        {"version": __version__, "paths": dict(sorted(installed.items()))},
        indent=2,
        ensure_ascii=False,
    ) + "\n"
    path = manifest_path(dest)
    try:
        if path.is_file() and path.read_text(encoding="utf-8") == payload:
            return None
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload, encoding="utf-8")
    except OSError as exc:
        return f"{MANIFEST_NAME}: {exc}"
    return None


# ─── Install ──────────────────────────────────────────────────────────


def _kept_reason(rel: str) -> str:
    if rel in RETIRED_PATHS:
        return f"{rel}: retired, but modified — left in place"
    return f"{rel}: no longer shipped, but modified — left in place"


def run_install(*, dest: Path, dry_run: bool = False) -> dict[str, Any]:
    """Copy the packaged kit beneath ``dest`` and prune what it retired.

    Returns a report dict. ``changed`` is ``False`` when every destination
    file already matches the kit and there is nothing to prune (or the kit
    is empty).
    """
    dest = Path(dest).expanduser()
    report: dict[str, Any] = {
        "dest": str(dest),
        "kit": str(KIT_ROOT),
        "dry_run": dry_run,
        "written": [],
        "unchanged": [],
        "backed_up": [],
        "pruned": [],
        "kept": [],
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

    landed: dict[str, str] = {}
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
                landed[rel] = digest(new_bytes)
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
        landed[rel] = digest(new_bytes)

    shipped = {rel for rel, _src in files}
    prunable, kept = stale_paths(dest=dest, shipped=shipped)
    for rel in prunable:
        target = dest / rel
        if not dry_run:
            try:
                target.unlink()
            except OSError as exc:
                report["errors"].append(f"{rel}: {exc}")
                continue
        report["pruned"].append(rel)
    report["kept"].extend(_kept_reason(rel) for rel in kept)

    if not dry_run:
        error = _write_manifest(dest, installed=landed)
        if error:
            report["errors"].append(error)

    report["changed"] = bool(
        report["written"] or report["backed_up"] or report["pruned"]
    )
    return report


def print_report(report: dict[str, Any]) -> None:
    """Print every path written, pruned, backed up, or kept, and a count of no-ops."""
    prefix = "[dry-run] " if report["dry_run"] else ""
    print(f"{prefix}dest:      {report['dest']}")
    print(f"{prefix}written:   {len(report['written'])}")
    print(f"{prefix}unchanged: {len(report['unchanged'])}")
    print(f"{prefix}backed_up: {len(report['backed_up'])}")
    print(f"{prefix}pruned:    {len(report['pruned'])}")
    if report["kept"]:
        print(f"{prefix}kept:      {len(report['kept'])}")
    for rel in report["written"]:
        print(f"{prefix}  wrote     {rel}")
    for rel in report["pruned"]:
        print(f"{prefix}  pruned    {rel}")
    for rel in report["backed_up"]:
        print(f"{prefix}  backup    {rel}")
    for note in report["kept"]:
        print(f"{prefix}  kept      {note}")
    for rel in report["unchanged"]:
        print(f"{prefix}  unchanged {rel}")
    if report["errors"]:
        print(f"{prefix}errors:    {len(report['errors'])}")
        for err in report["errors"][:10]:
            print(f"{prefix}  ! {err}")
    if not report["changed"] and not report["errors"]:
        print(f"{prefix}nothing to write: every file already matches the kit")
