"""Clean up links to discarded candidates and slash-nested stubs (#282).

Offline one-time migration for vaults whose candidates were discarded before
``candidates discard`` started rewriting links. For every archived candidate
that no live page answers to (see :func:`llmwiki.candidates.discarded_names`),
every ``[[link]]`` to its name outside ``wiki/archive/`` becomes plain text —
or, when the name is given in ``--redirect NAME=PAGE``, points at that
existing page, which records the name under ``## Aliases``. Both use the same
rewrite as ``candidates discard``. Every ``--redirect`` pair is checked before
the first write: a bad one stops the run with nothing changed, and a name a
live page already answers to is reported as skipped rather than dropped.

It also moves candidate stubs a ``/`` in their name filed into a subfolder
(``candidates/entities/A/B thing.md``) to the flat path
:func:`llmwiki.candidates.candidate_filename` gives them, never overwriting an
existing file.

No synthesis backend or network call; ``raw/`` is never written. A second run
changes nothing.

Usage::

    llmwiki migrate discarded-topic-links --vault /path/to/vault --dry-run
    llmwiki migrate discarded-topic-links --vault /path/to/vault \\
        --redirect "Old Name=ExistingPage"
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from llmwiki._frontmatter import parse_frontmatter
from llmwiki.candidates import (
    MIRRORED_SUBDIRS,
    archived_candidate_names,
    archived_candidate_source_count,
    candidate_filename,
    candidates_dir,
    discarded_names,
    find_live_page,
    record_redirect_alias,
    rewrite_links_to,
)
from llmwiki.wikilinks import norm_page_key


def parse_redirects(pairs: list[str]) -> dict[str, str]:
    """Parse ``NAME=PAGE`` strings into ``{NAME: PAGE}``.

    Splits on the last ``=`` so a name may itself contain one. Raises
    ``ValueError`` on a malformed pair.
    """
    redirects: dict[str, str] = {}
    for pair in pairs:
        name, sep, page = pair.rpartition("=")
        if not sep or not name.strip() or not page.strip():
            raise ValueError(f"--redirect expects NAME=PAGE, got {pair!r}")
        redirects[name.strip()] = page.strip()
    return redirects


def _flatten_nested_stubs(
    wiki: Path, report: dict[str, Any], *, dry_run: bool,
) -> None:
    """Move ``candidates/<kind>/<sub>/…/<x>.md`` to its flat sanitized path."""
    root = candidates_dir(wiki)
    for kind in MIRRORED_SUBDIRS:
        kind_dir = root / kind
        if not kind_dir.is_dir():
            continue
        for path in sorted(kind_dir.rglob("*.md")):
            if path.parent == kind_dir:
                continue
            try:
                meta, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError) as exc:
                report["errors"].append(f"{path.relative_to(wiki).as_posix()}: {exc}")
                continue
            name = str(meta.get("title") or "").strip() or (
                path.relative_to(kind_dir).with_suffix("").as_posix()
            )
            dest = kind_dir / candidate_filename(name)
            rel = path.relative_to(wiki).as_posix()
            dest_rel = dest.relative_to(wiki).as_posix()
            if dest.exists():
                report["conflicts"].append(f"{rel} -> {dest_rel} (already exists)")
                continue
            report["flattened"].append(f"{rel} -> {dest_rel}")
            if dry_run:
                continue
            path.rename(dest)
            parent = path.parent
            while parent != kind_dir and not any(parent.iterdir()):
                parent.rmdir()
                parent = parent.parent


def run_migration(
    *,
    vault: Path,
    dry_run: bool = False,
    redirects: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Unlink / redirect links to discarded candidates and flatten nested stubs.

    ``redirects`` maps a discarded candidate name to the existing live page its
    links should point at. Every pair is validated before anything is written,
    so a bad one leaves the vault untouched (``report["aborted"]``) instead of
    half-migrated. Dry-run computes the same report without writing. Never
    touches ``raw/``.
    """
    vault = Path(vault).expanduser().resolve()
    wiki = vault / "wiki"
    report: dict[str, Any] = {
        "vault": str(vault),
        "wiki_dir": str(wiki),
        "dry_run": dry_run,
        "unlinked": {},
        "redirected": {},
        "aliases_recorded": [],
        "changed_pages": [],
        "flattened": [],
        "conflicts": [],
        "skipped": [],
        "errors": [],
        "aborted": False,
        "changed": False,
    }
    if not wiki.is_dir():
        report["errors"].append(f"missing wiki dir: {wiki}")
        report["aborted"] = True
        return report

    errors: list[str] = report["errors"]
    archived = archived_candidate_names(wiki, errors=errors)
    discarded = discarded_names(wiki, errors=errors)
    targets: dict[str, str | None] = dict.fromkeys(discarded)
    redirect_pages: dict[str, str] = {}
    aliases_to_record: list[tuple[Path, str, int]] = []
    redirect_errors: list[str] = []
    for name, page_name in (redirects or {}).items():
        key = norm_page_key(name)
        if key not in archived:
            redirect_errors.append(
                f"--redirect {name!r}: no archived candidate by that name"
            )
            continue
        if key not in discarded:
            report["skipped"].append(
                f"--redirect {name!r}: a live page already answers to that name, "
                f"so its links resolve and no redirect was needed"
            )
            continue
        try:
            page = find_live_page(wiki, page_name)
        except (FileNotFoundError, ValueError) as exc:
            redirect_errors.append(f"--redirect {name!r}: {exc}")
            continue
        targets[key] = page.stem
        redirect_pages[key] = page.stem
        aliases_to_record.append(
            (page, discarded[key], archived_candidate_source_count(wiki, key))
        )
    if redirect_errors:
        # Nothing has been written yet: refuse the whole run rather than
        # migrate part of the vault and still exit non-zero.
        errors.extend(redirect_errors)
        report["aborted"] = True
        return report

    _flatten_nested_stubs(wiki, report, dry_run=dry_run)

    counts, pages = rewrite_links_to(wiki, targets, dry_run=dry_run, errors=errors)
    for page, name, source_count in aliases_to_record:
        if record_redirect_alias(
            page, name, source_count=source_count, dry_run=dry_run,
        ):
            report["aliases_recorded"].append(
                f"{name} -> {page.relative_to(wiki).as_posix()}"
            )
    for key, n in counts.items():
        bucket = "redirected" if key in redirect_pages else "unlinked"
        label = discarded[key]
        if key in redirect_pages:
            label = f"{label} -> {redirect_pages[key]}"
        report[bucket][label] = n
    report["changed_pages"] = pages
    report["changed"] = bool(
        pages or report["flattened"] or report["aliases_recorded"]
    )
    return report


