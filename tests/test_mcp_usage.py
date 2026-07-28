"""Tests for local-only MCP usage telemetry (#26).

Collection is per-process append-only JSONL under ``<root>/usage/``,
merged at read time; aggregation folds the records into totals and a
kept-forever rollup so raw logs can be rotated.
"""
from __future__ import annotations

import json
from pathlib import Path

from llmwiki import usage


def _read_lines(p: Path) -> list[dict]:
    return [json.loads(ln) for ln in p.read_text().splitlines() if ln.strip()]


# ─── UsageRecorder ────────────────────────────────────────────────────────

def test_recorder_writes_per_process_file(tmp_path: Path):
    rec = usage.UsageRecorder(
        tmp_path, pid=51119, started="2026-07-16T09:00:00Z",
    )
    rec.record(tool="wiki_search", query="sync", hits=3,
               resp_bytes=18432, duration_ms=210, ts="2026-07-16T12:00:00Z",
               caller_project="sde-automation",
               caller_source=usage.CALLER_CLIENT_ROOT)

    files = list((tmp_path / "usage").glob("mcp-*.jsonl"))
    assert len(files) == 1
    # pid + start stamp are encoded in the filename so two processes never
    # collide on the same file.
    assert "51119" in files[0].name
    rows = _read_lines(files[0])
    assert rows == [{
        "ts": "2026-07-16T12:00:00Z",
        "tool": "wiki_search",
        "query": "sync",
        "hits": 3,
        "resp_bytes": 18432,
        "duration_ms": 210,
        "caller_project": "sde-automation",
        "caller_source": "client-root",
        "server_pid": 51119,
        "server_started": "2026-07-16T09:00:00Z",
    }]


def test_recorder_appends_multiple_records(tmp_path: Path):
    rec = usage.UsageRecorder(tmp_path, pid=1, started="2026-07-16T09:00:00Z")
    rec.record(tool="wiki_query", hits=0, resp_bytes=10, duration_ms=5)
    rec.record(tool="wiki_query", hits=2, resp_bytes=20, duration_ms=7)
    files = list((tmp_path / "usage").glob("mcp-*.jsonl"))
    assert len(files) == 1
    assert len(_read_lines(files[0])) == 2


def test_record_never_raises_on_bad_dir(tmp_path: Path):
    # A file where the usage dir should be → mkdir fails; telemetry must
    # swallow it rather than break the tool call.
    (tmp_path / "usage").write_text("i am a file, not a dir")
    rec = usage.UsageRecorder(tmp_path, pid=1, started="2026-07-16T09:00:00Z")
    rec.record(tool="wiki_query", hits=1, resp_bytes=1, duration_ms=1)  # no raise


# ─── iter_records / merge across processes ────────────────────────────────

def test_iter_records_merges_all_process_files(tmp_path: Path):
    usage.UsageRecorder(tmp_path, pid=1, started="2026-07-16T09:00:00Z").record(
        tool="wiki_search", hits=1, resp_bytes=5, duration_ms=1)
    usage.UsageRecorder(tmp_path, pid=2, started="2026-07-16T09:02:00Z").record(
        tool="wiki_query", hits=2, resp_bytes=6, duration_ms=1)
    tools = sorted(r["tool"] for r in usage.iter_records(tmp_path))
    assert tools == ["wiki_query", "wiki_search"]


def test_iter_records_skips_malformed_lines(tmp_path: Path):
    d = tmp_path / "usage"
    d.mkdir()
    (d / "mcp-1-x.jsonl").write_text(
        '{"tool": "wiki_search", "hits": 1}\nnot json\n{"tool": "wiki_query", "hits": 0}\n'
    )
    tools = sorted(r["tool"] for r in usage.iter_records(tmp_path))
    assert tools == ["wiki_query", "wiki_search"]


def test_iter_records_empty_when_no_dir(tmp_path: Path):
    assert list(usage.iter_records(tmp_path)) == []


# ─── aggregate ────────────────────────────────────────────────────────────

