"""Usable body budget for whole-document chunking (#311, review N1).

Spec: ``context/spec/324-whole-document-storage/``. A backend's budget is how
many raw-body characters ONE document-chunk call can carry. Resolution order:

1. ``synthesis.<backend>.usable_body_chars`` (explicit characters)
2. ``synthesis.<backend>.context_window_tokens`` (converted conservatively)
3. the backend's own knowledge — Claude / Cursor alias tables, Ollama's ``/api/show``
4. the assumed window: ``ASSUMED_AGENT_WINDOW_TOKENS`` (200k) for Claude and
   Cursor, ``DEFAULT_CONTEXT_WINDOW_TOKENS`` (8192) for Ollama / generic

A derived budget is ``(window - scaffolding - prompt reserve - output reserve -
working margin) * 2.05`` with scaffolding and margin set by the backend class
(Ollama / Claude lean / Claude non-lean and Cursor CLI). The 1,000-character
floor applies only to what the operator sized tiny (explicit ``usable_body_chars``
or a configured ``context_window_tokens``); a derived default that cannot carry
the reserves warns and clamps to the 8,000-character session cap (agents).

Session / evidence bodies are NOT governed by it: they keep the historical
8,000-character send cap.
"""

from __future__ import annotations

import json
import logging
import stat
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from llmwiki.cli import _estimate_backend
from llmwiki.state_store import read_state
from llmwiki.synth.base import (
    ASSUMED_AGENT_WINDOW_TOKENS,
    BODY_CHARS_PER_TOKEN,
    CLAUDE_LEAN_BUDGET,
    DEFAULT_CONTEXT_WINDOW_TOKENS,
    DEFAULT_USABLE_BODY_CHARS,
    FULL_AGENT_OVERHEAD_TOKENS,
    GENERIC_BUDGET,
    HEAVY_AGENT_BUDGET,
    LEAN_OVERHEAD_TOKENS,
    MIN_USABLE_BODY_CHARS,
    OLLAMA_BUDGET,
    OUTPUT_RESERVE_TOKENS,
    PROMPT_RESERVE_TOKENS,
    SESSION_BODY_SEND_CAP_CHARS,
    BaseSynthesizer,
    BodyBudgetConfig,
    BudgetClass,
    load_body_budget_config,
    page_timeout_seconds,
    resolve_usable_body_chars,
    usable_body_chars_for_window,
    window_tokens_for_body_chars,
)
from llmwiki.synth.claude_cli import ClaudeCLISynthesizer, known_claude_context_window
from llmwiki.synth.cursor_cli import CursorCLISynthesizer, known_cursor_context_window
from llmwiki.synth.estimate import synthesize_estimate_report
from llmwiki.synth.ollama import OllamaConfig, OllamaSynthesizer, load_ollama_config
from llmwiki.synth.pipeline import refresh_synth_pending, resolve_backend, synthesize_new_sessions

TEMPLATE = "Summarize:\n{body}\nMeta:\n{meta}\n"


