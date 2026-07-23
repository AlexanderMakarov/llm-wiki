"""#51: telemetry must attribute a call to the *caller's* project.

Attribution used to be the server process's own ``os.getcwd()``, captured
once at construction — so every record from a server launched out of
``~/code/llm-wiki`` claimed ``llm-wiki`` no matter which project's session
actually made the call. These tests pin the replacement: attribution is
resolved per call, from a signal the caller supplied (MCP roots, or a
caller-scoped path argument), and is honestly ``unknown`` when there is
no such signal.
"""
from __future__ import annotations

import json
from pathlib import Path

from llmwiki import usage
from llmwiki.mcp import server as mcp_server


def _read_lines(p: Path) -> list[dict]:
    return [json.loads(ln) for ln in p.read_text().splitlines() if ln.strip()]


def _only_record(root: Path) -> dict:
    files = list((root / "usage").glob("mcp-*.jsonl"))
    assert len(files) == 1, files
    rows = _read_lines(files[0])
    assert len(rows) == 1, rows
    return rows[0]


# ─── Resolver ─────────────────────────────────────────────────────────────

def test_client_root_uri_names_the_caller_project(tmp_path: Path):
    project, source = usage.resolve_caller(
        {}, client_roots=["file:///home/dev/code/armenian-words"],
        content_root=tmp_path)
    assert (project, source) == ("armenian-words", usage.CALLER_CLIENT_ROOT)


def test_percent_encoded_client_root_is_decoded(tmp_path: Path):
    project, _ = usage.resolve_caller(
        {}, client_roots=["file:///home/dev/code/my%20project"],
        content_root=tmp_path)
    assert project == "my-project"


def test_client_root_outranks_a_path_argument(tmp_path: Path):
    """A caller in project-b adding a file that lives in project-a's tree is
    still project-b calling — roots answer "who called", paths only hint."""
    project, source = usage.resolve_caller(
        {"path": "/tmp/claude-1000/-home-dev-code-project-a/s1/scratchpad/n.md"},
        client_roots=["file:///home/dev/code/project-b"],
        content_root=tmp_path)
    assert (project, source) == ("project-b", usage.CALLER_CLIENT_ROOT)


def test_encoded_project_dir_in_a_path_attributes_the_caller(tmp_path: Path):
    """Agent scratchpads and session stores carry the caller's cwd encoded
    into a path segment (``-home-dev-code-project-a``) — the one caller-scoped
    signal available when a client doesn't speak the roots protocol."""
    project, source = usage.resolve_caller(
        {"path": "/tmp/claude-1000/-home-dev-code-project-a/s1/scratchpad/n.md"},
        client_roots=[], content_root=tmp_path)
    assert (project, source) == ("project-a", usage.CALLER_PATH)


def test_session_store_path_attributes_the_caller(tmp_path: Path):
    project, source = usage.resolve_caller(
        {"path": "/home/dev/.claude/projects/-home-dev-code-project-a/s1.jsonl"},
        client_roots=[], content_root=tmp_path)
    assert (project, source) == ("project-a", usage.CALLER_PATH)


def test_wiki_page_path_is_the_subject_not_the_caller(tmp_path: Path):
    """``wiki_read_page("wiki/sources/project-a/…")`` says what was read, not
    who read it. Treating it as caller identity would make every retrieval
    look same-project and erase the cross-project signal entirely."""
    project, source = usage.resolve_caller(
        {"path": "wiki/sources/project-a/2026-07-01-session.md"},
        client_roots=[], content_root=tmp_path)
    assert (project, source) == (usage.UNATTRIBUTED, usage.CALLER_UNATTRIBUTED)


def test_path_inside_the_content_root_is_the_subject_not_the_caller(tmp_path: Path):
    inside = tmp_path / "wiki" / "entities" / "Thing.md"
    project, _ = usage.resolve_caller(
        {"path": str(inside)}, client_roots=[], content_root=tmp_path)
    assert project == usage.UNATTRIBUTED


def test_no_caller_signal_never_falls_back_to_server_cwd(tmp_path: Path, monkeypatch):
    """The whole bug: the server's own cwd is not the caller's project."""
    monkeypatch.chdir(tmp_path)
    project, source = usage.resolve_caller(
        {"question": "what did I decide about sync"},
        client_roots=[], content_root=tmp_path)
    assert (project, source) == (usage.UNATTRIBUTED, usage.CALLER_UNATTRIBUTED)
    assert project != tmp_path.name


