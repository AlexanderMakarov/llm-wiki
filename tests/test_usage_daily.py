"""Tests for usage/daily.json persistence and value aggregates (#52)."""
from __future__ import annotations

import json
from pathlib import Path

from llmwiki import usage


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def test_day_buckets_from_records_counts_retrievals_and_writes():
    records = [
        {"ts": "2026-07-19T10:00:00Z", "tool": "wiki_query",
         "caller_project": "a", "caller_source": "client-root"},
        {"ts": "2026-07-19T11:00:00Z", "tool": "wiki_search",
         "caller_project": "a", "caller_source": "client-root"},
        {"ts": "2026-07-19T12:00:00Z", "tool": "wiki_add",
         "caller_project": "b", "caller_source": "project-dir-env"},
        {"ts": "2026-07-20T09:00:00Z", "tool": "wiki_lint",
         "caller_project": "unknown", "caller_source": "unattributed"},
        {"ts": "bad", "tool": "wiki_query"},  # skipped — no day
    ]
    days = usage.day_buckets_from_records(records)
    assert days["2026-07-19"]["mcp_calls"] == 3
    assert days["2026-07-19"]["retrievals"] == 2
    assert days["2026-07-19"]["writes"] == 1
    assert days["2026-07-19"]["session_reads"] == 0
    assert days["2026-07-19"]["doc_reads"] == 0
    assert days["2026-07-19"]["other_reads"] == 0
    assert days["2026-07-19"]["attributed_projects"] == 2
    assert days["2026-07-19"]["by_tool"]["wiki_query"] == 1
    assert days["2026-07-20"]["mcp_calls"] == 1
    assert days["2026-07-20"]["unattributed_calls"] == 1
    assert days["2026-07-20"]["attributed_projects"] == 0


def test_day_buckets_session_vs_doc_reads(tmp_path: Path):
    wiki = tmp_path / "wiki"
    sources = wiki / "sources"
    sources.mkdir(parents=True)
    (sources / "sess.md").write_text(
        "---\nsource_file: raw/sessions/p/s.md\n---\n", encoding="utf-8")
    (sources / "doc.md").write_text(
        "---\nsource_file: raw/docs/p/d.md\n---\n", encoding="utf-8")
    (sources / "tagged.md").write_text(
        "---\ntags: [wiki-add, raw-doc]\n---\n", encoding="utf-8")
    records = [
        {"ts": "2026-07-19T10:00:00Z", "tool": "wiki_read_page",
         "query": "wiki/sources/sess.md"},
        {"ts": "2026-07-19T11:00:00Z", "tool": "wiki_read_page",
         "query": "sources/doc.md"},
        {"ts": "2026-07-19T12:00:00Z", "tool": "wiki_read_page",
         "query": "wiki/sources/tagged.md"},
        {"ts": "2026-07-19T13:00:00Z", "tool": "wiki_read_page",
         "query": "wiki/entities/Foo.md"},
    ]
    days = usage.day_buckets_from_records(records, wiki_root=wiki)
    bucket = days["2026-07-19"]
    assert bucket["session_reads"] == 1
    assert bucket["doc_reads"] == 2  # source_file doc + raw-doc tags
    assert bucket["other_reads"] == 1
    assert bucket["retrievals"] == 4


def test_day_buckets_read_kind_path_heuristics_without_wiki_root():
    """When wiki_root is absent, raw/sessions vs raw/docs in the path classify reads."""
    records = [
        {"ts": "2026-07-19T10:00:00Z", "tool": "wiki_read_page",
         "query": "raw/sessions/foo/bar.md"},
        {"ts": "2026-07-19T11:00:00Z", "tool": "wiki_read_page",
         "query": "raw/docs/foo/bar.md"},
        {"ts": "2026-07-19T12:00:00Z", "tool": "wiki_read_page",
         "query": "wiki/sources/unknown.md"},
    ]
    days = usage.day_buckets_from_records(records)
    bucket = days["2026-07-19"]
    assert bucket["session_reads"] == 1
    assert bucket["doc_reads"] == 1
    assert bucket["other_reads"] == 1


def test_merge_day_buckets_sums_read_kinds():
    a = {"2026-07-19": {"mcp_calls": 1, "session_reads": 2, "doc_reads": 1}}
    b = {"2026-07-19": {"mcp_calls": 3, "session_reads": 1, "other_reads": 2}}
    merged = usage.merge_day_buckets(a, b)
    assert merged["2026-07-19"]["session_reads"] == 3
    assert merged["2026-07-19"]["doc_reads"] == 1
    assert merged["2026-07-19"]["other_reads"] == 2
    assert merged["2026-07-19"]["mcp_calls"] == 4


def test_normalize_day_bucket_defaults_missing_read_fields():
    norm = usage._normalize_day_bucket({"mcp_calls": 5})
    assert norm is not None
    assert norm["session_reads"] == 0
    assert norm["doc_reads"] == 0
    assert norm["other_reads"] == 0


