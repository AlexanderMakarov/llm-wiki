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
them: by the path :func:`expected_source_page` derives (doc pages carry
an empty ``source_file``, so path is the only handle on them) AND by the
``source_file: raw/docs/<rel>`` frontmatter key a hand-placed page may
claim (arbitrary folder/name). Both are unioned so neither escapes.
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from pathlib import Path

from llmwiki._frontmatter import parse_frontmatter
from llmwiki.add_doc import remove_raw_docs
from llmwiki.synth.pipeline import (
    _append_log,
    _rebuild_index,
    source_page_paths,
    synth_page_filename,
)
from llmwiki.state_store import read_state, update_state

__all__ = [
    "RemoveIncompleteError",
    "RemovePlan",
    "build_remove_plan",
    "format_plan",
    "execute_remove_plan",
]


class RemoveIncompleteError(RuntimeError):
    """A raw doc could not be unlinked, so the cascade stopped before
    touching anything derived from it."""


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

    @property
    def is_empty(self) -> bool:
        return not (self.raw_docs or self.state_keys or self.source_pages
                    or self.pending_sources)


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
    Synthesized doc pages carry an empty ``source_file``, which is why an
    empty value still counts as owned.
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
    lines += [
        "",
        "  then: prune backlinks, rebuild wiki/index.md, append remove log entry.",
    ]
    return "\n".join(lines)


def execute_remove_plan(
    plan: RemovePlan,
    *,
    state_file: Path | None = None,
) -> dict[str, int]:
    """Carry out ``plan``: unlink raw docs + source pages, drop their
    synth-state keys, then refresh the derived indexes (backlinks, wiki
    index, log). A no-op plan changes nothing and logs nothing.

    Raises :class:`RemoveIncompleteError` when a raw doc could not be
    unlinked, BEFORE any derived page or state key is touched — a vault
    left holding the raw file but missing its page and state entry is
    worse than one that was never touched."""

    result = {
        "raw_docs": 0,
        "source_pages": 0,
        "state_keys": 0,
        "pending_entries": 0,
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
    )
    return result
