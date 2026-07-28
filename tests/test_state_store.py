"""Tests for unified vault state (llmwiki-state.json + sidecar)."""

from __future__ import annotations

import json
from pathlib import Path

from llmwiki.render import js
from llmwiki.state_store import (
    configure_state_file,
    get_state_file,
    read_state,
    resolve_sidecar_file,
    resolve_state_file,
    update_state,
    write_state,
)


def test_configure_state_file_sets_active(tmp_path: Path):
    vault = tmp_path / "vault"
    vault.mkdir()
    configure_state_file(vault)
    assert get_state_file() == vault / "llmwiki-state.json"
    assert resolve_state_file() == vault / "llmwiki-state.json"


def test_resolve_state_file_from_vault_dir(tmp_path: Path):
    vault = tmp_path / "vault"
    vault.mkdir()
    assert resolve_state_file(vault) == vault / "llmwiki-state.json"


def test_write_state_emits_js_sidecar(tmp_path: Path):
    vault = tmp_path / "vault"
    vault.mkdir()
    state_file = vault / "llmwiki-state.json"
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

    idx = js.JS.index("renderStateWidget")
    chunk = js.JS[idx : idx + 1200]
    assert "fetch(" not in chunk


def test_queue_trace_js_renders_state_widget():

    assert "renderStateWidget" in js.JS
    assert "state-pipeline-table" in js.JS
    assert "To synthesize" in js.JS
    assert "Not synthesized sessions" in js.JS
    assert "Estimate warnings" in js.JS
    assert "Cost estimate" not in js.JS
    assert "previewLimit = 3" not in js.JS
    assert "<li>none</li>" not in js.JS
