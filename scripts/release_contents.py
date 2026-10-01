#!/usr/bin/env python3
"""Print CHANGELOG Unreleased entries for the release version proposal.

Breaking first, then Added / Changed / Fixed / Removed; maintainer-only notes
folded to one line; semver hint from the last released heading.

    python3 scripts/release_contents.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CHANGELOG = REPO_ROOT / "CHANGELOG.md"
SECTIONS = ("Added", "Changed", "Fixed", "Removed")

_ENTRY = re.compile(r"^- (?P<breaking>\*\*Breaking:\*\* )?\*\*(?P<title>.+?)\*\*")
_NOTE = re.compile(r"^\s+- \*Release note:\*\s*(?P<note>.+)$")
_VERSION = re.compile(r"^## \[(\d+)\.(\d+)\.(\d+)\]", re.MULTILINE)


def parse_unreleased(text: str) -> list[dict[str, object]]:
    """Entries under ``## [Unreleased]`` as ``{title, section, breaking, note}``."""
    start = text.find("## [Unreleased]")
    if start < 0:
        return []
    end = text.find("\n## [", start + 1)
    body = text[start:end if end > 0 else len(text)]
    entries: list[dict[str, object]] = []
    section = ""
    for line in body.splitlines():
        if line.startswith("### "):
            section = line[4:].strip()
            continue
        m = _ENTRY.match(line)
        if m and section:
            entries.append({
                "title": m["title"],
                "section": section,
                "breaking": bool(m["breaking"]),
                "note": "",
            })
            continue
        n = _NOTE.match(line)
        if n and entries:
            entries[-1]["note"] = n["note"].strip()
    return entries


def last_version(text: str) -> tuple[int, int, int] | None:
    m = _VERSION.search(text)
    return (int(m[1]), int(m[2]), int(m[3])) if m else None


def _maintainer_only(entry: dict[str, object]) -> bool:
    return str(entry["note"]).lower().startswith("maintainers only")


def render(entries: list[dict[str, object]], last: tuple[int, int, int] | None) -> str:
    lines: list[str] = []

    def group(title: str, items: list[dict[str, object]]) -> None:
        if not items:
            return
        lines.append(f"**{title}** ({len(items)})")
        for e in items:
            note = str(e["note"])
            lines.append(f"- {e['title']}" + (f" — {note}" if note else ""))
        lines.append("")

    public = [e for e in entries if not _maintainer_only(e)]
    group("Breaking", [e for e in public if e["breaking"]])
    for section in SECTIONS:
        group(section, [e for e in public if e["section"] == section and not e["breaking"]])
    internal = [e for e in entries if _maintainer_only(e)]
    if internal:
        titles = "; ".join(str(e["title"]) for e in internal)
        lines.append(f"**Maintainer-only** ({len(internal)}): {titles}")
        lines.append("")

    if last is not None:
        major, minor, patch = last
        breaking = sum(1 for e in entries if e["breaking"])
        if breaking:
            hint = (
                f"{breaking} Breaking entr{'y' if breaking == 1 else 'ies'} → "
                f"semver major {major + 1}.0.0; a minor would be {major}.{minor + 1}.0."
            )
        else:
            hint = f"No Breaking entries → minor {major}.{minor + 1}.0 (or patch if only fixes)."
        lines.append(f"**Version:** last release {major}.{minor}.{patch}. {hint}")
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