def test_refresh_daily_idempotent_across_builds(tmp_path: Path):
    _write_jsonl(tmp_path / "usage" / "mcp-1-x.jsonl", [
        {"ts": "2026-07-19T10:00:00Z", "tool": "wiki_query",
         "caller_project": "a", "caller_source": "client-root", "hits": 1},
        {"ts": "2026-07-19T11:00:00Z", "tool": "wiki_search",
         "caller_project": "a", "caller_source": "client-root", "hits": 2},
    ])
    d1 = usage.refresh_daily(tmp_path)
    d2 = usage.refresh_daily(tmp_path)
    assert d1["2026-07-19"]["mcp_calls"] == 2
    assert d2["2026-07-19"]["mcp_calls"] == 2  # not 4
    raw = json.loads((tmp_path / "usage" / "daily.json").read_text())
    assert raw["days"]["2026-07-19"]["mcp_calls"] == 2
    assert raw["days"]["2026-07-19"]["retrievals"] == 2


def test_compact_folds_into_daily_before_delete(tmp_path: Path):
    # Past-month file → compact folds it; daily must keep the day forever.
    _write_jsonl(tmp_path / "usage" / "mcp-old.jsonl", [
        {"ts": "2026-05-10T10:00:00Z", "tool": "wiki_query",
         "caller_project": "a", "caller_source": "client-root", "hits": 1},
        {"ts": "2026-05-10T11:00:00Z", "tool": "wiki_add",
         "caller_project": "a", "caller_source": "client-root", "hits": 0},
    ])
    # Current-month live file stays.
    _write_jsonl(tmp_path / "usage" / "mcp-live.jsonl", [
        {"ts": "2026-07-19T10:00:00Z", "tool": "wiki_search",
         "caller_project": "b", "caller_source": "client-root", "hits": 3},
    ])
    usage.compact(tmp_path, now_month="2026-07")
    assert not (tmp_path / "usage" / "mcp-old.jsonl").exists()
    assert (tmp_path / "usage" / "mcp-live.jsonl").exists()
    daily = usage.load_daily(tmp_path)
    assert "mcp-old.jsonl" in daily["folded_daily_files"]
    assert daily["folded_days"]["2026-05-10"]["mcp_calls"] == 2
    assert daily["folded_days"]["2026-05-10"]["writes"] == 1
    # refresh merges folded + live for display
    days = usage.refresh_daily(tmp_path)
    assert days["2026-05-10"]["mcp_calls"] == 2
    assert days["2026-07-19"]["mcp_calls"] == 1


def test_value_summary_excludes_unknown_from_project_count():
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
            "proj-a": {"calls": 3},
            "proj-b": {"calls": 2},
        },
    }
    summary = usage.value_summary(totals, wiki_page_count=10)
    assert summary["retrievals"] == 7
    assert summary["writes"] == 2
    assert summary["attributed_project_count"] == 2
    assert summary["unattributed_calls"] == 5
    assert abs(summary["answer_rate"] - (6 / 7)) < 1e-9  # entity tools only
    assert abs(summary["payoff_per_page"] - 0.7) < 1e-9


def test_page_retrievals_normalizes_paths():
    records = [
        {"tool": "wiki_read_page", "query": "wiki/sources/a.md"},
        {"tool": "wiki_read_page", "query": "./wiki/sources/a.md"},
        {"tool": "wiki_read_page", "query": "sources/b.md"},
        {"tool": "wiki_search", "query": "wiki/sources/a.md"},
    ]
    counts = usage.page_retrievals(records)
    assert counts["wiki/sources/a.md"] == 2
    assert counts["wiki/sources/b.md"] == 1


def test_classify_source_kind_session_vs_doc():
    assert usage.classify_source_kind(
        "---\nsource_file: raw/sessions/p/x.md\n---\n") == "session"
    assert usage.classify_source_kind(
        "---\nsource_file: raw/docs/p/x.md\n---\n") == "doc"
    assert usage.classify_source_kind(
        "---\ntags: [wiki-add, raw-doc]\n---\n") == "doc"
    assert usage.classify_source_kind("---\ntitle: X\n---\n") == "other"


def test_corpus_and_read_mix(tmp_path: Path):
    wiki = tmp_path / "wiki"
    sources = wiki / "sources"
    sources.mkdir(parents=True)
    (sources / "s.md").write_text(
        "---\nsource_file: raw/sessions/p/s.md\n---\n", encoding="utf-8")
    (sources / "d.md").write_text(
        "---\nsource_file: raw/docs/p/d.md\n---\n", encoding="utf-8")
    mix = usage.corpus_source_mix(sources)
    assert mix == {"session": 1, "doc": 1, "other": 0, "total": 2}
    reads = usage.read_mix_from_retrievals(
        {"wiki/sources/s.md": 3, "wiki/sources/d.md": 1},
        wiki_root=wiki,
    )
    assert reads["session"] == 3
    assert reads["doc"] == 1
    assert reads["total"] == 4
