"""Token usage visualization (v0.8 — closes #66).

Three related renders, all stdlib-only, all pure SVG/HTML:

1. **Session token card** — inline card on every session page showing the
   four token categories (input / cache_creation / cache_read / output)
   with stacked bars, human-readable numbers, and a cache-hit-ratio
   indicator (green ≥80%, yellow 50–79%, red <50%).

2. **Project token timeline** — area chart across session dates for a
   project entity page. X = date, Y = tokens (log scale because the
   gap between `input` at ~10k and `cache_read` at ~10M is several
   orders of magnitude).

3. **Site-wide summary stats** — four numbers for `site/index.html`:
   total tokens processed, average per session, best cache hit ratio,
   most token-heavy project.

All three consume the `token_totals` dict written by the converter (#63).
Missing / malformed data degrades to an empty card or "Token usage not
available" message — never a crash.
"""

from __future__ import annotations

import html
import json
import math
import re
from collections.abc import Iterable, Mapping
from datetime import date
from typing import Any

from llmwiki.format_numbers import format_tokens

# ─── data extraction ─────────────────────────────────────────────────────


def parse_token_totals(meta: Mapping[str, object]) -> dict[str, int]:
    """Pull `token_totals` out of a session meta dict.

    Returns `{}` for missing / malformed data. The converter writes
    this as an inline JSON object in frontmatter (#63), so the
    frontmatter parser stores it as a string we `json.loads` here.
    Matches the shape of `parse_tool_counts` for consistency.
    """
    raw = meta.get("token_totals")
    if raw is None or raw == "":
        return {}
    if isinstance(raw, dict):
        return {str(k): int(v) for k, v in raw.items()
                if isinstance(v, (int, float))}
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except ValueError:
            return {}
        if isinstance(data, dict):
            return {str(k): int(v) for k, v in data.items()
                    if isinstance(v, (int, float))}
    return {}


def cache_hit_ratio(totals: dict[str, int]) -> float | None:
    """Return the cache hit ratio as a float in `[0.0, 1.0]`, or None
    if the denominator is zero (no input activity at all).

    Formula matches Anthropic's definition:

        cache_read / (cache_read + cache_creation + input)

    cache_read wins when the model re-uses prior context; cache_creation
    is the first-seen cost of caching; input is fresh (uncached) context.
    """
    cr = totals.get("cache_read", 0)
    cc = totals.get("cache_creation", 0)
    inp = totals.get("input", 0)
    denom = cr + cc + inp
    if denom <= 0:
        return None
    return cr / denom


def _hit_ratio_tier(ratio: float | None) -> tuple[str, str]:
    """Return `(class, label)` for a hit ratio's health tier."""
    if ratio is None:
        return ("tier-unknown", "n/a")
    if ratio >= 0.80:
        return ("tier-green", "healthy")
    if ratio >= 0.50:
        return ("tier-yellow", "warming up")
    return ("tier-red", "cold cache")


# ─── session token card ─────────────────────────────────────────────────


_CATEGORIES = ("input", "cache_creation", "cache_read", "output")
_CATEGORY_LABELS = {
    "input": "Input",
    "cache_creation": "Cache creation",
    "cache_read": "Cache read",
    "output": "Output",
}
_CATEGORY_FALLBACK = {
    "input": "#3b82f6",       # blue — fresh context
    "cache_creation": "#f59e0b",  # amber — write cost
    "cache_read": "#10b981",  # green — reuse win
    "output": "#a855f7",      # purple — generation
}


