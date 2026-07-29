#!/usr/bin/env python3
"""
TASK 3: Add missing metadata fields to raw/sessions/.

For each session file, calculate and add these frontmatter fields if missing:
- duration_seconds: difference between 'ended' and 'started' timestamps (ISO format)
- turn_count: equal to user_messages (already present)
- is_subagent: true if 'subagent' appears in the filename, false otherwise

Only adds fields that are missing — never overwrites existing ones.
"""

import os
import re
from datetime import datetime

SESSIONS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "raw", "sessions",
)


def parse_iso(ts: str) -> datetime | None:
    """Parse an ISO 8601 timestamp, tolerating various formats."""
    if not ts:
        return None
    # Remove trailing timezone info for parsing
    ts = ts.strip()
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        pass
    # Try stripping microseconds or timezone manually
    for fmt in [
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
    ]:
        try:
            return datetime.strptime(ts, fmt)
        except ValueError:
            continue
    return None


def add_missing_metadata():
    added_duration = 0
    added_turn_count = 0
    added_is_subagent = 0
    skipped_already_complete = 0
    errors = []

    for fname in sorted(os.listdir(SESSIONS_DIR)):
        if not fname.endswith(".md") or not fname.startswith("2026-"):
            continue

        fpath = os.path.join(SESSIONS_DIR, fname)
        with open(fpath, encoding="utf-8") as f:
            content = f.read()

        # Parse frontmatter
        fm_match = re.match(r"^(---\n)(.*?\n)(---)", content, re.DOTALL)
        if not fm_match:
            errors.append(f"  NO FRONTMATTER: {fname}")
            continue

        fm_start = fm_match.group(1)
        fm_body = fm_match.group(2)
        fm_end = fm_match.group(3)
        body = content[fm_match.end():]

        has_duration = bool(re.search(r"^duration_seconds:", fm_body, re.MULTILINE))
        has_turn_count = bool(re.search(r"^turn_count:", fm_body, re.MULTILINE))
        has_is_subagent = bool(re.search(r"^is_subagent:", fm_body, re.MULTILINE))

        if has_duration and has_turn_count and has_is_subagent:
            skipped_already_complete += 1
            continue

        lines_to_add = []

        # duration_seconds
        if not has_duration:
            started_m = re.search(r"^started:\s*(.+)$", fm_body, re.MULTILINE)
            ended_m = re.search(r"^ended:\s*(.+)$", fm_body, re.MULTILINE)
            if started_m and ended_m:
                start_dt = parse_iso(started_m.group(1).strip())
                end_dt = parse_iso(ended_m.group(1).strip())
                if start_dt and end_dt:
                    duration = int((end_dt - start_dt).total_seconds())
                    duration = max(0, duration)  # clamp negatives
                    lines_to_add.append(f"duration_seconds: {duration}")
                    added_duration += 1
                else:
                    lines_to_add.append("duration_seconds: 0")
                    added_duration += 1
            else:
                lines_to_add.append("duration_seconds: 0")
                added_duration += 1

        # turn_count
        if not has_turn_count:
            um_m = re.search(r"^user_messages:\s*(\d+)", fm_body, re.MULTILINE)
            turn_val = um_m.group(1) if um_m else "0"
            lines_to_add.append(f"turn_count: {turn_val}")
            added_turn_count += 1

        # is_subagent
        if not has_is_subagent:
            is_sub = "true" if "subagent" in fname.lower() else "false"
            lines_to_add.append(f"is_subagent: {is_sub}")
            added_is_subagent += 1

        if lines_to_add:
            # Add new fields before the closing ---
            # Insert them at the end of frontmatter (before the last newline)
            insert_text = "\n".join(lines_to_add) + "\n"
            new_fm_body = fm_body + insert_text
            new_content = fm_start + new_fm_body + fm_end + body

            with open(fpath, "w", encoding="utf-8") as f:
                f.write(new_content)

    # Report
    print("=" * 60)
    print("TASK 3: Add Missing Metadata Fields")
    print("=" * 60)
    print(f"  Added duration_seconds:  {added_duration}")
    print(f"  Added turn_count:        {added_turn_count}")
    print(f"  Added is_subagent:       {added_is_subagent}")
    print(f"  Already complete:        {skipped_already_complete}")
    if errors:
        print(f"  Errors:                  {len(errors)}")
        for e in errors:
            print(e)
    print()


if __name__ == "__main__":
    add_missing_metadata()
