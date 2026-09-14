#!/usr/bin/env python3
"""#56 / #253: deterministic in-place username rewrite of paths in raw/.

``migrate raw-redaction`` rewrites ``raw/sessions/*.md`` so home-path *and*
dash-encoded agent-store segments use the ``USER`` placeholder
(``-Users-<you>-…`` → ``-Users-USER-…``). ``migrate raw-unredaction`` is the
reverse: it restores the real username in those same path shapes (bare
occurrences of the placeholder word are never touched). Neither does:

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
  python3 scripts/migrate_raw_encoded_username.py --vault /path/to/vault --reverse
  llmwiki migrate raw-redaction --vault /path/to/vault
  llmwiki migrate raw-unredaction --vault /path/to/vault
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


def _resolve_usernames(
    real_username: str | None, replacement_username: str | None
) -> tuple[str, str, dict[str, Any]]:
    """Fill unset usernames from the effective convert config; validate them."""
    red: dict[str, Any] = {}
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
    return real_username, replacement_username, red


def _rewrite_sessions(
    *,
    vault: Path,
    from_user: str,
    to_user: str,
    real_username: str,
    replacement_username: str,
    direction: str,
    dry_run: bool,
) -> dict[str, Any]:
    """Apply ``from_user`` → ``to_user`` path rewrites to every raw session file."""
    sessions = _sessions_dir(vault)
    report: dict[str, Any] = {
        "vault": str(vault),
        "sessions_dir": str(sessions),
        "real_username": real_username,
        "replacement_username": replacement_username,
        "direction": direction,
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
        updated = _substitute_path_username(
            original, from_user=from_user, to_user=to_user
        )
        if updated == original:
            report["unchanged"] += 1
            continue
        report["rewritten"] += 1
        report["files"].append(str(path.relative_to(vault)))
        if not dry_run:
            path.write_text(updated, encoding="utf-8")
    return report


def run_migration(
    *,
    vault: Path,
    real_username: str | None = None,
    replacement_username: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Redact ``vault/raw/sessions/**/*.md`` in place (real → placeholder).

    Runs regardless of ``redaction.redact_username``: invoking the migration
    is the explicit request to redact. Returns a report dict.
    """
    real, repl, _red = _resolve_usernames(real_username, replacement_username)
    return _rewrite_sessions(
        vault=vault.expanduser().resolve(),
        from_user=real,
        to_user=repl,
        real_username=real,
        replacement_username=repl,
        direction="redact",
        dry_run=dry_run,
    )


def run_unredaction(
    *,
    vault: Path,
    real_username: str | None = None,
    replacement_username: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Restore the real username in ``vault/raw/sessions/**/*.md`` (#253).

    Rewrites the placeholder back to ``real_username`` only in home-path and
    dash-encoded path positions, so a bare placeholder word in prose stays.
    Idempotent. Raises ``ValueError`` when ``real_username`` is empty or
    equals the placeholder. The report's ``config_redact_username`` is True
    when the effective config would redact new syncs again.
    """
    real, repl, red = _resolve_usernames(real_username, replacement_username)
    if not red:
        red = _resolve_convert_config(None).get("redaction", {})
    report = _rewrite_sessions(
        vault=vault.expanduser().resolve(),
        from_user=repl,
        to_user=real,
        real_username=real,
        replacement_username=repl,
        direction="unredact",
        dry_run=dry_run,
    )
    report["config_redact_username"] = bool(red.get("redact_username", False))
    return report


def print_report(report: dict[str, Any]) -> None:
    """Print a migration report produced by ``run_migration`` / ``run_unredaction``."""
    real, repl = report["real_username"], report["replacement_username"]
    unredact = report.get("direction") == "unredact"
    print(f"vault:       {report['vault']}")
    print(f"sessions:    {report['sessions_dir']}")
    print(f"username:    {repl + ' → ' + real if unredact else real + ' → ' + repl}")
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
    if unredact and report.get("config_redact_username"):
        print(
            "note: redaction.redact_username is still true in config — new "
            "syncs will keep writing the placeholder; set it to false to keep "
            "real paths."
        )
    print(
        "note: wiki/ untouched; no synthesize queued. "
        "Run `llmwiki build --vault …` afterwards so site/ picks up changes."
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=(
            "Deterministic #56 / #253 migration: redact (or, with --reverse, "
            "restore) home-path usernames in raw/sessions without re-sync or "
            "re-synth."
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
    p.add_argument(
        "--reverse",
        action="store_true",
        help="Restore the real username in place of the placeholder",
    )
    args = p.parse_args(argv)
    runner = run_unredaction if args.reverse else run_migration
    try:
        report = runner(
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
