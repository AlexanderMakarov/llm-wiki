"""Analytics MCP usage + Wiki value HTML renderers (#27, #52).

Extracted from ``build.py`` so the site orchestrator stays under the
line-count ceiling while the value layer stays independently testable.
"""
from __future__ import annotations

import html
from typing import Any

from llmwiki.usage import UNATTRIBUTED, is_entity_tool, value_summary


def render_project_usage_block(
    project_slug: str, usage_totals: dict[str, Any], doc_count: int
) -> str:
    """Per-project stats: raw-doc count + MCP calls / items / server processes.
    Empty when the project has neither raw docs nor telemetry."""
    p = (usage_totals or {}).get("per_project", {}).get(project_slug, {})
    calls = int(p.get("calls", 0) or 0)
    items = int(p.get("items_returned", 0) or 0)
    procs = int(p.get("server_processes", 0) or 0)
    if calls == 0 and doc_count == 0:
        return ""
    ptools = (usage_totals or {}).get("per_project_tool", {}).get(project_slug, {})
    tool_table = ""
    if ptools:
        rows = []
        for tool, s in sorted(ptools.items(), key=lambda kv: -kv[1].get("calls", 0)):
            calls_t = int(s.get("calls", 0) or 0)
            items_t = int(s.get("items_returned", 0) or 0)
            items_cell = str(items_t) if is_entity_tool(tool) else "—"
            rows.append(
                f'<tr><td>{html.escape(tool)}</td><td>{calls_t}</td><td>{items_cell}</td></tr>')
        tool_table = (
            '<table class="mcp-usage-table"><thead><tr>'
            '<th>Tool</th><th>Calls</th><th>Answers</th></tr></thead><tbody>'
            + "".join(rows) + '</tbody></table>')
    return (
        '<section class="section project-usage-section"><div class="container">'
        '<div class="token-stat-grid">'
        f'<div class="token-stat"><div class="token-stat-label muted">Raw documents</div>'
        f'<div class="token-stat-value">{int(doc_count)}</div></div>'
        f'<div class="token-stat"><div class="token-stat-label muted">MCP calls</div>'
        f'<div class="token-stat-value">{calls}</div></div>'
        f'<div class="token-stat"><div class="token-stat-label muted">MCP items returned</div>'
        f'<div class="token-stat-value">{items}</div></div>'
        f'<div class="token-stat"><div class="token-stat-label muted">MCP server processes</div>'
        f'<div class="token-stat-value">{procs}</div></div>'
        f'</div>{tool_table}</div></section>'
    )


def render_mcp_heaviest_card(
    usage_totals: dict[str, Any], link_prefix: str = ""
) -> str:
    """The "Heaviest project by MCP usage" stat card — the project with the
    most llm-wiki MCP calls. Shares the token-stats row. Empty string when
    there is no telemetry.

    Calls whose caller couldn't be identified are excluded (#51): the
    unattributed bucket isn't a project, and naming it here would both credit
    a project that never called and link to a page that doesn't exist."""
    per_project = {slug: s for slug, s in usage_totals.get("per_project", {}).items()
                   if slug != UNATTRIBUTED}
    if not per_project:
        return ""
    slug, s = max(per_project.items(), key=lambda kv: kv[1].get("calls", 0))
    calls = int(s.get("calls", 0) or 0)
    if calls == 0:
        return ""
    return (
        f'      <a class="token-stat" href="{link_prefix}projects/{html.escape(slug)}.html">'
        f'<div class="token-stat-label muted">Heaviest project by MCP usage</div>'
        f'<div class="token-stat-value">{calls}</div>'
        f'<div class="token-stat-sub muted">{html.escape(slug)} · calls</div></a>'
    )