def _window_chars(
    tokens: int, scaffolding: int = 0, margin_floor: int = 0, margin_percent: int = 0
) -> int:
    """The locked formula, spelled out independently of ``BudgetClass``."""
    margin = max(margin_floor, tokens * margin_percent // 100)
    usable = tokens - scaffolding - PROMPT_RESERVE_TOKENS - OUTPUT_RESERVE_TOKENS - margin
    return max(1000, int(round(usable * BODY_CHARS_PER_TOKEN, 6)))  # truncate: never over-promise a char


def _ollama_chars(tokens: int) -> int:
    return _window_chars(tokens, 500, 2048, 10)


def _claude_lean_chars(tokens: int) -> int:
    return _window_chars(tokens, LEAN_OVERHEAD_TOKENS, 8192, 25)


def _heavy_chars(tokens: int) -> int:
    return _window_chars(tokens, FULL_AGENT_OVERHEAD_TOKENS, 16_384, 35)


# ─── formula ───────────────────────────────────────────────────────────


def test_backend_classes_carry_the_locked_scaffolding_and_margin() -> None:
    assert (OLLAMA_BUDGET.scaffolding_tokens, OLLAMA_BUDGET.margin_floor_tokens, OLLAMA_BUDGET.margin_percent) == (
        500,
        2048,
        10,
    )
    assert (
        CLAUDE_LEAN_BUDGET.scaffolding_tokens,
        CLAUDE_LEAN_BUDGET.margin_floor_tokens,
        CLAUDE_LEAN_BUDGET.margin_percent,
    ) == (890, 8192, 25)
    assert (
        HEAVY_AGENT_BUDGET.scaffolding_tokens,
        HEAVY_AGENT_BUDGET.margin_floor_tokens,
        HEAVY_AGENT_BUDGET.margin_percent,
    ) == (35_000, 16_384, 35)
    assert (PROMPT_RESERVE_TOKENS, OUTPUT_RESERVE_TOKENS, BODY_CHARS_PER_TOKEN) == (2000, 2600, 2.05)


@pytest.mark.parametrize(
    ("window", "ollama", "lean", "heavy"),
    [
        # 8k: Ollama keeps a small budget; both Claude classes bottom out at the floor.
        (8192, 2140, 1000, 1000),
        # 32k: the heavy agent scaffolding (35k) exceeds the window — floor.
        (32_768, 50_003, 39_126, 1000),
        # 200k: the margin is a percentage of the window.
        (200_000, 358_545, 296_245, 185_320),
    ],
)
def test_budget_examples_per_backend_class(window: int, ollama: int, lean: int, heavy: int) -> None:
    assert usable_body_chars_for_window(window, OLLAMA_BUDGET) == ollama == _ollama_chars(window)
    assert usable_body_chars_for_window(window, CLAUDE_LEAN_BUDGET) == lean == _claude_lean_chars(window)
    assert usable_body_chars_for_window(window, HEAVY_AGENT_BUDGET) == heavy == _heavy_chars(window)


def test_working_margin_is_the_larger_of_floor_and_percentage_of_window() -> None:
    assert CLAUDE_LEAN_BUDGET.working_margin(8192) == 8192  # floor wins
    assert CLAUDE_LEAN_BUDGET.working_margin(200_000) == 50_000  # 25% wins
    assert HEAVY_AGENT_BUDGET.working_margin(200_000) == 70_000
    assert OLLAMA_BUDGET.working_margin(8192) == 2048
    assert OLLAMA_BUDGET.working_margin(200_000) == 20_000


def test_generic_class_is_the_bare_prompt_and_output_reserve() -> None:
    assert usable_body_chars_for_window(8192) == _window_chars(8192)
    assert usable_body_chars_for_window(200_000) == _window_chars(200_000)
    assert usable_body_chars_for_window(32_768) > usable_body_chars_for_window(16_384)


def test_agent_overhead_lowers_the_budget_in_every_derived_window() -> None:
    for window in (50_000, 200_000, 1_000_000):
        generic = usable_body_chars_for_window(window, GENERIC_BUDGET)
        ollama = usable_body_chars_for_window(window, OLLAMA_BUDGET)
        lean = usable_body_chars_for_window(window, CLAUDE_LEAN_BUDGET)
        heavy = usable_body_chars_for_window(window, HEAVY_AGENT_BUDGET)
        assert generic > ollama > heavy
        assert generic > lean > heavy


def test_derived_budget_has_no_hard_cap() -> None:
    """No 64 KiB (or any other) ceiling: a huge window yields a huge budget."""
    assert usable_body_chars_for_window(1_000_000, CLAUDE_LEAN_BUDGET) > 64 * 1024 * 10
    assert usable_body_chars_for_window(1_000_000, HEAVY_AGENT_BUDGET) == _heavy_chars(1_000_000)


@pytest.mark.parametrize("budget_class", [GENERIC_BUDGET, OLLAMA_BUDGET, CLAUDE_LEAN_BUDGET, HEAVY_AGENT_BUDGET])
def test_budget_never_drops_below_the_floor_however_small_the_window(budget_class: BudgetClass) -> None:
    assert usable_body_chars_for_window(1, budget_class) == MIN_USABLE_BODY_CHARS
    assert usable_body_chars_for_window(0, budget_class) == MIN_USABLE_BODY_CHARS


@pytest.mark.parametrize("budget_class", [OLLAMA_BUDGET, CLAUDE_LEAN_BUDGET, HEAVY_AGENT_BUDGET])
@pytest.mark.parametrize("chars", [1000, 7000, 30_000, 100_000, 400_000, 2_000_000])
def test_window_for_body_chars_is_the_smallest_window_that_holds_it(budget_class: BudgetClass, chars: int) -> None:
    window = window_tokens_for_body_chars(chars, budget_class)
    assert usable_body_chars_for_window(window, budget_class) >= chars
    if chars > MIN_USABLE_BODY_CHARS:
        assert usable_body_chars_for_window(window - 1, budget_class) < chars


def test_default_budget_is_derived_from_the_default_window_not_typed() -> None:
    assert DEFAULT_USABLE_BODY_CHARS == usable_body_chars_for_window(DEFAULT_CONTEXT_WINDOW_TOKENS)


# ─── config parsing ────────────────────────────────────────────────────


def test_load_body_budget_config_reads_both_keys() -> None:
    cfg = load_body_budget_config({"usable_body_chars": 9000, "context_window_tokens": "32768"}, "claude")
    assert cfg == BodyBudgetConfig(usable_body_chars=9000, context_window_tokens=32768)


@pytest.mark.parametrize("bad", [0, -5, "many", True, 1.5e-9])
def test_unusable_values_warn_and_are_ignored(bad: Any, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="llmwiki.synth.base"):
        cfg = load_body_budget_config({"usable_body_chars": bad, "context_window_tokens": bad}, "ollama")
    assert cfg == BodyBudgetConfig()
    assert "synthesis.ollama.usable_body_chars" in caplog.text
    assert "synthesis.ollama.context_window_tokens" in caplog.text


def test_missing_keys_are_silent(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="llmwiki.synth.base"):
        assert load_body_budget_config({}, "claude") == BodyBudgetConfig()
        assert load_body_budget_config(None, "claude") == BodyBudgetConfig()
    assert caplog.text == ""


# ─── resolution order ──────────────────────────────────────────────────


def test_resolution_order_explicit_chars_then_config_window_then_known_then_default() -> None:
    def known() -> int:
        return 16_384

    both = BodyBudgetConfig(usable_body_chars=12_345, context_window_tokens=100_000)
    assert resolve_usable_body_chars(both, known_window_tokens=known) == 12_345
    window = BodyBudgetConfig(context_window_tokens=100_000)
    assert resolve_usable_body_chars(window, known_window_tokens=known) == _window_chars(100_000)
    assert resolve_usable_body_chars(BodyBudgetConfig(), known_window_tokens=known) == _window_chars(16_384)
    assert resolve_usable_body_chars(BodyBudgetConfig(), known_window_tokens=lambda: None) == DEFAULT_USABLE_BODY_CHARS
    assert resolve_usable_body_chars(BodyBudgetConfig()) == DEFAULT_USABLE_BODY_CHARS


def test_resolution_applies_the_backend_class_to_derived_budgets_only() -> None:
    explicit = BodyBudgetConfig(usable_body_chars=12_345)
    assert resolve_usable_body_chars(explicit, budget_class=HEAVY_AGENT_BUDGET) == 12_345
    window = BodyBudgetConfig(context_window_tokens=200_000)
    assert resolve_usable_body_chars(window, budget_class=HEAVY_AGENT_BUDGET) == _heavy_chars(200_000)
    assert resolve_usable_body_chars(BodyBudgetConfig(), budget_class=HEAVY_AGENT_BUDGET) == 1000


def _cfg(backend: str, **block: Any) -> dict[str, Any]:
    return {"synthesis": {"backend": backend, backend: block}}


@pytest.mark.parametrize("backend", ["claude", "cursor_cli", "ollama"])
def test_every_backend_honours_explicit_chars_over_window(backend: str) -> None:
    block = {"usable_body_chars": 12_345, "context_window_tokens": 100_000}
    assert resolve_backend(_cfg(backend, **block)).usable_body_chars() == 12_345


@pytest.mark.parametrize(
    ("backend", "expected"),
    [("claude", _claude_lean_chars), ("cursor_cli", _heavy_chars), ("ollama", _ollama_chars)],
)
def test_every_backend_derives_from_a_configured_window_with_its_own_class(backend: str, expected: Any) -> None:
    got = resolve_backend(_cfg(backend, context_window_tokens=200_000)).usable_body_chars()
    assert got == expected(200_000)


def test_claude_known_alias_table_gives_the_large_window() -> None:
    for model in ("sonnet", "haiku", "opus", "claude-sonnet-4-5"):
        assert known_claude_context_window(model) == 200_000
        backend = resolve_backend(_cfg("claude", model=model))
        assert backend.usable_body_chars() == _claude_lean_chars(200_000) == 296_245
    assert known_claude_context_window("some-custom-model") is None
    assert known_claude_context_window(None) is None


def test_claude_lean_off_uses_the_heavy_agent_class() -> None:
    nested = resolve_backend(_cfg("claude", model="sonnet", lean=False))
    assert nested.usable_body_chars() == _heavy_chars(200_000) == 185_320
    flat = resolve_backend({"synthesis": {"backend": "claude", "claude_model": "sonnet", "claude_lean": False}})
    assert flat.usable_body_chars() == 185_320
    lean_default = resolve_backend(_cfg("claude", model="sonnet"))
    assert lean_default.usable_body_chars() > nested.usable_body_chars()


def test_claude_unknown_model_assumes_a_200k_window_with_the_lean_class() -> None:
    got = resolve_backend(_cfg("claude", model="my-proxy-model")).usable_body_chars()
    assert got == _claude_lean_chars(ASSUMED_AGENT_WINDOW_TOKENS) == 296_245
    heavy = resolve_backend(_cfg("claude", model="my-proxy-model", lean=False)).usable_body_chars()
    assert heavy == _heavy_chars(ASSUMED_AGENT_WINDOW_TOKENS) == 185_320


def test_claude_configured_window_beats_the_alias_table() -> None:
    backend = resolve_backend(_cfg("claude", model="sonnet", context_window_tokens=32_768))
    assert backend.usable_body_chars() == _claude_lean_chars(32_768) == 39_126


@pytest.mark.parametrize("model", ["composer-2.5", "composer-2.5-fast", "Composer-2.5-Fast", "some-future-model"])
def test_cursor_assumes_a_200k_window_with_the_heavy_class(model: str) -> None:
    """Known aliases and unlisted ids both land on 200k; never the 1,000 floor."""
    got = resolve_backend(_cfg("cursor_cli", model=model)).usable_body_chars()
    assert got == _heavy_chars(ASSUMED_AGENT_WINDOW_TOKENS) == 185_320


def test_cursor_alias_table_knows_the_composer_models() -> None:
    assert known_cursor_context_window("composer-2.5") == 200_000
    assert known_cursor_context_window("composer-2.5-fast") == 200_000
    assert known_cursor_context_window("some-future-model") is None
    assert known_cursor_context_window(None) is None


def test_cursor_configured_window_beats_the_alias_table() -> None:
    sized = resolve_backend(_cfg("cursor_cli", model="composer-2.5", context_window_tokens=400_000))
    assert sized.usable_body_chars() == _heavy_chars(400_000)


@pytest.mark.parametrize(
    "backend_factory",
    [
        lambda: ClaudeCLISynthesizer(claude_path="/usr/bin/claude", model="custom-model"),
        lambda: ClaudeCLISynthesizer(claude_path="/usr/bin/claude", model="custom-model", lean=False),
        lambda: CursorCLISynthesizer(model="composer-2.5"),
        lambda: CursorCLISynthesizer(model="composer-2.5-fast"),
        lambda: CursorCLISynthesizer(model="unlisted-model"),
    ],
    ids=["claude_lean", "claude_heavy", "composer-2.5", "composer-2.5-fast", "unlisted"],
)
def test_agent_defaults_never_land_on_the_1k_floor(backend_factory: Any) -> None:
    got = backend_factory().usable_body_chars()
    assert got >= SESSION_BODY_SEND_CAP_CHARS
    assert got > MIN_USABLE_BODY_CHARS


# ─── the 1,000-character floor is for explicit tiny values only ────────


def test_explicit_tiny_usable_body_chars_is_used_as_is(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="llmwiki.synth.base"):
        got = resolve_backend(_cfg("cursor_cli", usable_body_chars=500)).usable_body_chars()
    assert got == 500
    assert caplog.text == ""


def test_explicit_tiny_window_floors_at_1000_without_a_warning(caplog: pytest.LogCaptureFixture) -> None:
    """An operator who sets a window the heavy reserves cannot fit gets the 1,000-character floor."""
    with caplog.at_level(logging.WARNING, logger="llmwiki.synth.base"):
        got = resolve_backend(_cfg("cursor_cli", context_window_tokens=8192)).usable_body_chars()
    assert got == MIN_USABLE_BODY_CHARS
    assert caplog.text == ""


def test_derived_default_with_no_room_warns_and_clamps_to_the_session_cap(caplog: pytest.LogCaptureFixture) -> None:
    """A known/assumed window that cannot carry the reserves is a bug: warn, never a silent 1,000."""
    with caplog.at_level(logging.WARNING, logger="llmwiki.synth.base"):
        got = resolve_usable_body_chars(
            BodyBudgetConfig(),
            known_window_tokens=lambda: 32_768,
            budget_class=HEAVY_AGENT_BUDGET,
            derived_floor_chars=SESSION_BODY_SEND_CAP_CHARS,
        )
    assert got == SESSION_BODY_SEND_CAP_CHARS
    assert "no room for a body" in caplog.text
    assert "heavy-agent" in caplog.text


def test_derived_default_clamps_only_when_the_reserves_leave_no_room() -> None:
    # 80,000-token heavy window: room 80000 - 39600 - 28000 = 12,400 tokens → 25,420 chars, above the clamp.
    assert resolve_usable_body_chars(
        BodyBudgetConfig(),
        known_window_tokens=lambda: 80_000,
        budget_class=HEAVY_AGENT_BUDGET,
        derived_floor_chars=SESSION_BODY_SEND_CAP_CHARS,
    ) == _heavy_chars(80_000)
    # 60,000-token window: room 60000 - 39600 - 21000 = -600 tokens → clamped to the session cap.
    assert resolve_usable_body_chars(
        BodyBudgetConfig(),
        known_window_tokens=lambda: 60_000,
        budget_class=HEAVY_AGENT_BUDGET,
        derived_floor_chars=SESSION_BODY_SEND_CAP_CHARS,
    ) == SESSION_BODY_SEND_CAP_CHARS


# ─── Ollama auto-detection (/api/show) ─────────────────────────────────


class _ShowHTTP:
    """POST double: ``/api/show`` answers with ``show``; ``/api/generate`` echoes OK."""

    def __init__(self, show: tuple[int, str] | Exception):
        self.show = show
        self.show_calls = 0
        self.generate_payloads: list[dict[str, Any]] = []

    def __call__(self, url: str, payload: dict[str, Any], *, timeout: float) -> tuple[int, str]:
        if url.endswith("/api/show"):
            self.show_calls += 1
            if isinstance(self.show, Exception):
                raise self.show
            return self.show
        self.generate_payloads.append(payload)
        return 200, json.dumps({"response": "ok"})


def _show(parameters: str | None, context_length: int | None) -> tuple[int, str]:
    body: dict[str, Any] = {}
    if parameters is not None:
        body["parameters"] = parameters
    if context_length is not None:
        body["model_info"] = {"general.architecture": "llama", "llama.context_length": context_length}
    return 200, json.dumps(body)


def _ollama(show: tuple[int, str] | Exception, **block: Any) -> tuple[OllamaSynthesizer, _ShowHTTP]:
    http = _ShowHTTP(show)
    cfg = load_ollama_config(_cfg("ollama", **block))
    return OllamaSynthesizer(config=cfg, http_post=http), http


def test_ollama_uses_the_modelfile_num_ctx_it_detects() -> None:
    synth, http = _ollama(_show("temperature 0.7\nnum_ctx 16384", 131_072))
    assert synth.usable_body_chars() == _ollama_chars(16_384)
    assert synth.usable_body_chars() == _ollama_chars(16_384)
    assert http.show_calls == 1, "detection runs once per backend instance"


def test_ollama_detected_num_ctx_is_capped_by_the_trained_context() -> None:
    synth, _ = _ollama(_show("num_ctx 32768", 8192))
    assert synth.usable_body_chars() == _ollama_chars(8192)


def test_ollama_without_num_ctx_does_not_adopt_the_trained_maximum() -> None:
    """The trained 131k window is not what the server loads by default — only the default window applies."""
    synth, _ = _ollama(_show("temperature 0.7", 131_072))
    assert synth.usable_body_chars() == _ollama_chars(DEFAULT_CONTEXT_WINDOW_TOKENS)


def test_ollama_small_trained_context_caps_the_default_window() -> None:
    synth, _ = _ollama(_show(None, 6000))
    assert synth.usable_body_chars() == _ollama_chars(6000)


@pytest.mark.parametrize(
    "show",
    [(404, ""), (500, "boom"), (200, "not json"), (200, "[]"), ConnectionError("down")],
    ids=["404", "500", "bad-json", "not-an-object", "raises"],
)
def test_ollama_detection_failure_falls_back_to_the_default(show: tuple[int, str] | Exception) -> None:
    synth, _ = _ollama(show)
    assert synth.usable_body_chars() == _ollama_chars(DEFAULT_CONTEXT_WINDOW_TOKENS)


def test_ollama_configured_window_or_chars_skip_detection_for_the_budget() -> None:
    synth, http = _ollama((404, ""), context_window_tokens=24_000)
    assert synth.usable_body_chars() == _ollama_chars(24_000)
    synth2, http2 = _ollama((404, ""), usable_body_chars=11_111)
    assert synth2.usable_body_chars() == 11_111
    assert http.show_calls == 0 and http2.show_calls == 0


def test_ollama_page_calls_send_num_ctx_only_when_known() -> None:
    """Modelfile / config → send num_ctx; assumed default → leave the server alone (#311 N3)."""
    synth, http = _ollama(_show("num_ctx 16384", None))
    synth.synthesize_source_page("body", {}, TEMPLATE)
    assert http.generate_payloads[-1]["options"] == {"num_ctx": 16_384}

    synth_default, http_default = _ollama((404, ""))
    synth_default.synthesize_document_chunk("body", {}, TEMPLATE)
    assert "options" not in http_default.generate_payloads[-1]

    synth_trained, http_trained = _ollama(_show("temperature 0.7", 131_072))
    synth_trained.synthesize_source_page("body", {}, TEMPLATE)
    assert "options" not in http_trained.generate_payloads[-1]

    synth_cfg, http_cfg = _ollama((404, ""), context_window_tokens=24_000)
    synth_cfg.synthesize_source_page("body", {}, TEMPLATE)
    assert http_cfg.generate_payloads[-1]["options"] == {"num_ctx": 24_000}


def test_ollama_explicit_chars_raise_the_requested_window_to_fit() -> None:
    chars = 100_000
    synth, http = _ollama((404, ""), usable_body_chars=chars)
    synth.synthesize_document_chunk("body", {}, TEMPLATE)
    sent = http.generate_payloads[-1]["options"]["num_ctx"]
    assert sent > DEFAULT_CONTEXT_WINDOW_TOKENS
    assert usable_body_chars_for_window(sent, OLLAMA_BUDGET) >= chars, "the window must hold the explicit budget plus the reserves"


def test_ollama_config_exposes_the_nested_budget_keys() -> None:
    cfg = load_ollama_config(_cfg("ollama", usable_body_chars=9000, context_window_tokens=20_000))
    assert isinstance(cfg, OllamaConfig)
    assert cfg.body_budget == BodyBudgetConfig(usable_body_chars=9000, context_window_tokens=20_000)


# ─── sessions keep the 8,000-char send cap; document chunks are sent whole ──


def test_session_cap_is_the_historical_8000() -> None:
    assert SESSION_BODY_SEND_CAP_CHARS == 8000


def test_ollama_session_body_is_capped_but_a_document_chunk_is_sent_whole() -> None:
    synth, http = _ollama((404, ""), usable_body_chars=30_000)
    body = "y" * 25_000
    synth.synthesize_source_page(body, {}, "{body}")
    synth.synthesize_document_chunk(body, {}, "{body}")
    session_prompt, chunk_prompt = (p["prompt"] for p in http.generate_payloads)
    assert "y" * SESSION_BODY_SEND_CAP_CHARS in session_prompt
    assert "y" * (SESSION_BODY_SEND_CAP_CHARS + 1) not in session_prompt
    assert "y" * 25_000 in chunk_prompt


def test_cursor_session_body_is_capped_but_a_document_chunk_is_sent_whole() -> None:
    backend = CursorCLISynthesizer(body_budget=BodyBudgetConfig(usable_body_chars=30_000))
    sent: list[str] = []

    def _capture(*_a, **kwargs):
        sent.append(kwargs["input"])
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="ok", stderr="")

    body = "z" * 25_000
    with patch("llmwiki.synth.cursor_cli.resolve_cursor_agent_path", return_value="/bin/agent"), patch(
        "llmwiki.synth.cursor_cli.TrackedChildren.run", side_effect=_capture
    ):
        backend.synthesize_source_page(body, {}, TEMPLATE)
        backend.synthesize_document_chunk(body, {}, TEMPLATE)
    session_in, chunk_in = sent
    assert "z" * SESSION_BODY_SEND_CAP_CHARS in session_in
    assert "z" * (SESSION_BODY_SEND_CAP_CHARS + 1) not in session_in
    assert "z" * 25_000 in chunk_in


