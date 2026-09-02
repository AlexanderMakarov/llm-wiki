"""Repo hygiene: committed ``.md`` / ``.py`` must not contain the upstream maintainer username.

Fixtures and redacted transcripts use ``USER`` as the placeholder. The old
``ci.yml`` "Privacy grep" shell step enforced this; the check now runs as part
of ``pytest tests/`` so local and CI share one definition.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.tracked_files import tracked_files

# Assembled so the contiguous forbidden string never appears in this file
# (which would defeat the guard if a greppable literal were committed).
_FORBIDDEN_USERNAME = "".join(("deep", "shikha", "singh"))


def test_tracked_md_and_py_do_not_contain_real_username(
    request: pytest.FixtureRequest,
) -> None:
    """Privacy grep: no tracked ``.md``/``.py`` may contain the real username."""
    root = Path(request.config.rootpath)
    paths = tracked_files(root)
    if not paths:
        pytest.skip("git unavailable or not a repository")

    hits: list[str] = []
    for path in paths:
        if path.suffix not in {".md", ".py"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if _FORBIDDEN_USERNAME in text:
            hits.append(path.relative_to(root).as_posix())

    assert not hits, (
        "real username leaked into committed files "
        f"(fixtures must use USER): {hits}"
    )
