"""Offline ``synth.files`` backfill when wiki pages already cover raw sources.

Used by ``migrate topic-kinds`` (#174) and ``scripts/reconcile_synth_state_from_wiki.py``
(#255 maintainer / Pages workflow).
"""

from __future__ import annotations

from pathlib import Path

from llmwiki._frontmatter import is_subagent, parse_frontmatter
from llmwiki.synth.pipeline import (
    _load_state,
    _save_state,
    page_is_stub,
    page_needs_topics_rewrite,
    refresh_synth_pending,
    source_page_paths,
    synth_page_filename,
)


def _relative(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def backfill_synth_state_from_wiki_pages(
    *,
    vault: Path,
    dry_run: bool = False,
) -> tuple[int, list[str]]:
    """Upsert ``synth.files`` for raw rows with real, rewrite-clear wiki pages.

    After #163, ``source_synth_is_done`` requires a fresh-enough mtime in state;
    pages on disk alone do not count. This pass records each eligible raw
    session/doc's current mtime when its derived wiki target(s) exist and are
    non-stub / not topics-pending — the same eligibility checks as
    ``migrate topic-kinds`` (which may stamp Connections first, then run this).
    Shared synth filenames get an entry per raw file, not only the page's
    ``source_file``.

    Returns ``(upsert_count, errors)``.
    """
    vault = Path(vault).expanduser().resolve()
    wiki = vault / "wiki"
    sources_out = wiki / "sources"
    state_file = vault / "llmwiki-state.json"
    errors: list[str] = []
    if not sources_out.is_dir():
        return 0, errors

    try:
        state = _load_state(state_file)
    except (OSError, ValueError, TypeError) as exc:
        return 0, [f"state load: {exc}"]

    updates: dict[str, float] = {}

    sessions_root = vault / "raw" / "sessions"
    if sessions_root.is_dir():
        for path in sorted(sessions_root.rglob("*.md")):
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                errors.append(f"{_relative(path, vault)}: {exc}")
                continue
            meta, _body = parse_frontmatter(text)
            if not isinstance(meta, dict):
                meta = {}
            if is_subagent(meta, path):
                continue
            try:
                rel = str(path.relative_to(sessions_root))
            except ValueError:
                continue
            project = str(meta.get("project") or path.parent.name)
            filename = synth_page_filename(meta, path.stem)
            targets = source_page_paths(
                sources_out / project, filename, is_doc=False
            )
            if not targets:
                continue
            existing = [t for t in targets if t.is_file()]
            if not existing:
                continue
            if any(page_is_stub(t) for t in existing):
                continue
            if any(page_needs_topics_rewrite(t) for t in existing):
                continue
            try:
                updates[rel] = float(path.stat().st_mtime)
            except OSError as exc:
                errors.append(f"{_relative(path, vault)}: {exc}")

    docs_root = vault / "raw" / "docs"
    if docs_root.is_dir():
        for path in sorted(docs_root.rglob("*.md")):
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                errors.append(f"{_relative(path, vault)}: {exc}")
                continue
            meta, _body = parse_frontmatter(text)
            if not isinstance(meta, dict):
                meta = {}
            try:
                doc_rel = str(path.relative_to(docs_root))
            except ValueError:
                continue
            rel = "docs::" + doc_rel
            project = str(meta.get("project") or "docs")
            filename = synth_page_filename(meta, path.stem)
            targets = source_page_paths(
                sources_out / project, filename, is_doc=True
            )
            if not targets:
                continue
            existing = [t for t in targets if t.is_file()]
            if not existing:
                continue
            if any(page_is_stub(t) for t in existing):
                continue
            if any(page_needs_topics_rewrite(t) for t in existing):
                continue
            try:
                updates[rel] = float(path.stat().st_mtime)
            except OSError as exc:
                errors.append(f"{_relative(path, vault)}: {exc}")

    upserts = 0
    for rel, mtime in updates.items():
        prev = state.get(rel)
        if prev is not None and (prev + 1e-6) >= mtime:
            continue
        state[rel] = mtime
        upserts += 1

    if upserts and not dry_run:
        try:
            _save_state(state, state_file)
        except OSError as exc:
            errors.append(f"{state_file.name}: {exc}")
            return upserts, errors
    return upserts, errors


def reconcile_synth_state_from_wiki_pages(*, vault: Path) -> tuple[int, list[str]]:
    """Backfill ``synth.files`` then refresh ``synth.pending`` / pipeline for ``vault``."""
    vault = vault.expanduser().resolve()
    upserts, errors = backfill_synth_state_from_wiki_pages(vault=vault, dry_run=False)
    if errors:
        return upserts, errors
    refresh_synth_pending(
        raw_dir=vault / "raw" / "sessions",
        docs_dir=vault / "raw" / "docs",
        wiki_sources_dir=vault / "wiki" / "sources",
        state_file=vault / "llmwiki-state.json",
    )
    return upserts, errors