def render_session_token_card(meta: Mapping[str, object]) -> str:
    """Render an HTML card with stacked bars for the four token categories
    plus a cache-hit-ratio badge. Returns empty string if the session has
    no token data (older sessions missing the `token_totals` key)."""
    totals = parse_token_totals(meta)
    present = [c for c in _CATEGORIES if totals.get(c, 0) > 0]
    if not present:
        return ""

    max_val = max(totals.get(c, 0) for c in _CATEGORIES)
    rows: list[str] = []
    for cat in _CATEGORIES:
        val = totals.get(cat, 0)
        label = _CATEGORY_LABELS[cat]
        formatted = format_tokens(val)
        pct = (val / max_val) if max_val > 0 else 0.0
        bar_w_pct = round(pct * 100, 1)
        rows.append(
            f'<div class="token-row">'
            f'<span class="token-label">{label}</span>'
            f'<span class="token-bar-wrap">'
            f'<span class="token-bar token-bar-{cat}" style="width: {bar_w_pct}%"></span>'
            f'</span>'
            f'<span class="token-value">{formatted}</span>'
            f'</div>'
        )

    ratio = cache_hit_ratio(totals)
    ratio_class, ratio_label = _hit_ratio_tier(ratio)
    ratio_pct = f"{ratio * 100:.0f}%" if ratio is not None else "n/a"
    # The tier class goes on BOTH the container (for the background tint)
    # AND the value span (for the color), because the CSS selectors are
    # `.token-ratio.tier-green` + `.token-ratio-value.tier-green`.
    ratio_block = (
        f'<div class="token-ratio {ratio_class}">'
        f'<span class="token-ratio-label">Cache hit ratio</span>'
        f'<span class="token-ratio-value {ratio_class}">{ratio_pct}</span>'
        f'<span class="token-ratio-tier muted">· {ratio_label}</span>'
        f'</div>'
    )

    total_tokens = sum(totals.get(c, 0) for c in _CATEGORIES)
    return (
        f'<div class="token-card" role="group" aria-label="Token usage">'
        f'<div class="token-card-header">'
        f'<span class="token-card-title">Token usage</span>'
        f'<span class="token-card-total muted">{format_tokens(total_tokens)} total</span>'
        f'</div>'
        + "".join(rows)
        + ratio_block
        + '</div>'
    )


# ─── project token timeline ─────────────────────────────────────────────


def _log_scale(value: int, min_val: int, max_val: int, target_h: int) -> float:
    """Log-scale a token count to a pixel height. Returns 0 for zero."""
    if value <= 0 or max_val <= 0:
        return 0.0
    # log1p keeps tiny values visible without underflow issues
    lv = math.log1p(value)
    lmin = math.log1p(max(1, min_val))
    lmax = math.log1p(max_val)
    if lmax <= lmin:
        return target_h
    return (lv - lmin) / (lmax - lmin) * target_h


def _collect_timeline(
    metas: Iterable[Mapping[str, object]],
) -> list[tuple[date, dict[str, int]]]:
    """Group session metas by date (ascending) and sum token totals per
    date. Returns a list of (date, {cat: sum}) tuples. Sessions with no
    token data are skipped."""
    by_date: dict[date, dict[str, int]] = {}
    for meta in metas:
        totals = parse_token_totals(meta)
        if not any(totals.get(c, 0) > 0 for c in _CATEGORIES):
            continue
        raw = meta.get("date", "")
        try:
            d = date.fromisoformat(str(raw)[:10])
        except (ValueError, TypeError):
            continue
        acc = by_date.setdefault(d, {c: 0 for c in _CATEGORIES})
        for cat in _CATEGORIES:
            acc[cat] += int(totals.get(cat, 0))
    return sorted(by_date.items(), key=lambda x: x[0])


