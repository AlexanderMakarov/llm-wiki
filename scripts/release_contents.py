#!/usr/bin/env python3
"""Print what the next release ships, from CHANGELOG.md's Unreleased section.

The release cut asks the maintainer to pick a version; they pick it from what
ships. This prints the Unreleased entries as that list — breaking changes
first, then Added / Changed / Fixed / Removed, with maintainer-only entries
folded into one line — and what semver implies for the version.

Run from the repository root:

    python3 scripts/release_contents.py

Reads CHANGELOG.md only; writes nothing.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CHANGELOG = REPO_ROOT / "CHANGELOG.md"
SECTIONS = ("Added", "Changed", "Fixed", "Removed")

_ENTRY = re.compile(r"^- (?P<breaking>\*\*Breaking:\*\* )?\*\*(?P<title>.+?)\*\*")
_NOTE = re.compile(r"^\s+- \*Release note:\*\s*(?P<note>.+)$")
_VERSION = re.compile(r"^## \[(\d+)\.(\d+)\.(\d+)\]", re.MULTILINE)


@dataclass
class Entry:
    """One Unreleased bullet: its headline, section and release note."""

    title: str
    section: str
    breaking: bool = False
    note: str = ""

    @property
    def maintainer_only(self) -> bool:
        return self.note.lower().startswith("maintainers only")


def parse_unreleased(text: str) -> list[Entry]:
    """Return the entries under ``## [Unreleased]``, in file order."""
    start = text.find("## [Unreleased]")
    if start < 0:
        return []
    end = text.find("\n## [", start + 1)
    body = text[start:end if end > 0 else len(text)]
    entries: list[Entry] = []
    section = ""
    for line in body.splitlines():
        if line.startswith("### "):
            section = line[4:].strip()
            continue
        m = _ENTRY.match(line)
        if m and section:
            entries.append(Entry(m["title"], section, breaking=bool(m["breaking"])))
            continue
        n = _NOTE.match(line)
        if n and entries:
            entries[-1].note = n["note"].strip()
    return entries


def last_version(text: str) -> tuple[int, int, int] | None:
    """The newest released ``X.Y.Z`` heading, if any."""
    m = _VERSION.search(text)
    return (int(m[1]), int(m[2]), int(m[3])) if m else None


def render(entries: list[Entry], last: tuple[int, int, int] | None) -> str:
    """The release contents as Markdown, breaking changes first."""
    lines: list[str] = []

    def group(title: str, items: list[Entry]) -> None:
        if not items:
            return
        lines.append(f"**{title}** ({len(items)})")
        for e in items:
            lines.append(f"- {e.title}" + (f" — {e.note}" if e.note else ""))
        lines.append("")

    public = [e for e in entries if not e.maintainer_only]
    group("Breaking", [e for e in public if e.breaking])
    for section in SECTIONS:
        group(section, [e for e in public if e.section == section and not e.breaking])
    internal = [e for e in entries if e.maintainer_only]
    if internal:
        lines.append(f"**Maintainer-only** ({len(internal)}): " + "; ".join(e.title for e in internal))
        lines.append("")

    if last is not None:
        major, minor, _patch = last
        breaking = sum(1 for e in entries if e.breaking)
        lines.append(
            f"**Version:** last release {major}.{minor}.{_patch}. "
            + (
                f"{breaking} Breaking entr{'y' if breaking == 1 else 'ies'} → semver major "
                f"{major + 1}.0.0; a minor would be {major}.{minor + 1}.0."
                if breaking
                else f"No Breaking entries → minor {major}.{minor + 1}.0 (or patch if only fixes)."
            )
        )
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    text = CHANGELOG.read_text(encoding="utf-8")
    entries = parse_unreleased(text)
    if not entries:
        print("CHANGELOG.md has no Unreleased entries — nothing to release.", file=sys.stderr)
        return 1
    sys.stdout.write(render(entries, last_version(text)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
