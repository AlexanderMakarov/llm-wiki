"""Helpers for acceptance tests that assert release-note content in CHANGELOG.md."""

from __future__ import annotations

import re


def shipping_section_text(changelog_text: str) -> str:
    """Return [Unreleased] body, or the newest versioned section when Unreleased is empty.

    After a release cut, feature bullets move from ``## [Unreleased]`` into
    ``## [X.Y.Z]``; acceptance tests should keep reading the shipping notes
    without hard-coding a version number on every release.
    """
    m = re.search(r"^## \[Unreleased\]\s*\n(.*?)(?=^## \[)", changelog_text, re.M | re.S)
    if not m:
        raise AssertionError("no [Unreleased] section in CHANGELOG.md")
    unreleased = m.group(1)
    if re.search(r"^- ", unreleased, re.M):
        return unreleased
    m2 = re.search(
        r"^(## \[\d+\.\d+\.\d+\][^\n]*\n.*?)(?=^## \[)",
        changelog_text,
        re.M | re.S,
    )
    if not m2:
        raise AssertionError("no versioned changelog section after [Unreleased]")
    return m2.group(1)
