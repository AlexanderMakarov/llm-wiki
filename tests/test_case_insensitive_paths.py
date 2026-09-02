"""Regression test for #160: case-insensitive git path collisions.

Two tracked paths differing only in case (e.g. ``demo/.../LLMWiki.md`` and
``demo/.../llmwiki.md``) coexist fine on case-sensitive Linux but collide on
case-insensitive filesystems (macOS default, Windows) — one file silently
shadows the other on checkout. Runs under the standard ``pytest tests/`` suite
(local and CI).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.tracked_files import tracked_files


def test_no_git_tracked_paths_collide_when_case_folded(
    request: pytest.FixtureRequest,
) -> None:
    """#160 regression: no two ``git ls-files`` paths may fold to the same lowercase form."""
    root = Path(request.config.rootpath)
    paths = tracked_files(root)
    if not paths:
        pytest.skip("git unavailable or not a repository")

    seen: dict[str, str] = {}
    collisions: list[tuple[str, str]] = []
    for path in paths:
        rel = path.relative_to(root).as_posix()
        folded = rel.lower()
        if folded in seen:
            collisions.append((seen[folded], rel))
        else:
            seen[folded] = rel

    assert not collisions, (
        "git-tracked paths collide when case-folded (breaks checkout on "
        f"case-insensitive filesystems): {collisions}"
    )