def test_aggregate_totals_per_tool_and_project():
    records = [
        {"tool": "wiki_search", "hits": 3, "resp_bytes": 100, "caller_project": "a", "caller_source": "client-root"},
        {"tool": "wiki_search", "hits": 0, "resp_bytes": 50, "caller_project": "a", "caller_source": "client-root"},
        {"tool": "wiki_query", "hits": 2, "resp_bytes": 200, "caller_project": "b", "caller_source": "client-root"},
    ]
    agg = usage.aggregate(records)
    assert agg["total_calls"] == 3
    assert agg["total_resp_bytes"] == 350
    assert agg["per_tool"]["wiki_search"]["calls"] == 2
    assert agg["per_tool"]["wiki_search"]["zero_hits"] == 1
    assert agg["per_tool"]["wiki_search"]["zero_hit_rate"] == 0.5
    assert agg["per_tool"]["wiki_search"]["resp_bytes"] == 150
    assert agg["per_project"]["a"]["calls"] == 2
    assert agg["per_project"]["b"]["calls"] == 1


def test_aggregate_empty():
    agg = usage.aggregate([])
    assert agg["total_calls"] == 0
    assert agg["total_resp_bytes"] == 0
    assert agg["per_tool"] == {}
    assert agg["per_project"] == {}


def test_aggregate_unknown_fields_default():
    # Missing tool / project / hits fall back sanely.
    agg = usage.aggregate([{"resp_bytes": 5}])
    assert agg["per_tool"]["unknown"]["calls"] == 1
    assert agg["per_project"]["unknown"]["calls"] == 1
    # hits absent → not counted as a zero-hit (unknown, not a miss)
    assert agg["per_tool"]["unknown"]["zero_hits"] == 0


# ─── merge_aggregates ─────────────────────────────────────────────────────

def test_merge_aggregates_sums_counters():
    a = usage.aggregate([
        {"tool": "wiki_search", "hits": 1, "resp_bytes": 10, "caller_project": "p", "caller_source": "client-root"},
    ])
    b = usage.aggregate([
        {"tool": "wiki_search", "hits": 0, "resp_bytes": 5, "caller_project": "p", "caller_source": "client-root"},
        {"tool": "wiki_query", "hits": 3, "resp_bytes": 7, "caller_project": "q", "caller_source": "client-root"},
    ])
    m = usage.merge_aggregates(a, b)
    assert m["total_calls"] == 3
    assert m["total_resp_bytes"] == 22
    assert m["per_tool"]["wiki_search"]["calls"] == 2
    assert m["per_tool"]["wiki_search"]["zero_hits"] == 1
    assert m["per_tool"]["wiki_search"]["zero_hit_rate"] == 0.5
    assert m["per_project"]["q"]["calls"] == 1


# ─── compact / rollup ─────────────────────────────────────────────────────

def _record_at(root: Path, *, pid: int, started: str, ts: str, tool: str,
               hits: int = 1, resp_bytes: int = 10) -> None:
    usage.UsageRecorder(root, pid=pid, started=started).record(
        tool=tool, hits=hits, resp_bytes=resp_bytes, duration_ms=1, ts=ts)


def test_compact_folds_old_month_and_keeps_current(tmp_path: Path):
    # A June-only file and a July file, both keyed by their record ts.
    _record_at(tmp_path, pid=1, started="2026-06-30T09:00:00Z",
               ts="2026-06-30T09:00:00Z", tool="wiki_search")
    _record_at(tmp_path, pid=2, started="2026-07-16T09:00:00Z",
               ts="2026-07-16T09:00:00Z", tool="wiki_query", resp_bytes=20)

    usage.compact(tmp_path, now_month="2026-07")

    remaining = {p.name for p in (tmp_path / "usage").glob("mcp-*.jsonl")}
    # June file folded + deleted; July file (still being written) kept.
    assert len(remaining) == 1
    assert any("2026-07" in n for n in remaining)

    rollup = usage.load_rollup(tmp_path)
    assert rollup["total_calls"] == 1
    assert rollup["per_tool"]["wiki_search"]["calls"] == 1


def test_compact_keys_off_record_ts_not_filename(tmp_path: Path):
    # A file NAMED June but still receiving July calls (a long-lived server
    # that started last month) must NOT be folded or deleted — its latest
    # record is in the current month.
    _record_at(tmp_path, pid=1, started="2026-06-30T09:00:00Z",
               ts="2026-06-30T23:59:00Z", tool="wiki_search")
    _record_at(tmp_path, pid=1, started="2026-06-30T09:00:00Z",
               ts="2026-07-01T00:01:00Z", tool="wiki_search")

    usage.compact(tmp_path, now_month="2026-07")

    remaining = list((tmp_path / "usage").glob("mcp-*.jsonl"))
    assert len(remaining) == 1                      # live file untouched
    assert usage.load_rollup(tmp_path)["total_calls"] == 0  # nothing folded


