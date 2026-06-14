"""Tests for the OpenClaw + Cursor-CLI adapters and the load_records hook."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from llmwiki.adapters import REGISTRY, discover_all
from llmwiki.adapters.contrib.openclaw import OpenClawAdapter, _flatten_text_blocks
from llmwiki.adapters.contrib.cursor_cli import CursorCliAdapter
from llmwiki.convert import truncate_chars


def test_adapters_register():
    discover_all()
    assert "openclaw" in REGISTRY
    assert "cursor_cli" in REGISTRY


def test_truncate_chars_zero_means_no_limit():
    # The verbatim lever: max_chars <= 0 returns the text untouched.
    big = "x" * 10000
    assert truncate_chars(big, 0) == big
    assert truncate_chars(big, -1) == big
    assert "truncated" in truncate_chars(big, 100)


def test_flatten_text_blocks():
    assert _flatten_text_blocks("hello") == "hello"
    assert _flatten_text_blocks([{"type": "text", "text": "a"}, {"type": "text", "text": "b"}]) == "a\nb"
    assert _flatten_text_blocks([{"type": "image"}]) == ""


def test_openclaw_normalize_keeps_only_messages_and_flattens_user():
    records = [
        {"type": "session", "id": "s"},
        {"type": "model_change", "id": "m"},
        {"type": "message", "id": "1", "parentId": None, "timestamp": "t",
         "message": {"role": "user", "content": [{"type": "text", "text": "hi there"}]}},
        {"type": "message", "id": "2", "parentId": "1", "timestamp": "t",
         "message": {"role": "assistant", "content": [{"type": "text", "text": "hello"}]}},
    ]
    out = OpenClawAdapter().normalize_records(records)
    assert [r["type"] for r in out] == ["user", "assistant"]
    # User content flattened to a string so the shared renderer keeps it verbatim.
    assert out[0]["message"]["content"] == "hi there"
    # Assistant content kept as blocks.
    assert isinstance(out[1]["message"]["content"], list)


def test_openclaw_discover_skips_trajectories(tmp_path: Path, monkeypatch):
    store = tmp_path / ".openclaw" / "agents" / "main" / "sessions"
    store.mkdir(parents=True)
    (store / "a.jsonl").write_text("{}")
    (store / "a.trajectory.jsonl").write_text("{}")
    ad = OpenClawAdapter()
    ad.session_store_path = tmp_path / ".openclaw" / "agents"
    found = [p.name for p in ad.discover_sessions()]
    assert found == ["a.jsonl"]
    assert ad.derive_project_slug(store / "a.jsonl") == "openclaw-main"


def _make_cursor_store(db_path: Path, messages: list[dict]) -> None:
    """Build a minimal Cursor CLI store.db: JSON message blobs + a root tree
    blob whose bytes reference the message ids in order."""
    con = sqlite3.connect(db_path)
    con.execute("CREATE TABLE blobs (id TEXT PRIMARY KEY, data BLOB)")
    con.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
    ids = []
    for i, msg in enumerate(messages):
        bid = f"{i:064x}"  # deterministic 64-hex id
        ids.append(bid)
        con.execute("INSERT INTO blobs VALUES (?, ?)", (bid, json.dumps(msg).encode()))
    # Root tree blob: raw bytes are the message ids concatenated (in order),
    # so offset-ordering recovers the conversation order.
    root_id = "f" * 64
    root_bytes = ("".join(ids)).encode()
    con.execute("INSERT INTO blobs VALUES (?, ?)", (root_id, root_bytes))
    con.execute("INSERT INTO meta VALUES (?, ?)",
                ("0", json.dumps({"latestRootBlobId": root_id}).encode().hex()))
    con.commit()
    con.close()


def test_cursor_cli_loads_orders_and_normalizes(tmp_path: Path):
    db = tmp_path / "store.db"
    _make_cursor_store(db, [
        {"role": "system", "content": "you are an assistant"},
        {"role": "user", "content": "<user_query>what is 2+2</user_query>"},
        {"id": "1", "role": "assistant",
         "content": [{"type": "reasoning", "text": "think"}, {"type": "text", "text": "4"}]},
        {"role": "tool", "content": [{"type": "tool-result", "result": "noise"}]},
    ])
    ad = CursorCliAdapter()
    raw = ad.load_records(db)
    # Ordered by appearance in the root tree: system, user, assistant, tool.
    assert [r.get("role") for r in raw] == ["system", "user", "assistant", "tool"]

    norm = ad.normalize_records(raw)
    # system + tool dropped; user + assistant kept.
    assert [r["type"] for r in norm] == ["user", "assistant"]
    assert norm[0]["message"]["content"] == "<user_query>what is 2+2</user_query>"
    kinds = [b["type"] for b in norm[1]["message"]["content"]]
    assert kinds == ["thinking", "text"]


def test_build_site_honors_raw_sessions_param(tmp_path: Path):
    # Regression (#54 vault build): build_site used the module-level
    # RAW_SESSIONS constant, so `build --vault` silently read the repo's
    # raw/ instead of the vault's. It must read the path it's given.
    from llmwiki.build import build_site

    missing = tmp_path / "vault" / "raw" / "sessions"
    rc = build_site(out_dir=tmp_path / "site", raw_sessions=missing, raw_dir=missing.parent)
    # Honors the passed path: reports it missing and bails (rc 2) rather
    # than scanning the module constant.
    assert rc == 2
