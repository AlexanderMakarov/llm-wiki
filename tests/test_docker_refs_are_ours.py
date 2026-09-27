"""Repo hygiene: every project-artifact reference names *this* repository (#211).

This is a fork. Clone URLs, registry images, OCI provenance, marketplace
publishers and package metadata were all inherited pointing at the upstream
owner, and ``link-check.yml`` never caught it: lychee tests *liveness*, and an
upstream reference resolves fine. A reachable-but-foreign reference is worse
than a 404 — it silently succeeds and runs somebody else's software.

The owner is derived once from ``pyproject.toml`` ``[project.urls] Repository``
so no assertion hardcodes an owner string; rename the repo and the expectation
follows.

**Extending this file:** the scanned surfaces live in :data:`SURFACES`, a table
of :class:`Surface` rows (label, path predicate, pattern, what it asserts).
Sibling identity issues — #210 (PyPI), #212 (Homebrew), ``action.yml`` — extend
the check by adding a row, not by writing a parallel scanner. When #212 folds
its rows in, this file may be renamed to a neutral name such as
``test_identity_refs_are_ours.py``.
"""

from __future__ import annotations

import re
import tomllib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest

from llmwiki import REPO_ROOT
from tests.tracked_files import tracked_files

# ─── Scope ────────────────────────────────────────────────────────────

# Files whose *content* legitimately names a foreign owner, split by how the
# entry is matched — a directory prefix, a filename prefix, or an exact path:
# - ``CHANGELOG.md`` / ``RELEASE-NOTES*``: frozen release history.
# - ``context/``: specs and flow-logs recording the fork's own origin.
# - ``LICENSE``: MIT requires retaining the upstream copyright line.
# ``README.md`` is deliberately *not* here: only its two attribution lines
# name upstream, and exempting the whole file would unguard its clone URL,
# CI badges and issue links. See :data:`LINE_EXEMPTIONS`.
#: Whole directories, matched as a path prefix.
ALLOWLIST_DIRS: tuple[str, ...] = (
    "context/",
    "demo/raw/docs/phase-1-25-research-report/",
)

#: Filename *prefixes*, for versioned names (``RELEASE-NOTES-v1.2.3.md``).
#: A prefix is a wide exemption, so this stays as short as it can be.
ALLOWLIST_PREFIXES: tuple[str, ...] = ("RELEASE-NOTES",)

#: Exact paths. Prefix-matching these would silently exempt
#: ``LICENSE-APACHE``, ``CHANGELOG.md.orig`` and anything else that happens
#: to share the first characters.
ALLOWLIST_FILES: frozenset[str] = frozenset({
    "CHANGELOG.md",
    "LICENSE",
    # Competitive-landscape survey: cites third-party prior art by URL,
    # including a distinct project that shares our repo name exactly.
    "docs/research.md",
})

#: Reserved for #212. Our Homebrew tap does not exist yet, so repointing this
#: would document a 404 under our own name. Exactly one file fails the
#: "Homebrew tap owner" surface today: the setup guide's ``brew tap`` /
#: ``brew install`` commands. The other Homebrew files either already name us
#: (``homebrew/llmwiki.rb``) or mention upstream's tap only to warn against
#: pushing to it, which the surface deliberately does not match.
#: #212 DELETES this tuple — it must not grow, and no parallel Homebrew check
#: should be written alongside it.
HOMEBREW_EXEMPT_212: tuple[str, ...] = (
    "docs/deploy/homebrew-setup.md",
)

#: Line-level exemptions, for a file that is ours except for a few lines that
#: must credit upstream. The matching lines are dropped before scanning, so
#: every *other* line in the file stays guarded — unlike :data:`ALLOWLIST`,
#: which switches a whole file off.
LINE_EXEMPTIONS: dict[str, re.Pattern[str]] = {
    # README's Acknowledgements bullet and its license attribution line.
    "README.md": re.compile(
        r"original llm-wiki project this repository builds on"
        r"|originally based on"
    ),
}