def render_wiki_value_daily_chart(
    mcp_days: dict[str, dict[str, Any]],
    session_days: dict[str, int],
    *,
    width: int = 640,
    height: int = 120,
) -> str:
    """Pure-SVG dual series: MCP calls/day + wiki-using sessions/day (#52)."""
    all_days = sorted(set(mcp_days) | set(session_days))
    if len(all_days) < 1:
        return ""
    # Single-day still renders as bars so a fresh vault isn't blank.
    mcp_vals = [int((mcp_days.get(d) or {}).get("mcp_calls", 0) or 0) for d in all_days]
    sess_vals = [int(session_days.get(d, 0) or 0) for d in all_days]
    max_v = max(mcp_vals + sess_vals + [1])
    pad_l, pad_r, pad_t, pad_b = 28, 12, 10, 24
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b
    n = len(all_days)
    gap = 4
    slot = plot_w / n
    bar_w = max(2.0, min(14.0, slot - gap))

    def _bar(i: int, val: int, *, offset: float, cls: str) -> str:
        h = (val / max_v) * plot_h if max_v else 0
        x = pad_l + i * slot + offset
        y = pad_t + plot_h - h
        day = all_days[i]
        title = html.escape(f"{day}: {val}")
        return (
            f'<rect class="{cls}" x="{x:.1f}" y="{y:.1f}" '
            f'width="{bar_w:.1f}" height="{max(h, 0):.1f}" '
            f'data-date="{html.escape(day)}" data-count="{val}">'
            f'<title>{title}</title></rect>'
        )

    bars = []
    for i in range(n):
        bars.append(_bar(i, mcp_vals[i], offset=0, cls="wiki-value-bar mcp"))
        bars.append(_bar(i, sess_vals[i], offset=bar_w + 1, cls="wiki-value-bar sess"))
    # Axis labels: first + last day
    labels = (
        f'<text class="wiki-value-axis" x="{pad_l}" y="{height - 6}" '
        f'text-anchor="start">{html.escape(all_days[0])}</text>'
        f'<text class="wiki-value-axis" x="{width - pad_r}" y="{height - 6}" '
        f'text-anchor="end">{html.escape(all_days[-1])}</text>'
    )
    legend = (
        '<div class="wiki-value-legend muted">'
        '<span class="wiki-value-swatch mcp"></span> MCP calls · '
        '<span class="wiki-value-swatch sess"></span> Wiki-using sessions'
        '</div>'
    )
    svg = (
        f'<svg class="wiki-value-chart" xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {width} {height}" width="100%" height="{height}" '
        f'role="img" aria-label="Daily llmwiki MCP calls and wiki-using sessions">'
        + "".join(bars) + labels + "</svg>"
    )
    return legend + svg


def render_wiki_value_section(
    usage_totals: dict[str, Any],
    *,
    mcp_days: dict[str, dict[str, Any]] | None = None,
    session_days: dict[str, int] | None = None,
    corpus_mix: dict[str, int] | None = None,
    read_mix: dict[str, int] | None = None,
    top_pages: list[tuple[str, int]] | None = None,
    dead_stock: list[str] | None = None,
    dead_stock_total: int = 0,
    wiki_page_count: int = 0,
    estimate: dict[str, Any] | None = None,
) -> str:
    """Analytics "Wiki value" section (#52). Empty when there is no signal."""
    summary = value_summary(usage_totals or {}, wiki_page_count=wiki_page_count)
    mcp_days = mcp_days or {}
    session_days = session_days or {}
    corpus_mix = corpus_mix or {}
    read_mix = read_mix or {}
    top_pages = top_pages or []
    dead_stock = dead_stock or []
    has_usage = summary["total_calls"] > 0 or bool(mcp_days) or bool(session_days)
    has_corpus = int(corpus_mix.get("total", 0) or 0) > 0
    if not has_usage and not has_corpus:
        return ""

    cards = (
        '<div class="token-stat-grid wiki-value-stats">'
        f'<div class="token-stat"><div class="token-stat-label muted">Retrievals</div>'
        f'<div class="token-stat-value">{summary["retrievals"]}</div>'
        f'<div class="token-stat-sub muted">query · search · read_page</div></div>'
        f'<div class="token-stat"><div class="token-stat-label muted">Writes</div>'
        f'<div class="token-stat-value">{summary["writes"]}</div>'
        f'<div class="token-stat-sub muted">wiki_add</div></div>'
        f'<div class="token-stat"><div class="token-stat-label muted">Answer rate</div>'
        f'<div class="token-stat-value">{summary["answer_rate"] * 100:.0f}%</div>'
        f'<div class="token-stat-sub muted">entity tools with hits</div></div>'
        f'<div class="token-stat"><div class="token-stat-label muted">Payoff / page</div>'
        f'<div class="token-stat-value">{summary["payoff_per_page"]:.2f}</div>'
        f'<div class="token-stat-sub muted">retrievals ÷ {summary["wiki_page_count"]} pages</div></div>'
        f'<div class="token-stat"><div class="token-stat-label muted">Distinct projects</div>'
        f'<div class="token-stat-value">{summary["attributed_project_count"]}</div>'
        f'<div class="token-stat-sub muted">'
        f'{summary["unattributed_calls"]} unattributed calls</div></div>'
        '</div>'
    )

    cost_line = ""
    if estimate and (estimate.get("full_force_usd") or estimate.get("corpus_total")):
        ff = float(estimate.get("full_force_usd", 0) or 0)
        cost_line = (
            f'<p class="muted wiki-value-cost">Synthesis cost estimate (secondary): '
            f'${ff:,.2f} full-force · '
            f'{int(estimate.get("corpus_sessions", 0) or 0)} sessions · '
            f'{int(estimate.get("corpus_docs", 0) or 0)} docs</p>'
        )

    chart = render_wiki_value_daily_chart(mcp_days, session_days)
    chart_block = ""
    if chart:
        chart_block = (
            '<div class="wiki-value-chart-wrap">'
            '<h3>Daily usage</h3>'
            f'{chart}'
            '<p class="muted wiki-value-caption">MCP series is agent-agnostic (Claude, Cursor, '
            'Desktop, any MCP client). Session series is best-effort — Cursor '
            '<code>CallMcpTool</code> sessions count only when the transcript names llmwiki. '
            'Daily MCP totals are stored in <code>usage/daily.json</code> so they survive '
            'monthly log compaction.</p>'
            '</div>'
        )

    mix_block = ""
    if has_corpus or int(read_mix.get("total", 0) or 0) > 0:
        cs, cd = int(corpus_mix.get("session", 0)), int(corpus_mix.get("doc", 0))
        rs, rd, ro = (
            int(read_mix.get("session", 0)),
            int(read_mix.get("doc", 0)),
            int(read_mix.get("other", 0)),
        )
        rt = max(1, int(read_mix.get("total", 0) or 0)) if read_mix.get("total") else 0
        if rt:
            read_line = (
                f'Reads: {rs / rt * 100:.0f}% session · {rd / rt * 100:.0f}% doc'
                f' · {ro / rt * 100:.0f}% other'
            )
        else:
            read_line = "Reads: no wiki_read_page hits in retained telemetry"
        mix_block = (
            '<div class="wiki-value-mix">'
            '<h3>Sessions vs documents</h3>'
            f'<p>Corpus: {cs} session pages · {cd} doc pages</p>'
            f'<p class="muted">{read_line}</p>'
            '</div>'
        )

    top_block = ""
    if top_pages:
        items = "".join(
            f'<li><code>{html.escape(path)}</code> · {n}</li>'
            for path, n in top_pages[:8]
        )
        top_block = (
            '<div class="wiki-value-top">'
            '<h3>Top-earning pages</h3>'
            f'<ul class="wiki-value-list">{items}</ul>'
            '<p class="muted">By wiki_read_page hits in retained telemetry '
            '(live logs not yet compacted).</p>'
            '</div>'
        )

    dead_block = ""
    if dead_stock_total or dead_stock:
        sample = "".join(
            f'<li><code>{html.escape(p)}</code></li>' for p in dead_stock[:8]
        )
        more = (
            f'<p class="muted">…and {dead_stock_total - len(dead_stock)} more</p>'
            if dead_stock_total > len(dead_stock) else ""
        )
        dead_block = (
            '<div class="wiki-value-dead">'
            f'<h3>Dead stock ({dead_stock_total})</h3>'
            '<p class="muted">Synthesized source pages with no wiki_read_page hit '
            'in retained telemetry.</p>'
            f'<ul class="wiki-value-list">{sample}</ul>{more}'
            '</div>'
        )

    return (
        '<section class="section wiki-value-section"><div class="container">'
        '<h2>Wiki value</h2>'
        '<p class="muted">Usage-led signals: is the wiki being retrieved, by whom, '
        'and which pages earn their keep?</p>'
        f'{cards}{cost_line}{chart_block}{mix_block}{top_block}{dead_block}'
        '</div></section>'
    )


