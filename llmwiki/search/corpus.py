"""Corpus walk and capped reads for wiki search (#197).

Lifts ``_iter_scan_files`` / ``_read_capped`` behaviour from
``llmwiki.mcp.server`` into a root-agnostic scan. No import-time state —
every entry point takes explicit paths and caps.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from llmwiki._frontmatter import parse_frontmatter_dict
from llmwiki._system_pages import is_archived_path

# #483: same caps the MCP surface uses today.
DEFAULT_PER_FILE_CAP = 4 * 1024 * 1024  # 4 MiB / file
DEFAULT_AGGREGATE_BUDGET = 50 * 1024 * 1024  # 50 MiB / call


@dataclass(frozen=True, slots=True)
class ScannedPage:
    """One markdown file as search sees it after a capped read."""

    rel_path: str
    path: Path
    text: str
    text_lower: str
    title: str
    meta: dict[str, Any]
    size: int
    is_raw: bool


@dataclass(frozen=True, slots=True)
class CorpusScan:
    """Materialised corpus plus the completeness flags MCP already reports."""

    pages: list[ScannedPage] = field(default_factory=list)
    budget_exhausted: bool = False
    skipped_oversize: int = 0


@dataclass
class CorpusWalkStats:
    """Mutable completeness flags updated while :func:`iter_scanned_pages` runs.

    Callers that pass the iterator into :func:`search_match` can stop early
    when caps fill; these flags then reflect only the prefix of the walk that
    was actually read (same contract as the pre-#197 interleaved MCP loop).
    """

    budget_exhausted: bool = False
    skipped_oversize: int = 0


def read_capped(
    path: Path,
    *,
    remaining_budget: int,
    per_file_cap: int = DEFAULT_PER_FILE_CAP,
) -> tuple[str, int]:
    """Read up to ``min(per_file_cap, remaining_budget)`` bytes of ``path``.

    Returns ``(text, bytes_consumed)``. ``bytes_consumed == 0`` means the
    file was skipped (oversize, over-budget, or unreadable). Oversize files
    are never partial-read — a truncated token at the cap boundary would
    produce confusing hits.
    """
    try:
        size = path.stat().st_size
    except OSError:
        return "", 0
    cap = min(per_file_cap, max(0, remaining_budget))
    if size > per_file_cap:
        return "", 0
    if cap <= 0:
        return "", 0
    try:
        with path.open("rb") as f:
            raw = f.read(cap + 1)
    except OSError:
        return "", 0
    if len(raw) > cap:
        return "", 0
    try:
        return raw.decode("utf-8", errors="replace"), len(raw)
    except Exception:
        return "", 0


def iter_scan_files(
    roots: Iterable[Path],
    *,
    cold_storage_root: Path | None = None,
) -> Iterator[Path]:
    """Yield every ``.md`` under ``roots`` as one flat sequence.

    ``cold_storage_root`` names the wiki root whose ``archive/`` subtree is
    withheld (#140). Only that root's archive is cold — a folder named
    ``archive`` under ``raw/`` stays searchable.
    """
    for root in roots:
        if not root.exists():
            continue
        cold = cold_storage_root is not None and root == cold_storage_root
        for path in root.rglob("*.md"):
            if cold and is_archived_path(path.relative_to(root).parts):
                continue
            yield path


def iter_scanned_pages(
    roots: Iterable[Path],
    *,
    content_root: Path,
    cold_storage_root: Path | None = None,
    per_file_cap: int = DEFAULT_PER_FILE_CAP,
    aggregate_budget: int = DEFAULT_AGGREGATE_BUDGET,
    stats: CorpusWalkStats | None = None,
) -> Iterator[ScannedPage]:
    """Yield pages as they are read under byte caps (streaming walk).

    Stops when the aggregate budget is exhausted. Consumers such as
    :func:`~llmwiki.search.engine.search_match` may break out earlier when
    every query is saturated — remaining files are then never opened.
    """
    content_root = content_root.resolve()
    if stats is None:
        stats = CorpusWalkStats()
    budget = aggregate_budget

    for path in iter_scan_files(roots, cold_storage_root=cold_storage_root):
        if budget <= 0:
            stats.budget_exhausted = True
            break
        text, consumed = read_capped(
            path, remaining_budget=budget, per_file_cap=per_file_cap
        )
        if consumed == 0:
            try:
                size = path.stat().st_size
            except OSError:
                continue
            if size > per_file_cap:
                stats.skipped_oversize += 1
            elif size > budget:
                stats.budget_exhausted = True
            continue
        budget -= consumed
        meta = parse_frontmatter_dict(text)
        try:
            rel_path = str(path.resolve().relative_to(content_root))
        except ValueError:
            rel_path = str(path)
        title = str(meta.get("title", "") or "").strip()
        is_raw = rel_path.replace("\\", "/").startswith("raw/")
        yield ScannedPage(
            rel_path=rel_path,
            path=path,
            text=text,
            text_lower=text.lower(),
            title=title,
            meta=meta,
            size=consumed,
            is_raw=is_raw,
        )


def scan_corpus(
    roots: Iterable[Path],
    *,
    content_root: Path,
    cold_storage_root: Path | None = None,
    per_file_cap: int = DEFAULT_PER_FILE_CAP,
    aggregate_budget: int = DEFAULT_AGGREGATE_BUDGET,
) -> CorpusScan:
    """Materialise the full capped walk into a :class:`CorpusScan`.

    Prefer :func:`iter_scanned_pages` when the consumer can stop early (match
    mode). Extract mode and lint still use this list form because ranking /
    findability need the whole readable corpus.
    """
    stats = CorpusWalkStats()
    pages = list(
        iter_scanned_pages(
            roots,
            content_root=content_root,
            cold_storage_root=cold_storage_root,
            per_file_cap=per_file_cap,
            aggregate_budget=aggregate_budget,
            stats=stats,
        )
    )
    return CorpusScan(
        pages=pages,
        budget_exhausted=stats.budget_exhausted,
        skipped_oversize=stats.skipped_oversize,
    )
