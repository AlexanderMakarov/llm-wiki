"""Shared synthesis-backend contracts (#230) — parametrized across engines.

Backend-specific transport (Claude lean/JSON, Cursor allowlist/PATH probe,
Ollama HTTP retries) stays in the per-backend test modules. This file covers
resolve_backend wiring, shared-timeout isolation, CLI ``--backend`` overlay,
and overview soft-fail / skip behaviour that must stay identical.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from llmwiki.build import synthesize_overview
from llmwiki.cli import SYNTH_BACKEND_CHOICES, build_parser, cmd_synthesize
from llmwiki.synth.base import DummySynthesizer
from llmwiki.synth.claude_cli import (
    DEFAULT_CLAUDE_TIMEOUT,
    ClaudeCLISynthesizer,
    load_claude_config,
)
from llmwiki.synth.cursor_cli import (
    DEFAULT_CURSOR_TIMEOUT,
    CursorCLIError,
    CursorCLISynthesizer,
    load_cursor_cli_config,
)
from llmwiki.synth.ollama import OllamaSynthesizer
from llmwiki.synth.pipeline import resolve_backend


def _seed_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "raw" / "sessions").mkdir(parents=True)
    (vault / "raw" / "docs").mkdir(parents=True)
    (vault / "wiki" / "sources").mkdir(parents=True)
    (vault / "llmwiki-state.json").write_text("{}", encoding="utf-8")
    return vault


@dataclass(frozen=True)
class _ResolveCase:
    id: str
    config: dict[str, Any]
    expected_type: type
    expected_name: str
    model: str | None = None
    timeout: int | None = None


RESOLVE_CASES = [
    _ResolveCase("dummy_empty", {}, DummySynthesizer, "DummySynthesizer"),
    _ResolveCase(
        "dummy_explicit",
        {"synthesis": {"backend": "dummy"}},
        DummySynthesizer,
        "DummySynthesizer",
    ),
    _ResolveCase(
        "claude_nested",
        {
            "synthesis": {
                "backend": "claude",
                "claude": {"model": "nested-haiku", "timeout": 91},
                "claude_model": "flat-sonnet",
            }
        },
        ClaudeCLISynthesizer,
        "claude-cli",
        model="nested-haiku",
        timeout=91,
    ),
    _ResolveCase(
        "cursor_cli_defaults",
        {"synthesis": {"backend": "cursor_cli"}},
        CursorCLISynthesizer,
        "cursor-cli",
        model="composer-2.5",
        timeout=180,
    ),
    _ResolveCase(
        "cursor_cli_nested",
        {
            "synthesis": {
                "backend": "cursor_cli",
                "cursor_cli": {"model": "composer-2.5-fast", "timeout": 88},
            }
        },
        CursorCLISynthesizer,
        "cursor-cli",
        model="composer-2.5-fast",
        timeout=88,
    ),
    _ResolveCase(
        "ollama",
        {"synthesis": {"backend": "ollama", "ollama": {"model": "llama3.2"}}},
        OllamaSynthesizer,
        "OllamaSynthesizer",
        model="llama3.2",
    ),
]


@pytest.mark.parametrize("case", RESOLVE_CASES, ids=lambda c: c.id)
def test_resolve_backend_wiring(case: _ResolveCase) -> None:
    backend = resolve_backend(case.config)
    assert isinstance(backend, case.expected_type)
    assert backend.name == case.expected_name
    if case.model is not None:
        if isinstance(backend, OllamaSynthesizer):
            assert backend.config.model == case.model
        else:
            assert backend.model == case.model
    if case.timeout is not None:
        if isinstance(backend, OllamaSynthesizer):
            assert backend.config.timeout == case.timeout
        else:
            assert backend.timeout == case.timeout


@pytest.mark.parametrize(
    "bad_name",
    ["nope", "agent", "AGENT_DELEGATE"],
)
def test_resolve_backend_unknown_falls_back_to_dummy(
    bad_name: str, caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level("WARNING"):
        backend = resolve_backend({"synthesis": {"backend": bad_name}})
    assert isinstance(backend, DummySynthesizer)
    assert any(
        "Unknown synthesis.backend" in r.message for r in caplog.records
    )


@pytest.mark.parametrize(
    ("loader", "default_timeout"),
    [
        (load_claude_config, DEFAULT_CLAUDE_TIMEOUT),
        (load_cursor_cli_config, DEFAULT_CURSOR_TIMEOUT),
    ],
    ids=["claude", "cursor_cli"],
)
def test_cli_backends_ignore_shared_ollama_timeout(loader, default_timeout: int) -> None:
    cfg = loader({"synthesis": {"backend": "x", "timeout": 60}})
    assert cfg.timeout == default_timeout


def test_synth_parser_accepts_all_backend_choices() -> None:
    for name in SYNTH_BACKEND_CHOICES:
        args = build_parser().parse_args(["synth", "--backend", name])
        assert args.backend == name
    assert build_parser().parse_args(["synth"]).backend is None


def test_synth_parser_rejects_unknown_backend() -> None:
    with pytest.raises(SystemExit) as excinfo:
        build_parser().parse_args(["synth", "--backend", "nope"])
    assert excinfo.value.code == 2


@pytest.mark.parametrize("override", ["claude", "cursor_cli", "dummy", "ollama"])
def test_cli_backend_overlay_does_not_mutate_config(
    override: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    vault = _seed_vault(tmp_path)
    pinned = {"synthesis": {"backend": "dummy" if override != "dummy" else "ollama"}}
    seen: dict[str, Any] = {}

    class _Stub:
        name = override

        def is_available(self) -> bool:
            return True

    def _resolve(cfg: dict[str, Any]):
        seen["cfg"] = cfg
        return _Stub()

    monkeypatch.setattr("llmwiki.cli._load_sessions_config", lambda: pinned)
    monkeypatch.setattr("llmwiki.cli.resolve_backend", _resolve)

    args = build_parser().parse_args([
        "synth", "--check", "--backend", override, "--vault", str(vault),
    ])
    rc = cmd_synthesize(args)
    assert rc == 0
    assert seen["cfg"]["synthesis"]["backend"] == override
    assert pinned["synthesis"]["backend"] != override or override == "dummy"
    # When override == dummy and pinned was ollama, pinned stays ollama.
    if override != "dummy":
        assert pinned["synthesis"]["backend"] == "dummy"
    else:
        assert pinned["synthesis"]["backend"] == "ollama"
    out = capsys.readouterr().out
    assert f"Backend: {override}" in out
    assert "Available: True" in out


@pytest.mark.parametrize(
    ("backend_key", "nested", "expected_model"),
    [
        ("cursor_cli", {"cursor_cli": {"model": "composer-2.5"}}, "composer-2.5"),
        ("claude", {"claude": {"model": "haiku"}, "claude_model": "sonnet"}, "haiku"),
        ("claude", {"claude_model": "sonnet"}, "sonnet"),
    ],
    ids=["cursor_nested", "claude_nested_wins", "claude_flat"],
)
def test_estimate_honors_backend_model_resolution(
    backend_key: str,
    nested: dict[str, Any],
    expected_model: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    vault = _seed_vault(tmp_path)
    pinned = {"synthesis": {"backend": "dummy", **nested}}
    monkeypatch.setattr("llmwiki.cli._load_sessions_config", lambda: pinned)
    monkeypatch.setattr("llmwiki.cli._discover_raw_sessions", lambda raw_dir=None: [])
    monkeypatch.setattr("llmwiki.cli._load_state", lambda _p=None: {})
    monkeypatch.setattr("llmwiki.synth.pipeline._discover_raw_sessions", lambda raw_dir=None: [])
    monkeypatch.setattr("llmwiki.synth.pipeline._load_state", lambda _p=None: {})

    args = build_parser().parse_args([
        "synth", "--estimate", "--backend", backend_key, "--vault", str(vault),
    ])
    rc = cmd_synthesize(args)
    out = capsys.readouterr().out
    assert rc == 0
    assert pinned["synthesis"]["backend"] == "dummy"
    assert f"Execution model: {expected_model}" in out


def test_overview_dummy_skips_llm(capsys: pytest.CaptureFixture[str]) -> None:
    groups = {"demo": [(Path("/raw/x.md"), {"slug": "x"}, "")]}
    with patch.object(DummySynthesizer, "overview_completion") as complete:
        out = synthesize_overview(groups, synthesizer=DummySynthesizer())
    assert out is None
    complete.assert_not_called()
    assert "skipping overview LLM" in capsys.readouterr().out


@pytest.mark.parametrize(
    "backend_factory",
    [
        lambda: ClaudeCLISynthesizer(claude_path="/usr/bin/claude"),
        lambda: CursorCLISynthesizer(model="composer-2.5", timeout=60),
    ],
    ids=["claude", "cursor_cli"],
)
def test_overview_calls_overview_completion(backend_factory) -> None:
    groups = {"demo": [(Path("/raw/x.md"), {"slug": "ok-slug"}, "")]}
    backend = backend_factory()
    with patch.object(
        backend, "overview_completion", return_value="overview text"
    ) as complete:
        out = synthesize_overview(groups, synthesizer=backend)
    assert out == "overview text"
    complete.assert_called_once()
    assert "Data:" in complete.call_args.args[0]


def test_overview_soft_fails_when_completion_raises(
    capsys: pytest.CaptureFixture[str],
) -> None:
    groups = {"demo": [(Path("/raw/x.md"), {"slug": "ok"}, "")]}
    backend = CursorCLISynthesizer(model="composer-2.5", timeout=60)
    with patch.object(
        backend, "overview_completion", side_effect=CursorCLIError("boom")
    ):
        out = synthesize_overview(groups, synthesizer=backend)
    assert out is None
    assert "boom" in capsys.readouterr().err


def test_cursor_overview_completion_uses_run_prompt() -> None:
    """Cursor overview transport is ``run_prompt`` with a 120s cap."""
    backend = CursorCLISynthesizer(model="composer-2.5", timeout=180)
    with patch.object(backend, "run_prompt", return_value="ok") as run:
        assert backend.overview_completion("hello") == "ok"
    run.assert_called_once_with("hello", timeout=120.0)