def test_claude_session_body_is_capped_but_a_document_chunk_is_sent_whole(tmp_path: Path) -> None:
    out = tmp_path / "stdin.txt"
    script = tmp_path / "fake-claude"
    script.write_text(f'#!/bin/sh\ncat > "{out}"\necho ok\n')
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    backend = ClaudeCLISynthesizer(
        claude_path=str(script), body_budget=BodyBudgetConfig(usable_body_chars=30_000)
    )
    body = "c" * 25_000

    backend.synthesize_source_page(body, {}, TEMPLATE)
    session_in = out.read_text()
    backend.synthesize_document_chunk(body, {}, TEMPLATE)
    chunk_in = out.read_text()

    assert "c" * SESSION_BODY_SEND_CAP_CHARS in session_in
    assert "c" * (SESSION_BODY_SEND_CAP_CHARS + 1) not in session_in
    assert "c" * 25_000 in chunk_in


def test_pipeline_sends_documents_through_the_chunk_entry_point_and_sessions_through_the_page_one(
    tmp_path: Path,
) -> None:
    class Spy(BaseSynthesizer):
        is_llm = False

        def __init__(self) -> None:
            self.page_calls = 0
            self.chunk_calls = 0

        def is_available(self) -> bool:
            return True

        def synthesize_source_page(self, raw_body, meta, prompt_template):
            self.page_calls += 1
            return "## Summary\n\nok\n"

        def synthesize_document_chunk(self, chunk, meta, prompt_template):
            self.chunk_calls += 1
            return super().synthesize_document_chunk(chunk, meta, prompt_template)

    docs = tmp_path / "raw" / "docs"
    docs.mkdir(parents=True)
    (docs / "d.md").write_text("---\nslug: d\n---\n# D\n\nbody\n", encoding="utf-8")
    sessions = tmp_path / "raw" / "sessions"
    sessions.mkdir(parents=True)
    (sessions / "2026-01-01T00-00-proj-s.md").write_text(
        "---\nslug: s\nproject: proj\ndate: 2026-01-01\n---\nsession body\n", encoding="utf-8"
    )
    (tmp_path / "wiki" / "sources").mkdir(parents=True)
    log = tmp_path / "wiki" / "log.md"
    log.write_text("# Log\n", encoding="utf-8")
    spy = Spy()

    synthesize_new_sessions(
        backend=spy,
        raw_dir=sessions,
        docs_dir=docs,
        wiki_sources_dir=tmp_path / "wiki" / "sources",
        log_path=log,
        state_file=tmp_path / "state.json",
    )

    assert spy.chunk_calls == 1, "the document went through synthesize_document_chunk"
    assert spy.page_calls == 2, "the document delegates to the page entry point; the session calls it directly"


