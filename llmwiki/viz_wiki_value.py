"""Analytics MCP usage + Wiki value HTML renderers (#27, #52).

Extracted from ``build.py`` so the site orchestrator stays under the
line-count ceiling while the value layer stays independently testable.
"""
from __future__ import annotations

import html
from typing import Any

from llmwiki.render.collapse_section import collapse_section_list
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


def _render_mcp_usage_inner(
    usage_totals: dict[str, Any],
    docs_by_project: dict[str, int],
) -> str:
    """MCP totals caption + per-tool table — no outer section wrapper."""
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
        '<div class="wiki-usage-mcp">'
        '<h3>MCP tools</h3>'
        f'<p class="muted">{caption}</p>'
        f'{table}'
        '</div>'
    )


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
    docs_by_project: dict[str, int] | None = None,
) -> str:
    """Analytics "LLM-Wiki MCP usage" section (#52) — value cards, mix, MCP table."""
    summary = value_summary(usage_totals or {}, wiki_page_count=wiki_page_count)
    mcp_days = mcp_days or {}
    session_days = session_days or {}
    corpus_mix = corpus_mix or {}
    read_mix = read_mix or {}
    top_pages = top_pages or []
    dead_stock = dead_stock or []
    docs_by_project = docs_by_project or {}
    total_docs = sum(docs_by_project.values()) if docs_by_project else 0
    has_usage = summary["total_calls"] > 0 or bool(mcp_days) or bool(session_days)
    has_corpus = int(corpus_mix.get("total", 0) or 0) > 0
    has_mcp_table = summary["total_calls"] > 0 or total_docs > 0
    if not has_usage and not has_corpus and not has_mcp_table:
        return ""

    cards = (
        '<div class="token-stat-grid wiki-value-stats">'
        f'<div class="token-stat"><div class="token-stat-label muted">Retrievals</div>'
        f'<div class="token-stat-value">{summary["retrievals"]}</div>'
        f'<div class="token-stat-sub muted">search · read</div></div>'
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

    mcp_inner = _render_mcp_usage_inner(usage_totals or {}, docs_by_project)

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

        items = [
            f"<li><code>{html.escape(p)}</code></li>" for p in dead_stock
        ]
        intro = (
            '<p class="muted">Synthesized source pages with no wiki_read_page hit '
            "in retained telemetry.</p>"
        )
        dead_block = (
            '<div class="wiki-value-dead">'
            + collapse_section_list(
                "Dead stock",
                items,
                count=dead_stock_total or len(dead_stock),
                intro_html=intro,
                extra_class="wiki-value-dead-collapse",
            )
            + "</div>"
        )

    return (
        '<section class="section wiki-usage-section"><div class="container">'
        '<h2>LLM-Wiki MCP usage</h2>'
        '<p class="muted">MCP telemetry only: is the wiki being retrieved via '
        'llmwiki tools, by whom, and which pages earn their keep?</p>'
        f'{cards}{cost_line}{mix_block}{top_block}{dead_block}{mcp_inner}'
        '</div></section>'
    )


def render_candidates_review_section(
    *,
    pending: int = 0,
    stale: int = 0,
    by_kind: dict[str, int] | None = None,
    stale_days: int = 30,
) -> str:
    """Analytics cards for the candidates review queue (#84).

    Always rendered (including zeros) so a synthesize-only vault still shows
    that the review gate exists and is empty — not missing.
    """
    by_kind = by_kind or {}
    kind_bits = " · ".join(f"{k} {n}" for k, n in sorted(by_kind.items()) if n)
    kind_sub = kind_bits or "no stubs under wiki/candidates/"
    return (
        '<section class="section candidates-review-section"><div class="container">'
        '<h2><a href="candidates.html">Candidates to review</a></h2>'
        '<p class="muted">Pending entity/concept stubs. Drain via the Candidates page '
        "(copy its <code>llmwiki candidates apply --actions</code> command), "
        "agent <code>/wiki-candidates</code>, or CLI "
        "<code>apply</code> / <code>promote</code> / <code>flip-promote</code> / "
        "<code>merge</code> / <code>discard</code>. Synthesis alone does not "
        "finish the trusted layer.</p>"
        '<div class="token-stat-grid wiki-value-stats wiki-candidates-stats">'
        '<div class="token-stat"><div class="token-stat-label muted">'
        '<a href="candidates.html">Pending candidates</a></div>'
        f'<div class="token-stat-value"><a href="candidates.html">{int(pending)}</a></div>'
        f'<div class="token-stat-sub muted">{html.escape(kind_sub)}</div></div>'
        '<div class="token-stat"><div class="token-stat-label muted">Stale candidates</div>'
        f'<div class="token-stat-value">{int(stale)}</div>'
        f'<div class="token-stat-sub muted">age ≥ {int(stale_days)}d · '
        "<code>llmwiki candidates list --stale</code></div></div>"
        "</div></div></section>"
    )


def render_mcp_usage_section(
    usage_totals: dict[str, Any],
    docs_by_project: dict[str, int],
    link_prefix: str = "",
) -> str:
    """Standalone MCP section — kept for tests; analytics merges into MCP usage."""
    inner = _render_mcp_usage_inner(usage_totals, docs_by_project)
    if not inner:
        return ""
    return (
        '<section class="section mcp-usage-section"><div class="container">'
        '<h2>LLM-Wiki MCP usage</h2>'
        f'{inner}'
        '</div></section>'
    )


