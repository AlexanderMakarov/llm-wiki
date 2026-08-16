"""Canonical list of system / nav / scaffolding pages used across
graph.py, lint/rules.py, and (potentially) future emitters.

#arch-l7 (#628 sibling): graph.py and lint/rules.py shipped two
hand-maintained lists of "pages that are exempt from the source /
entity / concept schema." The lists overlapped but drifted —
graph.py had `log-archive-2026`, lint missed it; lint had
`index.md`, graph used type-checks instead.

This module owns the single source of truth. Callers can request
either form via the helpers below.
"""
from __future__ import annotations

# Slugs (no `.md` suffix) — the form graph.py wants because it
# operates on graph-node ids that are already stripped of extension.
SYSTEM_PAGE_SLUGS: frozenset[str] = frozenset({
    "CRITICAL_FACTS",
    "MEMORY",
    "SOUL",
    "hints",
    "hot",
    "dashboard",
    "overview",
    "log",
    "log-archive-2026",
    "index",
})

# Filenames (with `.md`) — the form lint/rules.py wants because its
# input is page paths read off disk.
SYSTEM_PAGE_FILES: frozenset[str] = frozenset(
    f"{slug}.md" for slug in SYSTEM_PAGE_SLUGS
)


def is_system_slug(slug: str) -> bool:
    """True if ``slug`` (no extension) is a known system / nav page."""
    return slug in SYSTEM_PAGE_SLUGS


def is_system_file(basename: str) -> bool:
    """True if ``basename`` ends with ``.md`` and names a system page."""
    return basename in SYSTEM_PAGE_FILES


# ─── Archive folder (#140) ─────────────────────────────────────────────

# Same drift class as the system-page lists above: `wiki/archive/` was
# excluded by lint, backlinks and tags but catalogued by reindex and
# emitted as graph nodes, so a discarded candidate produced an
# `index_sync` error on a correct vault. Cold storage is the decided
# treatment — archive/ holds the candidate-triage reject bin written by
# candidates._archive_candidate, and nothing there is a live page.
ARCHIVE_FOLDER = "archive"


def is_archived_path(rel_parts: tuple[str, ...]) -> bool:
    """True if a wiki-relative path points into cold storage.

    ``rel_parts`` is ``path.relative_to(wiki_dir).parts`` — e.g.
    ``("archive", "candidates", "2026-08-01T13-22-06", "Bash.md")``.

    Top-level only: cold storage is exactly ``wiki/archive/**``, the one
    tree ``candidates._archive_candidate`` writes to. A folder named
    ``archive`` nested under a page folder stays a live page, because
    source pages are grouped by project slug — matching "archive" at any
    depth would make every page under a project slug of that name vanish
    from lint, graph, backlinks, tags and the index with no error, and a
    knowledge base must not lose pages silently.
    """
    return bool(rel_parts) and rel_parts[0] == ARCHIVE_FOLDER
