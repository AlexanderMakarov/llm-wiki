#!/usr/bin/env python3
"""#56: deterministic in-place redaction of encoded usernames in raw/.

Rewrites ``raw/sessions/*.md`` so home-path *and* dash-encoded agent-store
segments use the ``USER`` placeholder (``-Users-<you>-…`` →
``-Users-USER-…``). Does **not**:

- call the LLM / enqueue ``synthesize``
- touch ``wiki/``
- re-read ``~/.claude/projects/`` or Cursor session stores (those transcripts
  are typically retained only ~30 days — older sessions cannot be
  re-converted from the agent store)

Prefer this over ``llmwiki sync --force`` when you care about redaction
completeness in already-synced ``raw/``.

Usage:
  python3 scripts/migrate_raw_encoded_username.py --vault /path/to/vault
  python3 scripts/migrate_raw_encoded_username.py --vault /path/to/vault --dry-run
  llmwiki migrate-raw-redaction --vault /path/to/vault
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from llmwiki.convert import (
    _resolve_convert_config,
    _substitute_path_username,
)


def _sessions_dir(vault: Path) -> Path:
    return vault / "raw" / "sessions"


def migrate_text(text: str, *, real_username: str, replacement: str) -> str:
    """Apply the same username substitution convert uses for new syncs."""
    return _substitute_path_username(
        text, from_user=real_username, to_user=replacement
    )


def run_migration(
    *,
    vault: Path,
    real_username: str | None = None,
    replacement_username: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Rewrite ``vault/raw/sessions/**/*.md`` in place. Returns a report dict."""
    vault = vault.expanduser().resolve()
    if real_username is None or replacement_username is None:
        cfg = _resolve_convert_config(None)
        red = cfg.get("redaction", {})
        if real_username is None:
            real_username = str(red.get("real_username") or "").strip()
        if replacement_username is None:
            replacement_username = str(
                red.get("replacement_username") or "USER"
            ).strip() or "USER"

    real_username = (real_username or "").strip()
    replacement_username = (replacement_username or "USER").strip() or "USER"
    if not real_username:
        raise ValueError(
            "real_username is empty — set redaction.real_username in "
            "config.json (or ensure $USER/$USERNAME is set) before migrating"
        )
    if real_username == replacement_username:
        raise ValueError(
            f"real_username and replacement_username are both "
            f"{real_username!r}; nothing to rewrite"
        )

    sessions = _sessions_dir(vault)
    report: dict[str, Any] = {
        "vault": str(vault),
        "sessions_dir": str(sessions),
        "real_username": real_username,
        "replacement_username": replacement_username,
        "dry_run": dry_run,
        "scanned": 0,
        "rewritten": 0,
        "unchanged": 0,
        "errors": [],
        "files": [],
    }
    if not sessions.is_dir():
        report["errors"].append(f"missing sessions dir: {sessions}")
        return report

    for path in sorted(sessions.rglob("*.md")):
        report["scanned"] += 1
        try:
            original = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            report["errors"].append(f"{path}: {exc}")
            continue
        updated = migrate_text(
            original,
            real_username=real_username,
            replacement=replacement_username,
        )
        if updated == original:
            report["unchanged"] += 1
            continue
        report["rewritten"] += 1
        report["files"].append(str(path.relative_to(vault)))
        if not dry_run:
            path.write_text(updated, encoding="utf-8")
    return report


def print_report(report: dict[str, Any]) -> None:
    print(f"vault:       {report['vault']}")
    print(f"sessions:    {report['sessions_dir']}")
    print(f"username:    {report['real_username']} → {report['replacement_username']}")
    print(f"dry_run:     {report['dry_run']}")
    print(f"scanned:     {report['scanned']}")
    print(f"rewritten:   {report['rewritten']}")
    print(f"unchanged:   {report['unchanged']}")
    if report["errors"]:
        print(f"errors:      {len(report['errors'])}")
        for err in report["errors"][:10]:
            print(f"  ! {err}")
    if report["files"] and (report["dry_run"] or report["rewritten"] <= 20):
        print("files:")
        for rel in report["files"][:50]:
            print(f"  - {rel}")
        if len(report["files"]) > 50:
            print(f"  … +{len(report['files']) - 50} more")
    print(
        "note: wiki/ untouched; no synthesize queued. "
        "Run `llmwiki build --vault …` afterwards so site/ picks up changes."
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=(
            "Deterministic #56 migration: redact encoded usernames in "
            "raw/sessions without re-sync or re-synth."
        )
    )
    p.add_argument(
        "--vault",
        type=Path,
        required=True,
        help="Vault root (contains raw/sessions/)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Report files that would change; write nothing",
    )
    p.add_argument(
        "--real-username",
        default=None,
        help="Override redaction.real_username (default: from config / $USER)",
    )
    p.add_argument(
        "--replacement-username",
        default=None,
        help="Override replacement placeholder (default: USER)",
    )
    args = p.parse_args(argv)
    try:
        report = run_migration(
            vault=args.vault,
            real_username=args.real_username,
            replacement_username=args.replacement_username,
            dry_run=args.dry_run,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print_report(report)
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
