#!/usr/bin/env python3
"""CLI wrapper for :func:`llmwiki.synth.state_backfill.reconcile_synth_state_from_wiki_pages`.

See module docstring in ``state_backfill`` and ``docs/deploy/github-pages.md`` (#255).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from llmwiki.synth.state_backfill import reconcile_synth_state_from_wiki_pages


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Reconcile synth.files and Pipeline pending from on-disk wiki/sources coverage."
        ),
    )
    parser.add_argument(
        "--vault",
        type=Path,
        required=True,
        help="Vault root (must contain wiki/, raw/, llmwiki-state.json)",
    )
    args = parser.parse_args(argv)
    vault = args.vault.expanduser().resolve()
    if not (vault / "wiki").is_dir():
        print(f"error: not a vault (missing wiki/): {vault}", file=sys.stderr)
        return 2
    upserts, errors = reconcile_synth_state_from_wiki_pages(vault=vault)
    for err in errors:
        print(f"warning: {err}", file=sys.stderr)
    if errors:
        return 1
    if upserts:
        print(
            f"reconciled {upserts} synth.files mtime "
            f"entr{'y' if upserts == 1 else 'ies'} from wiki pages; refreshed pending"
        )
    else:
        print("synth.files already matched wiki coverage; refreshed pending")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
