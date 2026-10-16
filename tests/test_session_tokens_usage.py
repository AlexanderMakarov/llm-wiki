"""Tests for usage/session-tokens.json store (#325)."""
from __future__ import annotations

import json
import time

from llmwiki.session_tokens_usage import (
    SIDECAR_GLOBAL,
    day_from_last_activity,
    emit_session_tokens_sidecar,
    load_session_tokens,
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
