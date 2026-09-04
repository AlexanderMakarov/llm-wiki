"""Helpers for acceptance tests that assert release-note content in CHANGELOG.md."""

from __future__ import annotations

import re


def shipping_section_text(changelog_text: str) -> str:
    """Return notes acceptance tests should search for shipping claims.

    After a release cut, feature bullets move from ``## [Unreleased]`` into
    ``## [X.Y.Z]``. Return Unreleased (when it has bullets) plus every
    versioned section so older acceptance tests still find their shipped
    bullets without hard-coding a version number on every release.
    """
    m = re.search(r"^## \[Unreleased\]\s*\n(.*?)(?=^## \[)", changelog_text, re.M | re.S)
    if not m:
        raise AssertionError("no [Unreleased] section in CHANGELOG.md")
    unreleased = m.group(1)
    versions = re.findall(
        r"(^## \[\d+\.\d+\.\d+\][^\n]*\n.*?)(?=^## \[|\Z)",
        changelog_text,
        re.M | re.S,
    )
    parts: list[str] = []
    if re.search(r"^- ", unreleased, re.M):
        parts.append(unreleased.rstrip())
    parts.extend(v.rstrip() for v in versions)
    if not parts:
        raise AssertionError("no versioned changelog section after [Unreleased]")
    return "\n\n".join(parts)
