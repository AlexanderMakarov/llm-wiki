#!/usr/bin/env python3
"""Read-only eval: proposed session ``description:`` for #249 weight tuning.

Loads recent Claude Code + Cursor CLI sessions from the local agent stores
(not the Obsidian vault). Prints assigned name (if any), top candidates with
scores, and the chosen description. Does not write any vault files.

Cursor store placeholder ``New Agent`` is treated as absent by
``assigned_session_name`` (falls through to scored prompts). Punctuation-only
candidates and Cursor XML chrome turns are skipped by the same convert/adapter
gates used at sync time.

Usage (from worktree root):

    python3 scripts/eval_session_descriptions.py --limit 15

Output is for chat review only — do not commit dumps that contain personal
paths or real usernames.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from llmwiki.adapters.claude_code import ClaudeCodeAdapter
from llmwiki.adapters.contrib.cursor_cli import CursorCliAdapter
from llmwiki.convert import (
    ARG_LONG_MIN,
    DESC_MAX_CHARS,
    LENGTH_WEIGHT,
    POSITION_STEP,
    TYPE_BASE_BARE,
    TYPE_BASE_HIGH,
    TYPE_BASE_SHORT_ARGS,
    Redactor,
    _description_candidate_has_alnum,
    _truncate_description,
    derive_description,
    rank_description_candidates,
)

_HOME = str(Path.home())
_REDACT_HOME = re.compile(re.escape(_HOME))


def _safe(text: str, max_len: int = 100) -> str:
    s = _REDACT_HOME.sub("~", text or "")
    s = s.replace("\n", " ").strip()
    if len(s) > max_len:
        s = s[: max_len - 3] + "..."
    return s


def _eval_one(adapter, path: Path, redact: Redactor) -> None:
    records = adapter.load_records(path)
    if hasattr(adapter, "normalize_records"):
        records = adapter.normalize_records(records) or records
    assigned = adapter.assigned_session_name(path, records)
    normalize = adapter.normalize_user_prompt
    ranked = rank_description_candidates(
        records, normalize_user_prompt=normalize
    )
    # Match convert: first non-empty line + alnum gate, else scored fallback.
    chosen = ""
    source = "SCORED"
    if isinstance(assigned, str) and assigned.strip():
        line = ""
        for raw_line in assigned.splitlines():
            part = raw_line.strip()
            if part:
                line = part
                break
        if line and _description_candidate_has_alnum(line):
            chosen = redact(_truncate_description(line))
            source = "ASSIGNED"
    if not chosen:
        chosen = derive_description(
            records, redact, normalize_user_prompt=normalize
        )
        source = "SCORED"
    print(f"\n=== {adapter.name} | {_safe(str(path), 80)} ===")
    print(f"source: {source}")
    if assigned:
        print(f"assigned: {_safe(assigned, 120)}")
    print(f"description: {_safe(chosen, 120)}")
    print("top candidates:")
    for row in ranked[:5]:
        print(
            f"  [{row['index']}] {row['score']:8.1f} {row['band']:16} "
            f"{_safe(str(row['text']), 90)}"
        )
    if not ranked and not assigned:
        print("  (no user-prompt candidates)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--limit",
        type=int,
        default=12,
        help="Max sessions per adapter (most recently modified first)",
    )
    args = parser.parse_args()
    redact = Redactor({"redaction": {"real_username": "", "extra_patterns": []}})

    print("Weights (frozen):")
    print(
        f"  ARG_LONG_MIN={ARG_LONG_MIN} TYPE_BARE={TYPE_BASE_BARE} "
        f"TYPE_SHORT={TYPE_BASE_SHORT_ARGS} TYPE_HIGH={TYPE_BASE_HIGH}"
    )
    print(
        f"  POSITION_STEP={POSITION_STEP} LENGTH_WEIGHT={LENGTH_WEIGHT} "
        f"DESC_MAX={DESC_MAX_CHARS}"
    )

    for adapter in (ClaudeCodeAdapter(), CursorCliAdapter()):
        try:
            paths = list(adapter.discover_sessions())
        except Exception as exc:  # noqa: BLE001 — eval must keep going
            print(f"\n=== {adapter.name}: discover failed: {exc} ===")
            continue
        paths = sorted(
            paths,
            key=lambda p: p.stat().st_mtime if p.is_file() else 0,
            reverse=True,
        )[: args.limit]
        print(f"\n# Adapter {adapter.name}: {len(paths)} sessions")
        for path in paths:
            try:
                _eval_one(adapter, path, redact)
            except Exception as exc:  # noqa: BLE001
                print(f"\n=== {adapter.name} | {_safe(str(path), 80)} ERROR: {exc} ===")


if __name__ == "__main__":
    main()