def render_project_token_timeline(
    metas: list[Mapping[str, object]],
    project_slug: str,
    width: int = 560,
    height: int = 150,
) -> str:
    """Render an area chart of per-date total tokens for a project.

    Uses log scale on the Y axis because `cache_read` easily dwarfs
    `input` by 100×. Returns empty string if the project has no token
    data. Single-date projects still produce a valid SVG (one flat
    column) — the shape collapses gracefully."""
    points = _collect_timeline(metas)
    if not points:
        return ""

    # Use total-tokens-per-day for the area chart (summed across cats).
    day_totals = [sum(totals.values()) for _, totals in points]
    max_total = max(day_totals)
    min_total = min(d for d in day_totals if d > 0) if day_totals else 1

    left_pad = 44
    right_pad = 8
    top_pad = 10
    bottom_pad = 22
    plot_w = width - left_pad - right_pad
    plot_h = height - top_pad - bottom_pad

    n = len(points)
    if n == 1:
        xs = [left_pad + plot_w / 2]
    else:
        xs = [left_pad + (i / (n - 1)) * plot_w for i in range(n)]
    ys = [
        top_pad + plot_h - _log_scale(d, min_total, max_total, plot_h)
        for d in day_totals
    ]

    # Build an area path: line along the top, then drop to the baseline.
    path_d: list[str] = [f"M {xs[0]:.1f} {top_pad + plot_h:.1f}"]
    for x, y in zip(xs, ys, strict=True):
        path_d.append(f"L {x:.1f} {y:.1f}")
    path_d.append(f"L {xs[-1]:.1f} {top_pad + plot_h:.1f} Z")

    # Y-axis labels: min, max, and log-mid
    y_max_label = format_tokens(max_total)
    y_min_label = format_tokens(min_total)

    # X-axis labels: first and last dates (YYYY-MM)
    x_first_label = points[0][0].strftime("%Y-%m")
    x_last_label = points[-1][0].strftime("%Y-%m")

    parts: list[str] = [
        f'<svg class="token-timeline-svg" xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
        f'role="img" aria-label="{html.escape(project_slug)} token usage timeline, '
        f'{x_first_label} to {x_last_label}">',
        '<style>',
        '.token-timeline-svg text { font: 10px system-ui, -apple-system, sans-serif; fill: var(--text-secondary, #475569); }',
        '.token-timeline-svg .axis { stroke: var(--border, #e5e7eb); stroke-width: 1; }',
        '.token-timeline-svg .area { fill: var(--token-area-fill, rgba(59, 130, 246, 0.25)); stroke: var(--token-area-stroke, #3b82f6); stroke-width: 1.5; }',
        '</style>',
        # Y-axis line
        f'<line class="axis" x1="{left_pad}" y1="{top_pad}" x2="{left_pad}" y2="{top_pad + plot_h}"/>',
        # X-axis line
        f'<line class="axis" x1="{left_pad}" y1="{top_pad + plot_h}" x2="{left_pad + plot_w}" y2="{top_pad + plot_h}"/>',
        # Area path
        f'<path class="area" d="{" ".join(path_d)}"/>',
        # Y axis labels
        f'<text x="{left_pad - 4}" y="{top_pad + 4}" text-anchor="end">{y_max_label}</text>',
        f'<text x="{left_pad - 4}" y="{top_pad + plot_h}" text-anchor="end">{y_min_label}</text>',
        # X axis labels
        f'<text x="{left_pad}" y="{height - 6}">{x_first_label}</text>',
        f'<text x="{left_pad + plot_w}" y="{height - 6}" text-anchor="end">{x_last_label}</text>',
    ]
    parts.append('</svg>')
    return "\n".join(parts)


def render_project_token_card(
    metas: list[Mapping[str, object]],
    project_slug: str,
) -> str:
    """Wrap `render_project_token_timeline` in the same card shell as
    session token usage so project pages have a uniform look."""
    svg = render_project_token_timeline(metas, project_slug)
    if not svg:
        return ""
    # Compute aggregate totals for the header
    totals_agg = {c: 0 for c in _CATEGORIES}
    for meta in metas:
        t = parse_token_totals(meta)
        for c in _CATEGORIES:
            totals_agg[c] += t.get(c, 0)
    total_all = sum(totals_agg.values())
    ratio = cache_hit_ratio(totals_agg)
    ratio_class, ratio_label = _hit_ratio_tier(ratio)
    ratio_pct = f"{ratio * 100:.0f}%" if ratio is not None else "n/a"
    return (
        f'<div class="token-card token-card-project" role="group" '
        f'aria-label="{html.escape(project_slug)} token usage">'
        f'<div class="token-card-header">'
        f'<span class="token-card-title">Token usage · timeline</span>'
        f'<span class="token-card-total muted">{format_tokens(total_all)} total · '
        f'<span class="token-ratio-value {ratio_class}">{ratio_pct}</span> cache hit · {ratio_label}</span>'
        f'</div>'
        + svg
        + '</div>'
    )


# ─── site-wide summary stats ────────────────────────────────────────────


_AGENT_DISPLAY_NAMES: dict[str, str] = {
    "claude_code": "Claude Code",
    "cursor_cli": "Cursor CLI",
    "codex_cli": "Codex CLI",
    "copilot_chat": "Copilot CLI / Chat",
    "gemini_cli": "Gemini CLI",
    "openclaw": "OpenClaw",
    "opencode": "OpenCode",
}


