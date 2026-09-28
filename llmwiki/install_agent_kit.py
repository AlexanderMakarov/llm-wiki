"""Copy packaged slash commands and skills into an agent directory (#109).

The kit lives at ``llmwiki/agent_kit/{commands,skills}/`` and ships inside
the installable package. ``llmwiki install-agent-kit --dest PATH`` copies
those two folders beneath ``PATH`` (so ``--dest .claude`` lands files where
Claude Code looks) and reports every path it writes.

A destination file is classified three ways. One that differs is weighed
against the digest ``dest/.llmwiki-agent-kit.json`` records for that path,
which is the only evidence of what llmwiki itself put there:

* **unchanged** — the content already matches the kit, so the file is left
  alone.
* **outdated** — the content is the revision the manifest records, so the
  file is our own stale copy. It is reported as outdated, naming the version
  that wrote it when the manifest records one, and overwritten with no
  ``.bak``. These are bytes we wrote ourselves, so keeping a copy of them is
  noise, and a needless ``.bak`` can overwrite a real one (#224) — the same
  rule the prune path follows.
* **customised** — the content matches nothing the manifest records, so the
  user edited it (or it predates the manifest). Their edits cannot be merged
  into the kit update, so the file is copied to ``<name>.bak`` beside it
  before the kit version is written, and the backup is reported only once it
  is on disk.

Because a manifest decides which files are replaced without a backup, treat
one you did not generate the way you treat the files beside it.

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


def _manifest_digests(manifest: dict[str, Any] | None) -> dict[str, str]:
    """Return the manifest's ``path -> sha256`` record.

    A manifest whose ``paths`` is not a mapping carries no digest for any
    path, so it contributes nothing and nothing it names is prunable.
    """
    entries = (manifest or {}).get("paths")
    if not isinstance(entries, dict):
        return {}
    return {
        rel: value
        for rel, value in entries.items()
        if isinstance(rel, str) and isinstance(value, str)
    }


def _manifest_version(manifest: dict[str, Any] | None) -> str | None:
    """Return the llmwiki version the manifest records, or ``None``."""
    version = (manifest or {}).get("version")
    return version if isinstance(version, str) and version.strip() else None


def known_digests(
    *, manifest: dict[str, Any] | None, shipped: set[str]
) -> dict[str, frozenset[str]]:
    """Return ``path -> digests llmwiki wrote there`` for paths it no longer ships.

    A retired digest only describes a path the kit has stopped shipping, so
    the package list and the manifest are merged for the prune decision and
    nowhere else.
    """
    authored: dict[str, set[str]] = {}
    for rel, digests in RETIRED_PATHS.items():
        authored.setdefault(rel, set()).update(digests)
    for rel, recorded in _manifest_digests(manifest).items():
        authored.setdefault(rel, set()).add(recorded)
    return {
        rel: frozenset(digests)
        for rel, digests in authored.items()
        if rel not in shipped
    }


def stale_paths(
    *, dest: Path, shipped: set[str], manifest: dict[str, Any] | None
) -> tuple[list[str], list[str]]:
    """Return ``(prunable, kept)`` dest-relative paths.

    ``prunable`` still holds content llmwiki wrote there. ``kept`` exists on
    disk under a path the kit dropped but no longer matches any digest we
    shipped, so it is somebody else's file and stays.
    """
    prunable: list[str] = []
    kept: list[str] = []
    for rel, digests in sorted(
        known_digests(manifest=manifest, shipped=shipped).items()
    ):
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
        return f"{path}: {exc}"
    return None


# ─── Install ──────────────────────────────────────────────────────────


def _kept_reason(rel: str, display: str) -> str:
    """Return the ``kept`` line for ``rel``, rendered at ``display``."""
    if rel in RETIRED_PATHS:
        return f"{display}: retired, but modified — left in place"
    return f"{display}: no longer shipped, but modified — left in place"


def run_install(*, dest: Path, dry_run: bool = False) -> dict[str, Any]:
    """Copy the packaged kit beneath ``dest`` and prune what it retired.

    Returns a report dict. Every differing file it overwrites is listed
    under ``written`` and again under ``outdated`` (bytes llmwiki wrote
    there, replaced without a backup) or ``customised`` (bytes it did not,
    backed up first). ``changed`` is ``False`` when every destination file
    already matches the kit and there is nothing to prune (or the kit is
    empty).
    """
    dest = Path(dest).expanduser()
    manifest = read_manifest(dest)
    manifest_digests = _manifest_digests(manifest)
    installed_version = _manifest_version(manifest)
    report: dict[str, Any] = {
        "dest": str(dest),
        "kit": str(KIT_ROOT),
        "dry_run": dry_run,
        "written": [],
        "unchanged": [],
        "outdated": [],
        "customised": [],
        "backed_up": [],
        "pruned": [],
        "kept": [],
        "errors": [],
        "changed": False,
        "installed_version": installed_version,
        "package_version": __version__,
        "attributed_versions": {},
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
            report["errors"].append(f"{target}: {exc}")
            continue
        if target.is_file():
            try:
                existing = target.read_bytes()
            except OSError as exc:
                report["errors"].append(f"{target}: {exc}")
                continue
            if existing == new_bytes:
                report["unchanged"].append(rel)
                landed[rel] = digest(new_bytes)
                continue
            recorded = manifest_digests.get(rel)
            if recorded is not None and recorded == digest(existing):
                report["outdated"].append(rel)
            else:
                bak = _bak_path(target)
                if not dry_run:
                    try:
                        bak.write_bytes(existing)
                    except OSError as exc:
                        report["errors"].append(f"{bak}: {exc}")
                        continue
                report["customised"].append(rel)
                report["backed_up"].append(f"{rel}.bak")
            if installed_version and recorded is not None:
                report["attributed_versions"][rel] = installed_version
        if not dry_run:
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(new_bytes)
            except OSError as exc:
                report["errors"].append(f"{target}: {exc}")
                continue
        report["written"].append(rel)
        landed[rel] = digest(new_bytes)

    shipped = {rel for rel, _src in files}
    prunable, kept = stale_paths(dest=dest, shipped=shipped, manifest=manifest)
    for rel in prunable:
        target = dest / rel
        if not dry_run:
            try:
                target.unlink()
            except OSError as exc:
                report["errors"].append(f"{target}: {exc}")
                continue
        report["pruned"].append(rel)
    report["kept"].extend(kept)

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
    root = Path(report["dest"]).expanduser().absolute()
    saved = "will be saved to" if report["dry_run"] else "was saved to"

    def at(rel: str) -> str:
        return str(root / rel)

    def count(label: str, value: int) -> None:
        print(f"{prefix}{label + ':':<12}{value}")

    def detail(label: str, text: str) -> None:
        print(f"{prefix}  {label:<10} {text}")

    def version_note(rel: str, wording: str) -> str:
        version = report["attributed_versions"].get(rel)
        return f" ({wording} {version})" if version else ""

    print(f"{prefix}{'dest:':<12}{root}")
    count("written", len(report["written"]))
    count("unchanged", len(report["unchanged"]))
    count("outdated", len(report["outdated"]))
    count("customised", len(report["customised"]))
    count("backed_up", len(report["backed_up"]))
    count("pruned", len(report["pruned"]))
    if report["kept"]:
        count("kept", len(report["kept"]))
    for rel in report["written"]:
        detail("wrote", at(rel))
    for rel in report["outdated"]:
        detail(
            "outdated",
            f"{at(rel)}{version_note(rel, 'installed by')} — llmwiki's own stale "
            f"copy, replaced with the current kit; no backup kept",
        )
    for rel in report["customised"]:
        detail(
            "customised",
            f"{at(rel)}{version_note(rel, 'patched from')} — your edits cannot be "
            f"merged into the kit update, so your previous content {saved} "
            f"{at(rel)}.bak",
        )
    for rel in report["pruned"]:
        detail("pruned", at(rel))
    for rel in report["kept"]:
        detail("kept", _kept_reason(rel, at(rel)))
    for rel in report["unchanged"]:
        detail("unchanged", at(rel))
    if report["errors"]:
        count("errors", len(report["errors"]))
        for err in report["errors"][:10]:
            print(f"{prefix}  ! {err}")
    if not report["changed"] and not report["errors"]:
        print(f"{prefix}nothing to write: every file already matches the kit")
