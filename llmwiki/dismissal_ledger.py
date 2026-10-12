"""Sole owner of ``wiki/archive/candidates/dismissals.json`` (#146 / #326).

Versioned ledger for discarded-candidate decisions (pure dismissals and
merge intents). Other modules must not open, parse, or write that path —
call the helpers here instead.

When :func:`load_ledger` finds no ledger file, it auto-rebuilds from
archived stubs and any legacy sibling ``*.reason.txt`` files (FR6), then
persists the result. Corrupt JSON fails loud; use
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


class DismissalLedger(TypedDict):
    """Versioned dismissals.json payload."""

    version: int
    dismissals: list[DismissalRecord]
    merges: list[MergeRecord]


def archive_candidates_dir(wiki_dir: Path) -> Path:
    """Return ``wiki/archive/candidates/`` (cold storage for dismissed stubs)."""
    return wiki_dir / ARCHIVE_FOLDER / ARCHIVED_CANDIDATES_SUBDIR


def ledger_path(wiki_dir: Path) -> Path:
    """Absolute path of ``dismissals.json`` under the archive candidates dir."""
    return archive_candidates_dir(wiki_dir) / LEDGER_FILENAME


def empty_ledger() -> DismissalLedger:
    """A fresh version-1 ledger with no decisions."""
    return {"version": LEDGER_VERSION, "dismissals": [], "merges": []}


def load_ledger(wiki_dir: Path) -> DismissalLedger:
    """Load the ledger, auto-rebuilding from the archive when the file is missing.

    Missing file → :func:`rebuild_ledger_from_archive` (imports legacy
    ``*.reason.txt`` + stubs, then saves). Present but unreadable /
    invalid JSON → raises. Wrong schema shape → ``ValueError``.
    """
    path = ledger_path(wiki_dir)
    if not path.is_file():
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
    """Yield dismissal records from the ledger (auto-rebuild if missing)."""
    yield from load_ledger(wiki_dir)["dismissals"]


def iter_merges(wiki_dir: Path) -> Iterator[MergeRecord]:
    """Yield merge records from the ledger (auto-rebuild if missing)."""
    yield from load_ledger(wiki_dir)["merges"]


def build_ledger_from_archive(wiki_dir: Path) -> DismissalLedger:
    """Scan archived stubs (+ legacy ``*.reason.txt``) into a ledger — no write.

    Walks ``wiki/archive/candidates/**/*.md``. A sibling ``<stem>.reason.txt``
    whose ``Reason:`` value is ``merged into <slug>`` becomes a merge entry;
    any other reason (including missing reason file) becomes a dismissal.
    First occurrence of each ``norm_page_key`` wins (sorted walk order).
    Callers that want the file on disk use :func:`rebuild_ledger_from_archive`
    or :func:`save_ledger`.
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

    return {
        "version": LEDGER_VERSION,
        "dismissals": dismissals,
        "merges": merges,
    }


def rebuild_ledger_from_archive(wiki_dir: Path) -> DismissalLedger:
    """Rebuild the ledger from archived stubs and legacy ``*.reason.txt`` files.

    Same scan as :func:`build_ledger_from_archive`, then persists the result.
    Idempotent: a second run that sees the same archive writes the same ledger.
    """
    ledger = build_ledger_from_archive(wiki_dir)
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
    if not isinstance(dismissals_raw, list) or not isinstance(merges_raw, list):
        raise ValueError("dismissals.json dismissals/merges must be arrays")
    return {
        "version": LEDGER_VERSION,
        "dismissals": [_coerce_dismissal(row) for row in dismissals_raw],
        "merges": [_coerce_merge(row) for row in merges_raw],
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
