"""Search facet enrichment (v1.0 · #161).

Adds confidence-weighted ranking and facet filters (lifecycle, tags)
to the static-site search index.

Builds on the chunked search index from #47. Each entry gains:
  - ``confidence``: float 0.0-1.0 (from page frontmatter)
  - ``lifecycle``: state string (draft/reviewed/verified/stale/archived)
  - ``tags``: list[str] (filtered to non-noise tags)

The facet summary (counts per value) is written alongside the index
so the client can render filter checkboxes without scanning the full
index first.
"""

from __future__ import annotations

from typing import Any

# Tag parsing lives in llmwiki.tag_utils (shared with categories).
from llmwiki.tag_utils import parse_tags_field as _parse_tags_field


def _parse_confidence(raw: Any) -> float:
    """Parse a confidence field, return 0.0 if missing/invalid."""
    if raw is None or raw == "":
        return 0.0
    try:
        c = float(raw)
    except (ValueError, TypeError):
        return 0.0
    return max(0.0, min(1.0, c))


def enrich_entry(entry: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any]:
    """Add facet fields to a search-index entry.

    Modifies ``entry`` in place and returns it.
    """
    entry["confidence"] = _parse_confidence(meta.get("confidence"))
    entry["lifecycle"] = str(meta.get("lifecycle", "")).lower()
    entry["tags"] = _parse_tags_field(meta.get("tags", ""))
    return entry


def aggregate_facets(entries: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    """Count entries by each facet value. Returns::

        {
            "lifecycle":   {"draft": 5, "verified": 20, ...},
            "tags":        {"flutter": 3, "python": 7, ...},
            "confidence":  {"high": N, "medium": N, "low": N, "none": N},
        }
    """
    counts = {
        "lifecycle": {},
        "tags": {},
        "confidence": {},
    }
    for entry in entries:
        lc = entry.get("lifecycle", "")
        if lc:
            counts["lifecycle"][lc] = counts["lifecycle"].get(lc, 0) + 1

        for tag in entry.get("tags", []):
            counts["tags"][tag] = counts["tags"].get(tag, 0) + 1

        conf = entry.get("confidence", 0.0)
        if conf >= 0.8:
            bucket = "high"
        elif conf >= 0.5:
            bucket = "medium"
        elif conf > 0:
            bucket = "low"
        else:
            bucket = "none"
        counts["confidence"][bucket] = counts["confidence"].get(bucket, 0) + 1

    return counts


def rank_by_confidence(
    entries: list[dict[str, Any]],
    query: str = "",
    *,
    confidence_weight: float = 0.3,
) -> list[dict[str, Any]]:
    """Return entries sorted by a combined relevance + confidence score.

    If ``query`` is empty, sorts by confidence alone. If provided, does
    a simple substring match on title and body, weighted by confidence.
    """
    q = query.lower().strip()

    def _score(entry: dict[str, Any]) -> float:
        conf = entry.get("confidence", 0.0)
        if not q:
            return conf

        title = str(entry.get("title", "")).lower()
        body = str(entry.get("body", "")).lower()
        tags = entry.get("tags", [])

        relevance = 0.0
        if q in title:
            relevance += 1.0
        if q in body:
            relevance += 0.5
        if any(q in t for t in tags):
            relevance += 0.3

        return relevance * (1.0 - confidence_weight) + conf * confidence_weight

    return sorted(entries, key=_score, reverse=True)


def filter_entries(
    entries: list[dict[str, Any]],
    *,
    lifecycles: list[str] | None = None,
    tags: list[str] | None = None,
    min_confidence: float = 0.0,
    max_confidence: float = 1.0,
) -> list[dict[str, Any]]:
    """Filter entries by facet values. Empty filter lists = no filter."""
    result = []
    for entry in entries:
        if lifecycles and entry.get("lifecycle", "") not in lifecycles:
            continue
        if tags:
            entry_tags = set(entry.get("tags", []))
            if not entry_tags & set(tags):
                continue
        conf = entry.get("confidence", 0.0)
        if not (min_confidence <= conf <= max_confidence):
            continue
        result.append(entry)
    return result
