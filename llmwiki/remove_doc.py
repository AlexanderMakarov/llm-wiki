"""`llmwiki remove` — cascade deletion of a raw doc and everything
derived from it (B2).

A raw doc under ``raw/docs/`` fans out into three durable artifacts: the
raw file(s), a ``synth.files`` key in the unified state store, and a
``wiki/sources/`` page (plus ``--part-*`` pages for oversized docs). A
naive ``rm raw/docs/...`` leaves the last two behind as orphans — a wiki
page pointing at a file that no longer exists, and a state key that keeps
the source looking "already synthesized". This module plans and executes
the full cascade so removal is complete and, via the plan/execute split,
identical whether it is previewed (``--dry-run``) or run for real.

Source pages are located two ways, matching how the synth pipeline keys
them: by the path :func:`expected_source_page` derives, AND by the
``source_file: raw/docs/<rel>`` frontmatter key — which synth now writes
on every doc page (#307) and which a hand-placed page under an arbitrary
folder/name may also claim. Both are unioned so neither escapes: a page
an older release left with a blank ``source_file`` is still only findable
by path.

Removing a source page also removes what other pages said about it (#277).
Every live page outside ``wiki/archive/`` that cites a removed slug in
``sources:`` loses that entry; a list item that is nothing but a
``[[wikilink]]`` to it is dropped; any other ``[[wikilink]]`` to it becomes
plain text. A curated page (entity, concept, project, synthesis, candidate)
left with no ``sources:`` at all is moved to ``wiki/archive/`` rather than
kept as an unsourced claim, and its name is recorded in the dismissal ledger
(``wiki/archive/candidates/dismissals.json``) so harvest never re-proposes it.
Nothing is annotated: the citation is trimmed, not flagged. The append-only
``wiki/log.md`` and its yearly archives are never rewritten, by either pass.
"""

from __future__ import annotations

import fnmatch
import os
import re
import shutil
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from llmwiki._frontmatter import parse_frontmatter
from llmwiki._system_pages import ARCHIVE_FOLDER, is_archived_path, is_system_file
from llmwiki.add_doc import remove_raw_docs
from llmwiki.candidates import parse_sources_field, rewrite_sources_line
from llmwiki.dismissal_ledger import archive_candidates_dir, ledger_path, load_ledger, save_ledger, upsert_dismissal
from llmwiki.state_store import read_state, update_state
from llmwiki.synth.pipeline import (
    _append_log,
    _rebuild_index,
    is_log_page,
    source_page_paths,
    synth_page_filename,
)
from llmwiki.wikilinks import norm_page_key, parse_page_aliases, rewrite_wikilinks, strip_anchor

__all__ = [
    "PageEdit",
    "RemoveIncompleteError",
    "RemovePlan",
    "build_remove_plan",
    "format_plan",
    "execute_remove_plan",
]

#: Top-level ``wiki/`` folders whose pages may be archived once their
#: ``sources:`` is gone. Navigation / system pages and ``sources/`` itself are
#: never archived.
_ARCHIVABLE_DIRS = frozenset({"entities", "concepts", "projects", "syntheses", "candidates"})

#: A markdown list item whose whole content is one ``[[wikilink]]``.
_LIST_ONLY_LINK_RE = re.compile(
    r"^[ \t]*(?:[-*+]|\d+[.)])[ \t]+\[\[([^\]|]+)(?:\|[^\]]*)?\]\][ \t]*$"
)
_CODE_FENCE_RE = re.compile(r"^[ \t]*(?:```|~~~)")


class RemoveIncompleteError(RuntimeError):
    """A raw doc could not be unlinked, so the cascade stopped before
    touching anything derived from it."""


@dataclass
class PageEdit:
    """What removing the source pages does to one citing page (#277)."""
    path: Path
    #: ``path`` relative to the vault's ``wiki/`` directory.
    rel: Path
    #: ``sources:`` entries dropped.
    sources_trimmed: int = 0
    #: ``[[wikilinks]]`` turned into plain text.
    links_unlinked: int = 0
    #: List items that were only a wikilink to a removed page, dropped.
    items_dropped: int = 0
    #: True when the page had ``sources:`` and has none left.
    sources_emptied: bool = False

    @property
    def archive(self) -> bool:
        """True when the page is a curated page that lost its last source."""
        return self.sources_emptied and _archivable(self.rel)


