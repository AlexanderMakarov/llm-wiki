"""Tests for the enhanced MCP tools (v1.0, #159) and the merged
``wiki_search`` (#102)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from unittest.mock import patch

from llmwiki.lint.rules.frontmatter_validity import FrontmatterValidity
from llmwiki.mcp.server import (
    TOOL_IMPLS,
    TOOLS,
    tool_wiki_category_browse,
    tool_wiki_confidence,
    tool_wiki_dashboard,
    tool_wiki_lifecycle,
    tool_wiki_search,
)
from llmwiki.schema import ALL_PAGE_KINDS, PAGE_KINDS, SYSTEM_PAGE_KINDS


def _search_schema() -> dict:
    return next(t for t in TOOLS if t["name"] == "wiki_search")["inputSchema"]

# ─── Registration ─────────────────────────────────────────────────────


def test_all_12_tools_registered():
    assert len(TOOLS) == 12
    names = {t["name"] for t in TOOLS}
    for required in ["wiki_query", "wiki_search", "wiki_list_sources",
                      "wiki_read_page", "wiki_lint", "wiki_sync", "wiki_export",
                      "wiki_confidence", "wiki_lifecycle", "wiki_dashboard",
                      "wiki_category_browse", "wiki_add"]:
        assert required in names


def test_search_is_the_only_search_tool():
    """One search tool spans every page kind — no separate entity search."""
    names = {t["name"] for t in TOOLS}
    assert "wiki_entity_search" not in names
    assert "wiki_entity_search" not in TOOL_IMPLS
    assert [n for n in names if "search" in n] == ["wiki_search"]


def test_all_tools_have_impl():
    for tool in TOOLS:
        assert tool["name"] in TOOL_IMPLS


# ─── wiki_confidence ─────────────────────────────────────────────────


def test_confidence_filter_by_min(tmp_path: Path):
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "a.md").write_text(
        '---\ntitle: "A"\ntype: entity\nconfidence: 0.9\n---\n', encoding="utf-8"
    )
    (wiki / "b.md").write_text(
        '---\ntitle: "B"\ntype: entity\nconfidence: 0.3\n---\n', encoding="utf-8"
    )
    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_confidence({"min_confidence": 0.8})
    text = result["content"][0]["text"]
    assert "a.md" in text
    assert "b.md" not in text


def test_confidence_filter_by_max(tmp_path: Path):
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "low.md").write_text(
        '---\ntitle: "L"\ntype: entity\nconfidence: 0.3\n---\n', encoding="utf-8"
    )
    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_confidence({"max_confidence": 0.5})
    assert "low.md" in result["content"][0]["text"]


def test_confidence_skips_pages_without_field(tmp_path: Path):
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "a.md").write_text(
        '---\ntitle: "A"\ntype: entity\n---\n', encoding="utf-8"
    )
    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_confidence({})
    assert "0 pages" in result["content"][0]["text"]


def test_confidence_handles_invalid_value(tmp_path: Path):
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "a.md").write_text(
        '---\ntitle: "A"\ntype: entity\nconfidence: high\n---\n', encoding="utf-8"
    )
    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_confidence({})
    assert "0 pages" in result["content"][0]["text"]


# ─── wiki_lifecycle ──────────────────────────────────────────────────


def test_lifecycle_requires_state():
    result = tool_wiki_lifecycle({})
    assert result.get("isError") is True


def test_lifecycle_filters_by_state(tmp_path: Path):
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "a.md").write_text(
        '---\ntitle: "A"\nlifecycle: draft\n---\n', encoding="utf-8"
    )
    (wiki / "b.md").write_text(
        '---\ntitle: "B"\nlifecycle: verified\n---\n', encoding="utf-8"
    )
    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_lifecycle({"state": "draft"})
    text = result["content"][0]["text"]
    assert "a.md" in text
    assert "b.md" not in text


def test_lifecycle_empty_state(tmp_path: Path):
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_lifecycle({"state": "verified"})
    assert "0 pages" in result["content"][0]["text"]


# ─── wiki_dashboard ──────────────────────────────────────────────────


def test_dashboard_counts_by_type(tmp_path: Path):
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "a.md").write_text(
        '---\ntitle: "A"\ntype: entity\n---\n', encoding="utf-8"
    )
    (wiki / "b.md").write_text(
        '---\ntitle: "B"\ntype: concept\n---\n', encoding="utf-8"
    )
    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_dashboard({})
    text = result["content"][0]["text"]
    assert "entity" in text
    assert "concept" in text


def test_dashboard_confidence_buckets(tmp_path: Path):
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "high.md").write_text(
        '---\ntitle: "H"\ntype: entity\nconfidence: 0.95\n---\n', encoding="utf-8"
    )
    (wiki / "low.md").write_text(
        '---\ntitle: "L"\ntype: entity\nconfidence: 0.2\n---\n', encoding="utf-8"
    )
    (wiki / "none.md").write_text(
        '---\ntitle: "N"\ntype: entity\n---\n', encoding="utf-8"
    )
    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_dashboard({})
    text = result["content"][0]["text"]
    assert "high" in text
    assert "low" in text


def test_dashboard_handles_empty_wiki(tmp_path: Path):
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_dashboard({})
    text = result["content"][0]["text"]
    assert "0 pages" in text


# ─── wiki_search (merged, #102) ──────────────────────────────────────


def _seed_kinds_vault(root: Path) -> None:
    """One page per kind, all mentioning "harbour" somewhere."""
    wiki = root / "wiki"
    (wiki / "entities").mkdir(parents=True)
    (wiki / "concepts").mkdir(parents=True)
    (wiki / "projects").mkdir(parents=True)
    (wiki / "entities" / "Harbour.md").write_text(
        '---\ntitle: "Harbour"\ntype: entity\n---\n\n# Harbour\n\nA port.\n',
        encoding="utf-8",
    )
    (wiki / "concepts" / "Docking.md").write_text(
        '---\ntitle: "Docking"\ntype: concept\n---\n\n'
        "# Docking\n\nShips dock at a harbour when they arrive.\n",
        encoding="utf-8",
    )
    (wiki / "projects" / "ferry-line.md").write_text(
        '---\ntitle: "Ferry Line"\ntype: project\n---\n\n'
        "# Ferry Line\n\nRuns between one harbour and the next.\n",
        encoding="utf-8",
    )


def _search_text(result: dict) -> str:
    return result["content"][0]["text"]


def _pages_in_order(result: dict) -> list[str]:
    """Ordered page paths from the page-level rendering."""
    return re.findall(r"^(\S+\.md)(?: — |$)", _search_text(result), re.MULTILINE)


def test_search_spans_every_kind(tmp_path: Path):
    _seed_kinds_vault(tmp_path)
    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_search({"term": "harbour"})
    pages = _pages_in_order(result)
    assert len(pages) == 3
    assert any("entities" in p for p in pages)
    assert any("concepts" in p for p in pages)
    assert any("projects" in p for p in pages)


def test_search_kind_narrows_to_one_page_kind(tmp_path: Path):
    _seed_kinds_vault(tmp_path)
    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_search({"term": "harbour", "kind": "concept"})
    pages = _pages_in_order(result)
    assert pages == ["wiki/concepts/Docking.md"]


def test_search_kind_accepts_project(tmp_path: Path):
    _seed_kinds_vault(tmp_path)
    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_search({"term": "harbour", "kind": "project"})
    assert _pages_in_order(result) == ["wiki/projects/ferry-line.md"]


def test_search_unknown_kind_is_rejected(tmp_path: Path):
    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_search({"term": "harbour", "kind": "banana"})
    assert result.get("isError") is True
    assert "unknown kind" in _search_text(result)


def test_search_name_match_ranks_above_body_match(tmp_path: Path):
    wiki = tmp_path / "wiki"
    (wiki / "entities").mkdir(parents=True)
    (wiki / "concepts").mkdir(parents=True)
    (wiki / "entities" / "Beacon.md").write_text(
        '---\ntitle: "Beacon"\ntype: entity\n---\n\n# Beacon\n\nA light.\n',
        encoding="utf-8",
    )
    # Sorts ahead of the name match on path alone, so only the
    # name-before-body rule can put the entity page first.
    (wiki / "concepts" / "Anchoring.md").write_text(
        '---\ntitle: "Anchoring"\ntype: concept\n---\n\n'
        "# Anchoring\n\nWe anchored past the beacon at dusk.\n",
        encoding="utf-8",
    )
    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_search({"term": "beacon"})
    pages = _pages_in_order(result)
    assert pages == ["wiki/entities/Beacon.md", "wiki/concepts/Anchoring.md"]


def test_search_returns_name_match_without_body_hit(tmp_path: Path):
    """A page whose path matches but whose text never does still comes back."""
    wiki = tmp_path / "wiki"
    (wiki / "entities").mkdir(parents=True)
    (wiki / "entities" / "Lighthouse.md").write_text(
        '---\ntitle: "Keeper"\ntype: entity\n---\n\n# Keeper\n\nTends the lamp.\n',
        encoding="utf-8",
    )
    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_search({"term": "lighthouse"})
    text = _search_text(result)
    assert _pages_in_order(result) == ["wiki/entities/Lighthouse.md"]
    assert not [ln for ln in text.splitlines() if ln.startswith("  :")]


def test_search_results_are_page_level(tmp_path: Path):
    """`path — title` with matching lines indented beneath it."""
    wiki = tmp_path / "wiki"
    (wiki / "concepts").mkdir(parents=True)
    (wiki / "concepts" / "Tides.md").write_text(
        '---\ntitle: "Tides"\ntype: concept\n---\n\n'
        "# Tides\n\nspring tide\nneap tide\n",
        encoding="utf-8",
    )
    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_search({"term": "tide"})
    text = _search_text(result)
    assert "wiki/concepts/Tides.md — Tides" in text
    assert "  :8: spring tide" in text
    assert "  :9: neap tide" in text


def _seed_source_corpora(root: Path) -> None:
    """A wiki source page and the raw transcript behind it.

    Both carry ``type: source`` — the raw converter stamps it, which is why
    ``kind`` and ``include_raw`` compose instead of excluding each other.
    """
    sources = root / "wiki" / "sources"
    sources.mkdir(parents=True)
    (sources / "ferry-log.md").write_text(
        '---\ntitle: "Ferry log"\ntype: source\n---\n\n'
        "## Summary\n\nThe crew reached the harbour at dawn.\n",
        encoding="utf-8",
    )
    sessions = root / "raw" / "sessions"
    sessions.mkdir(parents=True)
    (sessions / "2026-01-01T09-00-ferry.md").write_text(
        '---\ntitle: "Ferry session"\ntype: source\n---\n\n'
        "We sailed into the harbour.\n",
        encoding="utf-8",
    )


RAW_FERRY = "raw/sessions/2026-01-01T09-00-ferry.md"
WIKI_FERRY = "wiki/sources/ferry-log.md"


def test_search_kind_source_with_include_raw_spans_both_corpora(tmp_path: Path):
    """`kind` filters, `include_raw` selects corpora — they compose."""
    _seed_kinds_vault(tmp_path)
    _seed_source_corpora(tmp_path)
    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_search(
            {"term": "harbour", "kind": "source", "include_raw": True}
        )
    assert result.get("isError") is not True
    assert sorted(_pages_in_order(result)) == [RAW_FERRY, WIKI_FERRY]


def test_search_kind_no_raw_file_declares_yields_empty_raw_contribution(
    tmp_path: Path,
):
    """A kind no raw file carries just contributes nothing — not an error."""
    _seed_kinds_vault(tmp_path)
    _seed_source_corpora(tmp_path)
    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_search(
            {"term": "harbour", "kind": "project", "include_raw": True}
        )
    assert result.get("isError") is not True
    assert _pages_in_order(result) == ["wiki/projects/ferry-line.md"]


def test_search_include_raw_without_kind_scans_everything(tmp_path: Path):
    _seed_kinds_vault(tmp_path)
    _seed_source_corpora(tmp_path)
    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_search({"term": "harbour", "include_raw": True})
    pages = _pages_in_order(result)
    assert RAW_FERRY in pages
    assert WIKI_FERRY in pages
    assert "wiki/entities/Harbour.md" in pages


def test_search_kind_without_include_raw_stays_wiki_only(tmp_path: Path):
    _seed_kinds_vault(tmp_path)
    _seed_source_corpora(tmp_path)
    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_search({"term": "harbour", "kind": "source"})
    assert _pages_in_order(result) == [WIKI_FERRY]


def test_search_kind_schema_offers_project(tmp_path: Path):
    schema = _search_schema()
    assert schema["required"] == ["term"]
    assert "project" in schema["properties"]["kind"]["enum"]
    assert "entity" in schema["properties"]["kind"]["enum"]


# ─── page-kind vocabulary ────────────────────────────────────────────


def test_page_kinds_are_sourced_from_the_schema_module():
    """One vocabulary, two consumers: the public MCP input schema and the
    lint rule that validates frontmatter. Editing a lint rule must not be
    able to change the tool contract."""
    assert _search_schema()["properties"]["kind"]["enum"] == list(PAGE_KINDS)
    assert FrontmatterValidity.VALID_TYPES == set(ALL_PAGE_KINDS)


def test_search_does_not_offer_system_page_kinds():
    """``navigation`` and ``context`` are build/query machinery, not a kind
    anyone searches *for* — advertising them invites a filter that returns
    only plumbing."""
    offered = set(_search_schema()["properties"]["kind"]["enum"])
    assert not offered & set(SYSTEM_PAGE_KINDS)
    for kind in SYSTEM_PAGE_KINDS:
        result = tool_wiki_search({"term": "harbour", "kind": kind})
        assert result.get("isError") is True
        assert "unknown kind" in _search_text(result)


def test_unfiltered_search_still_reaches_system_pages(tmp_path: Path):
    """Excluding a kind from the filter must not exclude it from search."""
    entities = tmp_path / "wiki" / "entities"
    entities.mkdir(parents=True)
    (entities / "_context.md").write_text(
        '---\ntitle: "Entities"\ntype: context\n---\n\n'
        "Harbour towns and the people who run them.\n",
        encoding="utf-8",
    )
    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_search({"term": "harbour"})
    assert "wiki/entities/_context.md" in _search_text(result)


# ─── machine-readable mode + telemetry ───────────────────────────────


def test_search_json_format_returns_a_parseable_payload(tmp_path: Path):
    """Prose is for a reader; a caller that parses gets structure instead of
    a JSONDecodeError."""
    _seed_kinds_vault(tmp_path)
    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_search({"term": "harbour", "format": "json"})
    payload = json.loads(_search_text(result))
    assert payload["term"] == "harbour"
    assert payload["kind"] is None
    assert payload["include_raw"] is False
    assert payload["truncated"] is False
    assert payload["budget_exhausted"] is False
    assert payload["skipped_oversize_files"] == 0
    docking = next(pg for pg in payload["pages"]
                   if pg["path"] == "wiki/concepts/Docking.md")
    assert docking["title"] == "Docking"
    assert docking["name_match"] is False
    assert [ln["line"] for ln in docking["lines"]] == [8]
    assert "harbour" in docking["lines"][0]["text"]


def test_search_json_format_keeps_the_documented_ranking(tmp_path: Path):
    _seed_kinds_vault(tmp_path)
    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_search({"term": "harbour", "format": "json"})
    pages = json.loads(_search_text(result))["pages"]
    assert pages[0]["path"] == "wiki/entities/Harbour.md"
    assert pages[0]["name_match"] is True


def test_search_unknown_format_is_rejected(tmp_path: Path):
    result = tool_wiki_search({"term": "harbour", "format": "yaml"})
    assert result.get("isError") is True
    assert "unknown format" in _search_text(result)


def test_search_format_is_advertised_in_the_schema():
    fmt = _search_schema()["properties"]["format"]
    assert fmt["enum"] == ["text", "json"]
    assert fmt["default"] == "text"


def test_search_reports_result_rows_to_telemetry(tmp_path: Path):
    """``hits`` feeds one persisted series shared with every other tool, so
    it stays in result-row units — one per matching line, plus one for a
    page matched by name alone, which renders as a bare header."""
    wiki = tmp_path / "wiki"
    wiki.mkdir(parents=True)
    (wiki / "notes.md").write_text("alpha tide\nbeta tide\n", encoding="utf-8")
    (wiki / "tide-brief.md").write_text("nothing here\n", encoding="utf-8")
    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_search({"term": "tide"})
    assert result["_hits"] == 3


# ─── wiki_category_browse ────────────────────────────────────────────


def test_category_browse_lists_all(tmp_path: Path):
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "a.md").write_text(
        '---\ntitle: "A"\ntags: [flutter, mobile]\n---\n', encoding="utf-8"
    )
    (wiki / "b.md").write_text(
        '---\ntitle: "B"\ntags: [flutter]\n---\n', encoding="utf-8"
    )
    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_category_browse({})
    text = result["content"][0]["text"]
    assert "flutter" in text
    assert "mobile" in text


def test_category_browse_specific_tag(tmp_path: Path):
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "a.md").write_text(
        '---\ntitle: "A"\ntags: [flutter]\n---\n', encoding="utf-8"
    )
    (wiki / "b.md").write_text(
        '---\ntitle: "B"\ntags: [python]\n---\n', encoding="utf-8"
    )
    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_category_browse({"tag": "flutter"})
    text = result["content"][0]["text"]
    assert "a.md" in text
    assert "b.md" not in text


def test_category_browse_min_count(tmp_path: Path):
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "a.md").write_text(
        '---\ntitle: "A"\ntags: [popular]\n---\n', encoding="utf-8"
    )
    (wiki / "b.md").write_text(
        '---\ntitle: "B"\ntags: [popular]\n---\n', encoding="utf-8"
    )
    (wiki / "c.md").write_text(
        '---\ntitle: "C"\ntags: [lonely]\n---\n', encoding="utf-8"
    )
    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        result = tool_wiki_category_browse({"min_count": 2})
    text = result["content"][0]["text"]
    assert "popular" in text
    assert "lonely" not in text
