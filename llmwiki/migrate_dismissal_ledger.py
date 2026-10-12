"""Rebuild ``wiki/archive/candidates/dismissals.json`` from the archive (#326).

Offline one-time import for vaults that still carry legacy sibling
``*.reason.txt`` files (or archived stubs with no ledger yet). Scans
``wiki/archive/candidates/`` the same way :func:`llmwiki.dismissal_ledger.rebuild_ledger_from_archive`
does, then writes ``dismissals.json``.

When the ledger file is already missing, ordinary ledger reads
(:func:`llmwiki.dismissal_ledger.load_ledger`) auto-rebuild; this migrate
is the explicit operator path — including ``--dry-run`` and forcing a
rebuild when a ledger already exists.

No synthesis backend or network call; ``raw/`` is never written. A second
apply against an unchanged archive is a no-op (same ledger content).

Usage::

    llmwiki migrate dismissal-ledger --vault /path/to/vault --dry-run
    llmwiki migrate dismissal-ledger --vault /path/to/vault
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from llmwiki.dismissal_ledger import (
    LEDGER_FILENAME,
    build_ledger_from_archive,
    ledger_path,
    save_ledger,
)


def _ledger_payload(ledger: dict[str, Any]) -> str:
    """Canonical JSON for equality checks (matches :func:`save_ledger` shape)."""
    return json.dumps(ledger, indent=2, ensure_ascii=False) + "\n"


def run_migration(*, vault: Path, dry_run: bool = False) -> dict[str, Any]:
    """Import / rebuild ``dismissals.json`` from archived stubs + legacy reasons.

    Dry-run computes the same ledger without writing. Never touches ``raw/``.
    """
    vault = Path(vault).expanduser().resolve()
    wiki = vault / "wiki"
    path = ledger_path(wiki)
    report: dict[str, Any] = {
        "vault": str(vault),
        "wiki_dir": str(wiki),
        "ledger_path": str(path),
        "dry_run": dry_run,
        "dismissals": 0,
        "merges": 0,
        "ledger_existed": path.is_file(),
        "changed": False,
        "errors": [],
        "aborted": False,
    }
    if not wiki.is_dir():
        report["errors"].append(f"missing wiki dir: {wiki}")
        report["aborted"] = True
        return report

    built = build_ledger_from_archive(wiki)
    report["dismissals"] = len(built["dismissals"])
    report["merges"] = len(built["merges"])
    new_payload = _ledger_payload(built)

    if path.is_file():
        try:
            existing = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            report["errors"].append(f"{LEDGER_FILENAME}: {exc}")
            report["aborted"] = True
            return report
        report["changed"] = existing != new_payload
    else:
        report["changed"] = True

    if dry_run or report["aborted"]:
        return report

    if report["changed"]:
        save_ledger(wiki, built)
    return report


def print_report(report: dict[str, Any]) -> None:
    """Print an operator-facing summary."""
    if report["aborted"] and report["errors"]:
        print(f"vault:             {report['vault']}")
        print(f"errors:            {len(report['errors'])}")
        for err in report["errors"][:10]:
            print(f"  ! {err}")
        print("  nothing was written: fix the errors above and re-run")
        return

    print(f"vault:             {report['vault']}")
    print(f"wiki:              {report['wiki_dir']}")
    print(f"ledger:            {report['ledger_path']}")
    print(f"dry_run:           {report['dry_run']}")
    print(f"ledger existed:    {report['ledger_existed']}")
    print(f"dismissals:        {report['dismissals']}")
    print(f"merges:            {report['merges']}")
    if report["changed"]:
        action = "would write" if report["dry_run"] else "wrote"
        print(f"result:            {action} {LEDGER_FILENAME}")
    else:
        print(f"result:            unchanged ({LEDGER_FILENAME} already matches archive)")
    if report["dry_run"]:
        print("dry run: nothing was written")
    if report["errors"]:
        print(f"errors:            {len(report['errors'])}")
        for err in report["errors"][:10]:
            print(f"  ! {err}")