def _agent_display_name(agent: str) -> str:
    if agent in _AGENT_DISPLAY_NAMES:
        return _AGENT_DISPLAY_NAMES[agent]
    return agent.replace("_", " ").replace("-", " ").title()


def _format_coverage_since(raw: object) -> str:
    """Normalize a stored ``YYYY-MM-DD`` (or ISO) into ``YYYY/MM/DD`` for the hint."""
    if not isinstance(raw, str):
        return ""
    text = raw.strip()
    if not text:
        return ""
    day = text[:10]
    if len(day) == 10 and day[4] == "-" and day[7] == "-":
        return f"{day[0:4]}/{day[5:7]}/{day[8:10]}"
    return text.replace("-", "/")


def format_token_coverage_measured_known(by_agent: Mapping[str, Any]) -> list[str]:
    """Coverage bullets for agents with measured sessions (#325).

    Returns lines after the ``Measured on sessions`` header, e.g.
    ``- 2/1234 Cursor CLI (since 2026/10/15)``.
    """
    lines: list[str] = []
    for agent in sorted(by_agent):
        row = by_agent[agent]
        if not isinstance(row, Mapping):
            continue
        measured = int(row.get("measured") or 0)
        if measured <= 0:
            continue
        known = int(row.get("known") or 0)
        if known < measured:
            known = measured
        label = _agent_display_name(agent)
        line = f"- {measured}/{known} {label}"
        if known > measured:
            since = _format_coverage_since(row.get("since"))
            if since:
                line = f"{line} (since {since})"
        lines.append(line)
    return lines


def sum_agent_known_sessions(by_agent: Mapping[str, Any] | None) -> int:
    """Sum ``by_agent[*].known`` (coverage universe for the Tokens denominator)."""
    if not by_agent:
        return 0
    total = 0
    for row in by_agent.values():
        if not isinstance(row, Mapping):
            continue
        measured = int(row.get("measured") or 0)
        known = int(row.get("known") or 0)
        total += max(known, measured)
    return total


def format_site_tokens_sublabel(
    *,
    avg_per_session: int,
    measured_sessions: int,
    total_sessions: int,
) -> str:
    """Tokens card sub-line: ``by 1477/23456 sessions (3.7M/s)`` (#325).

    ``total_sessions`` is Σ agent ``known`` (Claude + Cursor + other agents),
    not the site session-page count.
    """
    total = max(int(total_sessions), int(measured_sessions))
    return (
        f"by {int(measured_sessions)}/{total} sessions "
        f"({format_tokens(int(avg_per_session))}/s)"
    )


def usage_file_preferred_for_site_stats(usage_data: Mapping[str, Any]) -> bool:
    """True when Analytics should read headline totals from the usage file."""
    sessions = usage_data.get("sessions")
    totals = usage_data.get("totals")
    if isinstance(sessions, Mapping) and sessions:
        return True
    if isinstance(totals, Mapping) and int(totals.get("sum") or 0) > 0:
        return True
    return False


def compute_site_stats_from_usage(usage_data: Mapping[str, Any]) -> dict[str, object]:
    """Headline token stats from ``usage/session-tokens.json`` aggregates."""
    totals = usage_data.get("totals") if isinstance(usage_data.get("totals"), Mapping) else {}
    by_agent = usage_data.get("by_agent") if isinstance(usage_data.get("by_agent"), Mapping) else {}
    total_tokens = int(totals.get("sum") or 0)
    session_count = 0
    for row in by_agent.values():
        if isinstance(row, Mapping):
            session_count += int(row.get("measured") or 0)
    avg = total_tokens // session_count if session_count > 0 else 0
    return {
        "total_tokens": total_tokens,
        "session_count": session_count,
        "avg_per_session": avg,
        "best_ratio_project": None,
        "heaviest_project": None,
        "by_agent": by_agent,
    }


