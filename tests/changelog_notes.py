"""Helpers for acceptance tests that assert release-note content in CHANGELOG.md."""

from __future__ import annotations

import re


def shipping_section_text(changelog_text: str) -> str:
    """Return notes acceptance tests should search for shipping claims.

    After a release cut, feature bullets move from ``## [Unreleased]`` into
    ``## [X.Y.Z]``. When Unreleased is empty, return the newest versioned
    section. When Unreleased already has new work, concatenate it with that
    newest section so older acceptance tests still find their shipped
    bullets without hard-coding a version number on every release.
    """
    m = re.search(r"^## \[Unreleased\]\s*\n(.*?)(?=^## \[)", changelog_text, re.M | re.S)
    if not m:
        raise AssertionError("no [Unreleased] section in CHANGELOG.md")
    unreleased = m.group(1)
    m2 = re.search(
        r"^(## \[\d+\.\d+\.\d+\][^\n]*\n.*?)(?=^## \[|\Z)",
        changelog_text,
        re.M | re.S,
    )
    latest = m2.group(1) if m2 else ""
    if re.search(r"^- ", unreleased, re.M):
        if latest:
            return unreleased.rstrip() + "\n\n" + latest
        return unreleased
    if not latest:
        raise AssertionError("no versioned changelog section after [Unreleased]")
    return latest
