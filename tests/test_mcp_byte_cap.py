"""Tests for #483 — MCP wiki_search / wiki_query must cap input bytes
to prevent OOM on huge files / huge corpora.

The bug: both tools called p.read_text() on every .md with no
size guard. `_SEARCH_HIT_CAP=200` capped output, not input. A
vault user with a 100MB Obsidian transcript thrashed the server
on every call.

The fix: `_read_capped(p, remaining_budget)` enforces a 4 MiB
per-file cap and a 50 MiB aggregate budget per call. Oversize
files are skipped entirely (no partial-read).
"""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import patch

from llmwiki.mcp.server import (
    _MCP_SCAN_AGGREGATE_BYTES,
    _MCP_SCAN_PER_FILE_BYTES,
    _read_capped,
    tool_wiki_search,
)


def _result_text(result: dict) -> str:
    return result["content"][0]["text"]


def _skipped_oversize(result: dict) -> int:
    """The oversize-skip counter the page-level rendering reports."""
    m = re.search(r"^skipped_oversize_files: (\d+)$", _result_text(result),
                  re.MULTILINE)
    assert m, f"no skipped_oversize_files line in: {_result_text(result)[:300]}"
    return int(m.group(1))


def test_read_capped_returns_text_under_cap(tmp_path: Path):
    p = tmp_path / "small.md"
    p.write_text("hello world\n", encoding="utf-8")
    text, consumed = _read_capped(p, remaining_budget=100_000)
    assert text == "hello world\n"
    assert consumed == len("hello world\n")


def test_read_capped_skips_oversize_file_entirely(tmp_path: Path):
    """Oversize files must be skipped (consumed=0) NOT partial-read."""
    p = tmp_path / "huge.md"
    big_content = "x" * (_MCP_SCAN_PER_FILE_BYTES + 1)
    p.write_text(big_content, encoding="utf-8")
    text, consumed = _read_capped(p, remaining_budget=_MCP_SCAN_AGGREGATE_BYTES)
    assert text == ""
    assert consumed == 0


def test_read_capped_respects_remaining_budget(tmp_path: Path):
    """File bigger than remaining budget but smaller than per-file
    cap → skip (cap is min of the two)."""
    p = tmp_path / "medium.md"
    p.write_text("y" * 1000, encoding="utf-8")
    text, consumed = _read_capped(p, remaining_budget=500)
    assert text == ""
    assert consumed == 0


def test_read_capped_zero_budget_skips(tmp_path: Path):
    p = tmp_path / "any.md"
    p.write_text("anything", encoding="utf-8")
    text, consumed = _read_capped(p, remaining_budget=0)
    assert text == ""
    assert consumed == 0


def test_read_capped_unreadable_file_returns_zero(tmp_path: Path):
    """Missing file returns ('', 0) gracefully — no exception."""
    p = tmp_path / "missing.md"
    text, consumed = _read_capped(p, remaining_budget=100_000)
    assert text == ""
    assert consumed == 0


def test_search_response_includes_skipped_oversize_counter(tmp_path: Path):
    """Surface the skipped count so callers know we didn't silently
    miss content."""
    wiki = tmp_path / "wiki"
    raw = tmp_path / "raw"
    wiki.mkdir()
    raw.mkdir()
    (wiki / "small.md").write_text("findme appears here\n", encoding="utf-8")
    (wiki / "huge.md").write_text("x" * (_MCP_SCAN_PER_FILE_BYTES + 100),
                                   encoding="utf-8")
    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        res = tool_wiki_search({"term": "findme"})
    text = _result_text(res)
    assert _skipped_oversize(res) >= 1, (
        f"expected ≥1 oversize file skipped, got: {text[:300]}"
    )
    assert "wiki/small.md" in text
    assert "findme appears here" in text


def test_search_normal_corpus_no_skips(tmp_path: Path):
    """Sanity: small-corpus calls should not report any skips."""
    wiki = tmp_path / "wiki"
    raw = tmp_path / "raw"
    wiki.mkdir()
    raw.mkdir()
    (wiki / "a.md").write_text("apple\n", encoding="utf-8")
    (wiki / "b.md").write_text("banana\n", encoding="utf-8")
    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        res = tool_wiki_search({"term": "apple"})
    assert _skipped_oversize(res) == 0
    assert "truncated: false" in _result_text(res)


def _budget_exhausted(result: dict) -> bool:
    m = re.search(r"^budget_exhausted: (true|false)$", _result_text(result),
                  re.MULTILINE)
    assert m, f"no budget_exhausted line in: {_result_text(result)[:300]}"
    return m.group(1) == "true"


def test_search_reports_budget_exhaustion(tmp_path: Path):
    """A scan that runs out of aggregate budget stopped short of the corpus.

    ``truncated`` only tracks the output caps, so without its own signal the
    footer reports a confidently complete scan over a partial one.
    """
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "small.md").write_text("findme\n", encoding="utf-8")
    (wiki / "wide.md").write_text("findme\n" * 400, encoding="utf-8")
    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path), \
            patch("llmwiki.mcp.server._MCP_SCAN_AGGREGATE_BYTES", 100):
        res = tool_wiki_search({"term": "findme"})
    assert _budget_exhausted(res)
    # Distinct from the oversize skip: the file is well within the per-file
    # cap, the call simply had no budget left for it.
    assert _skipped_oversize(res) == 0


def test_search_budget_exhaustion_is_reported_under_a_kind_filter(tmp_path: Path):
    """A narrow ``kind`` spends budget on files it then discards, so it
    reaches exhaustion on corpora a wide search would have finished."""
    wiki = tmp_path / "wiki"
    (wiki / "sources").mkdir(parents=True)
    (wiki / "projects").mkdir(parents=True)
    (wiki / "sources" / "transcript.md").write_text(
        '---\ntitle: "Transcript"\ntype: source\n---\n' + "findme\n" * 200,
        encoding="utf-8",
    )
    (wiki / "projects" / "ferry-line.md").write_text(
        '---\ntitle: "Ferry Line"\ntype: project\n---\n\nfindme\n',
        encoding="utf-8",
    )
    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path), \
            patch("llmwiki.mcp.server._MCP_SCAN_AGGREGATE_BYTES", 300):
        res = tool_wiki_search({"term": "findme", "kind": "project"})
    assert _budget_exhausted(res)


def test_search_within_budget_reports_a_complete_scan(tmp_path: Path):
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "a.md").write_text("findme\n", encoding="utf-8")
    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        res = tool_wiki_search({"term": "findme"})
    assert not _budget_exhausted(res)


def test_per_file_cap_constants_documented():
    """The cap values are part of the contract — make a future
    refactor that changes them notice this test."""
    assert _MCP_SCAN_PER_FILE_BYTES == 4 * 1024 * 1024
    assert _MCP_SCAN_AGGREGATE_BYTES == 50 * 1024 * 1024
