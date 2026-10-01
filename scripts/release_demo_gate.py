#!/usr/bin/env python3
"""Release-day mechanical gate for the committed demo vault (#240).

Maintainer-only. First refuses a stale demo: product docs changed since
``demo/.demo-source-rev`` (a non-empty ``refresh_demo.py`` plan) or demo
sessions without a source page. Then regenerates demo MCP usage (unless
skipped), builds the demo site to a local out dir with portable
``--local-root``, prints a concrete ``file://`` URL for human review, runs the
demo-content tests and ``llmwiki lint`` failing on errors and warnings.

Real (non-dry-run) mode shells out to sibling scripts / ``python3 -m llmwiki`` /
pytest. Run from the repository root so relative ``demo/`` resolves.

    python3 scripts/release_demo_gate.py --dry-run   # --today from demo/.demo-sessions-date
    python3 scripts/release_demo_gate.py --today 2026-09-14 --dry-run
    python3 scripts/release_demo_gate.py --today 2026-09-14
    python3 scripts/release_demo_gate.py --today 2026-09-14 --skip-usage --out /tmp/demo-site
    python3 scripts/release_demo_gate.py --today 2026-09-14 --allow-stale-demo  # version-only cut

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
DEMO = REPO_ROOT / "demo"
USAGE_SCRIPT = REPO_ROOT / "scripts" / "generate_demo_usage.py"
REFRESH_SCRIPT = REPO_ROOT / "scripts" / "refresh_demo.py"
SESSIONS_DATE_FILE = DEMO / ".demo-sessions-date"
#: Tests that assert on the committed demo's content. Each has failed after a
#: refresh while build and lint stayed green.
DEMO_CONTENT_TESTS = [
    "tests/test_case_insensitive_paths.py",
    "tests/test_search_acceptance.py",
    "tests/test_248_acceptance.py",
    "tests/test_refresh_demo.py",
    "tests/test_privacy_username.py",
]


def _file_url(out: Path) -> str:
    """Return a copy-pasteable file:// URL for the built index."""
    return (out / "index.html").resolve().as_uri()


def _run(argv: list[str]) -> int:
    """Run argv with cwd=repo root; stream output; return exit code."""
    proc = subprocess.run(argv, cwd=REPO_ROOT, check=False)
    return int(proc.returncode)


def _load_script(name: str, path: Path):
    """Import a sibling script from its path (``scripts/`` is not a package)."""
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_generate_demo_usage():
    """Import ``generate_demo_usage`` from its script path (not a package)."""
    return _load_script("generate_demo_usage", USAGE_SCRIPT)


def stale_demo_docs() -> list[str]:
    """``refresh_demo.py``'s plan against ``HEAD``, one ``"<action> <path>"`` per step.

    Non-empty means product docs changed after the demo's last refresh — for
    example a docs PR merged after the refresh PR — so the demo would ship
    the old text.
    """
    refresh = _load_script("refresh_demo", REFRESH_SCRIPT)
    diff, status = refresh.collect_git_output(REPO_ROOT, refresh.read_source_rev(REPO_ROOT))
    plan = refresh.expand_removes(refresh.plan_from_git(diff, status), DEMO / "raw" / "docs")
    return [f"{action} {path}" for action, path, _slug in plan]


def pending_demo_sessions() -> list[str]:
    """Non-headless demo sessions no ``wiki/sources`` page claims via ``source_file:``.

    Coverage is read off the pages, not synth state: state records file mtimes,
    so after any checkout every committed source looks changed. Headless
    sessions stay raw-only by design (#180). Stem heuristics from the docs
    refresh helper are intentionally not used — session filenames and page
    stems diverge after re-dating.
    """
    sessions = DEMO / "raw" / "sessions"
    sources = DEMO / "wiki" / "sources"
    claimed: set[str] = set()
    if sources.is_dir():
        for page in sources.rglob("*.md"):
            head = page.read_text(encoding="utf-8", errors="replace")[:1200]
            for line in head.splitlines():
                if line.startswith("source_file:"):
                    claimed.add(line.split(":", 1)[1].strip())
                    break
    missing: list[str] = []
    for raw in sorted(sessions.rglob("*.md")):
        head = raw.read_text(encoding="utf-8", errors="replace")[:4000]
        if "\nis_headless: true" in head:
            continue
        rel = raw.relative_to(DEMO).as_posix()
        if rel not in claimed:
            missing.append(rel)
    return missing


