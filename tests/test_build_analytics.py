from llmwiki.build import (
    render_mcp_heaviest_card,
    render_mcp_usage_section,
    render_project_usage_block,
    render_wiki_value_section,
)


def test_mcp_section_renders_tools_and_totals_caption():
    totals = {
        "total_calls": 12, "total_items_returned": 40, "total_server_processes": 3,
        "per_tool": {
            "wiki_search": {"calls": 8, "zero_hits": 2, "zero_hit_rate": 0.25, "resp_bytes": 0, "items_returned": 30},
            "wiki_lint":   {"calls": 4, "zero_hits": 0, "zero_hit_rate": 0.0,  "resp_bytes": 0, "items_returned": 0},
        },
        "per_project": {"proj-x": {"calls": 12, "resp_bytes": 0, "items_returned": 40, "server_processes": 3}},
    }
    html_out = render_mcp_usage_section(totals, {"proj-x": 5}, link_prefix="")
    assert "wiki_search" in html_out
    assert "mcp-usage-table" in html_out             # per-tool table present
    assert "12 MCP calls" in html_out                # totals caption
    assert "40 items returned" in html_out
    assert "3 server processes" in html_out
    assert "5 raw documents" in html_out
    # the most-active project moved out of this section into its own card
    assert "Most MCP-active project" not in html_out


def test_mcp_section_empty_without_data():
    empty = {"total_calls": 0, "total_items_returned": 0, "total_server_processes": 0,
             "per_tool": {}, "per_project": {}}
    assert render_mcp_usage_section(empty, {}, link_prefix="") == ""


def test_mcp_heaviest_card_picks_top_project():
    totals = {"per_project": {
        "proj-a": {"calls": 3}, "proj-b": {"calls": 9}, "proj-c": {"calls": 1},
    }}
    card = render_mcp_heaviest_card(totals, link_prefix="")
    assert "Heaviest project by MCP usage" in card
    assert "proj-b" in card and ">9<" in card
    assert 'href="projects/proj-b.html"' in card


def test_mcp_heaviest_card_ignores_unattributed_calls():
    """#51: the unattributed bucket is not a project — surfacing it would both
    name a project that never called and link to a page that doesn't exist."""
    totals = {"per_project": {
        "unknown": {"calls": 42}, "proj-a": {"calls": 3},
    }}
    card = render_mcp_heaviest_card(totals, link_prefix="")
    assert "proj-a" in card and ">3<" in card
    assert "unknown" not in card


def test_mcp_heaviest_card_empty_when_every_call_is_unattributed():
    assert render_mcp_heaviest_card(
        {"per_project": {"unknown": {"calls": 42}}}, link_prefix="") == ""


def test_mcp_heaviest_card_empty_without_telemetry():
    assert render_mcp_heaviest_card({"per_project": {}}, link_prefix="") == ""
    assert render_mcp_heaviest_card({"per_project": {"p": {"calls": 0}}}, link_prefix="") == ""


def test_project_usage_block_shows_project_slice():
    totals = {"per_project": {"proj-x": {"calls": 7, "items_returned": 20, "server_processes": 2, "resp_bytes": 0}},
              "per_tool": {}}
    out = render_project_usage_block("proj-x", totals, doc_count=4)
    # anchor on the value cells so a wrong number can't pass on an incidental
    # substring match (e.g. "2" inside a class name)
    assert ">7</div>" in out       # MCP calls
    assert ">20</div>" in out      # items returned
    assert ">2</div>" in out       # server processes
    assert ">4</div>" in out       # raw documents
    assert "MCP server processes" in out


def test_project_usage_block_empty_without_data():
    totals = {"per_project": {}, "per_tool": {}}
    assert render_project_usage_block("proj-x", totals, doc_count=0) == ""


def test_project_usage_block_renders_per_tool_table():
    totals = {
        "per_project": {"proj-x": {"calls": 3, "items_returned": 7, "server_processes": 1, "resp_bytes": 0}},
        "per_project_tool": {"proj-x": {
            "wiki_search": {"calls": 2, "items_returned": 7},
            "wiki_lint":   {"calls": 1, "items_returned": 0},
        }},
        "per_tool": {},
    }
    out = render_project_usage_block("proj-x", totals, doc_count=0)
    assert "wiki_search" in out and "wiki_lint" in out
    assert "mcp-usage-table" in out          # per-tool table present
    assert "—" in out                        # wiki_lint (non-entity) items cell is em dash


def test_wiki_value_section_renders_cards_and_chart():
    totals = {
        "total_calls": 10,
        "per_tool": {
            "wiki_query": {"calls": 4, "zero_hits": 1},
            "wiki_search": {"calls": 3, "zero_hits": 0},
            "wiki_add": {"calls": 2, "zero_hits": 0},
            "wiki_lint": {"calls": 1, "zero_hits": 0},
        },
        "per_project": {
            "unknown": {"calls": 5},
            "proj-a": {"calls": 5},
        },
    }
    out = render_wiki_value_section(
        totals,
        mcp_days={
            "2026-07-18": {"mcp_calls": 2},
            "2026-07-19": {"mcp_calls": 8},
        },
        session_days={"2026-07-18": 1, "2026-07-19": 3},
        corpus_mix={"session": 10, "doc": 4, "other": 0, "total": 14},
        read_mix={"session": 3, "doc": 1, "other": 0, "total": 4},
        top_pages=[("wiki/sources/a.md", 5)],
        dead_stock=["wiki/sources/dead.md"],
        dead_stock_total=1,
        wiki_page_count=14,
    )
    assert "Wiki value" in out
    assert "Retrievals" in out
    assert ">7</div>" in out
    assert "Distinct projects" in out
    assert ">1</div>" in out  # attributed project count
    assert "unattributed calls" in out
    assert "wiki-value-chart" in out
    assert "wiki-value-bar mcp" in out
    assert "wiki-value-bar sess" in out
    assert "Corpus: 10 session pages · 4 doc pages" in out
    assert "Top-earning pages" in out
    assert "wiki/sources/a.md" in out
    assert "Dead stock (1)" in out


def test_wiki_value_section_empty_without_data():
    assert render_wiki_value_section(
        {"total_calls": 0, "per_tool": {}, "per_project": {}},
    ) == ""


def test_wiki_value_excludes_unknown_from_distinct_projects():
    totals = {
        "total_calls": 3,
        "per_tool": {"wiki_query": {"calls": 3, "zero_hits": 0}},
        "per_project": {"unknown": {"calls": 3}},
    }
    out = render_wiki_value_section(totals, wiki_page_count=1)
    assert "Distinct projects" in out
    assert ">0</div>" in out
    assert "3 unattributed calls" in out
