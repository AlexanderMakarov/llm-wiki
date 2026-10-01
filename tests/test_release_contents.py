"""``scripts/release_contents.py`` — what the next release ships (#302)."""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "release_contents.py"
_RELEASE_SUBJECT = re.compile(r"^release\(v\d+\.\d+\.\d+\):")


def _head_is_release_commit(repo: Path = REPO) -> bool:
    """True when HEAD is a ``release(vX.Y.Z): …`` cut commit.

    Only those commits empty ``## [Unreleased]`` by design; every other commit
    must still keep parseable Unreleased entries so format drift is caught
    before the next cut.
    """
    try:
        subject = subprocess.check_output(
            ["git", "log", "-1", "--format=%s"],
            cwd=repo,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return False
    return bool(_RELEASE_SUBJECT.match(subject))

CHANGELOG = """# Changelog

## [Unreleased]

### Added

- **Shell completion (#1)** — details.
  - *Release note:* TAB completes commands (#1).
- **Gate script (#2)** — details.
  - *Release note:* Maintainers only: a gate (#2).

### Changed

- **Breaking:** **Add stops synthesizing (#3)** — details.
  - *Release note:* Pass --synthesize (#3).
- **Faster search (#4)** — details.

### Fixed

### Removed

- **Old kit (#5)** — details.

## [2.3.0] — 2026-09-08

### Added

- **Released thing (#9)** — details.
"""


@pytest.fixture(scope="module")
def contents():
    spec = importlib.util.spec_from_file_location("release_contents", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_parses_only_unreleased_entries_with_their_notes(contents):
    entries = contents.parse_unreleased(CHANGELOG)
    assert [(e["title"], e["section"], e["breaking"]) for e in entries] == [
        ("Shell completion (#1)", "Added", False),
        ("Gate script (#2)", "Added", False),
        ("Add stops synthesizing (#3)", "Changed", True),
        ("Faster search (#4)", "Changed", False),
        ("Old kit (#5)", "Removed", False),
    ]
    assert entries[0]["note"] == "TAB completes commands (#1)."
    assert contents._maintainer_only(entries[1])


def test_render_leads_with_breaking_and_folds_maintainer_entries(contents):
    text = contents.render(contents.parse_unreleased(CHANGELOG), contents.last_version(CHANGELOG))
    order = [text.index(h) for h in ("**Breaking**", "**Added**", "**Changed**", "**Removed**")]
    assert order == sorted(order)
    assert "- Add stops synthesizing (#3) — Pass --synthesize (#3)." in text
    assert "**Maintainer-only** (1): Gate script (#2)" in text
    assert "- Gate script (#2)" not in text
    assert "**Fixed**" not in text
    assert "last release 2.3.0" in text
    assert "semver major 3.0.0; a minor would be 2.4.0" in text


def test_head_is_release_commit_matches_release_subject_only():
    assert _RELEASE_SUBJECT.match("release(v2.4.0): bump version + CHANGELOG")
    assert not _RELEASE_SUBJECT.match("fix: allow empty Unreleased after a tagged cut")
    assert not _RELEASE_SUBJECT.match("chore: retrigger Actions after post-tag CI fix")


def test_real_changelog_parses(contents):
    """The script must keep up with the live CHANGELOG's entry format.

    Empty Unreleased is allowed **only** on a ``release(vX.Y.Z):`` commit (the
    cut that promotes Unreleased into a versioned section). On every other
    commit Unreleased must still yield entries. Release commits with an empty
    Unreleased still require the newest versioned section to parse.
    """
    text = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    entries = contents.parse_unreleased(text)
    assert all(e["section"] in contents.SECTIONS for e in entries)
    if entries:
        return
    assert _head_is_release_commit(), (
        "Unreleased section yielded no entries — allowed only on a "
        "release(vX.Y.Z): commit; add CHANGELOG Unreleased bullets for "
        "this change or cut a release"
    )
    last = contents.last_version(text)
    assert last is not None, "CHANGELOG has no versioned section"
    major, minor, patch = last
    heading = f"## [{major}.{minor}.{patch}]"
    start = text.find(heading)
    assert start >= 0, f"missing {heading}"
    end = text.find("\n## [", start + 1)
    body = text[start : end if end > 0 else len(text)]
    assert any(contents._ENTRY.match(line) for line in body.splitlines()), (
        f"{heading} has no parseable release entries"
    )