def test_cli_estimate_uses_the_configured_llm_backend_budget_but_not_the_dummy_one() -> None:
    assert _estimate_backend({}) is None
    assert _estimate_backend({"synthesis": {"backend": "dummy"}}) is None
    backend = _estimate_backend(_cfg("claude", usable_body_chars=12_345))
    assert backend is not None and backend.usable_body_chars() == 12_345


# ─── review-2 N3–N5 follow-ups ─────────────────────────────────────────


def test_page_timeout_scales_linearly_above_the_session_cap() -> None:
    assert page_timeout_seconds(180, 0) == 180
    assert page_timeout_seconds(180, SESSION_BODY_SEND_CAP_CHARS) == 180
    assert page_timeout_seconds(180, SESSION_BODY_SEND_CAP_CHARS + 1) == 181
    big = 296_245
    assert page_timeout_seconds(180, big) == (
        180 * big + SESSION_BODY_SEND_CAP_CHARS - 1
    ) // SESSION_BODY_SEND_CAP_CHARS


def test_claude_scales_timeout_for_large_document_chunks() -> None:
    backend = ClaudeCLISynthesizer(
        claude_path="/bin/claude",
        timeout=180,
        body_budget=BodyBudgetConfig(usable_body_chars=30_000),
    )
    timeouts: list[float] = []

    def _capture(*_a, **kwargs):
        timeouts.append(float(kwargs["timeout"]))
        return subprocess.CompletedProcess(args=[], returncode=0, stdout='{"result":"ok"}', stderr="")

    body = "c" * 25_000
    with patch.object(backend, "_resolved", return_value="/bin/claude"), patch(
        "llmwiki.synth.claude_cli.TrackedChildren.run", side_effect=_capture
    ):
        backend.synthesize_source_page(body, {}, TEMPLATE)
        backend.synthesize_document_chunk(body, {}, TEMPLATE)
    assert timeouts == [180, page_timeout_seconds(180, 25_000)]


