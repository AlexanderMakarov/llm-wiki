"""Re-file source pages that sit under a name synth no longer derives (#265).

A real source page is tied to its raw file by ``source_file:``. When the page
filename differs from the one :func:`~llmwiki.synth.pipeline.synth_page_filename`
derives for that raw file today, synth's dedup guard (#37) skips the source on
every run and ``--estimate`` / Home keep counting it as pending, because the
synth state is keyed by the raw file and nothing ever records it as done.

This migration is offline — no synthesis backend is called:

* each such page moves to ``wiki/sources/<project>/<derived>.md`` with its body
  and frontmatter intact; a doc's ``--part-NN`` pages move as one group;
* ``title`` changes only while it still reads ``Session: <old token> — <date>``,
  the converter's shape for the old name — it becomes the raw file's title;
* ``[[old-stem]]`` links (with ``|label`` or ``#anchor``) and frontmatter
  ``sources:`` entries across ``wiki/`` follow the move. A bare stem shared by
  more than one page is reported as ambiguous and left alone; a path-qualified
  link is rewritten when its path matches exactly one page. ``wiki/archive/``
  and the log are never touched;
* synth state records each moved source, and each real page already at its
  derived path, that has no entry yet — an existing entry is kept, since one
  older than the raw file marks a raw re-converted after synthesis;
* moves are applied first; a failed move is undone and dropped along with
  its link rewrites and state entry;
* a real page already at the derived path is a collision: both pages stay
  untouched and the source gets no state entry.

Usage::

    llmwiki migrate source-page-paths --vault /path/to/vault --dry-run
    llmwiki migrate source-page-paths --vault /path/to/vault
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import Any

from llmwiki._frontmatter import parse_frontmatter
from llmwiki._system_pages import is_archived_path
from llmwiki.state_store import resolve_state_file
from llmwiki.synth.pipeline import (
    _append_log,
    _load_state,
    _rebuild_index,
    _save_state,
    page_is_stub,
    refresh_synth_pending,
    synth_page_filename,
)
from llmwiki.wikilinks import WIKILINK_RE, norm_page_key, wikilink_targets

_PART_SUFFIX = re.compile(r"--part-\d+$")
_DATE_PREFIX = re.compile(r"^(\d{4}-\d{2}-\d{2})-(.+)$")
_FENCE = re.compile(r"^---[ \t]*$")
_TITLE_LINE = re.compile(r"^title:[ \t]*")
_SOURCES_INLINE = re.compile(r"^(sources:[ \t]*\[)(.*)(\][ \t]*)$")
_SOURCES_BLOCK_KEY = re.compile(r"^sources:[ \t]*$")
_BLOCK_ITEM = re.compile(r"^([ \t]*-[ \t]+)(.*?)([ \t]*)$")
#: Wiki files that record history rather than link to pages.
_LOG_FILE = re.compile(r"^log(-archive-.*)?\.md$")


def _relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _read(path: Path, errors: list[str], root: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        errors.append(f"{_relative(path, root)}: {exc}")
        return None


def _frontmatter_lines(text: str) -> tuple[list[str], int]:
    """Return ``(lines, end)`` where ``lines[1:end]`` is the frontmatter block.

    ``end`` is 0 when the text opens with no frontmatter fence.
    """
    lines = text.splitlines(keepends=True)
    if not lines or not _FENCE.match(lines[0].rstrip("\r\n").lstrip("﻿")):
        return lines, 0
    for i in range(1, len(lines)):
        if _FENCE.match(lines[i].rstrip("\r\n")):
            return lines, i
    return lines, 0


def _title_line(text: str) -> str | None:
    """The literal ``title:`` line of ``text``'s frontmatter, without newline."""
    lines, end = _frontmatter_lines(text)
    for line in lines[1:end]:
        stripped = line.rstrip("\r\n")
        if _TITLE_LINE.match(stripped):
            return stripped
    return None


def _replace_title_line(text: str, new_line: str) -> str:
    lines, end = _frontmatter_lines(text)
    for i in range(1, end):
        stripped = lines[i].rstrip("\r\n")
        if _TITLE_LINE.match(stripped):
            lines[i] = new_line + lines[i][len(stripped):]
            break
    return "".join(lines)


