"""CI gate: product-related path changes must also update AWOS notes under context/.

Invoked from the PR governance workflow after the caller has computed an honest
merge-base. Pass ``--base`` as that merge-base and ``--head`` as the PR head;
this module does not recompute merge-base.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Sequence

ARMED_PREFIXES: tuple[str, ...] = (
    "llmwiki/",
    "integrations/",
    "tests/",
    ".github/workflows/",
    "docs/maintainers/",
    "docs/reference/",
)

CONTEXT_PREFIX = "context/"

_FAILURE_LINES: tuple[str, ...] = (
    "Product-related paths changed without updating AWOS working notes under context/.",
    "This repository uses a spec-first AWOS flow: changes that arm this gate must also update the written plan/notes so maintainers and agents stay aligned.",
    "Armed path prefixes: llmwiki/, integrations/, tests/, .github/workflows/, docs/maintainers/, docs/reference/.",
    "How to fix: run the feature or fix flow (so context/ is updated with the change), or edit the owning notes under context/ to match what this PR changes.",
    "Any file under context/ is enough — the gate does not require a specific filename.",
)


def is_armed_path(path: str) -> bool:
    """Return True if *path* falls under an armed prefix."""
    normalized = path.replace("\\", "/")
    return any(normalized.startswith(prefix) for prefix in ARMED_PREFIXES)


def is_context_path(path: str) -> bool:
    """Return True if *path* is under the AWOS notes tree (context/)."""
    return path.replace("\\", "/").startswith(CONTEXT_PREFIX)


def has_armed_change(changed_paths: Sequence[str]) -> bool:
    """Return True if any changed path arms the gate."""
    return any(is_armed_path(p) for p in changed_paths)


def has_context_change(changed_paths: Sequence[str]) -> bool:
    """Return True if any changed path satisfies the gate via context/."""
    return any(is_context_path(p) for p in changed_paths)


def gate_passes(changed_paths: Sequence[str]) -> bool:
    """Decide pass/fail from a list of changed repo-relative paths.

    Pass when nothing armed changed, or when any context/ path also changed.
    Fail only when at least one armed path changed and no context/ path did.
    """
    if not has_armed_change(changed_paths):
        return True
    return has_context_change(changed_paths)


def failure_message_lines() -> list[str]:
    """Return the multi-line failure explanation (without ::error:: prefixes)."""
    return list(_FAILURE_LINES)


def print_failure(stream=None) -> None:
    """Emit GitHub Actions ``::error::`` lines for the failure explanation."""
    out = sys.stdout if stream is None else stream
    for line in failure_message_lines():
        print(f"::error::{line}", file=out)


def git_changed_paths(base: str, head: str, *, cwd: str | None = None) -> list[str]:
    """List paths changed between *base* and *head* via ``git diff --name-only``."""
    proc = subprocess.run(
        ["git", "diff", "--name-only", base, head],
        capture_output=True,
        text=True,
        check=True,
        cwd=cwd,
    )
    return [line for line in proc.stdout.splitlines() if line]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Fail when armed product paths change without a context/ AWOS notes update. "
            "Pass the merge-base as --base and the PR head as --head."
        ),
    )
    parser.add_argument(
        "--base",
        required=True,
        help="Git SHA for the left side of the diff (caller supplies merge-base).",
    )
    parser.add_argument(
        "--head",
        required=True,
        help="Git SHA for the PR head (right side of the diff).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        changed = git_changed_paths(args.base, args.head)
    except subprocess.CalledProcessError:
        print(
            f"::error::could not diff {args.base}..{args.head}; "
            "the gate cannot judge this PR",
            file=sys.stdout,
        )
        return 1
    if gate_passes(changed):
        return 0
    print_failure()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
