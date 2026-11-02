"""Eligibility rules for Analytics Tokens coverage ``known`` (#355)."""
from __future__ import annotations

from typing import Any

from llmwiki.convert import compute_token_totals, count_tool_calls, first_field
from llmwiki.synth.pipeline import resolve_exclude_non_usage_from_token_coverage
from llmwiki.viz_tokens import parse_token_totals

_BUCKET_KEYS = ("input", "cache_creation", "cache_read", "output")

# Adapters where sync/migrate can infer real vs placeholder from raw/origin
# signals. Other agents (OpenClaw, Cursor IDE, …) may have all-zero
# token_totals because capture is missing — never treat that as "no usage".
TOKEN_COVERAGE_PLACEHOLDER_AGENTS = frozenset({"claude_code", "cursor_cli", "codex_cli"})


def totals_nonempty(totals: dict[str, int]) -> bool:
    return any(int(totals.get(k) or 0) != 0 for k in _BUCKET_KEYS)


def is_synthetic_model(model: str | None) -> bool:
    """True for convert placeholders such as ``<synthetic>``."""
    if not model:
        return False
    text = str(model).strip().lower()
    if text in ("<synthetic>", "synthetic"):
        return True
    if text.startswith("<") and text.endswith(">") and "synthetic" in text:
        return True
    return False


def placeholder_filter_applies(agent: str, exclude_non_usage: bool) -> bool:
    """Whether #355 placeholder heuristics apply to this adapter's sessions."""
    return bool(exclude_non_usage) and agent in TOKEN_COVERAGE_PLACEHOLDER_AGENTS


def raw_meta_eligible_for_token_known(
    meta: dict[str, Any],
    *,
    exclude_non_usage: bool,
    agent: str,
) -> bool:
    """Whether a ``raw/sessions/*.md`` row counts toward ``by_agent.known``."""
    if not placeholder_filter_applies(agent, exclude_non_usage):
        return True
    totals = parse_token_totals(meta)
    if totals_nonempty(totals):
        return True
    if is_synthetic_model(str(meta.get("model") or "")):
        return False
    raw_tools = meta.get("tool_calls")
    if raw_tools is not None:
        try:
            if int(raw_tools) == 0:
                return False
        except (TypeError, ValueError):
            pass
    return True


def records_eligible_for_token_known(
    records: list[dict[str, Any]],
    *,
    exclude_non_usage: bool,
    agent: str,
) -> bool:
    """Whether an origin session counts toward ``by_agent.known``."""
    if not placeholder_filter_applies(agent, exclude_non_usage):
        return True
    totals = compute_token_totals(records)
    if totals_nonempty(totals):
        return True
    model = first_field(records, "model")
    if is_synthetic_model(model):
        return False
    if count_tool_calls(records) == 0:
        return False
    return True


def resolve_token_known_filter(cfg: dict[str, Any] | None) -> bool:
    """Read ``filters.exclude_non_usage_from_token_coverage`` (default True)."""
    return resolve_exclude_non_usage_from_token_coverage(cfg)