#: Text surfaces worth scanning. Anything else (images, fonts) is skipped.
SCANNED_SUFFIXES = frozenset({
    ".md", ".yml", ".yaml", ".json", ".toml", ".nix", ".sh",
    ".py", ".svg", ".rb", ".txt", ".cfg", ".ini", ".html", ".js",
})
SCANNED_NAMES = frozenset({"Dockerfile"})

#: Owner slots a doc may legitimately leave for the reader to fill in.
#: ``docs/deploy/github-pages.md`` tells you to clone *your own* fork.
PLACEHOLDER_RE = re.compile(r"^(<[^>]+>|\$\{?[A-Z_]+\}?|YOUR[-_]?\w*|OWNER)$", re.IGNORECASE)


# ─── Owner, derived once ──────────────────────────────────────────────


def _canonical_owner() -> str:
    """Return the GitHub owner from ``[project.urls] Repository``."""
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    repository = data["project"]["urls"]["Repository"]
    match = re.search(r"github\.com[:/]([^/]+)/", repository)
    assert match, f"cannot parse an owner out of Repository = {repository!r}"
    return match.group(1)


OWNER = _canonical_owner()
#: Container registries are case-insensitive and normalise to lowercase.
OWNER_LC = OWNER.lower()

#: The fork parent's owner. Assembled from fragments — the same trick
#: :data:`_FORBIDDEN_EMAIL` and ``tests/test_privacy_username.py`` use — so
#: this guard does not itself commit a greppable copy of what it forbids.
_UPSTREAM_OWNER = "".join(("Prati", "yush")).lower()


#: The invented owner test fixtures pin themselves to, so a fixture never
#: bakes in a real person's account. Not a real GitHub owner.
FIXTURE_OWNER = "ExampleOwner"

#: Reserved documentation names that may stand in an owner slot. ``example``
#: is the RFC 2606 documentation label, used by the Pages fixtures in
#: ``tests/test_pages_deploy.py`` and by CLI usage examples in docstrings.
#: Neither is a registrable GitHub account.
RESERVED_OWNERS = frozenset({FIXTURE_OWNER.lower(), "example"})


def _is_ours(candidate: str) -> bool:
    """True when ``candidate`` is our owner, a placeholder, or a reserved name."""
    return (
        candidate.lower() in {OWNER_LC, *RESERVED_OWNERS}
        or bool(PLACEHOLDER_RE.match(candidate))
    )


# ─── Surface table ────────────────────────────────────────────────────

# An owner slot: everything up to the next delimiter. Deliberately permissive
# so placeholders like `<your-user>` are *captured* and then judged, rather
# than silently skipped by a narrow character class.
_OWNER_SLOT = r"([^\s/:\"'`)\]}]+)"

# The repo name must end here: `llm-wiki-template` and `llm-wiki-agent` are
# *different, third-party* projects, not misspelt references to ours.
_REPO_END = r"(?![\w-])"


@dataclass(frozen=True)
class Surface:
    """One scanned reference shape.

    ``label``     human name used in failure messages.
    ``applies``   path predicate (repo-relative posix path -> bool).
    ``pattern``   regex whose group 1 is the owner slot.
    ``asserts``   what a reader should understand the row to guarantee.
    """

    label: str
    applies: Callable[[str], bool]
    pattern: re.Pattern[str]
    asserts: str


SURFACES: tuple[Surface, ...] = (
    Surface(
        label="GHCR image reference",
        applies=lambda _p: True,
        pattern=re.compile(rf"ghcr\.io/{_OWNER_SLOT}/llm-wiki{_REPO_END}"),
        asserts="no committed file pulls or pushes another owner's image",
    ),
    Surface(
        label="GitHub repository URL",
        applies=lambda _p: True,
        pattern=re.compile(rf"github\.com[:/]{_OWNER_SLOT}/llm-wiki{_REPO_END}"),
        asserts="no committed file links at another owner's repository",
    ),
    Surface(
        label="GitHub Pages site URL",
        applies=lambda _p: True,
        pattern=re.compile(rf"https?://{_OWNER_SLOT}\.github\.io/llm-wiki"),
        asserts="no committed file sends a reader to another owner's demo site",
    ),
    Surface(
        label="Homebrew tap owner",
        applies=lambda _p: True,
        pattern=re.compile(
            rf"(?:brew tap |brew install |github\.com[:/]){_OWNER_SLOT}"
            r"/(?:tap|homebrew-tap)\b"
        ),
        asserts="no committed file taps or installs from another owner's Homebrew tap",
    ),
    Surface(
        label="integration manifest owner",
        applies=lambda p: p.startswith("integrations/"),
        pattern=re.compile(
            rf"(?:github\.com[:/]|\"publisher\"\s*:\s*\"){_OWNER_SLOT}"
        ),
        asserts="marketplace publisher and repo fields name us, not a third party",
    ),
)