def test_cursor_scales_timeout_for_large_document_chunks() -> None:
    backend = CursorCLISynthesizer(
        timeout=180, body_budget=BodyBudgetConfig(usable_body_chars=30_000)
    )
    timeouts: list[float] = []

    def _capture(*_a, **kwargs):
        timeouts.append(float(kwargs["timeout"]))
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="ok", stderr="")

    body = "z" * 25_000
    with patch("llmwiki.synth.cursor_cli.resolve_cursor_agent_path", return_value="/bin/agent"), patch(
        "llmwiki.synth.cursor_cli.TrackedChildren.run", side_effect=_capture
    ):
        backend.synthesize_source_page(body, {}, TEMPLATE)
        backend.synthesize_document_chunk(body, {}, TEMPLATE)
    assert timeouts == [180, page_timeout_seconds(180, 25_000)]


def test_refresh_synth_pending_prices_docs_with_configured_backend(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """build/add refresh without an explicit backend must match synth --estimate (#311 N4)."""
    vault = tmp_path / "vault"
    raw = vault / "raw" / "sessions"
    docs = vault / "raw" / "docs"
    wiki = vault / "wiki" / "sources"
    raw.mkdir(parents=True)
    docs.mkdir(parents=True)
    wiki.mkdir(parents=True)
    # ~100 KB → many chunks at 7k budget, one chunk at a huge budget.
    (docs / "big.md").write_text(
        "---\nslug: big\ntitle: Big Doc\nproject: p\n---\n\n" + ("word " * 20_000) + "\n",
        encoding="utf-8",
    )
    state_file = vault / "llmwiki-state.json"
    cfg = _cfg("claude", usable_body_chars=7_000)
    monkeypatch.setattr("llmwiki.synth.pipeline._load_sessions_config", lambda: cfg)

    out = refresh_synth_pending(
        raw_dir=raw,
        docs_dir=docs,
        wiki_sources_dir=wiki,
        state_file=state_file,
        include_subagents="all",
        exclude_headless=False,
    )
    assert out["pending_total"] == 1
    pending_usd = float(read_state(state_file)["synth"]["pending"][0]["usd"])

    backend = resolve_backend(cfg)
    report = synthesize_estimate_report(
        raw_sessions=[],
        state_keys={},
        wiki_sources_dir=wiki,
        raw_root=raw,
        docs_root=docs,
        include_subagents="all",
        exclude_headless=False,
        backend=backend,
    )
    estimate_usd = float(report["unsynth_items"][0]["usd"])
    assert pending_usd == estimate_usd
    assert int(report["unsynth_items"][0]["chunks"]) > 1

    # Contrast: lean Claude's large default budget prices the same doc as one chunk.
    lean_report = synthesize_estimate_report(
        raw_sessions=[],
        state_keys={},
        wiki_sources_dir=wiki,
        raw_root=raw,
        docs_root=docs,
        include_subagents="all",
        exclude_headless=False,
        backend=resolve_backend({"synthesis": {"backend": "claude", "claude": {}}}),
    )
    assert int(lean_report["unsynth_items"][0]["chunks"]) == 1
    assert float(lean_report["unsynth_items"][0]["usd"]) != pending_usd
