"""CLI tests for ``llmwiki synth --backend`` (#230 · R2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from llmwiki.cli import (
    SYNTH_BACKEND_CHOICES,
    build_parser,
    cmd_synthesize,
)


def _seed_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "raw" / "sessions").mkdir(parents=True)
    (vault / "raw" / "docs").mkdir(parents=True)
    (vault / "wiki" / "sources").mkdir(parents=True)
    (vault / "llmwiki-state.json").write_text("{}", encoding="utf-8")
    return vault


def test_synth_parser_accepts_backend_choices() -> None:
    for name in SYNTH_BACKEND_CHOICES:
        args = build_parser().parse_args(["synth", "--backend", name])
        assert args.backend == name
    args = build_parser().parse_args(["synth"])
    assert args.backend is None


def test_synth_parser_rejects_unknown_backend() -> None:
    with pytest.raises(SystemExit) as excinfo:
        build_parser().parse_args(["synth", "--backend", "nope"])
    assert excinfo.value.code == 2


def test_cmd_synthesize_backend_overrides_config_for_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    vault = _seed_vault(tmp_path)
    pinned = {"synthesis": {"backend": "dummy"}}
    seen: dict = {}

    class _Claude:
        name = "claude"

        def is_available(self) -> bool:
            return True

    def _resolve(cfg):
        seen["cfg"] = cfg
        return _Claude()

    monkeypatch.setattr("llmwiki.cli._load_sessions_config", lambda: pinned)
    monkeypatch.setattr("llmwiki.cli.resolve_backend", _resolve)

    args = build_parser().parse_args([
        "synth", "--check", "--backend", "claude", "--vault", str(vault),
    ])
    rc = cmd_synthesize(args)
    assert rc == 0
    assert seen["cfg"]["synthesis"]["backend"] == "claude"
    # Overlay must not mutate the loaded config dict (no config.json write path).
    assert pinned["synthesis"]["backend"] == "dummy"
    out = capsys.readouterr().out
    assert "Backend: claude" in out
    assert "Available: True" in out


def test_cmd_synthesize_backend_override_not_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    vault = _seed_vault(tmp_path)
    writes: list[Path] = []
    pinned = {"synthesis": {"backend": "ollama"}}

    class _Dummy:
        name = "dummy"

        def is_available(self) -> bool:
            return True

    monkeypatch.setattr("llmwiki.cli._load_sessions_config", lambda: pinned)
    monkeypatch.setattr(
        "llmwiki.cli.resolve_backend",
        lambda cfg: _Dummy() if cfg["synthesis"]["backend"] == "dummy" else None,
    )
    monkeypatch.setattr(
        "llmwiki.cli.synthesize_new_sessions",
        lambda **kwargs: {
            "total_scanned": 0,
            "new_files": 0,
            "synthesized": 0,
            "skipped": 0,
            "errors": [],
            "backend": "dummy",
        },
    )

    real_write = Path.write_text

    def _spy_write(self: Path, *a, **k):
        writes.append(self)
        return real_write(self, *a, **k)

    monkeypatch.setattr(Path, "write_text", _spy_write)

    args = build_parser().parse_args([
        "synth", "--backend", "dummy", "--sources-only", "--vault", str(vault),
    ])
    assert cmd_synthesize(args) == 0
    assert pinned["synthesis"]["backend"] == "ollama"
    assert not any(p.name == "config.json" for p in writes)


def test_estimate_uses_nested_cursor_cli_model_with_backend_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    vault = _seed_vault(tmp_path)
    # Use Cursor default model now on the rate card (#230).
    pinned = {
        "synthesis": {
            "backend": "dummy",
            "cursor_cli": {"model": "composer-2.5"},
            "claude": {"model": "haiku"},
        },
    }
    monkeypatch.setattr("llmwiki.cli._load_sessions_config", lambda: pinned)
    monkeypatch.setattr("llmwiki.synth.pipeline._discover_raw_sessions", lambda raw_dir=None: [])
    monkeypatch.setattr("llmwiki.synth.pipeline._load_state", lambda _p=None: {})
    monkeypatch.setattr("llmwiki.cli._discover_raw_sessions", lambda raw_dir=None: [])
    monkeypatch.setattr("llmwiki.cli._load_state", lambda _p=None: {})

    args = build_parser().parse_args([
        "synth", "--estimate", "--backend", "cursor_cli", "--vault", str(vault),
    ])
    rc = cmd_synthesize(args)
    out = capsys.readouterr().out
    assert rc == 0
    assert "Execution model: composer-2.5" in out
    assert pinned["synthesis"]["backend"] == "dummy"


def test_estimate_uses_nested_claude_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    vault = _seed_vault(tmp_path)
    pinned = {
        "synthesis": {
            "backend": "claude",
            "claude": {"model": "haiku"},
            "claude_model": "sonnet",  # nested wins
        },
    }
    monkeypatch.setattr("llmwiki.cli._load_sessions_config", lambda: pinned)
    monkeypatch.setattr("llmwiki.cli._discover_raw_sessions", lambda raw_dir=None: [])
    monkeypatch.setattr("llmwiki.cli._load_state", lambda _p=None: {})

    args = build_parser().parse_args([
        "synth", "--estimate", "--vault", str(vault),
    ])
    rc = cmd_synthesize(args)
    out = capsys.readouterr().out
    assert rc == 0
    assert "Execution model: haiku" in out


def test_estimate_falls_back_to_flat_claude_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    vault = _seed_vault(tmp_path)
    pinned = {"synthesis": {"backend": "claude", "claude_model": "sonnet"}}
    monkeypatch.setattr("llmwiki.cli._load_sessions_config", lambda: pinned)
    monkeypatch.setattr("llmwiki.cli._discover_raw_sessions", lambda raw_dir=None: [])
    monkeypatch.setattr("llmwiki.cli._load_state", lambda _p=None: {})

    args = build_parser().parse_args([
        "synth", "--estimate", "--vault", str(vault),
    ])
    rc = cmd_synthesize(args)
    out = capsys.readouterr().out
    assert rc == 0
    assert "Execution model: sonnet" in out
