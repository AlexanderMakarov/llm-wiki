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
from llmwiki.add_doc import expected_source_page, remove_raw_docs
from llmwiki.synth.pipeline import (
    _append_log,
    _rebuild_index,
    source_page_paths,
    synth_page_filename,
)

__all__ = [
    "RemovePlan",
    "build_remove_plan",
    "format_plan",
    "execute_remove_plan",
]


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

    @property
    def is_empty(self) -> bool:
        return not (self.raw_docs or self.state_keys or self.source_pages)


def _matches(rel: Path, selector: str) -> bool:
    """True when ``selector`` (a glob) selects this raw doc.

    Tried against the project dir (first path segment), the file stem,
    and the full posix rel-path, so a bare project name (``ip-v-armenii``),
    a slug glob (``ip-v-armenii*``), or a nested path all land the doc.
    """
    project = rel.parts[0] if rel.parts else ""
    posix = rel.as_posix()
    return (
        fnmatch.fnmatch(project, selector)
        or fnmatch.fnmatch(rel.stem, selector)
        or fnmatch.fnmatch(posix, selector)
    )


def _state_key(rel: Path) -> str:
    """The ``synth.files`` key the pipeline writes for a raw doc."""
    return "docs::" + rel.as_posix()


def _source_file_key(rel: Path) -> str:
    """The ``source_file`` frontmatter value a doc's page claims."""
    return "raw/docs/" + rel.as_posix()


def _source_pages_for(
    raw_doc: Path, docs_dir: Path, wiki_sources: Path
) -> list[Path]:
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
    from llmwiki.state_store import read_state

    docs_dir = vault_root / "raw" / "docs"
    wiki_sources = vault_root / "wiki" / "sources"
    plan = RemovePlan(selector=selector, vault_root=vault_root)
    if not docs_dir.is_dir():
        return plan

    present_keys = set(read_state(state_file).get("synth", {}).get("files", {}))
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
        source_file_keys.add(_source_file_key(rel))
        for page in _source_pages_for(raw_doc, docs_dir, wiki_sources):
            if page.exists() and page not in seen_pages:
                seen_pages.add(page)
                pages.append(page)

    for page in _scan_by_source_file(wiki_sources, source_file_keys):
        if page not in seen_pages:
            seen_pages.add(page)
            pages.append(page)

    plan.source_pages = pages
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
    index, log). A no-op plan changes nothing and logs nothing."""
    from llmwiki.backlinks import prune_all
    from llmwiki.state_store import update_state

    result = {
        "raw_docs": 0,
        "source_pages": 0,
        "state_keys": len(plan.state_keys),
    }
    if plan.is_empty:
        return result

    result["raw_docs"] = len(remove_raw_docs(plan.raw_docs))
    result["source_pages"] = len(remove_raw_docs(plan.source_pages))

    if plan.state_keys:
        drop = set(plan.state_keys)

        def _mut(state: dict) -> dict:
            files = state.setdefault("synth", {}).setdefault("files", {})
            for key in drop:
                files.pop(key, None)
            return state

        update_state(_mut, state_file)

    wiki_dir = plan.vault_root / "wiki"
    prune_all(wiki_dir)
    _rebuild_index(wiki_dir)
    _append_log(
        f"{len(plan.raw_docs)} docs ({plan.selector})",
        log_path=wiki_dir / "log.md",
        operation="remove",
    )
    return result