def compute_site_stats(
    metas_by_project: dict[str, list[Mapping[str, object]]],
) -> dict[str, object]:
    """Return the numbers the Analytics Tokens tile wants:

    * `total_tokens`: int — sum of all token categories across sessions with data
    * `session_count`: int — sessions with ≥1 non-zero token category (the avg divisor; not the hero session count)
    * `avg_per_session`: int — ``total_tokens // session_count`` (0 when none)
    * `best_ratio_project`: (slug, ratio) or None
    * `heaviest_project`: (slug, total) or None
    """
    session_count = 0
    total_tokens = 0
    best_ratio: tuple[str, float] | None = None
    heaviest: tuple[str, int] | None = None

    for slug, metas in metas_by_project.items():
        proj_totals = {c: 0 for c in _CATEGORIES}
        proj_session_count = 0
        for meta in metas:
            t = parse_token_totals(meta)
            if not any(t.get(c, 0) > 0 for c in _CATEGORIES):
                continue
            for c in _CATEGORIES:
                proj_totals[c] += t.get(c, 0)
            session_count += 1
            proj_session_count += 1
            total_tokens += sum(t.get(c, 0) for c in _CATEGORIES)
        if proj_session_count == 0:
            continue
        proj_total = sum(proj_totals.values())
        if heaviest is None or proj_total > heaviest[1]:
            heaviest = (slug, proj_total)
        r = cache_hit_ratio(proj_totals)
        if r is not None and (best_ratio is None or r > best_ratio[1]):
            best_ratio = (slug, r)

    avg = total_tokens // session_count if session_count > 0 else 0
    return {
        "total_tokens": total_tokens,
        "session_count": session_count,
        "avg_per_session": avg,
        "best_ratio_project": best_ratio,
        "heaviest_project": heaviest,
    }


#: Fallback coverage disclosure when no per-agent measured/known rows are
#: available yet (#323). Prefer :func:`format_token_coverage_measured_known`
#: plus :data:`TOKEN_COVERAGE_OTHER_AGENTS_LINE` on the Analytics page once
#: ``usage/session-tokens.json`` feeds ``by_agent``.
TOKEN_COVERAGE_LINES: tuple[str, ...] = (
    "Counts input, output, cache creation, and cache read tokens from"
    " recorded, compatible session usage. This is session usage, not"
    " synthesis spend.",
    "Claude Code: included when usage fields are present.",
    "OpenClaw and OpenCode: counted only for records with compatible usage"
    " fields; native token support is not complete.",
    "Cursor CLI: included when usage fields are present (stop-hook JSONL;"
    " not context-window occupancy in the session store).",
    "Codex CLI and Cursor IDE: not captured by the token pipeline yet.",
    "Gemini CLI and Copilot CLI / Chat: no verified native token mapping.",
    "Sessions without usage data are excluded, not evidence of zero tokens."
    " The headline is a recorded-usage total, not a complete all-agent total.",
)

TOKEN_COVERAGE_OTHER_AGENTS_LINE = (
    "Other sessions and agents are filtered out or do not support Tokens metrics."
)

_HINT_ID_UNSAFE = re.compile(r"[^A-Za-z0-9_-]")


def render_token_coverage_hint(
    hint_id: str,
    *,
    by_agent: Mapping[str, Any] | None = None,
) -> str:
    """Return the accessible "what does this total cover?" control (#323).

    A ``<button>`` (labelled, ``aria-expanded``) plus a ``role="tooltip"``
    panel. When ``by_agent`` has measured coverage, the panel is the short
    measured/known lines plus :data:`TOKEN_COVERAGE_OTHER_AGENTS_LINE` — not
    the long static agent encyclopedia. Without measured rows, fall back to
    :data:`TOKEN_COVERAGE_LINES`. CSS reveals the panel on hover /
    focus-within / ``aria-expanded="true"``; the viewer script toggles
    ``aria-expanded`` for touch and closes on Escape / outside click.
    ``hint_id`` seeds the panel id (``<hint_id>-panel``).
    """
    safe = _HINT_ID_UNSAFE.sub("-", hint_id).strip("-") or "token-coverage"
    panel_id = f"{safe}-panel"
    measured = format_token_coverage_measured_known(by_agent or {})
    if measured:
        coverage_lines = [
            "Measured on sessions",
            *measured,
            TOKEN_COVERAGE_OTHER_AGENTS_LINE,
        ]
    else:
        coverage_lines = list(TOKEN_COVERAGE_LINES)
    lines = "".join(
        f'<span class="token-coverage-line">{html.escape(line)}</span>'
        for line in coverage_lines
    )
    return (
        '<span class="token-coverage-hint">'
        '<button type="button" class="token-coverage-btn"'
        ' aria-label="What do Tokens cover? Show agent coverage"'
        f' aria-describedby="{panel_id}" aria-expanded="false">i</button>'
        f'<span class="token-coverage-panel" role="tooltip" id="{panel_id}">'
        f'{lines}</span></span>'
    )