def test_compact_is_idempotent(tmp_path: Path):
    _record_at(tmp_path, pid=1, started="2026-06-30T09:00:00Z",
               ts="2026-06-30T09:00:00Z", tool="wiki_search")
    usage.compact(tmp_path, now_month="2026-07")
    usage.compact(tmp_path, now_month="2026-07")  # second run must not double-count
    assert usage.load_rollup(tmp_path)["total_calls"] == 1


def test_compact_saves_rollup_before_deleting(tmp_path: Path, monkeypatch):
    # If deletion fails after folding, the totals must already be durable in
    # the rollup AND the still-present file must not be double-counted.
    _record_at(tmp_path, pid=1, started="2026-06-30T09:00:00Z",
               ts="2026-06-30T09:00:00Z", tool="wiki_search")

    def _boom(self):
        raise OSError("disk gone")
    monkeypatch.setattr(Path, "unlink", _boom)

    usage.compact(tmp_path, now_month="2026-07")

    # Rollup persisted despite the unlink failure...
    assert usage.load_rollup(tmp_path)["total_calls"] == 1
    # ...and the un-deleted raw file is excluded from live aggregation, so
    # the combined view counts each record exactly once.
    assert usage.combined_totals(tmp_path)["total_calls"] == 1


def test_combined_totals_joins_rollup_and_live(tmp_path: Path):
    # One folded (June) + one live (July) → combined view sees both.
    _record_at(tmp_path, pid=1, started="2026-06-30T09:00:00Z",
               ts="2026-06-30T09:00:00Z", tool="wiki_search")
    usage.compact(tmp_path, now_month="2026-07")
    _record_at(tmp_path, pid=2, started="2026-07-16T09:00:00Z",
               ts="2026-07-16T09:00:00Z", tool="wiki_query", resp_bytes=20)

    combined = usage.combined_totals(tmp_path)
    assert combined["total_calls"] == 2
    assert combined["total_resp_bytes"] == 30
    assert combined["per_tool"]["wiki_search"]["calls"] == 1
    assert combined["per_tool"]["wiki_query"]["calls"] == 1


# ─── Server integration: handle_tools_call telemetry ──────────────────────

def _reset_server_telemetry():
    from llmwiki.mcp import server
    server._RECORDERS.clear()
    return server