def test_first_client_root_wins_when_several_are_reported(tmp_path: Path):
    project, _ = usage.resolve_caller(
        {}, client_roots=["file:///home/dev/code/first",
                          "file:///home/dev/code/second"],
        content_root=tmp_path)
    assert project == "first"


# ─── Recorder ─────────────────────────────────────────────────────────────

def test_one_recorder_stamps_a_different_caller_per_call(tmp_path: Path):
    """A single long-lived server serves calls from many sessions; one value
    captured at construction cannot distinguish them."""
    rec = usage.UsageRecorder(tmp_path, pid=7, started="2026-07-23T09:00:00Z")
    rec.record(tool="wiki_query", caller_project="project-a",
               caller_source=usage.CALLER_CLIENT_ROOT)
    rec.record(tool="wiki_query", caller_project="project-b",
               caller_source=usage.CALLER_CLIENT_ROOT)
    rows = _read_lines(next((tmp_path / "usage").glob("mcp-*.jsonl")))
    assert [r["caller_project"] for r in rows] == ["project-a", "project-b"]


def test_record_without_attribution_is_unknown_and_marked_unattributed(tmp_path: Path):
    usage.UsageRecorder(tmp_path, pid=7, started="2026-07-23T09:00:00Z").record(
        tool="wiki_lint")
    row = _only_record(tmp_path)
    assert row["caller_project"] == usage.UNATTRIBUTED
    assert row["caller_source"] == usage.CALLER_UNATTRIBUTED


# ─── Aggregation ──────────────────────────────────────────────────────────

def test_records_predating_the_fix_aggregate_as_unattributed():
    """Pre-#51 records carry no ``caller_source`` and a project name that is
    really the server's cwd — counting them under that name republishes the
    bug's output as fact."""
    totals = usage.aggregate([
        {"tool": "wiki_query", "caller_project": "llm-wiki", "hits": 2},
        {"tool": "wiki_query", "caller_project": "project-a", "hits": 1,
         "caller_source": usage.CALLER_CLIENT_ROOT},
    ])
    assert totals["per_project"][usage.UNATTRIBUTED]["calls"] == 1
    assert totals["per_project"]["project-a"]["calls"] == 1
    assert "llm-wiki" not in totals["per_project"]
    assert "llm-wiki" not in totals["per_project_tool"]


def test_unattributed_records_do_not_borrow_a_real_project_name():
    totals = usage.aggregate([
        {"tool": "wiki_search", "caller_project": "llm-wiki", "hits": 0,
         "caller_source": usage.CALLER_UNATTRIBUTED},
    ])
    assert list(totals["per_project"]) == [usage.UNATTRIBUTED]


def test_rollup_written_before_the_fix_collapses_to_unattributed(tmp_path: Path):
    """Compaction deletes the raw records, so a pre-#51 rollup is the only
    surviving copy of totals that were mis-attributed at write time."""
    usage.save_rollup(tmp_path, {
        "total_calls": 5, "total_resp_bytes": 0, "total_items_returned": 0,
        "total_server_processes": 1, "per_tool": {},
        "per_project": {"llm-wiki": {"calls": 5, "resp_bytes": 0,
                                     "items_returned": 3, "server_processes": 1}},
        "per_project_tool": {"llm-wiki": {"wiki_query": {"calls": 5,
                                                         "items_returned": 3}}},
        "folded_files": ["mcp-1-2026-06-01T00-00-00Z.jsonl"],
    })
    rollup = usage.load_rollup(tmp_path)
    assert "llm-wiki" not in rollup["per_project"]
    assert rollup["per_project"][usage.UNATTRIBUTED]["calls"] == 5
    assert rollup["per_project"][usage.UNATTRIBUTED]["items_returned"] == 3
    assert rollup["per_project_tool"][usage.UNATTRIBUTED]["wiki_query"]["calls"] == 5
    # Totals and the folded-file ledger are untouched — only the labels were wrong.
    assert rollup["total_calls"] == 5
    assert rollup["folded_files"] == ["mcp-1-2026-06-01T00-00-00Z.jsonl"]


def test_rollup_written_after_the_fix_keeps_its_project_labels(tmp_path: Path):
    usage.compact(tmp_path)  # writes nothing; marker comes from a real fold
    usage.save_rollup(tmp_path, {
        **usage.aggregate([{"tool": "wiki_query", "caller_project": "project-a",
                            "caller_source": usage.CALLER_CLIENT_ROOT}]),
        "attribution_version": usage.ATTRIBUTION_VERSION,
        "folded_files": [],
    })
    assert "project-a" in usage.load_rollup(tmp_path)["per_project"]


# ─── Server wiring ────────────────────────────────────────────────────────