@dataclass
class RemovePlan:
    """The complete set of artifacts a ``remove`` would delete, plus the
    derived-index effects that follow. Produced read-only by
    :func:`build_remove_plan`; consumed by :func:`execute_remove_plan`."""
    selector: str
    vault_root: Path
    raw_docs: list[Path] = field(default_factory=list)
    state_keys: list[str] = field(default_factory=list)
    source_pages: list[Path] = field(default_factory=list)
    pending_sources: list[str] = field(default_factory=list)
    #: Stems of the removed source pages that no surviving source page shares.
    removed_slugs: list[str] = field(default_factory=list)
    #: ``norm_page_key`` of each removed slug no surviving page answers to —
    #: the only link targets that become dangling and get unlinked.
    delink_keys: list[str] = field(default_factory=list)
    #: Live pages (outside ``wiki/archive/``) that cite a removed slug.
    citing_pages: list[PageEdit] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not (self.raw_docs or self.state_keys or self.source_pages
                    or self.pending_sources)

    @property
    def pages_to_archive(self) -> list[PageEdit]:
        return [e for e in self.citing_pages if e.archive]


def _archivable(rel: Path) -> bool:
    """True for a curated page that may move to ``wiki/archive/``.

    Decided from the ``wiki/``-relative path alone, so system and navigation
    pages (``index.md``, ``hot.md``, ``_context.md``, …) and everything under
    ``sources/`` are never archived.
    """
    return (
        len(rel.parts) >= 2
        and rel.parts[0] in _ARCHIVABLE_DIRS
        and not rel.name.startswith("_")
        and not is_system_file(rel.name)
    )


def _drop_link_only_items(text: str, keys: set[str]) -> tuple[str, int]:
    """Remove list items whose whole content is a wikilink to one of ``keys``.

    ``keys`` are :func:`norm_page_key` values; ``[[slug]]``, ``[[slug|label]]``
    and ``[[slug#anchor]]`` all match. Lines inside fenced code blocks are left
    alone. Returns the new text and the number of items dropped.
    """
    kept: list[str] = []
    dropped = 0
    in_fence = False
    for line in text.splitlines(keepends=True):
        body = line.rstrip("\r\n")
        if _CODE_FENCE_RE.match(body):
            in_fence = not in_fence
        elif not in_fence:
            m = _LIST_ONLY_LINK_RE.match(body)
            if m and norm_page_key(strip_anchor(m.group(1))) in keys:
                dropped += 1
                continue
        kept.append(line)
    return "".join(kept), dropped


def _edit_page(
    path: Path,
    rel: Path,
    text: str,
    slugs: set[str],
    link_keys: set[str],
) -> tuple[str, PageEdit]:
    """Apply the removal to one page's text; returns the new text + a tally.

    The single code path behind both the dry-run preview and the real run, so
    what is reported is what is written.
    """
    edit = PageEdit(path=path, rel=rel)
    new_text = text
    if link_keys:
        new_text, edit.items_dropped = _drop_link_only_items(new_text, link_keys)
        new_text, counts = rewrite_wikilinks(new_text, dict.fromkeys(link_keys))
        edit.links_unlinked = sum(counts.values())
    before = parse_sources_field(parse_frontmatter(new_text)[0].get("sources"))
    if before and slugs:
        new_text = rewrite_sources_line(new_text, slugs)
        after = parse_sources_field(parse_frontmatter(new_text)[0].get("sources"))
        edit.sources_trimmed = len(before) - len(after)
        edit.sources_emptied = not after
    return new_text, edit


def _changed(edit: PageEdit) -> bool:
    return bool(edit.sources_trimmed or edit.links_unlinked or edit.items_dropped)