def render_site_token_stats(
    metas_by_project: dict[str, list[Mapping[str, object]]],
    link_prefix: str = "",
    extra_cards: str = "",
    session_tokens_usage: Mapping[str, Any] | None = None,
) -> str:
    """Return a single-row stat-card block for the Analytics page: Tokens,
    Best cache hit, and Heaviest project (by tokens). ``extra_cards`` holds
    pre-rendered ``token-stat`` cards (e.g. the MCP-usage card) that share
    the same row. Empty string when there are neither token stats nor
    extra cards."""
    meta_stats = compute_site_stats(metas_by_project)
    stats = meta_stats
    by_agent: Mapping[str, Any] | None = None
    if session_tokens_usage and usage_file_preferred_for_site_stats(session_tokens_usage):
        usage_stats = compute_site_stats_from_usage(session_tokens_usage)
        stats = {
            **meta_stats,
            "total_tokens": usage_stats["total_tokens"],
            "session_count": usage_stats["session_count"],
            "avg_per_session": usage_stats["avg_per_session"],
        }
        by_agent = usage_stats.get("by_agent") if isinstance(usage_stats.get("by_agent"), Mapping) else None
    if stats["session_count"] == 0 and not extra_cards:
        return ""
    total = stats["total_tokens"]
    avg = stats["avg_per_session"]
    best = stats["best_ratio_project"]
    heaviest = stats["heaviest_project"]

    parts: list[str] = [
        '<section class="section token-stats-section">',
        '  <div class="container">',
        '    <div class="token-stat-grid">',
    ]
    n_with_tokens = int(stats["session_count"])
    # Denominator = Σ by_agent.known (measured agents + other agents' known).
    # Fall back to on-disk session metas only when the usage file has no rows.
    known_total = sum_agent_known_sessions(by_agent)
    total_sessions = (
        known_total
        if known_total > 0
        else sum(len(metas) for metas in metas_by_project.values())
    )
    if n_with_tokens > 0:
        sub = format_site_tokens_sublabel(
            avg_per_session=int(avg),
            measured_sessions=n_with_tokens,
            total_sessions=total_sessions,
        )
        parts.append(
            f'      <div class="token-stat" data-llmwiki-tokens-card>'
            f'<div class="token-stat-label muted">Tokens'
            f'{render_token_coverage_hint("token-coverage-site", by_agent=by_agent)}</div>'
            f'<div class="token-stat-value">{format_tokens(total)}</div>'
            f'<div class="token-stat-sub muted">{html.escape(sub)}</div></div>'
        )
    if best is not None:
        slug, r = best
        parts.append(
            f'      <a class="token-stat" href="{link_prefix}projects/{html.escape(slug)}.html">'
            f'<div class="token-stat-label muted">Best cache hit</div>'
            f'<div class="token-stat-value">{r * 100:.0f}%</div>'
            f'<div class="token-stat-sub muted">{html.escape(slug)}</div>'
            f'</a>'
        )
    if heaviest is not None:
        slug, total_proj = heaviest
        parts.append(
            f'      <a class="token-stat" href="{link_prefix}projects/{html.escape(slug)}.html">'
            f'<div class="token-stat-label muted">Heaviest project (by tokens)</div>'
            f'<div class="token-stat-value">{format_tokens(total_proj)}</div>'
            f'<div class="token-stat-sub muted">{html.escape(slug)}</div>'
            f'</a>'
        )
    if extra_cards:
        parts.append(extra_cards)
    parts.append('    </div>')
    if n_with_tokens > 0:
        parts.append(
            '    <p class="muted token-stats-note">Cumulative billed throughput'
            ' (token categories including cache_read), not context-window occupancy.</p>'
        )
    parts.append('  </div>')
    parts.append('</section>')
    return "\n".join(parts)
