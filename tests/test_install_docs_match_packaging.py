"""Every live `pip install` of our own package must name the published distribution (#210).

The repo shipped install instructions for three different distribution names at
once — `llm-wiki` in the README, `llm-notebook` in the GitHub Action and the
upgrade guide, `llm-wiki` in `pyproject.toml` — and none of them was installable.
A doc that tells a user to install a name we don't publish is indistinguishable
from a doc that works until they run it, so the check is mechanical: parse the
distribution name out of ``pyproject.toml`` and require every install command
for an ``llm-*`` distribution to use exactly that name.

Scope is deliberately "live guidance" only. History is not rewritten, so the
frozen changelog, the archived release notes, the AWOS delivery records under
``context/``, and the regenerated ``demo/`` vault keep whatever name they were
written with.
"""

from __future__ import annotations

import re
import tomllib

import pytest

from llmwiki import REPO_ROOT

#: Paths whose install commands are historical record, not instructions.
ALLOWLIST_PREFIXES = (
    "demo/",
    "context/",
    "CHANGELOG.md",
    "RELEASE-NOTES",
)

#: A pip install naming a distribution that starts with ``llm-``, with optional
#: extras and optional surrounding quotes: ``pip install -U "llm-wiki-plus[graph]"``.
INSTALL_RE = re.compile(
    r"""pip \s+ install \s+
        (?:(?:-U|--upgrade|--quiet|-q)\s+)*
        (?P<quote>['"]?)
        (?P<dist>llm-[A-Za-z0-9._-]+)
        (?:\[[^\]]*\])?
        (?P=quote)
    """,
    re.VERBOSE,
)


def _distribution_name() -> str:
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return data["project"]["name"]


def _tracked_files() -> list[str]:
    """Committed files whose install commands are user-facing instructions."""
    import subprocess  # noqa: PLC0415 — test-only helper, keeps the module import cheap

    out = subprocess.run(
        ["git", "ls-files", "-z", "*.md", "*.yml", "*.yaml"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    paths = [p for p in out.split("\0") if p]
    return [p for p in paths if not p.startswith(ALLOWLIST_PREFIXES)]


def _install_commands() -> list[tuple[str, int, str]]:
    """Return ``(path, line number, distribution)`` for every live install command."""
    found: list[tuple[str, int, str]] = []
    for rel in _tracked_files():
        path = REPO_ROOT / rel
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            for match in INSTALL_RE.finditer(line):
                found.append((rel, lineno, match.group("dist")))
    return found


def test_pyproject_declares_the_published_distribution():
    # `llmwiki` belongs to another author and PyPI rejects `llm-wiki` as too
    # similar to it, so neither shorter name can ever be published from here.
    assert _distribution_name() == "llm-wiki-plus"


def test_install_docs_name_the_packaged_distribution():
    dist = _distribution_name()
    wrong = [
        f"{path}:{lineno} installs {found!r}"
        for path, lineno, found in _install_commands()
        if found != dist
    ]
    assert not wrong, (
        f"install commands name a distribution other than pyproject's {dist!r}:\n  "
        + "\n  ".join(wrong)
        + f"\nUse `pip install {dist}` (extras: `{dist}[graph]`). If the line is "
        "historical rather than guidance, it belongs under one of "
        f"{ALLOWLIST_PREFIXES}."
    )


def test_the_scan_actually_finds_install_commands():
    # A regex that silently stops matching would make the test above vacuous.
    assert len(_install_commands()) >= 5


@pytest.mark.parametrize("doc", ["README.md", "CLAUDE.md", "AGENTS.md", "docs/tutorials/01-installation.md"])
def test_primary_entry_points_carry_an_install_line(doc: str):
    text = (REPO_ROOT / doc).read_text(encoding="utf-8")
    assert INSTALL_RE.search(text), f"{doc} lost its install command — it is a primary entry point"


def test_upstream_distribution_name_is_not_offered_as_an_install():
    """`llm-notebook` is upstream's name; we never published under it."""
    offenders = [
        f"{path}:{lineno}" for path, lineno, dist in _install_commands() if dist == "llm-notebook"
    ]
    assert not offenders, (
        "these lines tell a user to install `llm-notebook`, which is the upstream "
        "project rather than this fork: " + ", ".join(offenders)
    )
