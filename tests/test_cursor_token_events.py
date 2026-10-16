"""Cursor stop-hook JSONL capture + normalize merge (#325).

# @spec: 328-cursor-cli-token-usage
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from llmwiki.adapters.contrib.cursor_cli import CursorCliAdapter
from llmwiki.cursor_token_events import (
    append_hook_event,
    default_stop_hook_command,
    ingest_stream_json_text,
    install_stop_hook,
    merge_cursor_stop_token_hook,
    usage_records_for_conversation,
    write_stop_hook_script,
)


def test_append_and_load_hook_event(tmp_path: Path, monkeypatch):
    log = tmp_path / "events.jsonl"
    monkeypatch.setenv("LLMWIKI_CURSOR_TOKEN_EVENTS", str(log))
    payload = {
        "hook_event_name": "stop",
        "conversation_id": "conv-abc",
        "generation_id": "gen-1",
        "input_tokens": 1000,
        "output_tokens": 50,
        "cache_read_tokens": 400,
        "cache_write_tokens": 100,
    }
    assert append_hook_event(payload) is True
    assert append_hook_event(payload) is True  # second turn same gen — load dedupes
    records = usage_records_for_conversation("conv-abc")
    assert len(records) == 1
    usage = records[0]["message"]["usage"]
    assert usage["input_tokens"] == 500
    assert usage["cache_read_input_tokens"] == 400
    assert usage["cache_creation_input_tokens"] == 100
    assert usage["output_tokens"] == 50


def test_append_skips_occupancy_only(tmp_path: Path, monkeypatch):
    log = tmp_path / "events.jsonl"
    monkeypatch.setenv("LLMWIKI_CURSOR_TOKEN_EVENTS", str(log))
    assert (
        append_hook_event(
            {
                "conversation_id": "c1",
                "used_tokens": 12000,
                "max_tokens": 300000,
            }
        )
        is False
    )
    assert not log.exists()


def test_normalize_merges_hook_events_when_store_has_no_usage(
    tmp_path: Path, monkeypatch
):
    log = tmp_path / "events.jsonl"
    monkeypatch.setenv("LLMWIKI_CURSOR_TOKEN_EVENTS", str(log))
    append_hook_event(
        {
            "conversation_id": "sess-hook-1",
            "generation_id": "g1",
            "input_tokens": 200,
            "output_tokens": 20,
            "cache_read_tokens": 50,
            "cache_write_tokens": 10,
        }
    )
    adapter = CursorCliAdapter({})
    out = adapter.normalize_records(
        [
            {"type": "cursor_cli_meta", "sessionId": "sess-hook-1"},
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": [{"type": "text", "text": "yo"}]},
        ]
    )
    usages = [
        r["message"]["usage"]
        for r in out
        if r.get("type") == "assistant" and "usage" in r.get("message", {})
    ]
    assert len(usages) == 1
    assert usages[0]["input_tokens"] == 140
    assert usages[0]["output_tokens"] == 20


def test_normalize_does_not_double_count_when_store_has_usage(
    tmp_path: Path, monkeypatch
):
    log = tmp_path / "events.jsonl"
    monkeypatch.setenv("LLMWIKI_CURSOR_TOKEN_EVENTS", str(log))
    append_hook_event(
        {
            "conversation_id": "sess-hook-2",
            "generation_id": "g2",
            "input_tokens": 999,
            "output_tokens": 9,
            "cache_read_tokens": 0,
            "cache_write_tokens": 0,
        }
    )
    adapter = CursorCliAdapter({})
    out = adapter.normalize_records(
        [
            {"type": "cursor_cli_meta", "sessionId": "sess-hook-2"},
            {
                "role": "assistant",
                "content": [{"type": "text", "text": "yo"}],
                "usage": {
                    "input_tokens": 100,
                    "output_tokens": 10,
                    "cache_read_tokens": 40,
                    "cache_write_tokens": 20,
                },
            },
        ]
    )
    usages = [
        r["message"]["usage"]
        for r in out
        if r.get("type") == "assistant" and "usage" in r.get("message", {})
    ]
    assert len(usages) == 1
    assert usages[0]["input_tokens"] == 40


def test_merge_cursor_stop_token_hook_idempotent():
    hooks = {"version": 1, "hooks": {}}
    script = Path("/tmp/llmwiki-cursor-token-stop.sh")
    cmd = default_stop_hook_command(script)
    once = merge_cursor_stop_token_hook(hooks, cmd, install=True)
    twice = merge_cursor_stop_token_hook(once, cmd, install=True)
    assert len(twice["hooks"]["stop"]) == 1
    blob = json.dumps(twice)
    assert str(script) in blob
    assert "python3 -m llmwiki.cursor_token_events" not in blob


def test_shell_stop_hook_appends_raw_jsonl(tmp_path: Path):
    script = write_stop_hook_script(tmp_path / "llmwiki-cursor-token-stop.sh")
    log = tmp_path / "events.jsonl"
    payload = {
        "hook_event_name": "stop",
        "conversation_id": "conv-shell-1",
        "generation_id": "gen-shell-1",
        "input_tokens": 200,
        "output_tokens": 20,
        "cache_read_tokens": 50,
        "cache_write_tokens": 10,
    }
    env = {**os.environ, "LLMWIKI_CURSOR_TOKEN_EVENTS": str(log)}
    subprocess.run(
        [str(script)],
        input=json.dumps(payload).encode(),
        env=env,
        check=True,
        capture_output=True,
    )
    records = usage_records_for_conversation("conv-shell-1", path=log)
    assert len(records) == 1
    assert records[0]["message"]["usage"]["input_tokens"] == 140
    assert records[0]["message"]["usage"]["output_tokens"] == 20


def test_install_stop_hook_writes_shell_script(tmp_path: Path):
    hooks = tmp_path / "hooks.json"
    script = tmp_path / "llmwiki-cursor-token-stop.sh"
    out = install_stop_hook(hooks_path=hooks, script_path=script, backup=False)
    assert out == hooks
    assert script.is_file()
    assert os.access(script, os.X_OK)
    text = script.read_text(encoding="utf-8")
    assert text.startswith("#!/bin/sh")
    assert "llmwiki-cursor-token-stop" in text
    doc = json.loads(hooks.read_text(encoding="utf-8"))
    cmd = doc["hooks"]["stop"][0]["command"]
    assert "llmwiki-cursor-token-stop" in cmd
    assert str(script) in cmd
    assert "python3 -m" not in cmd


def test_ingest_stream_json_result_camel_case(tmp_path: Path, monkeypatch):
    log = tmp_path / "events.jsonl"
    monkeypatch.setenv("LLMWIKI_CURSOR_TOKEN_EVENTS", str(log))
    text = (
        '{"type":"assistant","message":{}}\n'
        '{"type":"result","session_id":"sess-cli-1","request_id":"req-1",'
        '"usage":{"inputTokens":200,"outputTokens":10,'
        '"cacheReadTokens":40,"cacheWriteTokens":20}}\n'
    )
    assert ingest_stream_json_text(text) == 1
    records = usage_records_for_conversation("sess-cli-1")
    assert len(records) == 1
    assert records[0]["message"]["usage"]["input_tokens"] == 140
    assert records[0]["message"]["usage"]["output_tokens"] == 10
