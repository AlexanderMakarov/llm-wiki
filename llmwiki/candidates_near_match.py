"""Near-match prior dismissals for pending candidates (#146 / #326).

Compares ``norm_page_key`` of a pending title/slug against dismissal ledger
records via ``difflib.SequenceMatcher``. Exact folded-key equality is *not*
a near-match (those stay excluded at harvest). Merges are never considered —
callers must feed :func:`llmwiki.dismissal_ledger.iter_dismissals` only.

This module does **not** open ``dismissals.json``; attach helpers load records
through ledger iterators when a vault path is given.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, MutableMapping, Sequence
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, TypedDict

from llmwiki.dismissal_ledger import DismissalRecord, iter_dismissals
from llmwiki.wikilinks import norm_page_key

# Align with ``topics._DEFAULT_SIMILARITY`` (0.90). Defined here so this module
# does not import ``topics`` (which pulls ``candidates`` / graph).
NEAR_MATCH_SIMILARITY = 0.90

#: Folded keys shorter than this are skipped (too ambiguous for near-match).
MIN_FOLDED_KEY_LENGTH = 4

#: Skip SequenceMatcher when relative length delta exceeds this (~0.25).
LENGTH_DELTA = 0.25

EMPTY_REASON_DISPLAY = "(discarded without explanation)"

__all__ = [
    "EMPTY_REASON_DISPLAY",
    "LENGTH_DELTA",
    "MIN_FOLDED_KEY_LENGTH",
    "NEAR_MATCH_SIMILARITY",
    "PriorDismissal",
    "attach_prior_dismissals",
    "format_dismissal_reason",
    "near_match_dismissal",
    "near_match_dismissals",
    "reuse_discard_reason",
]


class PriorDismissal(TypedDict):
    """One near-match dismissal related to a pending candidate."""

    name: str
    reason: str
    ratio: float


def format_dismissal_reason(reason: str | None) -> str:
    """Return ``reason`` for display; blank/None → :data:`EMPTY_REASON_DISPLAY`."""
    text = (reason or "").strip()
    return text if text else EMPTY_REASON_DISPLAY


def reuse_discard_reason(prior: Mapping[str, Any] | None) -> str:
    """Reason text to archive when discarding with a prior dismissal's reason.

    Blank priors become :data:`EMPTY_REASON_DISPLAY` so the site/CLI discard
    path always has a non-empty reason string.
    """
    if not prior:
        return EMPTY_REASON_DISPLAY
    return format_dismissal_reason(prior.get("reason") if isinstance(prior, Mapping) else None)


def _length_prefilter_ok(a: str, b: str) -> bool:
    """True when relative length delta is within :data:`LENGTH_DELTA`."""
    la, lb = len(a), len(b)
    if la == 0 or lb == 0:
        return False
    return abs(la - lb) / max(la, lb) <= LENGTH_DELTA


def _pending_folded_key(pending_name: str) -> str:
    return norm_page_key(pending_name)


def _candidate_pending_name(candidate: Mapping[str, Any]) -> str:
    """Prefer frontmatter title; fall back to filename slug."""
    title = candidate.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()
    slug = candidate.get("slug")
    if isinstance(slug, str) and slug.strip():
        return slug.strip()
    return ""


def _rank_key(ratio: float, discarded_at: str, name: str) -> tuple[float, str, str]:
    return (ratio, discarded_at, name)


def near_match_dismissals(
    pending_name: str,
    dismissals: Iterable[Mapping[str, Any]],
    *,
    similarity: float = NEAR_MATCH_SIMILARITY,
) -> list[PriorDismissal]:
    """Return all near-match dismissals for ``pending_name``, best first.

    Same filters as :func:`near_match_dismissal`, but keeps every hit at or
    above ``similarity``, sorted by highest ratio → most recent
    ``discarded_at`` → lexicographic ``name``.
    """
    pending_key = _pending_folded_key(pending_name)
    if len(pending_key) < MIN_FOLDED_KEY_LENGTH:
        return []

    hits: list[tuple[tuple[float, str, str], PriorDismissal]] = []
    for rec in dismissals:
        dismiss_key = str(rec.get("key") or "") or norm_page_key(str(rec.get("name") or ""))
        if not dismiss_key:
            continue
        if dismiss_key == pending_key:
            continue
        if len(dismiss_key) < MIN_FOLDED_KEY_LENGTH:
            continue
        if not _length_prefilter_ok(pending_key, dismiss_key):
            continue
        ratio = SequenceMatcher(None, pending_key, dismiss_key).ratio()
        if ratio < similarity:
            continue
        name = str(rec.get("name") or "")
        reason = str(rec.get("reason") or "")
        discarded_at = str(rec.get("discarded_at") or "")
        prior: PriorDismissal = {"name": name, "reason": reason, "ratio": ratio}
        hits.append((_rank_key(ratio, discarded_at, name), prior))

    hits.sort(key=lambda item: item[0], reverse=True)
    return [prior for _, prior in hits]


def near_match_dismissal(
    pending_name: str,
    dismissals: Iterable[Mapping[str, Any]],
    *,
    similarity: float = NEAR_MATCH_SIMILARITY,
) -> PriorDismissal | None:
    """Return the best near-match dismissal for ``pending_name``, or ``None``."""
    matches = near_match_dismissals(
        pending_name, dismissals, similarity=similarity
    )
    return matches[0] if matches else None


def attach_prior_dismissals(
    candidates: Sequence[MutableMapping[str, Any]],
    wiki_dir: Path | None = None,
    *,
    dismissals: Iterable[Mapping[str, Any]] | Sequence[DismissalRecord] | None = None,
) -> list[MutableMapping[str, Any]]:
    """Attach ``prior_dismissals`` (list) onto each near-matching candidate.

    When ``dismissals`` is omitted, loads via :func:`iter_dismissals`
    (requires ``wiki_dir``). Mutates each mapping in place and returns the
    same list-like sequence as a list. Candidates with no near-match leave
    ``prior_dismissals`` unset (key absent).
    """
    if dismissals is None:
        if wiki_dir is None:
            raise ValueError("wiki_dir is required when dismissals is not provided")
        records: list[Mapping[str, Any]] = list(iter_dismissals(wiki_dir))
    else:
        records = list(dismissals)

    out: list[MutableMapping[str, Any]] = list(candidates)
    if not records:
        for cand in out:
            cand.pop("prior_dismissals", None)
            cand.pop("prior_dismissal", None)
        return out

    for cand in out:
        pending = _candidate_pending_name(cand)
        priors = near_match_dismissals(pending, records) if pending else []
        if not priors:
            cand.pop("prior_dismissals", None)
            cand.pop("prior_dismissal", None)
        else:
            cand["prior_dismissals"] = priors
            # Best match kept for callers that only need one reason to reuse.
            cand["prior_dismissal"] = priors[0]
    return out