# ─── Scanning ─────────────────────────────────────────────────────────


def _owner_sweep_exempt(rel: str) -> bool:
    """True when ``rel`` is excused from the owner sweep."""
    return (
        rel in ALLOWLIST_FILES
        or rel in HOMEBREW_EXEMPT_212
        or rel.startswith(ALLOWLIST_DIRS)
        or rel.rsplit("/", 1)[-1].startswith(ALLOWLIST_PREFIXES)
    )


def _scannable(root: Path) -> list[tuple[str, str]]:
    """Return ``(relative_posix_path, text)`` for every in-scope tracked file."""
    out: list[tuple[str, str]] = []
    for path in tracked_files(root):
        rel = path.relative_to(root).as_posix()
        if _owner_sweep_exempt(rel):
            continue
        if path.suffix not in SCANNED_SUFFIXES and path.name not in SCANNED_NAMES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        exempt = LINE_EXEMPTIONS.get(rel)
        if exempt is not None:
            text = "\n".join(
                line for line in text.splitlines() if not exempt.search(line)
            )
        out.append((rel, text))
    return out


@pytest.fixture(scope="module")
def scanned() -> list[tuple[str, str]]:
    """In-scope tracked files, or skip when git is unavailable."""
    if not tracked_files(REPO_ROOT):
        pytest.skip("git unavailable or not a repository")
    return _scannable(REPO_ROOT)


# ─── Non-vacuity guards ───────────────────────────────────────────────


def test_scan_actually_sees_files(scanned):
    """A scan over nothing would pass every assertion below."""
    assert len(scanned) > 50, f"only {len(scanned)} files scanned — scope is broken"


def test_derived_owner_is_not_the_upstream_fork_parent():
    """A regressed Repository URL would make every sweep below vacuous.

    ``OWNER`` comes from ``pyproject.toml``; nothing else checks that value.
    If a bad merge pointed it back at the fork parent, every assertion in
    this file would pass while the repository was fully mis-attributed.
    """
    assert OWNER_LC != _UPSTREAM_OWNER, (
        f"pyproject.toml [project.urls] Repository names {OWNER!r} — "
        "the identity sweep is measuring the wrong owner"
    )


def test_docker_docs_still_reference_a_ghcr_image():
    """Guard the thing under test: a doc rewrite must not vacuously pass."""
    text = (REPO_ROOT / "docs" / "deploy" / "docker.md").read_text(encoding="utf-8")
    assert re.search(r"ghcr\.io/\S+/llm-wiki", text), (
        "docs/deploy/docker.md no longer names a GHCR image — either the guide "
        "moved, or the surface this test protects was deleted."
    )


def test_surface_patterns_match_something(scanned):
    """Every table row must be live; a dead row is a silent hole."""
    for surface in SURFACES:
        hits = sum(
            len(surface.pattern.findall(text))
            for rel, text in scanned
            if surface.applies(rel)
        )
        assert hits, f"{surface.label}: pattern matched nothing — row is dead"


# ─── The sweep ────────────────────────────────────────────────────────


@pytest.mark.parametrize("surface", SURFACES, ids=lambda s: s.label)
def test_surface_names_only_this_repository(surface: Surface, scanned):
    """Table-driven: no scanned file names a foreign owner on this surface."""
    foreign: list[str] = []
    for rel, text in scanned:
        if not surface.applies(rel):
            continue
        for candidate in surface.pattern.findall(text):
            if not _is_ours(candidate):
                foreign.append(f"{rel}: {candidate!r}")

    assert not foreign, (
        f"{surface.label} — expected owner {OWNER!r} ({surface.asserts}):\n  "
        + "\n  ".join(sorted(set(foreign)))
    )


