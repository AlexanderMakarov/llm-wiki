"""Cursor Agent CLI ``exclude_headless`` detection (#180 Slice 2).

Store meta (hex-encoded JSON in ``store.db`` meta table) marks nested
Task/subagents via ``subagentInfo`` and non-interactive auto-review via
``approvalMode == auto-review``. Interactive top-level Agent sessions stay
eligible.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from llmwiki import convert as c
from llmwiki.adapters.contrib.cursor_cli import CursorCliAdapter
from llmwiki.convert import DEFAULT_CONFIG, render_session_markdown


def _make_cursor_store(
    db_path: Path,
    messages: list[dict] | None = None,
    *,
    store_meta: dict | None = None,
) -> None:
    """Minimal Cursor CLI store.db with optional launch-meta fields."""
    messages = messages or [
        {"role": "user", "content": "<user_query>hello</user_query>"},
        {
            "role": "assistant",
            "content": [{"type": "text", "text": "hi"}],
        },
    ]
    meta = {"latestRootBlobId": "f" * 64}
    if store_meta:
        meta.update(store_meta)
    con = sqlite3.connect(db_path)
    con.execute("CREATE TABLE blobs (id TEXT PRIMARY KEY, data BLOB)")
    con.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
    ids: list[str] = []
    for i, msg in enumerate(messages):
        bid = f"{i:064x}"
        ids.append(bid)
        con.execute(
            "INSERT INTO blobs VALUES (?, ?)",
            (bid, json.dumps(msg).encode()),
        )
    root_id = meta["latestRootBlobId"]
    root_bytes = ("".join(ids)).encode()
    con.execute("INSERT INTO blobs VALUES (?, ?)", (root_id, root_bytes))
    con.execute(
        "INSERT INTO meta VALUES (?, ?)",
        ("0", json.dumps(meta).encode().hex()),
    )
    con.commit()
    con.close()


# ─── unit: is_headless_session shapes ─────────────────────────────────────


def test_headless_when_subagent_info_present():
    records = [
        {
            "type": "cursor_cli_meta",
            "subagentInfo": {
                "typeName": "code-reviewer",
                "parentAgentId": "parent-1",
            },
            "subagentTypeName": "code-reviewer",
        },
        {"type": "user", "message": {"role": "user", "content": "hi"}},
    ]
    assert CursorCliAdapter().is_headless_session(records) is True


def test_headless_when_approval_mode_auto_review():
    records = [
        {"type": "cursor_cli_meta", "approvalMode": "auto-review"},
        {"type": "user", "message": {"role": "user", "content": "hi"}},
    ]
    assert CursorCliAdapter().is_headless_session(records) is True


def test_headless_approval_mode_case_normalized():
    records = [{"type": "cursor_cli_meta", "approvalMode": " Auto-Review "}]
    assert CursorCliAdapter().is_headless_session(records) is True


def test_headless_when_subagent_info_is_string():
    """String subagentInfo still counts as present; must not call .keys()/.get."""
    records = [
        {"type": "cursor_cli_meta", "subagentInfo": "nested-agent"},
        {"type": "user", "message": {"role": "user", "content": "hi"}},
    ]
    assert CursorCliAdapter().is_headless_session(records) is True


def test_not_headless_for_interactive_top_level_agent():
    records = [
        {"type": "cursor_cli_meta", "approvalMode": "unrestricted"},
        {"type": "user", "message": {"role": "user", "content": "hi"}},
    ]
    assert CursorCliAdapter().is_headless_session(records) is False


def test_not_headless_when_meta_absent():
    records = [{"type": "user", "message": {"role": "user", "content": "hi"}}]
    assert CursorCliAdapter().is_headless_session(records) is False


# ─── load / normalize: meta obtained from store.db ────────────────────────


def test_load_records_injects_session_id_and_created_at(tmp_path: Path):
    """agentId → sessionId/slug; createdAt (ms) → ISO timestamp (#180 smoke)."""
    db = tmp_path / "store.db"
    agent_id = "e2285ab8-ea45-4ca1-97a2-0ae41bba47c5"
    # 2026-04-16T10:00:00.000Z
    created_ms = 1_776_333_600_000
    _make_cursor_store(
        db,
        store_meta={
            "agentId": agent_id,
            "createdAt": created_ms,
            "approvalMode": "unrestricted",
        },
    )
    ad = CursorCliAdapter()
    raw = ad.load_records(db)
    assert raw[0]["type"] == "cursor_cli_meta"
    assert raw[0]["sessionId"] == agent_id
    assert raw[0]["slug"] == "e2285ab8"
    assert raw[0]["timestamp"].startswith("2026-04-16T10:00:00")

    md, slug, started = render_session_markdown(
        ad.normalize_records(raw),
        db,
        "cursor-ws",
        lambda s: s,
        DEFAULT_CONFIG,
        False,
        adapter_name="cursor_cli",
        is_headless=False,
    )
    assert f"sessionId: {agent_id}" in md
    assert "sessionId: store" not in md
    assert slug == "e2285ab8"
    assert started.year == 2026 and started.month == 4 and started.day == 16


def test_load_records_string_subagent_info_no_keys_crash(tmp_path: Path):
    db = tmp_path / "store.db"
    _make_cursor_store(
        db,
        store_meta={
            "agentId": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "subagentInfo": "legacy-string-shape",
        },
    )
    ad = CursorCliAdapter()
    raw = ad.load_records(db)
    assert raw[0]["subagentInfo"] == "legacy-string-shape"
    assert "subagentTypeName" not in raw[0]
    norm = ad.normalize_records(raw)
    assert ad.is_headless_session(norm) is True


def test_load_records_injects_store_meta_for_headless(tmp_path: Path):
    db = tmp_path / "store.db"
    _make_cursor_store(
        db,
        store_meta={
            "approvalMode": "auto-review",
            "subagentInfo": {
                "typeName": "generalPurpose",
                "parentAgentId": "p1",
            },
        },
    )
    ad = CursorCliAdapter()
    raw = ad.load_records(db)
    assert raw[0]["type"] == "cursor_cli_meta"
    assert raw[0]["approvalMode"] == "auto-review"
    assert raw[0]["subagentTypeName"] == "generalPurpose"
    assert "subagentInfo" in raw[0]

    norm = ad.normalize_records(raw)
    assert norm[0]["type"] == "cursor_cli_meta"
    assert ad.is_headless_session(norm) is True


def test_load_records_interactive_meta_not_headless(tmp_path: Path):
    db = tmp_path / "store.db"
    _make_cursor_store(db, store_meta={"approvalMode": "unrestricted"})
    ad = CursorCliAdapter()
    norm = ad.normalize_records(ad.load_records(db))
    assert norm[0]["approvalMode"] == "unrestricted"
    assert ad.is_headless_session(norm) is False


# ─── frontmatter audit fields ─────────────────────────────────────────────


def test_render_persists_cursor_audit_fields(tmp_path: Path):
    records = [
        {
            "type": "cursor_cli_meta",
            "approvalMode": "auto-review",
            "subagentInfo": {"typeName": "code-explorer"},
            "subagentTypeName": "code-explorer",
        },
        {
            "type": "user",
            "sessionId": "sess-c",
            "timestamp": "2026-04-16T10:00:00Z",
            "message": {"role": "user", "content": "review please"},
        },
    ]
    md, _slug, _started = render_session_markdown(
        records,
        tmp_path / "store.db",
        "cursor-ws",
        lambda s: s,
        DEFAULT_CONFIG,
        False,
        adapter_name="cursor_cli",
        is_headless=True,
    )
    assert "is_headless: true" in md
    assert "approvalMode: auto-review" in md
    assert "subagentTypeName: code-explorer" in md


def test_render_omits_cursor_audit_fields_for_claude():
    records = [
        {
            "type": "user",
            "sessionId": "sess-1",
            "timestamp": "2026-04-16T10:00:00Z",
            "entrypoint": "cli",
            "promptSource": "typed",
            "message": {"role": "user", "content": "hi"},
        },
    ]
    md, _slug, _started = render_session_markdown(
        records,
        Path("sess-1.jsonl"),
        "proj",
        lambda s: s,
        DEFAULT_CONFIG,
        False,
        adapter_name="claude_code",
        is_headless=False,
    )
    assert "approvalMode:" not in md
    assert "subagentTypeName:" not in md
    assert "is_headless: false" in md


# ─── convert_all: skip / keep / filter-off ────────────────────────────────


def _seed_cursor(tmp_path: Path) -> tuple[Path, Path, Path]:
    home = tmp_path / "home"
    chats = home / ".cursor" / "chats" / "aabbccddeeff" / "chat-uuid-1"
    chats.mkdir(parents=True)
    out_dir = tmp_path / "repo" / "raw" / "sessions"
    state = tmp_path / "state.json"
    return chats, out_dir, state


def _patch_cursor(monkeypatch, home: Path) -> None:
    store = home / ".cursor" / "chats"
    monkeypatch.setattr(CursorCliAdapter, "session_store_path", store, raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setattr(c, "REPO_ROOT", home.parent / "repo")


def _write_config(tmp_path: Path, filters: dict) -> Path:
    cfg = tmp_path / "sessions_config.json"
    cfg.write_text(json.dumps({"filters": filters}), encoding="utf-8")
    return cfg


def test_convert_skips_cursor_auto_review_by_default(tmp_path, monkeypatch):
    chats, out_dir, state = _seed_cursor(tmp_path)
    _make_cursor_store(chats / "store.db", store_meta={"approvalMode": "auto-review"})
    home = tmp_path / "home"
    _patch_cursor(monkeypatch, home)
    c.discover_adapters()
    c.convert_all(
        adapters=["cursor_cli"],
        out_dir=out_dir,
        state_file=state,
        config_file=tmp_path / "nonexistent.json",
        include_current=True,
    )
    assert sorted(out_dir.rglob("*.md")) == []


def test_convert_skips_cursor_subagent_by_default(tmp_path, monkeypatch):
    chats, out_dir, state = _seed_cursor(tmp_path)
    _make_cursor_store(
        chats / "store.db",
        store_meta={
            "subagentInfo": {"typeName": "code-reviewer", "parentAgentId": "p"},
        },
    )
    _patch_cursor(monkeypatch, tmp_path / "home")
    c.discover_adapters()
    c.convert_all(
        adapters=["cursor_cli"],
        out_dir=out_dir,
        state_file=state,
        config_file=tmp_path / "nonexistent.json",
        include_current=True,
    )
    assert sorted(out_dir.rglob("*.md")) == []


def test_convert_keeps_interactive_cursor_agent(tmp_path, monkeypatch):
    chats, out_dir, state = _seed_cursor(tmp_path)
    agent_id = "11111111-2222-3333-4444-555555555555"
    _make_cursor_store(
        chats / "store.db",
        store_meta={
            "agentId": agent_id,
            "createdAt": 1_776_333_600_000,
            "approvalMode": "unrestricted",
        },
    )
    _patch_cursor(monkeypatch, tmp_path / "home")
    c.discover_adapters()
    c.convert_all(
        adapters=["cursor_cli"],
        out_dir=out_dir,
        state_file=state,
        config_file=tmp_path / "nonexistent.json",
        include_current=True,
    )
    files = sorted(out_dir.rglob("*.md"))
    assert len(files) == 1
    text = files[0].read_text(encoding="utf-8")
    assert "is_headless: false" in text
    assert "approvalMode: unrestricted" in text
    assert f"sessionId: {agent_id}" in text
    assert "sessionId: store" not in text
    assert "2026-04-16" in files[0].name


def test_convert_includes_cursor_headless_when_filter_off(tmp_path, monkeypatch):
    chats, out_dir, state = _seed_cursor(tmp_path)
    _make_cursor_store(
        chats / "store.db",
        store_meta={
            "approvalMode": "auto-review",
            "subagentInfo": {"typeName": "generalPurpose"},
        },
    )
    _patch_cursor(monkeypatch, tmp_path / "home")
    cfg = _write_config(tmp_path, {"exclude_headless": False})
    c.discover_adapters()
    c.convert_all(
        adapters=["cursor_cli"],
        out_dir=out_dir,
        state_file=state,
        config_file=cfg,
        include_current=True,
    )
    files = sorted(out_dir.rglob("*.md"))
    assert len(files) == 1
    text = files[0].read_text(encoding="utf-8")
    assert "is_headless: true" in text
    assert "approvalMode: auto-review" in text
    assert "subagentTypeName: generalPurpose" in text


def test_exclude_headless_precedes_include_subagents_all(tmp_path, monkeypatch, capsys):
    """Cursor nested agents are exclude_headless, not include_subagents (#180).

    Even with ``include_subagents: all``, a store with ``subagentInfo`` is
    still dropped when exclude_headless is on (default).
    """
    chats, out_dir, state = _seed_cursor(tmp_path)
    _make_cursor_store(
        chats / "store.db",
        store_meta={"subagentInfo": {"typeName": "code-explorer"}},
    )
    _patch_cursor(monkeypatch, tmp_path / "home")
    cfg = _write_config(
        tmp_path,
        {"exclude_headless": True, "include_subagents": "all"},
    )
    c.discover_adapters()
    c.convert_all(
        adapters=["cursor_cli"],
        out_dir=out_dir,
        state_file=state,
        config_file=cfg,
        include_current=True,
    )
    assert sorted(out_dir.rglob("*.md")) == []
    assert "1 headless" in capsys.readouterr().out
