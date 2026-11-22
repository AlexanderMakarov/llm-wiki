"""Merge one live curated wiki page into another (#365).

Distinct from :func:`llmwiki.candidates.merge`, which folds a *harvest stub*
into a trusted page (or another stub). This module merges two already-live
pages across kinds: the survivor keeps its path and ``type``/folder; the
loser is archived under ``wiki/archive/``; inbound ``[[wikilinks]]`` retarget
to the survivor; and the dismissal ledger records a merge intent.
"""

from __future__ import annotations

import os
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path

from llmwiki._system_pages import ARCHIVE_FOLDER
from llmwiki.candidates import (
    _WIKILINK_TARGET_RE,
    _ensure_dismissal_ledger,
    _parse_frontmatter,
    _reconcile_catalog,
    _record_alias,
    _section_span,
    _split_frontmatter_text,
    _union_connections,
    _union_sources_frontmatter,
    find_live_page,
    frontmatter_sources,
    page_names,
    rewrite_links_in_wiki,
)
from llmwiki.dismissal_ledger import archive_candidates_dir, upsert_merge
from llmwiki.topics import DUPLICATE_REVIEW_KINDS
from llmwiki.wikilinks import norm_page_key, parse_page_aliases

__all__ = ["merge_pages"]

_HEADING_LINE_RE = re.compile(r"^##\s+.+?\s*$", re.MULTILINE)


def merge_pages(
    from_name: str,
    wiki_dir: Path,
    *,
    into: str,
) -> Path:
    """Fold the live page named ``from_name`` into the live page named ``into``.

    Both names resolve across entities/concepts/projects via
    :func:`llmwiki.candidates.find_live_page` (exact stem, then unique
    ``norm_page_key`` fold). The survivor path and kind are unchanged even
    when the loser lives under a different folder. Cross-kind merges are
    allowed.

    Side effects:

    - Union the loser's ``sources:`` into the survivor's frontmatter and the
      loser's ``## Connections`` targets into the survivor's Connections list.
    - Append the loser's distinctive prose under ``## Page merge — <date>``.
    - Record the loser's name (and its prior aliases) under ``## Aliases``.
    - Rewrite inbound ``[[wikilinks]]`` that named the loser so they point at
      the survivor (display text preserved).
    - Move the loser to ``wiki/archive/<same relative path>`` (timestamp nest
      on collision), ``upsert_merge`` into the dismissal ledger, and reconcile
      ``wiki/index.md``.

    Returns the survivor page path. Raises ``FileNotFoundError`` when either
    name does not resolve, ``ValueError`` when the names are the same page,
    the fold is ambiguous, or a page is outside the mergeable kind set.
    """
    loser = find_live_page(wiki_dir, from_name)
    survivor = find_live_page(wiki_dir, into)
    if loser == survivor:
        raise ValueError(
            f"cannot merge a page into itself: "
            f"{loser.relative_to(wiki_dir).as_posix()}"
        )
    _require_mergeable(loser, wiki_dir, label="merge source")
    _require_mergeable(survivor, wiki_dir, label="merge target")

    loser_text = loser.read_text(encoding="utf-8")
    loser_meta, loser_body = _parse_frontmatter(loser_text)
    loser_title = str(loser_meta.get("title") or loser.stem)
    loser_sources = frontmatter_sources(loser_text)
    connection_slugs = _connection_targets(
        loser_body,
        skip={norm_page_key(loser.stem), norm_page_key(survivor.stem),
              norm_page_key(loser_title)},
    )
    prose = _live_page_merge_prose(loser_body)
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    source_count = len(loser_sources)

    merged = _union_sources_frontmatter(
        survivor.read_text(encoding="utf-8"), loser_sources,
    )
    meta_text, body = _split_frontmatter_text(merged)
    body = _union_connections(body, connection_slugs)
    for alias in _loser_alias_names(loser, loser_text, loser_title):
        if any(
            norm_page_key(existing) == norm_page_key(alias)
            for existing in parse_page_aliases(meta_text + body)
        ):
            continue
        body = _record_alias(body, alias, source_count, today, verb="merged")
    if prose:
        rel = loser.relative_to(wiki_dir).as_posix()
        body = (
            body.rstrip()
            + f"\n\n## Page merge — {today}\n\n"
            + f"Merged from `{rel}`:\n\n"
            + prose
            + "\n"
        )
    survivor.write_text(meta_text + body, encoding="utf-8")

    # Materialise the ledger before the page moves so upsert is incremental
    # rather than a rebuild that would treat the archived file as a dismissal.
    _ensure_dismissal_ledger(wiki_dir)
    dest = _archive_live_page(loser, wiki_dir)
    stub = Path(os.path.relpath(dest, archive_candidates_dir(wiki_dir))).as_posix()
    upsert_merge(
        wiki_dir,
        name=loser_title,
        into=survivor.stem,
        stub=stub,
    )

    rewrite_targets = {
        key: survivor.stem
        for key in {
            norm_page_key(name)
            for name in page_names(loser, loser_text)
        }
        if key and key != norm_page_key(survivor.stem)
    }
    if rewrite_targets:
        rewrite_links_in_wiki(wiki_dir, rewrite_targets)

    _reconcile_catalog(wiki_dir)
    return survivor


