#!/usr/bin/env python3
"""Refresh the demo vault from git-detected product documentation changes.

Maintainer-only. Never shipped, never referenced by the CLI, never run in CI.
Requires a git working copy of this repository (not a release archive) and a
reachable synthesis backend.

On a release cut, the ``/release`` skill defaults to running ``--dry-run`` (and a
real refresh when the plan is non-empty) **before** tagging so Pages does not
republish a docs-stale demo vault — skip only on an explicit human opt-out.
Session dates are a separate step — see ``scripts/generate_demo_sessions.py``
and ``docs/maintainers/RELEASE_PROCESS.md`` (#225). This script only plans
product-doc changes under ``docs/``.

Run from the repository root:

    python3 scripts/refresh_demo.py --dry-run
    python3 scripts/refresh_demo.py
    python3 scripts/refresh_demo.py --force
    python3 scripts/refresh_demo.py --base HEAD~5
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

type PlanItem = tuple[str, str, str]

DOCS_PREFIX = "docs/"
MAINTAINERS_PREFIX = "docs/maintainers/"
SOURCE_REV_REL = Path("demo") / ".demo-source-rev"
#: Written when a refresh starts mutating ``demo/``; cleared when the pin
#: advances. ``--resume`` requires this — porcelain dirt is not proof a
#: refresh ran, and a checkpoint-committed raw tree has a clean porcelain.
REFRESH_PENDING_REL = Path("demo") / ".demo-refresh-pending"
DEMO_VAULT_REL = Path("demo")
DEMO_SITE_REL = Path("demo") / "site"
LOCAL_ROOT = "/home/user"

_SLUG_UNSAFE = re.compile(r"[^a-z0-9]+")


def slug_for(path: str) -> str:
    """Stable slug from a product-doc path, unique across ``docs/`` subfolders."""
    posix = _posix(path)
    rest = posix[len(DOCS_PREFIX) :] if posix.startswith(DOCS_PREFIX) else posix
    if rest.endswith(".md"):
        rest = rest[: -len(".md")]
    return _SLUG_UNSAFE.sub("-", rest.lower()).strip("-") or "untitled"


def is_product_doc(path: str) -> bool:
    """True for user-facing markdown under ``docs/``, excluding maintainer docs.

    Change detection is scoped to ``docs/`` (functional-spec R3, technical
    Stage B1: ``git diff --name-status <rev> HEAD -- docs/``). ``docs/maintainers/``
    is contributor tooling, not the product corpus the demo summarises (R2).
    """
    posix = _posix(path)
    if not posix.startswith(DOCS_PREFIX):
        return False
    if posix == "docs/maintainers" or posix.startswith(MAINTAINERS_PREFIX):
        return False
    return posix.endswith(".md")


def plan_from_git(diff_output: str, status_output: str) -> list[PlanItem]:
    """Build an ordered ``(action, path, slug)`` plan from git text.

    Pure: no filesystem or vault access. ``diff_output`` is ``git diff
    --name-status``; ``status_output`` is ``git status --porcelain``. Uncommitted
    edits overlay committed changes and de-duplicate by path.
    """
    changes = _parse_name_status(diff_output)
    for path, change in _parse_porcelain(status_output).items():
        merged = _merge_change(changes.get(path), change)
        if merged is None:
            changes.pop(path, None)
        else:
            changes[path] = merged

    plan: list[PlanItem] = []
    for path in sorted(changes):
        letter, old_path = changes[path]
        if letter == "A":
            plan.append(("add", path, slug_for(path)))
        elif letter == "D":
            plan.append(("remove", path, slug_for(path)))
        elif letter in {"M", "R"}:
            # Remove first, then add. Re-adding an ingested document lands a
            # second snapshot under a drifted slug and leaves the original,
            # breaking inbound links. Removing first preserves the original slug.
            removed = old_path if letter == "R" and old_path else path
            plan.append(("remove", removed, slug_for(removed)))
            plan.append(("add", path, slug_for(path)))
    return plan


def format_plan(plan: list[PlanItem]) -> str:
    if not plan:
        return "plan: (no changes)"
    lines = [f"plan: {len(plan)} action(s)"]
    width = max(len(action) for action, _path, _slug in plan)
    for action, path, slug in plan:
        lines.append(f"  {action:<{width}}  {path}  ({slug})")
    return "\n".join(lines)


_SOURCE_LINE = re.compile(r'^source:\s*["\']?([^"\'\n]+?)["\']?\s*$', re.MULTILINE)


def doc_dirs_by_source(docs_dir: Path) -> dict[str, set[str]]:
    """Map each ``source:`` product-doc path to the ``raw/docs/`` dirs holding it.

    A doc can sit under more than one dir: the #143 seed wrote title-derived
    dirs, while this script adds under ``slug_for(path)``. Both copies carry
    the same ``source:``, which is the only reliable identity.
    """
    found: dict[str, set[str]] = {}
    if not docs_dir.is_dir():
        return found
    for raw in sorted(docs_dir.rglob("*.md")):
        head = raw.read_text(encoding="utf-8", errors="replace")[:2000]
        m = _SOURCE_LINE.search(head)
        if m:
            rel = raw.relative_to(docs_dir)
            found.setdefault(_posix(m.group(1)), set()).add(rel.parts[0])
    return found


def expand_removes(plan: list[PlanItem], docs_dir: Path) -> list[PlanItem]:
    """Follow every ``remove`` with removes for other dirs holding the same doc.

    ``slug_for(path)`` names only the dir this script writes; a copy of the
    same ``source:`` under any other dir would otherwise survive the refresh
    and ship next to the re-added doc as a duplicate (#298).
    """
    by_source = doc_dirs_by_source(docs_dir)
    out: list[PlanItem] = []
    for action, path, slug in plan:
        out.append((action, path, slug))
        if action == "remove":
            for other in sorted(by_source.get(_posix(path), set()) - {slug}):
                out.append(("remove", path, other))
    return out


def added_doc_slugs(plan: list[PlanItem]) -> list[str]:
    """Unique ``raw/docs/<slug>/`` project slugs this plan adds (sorted)."""
    return sorted({slug for action, _path, slug in plan if action == "add"})


def synth_argv_for_added_docs(vault: Path, plan: list[PlanItem]) -> list[str] | None:
    """Build a path-scoped ``synth --docs-only`` argv for docs this plan added.

    Returns ``None`` when the plan has no ``add`` actions, or when no markdown
    landed under ``vault/raw/docs/<slug>/`` yet (caller should treat that as
    skip-synth, not vault-wide fallback). Each ``--path`` is vault-relative so
    ``llmwiki synth`` resolves it under ``--vault``.
    """
    add_slugs = added_doc_slugs(plan)
    if not add_slugs:
        return None
    rel_paths: list[str] = []
    for slug in add_slugs:
        docs_dir = vault / "raw" / "docs" / slug
        if not docs_dir.is_dir():
            continue
        for path in sorted(docs_dir.rglob("*.md")):
            rel_paths.append(path.relative_to(vault).as_posix())
    if not rel_paths:
        return None
    argv = ["synth", "--vault", str(vault), "--docs-only"]
    for rel in rel_paths:
        argv.extend(["--path", rel])
    return argv


def wiki_page_covers_raw(wiki_dir: Path, raw: Path, vault: Path) -> bool:
    """True when a page under ``wiki/sources/<slug>/`` covers this raw doc.

    Stem match covers docs synth naming; ``source_file:`` is authoritative when
    present. Session coverage in the release gate uses ``source_file:`` only.
    """
    if not wiki_dir.is_dir():
        return False
    rel = raw.relative_to(vault).as_posix()
    stem = raw.stem
    for wiki in wiki_dir.glob("*.md"):
        if wiki.stem == stem or wiki.stem.endswith(f"-{stem}"):
            return True
        head = wiki.read_text(encoding="utf-8", errors="replace")[:1200]
        if f"source_file: {rel}" in head:
            return True
    return False


def missing_wiki_for_doc_slugs(vault: Path, slugs: list[str]) -> list[str]:
    """Return gap messages for raw docs under each slug that lack a wiki source page.

    Used after a path-scoped docs synth (and by ``--verify-slugs``) so a partial
    or rate-limited synth cannot look “done” just because lint/build still pass.
    Does **not** require clearing the vault-wide historical backlog — only the
    slugs this cut refreshed.
    """
    gaps: list[str] = []
    for slug in slugs:
        raw_dir = vault / "raw" / "docs" / slug
        wiki_dir = vault / "wiki" / "sources" / slug
        if not raw_dir.is_dir():
            continue
        for raw in sorted(raw_dir.rglob("*.md")):
            if not raw.is_file():
                continue
            if not wiki_page_covers_raw(wiki_dir, raw, vault):
                gaps.append(raw.relative_to(vault).as_posix())
    return gaps


def git_toplevel(cwd: Path | None = None) -> Path:
    """Return the working-copy root, or raise ``RefreshError`` if there isn't one."""
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise RefreshError(
            "git is not available; this command needs a git working copy of the "
            "repository and cannot run from a release archive"
        ) from exc
    if proc.returncode != 0:
        raise RefreshError(
            "not a git working copy; this command reads change from version "
            "history and cannot run from a release archive"
        )
    return Path(proc.stdout.strip())


def read_source_rev(repo: Path) -> str:
    path = repo / SOURCE_REV_REL
    if not path.is_file():
        raise RefreshError(
            f"{SOURCE_REV_REL.as_posix()} is missing — pass --base <rev> or "
            "--force for a first run"
        )
    rev = path.read_text(encoding="utf-8").strip()
    if not rev:
        raise RefreshError(f"{SOURCE_REV_REL.as_posix()} is empty — pass --base <rev>")
    return rev


def collect_git_output(repo: Path, base: str) -> tuple[str, str]:
    diff = _git(
        repo,
        ["diff", "--name-status", "-M", base, "HEAD", "--", "docs/"],
    )
    status = _git(repo, ["status", "--porcelain", "--", "docs/"])
    return diff, status


def force_diff(repo: Path) -> str:
    """Synthetic ``name-status`` treating every product doc as modified."""
    docs = _list_product_docs(repo)
    return "\n".join(f"M\t{path}" for path in docs)


def run_refresh(
    repo: Path,
    *,
    dry_run: bool = False,
    force: bool = False,
    base: str | None = None,
    python: str | None = None,
    resume: bool = False,
) -> int:
    """Drive add/remove/synth/build/lint against ``demo/``. Return a process exit code."""
    exe = python or sys.executable
    vault = repo / DEMO_VAULT_REL

    try:
        if force:
            plan = plan_from_git(force_diff(repo), "")
        else:
            recorded = base if base is not None else read_source_rev(repo)
            diff, status = collect_git_output(repo, recorded)
            plan = plan_from_git(diff, status)
    except RefreshError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    plan = expand_removes(plan, vault / "raw" / "docs")

    print(format_plan(plan))
    if resume:
        return _resume(repo, exe, vault, plan, dry_run=dry_run)
    if dry_run:
        print("dry-run — nothing written")
        return 0

    if not plan:
        _write_source_rev(repo)
        return 0

    needs_synth = any(action == "add" for action, _path, _slug in plan)
    if needs_synth:
        check = _run_llmwiki(exe, repo, ["synth", "--check"])
        if check.returncode != 0:
            print(
                "error: no synthesis backend is reachable — `llmwiki synth --check` failed.\n"
                "Set synthesis.backend in config.json to claude or ollama and confirm it is running.\n"
                "This command is a local maintainer tool; it cannot refresh the demo from a "
                "release archive and never runs in CI.\n"
                "Pass --dry-run to print the plan without calling a backend.",
                file=sys.stderr,
            )
            return 1

    _write_refresh_pending(repo)

    # The plan lists remove before add for every modified/renamed doc.
    # That ordering is mandatory: re-adding an ingested document lands a second
    # snapshot under a drifted slug and leaves the original, breaking inbound links.
    for action, path, slug in plan:
        if action == "remove":
            proc = _run_llmwiki(
                exe, repo, ["remove", slug, "--vault", str(vault), "--yes"]
            )
        elif action == "add":
            # Repo-relative, run from the repo root: `add` records the path it
            # is given in the vault's queue, and demo/ is published — an
            # absolute path would ship the maintainer's home directory.
            proc = _run_llmwiki(
                exe,
                repo,
                [
                    "add",
                    path,
                    "--vault",
                    str(vault),
                    "--no-build",
                    "--project",
                    slug,
                ],
            )
        else:
            print(f"error: unknown action {action!r}", file=sys.stderr)
            return 2
        if proc.returncode != 0:
            print(f"error: llmwiki {action} failed (exit {proc.returncode})", file=sys.stderr)
            return proc.returncode

    # Synth only the docs this plan added — never a vault-wide --docs-only pass
    # (that re-queues every pending raw/docs page and burns rate limits).
    return _finish(repo, exe, vault, plan, synth_argv_for_added_docs(vault, plan))


def _resume(repo: Path, exe: str, vault: Path, plan: list[PlanItem], *, dry_run: bool) -> int:
    """Finish a refresh whose synth was interrupted, without redoing its removes.

    The pin only advances once every plan-added doc has a page, so after an
    interruption the same plan is still pending and its removes and adds have
    already run. Re-running the refresh would remove and re-add every doc
    again; this synthesizes only the plan-added raw docs still lacking a page,
    in one run, then does the rest of a normal refresh.

    Proof the refresh started is ``demo/.demo-refresh-pending`` (written before
    the first remove/add), not porcelain — dirt can exist without a refresh,
    and a checkpoint-committed raw tree is clean porcelain.
    """
    pending = repo / REFRESH_PENDING_REL
    if not pending.is_file():
        print(
            "error: no in-progress refresh "
            f"({REFRESH_PENDING_REL.as_posix()} missing) — run without --resume",
            file=sys.stderr,
        )
        return 1
    unadded = [
        slug for slug in added_doc_slugs(plan)
        if not (vault / "raw" / "docs" / slug).is_dir()
    ]
    if unadded:
        print(
            "error: the refresh stopped before adding "
            f"{', '.join(unadded)} — --resume only finishes an interrupted synth; "
            "run the refresh again",
            file=sys.stderr,
        )
        return 1
    gaps = missing_wiki_for_doc_slugs(vault, added_doc_slugs(plan))
    print(f"resume: {len(gaps)} plan-added raw doc(s) still lack a wiki page")
    for gap in gaps:
        print(f"  {gap}")
    if dry_run:
        print("dry-run — nothing written")
        return 0
    synth_argv = None
    if gaps:
        synth_argv = ["synth", "--vault", str(vault), "--docs-only"]
        for gap in gaps:
            synth_argv.extend(["--path", gap])
    return _finish(repo, exe, vault, plan, synth_argv)


def _finish(
    repo: Path, exe: str, vault: Path, plan: list[PlanItem], synth_argv: list[str] | None,
) -> int:
    """Synth, build, require coverage for every plan-added doc, lint, advance the pin."""
    follow_ups: list[list[str]] = []
    if synth_argv is not None:
        follow_ups.append(synth_argv)
    follow_ups.append(
        ["build", "--vault", str(vault), "--out", str(repo / DEMO_SITE_REL),
         "--local-root", LOCAL_ROOT],
    )
    for argv in follow_ups:
        proc = _run_llmwiki(exe, repo, argv)
        if proc.returncode != 0:
            print(f"error: llmwiki {argv[0]} failed (exit {proc.returncode})", file=sys.stderr)
            return proc.returncode

    gaps = missing_wiki_for_doc_slugs(vault, added_doc_slugs(plan))
    if gaps:
        print(
            "error: docs refresh synth is incomplete — every raw doc this plan "
            "added needs a matching wiki/sources page before the pin advances.\n"
            "Lint/build can still pass with gaps; do not treat that as done.\n"
            "Missing coverage:",
            file=sys.stderr,
        )
        for gap in gaps:
            print(f"  {gap}", file=sys.stderr)
        print(
            "Re-run path-scoped synth for those slugs, or pass "
            "`--verify-slugs <slug>,…` after a manual synth to re-check.",
            file=sys.stderr,
        )
        return 1

    lint = _run_llmwiki(exe, repo, ["lint", "--vault", str(vault)])
    print("lint report:")
    if lint.stdout:
        print(lint.stdout, end="" if lint.stdout.endswith("\n") else "\n")
    if lint.stderr:
        print(lint.stderr, end="" if lint.stderr.endswith("\n") else "\n", file=sys.stderr)

    _write_source_rev(repo)
    return 0


def verify_doc_slugs(repo: Path, slugs: list[str]) -> int:
    """Exit 0 when each slug's raw docs have wiki coverage; else print gaps and exit 1."""
    vault = repo / DEMO_VAULT_REL
    clean = [s.strip() for s in slugs if s.strip()]
    if not clean:
        print("error: --verify-slugs needs at least one slug", file=sys.stderr)
        return 2
    gaps = missing_wiki_for_doc_slugs(vault, clean)
    if gaps:
        print(
            "error: demo docs synth incomplete for requested slugs "
            f"({len(gaps)} raw file(s) without wiki/sources coverage):",
            file=sys.stderr,
        )
        for gap in gaps:
            print(f"  {gap}", file=sys.stderr)
        return 1
    print(f"ok: wiki coverage for {len(clean)} slug(s)")
    return 0


def main(argv: list[str] | None = None, *, cwd: Path | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--dry-run", action="store_true", help="Print the plan, touch nothing")
    ap.add_argument(
        "--force",
        action="store_true",
        help="Treat every product doc under docs/ as changed",
    )
    ap.add_argument(
        "--base",
        metavar="REV",
        default=None,
        help="Override the revision in demo/.demo-source-rev",
    )
    ap.add_argument(
        "--resume",
        action="store_true",
        help=(
            "Finish a refresh whose synth was interrupted (requires "
            "demo/.demo-refresh-pending): synth only the plan-added docs "
            "still lacking a page, then lint and advance the pin"
        ),
    )
    ap.add_argument(
        "--verify-slugs",
        metavar="SLUGS",
        default=None,
        help=(
            "Comma-separated raw/docs project slugs; exit 1 if any lack "
            "wiki/sources coverage (local release gate — does not run a refresh)"
        ),
    )
    args = ap.parse_args(argv)

    try:
        repo = git_toplevel(cwd)
    except RefreshError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.verify_slugs is not None:
        return verify_doc_slugs(repo, args.verify_slugs.split(","))
    return run_refresh(
        repo, dry_run=args.dry_run, force=args.force, base=args.base, resume=args.resume,
    )


class RefreshError(Exception):
    """User-facing failure before any vault write."""


def _posix(path: str) -> str:
    return path.replace("\\", "/").lstrip("./")


def _parse_name_status(text: str) -> dict[str, tuple[str, str | None]]:
    """Parse ``git diff --name-status`` into ``{new_path: (letter, old_path)}``."""
    out: dict[str, tuple[str, str | None]] = {}
    for raw in text.splitlines():
        line = raw.strip("\n")
        if not line.strip():
            continue
        parts = line.split("\t")
        letter = parts[0][:1]
        if letter in {"R", "C"} and len(parts) >= 3:
            old_path, new_path = _posix(parts[1]), _posix(parts[2])
            if letter == "C":
                if is_product_doc(new_path):
                    out[new_path] = ("A", None)
                continue
            if is_product_doc(old_path) or is_product_doc(new_path):
                if is_product_doc(new_path):
                    out[new_path] = ("R", old_path)
                elif is_product_doc(old_path):
                    out[old_path] = ("D", None)
            continue
        if len(parts) < 2:
            continue
        path = _posix(parts[1])
        if not is_product_doc(path):
            continue
        if letter in {"A", "M", "D", "T"}:
            out[path] = ("M" if letter == "T" else letter, None)
    return out


def _parse_porcelain(text: str) -> dict[str, tuple[str, str | None]]:
    """Parse ``git status --porcelain`` into the same shape as name-status."""
    out: dict[str, tuple[str, str | None]] = {}
    for raw in text.splitlines():
        line = raw.rstrip("\n")
        if len(line) < 4:
            continue
        xy, rest = line[:2], line[3:]
        old_path: str | None = None
        path = rest
        if " -> " in rest:
            left, right = rest.split(" -> ", 1)
            old_path, path = _unquote(left), _unquote(right)
        else:
            path = _unquote(path)
        path = _posix(path)
        if old_path:
            old_path = _posix(old_path)
        letter = _porcelain_letter(xy)
        if letter is None:
            continue
        if letter == "R":
            if old_path and (is_product_doc(old_path) or is_product_doc(path)):
                if is_product_doc(path):
                    out[path] = ("R", old_path)
                elif is_product_doc(old_path):
                    out[old_path] = ("D", None)
            continue
        if not is_product_doc(path):
            continue
        out[path] = (letter, None)
    return out


def _porcelain_letter(xy: str) -> str | None:
    if xy == "??":
        return "A"
    if "R" in xy:
        return "R"
    if "D" in xy:
        return "D"
    if "A" in xy:
        return "A"
    if "M" in xy or "T" in xy:
        return "M"
    return None


def _merge_change(
    committed: tuple[str, str | None] | None,
    uncommitted: tuple[str, str | None],
) -> tuple[str, str | None] | None:
    """Overlay a working-tree change onto a committed one for the same path.

    Returns None when the net result is no change (added since base, then
    deleted in the working tree before refresh).
    """
    if committed is None:
        return uncommitted
    c_letter, c_old = committed
    u_letter, u_old = uncommitted
    if u_letter == "D":
        if c_letter == "A":
            return None
        return ("D", None)
    if c_letter == "A":
        return ("A", None)
    if c_letter == "R" and u_letter == "M":
        return ("R", c_old)
    if u_letter == "A" and c_letter == "D":
        return ("A", None)
    if u_letter == "R":
        return (u_letter, u_old or c_old)
    return (u_letter, u_old or c_old)


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        return value[1:-1].replace('\\"', '"')
    return value


def _git(repo: Path, args: list[str]) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip() or f"git {' '.join(args)} failed"
        raise RefreshError(err)
    return proc.stdout


def _list_product_docs(repo: Path) -> list[str]:
    listed = _git(repo, ["ls-files", "-co", "--exclude-standard", "--", "docs/"])
    docs = [path for line in listed.splitlines() if is_product_doc(path := _posix(line))]
    return sorted(set(docs))


def _write_refresh_pending(repo: Path) -> None:
    """Mark that remove/add has started; ``--resume`` requires this file."""
    dest = repo / REFRESH_PENDING_REL
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("1\n", encoding="utf-8")
    print(f"wrote {REFRESH_PENDING_REL.as_posix()}")


def _clear_refresh_pending(repo: Path) -> None:
    pending = repo / REFRESH_PENDING_REL
    if pending.is_file():
        pending.unlink()


def _write_source_rev(repo: Path) -> None:
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RefreshError("could not resolve HEAD")
    sha = proc.stdout.strip()
    dest = repo / SOURCE_REV_REL
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not (dest.is_file() and dest.read_text(encoding="utf-8").strip() == sha):
        dest.write_text(sha + "\n", encoding="utf-8")
        print(f"recorded {sha} in {SOURCE_REV_REL.as_posix()}")
    _clear_refresh_pending(repo)


def _run_llmwiki(python: str, repo: Path, argv: list[str]) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        [python, "-m", "llmwiki", *argv],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.stdout:
        print(proc.stdout, end="" if proc.stdout.endswith("\n") else "\n")
    if proc.stderr:
        print(proc.stderr, end="" if proc.stderr.endswith("\n") else "\n", file=sys.stderr)
    return proc


if __name__ == "__main__":
    raise SystemExit(main())
