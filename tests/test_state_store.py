"""Tests for unified vault state (llmwiki-state.json + sidecar)."""

from __future__ import annotations

import json
from pathlib import Path

from llmwiki.state_store import (
    read_state,
    resolve_sidecar_file,
    resolve_state_file,
    update_state,
    write_state,
)


def test_resolve_state_file_from_vault_dir(tmp_path: Path):
    vault = tmp_path / "vault"
    vault.mkdir()
    assert resolve_state_file(vault) == vault / "llmwiki-state.json"


def test_write_state_emits_js_sidecar(tmp_path: Path, monkeypatch):
    vault = tmp_path / "vault"
    vault.mkdir()
    state_file = vault / "llmwiki-state.json"
    monkeypatch.setattr(
        "llmwiki.state_store.load_default_vault_path",
        lambda: None,
    )
    write_state({"queue": {"items": [{"id": "t1", "status": "pending"}]}}, state_file)
    assert state_file.is_file()
    sidecar = resolve_sidecar_file(state_file)
    assert sidecar.is_file()
    text = sidecar.read_text(encoding="utf-8")
    assert text.startswith("window.LLMWIKI_STATE_SNAPSHOT = ")
    payload = json.loads(text.split("=", 1)[1].rstrip().rstrip(";"))
    assert payload["queue"]["items"][0]["id"] == "t1"


def test_update_state_increments_revision(tmp_path: Path):
    state_file = tmp_path / "llmwiki-state.json"
    write_state({}, state_file)
    update_state(lambda s: s, state_file)
    state = read_state(state_file)
    assert state["meta"]["revision"] >= +2


def test_queue_trace_js_has_no_fetch():
    from llmwiki.render import js

    idx = js.JS.index("renderQueueTrace")
    chunk = js.JS[idx : idx + 900]
    assert "fetch(" not in chunk


def test_queue_trace_js_renders_estimate_block():
    from llmwiki.render import js

    assert "Cost estimate" in js.JS
    assert "estimate.incremental_usd" in js.JS