def _require_mergeable(page: Path, wiki_dir: Path, *, label: str) -> None:
    """Refuse pages outside entities/concepts/projects (and non-wiki paths)."""
    try:
        rel = page.relative_to(wiki_dir)
    except ValueError as exc:
        raise ValueError(f"{label} escapes wiki/: {page}") from exc
    if not rel.parts or rel.parts[0] not in DUPLICATE_REVIEW_KINDS:
        kind = rel.parts[0] if rel.parts else "?"
        raise ValueError(
            f"{label} kind {kind!r} is not mergeable "
            f"(expected one of {sorted(DUPLICATE_REVIEW_KINDS)})"
        )


def _connection_targets(body: str, *, skip: set[str]) -> list[str]:
    """Ordered ``[[targets]]`` under ``## Connections``, minus ``skip`` keys."""
    span = _section_span(body, "Connections")
    if span is None:
        return []
    start, end = span
    ordered: list[str] = []
    seen: set[str] = set(skip)
    for raw in _WIKILINK_TARGET_RE.findall(body[start:end]):
        name = raw.split("#", 1)[0].strip()
        key = norm_page_key(name)
        if not name or key in seen:
            continue
        seen.add(key)
        ordered.append(name)
    return ordered


def _loser_alias_names(path: Path, text: str, title: str) -> list[str]:
    """Display names to record on the survivor: title, then prior aliases.

    Stem is included only when it differs from the title under
    :func:`norm_page_key`, so a page whose filename already matches its
    title does not get a duplicate Aliases bullet.
    """
    names: list[str] = []
    seen: set[str] = set()

    def _add(name: str) -> None:
        key = norm_page_key(name)
        if not name or not key or key in seen:
            return
        seen.add(key)
        names.append(name)

    _add(title)
    if norm_page_key(path.stem) != norm_page_key(title):
        _add(path.stem)
    for alias in parse_page_aliases(text):
        _add(alias)
    return names


def _live_page_merge_prose(body: str) -> str:
    """Loser body worth pasting: drop H1, Connections, and Aliases scaffold."""
    text = re.sub(r"^#\s+.*$", "", body, count=1, flags=re.MULTILINE)
    for heading in ("Connections", "Aliases"):
        text = _drop_section(text, heading)
    return text.strip()


def _drop_section(body: str, heading: str) -> str:
    """Remove ``## <heading>`` and its content through the next ``##``."""
    for match in _HEADING_LINE_RE.finditer(body):
        if match.group(0)[3:].strip().lower() != heading.lower():
            continue
        start = match.start()
        next_h = _HEADING_LINE_RE.search(body, match.end())
        end = next_h.start() if next_h else len(body)
        return (body[:start] + body[end:]).strip() + ("\n" if body[end:] else "")
    return body


def _archive_live_page(page: Path, wiki_dir: Path) -> Path:
    """Move ``page`` to ``wiki/archive/<relative path>`` (stamp nest on clash).

    Same layout :func:`llmwiki.remove_doc` uses for pages left unsourced, so a
    merge-archived entity stays under ``archive/entities/`` rather than the
    candidates triage bin. Ledger ``stub`` is then ``../entities/<Name>.md``
    relative to ``archive/candidates/``.
    """
    rel = page.relative_to(wiki_dir)
    dest = wiki_dir / ARCHIVE_FOLDER / rel
    if dest.exists():
        stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%S")
        dest = wiki_dir / ARCHIVE_FOLDER / stamp / rel
        n = 1
        while dest.exists():
            n += 1
            dest = wiki_dir / ARCHIVE_FOLDER / f"{stamp}-{n}" / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(page), str(dest))
    return dest