def _capture_sent(monkeypatch) -> list[dict]:
    sent: list[dict] = []
    monkeypatch.setattr(mcp_server, "send", sent.append)
    return sent


def test_roots_are_requested_once_the_client_says_it_is_initialized(monkeypatch):
    mcp_server.reset_client_state()
    sent = _capture_sent(monkeypatch)
    mcp_server.handle_initialize({"capabilities": {"roots": {"listChanged": True}}})
    assert sent == []  # nothing before the client is ready
    mcp_server.handle_client_notification("notifications/initialized")
    assert [m["method"] for m in sent] == ["roots/list"]
    assert sent[0].get("id") is not None


def test_client_without_roots_capability_is_never_sent_a_request(monkeypatch):
    """An extra unsolicited frame breaks clients that read one line per
    request — only ask a client that advertised the capability."""
    mcp_server.reset_client_state()
    sent = _capture_sent(monkeypatch)
    mcp_server.handle_initialize({"capabilities": {}})
    mcp_server.handle_client_notification("notifications/initialized")
    assert sent == []


def test_roots_response_becomes_the_caller_project(monkeypatch):
    mcp_server.reset_client_state()
    sent = _capture_sent(monkeypatch)
    mcp_server.handle_initialize({"capabilities": {"roots": {}}})
    mcp_server.handle_client_notification("notifications/initialized")
    consumed = mcp_server.handle_client_response({
        "jsonrpc": "2.0", "id": sent[0]["id"],
        "result": {"roots": [{"uri": "file:///home/dev/code/project-a",
                              "name": "project-a"}]},
    })
    assert consumed is True
    assert mcp_server.client_roots() == ["file:///home/dev/code/project-a"]


def test_roots_error_response_leaves_calls_unattributed(monkeypatch):
    mcp_server.reset_client_state()
    sent = _capture_sent(monkeypatch)
    mcp_server.handle_initialize({"capabilities": {"roots": {}}})
    mcp_server.handle_client_notification("notifications/initialized")
    mcp_server.handle_client_response({
        "jsonrpc": "2.0", "id": sent[0]["id"],
        "error": {"code": -32601, "message": "Method not found"},
    })
    assert mcp_server.client_roots() == []


def test_unrelated_response_id_is_not_consumed():
    mcp_server.reset_client_state()
    assert mcp_server.handle_client_response(
        {"jsonrpc": "2.0", "id": "someone-elses", "result": {}}) is False


def test_roots_are_re_requested_when_the_client_says_they_changed(monkeypatch):
    mcp_server.reset_client_state()
    sent = _capture_sent(monkeypatch)
    mcp_server.handle_initialize({"capabilities": {"roots": {"listChanged": True}}})
    mcp_server.handle_client_notification("notifications/initialized")
    mcp_server.handle_client_notification("notifications/roots/list_changed")
    assert [m["method"] for m in sent] == ["roots/list", "roots/list"]
    assert sent[0]["id"] != sent[1]["id"], "JSON-RPC ids must be unique per request"


def test_re_requesting_roots_supersedes_the_previous_request(monkeypatch):
    """Only the newest request stays outstanding: a reply to a superseded one
    carries roots the client has already told us are stale, and an unbounded
    pending set would grow for the life of a chatty session."""
    mcp_server.reset_client_state()
    sent = _capture_sent(monkeypatch)
    mcp_server.handle_initialize({"capabilities": {"roots": {"listChanged": True}}})
    mcp_server.handle_client_notification("notifications/initialized")
    mcp_server.handle_client_notification("notifications/roots/list_changed")
    assert mcp_server.pending_roots_ids() == [sent[1]["id"]]


def test_tool_call_is_recorded_against_the_client_root(tmp_path: Path, monkeypatch):
    mcp_server.reset_client_state()
    monkeypatch.setattr(mcp_server, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(mcp_server, "_RECORDERS", {})
    _capture_sent(monkeypatch)
    mcp_server.handle_initialize({"capabilities": {"roots": {}}})
    mcp_server.handle_client_notification("notifications/initialized")
    mcp_server.handle_client_response({
        "jsonrpc": "2.0", "id": mcp_server.pending_roots_ids()[0],
        "result": {"roots": [{"uri": "file:///home/dev/code/project-a"}]},
    })
    mcp_server.handle_tools_call({"name": "wiki_search", "arguments": {"term": "zzz"}})
    row = _only_record(tmp_path)
    assert row["caller_project"] == "project-a"
    assert row["caller_source"] == usage.CALLER_CLIENT_ROOT