# ─── Docker-specific contracts ────────────────────────────────────────

_CLONE_RE = re.compile(rf"git clone\s+(?:https://|git@)github\.com[:/]{_OWNER_SLOT}/llm-wiki{_REPO_END}")


def test_deploy_guides_clone_this_repository(scanned):
    """Every `git clone …/llm-wiki` under docs/deploy/ names us or a placeholder."""
    found = 0
    foreign: list[str] = []
    for rel, text in scanned:
        if not rel.startswith("docs/deploy/"):
            continue
        for candidate in _CLONE_RE.findall(text):
            found += 1
            if not _is_ours(candidate):
                foreign.append(f"{rel}: {candidate!r}")

    assert found, "no clone instructions found under docs/deploy/ — scope is broken"
    assert not foreign, "deploy guides clone a foreign repository:\n  " + "\n  ".join(foreign)


def _compose_image() -> str:
    text = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    match = re.search(r"^\s*image:\s*(\S+)", text, re.MULTILINE)
    assert match, "docker-compose.yml declares no image:"
    return match.group(1)


def test_docs_image_matches_compose_image():
    """The guide and the compose file must ship the same image reference."""
    compose_image = _compose_image()
    repository = compose_image.rsplit(":", 1)[0]
    docs = (REPO_ROOT / "docs" / "deploy" / "docker.md").read_text(encoding="utf-8")
    assert repository in docs, (
        f"docker-compose.yml uses {repository!r} but docs/deploy/docker.md never "
        "mentions it — a reader following the guide would pull a different image."
    )


def test_compose_header_only_names_files_that_exist():
    """`-f something.yml` in the header comment must resolve on disk."""
    text = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    header = text.split("\nservices:", 1)[0]
    referenced = re.findall(r"-f\s+(\S+\.ya?ml)", header)
    missing = [name for name in referenced if not (REPO_ROOT / name).is_file()]
    assert not missing, (
        "docker-compose.yml's header documents compose files that do not exist: "
        f"{missing}"
    )


# ─── Third-party email address ────────────────────────────────────────

#: The upstream maintainer's personal address, which the fork inherited
#: through the demo corpus and published on the live demo site. Assembled
#: from fragments — the same trick ``tests/test_privacy_username.py`` uses —
#: so this guard does not itself commit a greppable copy of what it forbids.
_FORBIDDEN_EMAIL = "".join(("prati", "yush", "1", "@", "gma", "il.com"))

#: Deliberately *narrower* than :data:`ALLOWLIST`. Frozen release history and
#: the attribution files may retain it; ``context/`` may not. A spec or
#: flow-log quoting the address back is exactly how it survived the first
#: sweep, so the working notes are in scope for this check.
EMAIL_ALLOWLIST_FILES: frozenset[str] = frozenset({
    "CHANGELOG.md",
    "LICENSE",
    "README.md",
    *HOMEBREW_EXEMPT_212,
})

#: Versioned release-note filenames, matched as a filename prefix.
EMAIL_ALLOWLIST_PREFIXES: tuple[str, ...] = ("RELEASE-NOTES",)


def test_no_tracked_file_publishes_the_upstream_email(scanned):
    """A third party's email address must not ship in this repository.

    ``scanned`` is only requested to reuse its git-availability skip; this
    check walks the *whole* tracked set, including paths and suffixes the
    owner sweep ignores, because an address can land anywhere.
    """
    assert scanned  # the module-scoped fixture already skipped if git is absent

    hits: list[str] = []
    for path in tracked_files(REPO_ROOT):
        rel = path.relative_to(REPO_ROOT).as_posix()
        if rel in EMAIL_ALLOWLIST_FILES or rel.rsplit("/", 1)[-1].startswith(
            EMAIL_ALLOWLIST_PREFIXES
        ):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if _FORBIDDEN_EMAIL in text:
            hits.append(rel)

    assert not hits, (
        "a third party's email address is committed in: " + ", ".join(sorted(hits))
    )
