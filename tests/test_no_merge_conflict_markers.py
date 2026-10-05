"""Repo hygiene: committed files must not contain unresolved git merge markers.

``pr-lint`` only checks that ``CHANGELOG.md`` was *touched* for feat/fix PRs.
``scripts/release_contents.parse_unreleased`` skips non-entry lines, so
``<<<<<<<``, ``=======``, and ``>>>>>>>`` in Unreleased never failed CI.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.tracked_files import tracked_files

# Exact git conflict-marker lines (seven < / = / >). Longer ``====…`` rules in
# vendor notices must not match the middle marker.
_CONFLICT_MARKER = re.compile(r"^(<<<<<<< .*|=======|>>>>>>> .*)$")

_TEXT_SUFFIXES = {
    ".md",
    ".py",
    ".yml",
    ".yaml",
    ".toml",
    ".json",
    ".txt",
    ".sh",
    ".css",
    ".js",
    ".html",
    ".rst",
    ".ini",
    ".cfg",
    ".svg",
}


def line_is_merge_conflict_marker(line: str) -> bool:
    """Return True when ``line`` is a git conflict marker (no trailing newline)."""
    return bool(_CONFLICT_MARKER.match(line.rstrip("\n")))


def conflict_marker_hits(text: str) -> list[int]:
    """1-based line numbers that look like unresolved merge conflict markers."""
    return [
        i
        for i, line in enumerate(text.splitlines(), start=1)
        if line_is_merge_conflict_marker(line)
    ]


def test_conflict_marker_detector_accepts_long_equals_rules():
    assert not conflict_marker_hits("====\n" + ("=" * 68) + "\n")
    assert conflict_marker_hits("<<<<<<< HEAD\n=======\n>>>>>>> origin/main\n") == [
        1,
        2,
        3,
    ]


def test_tracked_text_files_have_no_merge_conflict_markers(
    request: pytest.FixtureRequest,
) -> None:
    """Fail CI when any tracked text file still contains conflict markers."""
    root = Path(request.config.rootpath)
    paths = tracked_files(root)
    if not paths:
        pytest.skip("git unavailable or not a repository")

    hits: list[str] = []
    for path in paths:
        if path.suffix not in _TEXT_SUFFIXES and path.name not in {
            "Dockerfile",
            "Makefile",
            "LICENSE",
        }:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        lines = conflict_marker_hits(text)
        if lines:
            rel = path.relative_to(root).as_posix()
            shown = ", ".join(str(n) for n in lines[:8])
            more = "" if len(lines) <= 8 else f" (+{len(lines) - 8} more)"
            hits.append(f"{rel}:{shown}{more}")

    assert not hits, (
        "unresolved git merge conflict markers in tracked files: "
        + "; ".join(hits)
    )
