"""Shared synthesis-backend contracts (#230) — parametrized across engines.

Backend-specific transport (Claude lean/JSON, Cursor allowlist/PATH probe, Ollama HTTP retries) stays in the per-backend test modules. This file covers resolve_backend wiring, shared-timeout isolation, overview soft-fail / skip behaviour, and the usable-body budget API (#311 / @spec: 324-whole-document-storage). CLI ``synth --backend`` handler tests live in ``tests/cli/test_synth.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from llmwiki.build import synthesize_overview
from llmwiki.synth.base import (
    CAPPED_USABLE_BODY_CHARS,
    DUMMY_USABLE_BODY_CHARS,
    DummySynthesizer,
)
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


# ─── usable_body_chars budget (#311) ───────────────────────────────────


@pytest.mark.parametrize(
    "backend_factory",
    [
        lambda: ClaudeCLISynthesizer(claude_path="/usr/bin/claude"),
        lambda: CursorCLISynthesizer(model="composer-2.5"),
        lambda: OllamaSynthesizer(),
    ],
    ids=["claude_cli", "cursor_cli", "ollama"],
)
def test_capped_backends_report_finite_positive_usable_body_budget(
    backend_factory,
) -> None:
    """Claude / Cursor / Ollama expose a finite positive body budget under ~8k."""
    budget = backend_factory().usable_body_chars()
    assert budget == CAPPED_USABLE_BODY_CHARS
    assert 0 < budget < 8000
    assert budget == 8000 - 1000  # envelope minus prompt/meta overhead


def test_dummy_usable_body_budget_covers_multi_section_fixtures() -> None:
    """Dummy budget is large enough that multi-section fixtures fit in one call."""
    budget = DummySynthesizer().usable_body_chars()
    assert budget == DUMMY_USABLE_BODY_CHARS
    # Multi-section fixtures in the suite are tens of KB, not millions.
    assert budget >= 100_000
    assert budget > CAPPED_USABLE_BODY_CHARS * 100