def _matches(rel: Path, selector: str) -> bool:
    """True when ``selector`` (a glob) selects this raw doc.

    Matched against the project dir (first path segment) and the rel-path,
    with and without the ``.md`` suffix — so ``<project>*`` takes whole
    projects and ``proj/slug`` takes one doc.

    The bare file stem is deliberately NOT an axis: globbing it crosses
    project boundaries (``notes`` would select both ``taxes/notes.md`` and
    ``legal/notes.md``), which is the wrong default for a cascade that
    deletes. Target a single doc with its ``<project>/<stem>`` path.
    """
    project = rel.parts[0] if rel.parts else ""
    return (
        fnmatch.fnmatch(project, selector)
        or fnmatch.fnmatch(rel.as_posix(), selector)
        or fnmatch.fnmatch(rel.with_suffix("").as_posix(), selector)
    )


def _state_key(rel: Path) -> str:
    """The ``synth.files`` key the pipeline writes for a raw doc."""
    return "docs::" + rel.as_posix()


def _source_file_key(rel: Path) -> str:
    """The ``source_file`` frontmatter value a doc's page claims."""
    return "raw/docs/" + rel.as_posix()


def _owned_by(page: Path, source_key: str) -> bool:
    """True when ``page`` is safe to delete as ``source_key``'s derivative.

    Path derivation alone is not ownership: sessions write into the same
    ``wiki/sources/<project>/<date>-<slug>.md`` namespace, and the part-page
    glob (``<name>--part-*.md``) can also catch a differently-named doc's
    page. So a page that names a DIFFERENT ``source_file`` is left alone.
    An empty value still counts as owned: synth stamps every doc page with
    ``raw/docs/<rel>`` as of #307, but a page an older release wrote has
    nothing to claim with and must stay removable.
    """
    try:
        meta, _body = parse_frontmatter(page.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        return False
    claimed = str(meta.get("source_file", "")).strip()
    return claimed in ("", source_key)


def _source_pages_for(raw_doc: Path, wiki_sources: Path) -> list[Path]:
    """Every ``wiki/sources`` page derived from one raw doc, by path.

    Reuses the pipeline's own filename derivation + part-page discovery,
    so a doc that synth split into ``--part-NN`` pages is fully covered.
    """
    try:
        meta, _body = parse_frontmatter(raw_doc.read_text(encoding="utf-8"))
    except OSError:
        meta = {}
    project = str(meta.get("project") or "docs")
    filename = synth_page_filename(meta, raw_doc.stem)
    return source_page_paths(wiki_sources / project, filename, is_doc=True)


def _scan_by_source_file(wiki_sources: Path, keys: set[str]) -> list[Path]:
    """Pages whose ``source_file`` frontmatter is one of ``keys`` (#catches
    hand-placed pages under an arbitrary folder/name)."""
    found: list[Path] = []
    if not keys or not wiki_sources.is_dir():
        return found
    for p in wiki_sources.rglob("*.md"):
        if p.name.startswith("_"):
            continue
        try:
            meta, _body = parse_frontmatter(p.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            continue
        if str(meta.get("source_file", "")).strip() in keys:
            found.append(p)
    return found


def _live_pages(wiki_dir: Path, skip: set[Path]) -> list[tuple[Path, str]]:
    """``(path, text)`` of every readable page outside ``wiki/archive/``.

    ``skip`` holds pages about to be deleted. The append-only log and its
    yearly archives are skipped too: history is never rewritten.
    """
    pages: list[tuple[Path, str]] = []
    if not wiki_dir.is_dir():
        return pages
    for path in sorted(wiki_dir.rglob("*.md")):
        if (
            not path.is_file()
            or path in skip
            or is_archived_path(path.relative_to(wiki_dir).parts)
            or is_log_page(path.name)
        ):
            continue
        try:
            pages.append((path, path.read_text(encoding="utf-8")))
        except (OSError, UnicodeDecodeError):
            continue
    return pages


def _scan_citing_pages(
    wiki_dir: Path, source_pages: list[Path],
) -> tuple[list[str], list[str], list[PageEdit]]:
    """``(removed_slugs, delink_keys, citing_pages)`` for the planned deletions.

    A slug is dropped from the removal when another source page still
    resolves under it (two projects can share a stem). A link key is dropped
    when any surviving page still answers to it — by stem or under
    ``## Aliases`` — so a ``[[name]]`` that a project or entity page also
    answers to is never unlinked.
    """
    planned = set(source_pages)
    sources_dir = wiki_dir / "sources"
    survivors = (
        {p.stem.casefold() for p in sources_dir.rglob("*.md") if p not in planned}
        if sources_dir.is_dir() else set()
    )
    slugs = sorted({p.stem for p in source_pages if p.stem.casefold() not in survivors})
    if not slugs:
        return [], [], []

    pages = _live_pages(wiki_dir, planned)
    owned: set[str] = set()
    for path, text in pages:
        owned.add(norm_page_key(path.stem))
        owned.update(norm_page_key(a) for a in parse_page_aliases(text))
    keys = sorted({norm_page_key(s) for s in slugs} - owned - {""})

    citing: list[PageEdit] = []
    for path, text in pages:
        rel = path.relative_to(wiki_dir)
        _new, edit = _edit_page(path, rel, text, set(slugs), set(keys))
        if _changed(edit):
            citing.append(edit)
    return slugs, keys, citing


def build_remove_plan(
    vault_root: Path,
    selector: str,
    *,
    state_file: Path | None = None,
) -> RemovePlan:
    """Compute — without touching anything — the full cascade for
    ``selector`` against ``vault_root/raw/docs``.

    ``state_file`` overrides the vault's ``llmwiki-state.json`` (tests);
    only state keys actually present are listed, so a dry-run reports the
    real dangling keys rather than every key it would attempt to pop.
    """

    docs_dir = vault_root / "raw" / "docs"
    wiki_sources = vault_root / "wiki" / "sources"
    plan = RemovePlan(selector=selector, vault_root=vault_root)
    if not docs_dir.is_dir():
        return plan

    synth_state = read_state(state_file).get("synth", {})
    present_keys = set(synth_state.get("files", {}))
    source_file_keys: set[str] = set()
    pages: list[Path] = []
    seen_pages: set[Path] = set()

    for raw_doc in sorted(docs_dir.rglob("*.md")):
        rel = raw_doc.relative_to(docs_dir)
        if not _matches(rel, selector):
            continue
        plan.raw_docs.append(raw_doc)
        key = _state_key(rel)
        if key in present_keys:
            plan.state_keys.append(key)
        src_key = _source_file_key(rel)
        source_file_keys.add(src_key)
        for page in _source_pages_for(raw_doc, wiki_sources):
            if page.exists() and page not in seen_pages and _owned_by(page, src_key):
                seen_pages.add(page)
                pages.append(page)

    for page in _scan_by_source_file(wiki_sources, source_file_keys):
        if page not in seen_pages:
            seen_pages.add(page)
            pages.append(page)

    plan.source_pages = pages
    plan.removed_slugs, plan.delink_keys, plan.citing_pages = _scan_citing_pages(
        vault_root / "wiki", pages,
    )
    # synth.pending is the not-yet-synthesized backlog — a LIST, separate from
    # the synth.files dict. A doc removed before it was ever synthesized has no
    # files key, only a pending entry; dropping just files would strand it
    # pointing at a file that no longer exists.
    plan.pending_sources = sorted({
        str(entry.get("source", ""))
        for entry in synth_state.get("pending", [])
        if isinstance(entry, dict)
        and str(entry.get("source", "")) in source_file_keys
    })
    return plan


def format_plan(plan: RemovePlan) -> str:
    """Human-readable preview of the whole cascade for ``--dry-run``."""
    if plan.is_empty:
        return f"remove: selector {plan.selector!r} matched nothing — nothing to do."
    lines = [
        f"remove: selector {plan.selector!r} would cascade "
        f"{len(plan.raw_docs)} raw doc(s):",
        "",
        "  raw/docs files:",
    ]
    lines += [f"    - {p}" for p in plan.raw_docs]
    lines += ["", "  synth-state keys:"]
    lines += [f"    - {k}" for k in plan.state_keys] or ["    (none)"]
    lines += ["", "  synth pending entries:"]
    lines += [f"    - {s}" for s in plan.pending_sources] or ["    (none)"]
    lines += ["", "  wiki/sources pages:"]
    lines += [f"    - {p}" for p in plan.source_pages] or ["    (none)"]
    lines += ["", "  citing pages (sources: trimmed, wikilinks to removed pages cleaned):"]
    lines += [f"    - wiki/{e.rel.as_posix()}  ({_describe(e)})" for e in plan.citing_pages] or [
        "    (none)"
    ]
    lines += ["", "  pages to archive (sources: emptied) -> wiki/archive/, names marked settled for harvest:"]
    lines += [f"    - wiki/{e.rel.as_posix()}" for e in plan.pages_to_archive] or ["    (none)"]
    lines += [
        "",
        "  then: rewrite the citing pages above (log.md is never rewritten), "
        "rebuild wiki/index.md, append remove log entry.",
    ]
    return "\n".join(lines)


def _describe(edit: PageEdit) -> str:
    bits = []
    if edit.sources_trimmed:
        bits.append(f"{edit.sources_trimmed} source(s) trimmed")
    if edit.items_dropped:
        bits.append(f"{edit.items_dropped} list item(s) dropped")
    if edit.links_unlinked:
        bits.append(f"{edit.links_unlinked} link(s) unlinked")
    if edit.archive:
        bits.append("will archive")
    return ", ".join(bits)


def _summarize_edits(edits: list[PageEdit]) -> str:
    """One-line tally of ``edits`` for the CLI summary and the log entry."""
    return (
        f"{len(edits)} citing page(s): "
        f"{sum(e.sources_trimmed for e in edits)} source(s) trimmed, "
        f"{sum(e.links_unlinked for e in edits)} link(s) unlinked, "
        f"{sum(e.items_dropped for e in edits)} list item(s) dropped, "
        f"{sum(1 for e in edits if e.archive)} page(s) archived"
    )


def _archive_page(page: Path, wiki_dir: Path) -> Path:
    """Move ``page`` to ``wiki/archive/<same relative path>``.

    On a name collision the page lands under a UTC-timestamp folder instead
    (``wiki/archive/<stamp>/<relative path>``), so nothing already archived is
    overwritten.
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


#: Ledger reason for a page ``remove`` archived because its last source went.
_DISMISSAL_REASON = "archived by remove: last citing source removed"


def _record_dismissal(original: Path, dest: Path, wiki_dir: Path) -> None:
    """Settle the archived page's name(s) in the dismissal ledger (#277).

    One row per distinct ``norm_page_key`` of the filename stem and the
    frontmatter ``title``. ``stub`` follows the ledger's convention — the
    archived file relative to ``wiki/archive/candidates/`` — so a candidate
    that lands there is a bare ``<name>.md`` and any other archived page reads
    ``../<folder>/<name>.md`` (or ``../<stamp>/…`` after a collision).
    """
    stub = Path(os.path.relpath(dest, archive_candidates_dir(wiki_dir))).as_posix()
    names = [original.stem]
    try:
        title = parse_frontmatter(dest.read_text(encoding="utf-8"))[0].get("title")
    except (OSError, UnicodeDecodeError):
        title = None
    if title and norm_page_key(str(title)) != norm_page_key(original.stem):
        names.append(str(title))
    for name in names:
        if norm_page_key(name):
            upsert_dismissal(wiki_dir, name=name, stub=stub, reason=_DISMISSAL_REASON)


def _apply_page_edits(plan: RemovePlan) -> tuple[list[PageEdit], int]:
    """Rewrite every citing page, archive the ones left unsourced, and unlink
    inbound links to what was archived. Returns the edits actually made and the
    inbound links unlinked."""
    wiki_dir = plan.vault_root / "wiki"
    slugs, keys = set(plan.removed_slugs), set(plan.delink_keys)
    done: list[PageEdit] = []
    for planned in plan.citing_pages:
        try:
            text = planned.path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        new_text, edit = _edit_page(planned.path, planned.rel, text, slugs, keys)
        if not _changed(edit):
            continue
        planned.path.write_text(new_text, encoding="utf-8")
        done.append(edit)

    archived = [e for e in done if e.archive]
    if archived:
        # Materialise the ledger before anything moves, so the first upsert is
        # an incremental update rather than a rebuild from the archive.
        if not ledger_path(wiki_dir).is_file():
            save_ledger(wiki_dir, load_ledger(wiki_dir))
    for edit in archived:
        dest = _archive_page(edit.path, wiki_dir)
        _record_dismissal(edit.path, dest, wiki_dir)
    inbound = 0
    if archived:
        # A name another live page still answers to keeps its links. The same
        # page set (no archive/, no log pages) drives both the ownership check
        # and the rewrite, so append-only history is never touched.
        live = _live_pages(wiki_dir, set())
        owned: set[str] = set()
        for path, text in live:
            owned.add(norm_page_key(path.stem))
            owned.update(norm_page_key(a) for a in parse_page_aliases(text))
        gone = {norm_page_key(e.path.stem) for e in archived} - owned - {""}
        if gone:
            targets = dict.fromkeys(gone)
            for path, text in live:
                new_text, counts = rewrite_wikilinks(text, targets, self_stem=path.stem)
                if counts and new_text != text:
                    path.write_text(new_text, encoding="utf-8")
                    inbound += sum(counts.values())
    return done, inbound


def execute_remove_plan(
    plan: RemovePlan,
    *,
    state_file: Path | None = None,
) -> dict[str, int]:
    """Carry out ``plan``: unlink raw docs + source pages, drop their
    synth-state keys, clean up the pages that cited the removed ones (trim
    ``sources:``, drop or unlink wikilinks, archive pages left unsourced),
    then refresh the wiki index and log. A no-op plan changes nothing and
    logs nothing.

    Raises :class:`RemoveIncompleteError` when a raw doc could not be
    unlinked, BEFORE any derived page or state key is touched — a vault
    left holding the raw file but missing its page and state entry is
    worse than one that was never touched."""

    result = {
        "raw_docs": 0,
        "source_pages": 0,
        "state_keys": 0,
        "pending_entries": 0,
        "citing_pages": 0,
        "sources_trimmed": 0,
        "links_unlinked": 0,
        "list_items_dropped": 0,
        "pages_archived": 0,
    }
    if plan.is_empty:
        return result

    removed_raw = remove_raw_docs(plan.raw_docs)
    if len(removed_raw) != len(plan.raw_docs):
        stuck = [str(p) for p in plan.raw_docs if p.exists()]
        shown = ", ".join(stuck[:3]) + (" …" if len(stuck) > 3 else "")
        raise RemoveIncompleteError(
            f"removed {len(removed_raw)} of {len(plan.raw_docs)} raw doc(s); "
            f"could not delete {shown} — derived pages and synth state were "
            "left untouched"
        )
    result["raw_docs"] = len(removed_raw)
    result["source_pages"] = len(remove_raw_docs(plan.source_pages))
    result["state_keys"] = len(plan.state_keys)
    result["pending_entries"] = len(plan.pending_sources)

    if plan.state_keys or plan.pending_sources:
        drop_keys = set(plan.state_keys)
        drop_pending = set(plan.pending_sources)

        def _mut(state: dict) -> dict:
            synth = state.setdefault("synth", {})
            files = synth.setdefault("files", {})
            for key in drop_keys:
                files.pop(key, None)
            pending = synth.get("pending")
            if drop_pending and isinstance(pending, list):
                kept = [
                    e for e in pending
                    if not (isinstance(e, dict)
                            and str(e.get("source", "")) in drop_pending)
                ]
                synth["pending"] = kept
                if isinstance(synth.get("pending_total"), int):
                    synth["pending_total"] = len(kept)
            return state

        update_state(_mut, state_file)

    # Trim what the surviving pages said about the removed source pages (#277).
    edits, inbound = _apply_page_edits(plan)
    result["citing_pages"] = len(edits)
    result["sources_trimmed"] = sum(e.sources_trimmed for e in edits)
    result["links_unlinked"] = sum(e.links_unlinked for e in edits) + inbound
    result["list_items_dropped"] = sum(e.items_dropped for e in edits)
    result["pages_archived"] = sum(1 for e in edits if e.archive)

    # No backlink pruning here: `backlinks.prune_all` strips the block from
    # EVERY page in the wiki, and nothing regenerates them (`inject_all` has
    # no caller), so calling it would destroy backlinks wiki-wide as a side
    # effect of removing one project.
    wiki_dir = plan.vault_root / "wiki"
    _rebuild_index(wiki_dir)
    _append_log(
        f"{result['raw_docs']} docs ({plan.selector})",
        log_path=wiki_dir / "log.md",
        operation="remove",
        details={"processed": _summarize_edits(edits)} if edits else None,
    )
    return result