def print_report(report: dict[str, Any]) -> None:
    """Print an operator-facing summary. Quiet when nothing needs doing."""
    if (
        not report["changed"]
        and not report["errors"]
        and not report["conflicts"]
        and not report["skipped"]
    ):
        print("nothing to migrate: no links to discarded candidates and no nested stubs")
        return

    print(f"vault:             {report['vault']}")
    print(f"wiki:              {report['wiki_dir']}")
    print(f"dry_run:           {report['dry_run']}")
    print(f"pages changed:     {len(report['changed_pages'])}")
    print(f"links unlinked:    {sum(report['unlinked'].values())}")
    for name, n in sorted(report["unlinked"].items()):
        print(f"  {n:>5}  {name}")
    print(f"links redirected:  {sum(report['redirected'].values())}")
    for name, n in sorted(report["redirected"].items()):
        print(f"  {n:>5}  {name}")
    for entry in report["aliases_recorded"]:
        print(f"  alias  {entry}")
    for rel in report["changed_pages"]:
        print(f"  changed    {rel}")
    print(f"stubs flattened:   {len(report['flattened'])}")
    for entry in report["flattened"]:
        print(f"  moved      {entry}")
    if report["conflicts"]:
        print(f"conflicts:         {len(report['conflicts'])}")
        for entry in report["conflicts"]:
            print(f"  ! {entry}")
    if report["skipped"]:
        print(f"skipped:           {len(report['skipped'])}")
        for entry in report["skipped"]:
            print(f"  - {entry}")
    if report["errors"]:
        print(f"errors:            {len(report['errors'])}")
        for err in report["errors"][:10]:
            print(f"  ! {err}")
        if report["aborted"]:
            print("  nothing was written: fix the errors above and re-run")
        else:
            print(
                "  the changes above were applied; the files named above were "
                "left as they are"
            )