def _freshness_failures() -> list[str]:
    """Human-readable reasons the committed demo is not current."""
    problems: list[str] = []
    docs = stale_demo_docs()
    if docs:
        problems.append(
            f"demo docs are stale: refresh_demo.py would run {len(docs)} step(s) — "
            "run it (and synth the added docs) before the cut:"
        )
        problems.extend(f"    {step}" for step in docs)
    sessions = pending_demo_sessions()
    if sessions:
        problems.append(f"{len(sessions)} demo session(s) have no source page — synth them:")
        problems.extend(f"    {rel}" for rel in sessions)
    return problems


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
    allow_stale_demo: bool = False,
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
        "--fail-on-warnings",
    ]
    pytest_argv = [python, "-m", "pytest", *DEMO_CONTENT_TESTS, "-q"]

    if dry_run:
        print("dry-run — planned steps (nothing written / no build):")
        if allow_stale_demo:
            print("  skip demo freshness checks (--allow-stale-demo)")
        else:
            print("  check demo docs match HEAD and every demo session has a source page")
        if skip_usage:
            print("  skip usage regen (--skip-usage)")
        else:
            print(f"  generate_demo_usage --today {today}")
        print(f"  {' '.join(build_argv)}")
        print(f"  {' '.join(pytest_argv)}")
        print(f"  {' '.join(lint_argv)}")
        _print_review_hints(out)
        return 0

    if allow_stale_demo:
        print("==> skip demo freshness checks (--allow-stale-demo)")
    else:
        print("==> demo freshness")
        problems = _freshness_failures()
        if problems:
            print("\n".join(problems), file=sys.stderr)
            return 1

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
        metavar="YYYY-MM-DD",
        help=(
            "Release day forwarded to generate_demo_usage (default: the date in "
            "demo/.demo-sessions-date; must match it when both are set)"
        ),
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
        "--allow-stale-demo",
        action="store_true",
        help=(
            "Skip the stale-docs and pending-session checks — only for a cut "
            "whose demo refresh the human explicitly opted out of"
        ),
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        metavar="DIR",
        help=f"Build output directory (default: {DEFAULT_OUT})",
    )
    return ap


def resolve_today(given: str | None) -> str:
    """The release day: the date the demo sessions were generated with.

    ``--today`` must match it when both exist — a cut that crosses midnight
    keeps one date, since a new one re-dates every session and needs a full
    session re-synth. Exit 2 when neither is available or they disagree.
    """
    recorded = (
        SESSIONS_DATE_FILE.read_text(encoding="utf-8").strip()
        if SESSIONS_DATE_FILE.is_file() else None
    )
    if given and recorded and given != recorded:
        print(
            f"error: --today {given} differs from the date the demo sessions were "
            f"generated with ({recorded}, {SESSIONS_DATE_FILE.relative_to(REPO_ROOT)}). "
            "Keep one release day per cut, or regenerate the sessions for the new date.",
            file=sys.stderr,
        )
        raise SystemExit(2)
    today = given or recorded
    if not today:
        print(
            "error: pass --today YYYY-MM-DD (no demo/.demo-sessions-date recorded yet)",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return today


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return run_gate(
        today=resolve_today(args.today),
        out=args.out,
        dry_run=args.dry_run,
        skip_usage=args.skip_usage,
        allow_stale_demo=args.allow_stale_demo,
    )


if __name__ == "__main__":
    raise SystemExit(main())
