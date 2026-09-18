"""Corpus walk and capped reads for wiki search (#197).

Lifts ``_iter_scan_files`` / ``_read_capped`` behaviour from
``llmwiki.mcp.server`` into a root-agnostic scan. No import-time state —
every entry point takes explicit paths and caps.
"""

from __future__ import annotations

import os
import stat
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
    cap = min(per_file_cap, max(0, remaining_budget))
    if cap <= 0:
        return "", 0
    flags = os.O_RDONLY
    for name in ("O_BINARY", "O_CLOEXEC", "O_NOFOLLOW", "O_NONBLOCK"):
        flags |= getattr(os, name, 0)
    fd = -1
    try:
        fd = os.open(path, flags)
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > per_file_cap:
            return "", 0
        with os.fdopen(fd, "rb") as f:
            fd = -1  # ownership moved to the file object
            raw = f.read(cap + 1)
    except OSError:
        return "", 0
    finally:
        if fd >= 0:
            os.close(fd)
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
    """Yield every safe ``.md`` under ``roots`` in deterministic order.

    ``cold_storage_root`` names the wiki root whose ``archive/`` subtree is
    withheld (#140). Only that root's archive is cold — a folder named
    ``archive`` under ``raw/`` stays searchable.

    Candidates are resolved and checked before they reach the reader. Final
    symlinks are skipped, and a path reached through a symlinked directory is
    accepted only when its resolved target remains inside the scan root. This
    keeps an untrusted vault from making search read an arbitrary host file.
    """
    for root in roots:
        try:
            resolved_root = root.resolve(strict=True)
        except OSError:
            continue
        if not resolved_root.is_dir():
            continue
        cold = False
        if cold_storage_root is not None:
            try:
                cold = resolved_root == cold_storage_root.resolve(strict=True)
            except OSError:
                pass
        for candidate in sorted(resolved_root.rglob("*.md")):
            try:
                relative = candidate.relative_to(resolved_root)
            except ValueError:
                continue
            if cold and is_archived_path(relative.parts):
                continue
            try:
                if candidate.is_symlink():
                    continue
                path = candidate.resolve(strict=True)
                path.relative_to(resolved_root)
            except (OSError, ValueError):
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
