"""Whole-feature acceptance tests for #230: Cursor Agent CLI synthesis backend.

# @layer: integration
# @spec: 226-cursor-cli-synth-backend
# @regression

Slice-level unit tests live in ``test_synth_cursor_cli.py``, ``test_synth_backend_cli.py``,
``test_synthesize_overview_safety.py``, and ``test_cache.py``. This module exercises the
cross-cutting acceptance criteria from ``functional-spec.md`` through the CLI entry point
and the shared backend resolution paths, with ``subprocess`` mocked — no live Cursor.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from llmwiki.build import synthesize_overview
from llmwiki.cache import MODEL_PRICING, resolve_pricing_model
from llmwiki.cli import build_parser, cmd_synthesize
from llmwiki.synth.base import DummySynthesizer
from llmwiki.synth.cursor_cli import (
    DEFAULT_CURSOR_MODEL,
    DEFAULT_CURSOR_TIMEOUT,
    CursorCLISynthesizer,
    lean_argv,
    load_cursor_cli_config,
    resolve_cursor_agent_path,
)
from llmwiki.synth.pipeline import resolve_backend

_DOC = """---
title: "Acceptance fixture"
slug: cursor-accept
project: demo
---

# Fixture

Body for cursor_cli acceptance synth.
"""

_CURSOR_PAGE = "## Summary\n\nCursor-synthesized acceptance page.\n"


def _completed(
    *,
    returncode: int = 0,
    stdout: str = _CURSOR_PAGE,
    stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["agent"], returncode=returncode, stdout=stdout, stderr=stderr
    )


def _seed_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "raw" / "docs").mkdir(parents=True)
    (vault / "wiki" / "sources").mkdir(parents=True)
    (vault / "llmwiki-state.json").write_text("{}", encoding="utf-8")
    (vault / "raw" / "docs" / "cursor-accept.md").write_text(_DOC, encoding="utf-8")
    return vault


def _mock_agent_run(*, probe_ok: bool = True, page: str = _CURSOR_PAGE):
    """Return a subprocess.run side_effect: probe then synth pages."""

    def _side_effect(*_args, **kwargs):
        prompt = kwargs.get("input") or ""
        if "Reply with exactly: OK" in prompt:
            if not probe_ok:
                return _completed(returncode=1, stdout="", stderr="auth failed")
            return _completed(stdout="OK\n")
        return _completed(stdout=page)

    return _side_effect


def test_shipped_default_backend_remains_dummy() -> None:  # @regression
    """R1: unchanged install keeps dummy as the default synthesis backend."""
    backend = resolve_backend({})
    assert isinstance(backend, DummySynthesizer)


def test_resolve_backend_cursor_cli_reads_nested_config() -> None:  # @regression
    """R1/R3: ``cursor_cli`` resolves from ``synthesis.cursor_cli`` nested block."""
    backend = resolve_backend({
        "synthesis": {
            "backend": "cursor_cli",
            "cursor_cli": {"model": "composer-2.5-fast", "timeout": 99},
        },
    })
    assert isinstance(backend, CursorCLISynthesizer)
    assert backend.model == "composer-2.5-fast"
    assert backend.timeout == 99


def test_nested_config_defaults_to_cheapest_composer() -> None:  # @regression
    """R3: default model is ``composer-2.5``, timeout matches Claude-scale default."""
    cfg = load_cursor_cli_config({"synthesis": {"backend": "cursor_cli"}})
    assert cfg.model == DEFAULT_CURSOR_MODEL
    assert cfg.model == "composer-2.5"
    assert cfg.timeout == DEFAULT_CURSOR_TIMEOUT


def test_lean_argv_is_non_interactive_and_has_no_worktree_flags() -> None:  # @regression
    """R3/R4: lean invocation uses ask + sandbox + tiny allowlist; no force/yolo/worktree."""
    argv = lean_argv("/bin/agent", model="composer-2.5")
    assert argv[0] == "/bin/agent"
    assert "-p" in argv
    assert argv[argv.index("--mode") + 1] == "ask"
    assert argv[argv.index("--sandbox") + 1] == "enabled"
    assert argv[argv.index("--allowed-tools") + 1] == "truncated_tool_call"
    assert argv[argv.index("--model") + 1] == "composer-2.5"
    forbidden = ("--force", "--yolo", "--approve-mcps", "--worktree")
    for flag in forbidden:
        assert flag not in argv


def test_cli_synth_cursor_cli_writes_real_source_page(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:  # @regression
    """R1/R4: ``--backend cursor_cli`` synthesizes a real page via mocked Agent CLI."""
    vault = _seed_vault(tmp_path)
    pinned = {"synthesis": {"backend": "dummy", "cursor_cli": {"model": "composer-2.5"}}}
    monkeypatch.setattr("llmwiki.cli._load_sessions_config", lambda: pinned)

    with patch(
        "llmwiki.synth.cursor_cli.resolve_cursor_agent_path",
        return_value="/bin/agent",
    ), patch(
        "llmwiki.synth.cursor_cli.subprocess.run",
        side_effect=_mock_agent_run(),
    ):
        args = build_parser().parse_args([
            "synth",
            "--backend", "cursor_cli",
            "--sources-only",
            "--vault", str(vault),
        ])
        rc = cmd_synthesize(args)

    assert rc == 0
    assert pinned["synthesis"]["backend"] == "dummy"
    pages = list((vault / "wiki" / "sources").rglob("*.md"))
    assert len(pages) == 1
    text = pages[0].read_text(encoding="utf-8")
    assert "Cursor-synthesized acceptance page" in text
    assert "This page is a placeholder" not in text


def test_cli_backend_overlay_honored_on_check_without_mutating_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:  # @regression
    """R2: ``--backend cursor_cli`` overlays config for ``--check`` only."""
    vault = _seed_vault(tmp_path)
    pinned = {"synthesis": {"backend": "dummy"}}
    monkeypatch.setattr("llmwiki.cli._load_sessions_config", lambda: pinned)

    with patch(
        "llmwiki.synth.cursor_cli.resolve_cursor_agent_path",
        return_value="/bin/agent",
    ), patch(
        "llmwiki.synth.cursor_cli.subprocess.run",
        side_effect=_mock_agent_run(),
    ):
        args = build_parser().parse_args([
            "synth", "--check", "--backend", "cursor_cli", "--vault", str(vault),
        ])
        rc = cmd_synthesize(args)

    out = capsys.readouterr().out
    assert rc == 0
    assert pinned["synthesis"]["backend"] == "dummy"
    assert "Backend: cursor-cli" in out
    assert "Available: True" in out


def test_cli_rejects_unknown_backend() -> None:  # @regression
    """R2 negative: unknown ``--backend`` is rejected at parse time (exit 2)."""
    with pytest.raises(SystemExit) as excinfo:
        build_parser().parse_args(["synth", "--backend", "surprise-engine"])
    assert excinfo.value.code == 2


def test_cli_unavailable_cursor_cli_fails_without_failover(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:  # @regression
    """R2/R5 negative: probe failure exits 1 — no silent fallback to dummy."""
    vault = _seed_vault(tmp_path)
    pinned = {"synthesis": {"backend": "cursor_cli"}}
    monkeypatch.setattr("llmwiki.cli._load_sessions_config", lambda: pinned)

    with patch(
        "llmwiki.synth.cursor_cli.resolve_cursor_agent_path",
        return_value="/bin/agent",
    ), patch(
        "llmwiki.synth.cursor_cli.subprocess.run",
        side_effect=_mock_agent_run(probe_ok=False),
    ):
        args = build_parser().parse_args([
            "synth", "--sources-only", "--vault", str(vault),
        ])
        rc = cmd_synthesize(args)

    err = capsys.readouterr().err
    assert rc == 1
    assert "not available" in err
    assert not list((vault / "wiki" / "sources").rglob("*.md"))


def test_check_requires_successful_probe_not_binary_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:  # @regression
    """R5: binary on PATH alone is insufficient — auth/probe failure fails ``--check``."""
    vault = _seed_vault(tmp_path)
    monkeypatch.setattr(
        "llmwiki.cli._load_sessions_config",
        lambda: {"synthesis": {"backend": "cursor_cli"}},
    )

    with patch(
        "llmwiki.synth.cursor_cli.resolve_cursor_agent_path",
        return_value="/bin/agent",
    ), patch(
        "llmwiki.synth.cursor_cli.subprocess.run",
        return_value=_completed(returncode=1, stderr="not logged in"),
    ):
        args = build_parser().parse_args(["synth", "--check", "--vault", str(vault)])
        rc = cmd_synthesize(args)

    out = capsys.readouterr().out
    assert rc == 1
    assert "Available: False" in out


def test_cli_estimate_honors_backend_override_and_nested_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:  # @regression
    """R2/R7: ``--estimate --backend cursor_cli`` reads nested model and shows cost."""
    vault = _seed_vault(tmp_path)
    pinned = {
        "synthesis": {
            "backend": "dummy",
            "cursor_cli": {"model": "composer-2.5"},
        },
    }
    monkeypatch.setattr("llmwiki.cli._load_sessions_config", lambda: pinned)
    monkeypatch.setattr("llmwiki.cli._discover_raw_sessions", lambda raw_dir=None: [])
    monkeypatch.setattr("llmwiki.cli._load_state", lambda _p=None: {})

    args = build_parser().parse_args([
        "synth", "--estimate", "--backend", "cursor_cli", "--vault", str(vault),
    ])
    rc = cmd_synthesize(args)
    out = capsys.readouterr().out

    assert rc == 0
    assert pinned["synthesis"]["backend"] == "dummy"
    assert "Execution model: composer-2.5" in out
    assert "$" in out


@pytest.mark.parametrize(
    ("alias", "canonical"),
    [
        ("composer", "composer-2.5"),
        ("composer-2.5-fast", "composer-2.5-fast"),
        ("cursor-grok-4.6-high", "grok-4.6"),
        ("grok-4.5-fast", "grok-4.5-fast"),
    ],
)
def test_cursor_pricing_aliases_on_packaged_rate_card(alias: str, canonical: str) -> None:  # @regression
    """R7: Cursor model ids and aliases resolve on ``model_pricing.csv``."""
    resolved = resolve_pricing_model(alias)
    assert resolved == canonical
    assert canonical in MODEL_PRICING
    rates = MODEL_PRICING[canonical]
    assert rates["input"] > 0
    assert rates["output"] > 0


def test_overview_dummy_backend_skips_llm_spend(capsys: pytest.CaptureFixture[str]) -> None:  # @regression
    """R4b: dummy backend never shells out for site overview."""
    groups = {"demo": [(Path("/raw/x.md"), {"slug": "x"}, "")]}
    out = synthesize_overview(groups, config={"synthesis": {"backend": "dummy"}})
    assert out is None
    assert "skipping overview LLM" in capsys.readouterr().out


def test_overview_follows_cursor_cli_backend() -> None:  # @regression
    """R4b: overview uses the active ``cursor_cli`` backend (mocked subprocess)."""
    groups = {"demo": [(Path("/raw/x.md"), {"slug": "x"}, "")]}
    backend = CursorCLISynthesizer(model="composer-2.5", timeout=60)

    with patch.object(
        backend,
        "run_prompt",
        return_value="overview from cursor",
    ) as run:
        out = synthesize_overview(groups, synthesizer=backend)

    assert out == "overview from cursor"
    run.assert_called_once()
    lean = lean_argv("/bin/agent", model="composer-2.5")
    assert "-p" in lean
    assert "--mode" in lean


def test_path_resolution_prefers_agent_binary() -> None:  # @regression
    """R3: Cursor binary comes from PATH only — ``agent`` before ``cursor-agent``."""
    with patch("llmwiki.synth.cursor_cli.shutil.which") as which:
        which.side_effect = lambda name: {
            "agent": "/usr/bin/agent",
            "cursor-agent": "/usr/bin/cursor-agent",
        }.get(name)
        assert resolve_cursor_agent_path() == "/usr/bin/agent"
