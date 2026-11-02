"""#355 — exclude placeholder sessions from Tokens coverage ``known``."""
from __future__ import annotations

from pathlib import Path

import pytest

from llmwiki.migrate_session_tokens import (
    _coverage_from_origins_and_raw,
    run_migration,
)
from llmwiki.session_tokens_usage import load_session_tokens
from llmwiki.token_coverage import (
    is_synthetic_model,
    raw_meta_eligible_for_token_known,
    records_eligible_for_token_known,
)


def test_is_synthetic_model():
    assert is_synthetic_model("<synthetic>")
    assert is_synthetic_model("  <SYNTHETIC>  ")
    assert not is_synthetic_model("claude-sonnet-4-20250514")


def test_raw_meta_excludes_synthetic_zero_tool_by_default():
    meta = {
        "model": "<synthetic>",
        "tool_calls": 0,
        "token_totals": '{"input": 0, "output": 0, "cache_creation": 0, "cache_read": 0}',
    }
    assert not raw_meta_eligible_for_token_known(meta, exclude_non_usage=True)
    assert raw_meta_eligible_for_token_known(meta, exclude_non_usage=False)


def test_raw_meta_keeps_unmeasured_sessions_with_tool_calls():
    meta = {"tool_calls": 3}
    assert raw_meta_eligible_for_token_known(meta, exclude_non_usage=True)


def test_records_exclude_empty_usage_zero_tools():
    records = [
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "hi"}]}},
    ]
    assert not records_eligible_for_token_known(records, exclude_non_usage=True)


@pytest.fixture
def isolate_token_coverage_origins(monkeypatch):
    """Coverage tests must not walk the developer's real agent session stores."""
    monkeypatch.setattr("llmwiki.migrate_session_tokens.REGISTRY", {})


def test_coverage_from_raw_omits_synthetic_placeholders(
    tmp_path: Path, monkeypatch, isolate_token_coverage_origins
):
    vault = tmp_path / "vault"
    sessions = vault / "raw" / "sessions"
    sessions.mkdir(parents=True)
    (sessions / "measured.md").write_text(
        "---\n"
        "tags: [claude-code, session-transcript]\n"
        "sessionId: s-measured\n"
        'token_totals: {"input": 1, "cache_creation": 0, "cache_read": 0, "output": 0}\n'
        "tool_calls: 2\n"
        "---\n\n# measured\n",
        encoding="utf-8",
    )
    (sessions / "placeholder.md").write_text(
        "---\n"
        "tags: [claude-code, session-transcript]\n"
        "sessionId: s-placeholder\n"
        "model: <synthetic>\n"
        "tool_calls: 0\n"
        'token_totals: {"input": 0, "cache_creation": 0, "cache_read": 0, "output": 0}\n'
        "---\n\n# placeholder\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "llmwiki.migrate_session_tokens._backfill_capable_adapter",
        lambda *args, **kwargs: None,
    )
    report = run_migration(vault=vault, dry_run=False, config={})
    assert report["raw_upserts"] == 1
    assert report["raw_skipped_empty"] == 1
    data = load_session_tokens(vault)
    assert data["by_agent"]["claude_code"]["measured"] == 1
    assert data["by_agent"]["claude_code"]["known"] == 1


def test_coverage_respects_filter_off(tmp_path: Path, isolate_token_coverage_origins):
    sessions = tmp_path / "raw" / "sessions"
    sessions.mkdir(parents=True)
    (sessions / "placeholder.md").write_text(
        "---\n"
        "tags: [claude-code, session-transcript]\n"
        "model: <synthetic>\n"
        "tool_calls: 0\n"
        "---\n\n# placeholder\n",
        encoding="utf-8",
    )
    known, _since = _coverage_from_origins_and_raw(
        sessions,
        {"filters": {"exclude_non_usage_from_token_coverage": False}},
        {},
    )
    assert known["claude_code"] == 1


def test_coverage_default_filter_excludes_placeholder(
    tmp_path: Path, isolate_token_coverage_origins
):
    sessions = tmp_path / "raw" / "sessions"
    sessions.mkdir(parents=True)
    (sessions / "placeholder.md").write_text(
        "---\n"
        "tags: [claude-code, session-transcript]\n"
        "model: <synthetic>\n"
        "tool_calls: 0\n"
        "---\n\n# placeholder\n",
        encoding="utf-8",
    )
    known, _since = _coverage_from_origins_and_raw(sessions, {}, {})
    assert known.get("claude_code", 0) == 0
