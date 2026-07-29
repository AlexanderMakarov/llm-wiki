#!/usr/bin/env python3
"""Normalize broken wikilinks in wiki/ source pages.

Scans all .md files under wiki/ for wikilinks containing "/" or "\\"
and normalizes them by:
1. Keeping only the leaf name (last segment after /)
2. Stripping backslashes
3. TitleCasing the result (remove spaces/hyphens, capitalize)
4. Preserving display text in [[target|display]] format

Also handles edge cases:
- [[00 - Framework - Apps/Framework\\|App Framework]] -> [[Framework|App Framework]]
- [[Prompts/]] -> [[Prompts]]
- [["@skillscraft/spec", ...]] -> skipped (not a real wikilink)
- [[ -s "$HOME/..." ]] -> skipped (shell expression, not wikilink)
"""

import re
from pathlib import Path

WIKI_DIR = Path(__file__).resolve().parent.parent / "wiki"

# Match wikilinks that contain / or \ in the target portion
# Captures: full match, target (before |), display text (after |, optional)
BROKEN_WIKILINK_RE = re.compile(
    r'\[\['           # opening [[
    r'('              # group 1: target
    r'[^\]|]*'        #   anything except ] or |
    r'[/\\]'          #   must contain at least one / or \
    r'[^\]|]*'        #   rest of target
    r')'
    r'(?:\|([^\]]*))?' # optional group 2: |display text
    r'\]\]'           # closing ]]
)

def is_real_wikilink(target: str) -> bool:
    """Filter out shell expressions, JSON-like strings, etc."""
    target = target.strip()
    if target.startswith('"') or target.startswith("'"):
        return False
    if target.startswith('-s ') or target.startswith(' -'):
        return False
    if ',' in target and '"' in target:
        return False
    if '$' in target:
        return False
    return True


def to_title_case(name: str) -> str:
    """Convert a name to TitleCase: remove spaces, hyphens, underscores; capitalize words."""
    # Strip leading/trailing whitespace
    name = name.strip()
    # Remove trailing slash (e.g., "Prompts/")
    name = name.rstrip('/')
    # Strip backslashes
    name = name.replace('\\', '')
    # Split on spaces, hyphens, underscores
    words = re.split(r'[\s\-_]+', name)
    # Filter empty strings and capitalize
    words = [w.capitalize() for w in words if w]
    return ''.join(words)


def normalize_wikilink(match: re.Match) -> str:
    """Replace a broken wikilink with its normalized form."""
    target = match.group(1)
    display = match.group(2)  # may be None

    if not is_real_wikilink(target):
        return match.group(0)  # leave unchanged

    # Strip backslashes from target
    clean_target = target.replace('\\', '')

    # Take the leaf name (last path segment)
    # Handle both / separators
    segments = clean_target.split('/')
    leaf = segments[-1].strip()

    # If leaf is empty (e.g., [[Prompts/]]), use the last non-empty segment
    if not leaf:
        for seg in reversed(segments):
            seg = seg.strip()
            if seg:
                leaf = seg
                break

    if not leaf:
        return match.group(0)  # safety: leave unchanged

    # TitleCase the leaf
    normalized = to_title_case(leaf)

    if not normalized:
        return match.group(0)  # safety

    if display is not None:
        return f'[[{normalized}|{display}]]'
    else:
        return f'[[{normalized}]]'


def main():
    total_normalized = 0
    files_modified = 0

    md_files = sorted(WIKI_DIR.rglob("*.md"))
    print(f"Scanning {len(md_files)} markdown files under wiki/...")

    for md_file in md_files:
        text = md_file.read_text(encoding="utf-8", errors="replace")

        # Count matches before replacement
        matches = list(BROKEN_WIKILINK_RE.finditer(text))
        real_matches = [m for m in matches if is_real_wikilink(m.group(1))]

        if not real_matches:
            continue

        new_text = BROKEN_WIKILINK_RE.sub(normalize_wikilink, text)

        if new_text != text:
            md_file.write_text(new_text, encoding="utf-8")
            count = len(real_matches)
            total_normalized += count
            files_modified += 1
            rel = md_file.relative_to(WIKI_DIR)
            print(f"  {rel}: {count} links normalized")

    print(f"\nDone: {total_normalized} wikilinks normalized across {files_modified} files.")
    return total_normalized


if __name__ == "__main__":
    main()
