"""Tests for ``llmwiki configure-sources`` (#182)."""

from __future__ import annotations

import json
from pathlib import Path

from llmwiki import REPO_ROOT
from llmwiki.adapters import REGISTRY
from llmwiki.adapters.base import BaseAdapter
from llmwiki.configure_sources import run_configure_sources


def test_configure_sources_non_interactive_skips(monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    assert run_configure_sources() == 0


def test_configure_sources_yes_flag_skips(monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    assert run_configure_sources(yes=True) == 0


def test_configure_sources_writes_enabled_adapter(monkeypatch, tmp_path: Path):
    cfg_path = REPO_ROOT / "config.json"
    backup = cfg_path.read_text(encoding="utf-8") if cfg_path.is_file() else None
    if cfg_path.is_file():
        cfg_path.unlink()

    class _FakeAdapter(BaseAdapter):
        name = "fake_ai"
        is_ai_session = True
        session_store_path = tmp_path / "store"

        @classmethod
        def description(cls) -> str:
            return "fake"

    (tmp_path / "store").mkdir(parents=True, exist_ok=True)

    saved = dict(REGISTRY)
    REGISTRY.clear()
    REGISTRY["fake_ai"] = _FakeAdapter

    def _noop_discover() -> None:
        return None

    monkeypatch.setattr("llmwiki.configure_sources.REGISTRY", REGISTRY)
    monkeypatch.setattr("llmwiki.configure_sources.discover_all", _noop_discover)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)

    choices = iter(["y", "y"])

    try:
        rc = run_configure_sources(
            ask_choice=lambda *a, **k: next(choices),
            ask_until=lambda *a, **k: a[1],
        )
        assert rc == 0
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
        assert data["adapters"]["fake_ai"]["enabled"] is True
    finally:
        if cfg_path.is_file():
            cfg_path.unlink()
        if backup is not None:
            cfg_path.write_text(backup, encoding="utf-8")
        REGISTRY.clear()
        REGISTRY.update(saved)
