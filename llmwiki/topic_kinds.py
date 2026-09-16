"""Folder → Connections kind map for entity/concept pages (#174 / #257).

Leaf module: no imports from ``synth`` or ``migrate_topic_kinds``, so vocabulary
injection and the offline stamp can share one scanner without a circular import.
"""

from __future__ import annotations

from pathlib import Path

#: Folder relative to ``wiki/`` → kind stamped onto Connections bullets.
_KIND_FOLDERS: tuple[tuple[str, str], ...] = (
    ("entities", "entity"),
    ("concepts", "concept"),
    ("candidates/entities", "entity"),
    ("candidates/concepts", "concept"),
)

_CONTEXT_FILE = "_context.md"


def build_kind_map(wiki: Path) -> tuple[dict[str, str], list[str]]:
    """Return case-folded stem→kind and ambiguous names skipped.

    Scans ``entities``, ``concepts``, and the candidates mirrors. A stem that
    appears under both kinds is removed from the map and listed as ambiguous
    (never guessed). ``_context.md`` and non-files are ignored.
    """
    kind_map: dict[str, str] = {}
    display: dict[str, str] = {}
    ambiguous_keys: set[str] = set()

    for rel, kind in _KIND_FOLDERS:
        folder = wiki / rel
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.md")):
            if not path.is_file() or path.name == _CONTEXT_FILE:
                continue
            key = path.stem.casefold()
            display.setdefault(key, path.stem)
            if key in ambiguous_keys:
                continue
            existing = kind_map.get(key)
            if existing is None:
                kind_map[key] = kind
            elif existing != kind:
                del kind_map[key]
                ambiguous_keys.add(key)

    ambiguous = sorted(display[k] for k in ambiguous_keys)
    return kind_map, ambiguous
