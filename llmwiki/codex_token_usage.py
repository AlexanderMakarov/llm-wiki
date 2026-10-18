"""Map Codex CLI ``token_count`` usage to Claude ``message.usage`` shape (#324).

Codex ``event_msg`` payloads with ``payload.type == "token_count"`` expose
cumulative ``info.total_token_usage`` (prefer the last snapshot) and per-turn
``info.last_token_usage`` (sum once across the session when totals are absent).

Input is inclusive of cache read/write; Claude's four fields are disjoint.
When ``reasoning_output_tokens`` is present it is treated as a subset of
``output_tokens`` and omitted from Tokens. Occupancy
(``model_context_window``) and ``rate_limits`` alone are never mapped.

@spec: 329-codex-cli-token-usage
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

# Fields summed when falling back to last_token_usage deltas.
_SUM_KEYS = (
    "input_tokens",
    "cached_input_tokens",
    "cache_write_input_tokens",
    "output_tokens",
    "reasoning_output_tokens",
    "total_tokens",
)


def _int_field(raw: Mapping[str, Any], *keys: str) -> int | None:
    for key in keys:
        if key not in raw:
            continue
        val = raw[key]
        if val is None or isinstance(val, bool):
            continue
        try:
            return int(val)
        except (TypeError, ValueError):
            continue
    return None


def map_codex_token_usage_to_claude_usage(
    raw: Mapping[str, Any],
) -> dict[str, int] | None:
    """Map one Codex usage blob to Claude assistant ``message.usage`` fields.

    Returns ``None`` when no measurable throughput fields are present (empty,
    occupancy-only blobs passed through by mistake, or all-zero totals).
    """
    if not isinstance(raw, Mapping):
        return None

    has_in = "input_tokens" in raw
    has_out = "output_tokens" in raw
    has_cr = "cached_input_tokens" in raw
    has_cw = "cache_write_input_tokens" in raw
    if not (has_in or has_out or has_cr or has_cw):
        return None

    inp = _int_field(raw, "input_tokens")
    out = _int_field(raw, "output_tokens")
    cr = _int_field(raw, "cached_input_tokens") or 0
    cw = _int_field(raw, "cache_write_input_tokens") or 0

    if inp is None and out is None and cr == 0 and cw == 0:
        return None

    inp_val = inp or 0
    out_val = out or 0
    if inp_val == 0 and out_val == 0 and cr == 0 and cw == 0:
        return None

    if "reasoning_output_tokens" in raw:
        rea = _int_field(raw, "reasoning_output_tokens") or 0
        output_tokens = max(0, out_val - rea)
    else:
        output_tokens = out_val

    return {
        "input_tokens": max(0, inp_val - cr - cw),
        "cache_creation_input_tokens": cw,
        "cache_read_input_tokens": cr,
        "output_tokens": output_tokens,
    }


def _sum_last_token_usages(blobs: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    """Sum per-turn ``last_token_usage`` fields once across the session."""
    summed: dict[str, int] = {}
    for key in _SUM_KEYS:
        total = 0
        seen = False
        for blob in blobs:
            if key not in blob:
                continue
            seen = True
            val = _int_field(blob, key)
            if val is not None:
                total += val
        if seen:
            summed[key] = total
    return summed


def _token_count_info(rec: Mapping[str, Any]) -> Mapping[str, Any] | None:
    """Return ``payload.info`` for an ``event_msg`` / ``token_count`` record."""
    if rec.get("type") != "event_msg":
        return None
    payload = rec.get("payload")
    if not isinstance(payload, Mapping):
        return None
    if payload.get("type") != "token_count":
        return None
    info = payload.get("info")
    if isinstance(info, Mapping):
        return info
    return None


def extract_codex_session_usage(
    records: list[dict[str, Any]] | Sequence[Mapping[str, Any]],
) -> dict[str, int] | None:
    """Walk session records; map final Codex usage to Claude four fields.

    Prefers the last ``info.total_token_usage`` snapshot (never sums successive
    totals). If that snapshot is missing or unmappable (empty / all-zero), sums
    ``info.last_token_usage`` once across all ``token_count`` events.
    Occupancy-only / ``rate_limits``-only / empty sessions return ``None``.
    """
    if not records:
        return None

    last_total: Mapping[str, Any] | None = None
    last_deltas: list[Mapping[str, Any]] = []

    for rec in records:
        if not isinstance(rec, Mapping):
            continue
        info = _token_count_info(rec)
        if info is None:
            continue
        total = info.get("total_token_usage")
        if isinstance(total, Mapping):
            last_total = total
        last_u = info.get("last_token_usage")
        if isinstance(last_u, Mapping):
            last_deltas.append(last_u)

    if last_total is not None:
        mapped = map_codex_token_usage_to_claude_usage(last_total)
        if mapped is not None:
            return mapped

    if last_deltas:
        return map_codex_token_usage_to_claude_usage(_sum_last_token_usages(last_deltas))

    return None
