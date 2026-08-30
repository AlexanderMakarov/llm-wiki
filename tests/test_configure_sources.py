"""Tests for ``llmwiki configure-sources`` (#182, #192 lookback quiz).

# @layer: unit
# @spec: 177-sync-lookback
# @regression
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from llmwiki.adapters import REGISTRY
from llmwiki.adapters.base import BaseAdapter, SyncCandidateEstimate
from llmwiki.configure_sources import (
    _INHERIT_SINCE,
    _estimate_for,
    _format_earliest,
    _merge_write_config,
    _suggested_path,
    run_configure_sources,
    suggested_since_today_minus_30,
)


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


def test_format_earliest_is_local_calendar_day():
    # Fixed UTC instant → local calendar day (system tz), no clock time.
    est = SyncCandidateEstimate(
        eligible=1,
        in_last_30_days=1,
        earliest=datetime(2024, 10, 24, 14, 20, 6, tzinfo=UTC),
    )
    assert _format_earliest(est) == est.earliest.astimezone().date().isoformat()
    assert "T" not in _format_earliest(est)
    assert _format_earliest(SyncCandidateEstimate(eligible=0, in_last_30_days=0)) == "—"


def test_suggested_since_today_minus_30_is_absolute():
    fixed = datetime(2026, 8, 30, tzinfo=UTC)
    assert suggested_since_today_minus_30(today=fixed) == "2026-07-31"


def test_configure_sources_writes_enabled_adapter(monkeypatch, tmp_path: Path):
    cfg_path = tmp_path / "config.json"

    class _FakeAdapter(BaseAdapter):
        name = "fake_ai"
        is_ai_session = True
        session_store_path = tmp_path / "store"

        @classmethod
        def description(cls) -> str:
            return "fake"

        def estimate_sync_candidates(self) -> SyncCandidateEstimate:
            return SyncCandidateEstimate(
                eligible=3,
                in_last_30_days=1,
                earliest=datetime(2025, 3, 1, tzinfo=UTC),
            )

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
        # Enter on shared → today−30 absolute; Enter on override → no since key
        assert data["filters"]["since"] == suggested_since_today_minus_30()
        assert "since" not in data["adapters"]["fake_ai"]
        assert printed == ["table"]
    finally:
        REGISTRY.clear()
        REGISTRY.update(saved)


def test_configure_sources_shared_custom_and_adapter_date(monkeypatch, tmp_path: Path):
    """Shared typed date + adapter typed date; unrelated keys kept."""
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(
        json.dumps(
            {
                "filters": {"since": "2020-01-01", "exclude_headless": True},
                "adapters": {"fake_ai": {"enabled": False, "extra": 1}},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    class _FakeAdapter(BaseAdapter):
        name = "fake_ai"
        is_ai_session = True
        session_store_path = tmp_path / "store"

        @classmethod
        def description(cls) -> str:
            return "fake"

        def estimate_sync_candidates(self) -> SyncCandidateEstimate:
            return SyncCandidateEstimate(eligible=2, in_last_30_days=2)

    (tmp_path / "store").mkdir(parents=True, exist_ok=True)

    saved = dict(REGISTRY)
    REGISTRY.clear()
    REGISTRY["fake_ai"] = _FakeAdapter

    monkeypatch.setattr("llmwiki.configure_sources.REPO_ROOT", tmp_path)
    monkeypatch.setattr("llmwiki.configure_sources.REGISTRY", REGISTRY)
    monkeypatch.setattr("llmwiki.configure_sources.discover_all", lambda: None)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr(
        "llmwiki.configure_sources.print_adapters_table",
        lambda *a, **k: None,
    )

    choices = iter(["y", "y"])
    until_raw = iter(["2026-05-01", "2026-06-15"])

    def _until(prompt, default, resolve):
        raw = next(until_raw)
        return resolve(raw)

    try:
        rc = run_configure_sources(
            ask_choice=lambda *a, **k: next(choices),
            ask_until=_until,
        )
        assert rc == 0
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
        assert data["filters"]["since"] == "2026-05-01"
        assert data["filters"]["exclude_headless"] is True  # unrelated key kept
        assert data["adapters"]["fake_ai"]["since"] == "2026-06-15"
        assert data["adapters"]["fake_ai"]["enabled"] is True
        assert data["adapters"]["fake_ai"]["extra"] == 1  # unrelated key kept
    finally:
        REGISTRY.clear()
        REGISTRY.update(saved)


def test_configure_sources_adapter_enter_inherits_shared(monkeypatch, tmp_path: Path):
    cfg_path = tmp_path / "config.json"

    class _FakeAdapter(BaseAdapter):
        name = "fake_ai"
        is_ai_session = True
        session_store_path = tmp_path / "store"

        @classmethod
        def description(cls) -> str:
            return "fake"

        def estimate_sync_candidates(self) -> SyncCandidateEstimate:
            return SyncCandidateEstimate(eligible=0, in_last_30_days=0)

    (tmp_path / "store").mkdir(parents=True, exist_ok=True)

    saved = dict(REGISTRY)
    REGISTRY.clear()
    REGISTRY["fake_ai"] = _FakeAdapter

    monkeypatch.setattr("llmwiki.configure_sources.REPO_ROOT", tmp_path)
    monkeypatch.setattr("llmwiki.configure_sources.REGISTRY", REGISTRY)
    monkeypatch.setattr("llmwiki.configure_sources.discover_all", lambda: None)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr(
        "llmwiki.configure_sources.print_adapters_table",
        lambda *a, **k: None,
    )

    choices = iter(["y", "y"])
    # shared Enter (today−30) · adapter Enter (inherit)
    until_raw = iter(["", ""])

    def _until(prompt, default, resolve):
        raw = next(until_raw)
        if not raw:
            return default
        return resolve(raw)

    try:
        rc = run_configure_sources(
            ask_choice=lambda *a, **k: next(choices),
            ask_until=_until,
        )
        assert rc == 0
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
        assert data["filters"]["since"] == suggested_since_today_minus_30()
        assert "since" not in data["adapters"]["fake_ai"]
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

        def estimate_sync_candidates(self) -> SyncCandidateEstimate:
            return SyncCandidateEstimate(eligible=0, in_last_30_days=0)

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

    choices = iter(["y", "y"])
    # shared Enter; Path custom; adapter start-date Enter
    until_calls: list[str] = []

    def _until(prompt, default, resolve):
        until_calls.append(prompt)
        if "Path" in prompt:
            return str(custom)
        return default

    try:
        rc = run_configure_sources(
            ask_choice=lambda *a, **k: next(choices),
            ask_until=_until,
        )
        assert rc == 0
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
        assert data["adapters"]["openclaw"]["roots"] == [str(custom)]
        assert data["filters"]["since"] == suggested_since_today_minus_30()
        assert "since" not in data["adapters"]["openclaw"]
        assert any("Path" in p for p in until_calls)
    finally:
        REGISTRY.clear()
        REGISTRY.update(saved)


def test_configure_sources_enter_keeps_stored_shared_since(monkeypatch, tmp_path: Path):
    """Re-run: Enter on shared keeps the stored date (not today−30)."""
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(
        json.dumps({"filters": {"since": "2024-01-01"}}) + "\n",
        encoding="utf-8",
    )

    class _FakeAdapter(BaseAdapter):
        name = "fake_ai"
        is_ai_session = True
        session_store_path = tmp_path / "store"

        @classmethod
        def description(cls) -> str:
            return "fake"

        def estimate_sync_candidates(self) -> SyncCandidateEstimate:
            return SyncCandidateEstimate(eligible=1, in_last_30_days=1)

    (tmp_path / "store").mkdir(parents=True, exist_ok=True)

    saved = dict(REGISTRY)
    REGISTRY.clear()
    REGISTRY["fake_ai"] = _FakeAdapter

    monkeypatch.setattr("llmwiki.configure_sources.REPO_ROOT", tmp_path)
    monkeypatch.setattr("llmwiki.configure_sources.REGISTRY", REGISTRY)
    monkeypatch.setattr("llmwiki.configure_sources.discover_all", lambda: None)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr(
        "llmwiki.configure_sources.print_adapters_table",
        lambda *a, **k: None,
    )

    choices = iter(["y", "y"])

    try:
        rc = run_configure_sources(
            ask_choice=lambda *a, **k: next(choices),
            ask_until=lambda *a, **k: a[1],
        )
        assert rc == 0
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
        assert data["filters"]["since"] == "2024-01-01"
    finally:
        REGISTRY.clear()
        REGISTRY.update(saved)


def test_merge_write_config_clears_adapter_since(tmp_path: Path, monkeypatch):
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(
        json.dumps(
            {
                "filters": {"since": "2026-01-01"},
                "adapters": {
                    "x": {"enabled": True, "since": "2026-02-01", "roots": ["/a"]},
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("llmwiki.configure_sources.REPO_ROOT", tmp_path)
    _merge_write_config(
        {"x": {"enabled": True}},
        filters_since="2026-07-31",
        clear_adapter_since={"x"},
    )
    data = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert data["filters"]["since"] == "2026-07-31"
    assert "since" not in data["adapters"]["x"]
    assert data["adapters"]["x"]["roots"] == ["/a"]


def test_merge_write_config_inherit_sentinel_leaves_filters(tmp_path: Path, monkeypatch):
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(
        json.dumps({"filters": {"since": "2026-03-01"}, "adapters": {}}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("llmwiki.configure_sources.REPO_ROOT", tmp_path)
    _merge_write_config({"y": {"enabled": False}}, filters_since=_INHERIT_SINCE)
    data = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert data["filters"]["since"] == "2026-03-01"


def test_configure_sources_missing_path_empty_skips_without_hang(monkeypatch, tmp_path: Path):
    """B1: empty Path answers (EOF) skip the adapter instead of spinning."""
    cfg_path = tmp_path / "config.json"

    class _FakeAdapter(BaseAdapter):
        name = "openclaw"
        is_ai_session = True
        session_store_path = tmp_path / "missing"

        @classmethod
        def description(cls) -> str:
            return "fake"

        def estimate_sync_candidates(self) -> SyncCandidateEstimate:
            return SyncCandidateEstimate(eligible=0, in_last_30_days=0)

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
    choices = iter(["y", "y"])  # enable despite missing store; save
    path_asks = {"n": 0}

    def _until(prompt, default, resolve):
        if prompt.strip().startswith("Path:"):
            path_asks["n"] += 1
            return default
        return default

    try:
        rc = run_configure_sources(
            ask_choice=lambda *a, **k: next(choices),
            ask_until=_until,
        )
        assert rc == 0
        assert path_asks["n"] == 3
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
        assert "openclaw" not in data.get("adapters", {})
        assert "filters" in data and "since" in data["filters"]
    finally:
        REGISTRY.clear()
        REGISTRY.update(saved)


def test_estimate_for_reports_exception_class(tmp_path: Path):
    class _Boom(BaseAdapter):
        name = "boom"
        session_store_path = tmp_path

        def estimate_sync_candidates(self):
            raise OSError("locked")

    est, err = _estimate_for("boom", _Boom, {})
    assert est.eligible == 0
    assert err == "OSError"


def test_configure_sources_ingest_not_ready_defaults_off(monkeypatch, tmp_path: Path, capsys):
    """N6: ingest_ready=False offers [y/N] even when the store is present."""
    (tmp_path / "store").mkdir()

    class _Ide(BaseAdapter):
        name = "cursor_ide"
        ingest_ready = False
        is_ai_session = True
        session_store_path = tmp_path / "store"

        @classmethod
        def description(cls) -> str:
            return "ide"

        def estimate_sync_candidates(self) -> SyncCandidateEstimate:
            return SyncCandidateEstimate(eligible=1, in_last_30_days=1)

    saved = dict(REGISTRY)
    REGISTRY.clear()
    REGISTRY["cursor_ide"] = _Ide
    monkeypatch.setattr("llmwiki.configure_sources.REPO_ROOT", tmp_path)
    monkeypatch.setattr("llmwiki.configure_sources.REGISTRY", REGISTRY)
    monkeypatch.setattr("llmwiki.configure_sources.discover_all", lambda: None)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr(
        "llmwiki.configure_sources.print_adapters_table",
        lambda *a, **k: None,
    )
    enable_defaults: list[str] = []
    answers = iter(["n", "y"])  # decline enable; save shared date

    def _choice(prompt, valid, default, **k):
        if "Enable" in prompt:
            enable_defaults.append(default)
            return next(answers)
        return next(answers)

    try:
        rc = run_configure_sources(
            ask_choice=_choice,
            ask_until=lambda *a, **k: a[1],
        )
        assert rc == 0
        assert enable_defaults == ["n"]
        out = capsys.readouterr().out
        assert "not included in a default sync" in out
        assert "#2" not in out
    finally:
        REGISTRY.clear()
        REGISTRY.update(saved)

