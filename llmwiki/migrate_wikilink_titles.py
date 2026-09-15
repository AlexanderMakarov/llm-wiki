"""Rewrite bare resolving ``[[slug]]`` wikilinks to ``[[slug|Title]]`` (#259).

Offline one-time migration: titles come from frontmatter already on disk
under ``wiki/``. No synthesis backend or network call. Complements the
title-only findability lint by making link display text match page titles
without changing link targets.

Usage::

    llmwiki migrate wikilink-titles --vault /path/to/vault --dry-run
    llmwiki migrate wikilink-titles --vault /path/to/vault
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from llmwiki._system_pages import is_archived_path
from llmwiki.graph import scan_pages
from llmwiki.wikilinks import (
    WIKILINK_RE,
    build_page_alias_map,
    resolve_wikilink_target,
    strip_anchor,
)

#: Detect an explicit display pipe inside ``[[…]]`` (group 1 excludes ``|``).
_HAS_DISPLAY_PIPE_RE = re.compile(r"\[\[[^\]|]+\|")


def _title_is_safe(title: str) -> bool:
    """Return False for empty or wikilink-breaking display text."""
    if not title.strip():
        return False
    return "|" not in title and "]]" not in title


def build_title_map(wiki: Path) -> tuple[dict[str, str], dict[str, str], set[str]]:
    """Return slug→title, alias map, and slug set aligned with the graph scan.

    Uses :func:`llmwiki.graph.scan_pages` so stem collisions and archive skips
    match ``build_graph``. Titles fall back to the page stem when frontmatter
    omits ``title`` (same as the graph).
    """
    pages = scan_pages(wiki)
    slug_to_title = {slug: str(page["title"]) for slug, page in pages.items()}
    bodies = {slug: page["body"] for slug, page in pages.items()}
    slugs = set(pages)
    alias_map = build_page_alias_map(bodies)
    return slug_to_title, alias_map, slugs


def _rewrite_wikilink_match(
    full: str,
    target: str,
    *,
    slugs: set[str],
    alias_map: dict[str, str],
    slug_to_title: dict[str, str],
) -> tuple[str, str]:
    """Return ``(new_link, outcome)`` for one ``WIKILINK_RE`` match.

    ``outcome`` is one of ``rewritten``, ``skipped_display``, ``skipped_unresolved``,
    ``skipped_non_bare``, ``skipped_unsafe_title``.
    """
    if _HAS_DISPLAY_PIPE_RE.match(full):
        return full, "skipped_display"

    anchor = strip_anchor(target)
    if not anchor:
        return full, "skipped_unresolved"

    resolved = resolve_wikilink_target(anchor, slugs, alias_map)
    if resolved is None:
        return full, "skipped_unresolved"

    if anchor.casefold() != resolved.casefold():
        return full, "skipped_non_bare"

    title = slug_to_title.get(resolved, "")
    if not _title_is_safe(title):
        return full, "skipped_unsafe_title"

    return f"[[{target}|{title}]]", "rewritten"


def rewrite_wikilink_titles(
    text: str,
    *,
    slug_to_title: dict[str, str],
    alias_map: dict[str, str],
    slugs: set[str],
) -> tuple[str, dict[str, int]]:
    """Rewrite bare resolving wikilinks in ``text``; return new text and counters."""
    counters = {
        "links_rewritten": 0,
        "links_skipped_display": 0,
        "links_skipped_unresolved": 0,
        "links_skipped_non_bare": 0,
        "links_skipped_unsafe_title": 0,
    }
    if not WIKILINK_RE.search(text):
        return text, counters

    parts: list[str] = []
    last = 0
    for match in WIKILINK_RE.finditer(text):
        parts.append(text[last : match.start()])
        full = match.group(0)
        target = match.group(1)
        new_link, outcome = _rewrite_wikilink_match(
            full,
            target,
            slugs=slugs,
            alias_map=alias_map,
            slug_to_title=slug_to_title,
        )
        if outcome == "rewritten":
            counters["links_rewritten"] += 1
        elif outcome.startswith("skipped_"):
            key = outcome.replace("skipped_", "links_skipped_", 1)
            counters[key] += 1
        parts.append(new_link)
        last = match.end()
    parts.append(text[last:])
    return "".join(parts), counters


def _relative(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _iter_wiki_markdown(wiki: Path) -> list[Path]:
    if not wiki.is_dir():
        return []
    paths: list[Path] = []
    for path in sorted(wiki.rglob("*.md")):
        if not path.is_file() or path.stem in ("README",):
            continue
        try:
            rel = path.relative_to(wiki)
        except ValueError:
            continue
        if is_archived_path(rel.parts):
            continue
        paths.append(path)
    return paths


def run_migration(*, vault: Path, dry_run: bool = False) -> dict[str, Any]:
    """Rewrite bare slug wikilinks under ``vault/wiki`` to show target titles.

    Dry-run computes the same report without writing files. Never touches
    ``raw/``.
    """
    vault = Path(vault).expanduser().resolve()
    wiki = vault / "wiki"
    report: dict[str, Any] = {
        "vault": str(vault),
        "wiki_dir": str(wiki),
        "dry_run": dry_run,
        "pages_changed": 0,
        "links_rewritten": 0,
        "links_skipped_display": 0,
        "links_skipped_unresolved": 0,
        "links_skipped_non_bare": 0,
        "links_skipped_unsafe_title": 0,
        "changed_pages": [],
        "errors": [],
        "changed": False,
    }
    if not wiki.is_dir():
        report["errors"].append(f"missing wiki dir: {wiki}")
        return report

    slug_to_title, alias_map, slugs = build_title_map(wiki)

    for path in _iter_wiki_markdown(wiki):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            report["errors"].append(f"{_relative(path, vault)}: {exc}")
            continue

        new_text, counters = rewrite_wikilink_titles(
            text,
            slug_to_title=slug_to_title,
            alias_map=alias_map,
            slugs=slugs,
        )
        for key, value in counters.items():
            report[key] += value

        if counters["links_rewritten"] == 0 or new_text == text:
            continue

        rel_path = _relative(path, vault)
        if dry_run:
            report["pages_changed"] += 1
            report["changed_pages"].append(rel_path)
            continue

        try:
            path.write_text(new_text, encoding="utf-8")
        except OSError as exc:
            report["errors"].append(f"{rel_path}: {exc}")
            for key, value in counters.items():
                report[key] -= value
            continue

        report["pages_changed"] += 1
        report["changed_pages"].append(rel_path)

    report["changed"] = bool(
        report["links_rewritten"] > 0 or report["pages_changed"] > 0
    )
    return report


def print_report(report: dict[str, Any]) -> None:
    """Print an operator-facing summary. Quiet when nothing needs doing."""
    if not report["changed"] and not report["errors"]:
        print("nothing to migrate: no bare slug wikilinks need title display text")
        return

    print(f"vault:                       {report['vault']}")
    print(f"wiki:                        {report['wiki_dir']}")
    print(f"dry_run:                     {report['dry_run']}")
    print(f"pages changed:               {report['pages_changed']}")
    print(f"links rewritten:             {report['links_rewritten']}")
    print(f"links skipped (display):     {report['links_skipped_display']}")
    print(f"links skipped (unresolved):  {report['links_skipped_unresolved']}")
    print(f"links skipped (non-bare):    {report['links_skipped_non_bare']}")
    print(f"links skipped (unsafe title): {report['links_skipped_unsafe_title']}")
    for rel in report["changed_pages"]:
        print(f"  changed  {rel}")
    if report["errors"]:
        print(f"errors:                      {len(report['errors'])}")
        for err in report["errors"][:10]:
            print(f"  ! {err}")