def _wiki_pages(wiki: Path) -> list[Path]:
    """Every live wiki page: cold storage (``wiki/archive/``) is skipped."""
    pages: list[Path] = []
    for path in sorted(wiki.rglob("*.md")):
        if not path.is_file():
            continue
        if is_archived_path(path.relative_to(wiki).parts):
            continue
        pages.append(path)
    return pages


def _raw_source(vault: Path, source_file: str) -> tuple[Path, str, bool] | None:
    """Resolve a ``source_file`` claim to ``(raw path, synth state key, is_doc)``."""
    src = source_file.replace("\\", "/").strip()
    for prefix, is_doc in (("raw/sessions/", False), ("raw/docs/", True)):
        if src.startswith(prefix):
            rel = src[len(prefix):]
            if not rel or ".." in Path(rel).parts:
                return None
            raw = vault / src
            if not raw.is_file():
                return None
            return raw, ("docs::" + rel if is_doc else rel), is_doc
    return None


def _old_converter_title(stem: str) -> str | None:
    """``Session: <token> — <date>`` for a ``<date>-<token>`` page stem."""
    m = _DATE_PREFIX.match(_PART_SUFFIX.sub("", stem))
    return f"Session: {m.group(2)} — {m.group(1)}" if m else None


def _plan_sources(
    vault: Path, wiki: Path, errors: list[str]
) -> tuple[dict[str, dict[str, Any]], dict[Path, str]]:
    """Group every source page under ``wiki/sources/`` by the raw file it claims.

    Returns ``(sources, stub_claims)``: ``sources`` maps a synth state key to
    its raw file, derived target and the real page groups claiming it;
    ``stub_claims`` maps each stub page to the ``source_file`` it claims.
    """
    sources_dir = wiki / "sources"
    sources: dict[str, dict[str, Any]] = {}
    stub_claims: dict[Path, str] = {}
    raw_meta: dict[Path, tuple[dict[str, Any], str | None] | None] = {}
    if not sources_dir.is_dir():
        return sources, stub_claims
    for page in sorted(sources_dir.rglob("*.md")):
        if not page.is_file() or page.name.startswith("_"):
            continue
        text = _read(page, errors, vault)
        if text is None:
            continue
        meta, _body = parse_frontmatter(text)
        claim = str(meta.get("source_file") or "").strip()
        if not claim:
            continue
        if page_is_stub(page):
            stub_claims[page] = claim
            continue
        resolved = _raw_source(vault, claim)
        if resolved is None:
            continue
        raw, key, is_doc = resolved
        if raw not in raw_meta:
            raw_text = _read(raw, errors, vault)
            raw_meta[raw] = (
                None if raw_text is None
                else (parse_frontmatter(raw_text)[0], _title_line(raw_text))
            )
        cached = raw_meta[raw]
        if cached is None:
            continue
        rmeta, raw_title_line = cached
        entry = sources.get(key)
        if entry is None:
            if is_doc:
                project = str(rmeta.get("project") or "docs")
            else:
                project = str(rmeta.get("project") or raw.parent.name)
            entry = sources[key] = {
                "key": key,
                "raw": raw,
                "source_file": claim,
                "is_doc": is_doc,
                "target_dir": sources_dir / project,
                "filename": synth_page_filename(rmeta, raw.stem),
                "raw_title": rmeta.get("title"),
                "raw_title_line": raw_title_line,
                "groups": defaultdict(list),
            }
        base = _PART_SUFFIX.sub("", page.stem) if is_doc else page.stem
        entry["groups"][(page.parent, base)].append(page)
    return sources, stub_claims


