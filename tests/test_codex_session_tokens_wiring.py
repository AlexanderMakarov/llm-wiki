"""Convert / migrate upserts Codex session Tokens into usage store (#324).

# @spec: 329-codex-cli-token-usage
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from llmwiki.adapters import discover_all
from llmwiki.convert import convert_all
from llmwiki.migrate_session_tokens import run_migration
from llmwiki.session_tokens_usage import load_session_tokens

_FIXTURE = (
    Path(__file__).resolve().parent / "fixtures" / "codex_token_count_session.jsonl"
)

_EXPECTED_TOTALS = {
    "input": 340,
    "cache_creation": 10,
    "cache_read": 50,
    "output": 60,
}


def _write_codex_config(path: Path, roots: list[Path]) -> Path:
    path.write_text(
        json.dumps(
            {
                "filters": {"exclude_headless": False},
                "adapters": {"codex_cli": {"roots": [str(r) for r in roots]}},
            }
        ),
        encoding="utf-8",
    )
    return path


def test_convert_codex_fixture_upserts_token_totals_and_usage_file(tmp_path: Path):
    """Steady-state convert: nonempty Codex usage → frontmatter + session-tokens."""
    store = tmp_path / "codex-sessions"
    store.mkdir()
    shutil.copy(_FIXTURE, store / "rollout-tokens.jsonl")

    vault = tmp_path / "vault"
    out_dir = vault / "raw" / "sessions"
    out_dir.mkdir(parents=True)
    (vault / "site").mkdir()
    state = tmp_path / "state.json"
    cfg = _write_codex_config(tmp_path / "sessions_config.json", [store])

    discover_all()
    rc = convert_all(
        adapters=["codex_cli"],
        out_dir=out_dir,
        state_file=state,
        config_file=cfg,
        include_current=True,
        force=True,
    )
    assert rc == 0

    written = list(out_dir.glob("*.md"))
    assert len(written) == 1
    md = written[0].read_text(encoding="utf-8")
    assert "token_totals:" in md
    assert "sess-codex-tokens-fixture" in md
    totals_line = next(
        line for line in md.splitlines() if line.startswith("token_totals: ")
    )
    assert json.loads(totals_line[len("token_totals: ") :]) == _EXPECTED_TOTALS

    usage = load_session_tokens(vault)
    sess = usage["sessions"]["sess-codex-tokens-fixture"]
    assert sess["agent"] == "codex_cli"
    assert sess["totals"] == _EXPECTED_TOTALS
    assert sess["in_raw"] is True
    assert usage["by_agent"]["codex_cli"]["measured"] >= 1
    assert usage["totals"]["sum"] == sum(_EXPECTED_TOTALS.values())


def test_convert_codex_occupancy_only_omits_token_totals_and_usage(tmp_path: Path):
    """Empty / occupancy-only Codex sessions must not fabricate zeros."""
    store = tmp_path / "codex-sessions"
    store.mkdir()
    (store / "rollout-empty.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "type": "session_meta",
                        "timestamp": "2026-04-01T10:00:00.000Z",
                        "payload": {
                            "id": "sess-codex-empty",
                            "cwd": "/home/USER/demo-project",
                        },
                    }
                ),
                json.dumps(
                    {
                        "type": "response_item",
                        "timestamp": "2026-04-01T10:00:01.000Z",
                        "payload": {
                            "type": "message",
                            "role": "user",
                            "content": [{"type": "input_text", "text": "hi"}],
                        },
                    }
                ),
                json.dumps(
                    {
                        "type": "response_item",
                        "timestamp": "2026-04-01T10:00:02.000Z",
                        "payload": {
                            "type": "message",
                            "role": "assistant",
                            "content": [{"type": "output_text", "text": "yo"}],
                        },
                    }
                ),
                json.dumps(
                    {
                        "type": "event_msg",
                        "timestamp": "2026-04-01T10:00:02.500Z",
                        "payload": {
                            "type": "token_count",
                            "info": {"model_context_window": 200_000},
                            "rate_limits": {"primary": {"used_percent": 1.0}},
                        },
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    vault = tmp_path / "vault"
    out_dir = vault / "raw" / "sessions"
    out_dir.mkdir(parents=True)
    state = tmp_path / "state.json"
    cfg = _write_codex_config(tmp_path / "sessions_config.json", [store])

    discover_all()
    rc = convert_all(
        adapters=["codex_cli"],
        out_dir=out_dir,
        state_file=state,
        config_file=cfg,
        include_current=True,
        force=True,
    )
    assert rc == 0
    written = list(out_dir.glob("*.md"))
    assert len(written) == 1
    md = written[0].read_text(encoding="utf-8")
    assert "token_totals:" not in md
    assert "sess-codex-empty" in md

    usage = load_session_tokens(vault)
    assert "sess-codex-empty" not in usage.get("sessions", {})
    assert usage.get("totals", {}).get("sum", 0) == 0


def test_migrate_codex_raw_frontmatter_fills_usage_file(tmp_path: Path, monkeypatch):
    """migrate session-tokens picks up codex_cli from raw token_totals."""
    vault = tmp_path / "vault"
    sessions = vault / "raw" / "sessions"
    sessions.mkdir(parents=True)
    (sessions / "2026-04-01T10-00-demo-codex.md").write_text(
        "---\n"
        'title: "Codex demo"\n'
        "type: source\n"
        "tags: [codex-cli, session-transcript]\n"
        "date: 2026-04-01\n"
        "sessionId: sess-migrate-codex\n"
        "ended: 2026-04-01T12:00:00+00:00\n"
        'token_totals: {"input": 11, "cache_creation": 1, "cache_read": 2, "output": 3}\n'
        "---\n\n# Codex demo\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "llmwiki.migrate_session_tokens._backfill_capable_adapter",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "llmwiki.migrate_session_tokens._coverage_from_origins_and_raw",
        lambda sessions_dir, config, usage_data: (
            {"codex_cli": 1},
            {"codex_cli": "2026-04-01"},
        ),
    )
    report = run_migration(vault=vault, dry_run=False)
    assert report["errors"] == 0
    assert report["raw_upserts"] == 1
    data = load_session_tokens(vault)
    assert data["sessions"]["sess-migrate-codex"]["agent"] == "codex_cli"
    assert data["sessions"]["sess-migrate-codex"]["totals"]["input"] == 11
    assert data["by_agent"]["codex_cli"]["measured"] == 1


def test_migrate_adapters_filter_limits_origin_backfill(tmp_path: Path, monkeypatch):
    """``adapters=['codex_cli']`` must not walk Claude/Cursor origins (#324)."""
    vault = tmp_path / "vault"
    (vault / "raw" / "sessions").mkdir(parents=True)
    called: list[str] = []

    def _capture(vault, sessions_dir, adapter_name, **kwargs):
        called.append(adapter_name)

    monkeypatch.setattr(
        "llmwiki.migrate_session_tokens._backfill_capable_adapter",
        _capture,
    )
    monkeypatch.setattr(
        "llmwiki.migrate_session_tokens._coverage_from_origins_and_raw",
        lambda *a, **k: ({}, {}),
    )
    report = run_migration(
        vault=vault,
        dry_run=True,
        adapters=["codex_cli"],
        skip_raw=True,
    )
    assert called == ["codex_cli"]
    assert report["origin_adapters"] == ["codex_cli"]


def test_migrate_unknown_adapter_errors(tmp_path: Path, monkeypatch, capsys):
    """Explicit typo --adapter must fail closed, not silent no-op (#324 review)."""
    vault = tmp_path / "vault"
    (vault / "raw" / "sessions").mkdir(parents=True)
    called: list[str] = []

    monkeypatch.setattr(
        "llmwiki.migrate_session_tokens._backfill_capable_adapter",
        lambda *a, **k: called.append("ran"),
    )
    report = run_migration(
        vault=vault,
        dry_run=True,
        adapters=["codex"],
        skip_raw=True,
    )
    err = capsys.readouterr().err
    assert report["errors"] >= 1
    assert "migrate.session_tokens.unknown_adapter" in err
    assert called == []
