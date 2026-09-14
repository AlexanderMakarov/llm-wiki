#!/usr/bin/env python3
"""Release-day mechanical gate for the committed demo vault (#240).

Maintainer-only. Regenerates demo MCP usage (unless skipped), builds the demo
site to a local out dir with portable ``--local-root``, prints a concrete
``file://`` URL for human review, then runs the case-fold pytest and
``llmwiki lint --fail-on-errors``.

Real (non-dry-run) mode shells out to sibling scripts / ``python3 -m llmwiki`` /
pytest. Run from the repository root so relative ``demo/`` resolves.

    python3 scripts/release_demo_gate.py --today 2026-09-14 --dry-run
    python3 scripts/release_demo_gate.py --today 2026-09-14
    python3 scripts/release_demo_gate.py --today 2026-09-14 --skip-usage --out /tmp/demo-site

Exit 0 only when every mechanical step succeeds. Non-zero means the release
cut must not proceed to tag push. Does not bump version, edit CHANGELOG, or
touch git.
"""

from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = Path("/tmp/demo-site")
LOCAL_ROOT = "/home/user"
USAGE_SCRIPT = REPO_ROOT / "scripts" / "generate_demo_usage.py"
CASE_FOLD_TEST = "tests/test_case_insensitive_paths.py"


def _file_url(out: Path) -> str:
    """Return a copy-pasteable file:// URL for the built index."""
    return (out / "index.html").resolve().as_uri()


def _run(argv: list[str]) -> int:
    """Run argv with cwd=repo root; stream output; return exit code."""
    proc = subprocess.run(argv, cwd=REPO_ROOT, check=False)
    return int(proc.returncode)


def _load_generate_demo_usage():
    """Import ``generate_demo_usage`` from its script path (not a package)."""
    spec = importlib.util.spec_from_file_location(
        "generate_demo_usage", USAGE_SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {USAGE_SCRIPT}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run_generate_usage(today: str) -> int:
    """Call ``generate_demo_usage.main`` with ``--today`` (same Python)."""
    mod = _load_generate_demo_usage()
    saved = sys.argv
    try:
        sys.argv = [str(USAGE_SCRIPT), "--today", today]
        return int(mod.main())
    finally:
        sys.argv = saved


def _print_review_hints(out: Path) -> None:
    url = _file_url(out)
    print(f"\nReview: {url}")
    print(
        f"Optional local server: "
        f"python3 -m http.server --directory {out} 8000"
    )


def run_gate(
    *,
    today: str,
    out: Path,
    dry_run: bool = False,
    skip_usage: bool = False,
) -> int:
    """Execute or print the release demo gate steps. Return process exit code."""
    python = sys.executable
    build_argv = [
        python, "-m", "llmwiki", "build",
        "--vault", "demo",
        "--out", str(out),
        "--local-root", LOCAL_ROOT,
    ]
    lint_argv = [
        python, "-m", "llmwiki", "lint",
        "--vault", "demo",
        "--fail-on-errors",
    ]
    pytest_argv = [python, "-m", "pytest", CASE_FOLD_TEST, "-q"]

    if dry_run:
        print("dry-run — planned steps (nothing written / no build):")
        if skip_usage:
            print("  skip usage regen (--skip-usage)")
        else:
            print(f"  generate_demo_usage --today {today}")
        print(f"  {' '.join(build_argv)}")
        print(f"  {' '.join(pytest_argv)}")
        print(f"  {' '.join(lint_argv)}")
        _print_review_hints(out)
        return 0

    if not skip_usage:
        print(f"==> generate_demo_usage --today {today}")
        code = _run_generate_usage(today)
        if code != 0:
            return code
    else:
        print("==> skip usage regen (--skip-usage)")

    print(f"==> {' '.join(build_argv)}")
    code = _run(build_argv)
    if code != 0:
        return code

    _print_review_hints(out)

    print(f"==> {' '.join(pytest_argv)}")
    code = _run(pytest_argv)
    if code != 0:
        return code

    print(f"==> {' '.join(lint_argv)}")
    code = _run(lint_argv)
    if code != 0:
        return code

    print("\ngate passed (mechanical). Human must still visually OK the demo.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument(
        "--today",
        required=True,
        metavar="YYYY-MM-DD",
        help="Anchor date forwarded to generate_demo_usage (required)",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned steps and file:// URL; write/build nothing",
    )
    ap.add_argument(
        "--skip-usage",
        action="store_true",
        help="Skip demo/usage regeneration (version-only cuts)",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        metavar="DIR",
        help=f"Build output directory (default: {DEFAULT_OUT})",
    )
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return run_gate(
        today=args.today,
        out=args.out,
        dry_run=args.dry_run,
        skip_usage=args.skip_usage,
    )


if __name__ == "__main__":
    raise SystemExit(main())
