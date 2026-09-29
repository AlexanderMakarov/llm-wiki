"""Repo hygiene: committed files must not name people who are not us.

Two forbidden strings, one shape of check:

* the upstream maintainer username, which must not reach committed ``.md`` /
  ``.py`` — fixtures and redacted transcripts use ``USER`` as the placeholder.
  The old ``ci.yml`` "Privacy grep" shell step enforced this; the check now
  runs as part of ``pytest tests/`` so local and CI share one definition.
* the fork parent's GitHub owner (#211). This is a fork, and clone URLs,
  registry images, OCI provenance and package metadata were all inherited
  pointing at the upstream account. ``link-check.yml`` never caught it:
  lychee tests *liveness*, and an upstream reference resolves fine.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.tracked_files import tracked_files

# Assembled so the contiguous forbidden string never appears in this file
# (which would defeat the guard if a greppable literal were committed).
_FORBIDDEN_USERNAME = "".join(("deep", "shikha", "singh"))

#: The fork parent's GitHub owner, matched case-insensitively (it appears both
#: TitleCased in URLs and lowercased in registry paths).
_UPSTREAM_OWNER = "".join(("prati", "yush"))

#: Files that legitimately still name upstream: MIT attribution, the README
#: acknowledgement, frozen release history, and specs recording the fork's
#: origin.
UPSTREAM_OWNER_ALLOWLIST: tuple[str, ...] = (
    "LICENSE",
    "README.md",
    "CHANGELOG.md",
    "RELEASE-NOTES",
    "context/",
)


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


def test_tracked_files_do_not_hardcode_the_upstream_owner(
    request: pytest.FixtureRequest,
) -> None:
    """No tracked file outside the allowlist names the fork parent (#211).

    Scans every tracked file, not just ``.md``/``.py``: the inherited
    references lived in ``Dockerfile``, compose and workflow YAML too. The
    owner substring also catches the upstream maintainer's email address,
    which begins with it.
    """
    root = Path(request.config.rootpath)
    paths = tracked_files(root)
    if not paths:
        pytest.skip("git unavailable or not a repository")

    hits: list[str] = []
    for path in paths:
        rel = path.relative_to(root).as_posix()
        if rel.startswith(UPSTREAM_OWNER_ALLOWLIST):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if _UPSTREAM_OWNER in text.lower():
            hits.append(rel)

    assert not hits, (
        "the fork parent's owner is still hardcoded in: " + ", ".join(sorted(hits))
    )
