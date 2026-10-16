"""Map Cursor turn usage fields to Claude ``message.usage`` shape (#325).

Cursor reports inclusive ``input_tokens`` / ``inputTokens`` (cache read/write
already inside input). Claude's four fields are disjoint. Occupancy gauges
(``used_tokens`` / ``max_tokens``) are never mapped to measurable usage.

Accepts both snake_case (IDE ``stop`` hook / forum 168317) and camelCase
(Agent CLI ``stream-json`` ``result.usage``).
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

# Canonical snake keys after :func:`normalize_cursor_usage_keys`.
_USAGE_KEYS = frozenset(
    {
        "input_tokens",
        "output_tokens",
        "cache_read_tokens",
        "cache_write_tokens",
        "cache_read",
        "cache_write",
    }
)
_OCCUPANCY_KEYS = frozenset({"used_tokens", "max_tokens", "usedTokens", "maxTokens"})

# camelCase (stream-json) → snake_case (hook / Claude map).
_CAMEL_TO_SNAKE = {
    "inputTokens": "input_tokens",
    "outputTokens": "output_tokens",
    "cacheReadTokens": "cache_read_tokens",
    "cacheWriteTokens": "cache_write_tokens",
    "cacheRead": "cache_read",
    "cacheWrite": "cache_write",
    "usedTokens": "used_tokens",
    "maxTokens": "max_tokens",
}


def normalize_cursor_usage_keys(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Return a shallow copy with camelCase token keys folded to snake_case."""
    if not isinstance(raw, Mapping):
        return {}
    out: dict[str, Any] = {}
    for key, val in raw.items():
        canon = _CAMEL_TO_SNAKE.get(str(key), str(key))
        # Prefer first-seen; do not overwrite snake with empty camel.
        if canon in out and out[canon] is not None:
            continue
        out[canon] = val
    return out


def _int_field(raw: Mapping[str, Any], *keys: str) -> int | None:
    for key in keys:
        if key not in raw:
            continue
        val = raw[key]
        if val is None:
            continue
        if isinstance(val, bool):
            continue
        try:
            return int(val)
        except (TypeError, ValueError):
            continue
    return None


def _has_key(raw: Mapping[str, Any], *keys: str) -> bool:
    return any(key in raw for key in keys)


def map_cursor_usage_to_claude_usage(raw: Mapping[str, Any]) -> dict[str, int] | None:
    """Map one Cursor usage object to Claude assistant ``message.usage`` fields.

    Returns ``None`` for occupancy-only payloads or when no turn throughput
    fields are present.
    """
    if not isinstance(raw, Mapping):
        return None

    norm = normalize_cursor_usage_keys(raw)

    has_in = "input_tokens" in norm
    has_out = "output_tokens" in norm
    has_occupancy = _has_key(norm, "used_tokens", "max_tokens")
    if has_occupancy and not has_in and not has_out:
        return None
    if not has_in and not has_out:
        return None

    inp = _int_field(norm, "input_tokens")
    out = _int_field(norm, "output_tokens")
    cr = _int_field(norm, "cache_read_tokens", "cache_read") or 0
    cw = _int_field(norm, "cache_write_tokens", "cache_write") or 0

    if inp is None and out is None:
        return None

    inp_val = inp or 0
    out_val = out or 0
    if inp_val == 0 and out_val == 0 and cr == 0 and cw == 0:
        return None

    fresh_input = max(0, inp_val - cr - cw)
    return {
        "input_tokens": fresh_input,
        "cache_creation_input_tokens": cw,
        "cache_read_input_tokens": cr,
        "output_tokens": out_val,
    }


def extract_cursor_usage_from_record(rec: Mapping[str, Any]) -> dict[str, int] | None:
    """Find a Cursor usage blob on a transcript record and map it."""
    if not isinstance(rec, Mapping):
        return None

    candidates: list[Mapping[str, Any]] = []
    usage = rec.get("usage")
    if isinstance(usage, Mapping):
        candidates.append(usage)

    message = rec.get("message")
    if isinstance(message, Mapping):
        msg_usage = message.get("usage")
        if isinstance(msg_usage, Mapping):
            candidates.append(msg_usage)

    # Top-level snake or camel throughput / occupancy keys.
    top_level = {
        k: rec[k]
        for k in list(_USAGE_KEYS) + list(_OCCUPANCY_KEYS) + list(_CAMEL_TO_SNAKE)
        if k in rec
    }
    if top_level:
        candidates.append(top_level)

    for raw in candidates:
        mapped = map_cursor_usage_to_claude_usage(raw)
        if mapped is not None:
            return mapped
    return None