def test_handle_tools_call_records_telemetry(tmp_path: Path, monkeypatch):
    server = _reset_server_telemetry()
    monkeypatch.setattr(server, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(server, "TELEMETRY_ENABLED", True)
    (tmp_path / "wiki").mkdir()

    result = server.handle_tools_call(
        {"name": "wiki_search", "arguments": {"term": "anything"}})
    assert result["isError"] is False

    records = list(usage.iter_records(tmp_path))
    assert len(records) == 1
    r = records[0]
    assert r["tool"] == "wiki_search"
    assert r["query"] == "anything"
    assert r["hits"] == 0            # empty wiki → matches == []
    assert r["resp_bytes"] > 0       # the JSON payload we returned
    assert isinstance(r["duration_ms"], int) and r["duration_ms"] >= 0
    assert "caller_project" in r and "server_pid" in r


def test_handle_tools_call_records_zero_hits_on_error(tmp_path: Path, monkeypatch):
    server = _reset_server_telemetry()
    monkeypatch.setattr(server, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(server, "TELEMETRY_ENABLED", True)

    # Missing required 'term' → the tool returns an isError result.
    result = server.handle_tools_call(
        {"name": "wiki_search", "arguments": {}})
    assert result["isError"] is True

    records = list(usage.iter_records(tmp_path))
    assert len(records) == 1
    assert records[0]["hits"] == 0
    assert records[0]["tool"] == "wiki_search"


def test_unknown_tool_is_not_recorded(tmp_path: Path, monkeypatch):
    server = _reset_server_telemetry()
    monkeypatch.setattr(server, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(server, "TELEMETRY_ENABLED", True)

    server.handle_tools_call({"name": "does_not_exist", "arguments": {}})
    assert list(usage.iter_records(tmp_path)) == []


def test_telemetry_disabled_writes_nothing(tmp_path: Path, monkeypatch):
    server = _reset_server_telemetry()
    monkeypatch.setattr(server, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(server, "TELEMETRY_ENABLED", False)
    (tmp_path / "wiki").mkdir()

    server.handle_tools_call(
        {"name": "wiki_search", "arguments": {"term": "x"}})
    assert not (tmp_path / "usage").exists()


def test_query_zero_hits_recorded_from_no_match_sentinel(tmp_path: Path, monkeypatch):
    # wiki_query returns prose, not JSON. Its documented "no results"
    # output must still register as a zero-hit call (the knowledge-gap
    # signal for /wiki-reflect), not as an unknown count.
    server = _reset_server_telemetry()
    monkeypatch.setattr(server, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(server, "TELEMETRY_ENABLED", True)
    (tmp_path / "wiki").mkdir()

    server.handle_tools_call(
        {"name": "wiki_query", "arguments": {"question": "nonexistent topic"}})
    rec = list(usage.iter_records(tmp_path))[0]
    assert rec["tool"] == "wiki_query"
    assert rec["hits"] == 0


def test_query_positive_hits_recorded(tmp_path: Path, monkeypatch):
    server = _reset_server_telemetry()
    monkeypatch.setattr(server, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(server, "TELEMETRY_ENABLED", True)
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "index.md").write_text("# Index\n")
    (wiki / "topic.md").write_text('---\ntitle: "Synthesis"\n---\nsynthesis pipeline notes\n')

    server.handle_tools_call(
        {"name": "wiki_query", "arguments": {"question": "synthesis"}})
    rec = list(usage.iter_records(tmp_path))[0]
    assert rec["hits"] and rec["hits"] >= 1


def test_query_hits_not_inflated_by_snippet_headings(tmp_path: Path, monkeypatch):
    # A matched page whose body contains a line that looks like a result
    # heading must not be double-counted — only real page headings count.
    server = _reset_server_telemetry()
    monkeypatch.setattr(server, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(server, "TELEMETRY_ENABLED", True)
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "index.md").write_text("# Index\n")
    (wiki / "topic.md").write_text(
        '---\ntitle: "Synthesis"\n---\n'
        "synthesis notes\n"
        "## `wiki/fake.md` (score: 99.9)\n"  # a heading-shaped line in the body
        "more synthesis text\n"
    )
    server.handle_tools_call(
        {"name": "wiki_query", "arguments": {"question": "synthesis"}})
    rec = list(usage.iter_records(tmp_path))[0]
    assert rec["hits"] == 1  # one real matched page, not two


def test_recorder_construction_failure_does_not_break_tool_call(tmp_path: Path, monkeypatch):
    # Telemetry must never break a tool call — even if the recorder itself
    # cannot be built.
    server = _reset_server_telemetry()
    monkeypatch.setattr(server, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(server, "TELEMETRY_ENABLED", True)
    (tmp_path / "wiki").mkdir()

    def _boom():
        raise RuntimeError("recorder exploded")
    monkeypatch.setattr(server, "_get_recorder", _boom)

    result = server.handle_tools_call(
        {"name": "wiki_search", "arguments": {"term": "x"}})
    assert result["isError"] is False  # tool result survived


def test_hits_channel_stripped_from_client_result(tmp_path: Path, monkeypatch):
    # The private _hits telemetry channel must never reach the MCP client.
    server = _reset_server_telemetry()
    monkeypatch.setattr(server, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(server, "TELEMETRY_ENABLED", True)
    (tmp_path / "wiki").mkdir()
    (tmp_path / "wiki" / "index.md").write_text("# Index\n")

    result = server.handle_tools_call(
        {"name": "wiki_query", "arguments": {"question": "anything"}})
    assert "_hits" not in result
    assert set(result.keys()) == {"content", "isError"}


# ─── Task 1: items_returned ───────────────────────────────────────────────

def test_items_returned_counts_only_entity_tools():
    from llmwiki.usage import aggregate
    records = [
        {"tool": "wiki_search", "hits": 5, "caller_project": "p", "caller_source": "client-root", "server_pid": 1, "server_started": "s1"},
        {"tool": "wiki_query", "hits": 3, "caller_project": "p", "caller_source": "client-root", "server_pid": 1, "server_started": "s1"},
        {"tool": "wiki_lint", "hits": 9, "caller_project": "p", "caller_source": "client-root", "server_pid": 1, "server_started": "s1"},   # excluded
        {"tool": "wiki_search", "hits": None, "caller_project": "p", "caller_source": "client-root", "server_pid": 1, "server_started": "s1"},  # unknown, not counted
        {"tool": "wiki_search", "hits": 0, "caller_project": "p", "caller_source": "client-root", "server_pid": 1, "server_started": "s1"},  # zero, not counted
    ]
    agg = aggregate(records)
    assert agg["total_items_returned"] == 8            # 5 + 3
    assert agg["per_tool"]["wiki_search"]["items_returned"] == 5
    assert agg["per_tool"]["wiki_query"]["items_returned"] == 3
    assert agg["per_tool"]["wiki_lint"]["items_returned"] == 0
    assert agg["per_project"]["p"]["items_returned"] == 8

def test_entity_tool_classification():
    from llmwiki.usage import ENTITY_TOOLS, is_entity_tool
    assert is_entity_tool("wiki_search") is True
    assert is_entity_tool("wiki_dashboard") is False
    assert "wiki_confidence" in ENTITY_TOOLS and "wiki_sync" not in ENTITY_TOOLS


# ─── Task 2: server_processes ─────────────────────────────────────────────

def test_server_processes_counts_distinct_pairs():
    from llmwiki.usage import aggregate
    records = [
        {"tool": "wiki_search", "caller_project": "a", "caller_source": "client-root", "server_pid": 1, "server_started": "s1"},
        {"tool": "wiki_search", "caller_project": "a", "caller_source": "client-root", "server_pid": 1, "server_started": "s1"},  # same proc
        {"tool": "wiki_query",  "caller_project": "a", "caller_source": "client-root", "server_pid": 2, "server_started": "s2"},  # 2nd proc
        {"tool": "wiki_query",  "caller_project": "b", "caller_source": "client-root", "server_pid": 3, "server_started": "s3"},
    ]
    agg = aggregate(records)
    assert agg["per_project"]["a"]["server_processes"] == 2
    assert agg["per_project"]["b"]["server_processes"] == 1
    assert agg["total_server_processes"] == 3

def test_merge_sums_server_processes_and_legacy_rollup_defaults_zero():
    from llmwiki.usage import aggregate, merge_aggregates
    live = aggregate([
        {"tool": "wiki_search", "caller_project": "a", "caller_source": "client-root", "server_pid": 9, "server_started": "s9"},
    ])
    legacy = {  # old rollup shape: no items_returned / server_processes
        "total_calls": 2, "total_resp_bytes": 0,
        "per_tool": {"wiki_search": {"calls": 2, "zero_hits": 0, "resp_bytes": 0}},
        "per_project": {"a": {"calls": 2, "resp_bytes": 0}},
    }
    merged = merge_aggregates(legacy, live)
    assert merged["per_project"]["a"]["server_processes"] == 1   # 0 (legacy) + 1 (live)
    assert merged["per_project"]["a"]["items_returned"] == 0
    assert merged["total_server_processes"] == 1
    assert merged["total_calls"] == 3


# ─── Task 9: per_project_tool breakdown ────────────────────────────────────

def test_per_project_tool_breakdown():
    from llmwiki.usage import aggregate
    records = [
        {"tool": "wiki_search", "hits": 5, "caller_project": "a", "caller_source": "client-root", "server_pid": 1, "server_started": "s1"},
        {"tool": "wiki_search", "hits": 2, "caller_project": "a", "caller_source": "client-root", "server_pid": 1, "server_started": "s1"},
        {"tool": "wiki_lint",   "hits": 9, "caller_project": "a", "caller_source": "client-root", "server_pid": 1, "server_started": "s1"},  # entity=False → items 0
        {"tool": "wiki_query",  "hits": 4, "caller_project": "b", "caller_source": "client-root", "server_pid": 2, "server_started": "s2"},
    ]
    agg = aggregate(records)
    assert agg["per_project_tool"]["a"]["wiki_search"] == {"calls": 2, "items_returned": 7}
    assert agg["per_project_tool"]["a"]["wiki_lint"] == {"calls": 1, "items_returned": 0}
    assert agg["per_project_tool"]["b"]["wiki_query"] == {"calls": 1, "items_returned": 4}

def test_merge_sums_per_project_tool_and_legacy_defaults_empty():
    from llmwiki.usage import aggregate, merge_aggregates
    live = aggregate([
        {"tool": "wiki_search", "hits": 3, "caller_project": "a", "caller_source": "client-root", "server_pid": 9, "server_started": "s9"},
    ])
    legacy = {  # old rollup shape: no per_project_tool at all
        "total_calls": 1, "total_resp_bytes": 0,
        "per_tool": {"wiki_search": {"calls": 1, "zero_hits": 0, "resp_bytes": 0}},
        "per_project": {"a": {"calls": 1, "resp_bytes": 0}},
    }
    merged = merge_aggregates(legacy, live)
    assert merged["per_project_tool"]["a"]["wiki_search"] == {"calls": 1, "items_returned": 3}