def render_mcp_usage_section(
    usage_totals: dict[str, Any],
    docs_by_project: dict[str, int],
    link_prefix: str = "",
) -> str:
    """Static "Wiki usage (MCP)" section: a one-line totals caption plus a
    per-tool calls/items/zero-hit table. Empty string when there is neither
    telemetry nor any raw document."""
    total_calls = int(usage_totals.get("total_calls", 0) or 0)
    total_docs = sum(docs_by_project.values()) if docs_by_project else 0
    if total_calls == 0 and total_docs == 0:
        return ""

    per_tool = usage_totals.get("per_tool", {})
    rows = []
    for tool, s in sorted(per_tool.items(), key=lambda kv: -kv[1].get("calls", 0)):
        calls = int(s.get("calls", 0) or 0)
        items = int(s.get("items_returned", 0) or 0)
        items_cell = str(items) if is_entity_tool(tool) else "—"
        zhr = float(s.get("zero_hit_rate", 0.0) or 0.0)
        rows.append(
            f'<tr><td>{html.escape(tool)}</td><td>{calls}</td>'
            f'<td>{items_cell}</td><td>{zhr * 100:.0f}%</td></tr>'
        )
    table = (
        '<table class="mcp-usage-table"><thead><tr>'
        '<th>Tool</th><th>Calls</th><th>Items returned</th><th>Zero-hit rate</th>'
        '</tr></thead><tbody>' + "".join(rows) + '</tbody></table>'
    ) if rows else ""

    total_items = int(usage_totals.get("total_items_returned", 0) or 0)
    total_procs = int(usage_totals.get("total_server_processes", 0) or 0)
    caption = (
        f'{total_calls} MCP calls · {total_items} items returned · '
        f'{total_procs} server processes · {total_docs} raw documents · '
        f'as of last build.'
    )
    return (
        '<section class="section mcp-usage-section"><div class="container">'
        '<h2>Wiki usage (MCP)</h2>'
        f'<p class="muted">{caption}</p>'
        f'{table}'
        '</div></section>'
    )


