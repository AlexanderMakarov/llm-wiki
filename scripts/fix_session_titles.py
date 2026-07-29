#!/usr/bin/env python3
"""
TASK 1: Fix session titles in raw/sessions/.

For files where the title is "Session: <slug> — <date>", check the project: field.
If project exists and is not 'unknown', update title to "Session: <project>/<slug> — <date>".

Only modifies the title: line in YAML frontmatter. Does not touch body content.
"""

import os
import re

SESSIONS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "raw", "sessions",
)


def fix_titles():
    updated = 0
    skipped_no_match = 0
    skipped_already = 0
    skipped_no_project = 0
    errors = []

    for fname in sorted(os.listdir(SESSIONS_DIR)):
        if not fname.endswith(".md") or not fname.startswith("2026-"):
            continue

        fpath = os.path.join(SESSIONS_DIR, fname)
        with open(fpath, encoding="utf-8") as f:
            content = f.read()

        # Parse frontmatter (between first --- and second ---)
        fm_match = re.match(r"^(---\n)(.*?\n)(---)", content, re.DOTALL)
        if not fm_match:
            errors.append(f"  NO FRONTMATTER: {fname}")
            continue

        fm_start = fm_match.group(1)  # "---\n"
        fm_body = fm_match.group(2)   # frontmatter content
        fm_end = fm_match.group(3)    # "---"
        body = content[fm_match.end():]

        # Extract title from frontmatter
        title_match = re.search(
            r'^(title:\s*"Session:\s+)([\w-]+)(\s+—\s+\d{4}-\d{2}-\d{2}")',
            fm_body,
            re.MULTILINE,
        )
        if not title_match:
            skipped_no_match += 1
            continue

        slug_in_title = title_match.group(2)

        # If already has a project prefix (contains /), skip
        if "/" in slug_in_title:
            skipped_already += 1
            continue

        # Extract project from frontmatter
        project_match = re.search(r"^project:\s*(\S+)", fm_body, re.MULTILINE)
        if not project_match or project_match.group(1) == "unknown":
            skipped_no_project += 1
            continue

        project = project_match.group(1)

        # Build new title line
        old_title_line = title_match.group(0)
        new_title_line = (
            title_match.group(1)
            + project + "/" + slug_in_title
            + title_match.group(3)
        )

        # Replace in frontmatter only
        new_fm_body = fm_body.replace(old_title_line, new_title_line, 1)
        new_content = fm_start + new_fm_body + fm_end + body

        with open(fpath, "w", encoding="utf-8") as f:
            f.write(new_content)

        updated += 1

    # Report
    print("=" * 60)
    print("TASK 1: Fix Session Titles")
    print("=" * 60)
    print(f"  Titles updated:          {updated}")
    print(f"  Already had project:     {skipped_already}")
    print(f"  No 'Session:' title:     {skipped_no_match}")
    print(f"  No usable project:       {skipped_no_project}")
    if errors:
        print(f"  Errors:                  {len(errors)}")
        for e in errors:
            print(e)
    print()


if __name__ == "__main__":
    fix_titles()
