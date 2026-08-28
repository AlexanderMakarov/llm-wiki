"""Tests for ``llmwiki configure-sources`` (#182)."""

from __future__ import annotations

import json
from pathlib import Path

from llmwiki.adapters import REGISTRY
from llmwiki.adapters.base import BaseAdapter
from llmwiki.configure_sources import _suggested_path, run_configure_sources


def test_configure_sources_non_interactive_skips(monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    assert run_configure_sources() == 0


def test_configure_sources_yes_flag_skips(monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    assert run_configure_sources(yes=True) == 0


def test_suggested_path_prefers_existing_default(tmp_path: Path, monkeypatch):
    linux = tmp_path / "linux-store"
    linux.mkdir(parents=True)
    mac = tmp_path / "mac-store"

    class _FakeAdapter(BaseAdapter):
        name = "fake"
        session_store_path = [mac, linux]

    assert _suggested_path(_FakeAdapter, {}, "fake") == str(linux)


def test_configure_sources_writes_enabled_adapter(monkeypatch, tmp_path: Path):
    cfg_path = tmp_path / "config.json"

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

    monkeypatch.setattr("llmwiki.configure_sources.REPO_ROOT", tmp_path)
    monkeypatch.setattr("llmwiki.configure_sources.REGISTRY", REGISTRY)
    monkeypatch.setattr("llmwiki.configure_sources.discover_all", lambda: None)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)

    choices = iter(["y", "y"])
    printed: list[str] = []

    def _capture_print_adapters(config, *, wide=False, selected_names=None):
        printed.append("table")

    monkeypatch.setattr(
        "llmwiki.configure_sources.print_adapters_table",
        _capture_print_adapters,
    )

    try:
        rc = run_configure_sources(
            ask_choice=lambda *a, **k: next(choices),
            ask_until=lambda *a, **k: a[1],
        )
        assert rc == 0
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
        assert data["adapters"]["fake_ai"]["enabled"] is True
        assert printed == ["table"]
    finally:
        REGISTRY.clear()
        REGISTRY.update(saved)


def test_configure_sources_not_detected_custom_path(monkeypatch, tmp_path: Path):
    cfg_path = tmp_path / "config.json"

    class _FakeAdapter(BaseAdapter):
        name = "openclaw"
        is_ai_session = True
        session_store_path = tmp_path / "missing"

        @classmethod
        def description(cls) -> str:
            return "fake openclaw"

    custom = tmp_path / "custom-inbox"
    custom.mkdir(parents=True)

    saved = dict(REGISTRY)
    REGISTRY.clear()
    REGISTRY["openclaw"] = _FakeAdapter

    monkeypatch.setattr("llmwiki.configure_sources.REPO_ROOT", tmp_path)
    monkeypatch.setattr("llmwiki.configure_sources.REGISTRY", REGISTRY)
    monkeypatch.setattr("llmwiki.configure_sources.discover_all", lambda: None)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr(
        "llmwiki.configure_sources.print_adapters_table",
        lambda *a, **k: None,
    )

    choices = iter(["y", "y", "y"])

    try:
        rc = run_configure_sources(
            ask_choice=lambda *a, **k: next(choices),
            ask_until=lambda *a, **k: str(custom),
        )
        assert rc == 0
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
        assert data["adapters"]["openclaw"]["roots"] == [str(custom)]
    finally:
        REGISTRY.clear()
        REGISTRY.update(saved)