def _plan_moves(
    sources: dict[str, dict[str, Any]], stub_claims: dict[Path, str], wiki: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    """Return ``(moves, collisions, heal keys)``.

    ``heal keys`` are sources whose real page already sits at the derived
    target and that have no colliding page elsewhere.
    """
    moves: list[dict[str, Any]] = []
    collisions: list[dict[str, Any]] = []
    heal: list[str] = []
    claimed: set[Path] = set()
    for key in sorted(sources):
        entry = sources[key]
        target_dir: Path = entry["target_dir"]
        filename: str = entry["filename"]
        groups = entry["groups"]
        at_target = (target_dir, filename) in groups
        source_collided = False
        for (folder, base), pages in sorted(groups.items()):
            if (folder, base) == (target_dir, filename):
                continue
            dests = [
                target_dir / f"{filename}{page.stem[len(base):]}.md" for page in pages
            ]
            reason = None
            if at_target:
                reason = "a real page for this source already sits at the target"
            for dest in dests:
                if reason:
                    break
                if dest in claimed:
                    reason = "another page is moving to the same target"
                elif dest.exists() and stub_claims.get(dest) != entry["source_file"]:
                    reason = "the target path is already taken"
            if reason:
                source_collided = True
                for page, dest in zip(pages, dests, strict=True):
                    collisions.append({
                        "from": _relative(page, wiki),
                        "to": _relative(dest, wiki),
                        "reason": reason,
                    })
                continue
            claimed.update(dests)
            old_title_shape = _old_converter_title(base)
            for page, dest in zip(pages, dests, strict=True):
                moves.append({
                    "key": key,
                    "path": page,
                    "dest": dest,
                    "from": _relative(page, wiki),
                    "to": _relative(dest, wiki),
                    "old_stem": page.stem,
                    "new_stem": dest.stem,
                    "old_title_shape": old_title_shape,
                    "raw_title": entry["raw_title"],
                    "raw_title_line": entry["raw_title_line"],
                })
        if at_target and not source_collided:
            heal.append(key)
    return moves, collisions, heal


def _link_rewriter(
    moves: list[dict[str, Any]], all_pages: list[Path], wiki: Path,
) -> tuple[
    dict[str, dict[str, Any] | None],
    dict[str, dict[str, Any] | None],
    dict[str, list[tuple[Path, dict[str, Any] | None]]],
]:
    """Return ``(bare, qualified, shared)`` lookups of moved pages.

    ``bare`` maps an old stem to its move (``None`` when that stem cannot be
    rewritten unambiguously); ``qualified`` maps each live page's wiki-relative
    path without ``.md`` to the move of that page, if any. ``shared`` maps an
    old stem that several pages carry to its source-page candidates, each with
    the move to follow — ``None`` for a candidate that stays put or whose new
    stem would itself be ambiguous.
    """
    moved_paths = {m["path"] for m in moves}
    replaced = {m["dest"] for m in moves}
    stem_count = Counter(p.stem for p in all_pages)
    new_stem_count = Counter(m["new_stem"] for m in moves)
    # Pages that will still exist under their stem after the pass.
    remaining = Counter(
        p.stem for p in all_pages if p not in moved_paths and p not in replaced
    )

    def _new_is_unique(m: dict[str, Any]) -> bool:
        return new_stem_count[m["new_stem"]] == 1 and remaining[m["new_stem"]] == 0

    by_path = {m["path"]: m for m in moves}
    bare: dict[str, dict[str, Any] | None] = {}
    shared: dict[str, list[tuple[Path, dict[str, Any] | None]]] = {}
    for m in moves:
        unique_old = stem_count[m["old_stem"]] == 1
        bare[m["old_stem"]] = m if unique_old and _new_is_unique(m) else None
        if not unique_old and m["old_stem"] not in shared:
            shared[m["old_stem"]] = [
                (p, by_path[p] if p in by_path and _new_is_unique(by_path[p]) else None)
                for p in all_pages
                if p.stem == m["old_stem"] and p.relative_to(wiki).parts[0] == "sources"
            ]
    qualified = {
        _relative(p, wiki).removesuffix(".md"): by_path.get(p) for p in all_pages
    }
    return bare, qualified, shared


class _Backlinks:
    """Pick the one candidate page that links back to the referring page.

    A bare ``[[stem]]`` that several source pages answer to names no page on
    its own; the candidate whose body wikilinks the referrer is almost always
    the one meant (a project or entity page and the session it lists point at
    each other). Targets are matched on :func:`norm_page_key`, the fold
    ``link_integrity`` applies. A back-linker that stays put keeps the link as
    it is; one whose new stem would be ambiguous too leaves it ambiguous.
    """

    def __init__(
        self,
        shared: dict[str, list[tuple[Path, dict[str, Any] | None]]],
        moving: set[Path],
        read: Callable[[Path], str | None],
    ) -> None:
        self._shared = shared
        self._moving = moving
        self._read = read
        self._targets: dict[Path, set[str]] = {}

    def _links_of(self, page: Path) -> set[str]:
        if page not in self._targets:
            text = self._read(page) or ""
            self._targets[page] = {
                norm_page_key(t.rsplit("/", 1)[-1].removesuffix(".md"))
                for t in wikilink_targets(text)
            }
        return self._targets[page]

    def resolve(
        self, stem: str, referrer: Path
    ) -> tuple[str, dict[str, Any] | None]:
        """Return ``("rewrite", move)``, ``("kept", None)`` or ``("ambiguous", None)``."""
        candidates = self._shared.get(stem)
        if not candidates:
            return "ambiguous", None
        key = norm_page_key(referrer.stem)
        linking = [
            (page, move) for page, move in candidates
            if page != referrer and key in self._links_of(page)
        ]
        if len(linking) != 1:
            return "ambiguous", None
        page, move = linking[0]
        if page not in self._moving:
            return "kept", None
        if move is None:
            return "ambiguous", None
        return "rewrite", move


def _resolve_qualified(
    name: str, qualified: dict[str, dict[str, Any] | None]
) -> tuple[str, dict[str, Any] | None]:
    """Resolve a path-qualified link the way a vault browser does: by path suffix.

    Returns ``("unique" | "ambiguous" | "none", move)``.
    """
    q = name.strip().lstrip("/")
    matches = [
        rel for rel in qualified
        if rel == q or rel.endswith("/" + q) or f"wiki/{rel}" == q
    ]
    if len(matches) == 1:
        return "unique", qualified[matches[0]]
    if any(qualified[rel] for rel in matches):
        return "ambiguous", None
    return "none", None


def _rewrite_links(
    text: str,
    bare: dict[str, dict[str, Any] | None],
    qualified: dict[str, dict[str, Any] | None],
    new_titles: dict[str, tuple[str, str]],
    resolve_shared: Callable[[str], tuple[str, dict[str, Any] | None]],
) -> tuple[str, int, Counter[str], Counter[str]]:
    """Rewrite links to moved pages.

    Returns ``(text, count, ambiguous occurrences per stem, backlink
    outcomes)``; ``count``
    includes links rewritten through a back-linking candidate.
    """
    count = 0
    ambiguous: Counter[str] = Counter()
    backlinks: Counter[str] = Counter()

    def _sub(match: re.Match[str]) -> str:
        nonlocal count
        inner = match.group(0)[2:-2]
        target, sep, label = inner.partition("|")
        name, hash_, anchor = target.partition("#")
        clean = name.strip()
        md = clean.endswith(".md")
        clean = clean.removesuffix(".md")
        if "/" in clean:
            outcome, move = _resolve_qualified(clean, qualified)
            if outcome == "ambiguous":
                ambiguous[clean.rsplit("/", 1)[-1]] += 1
            if move is None:
                return match.group(0)
            parts = clean.strip("/").split("/")
            full_new = ("wiki/" + move["to"].removesuffix(".md")).split("/")
            new_name = "/".join(full_new[-len(parts):])
        else:
            if clean not in bare:
                return match.group(0)
            move = bare[clean]
            if move is None:
                outcome, move = resolve_shared(clean)
                if outcome == "kept":
                    backlinks["kept"] += 1
                    return match.group(0)
                if move is None:
                    ambiguous[clean] += 1
                    return match.group(0)
                backlinks["rewritten"] += 1
            new_name = move["new_stem"]
        if md:
            new_name += ".md"
        titles = new_titles.get(move["old_stem"])
        if sep and titles and label.strip() == titles[0]:
            label = titles[1]
        count += 1
        return f"[[{new_name}{hash_}{anchor}{sep}{label}]]"

    return WIKILINK_RE.sub(_sub, text), count, ambiguous, backlinks


def _rewrite_item(
    item: str,
    bare: dict[str, dict[str, Any] | None],
    resolve_shared: Callable[[str], tuple[str, dict[str, Any] | None]],
) -> tuple[str, str]:
    """Rewrite one ``sources:`` entry.

    Returns ``(text, outcome)`` with outcome ``keep``, ``rewritten``,
    ``backlink`` (rewritten through a back-linking candidate), ``kept``
    (the back-linker stays put) or ``ambiguous``.
    """
    stripped = item.strip()
    quote = stripped[0] if stripped[:1] in ("'", '"') and stripped[-1:] == stripped[:1] else ""
    value = stripped[1:-1] if quote else stripped
    if value not in bare:
        return item, "keep"
    move = bare[value]
    outcome = "rewritten"
    if move is None:
        outcome, move = resolve_shared(value)
        if outcome == "kept":
            return item, "kept"
        if move is None:
            return item, "ambiguous"
        outcome = "backlink"
    lead = item[: len(item) - len(item.lstrip())]
    trail = item[len(item.rstrip()):]
    return f"{lead}{quote}{move['new_stem']}{quote}{trail}", outcome


def _rewrite_sources_list(
    text: str,
    bare: dict[str, dict[str, Any] | None],
    resolve_shared: Callable[[str], tuple[str, dict[str, Any] | None]],
) -> tuple[str, int, Counter[str], Counter[str]]:
    """Rewrite old stems in the frontmatter ``sources:`` list (inline or block).

    Returns the same shape as :func:`_rewrite_links`.
    """
    lines, end = _frontmatter_lines(text)
    count = 0
    ambiguous: Counter[str] = Counter()
    backlinks: Counter[str] = Counter()

    def _tally(item: str, outcome: str) -> None:
        nonlocal count
        if outcome in ("rewritten", "backlink"):
            count += 1
        if outcome == "backlink":
            backlinks["rewritten"] += 1
        elif outcome == "kept":
            backlinks["kept"] += 1
        elif outcome == "ambiguous":
            ambiguous[item.strip().strip("'\"")] += 1
    in_block = False
    for i in range(1, end):
        body = lines[i].rstrip("\r\n")
        newline = lines[i][len(body):]
        if in_block:
            m = _BLOCK_ITEM.match(body)
            if not m:
                in_block = False
            else:
                new_item, outcome = _rewrite_item(m.group(2), bare, resolve_shared)
                _tally(m.group(2), outcome)
                lines[i] = f"{m.group(1)}{new_item}{m.group(3)}{newline}"
                continue
        if _SOURCES_BLOCK_KEY.match(body):
            in_block = True
            continue
        m = _SOURCES_INLINE.match(body)
        if not m:
            continue
        items = m.group(2).split(",") if m.group(2).strip() else []
        out: list[str] = []
        for item in items:
            new_item, outcome = _rewrite_item(item, bare, resolve_shared)
            _tally(item, outcome)
            out.append(new_item)
        lines[i] = f"{m.group(1)}{','.join(out)}{m.group(3)}{newline}"
    return "".join(lines), count, ambiguous, backlinks


def run_migration(*, vault: Path, dry_run: bool = False) -> dict[str, Any]:
    """Move stale source pages under ``vault/wiki/sources`` to their derived paths.

    Returns a report dict; ``changed`` is ``False`` when nothing moved, no link
    changed and no state entry was recorded — a second run on a migrated vault.
    """
    vault = Path(vault).expanduser().resolve()
    wiki = vault / "wiki"
    report: dict[str, Any] = {
        "vault": str(vault),
        "wiki_dir": str(wiki),
        "dry_run": dry_run,
        "moves": [],
        "collisions": [],
        "rewritten_pages": [],
        "links_rewritten": 0,
        "sources_rewritten": 0,
        "disambiguated": 0,
        "disambiguated_kept": 0,
        "ambiguous": [],
        "still_ambiguous": 0,
        "would_break": 0,
        "state_upserts": [],
        "errors": [],
        "changed": False,
    }
    errors: list[str] = report["errors"]
    if not wiki.is_dir():
        errors.append(f"missing wiki dir: {wiki}")
        return report

    sources, stub_claims = _plan_sources(vault, wiki, errors)
    planned, collisions, heal = _plan_moves(sources, stub_claims, wiki)
    report["collisions"] = collisions

    original: dict[Path, str | None] = {}

    def _original(page: Path) -> str | None:
        if page not in original:
            original[page] = _read(page, errors, vault)
        return original[page]

    # Title updates first: link labels that quote the old title follow them.
    moves: list[dict[str, Any]] = []
    moved_texts: dict[Path, str] = {}
    new_titles: dict[str, tuple[str, str]] = {}
    for move in planned:
        text = _original(move["path"])
        if text is None:
            continue
        moves.append(move)
        meta, _body = parse_frontmatter(text)
        old_title = meta.get("title")
        raw_title = move["raw_title"]
        title_updated = (
            isinstance(old_title, str)
            and old_title == move["old_title_shape"]
            and isinstance(raw_title, str)
            and bool(raw_title.strip())
            and raw_title != old_title
            and move["raw_title_line"] is not None
        )
        if title_updated:
            text = _replace_title_line(text, move["raw_title_line"])
            new_titles[move["old_stem"]] = (old_title, raw_title)
        moved_texts[move["path"]] = text
        move["title_updated"] = title_updated

    all_pages = _wiki_pages(wiki)
    state_file = resolve_state_file(vault)
    try:
        state = _load_state(state_file)
    except (OSError, ValueError, TypeError) as exc:
        errors.append(f"state load: {exc}")
        state = {}

    rewrites = _plan_rewrites(moves, all_pages, wiki, moved_texts, new_titles, _original)
    updates = _state_updates(moves, heal, sources, state, errors)
    _fill_report(report, moves, rewrites, updates)
    if dry_run or not report["changed"]:
        return report

    # Moves land first; a move that fails is rolled back and dropped, and the
    # link rewrites and state entries are then planned for the moves that held.
    landed = _apply_moves(moves, moved_texts, _original, wiki, errors)
    if len(landed) != len(moves):
        moves = landed
        rewrites = _plan_rewrites(
            moves, all_pages, wiki, moved_texts, new_titles, _original
        )
        updates = _state_updates(moves, heal, sources, state, errors)
        _fill_report(report, moves, rewrites, updates)

    by_path = {m["path"]: m for m in moves}
    for path, text in rewrites["texts"].items():
        move = by_path.get(path)
        target = move["dest"] if move else path
        if move and text == moved_texts[path]:
            continue
        try:
            target.write_text(text, encoding="utf-8")
        except OSError as exc:
            errors.append(f"{_relative(target, wiki)}: {exc}")

    if updates:
        try:
            _save_state({**state, **updates}, state_file)
        except OSError as exc:
            errors.append(f"{state_file.name}: {exc}")

    if moves and (wiki / "index.md").is_file():
        try:
            _rebuild_index(wiki)
        except (OSError, ValueError, RuntimeError) as exc:
            errors.append(f"index rebuild: {exc}")
    if report["changed"]:
        try:
            refresh_synth_pending(
                raw_dir=vault / "raw" / "sessions",
                docs_dir=vault / "raw" / "docs",
                wiki_sources_dir=wiki / "sources",
                state_file=state_file,
            )
        except (OSError, ValueError) as exc:
            errors.append(f"pending refresh: {exc}")
        _append_log("source page paths", log_path=wiki / "log.md", operation="migrate")
    return report


def _plan_rewrites(
    moves: list[dict[str, Any]],
    all_pages: list[Path],
    wiki: Path,
    moved_texts: dict[Path, str],
    new_titles: dict[str, tuple[str, str]],
    read: Callable[[Path], str | None],
) -> dict[str, Any]:
    """Plan the link and ``sources:`` rewrites that follow ``moves``.

    ``texts`` maps each page to write — keyed by its path before the pass —
    to its new text; a moved page always appears, with its title update. A
    page a move replaces (a stub at the derived path) is left out: the move
    overwrites it.
    """
    bare, qualified, shared = _link_rewriter(moves, all_pages, wiki)
    moved_paths = {m["path"] for m in moves}
    replaced = {m["dest"] for m in moves} - moved_paths
    backlinker = _Backlinks(shared, moved_paths, read)
    plan: dict[str, Any] = {
        "texts": {},
        "rewritten_pages": [],
        "links": 0,
        "sources": 0,
        "disambiguated": 0,
        "disambiguated_kept": 0,
    }
    ambiguous: dict[str, set[str]] = defaultdict(set)
    hits: Counter[str] = Counter()
    for page in all_pages:
        if page in replaced or (page.parent == wiki and _LOG_FILE.match(page.name)):
            continue
        text = moved_texts.get(page)
        if text is None:
            text = read(page)
            if text is None:
                continue

        def _resolve(stem: str, page: Path = page) -> tuple[str, dict[str, Any] | None]:
            return backlinker.resolve(stem, page)

        rewritten, links, amb_links, bl_links = _rewrite_links(
            text, bare, qualified, new_titles, _resolve
        )
        rewritten, listed, amb_listed, bl_listed = _rewrite_sources_list(
            rewritten, bare, _resolve
        )
        backlinks = bl_links + bl_listed
        plan["disambiguated"] += backlinks["rewritten"]
        plan["disambiguated_kept"] += backlinks["kept"]
        hits.update(amb_links)
        hits.update(amb_listed)
        for stem in amb_links | amb_listed:
            ambiguous[stem].add(_relative(page, wiki))
        if links or listed:
            plan["links"] += links
            plan["sources"] += listed
            plan["rewritten_pages"].append({
                "page": _relative(page, wiki),
                "links": links,
                "sources": listed,
            })
        if rewritten != text or page in moved_paths:
            plan["texts"][page] = rewritten
    kept_stems = {p.stem for p in all_pages if p not in moved_paths}
    plan["ambiguous"] = [
        {
            "stem": stem,
            "referrers": sorted(refs),
            "occurrences": hits[stem],
            "dangling": stem not in kept_stems,
        }
        for stem, refs in sorted(ambiguous.items())
    ]
    return plan


def _state_updates(
    moves: list[dict[str, Any]],
    heal: list[str],
    sources: dict[str, dict[str, Any]],
    state: dict[str, float],
    errors: list[str],
) -> dict[str, float]:
    """Synth state entries to record: moved or healed sources with no entry yet.

    An existing entry is kept even when it is older than the raw file — the
    raw was re-converted after synthesis, so synth must still see it as stale.
    """
    updates: dict[str, float] = {}
    for key in sorted({m["key"] for m in moves} | set(heal)):
        if key in state:
            continue
        try:
            updates[key] = float(sources[key]["raw"].stat().st_mtime)
        except OSError as exc:
            errors.append(f"{sources[key]['source_file']}: {exc}")
    return updates


def _fill_report(
    report: dict[str, Any],
    moves: list[dict[str, Any]],
    rewrites: dict[str, Any],
    updates: dict[str, float],
) -> None:
    report["moves"] = [
        {"from": m["from"], "to": m["to"], "title_updated": m["title_updated"]}
        for m in moves
    ]
    report["rewritten_pages"] = rewrites["rewritten_pages"]
    report["links_rewritten"] = rewrites["links"]
    report["sources_rewritten"] = rewrites["sources"]
    report["disambiguated"] = rewrites["disambiguated"]
    report["disambiguated_kept"] = rewrites["disambiguated_kept"]
    report["ambiguous"] = rewrites["ambiguous"]
    report["still_ambiguous"] = sum(a["occurrences"] for a in rewrites["ambiguous"])
    report["would_break"] = sum(
        a["occurrences"] for a in rewrites["ambiguous"] if a["dangling"]
    )
    report["state_upserts"] = sorted(updates)
    report["changed"] = bool(
        report["moves"] or report["rewritten_pages"] or report["state_upserts"]
    )


def _apply_moves(
    moves: list[dict[str, Any]],
    moved_texts: dict[Path, str],
    read: Callable[[Path], str | None],
    wiki: Path,
    errors: list[str],
) -> list[dict[str, Any]]:
    """Move pages source by source; return the moves that landed.

    A doc's part pages move together: when any page of a source fails to
    write or to leave its old path, the pages already moved for that source
    go back and whatever sat at their targets is restored.
    """
    by_key: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for move in moves:
        by_key[move["key"]].append(move)
    landed: list[dict[str, Any]] = []
    for key in sorted(by_key):
        done: list[tuple[dict[str, Any], str | None]] = []
        failed = False
        for move in by_key[key]:
            path: Path = move["path"]
            dest: Path = move["dest"]
            try:
                prior = dest.read_text(encoding="utf-8") if dest.is_file() else None
            except (OSError, UnicodeDecodeError) as exc:
                errors.append(f"{move['to']}: {exc}; not moved")
                failed = True
                break
            try:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(moved_texts[path], encoding="utf-8")
            except OSError as exc:
                errors.append(f"{move['from']} → {move['to']}: {exc}; not moved")
                failed = True
                _restore(dest, prior, wiki, errors)
                break
            try:
                path.unlink()
            except OSError as exc:
                errors.append(f"{move['from']}: {exc}; move undone")
                failed = True
                _restore(dest, prior, wiki, errors)
                break
            done.append((move, prior))
        if not failed:
            landed.extend(by_key[key])
            continue
        for move, prior in reversed(done):
            text = read(move["path"])
            try:
                if text is not None:
                    move["path"].write_text(text, encoding="utf-8")
            except OSError as exc:
                errors.append(f"{move['from']}: {exc}; could not put the page back")
                continue
            _restore(move["dest"], prior, wiki, errors)
    return landed


def _restore(dest: Path, prior: str | None, wiki: Path, errors: list[str]) -> None:
    """Put back what sat at ``dest`` before a move wrote there."""
    try:
        if prior is None:
            dest.unlink(missing_ok=True)
        else:
            dest.write_text(prior, encoding="utf-8")
    except OSError as exc:
        errors.append(f"{_relative(dest, wiki)}: {exc}; could not undo the write")


def print_report(report: dict[str, Any]) -> None:
    """Print planned or applied moves, collisions, link rewrites and state upserts."""
    if not report["changed"] and not report["collisions"] and not report["errors"]:
        print("nothing to migrate: every source page sits at its derived path")
        return
    print(f"vault:            {report['vault']}")
    print(f"dry_run:          {report['dry_run']}")
    print(f"moves:            {len(report['moves'])}")
    for move in report["moves"]:
        note = "  (title updated)" if move["title_updated"] else ""
        print(f"  {move['from']} → {move['to']}{note}")
    print(f"collisions:       {len(report['collisions'])}")
    for col in report["collisions"]:
        print(f"  ! {col['from']} → {col['to']}: {col['reason']}; left untouched")
    print(f"links rewritten:  {report['links_rewritten']}")
    print(f"sources entries:  {report['sources_rewritten']}")
    for page in report["rewritten_pages"]:
        print(f"  {page['page']}: {page['links']} link(s), {page['sources']} sources entry(ies)")
    print(
        f"disambiguated by backlink: {report['disambiguated']} rewritten, "
        f"{report['disambiguated_kept']} kept (back-linker stays put)"
    )
    print(
        f"still ambiguous:  {report['still_ambiguous']} link(s)/entries over "
        f"{len(report['ambiguous'])} stem(s); {report['would_break']} would break"
    )
    for amb in report["ambiguous"]:
        refs = ", ".join(amb["referrers"][:5])
        more = "" if len(amb["referrers"]) <= 5 else f" … +{len(amb['referrers']) - 5} more"
        print(f"  ? [[{amb['stem']}]] names several pages; not rewritten in: {refs}{more}")
        if amb["dangling"]:
            print("    every page of that name moves, so these links break; fix them by hand")
    print(f"state upserts:    {len(report['state_upserts'])}")
    for key in report["state_upserts"]:
        print(f"  {key}")
    if report["errors"]:
        print(f"errors:           {len(report['errors'])}")
        for err in report["errors"][:10]:
            print(f"  ! {err}")
    if report["moves"] and not report["dry_run"]:
        print("note: run `llmwiki build --vault …` so site/ picks up the new paths.")
