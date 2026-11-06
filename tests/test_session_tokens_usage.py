"""Tests for usage/session-tokens.json store (#325)."""
from __future__ import annotations

import json
import time

import pytest

import llmwiki.session_tokens_usage as stu
from llmwiki.session_tokens_usage import (
    SIDECAR_GLOBAL,
    day_from_last_activity,
    emit_session_tokens_sidecar,
    load_session_tokens,
    session_tokens_batch,
    upsert_session_tokens,
    usage_path,
)


def _totals(**kwargs: int) -> dict[str, int]:
    base = {"input": 0, "cache_creation": 0, "cache_read": 0, "output": 0}
    base.update(kwargs)
    return base


def test_day_from_last_activity_utc():
    assert day_from_last_activity("2026-03-15T23:30:00Z") == "2026-03-15"
    assert day_from_last_activity("2026-03-16T01:00:00+04:00") == "2026-03-15"


def test_idempotent_upsert_same_fingerprint(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    kwargs = {
        "session_key": "sess-a",
        "agent": "cursor_cli",
        "totals": _totals(input=100, output=20),
        "fingerprint": "fp-1",
        "last_activity": "2026-04-01T12:00:00Z",
    }
    assert upsert_session_tokens(vault, **kwargs) is True
    data = load_session_tokens(vault)
    assert data["totals"]["input"] == 100
    assert data["totals"]["output"] == 20
    assert data["totals"]["sum"] == 120
    assert data["by_agent"]["cursor_cli"]["known"] == 1
    assert data["by_agent"]["cursor_cli"]["measured"] == 1

    assert upsert_session_tokens(vault, **kwargs) is False
    assert load_session_tokens(vault)["totals"]["sum"] == 120


def test_fingerprint_skip_leaves_mtime_unchanged(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    kwargs = {
        "session_key": "sess-b",
        "agent": "claude_code",
        "totals": _totals(input=10),
        "fingerprint": "stable",
        "last_activity": "2026-05-01T10:00:00Z",
    }
    assert upsert_session_tokens(vault, **kwargs) is True
    path = usage_path(vault)
    mtime = path.stat().st_mtime
    time.sleep(0.02)
    assert upsert_session_tokens(vault, **kwargs) is False
    assert path.stat().st_mtime == mtime


def test_day_moves_on_resume(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    key = "sess-c"
    assert upsert_session_tokens(
        vault,
        session_key=key,
        agent="cursor_cli",
        totals=_totals(input=50, output=5),
        fingerprint="fp-old",
        last_activity="2026-06-01T22:00:00Z",
    )
    assert "2026-06-01" in load_session_tokens(vault)["days"]

    assert upsert_session_tokens(
        vault,
        session_key=key,
        agent="cursor_cli",
        totals=_totals(input=80, output=8),
        fingerprint="fp-new",
        last_activity="2026-06-02T01:00:00Z",
    )
    data = load_session_tokens(vault)
    assert "2026-06-01" not in data["days"] or "cursor_cli" not in data["days"].get(
        "2026-06-01", {}
    )
    assert data["days"]["2026-06-02"]["cursor_cli"]["input"] == 80
    assert data["totals"]["input"] == 80
    assert data["sessions"][key]["day"] == "2026-06-02"


def test_metrics_only_stub_counts_in_aggregates(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    assert upsert_session_tokens(
        vault,
        session_key="metrics-only",
        agent="cursor_cli",
        totals=_totals(cache_read=200),
        fingerprint="m1",
        last_activity="2026-07-10T15:00:00Z",
        metrics_only=True,
        in_raw=False,
    )
    data = load_session_tokens(vault)
    stub = data["sessions"]["metrics-only"]
    assert stub["metrics_only"] is True
    assert stub["in_raw"] is False
    assert data["by_agent"]["cursor_cli"]["measured"] == 1
    assert data["totals"]["cache_read"] == 200


def test_emit_session_tokens_sidecar(tmp_path):
    vault = tmp_path / "vault"
    site = tmp_path / "site"
    vault.mkdir()
    site.mkdir()
    upsert_session_tokens(
        vault,
        session_key="s1",
        agent="cursor_cli",
        totals=_totals(output=9),
        fingerprint="x",
        last_activity="2026-08-01T00:00:00Z",
    )
    emit_session_tokens_sidecar(vault, site)
    text = (site / "session-tokens.js").read_text(encoding="utf-8")
    assert text.startswith(f"window.{SIDECAR_GLOBAL} = ")
    payload = json.loads(text.split("=", 1)[1].rstrip().rstrip(";"))
    assert payload["totals"]["output"] == 9
    assert "sessions" not in payload
    assert "s1" not in text


def test_emit_session_tokens_sidecar_omits_metrics_only_session_keys(tmp_path):
    """Public sidecar must not embed vault session ledger keys (#325 B1)."""
    vault = tmp_path / "vault"
    site = tmp_path / "site"
    vault.mkdir()
    site.mkdir()
    upsert_session_tokens(
        vault,
        session_key="metrics-only-secret-key",
        agent="cursor_cli",
        totals=_totals(cache_read=200),
        fingerprint="m1",
        last_activity="2026-07-10T15:00:00Z",
        metrics_only=True,
        in_raw=False,
    )
    emit_session_tokens_sidecar(vault, site)
    text = (site / "session-tokens.js").read_text(encoding="utf-8")
    payload = json.loads(text.split("=", 1)[1].rstrip().rstrip(";"))
    assert "sessions" not in payload
    assert "metrics-only-secret-key" not in text
    assert payload["by_agent"]["cursor_cli"]["measured"] == 1
    assert payload["totals"]["cache_read"] == 200


def _upsert_n(vault, n: int, *, start: int = 0) -> None:
    for i in range(start, start + n):
        upsert_session_tokens(
            vault,
            session_key=f"s-{i}",
            agent="claude_code" if i % 2 else "codex_cli",
            totals=_totals(input=i + 1, output=1),
            fingerprint=f"fp-{i}",
            last_activity=f"2026-04-{(i % 28) + 1:02d}T12:00:00Z",
        )


def _count_writes(monkeypatch) -> list[int]:
    writes: list[int] = []
    real = stu._write_document

    def counting(vault, data):
        writes.append(1)
        real(vault, data)

    monkeypatch.setattr(stu, "_write_document", counting)
    return writes


def _without_timestamp(vault) -> dict:
    data = json.loads(usage_path(vault).read_text(encoding="utf-8"))
    data.pop("updated_at", None)
    return data


def test_batch_writes_store_once_with_same_result(tmp_path, monkeypatch):
    """Batched upserts persist once and match per-session upserts exactly."""
    plain, batched = tmp_path / "plain", tmp_path / "batched"
    plain.mkdir()
    batched.mkdir()
    _upsert_n(plain, 30)
    _upsert_n(plain, 5)  # unchanged fingerprints: no-ops

    writes = _count_writes(monkeypatch)
    with session_tokens_batch(batched):
        _upsert_n(batched, 30)
        _upsert_n(batched, 5)
    assert len(writes) == 1
    assert _without_timestamp(batched) == _without_timestamp(plain)


def test_load_inside_batch_sees_pending_upserts(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    with session_tokens_batch(vault):
        _upsert_n(vault, 3)
        assert not usage_path(vault).exists()
        data = load_session_tokens(vault)
        assert len(data["sessions"]) == 3
        assert data["totals"]["input"] == 1 + 2 + 3
    assert load_session_tokens(vault)["totals"]["input"] == 6


def test_batch_saves_progress_when_block_raises(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    with pytest.raises(KeyboardInterrupt), session_tokens_batch(vault):
        _upsert_n(vault, 4)
        raise KeyboardInterrupt
    assert len(load_session_tokens(vault)["sessions"]) == 4


def test_nested_batch_joins_outer(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    vault.mkdir()
    writes = _count_writes(monkeypatch)
    with session_tokens_batch(vault):
        with session_tokens_batch(vault):
            _upsert_n(vault, 2)
        assert writes == []
        _upsert_n(vault, 2, start=2)
    assert len(writes) == 1
    assert len(load_session_tokens(vault)["sessions"]) == 4


def test_batch_without_changes_does_not_write(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    vault.mkdir()
    writes = _count_writes(monkeypatch)
    with session_tokens_batch(vault):
        load_session_tokens(vault)
    assert writes == []
