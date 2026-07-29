#!/usr/bin/env python3
"""
TASK 2: Fix model metadata in raw/sessions/.

In YAML frontmatter only:
- Empty model: → set to 'unknown'
- model: containing '{' (JSON blob) → try to extract name, else 'unknown'
- model: 'c' (truncated) → set to 'unknown'

Does not touch body content outside frontmatter.
"""

import json
import os

SESSIONS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "raw", "sessions",
)


def fix_models():
    fixed_empty = 0
    fixed_json = 0
    fixed_truncated = 0
    already_ok = 0
    details = []

    for fname in sorted(os.listdir(SESSIONS_DIR)):
        if not fname.endswith(".md") or not fname.startswith("2026-"):
            continue

        fpath = os.path.join(SESSIONS_DIR, fname)
        with open(fpath, encoding="utf-8") as f:
            lines = f.readlines()

        # Find frontmatter boundaries
        if not lines or lines[0].strip() != "---":
            continue
        fm_end_idx = None
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                fm_end_idx = i
                break
        if fm_end_idx is None:
            continue

        # Find the model line within frontmatter (lines 1..fm_end_idx-1)
        model_line_idx = None
        model_value = None
        for i in range(1, fm_end_idx):
            if lines[i].startswith("model:"):
                model_line_idx = i
                # Everything after "model:" on that line
                model_value = lines[i][len("model:"):].strip()
                break

        if model_line_idx is None:
            continue

        new_value = None
        fix_type = None

        if not model_value:
            # Empty model
            new_value = "unknown"
            fix_type = "empty"
        elif model_value == "c":
            # Truncated
            new_value = "unknown"
            fix_type = "truncated"
        elif "{" in model_value:
            # JSON blob — try to extract a model name
            try:
                blob = json.loads(model_value)
                extracted = (
                    blob.get("model")
                    or blob.get("name")
                    or blob.get("model_id")
                    or blob.get("id")
                )
                new_value = extracted if extracted else "unknown"
            except (json.JSONDecodeError, AttributeError):
                new_value = "unknown"
            fix_type = "json_blob"
        else:
            already_ok += 1
            continue

        # Replace the model line
        lines[model_line_idx] = f"model: {new_value}\n"

        with open(fpath, "w", encoding="utf-8") as f:
            f.writelines(lines)

        if fix_type == "empty":
            fixed_empty += 1
            details.append(f"  EMPTY → unknown: {fname}")
        elif fix_type == "json_blob":
            fixed_json += 1
            details.append(
                f"  JSON → {new_value}: {fname} (was: {model_value[:60]})"
            )
        elif fix_type == "truncated":
            fixed_truncated += 1
            details.append(f"  'c' → unknown: {fname}")

    # Report
    print("=" * 60)
    print("TASK 2: Fix Model Metadata")
    print("=" * 60)
    print(f"  Fixed empty model:       {fixed_empty}")
    print(f"  Fixed JSON blob model:   {fixed_json}")
    print(f"  Fixed truncated 'c':     {fixed_truncated}")
    print(f"  Already OK:              {already_ok}")
    print(f"  Total fixed:             {fixed_empty + fixed_json + fixed_truncated}")
    print()
    if details:
        print("Details:")
        for d in details:
            print(d)
        print()


if __name__ == "__main__":
    fix_models()
