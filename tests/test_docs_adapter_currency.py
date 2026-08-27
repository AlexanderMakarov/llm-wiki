"""Docs currency: user-facing adapter support claims must match product state (#180).

Greps shipped product docs (not CHANGELOG / UPGRADING history) for banned
stale phrases such as “v0.1 stub”, “will be supported in…”, “coming in v0.”.
Fails when those strings appear so Codex / Cursor / etc. cannot drift back
into “future stub” wording.
"""

from __future__ import annotations

from pathlib import Path

from tests.conftest import REPO_ROOT

# Phrases that claim future / stub adapter support (tech spec § Docs currency).
BANNED_STALE_PHRASES: tuple[str, ...] = (
    "will be supported in",
    "coming in v0.",
    "v0.1 stub",
    "stub in v0.1",
    "not yet production-ready",
    "Configuration will land in v0.2",
    "✅ stub (v0.2)",
    "stub (v0.2)",
    "codex_cli.py (stub",
    "gemini_cli.py (planned)",
    "opencode.py (planned)",
)

# Paths relative to repo root that are historical release notes, not live docs.
_EXCLUDED_REL_PREFIXES: tuple[str, ...] = (
    "CHANGELOG.md",
    "docs/UPGRADING.md",
    "demo/",  # vault copies of older product docs
    "context/",  # AWOS working notes may quote the ban list
)

_SCAN_ROOTS: tuple[Path, ...] = (
    REPO_ROOT / "docs",
    REPO_ROOT / "README.md",
    REPO_ROOT / "AGENTS.md",
    REPO_ROOT / "CLAUDE.md",
)


def _is_excluded(path: Path) -> bool:
    try:
        rel = path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return True
    for prefix in _EXCLUDED_REL_PREFIXES:
        if rel == prefix or rel.startswith(prefix):
            return True
    return False


def iter_user_facing_markdown() -> list[Path]:
    """Markdown that ships as product / schema docs (excludes changelog history)."""
    out: list[Path] = []
    for root in _SCAN_ROOTS:
        if root.is_file() and root.suffix == ".md":
            if not _is_excluded(root):
                out.append(root)
            continue
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.md")):
            if _is_excluded(path):
                continue
            out.append(path)
    return out


def find_banned_phrase_hits(
    paths: list[Path],
    phrases: tuple[str, ...] = BANNED_STALE_PHRASES,
) -> list[str]:
    """Return human-readable hit lines for any banned phrase in ``paths``."""
    hits: list[str] = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        try:
            label = path.relative_to(REPO_ROOT).as_posix()
        except ValueError:
            label = path.name
        for phrase in phrases:
            start = 0
            while True:
                i = text.find(phrase, start)
                if i < 0:
                    break
                line_no = text.count("\n", 0, i) + 1
                hits.append(f"{label}:{line_no}: {phrase!r}")
                start = i + len(phrase)
    return hits


def test_docs_adapter_support_claims_are_current() -> None:
    """@spec: 175-exclude-headless-adapters — R6 docs currency gate."""
    paths = iter_user_facing_markdown()
    assert paths, "expected at least one user-facing markdown file to scan"
    hits = find_banned_phrase_hits(paths)
    assert not hits, (
        "Stale adapter-support wording in user-facing docs "
        "(exclude CHANGELOG / UPGRADING; update support map instead):\n"
        + "\n".join(hits)
    )


def test_docs_currency_checker_fails_on_planted_stale_phrase(
    tmp_path: Path,
) -> None:
    """Plant a banned phrase — the checker must report it (RED for planted)."""
    planted = tmp_path / "planted.md"
    planted.write_text(
        "Codex CLI adapter will be supported in v0.2 as a v0.1 stub.\n",
        encoding="utf-8",
    )
    hits = find_banned_phrase_hits([planted])
    assert hits, "expected planted stale phrases to be detected"
    joined = " ".join(hits)
    assert "will be supported in" in joined
    assert "v0.1 stub" in joined


def test_banned_phrase_list_covers_spec_examples() -> None:
    required = (
        "will be supported in",
        "coming in v0.",
        "v0.1 stub",
    )
    for phrase in required:
        assert phrase in BANNED_STALE_PHRASES
