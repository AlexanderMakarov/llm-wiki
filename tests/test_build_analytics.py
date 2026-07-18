from llmwiki.build import render_mcp_usage_section


def test_mcp_section_renders_tools_and_totals():
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
    assert "Most MCP-active project" in html_out
    assert "proj-x" in html_out
    assert "40" in html_out            # items returned total
    assert "5" in html_out             # raw docs count


def test_mcp_section_empty_without_data():
    empty = {"total_calls": 0, "total_items_returned": 0, "total_server_processes": 0,
             "per_tool": {}, "per_project": {}}
    assert render_mcp_usage_section(empty, {}, link_prefix="") == ""
