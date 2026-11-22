"""Sole owner of ``wiki/archive/candidates/dismissals.json`` (#146 / #326).

Versioned ledger for discarded-candidate decisions (pure dismissals and
merge intents) and durable keep-distinct pairs (#418). Other modules must
not open, parse, or write that path — call the helpers here instead.

When :func:`load_ledger` finds no ledger file but ``wiki/archive/`` exists, it
auto-rebuilds from archived stubs and any legacy sibling ``*.reason.txt``
files (FR6), then persists the result. The rebuild also keeps the names of
pages ``llmwiki remove`` archived outside ``archive/candidates/`` (#277), under
:data:`REMOVE_DISMISSAL_REASON`. Archive rebuild never invents
``keep_distinct`` rows. With no archive a read returns an empty ledger and
writes nothing. Corrupt JSON fails loud; use
:func:`rebuild_ledger_from_archive` or ``llmwiki migrate dismissal-ledger``
to repair / re-import.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict

from llmwiki._frontmatter import parse_frontmatter
from llmwiki._system_pages import ARCHIVE_FOLDER
from llmwiki.wikilinks import norm_page_key

LEDGER_VERSION = 1
LEDGER_FILENAME = "dismissals.json"
ARCHIVED_CANDIDATES_SUBDIR = "candidates"

#: Ledger reason for a page ``llmwiki remove`` archived because its last
#: source went. A rebuild assigns it to every archived page found outside
#: ``archive/candidates/`` — ``remove`` is the only writer of those paths.
REMOVE_DISMISSAL_REASON = "archived by remove: last citing source removed"

# Legacy reason-file layout (copied for rebuild only — ledger is SoT going forward).
_REASON_FIELD_REASON = "Reason"
_REASON_FIELD_DISCARDED_AT = "Discarded at"
_MERGE_REASON_PREFIX = "merged into "


class DismissalRecord(TypedDict):
    """One pure dismissal in the ledger."""

    key: str
    name: str
    reason: str
    discarded_at: str
    stub: str


class MergeRecord(TypedDict):
    """One merge intent co-located in the ledger (not a dismissal for near-match)."""

    key: str
    name: str
    into: str
    merged_at: str
    stub: str


class KeepDistinctRecord(TypedDict):
    """One durable keep-distinct pair (unordered page identities)."""

    key: str
    a: str
    b: str
    decided_at: str
    why: str


class DismissalLedger(TypedDict):
    """Versioned dismissals.json payload."""

    version: int
    dismissals: list[DismissalRecord]
    merges: list[MergeRecord]
    keep_distinct: list[KeepDistinctRecord]


def archive_candidates_dir(wiki_dir: Path) -> Path:
    """Return ``wiki/archive/candidates/`` (cold storage for dismissed stubs)."""
    return wiki_dir / ARCHIVE_FOLDER / ARCHIVED_CANDIDATES_SUBDIR


def ledger_path(wiki_dir: Path) -> Path:
    """Absolute path of ``dismissals.json`` under the archive candidates dir."""
    return archive_candidates_dir(wiki_dir) / LEDGER_FILENAME


def empty_ledger() -> DismissalLedger:
    """A fresh version-1 ledger with no decisions."""
    return {
        "version": LEDGER_VERSION,
        "dismissals": [],
        "merges": [],
        "keep_distinct": [],
    }


def load_ledger(wiki_dir: Path) -> DismissalLedger:
    """Load the ledger, auto-rebuilding from an existing archive when the file is missing.

    Missing file → :func:`rebuild_ledger_from_archive` (imports legacy
    ``*.reason.txt`` + stubs + ``remove``-archived pages, then saves). With no
    ``wiki/archive/`` there is nothing to import, so the read returns an empty
    ledger and writes nothing.
    Present but unreadable / invalid JSON → raises. Wrong schema shape →
    ``ValueError``.
    """
    path = ledger_path(wiki_dir)
    if not path.is_file():
        if not (wiki_dir / ARCHIVE_FOLDER).is_dir():
            return empty_ledger()
        return rebuild_ledger_from_archive(wiki_dir)
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise
    return _coerce_ledger(data)


def save_ledger(wiki_dir: Path, ledger: DismissalLedger) -> None:
    """Persist ``ledger`` atomically (temp file in the same dir + ``os.replace``)."""
    path = ledger_path(wiki_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(ledger, indent=2, ensure_ascii=False) + "\n"
    fd, tmp = tempfile.mkstemp(
        dir=str(path.parent), prefix=".dismissals-", suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
        os.replace(tmp, path)
    finally:
        try:
            if os.path.exists(tmp):
                os.unlink(tmp)
        except OSError:
            pass


def upsert_dismissal(
    wiki_dir: Path,
    *,
    name: str,
    stub: str,
    reason: str = "",
    discarded_at: str | None = None,
    key: str | None = None,
) -> DismissalRecord:
    """Insert or replace a dismissal keyed by ``norm_page_key`` of ``name``.

    ``stub`` is the posix path of the archived markdown relative to
    ``wiki/archive/candidates/``. ``discarded_at`` defaults to UTC now (ISO).
    """
    record_key = key if key is not None else norm_page_key(name)
    if not record_key:
        raise ValueError(f"cannot upsert dismissal with empty key for name={name!r}")
    record: DismissalRecord = {
        "key": record_key,
        "name": name,
        "reason": reason,
        "discarded_at": discarded_at
        if discarded_at is not None
        else datetime.now(UTC).isoformat(),
        "stub": stub,
    }
    ledger = load_ledger(wiki_dir)
    rows = ledger["dismissals"]
    for i, row in enumerate(rows):
        if row["key"] == record_key:
            rows[i] = record
            break
    else:
        rows.append(record)
    save_ledger(wiki_dir, ledger)
    return record


def upsert_merge(
    wiki_dir: Path,
    *,
    name: str,
    into: str,
    stub: str,
    merged_at: str | None = None,
    key: str | None = None,
) -> MergeRecord:
    """Insert or replace a merge intent keyed by ``norm_page_key`` of ``name``.

    ``into`` is the survivor slug. ``stub`` is relative to
    ``wiki/archive/candidates/``. ``merged_at`` defaults to UTC now (ISO).
    """
    record_key = key if key is not None else norm_page_key(name)
    if not record_key:
        raise ValueError(f"cannot upsert merge with empty key for name={name!r}")
    record: MergeRecord = {
        "key": record_key,
        "name": name,
        "into": into,
        "merged_at": merged_at
        if merged_at is not None
        else datetime.now(UTC).isoformat(),
        "stub": stub,
    }
    ledger = load_ledger(wiki_dir)
    rows = ledger["merges"]
    for i, row in enumerate(rows):
        if row["key"] == record_key:
            rows[i] = record
            break
    else:
        rows.append(record)
    save_ledger(wiki_dir, ledger)
    return record


def iter_dismissals(wiki_dir: Path) -> Iterator[DismissalRecord]:
    """Yield dismissal records from the ledger (see :func:`load_ledger` when missing)."""
    yield from load_ledger(wiki_dir)["dismissals"]


def iter_merges(wiki_dir: Path) -> Iterator[MergeRecord]:
    """Yield merge records from the ledger (see :func:`load_ledger` when missing)."""
    yield from load_ledger(wiki_dir)["merges"]


def upsert_keep_distinct(
    wiki_dir: Path,
    *,
    a: str,
    b: str,
    why: str = "",
    decided_at: str | None = None,
    key: str | None = None,
) -> KeepDistinctRecord:
    """Insert or replace a keep-distinct pair keyed by sorted ``norm_page_key`` ids.

    ``a`` / ``b`` are display names; the durable ``key`` is
    ``norm_page_key(lo)|norm_page_key(hi)`` (lexicographic on folded keys).
    Display fields are stored in that same order. ``decided_at`` defaults to
    UTC now (ISO).
    """
    record_key, name_a, name_b = _keep_distinct_pair_names(a, b)
    if key is not None:
        record_key = key
    if not record_key:
        raise ValueError(
            f"cannot upsert keep-distinct with empty key for a={a!r} b={b!r}"
        )
    record: KeepDistinctRecord = {
        "key": record_key,
        "a": name_a,
        "b": name_b,
        "decided_at": decided_at
        if decided_at is not None
        else datetime.now(UTC).isoformat(),
        "why": why,
    }
    ledger = load_ledger(wiki_dir)
    rows = ledger["keep_distinct"]
    for i, row in enumerate(rows):
        if row["key"] == record_key:
            rows[i] = record
            break
    else:
        rows.append(record)
    save_ledger(wiki_dir, ledger)
    return record


def iter_keep_distinct(wiki_dir: Path) -> Iterator[KeepDistinctRecord]:
    """Yield keep-distinct records from the ledger (see :func:`load_ledger`)."""
    yield from load_ledger(wiki_dir)["keep_distinct"]


def is_keep_distinct_pair(wiki_dir: Path, a: str, b: str) -> bool:
    """Return True when the ledger records ``a`` and ``b`` as keep-distinct.

    Pair identity is unordered: ``(a, b)`` and ``(b, a)`` share one key.
    Empty or same-folded names are never keep-distinct.
    """
    try:
        pair_key, _, _ = _keep_distinct_pair_names(a, b)
    except ValueError:
        return False
    return any(row["key"] == pair_key for row in load_ledger(wiki_dir)["keep_distinct"])


def build_ledger_from_archive(wiki_dir: Path) -> DismissalLedger:
    """Scan the archive (+ legacy ``*.reason.txt``) into a ledger — no write.

    Walks ``wiki/archive/candidates/**/*.md`` first. A sibling
    ``<stem>.reason.txt`` whose ``Reason:`` value is ``merged into <slug>``
    becomes a merge entry; any other reason (including missing reason file)
    becomes a dismissal. Then walks the rest of ``wiki/archive/`` — pages
    ``llmwiki remove`` archived (#277) — and records a dismissal under
    :data:`REMOVE_DISMISSAL_REASON` for the filename stem and the frontmatter
    ``title`` of each, with ``stub`` relative to ``archive/candidates/``
    (``../entities/Foo.md``), so a rebuild keeps those names settled.
    First occurrence of each ``norm_page_key`` wins (candidates before
    ``remove`` pages, each in sorted walk order). Callers that want the file
    on disk use :func:`rebuild_ledger_from_archive` or :func:`save_ledger`.
    """
    root = archive_candidates_dir(wiki_dir)
    dismissals: list[DismissalRecord] = []
    merges: list[MergeRecord] = []
    seen_dismiss: set[str] = set()
    seen_merge: set[str] = set()

    if root.is_dir():
        for path in sorted(root.rglob("*.md")):
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            meta, _ = parse_frontmatter(text)
            title = meta.get("title")
            name = (str(title).strip() if title else "") or path.stem
            key = norm_page_key(name)
            if not key:
                continue
            stub = path.relative_to(root).as_posix()
            reason_path = path.with_suffix(".reason.txt")
            reason_text = ""
            discarded_at = ""
            if reason_path.is_file():
                try:
                    reason_body = reason_path.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    reason_body = ""
                reason_text = _reason_field_value(reason_body, _REASON_FIELD_REASON)
                discarded_at = _reason_field_value(
                    reason_body, _REASON_FIELD_DISCARDED_AT,
                )
            into = _parse_merge_reason(reason_text)
            if into:
                if key in seen_merge:
                    continue
                seen_merge.add(key)
                merges.append({
                    "key": key,
                    "name": name,
                    "into": into,
                    "merged_at": discarded_at,
                    "stub": stub,
                })
                continue
            if key in seen_dismiss:
                continue
            seen_dismiss.add(key)
            dismissals.append({
                "key": key,
                "name": name,
                "reason": reason_text,
                "discarded_at": discarded_at,
                "stub": stub,
            })

    archive_root = wiki_dir / ARCHIVE_FOLDER
    if archive_root.is_dir():
        for path in sorted(archive_root.rglob("*.md")):
            if path.is_relative_to(root):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            title = parse_frontmatter(text)[0].get("title")
            stub = Path(os.path.relpath(path, root)).as_posix()
            for name in (path.stem, str(title).strip() if title else ""):
                key = norm_page_key(name)
                if not key or key in seen_dismiss:
                    continue
                seen_dismiss.add(key)
                dismissals.append({
                    "key": key,
                    "name": name,
                    "reason": REMOVE_DISMISSAL_REASON,
                    "discarded_at": "",
                    "stub": stub,
                })

    return {
        "version": LEDGER_VERSION,
        "dismissals": dismissals,
        "merges": merges,
        # Keep-distinct is operator SoT only — never invent from archive stubs.
        "keep_distinct": [],
    }


def rebuild_ledger_from_archive(wiki_dir: Path) -> DismissalLedger:
    """Rebuild the ledger from archived stubs, legacy ``*.reason.txt`` files and
    ``remove``-archived pages.

    Same scan as :func:`build_ledger_from_archive`, then persists the result.
    Existing ``keep_distinct`` rows are preserved (rebuild never invents them
    from the archive). Idempotent for dismissals/merges when the archive is
    unchanged.
    """
    ledger = build_ledger_from_archive(wiki_dir)
    path = ledger_path(wiki_dir)
    if path.is_file():
        try:
            existing = _coerce_ledger(
                json.loads(path.read_text(encoding="utf-8"))
            )
            ledger["keep_distinct"] = existing["keep_distinct"]
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
            pass
    save_ledger(wiki_dir, ledger)
    return ledger


# ─── internals ─────────────────────────────────────────────────────────


def _reason_field(label: str, value: object) -> str:
    """One ``<label>: <value>`` line matching legacy reason-file layout."""
    return f"{label}: {value}"


def _reason_field_value(text: str, label: str) -> str:
    """Value ``label`` carries in a reason file, ``""`` when absent."""
    prefix = _reason_field(label, "")
    for line in text.splitlines():
        if line.startswith(prefix):
            return line[len(prefix):].strip()
    return ""


def _parse_merge_reason(reason: str) -> str:
    """Survivor slug from a ``merged into …`` reason, else ``""``."""
    if not reason.startswith(_MERGE_REASON_PREFIX):
        return ""
    return reason[len(_MERGE_REASON_PREFIX):].strip()


def _keep_distinct_pair_names(a: str, b: str) -> tuple[str, str, str]:
    """Stable unordered pair: ``(key, display_lo, display_hi)``.

    ``key`` is ``norm_page_key(lo)|norm_page_key(hi)`` with folded keys sorted.
    Display names follow that order. Raises ``ValueError`` when either fold is
    empty or both fold to the same identity.
    """
    ka, kb = norm_page_key(a), norm_page_key(b)
    if not ka or not kb:
        raise ValueError(
            f"cannot form keep-distinct key for a={a!r} b={b!r}"
        )
    if ka == kb:
        raise ValueError(
            f"keep-distinct requires two distinct page identities, got a={a!r} b={b!r}"
        )
    if ka <= kb:
        return f"{ka}|{kb}", a, b
    return f"{kb}|{ka}", b, a


def _coerce_ledger(data: object) -> DismissalLedger:
    """Validate and normalise a JSON payload into :class:`DismissalLedger`."""
    if not isinstance(data, dict):
        raise ValueError("dismissals.json must be a JSON object")
    version = data.get("version", LEDGER_VERSION)
    if version != LEDGER_VERSION:
        raise ValueError(
            f"unsupported dismissals.json version: {version!r} "
            f"(expected {LEDGER_VERSION})"
        )
    dismissals_raw = data.get("dismissals", [])
    merges_raw = data.get("merges", [])
    keep_distinct_raw = data.get("keep_distinct", [])
    if (
        not isinstance(dismissals_raw, list)
        or not isinstance(merges_raw, list)
        or not isinstance(keep_distinct_raw, list)
    ):
        raise ValueError(
            "dismissals.json dismissals/merges/keep_distinct must be arrays"
        )
    return {
        "version": LEDGER_VERSION,
        "dismissals": [_coerce_dismissal(row) for row in dismissals_raw],
        "merges": [_coerce_merge(row) for row in merges_raw],
        "keep_distinct": [
            _coerce_keep_distinct(row) for row in keep_distinct_raw
        ],
    }


def _coerce_dismissal(row: object) -> DismissalRecord:
    if not isinstance(row, dict):
        raise ValueError("dismissal entry must be an object")
    return {
        "key": str(row.get("key") or ""),
        "name": str(row.get("name") or ""),
        "reason": str(row.get("reason") or ""),
        "discarded_at": str(row.get("discarded_at") or ""),
        "stub": str(row.get("stub") or ""),
    }


def _coerce_merge(row: object) -> MergeRecord:
    if not isinstance(row, dict):
        raise ValueError("merge entry must be an object")
    return {
        "key": str(row.get("key") or ""),
        "name": str(row.get("name") or ""),
        "into": str(row.get("into") or ""),
        "merged_at": str(row.get("merged_at") or ""),
        "stub": str(row.get("stub") or ""),
    }


def _coerce_keep_distinct(row: object) -> KeepDistinctRecord:
    if not isinstance(row, dict):
        raise ValueError("keep_distinct entry must be an object")
    a = str(row.get("a") or "")
    b = str(row.get("b") or "")
    raw_key = str(row.get("key") or "")
    if raw_key:
        key = raw_key
    else:
        try:
            key, a, b = _keep_distinct_pair_names(a, b)
        except ValueError:
            key = ""
    return {
        "key": key,
        "a": a,
        "b": b,
        "decided_at": str(row.get("decided_at") or ""),
        "why": str(row.get("why") or ""),
    }
