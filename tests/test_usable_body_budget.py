"""Usable body budget for whole-document chunking (#311, review N1).

Spec: ``context/spec/324-whole-document-storage/``. A backend's budget is how
many raw-body characters ONE document-chunk call can carry. Resolution order:

1. ``synthesis.<backend>.usable_body_chars`` (explicit characters)
2. ``synthesis.<backend>.context_window_tokens`` (converted conservatively)
3. the backend's own knowledge — Claude's alias table, Ollama's ``/api/show``
4. the documented default window (``DEFAULT_CONTEXT_WINDOW_TOKENS``)

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
from llmwiki.synth.base import (
    BODY_CHARS_PER_TOKEN,
    DEFAULT_CONTEXT_WINDOW_TOKENS,
    DEFAULT_USABLE_BODY_CHARS,
    MIN_USABLE_BODY_CHARS,
    OUTPUT_RESERVE_TOKENS,
    PROMPT_RESERVE_TOKENS,
    SESSION_BODY_SEND_CAP_CHARS,
    BaseSynthesizer,
    BodyBudgetConfig,
    load_body_budget_config,
    resolve_usable_body_chars,
    usable_body_chars_for_window,
)
from llmwiki.synth.claude_cli import ClaudeCLISynthesizer, known_claude_context_window
from llmwiki.synth.cursor_cli import CursorCLISynthesizer
from llmwiki.synth.ollama import OllamaConfig, OllamaSynthesizer, load_ollama_config
from llmwiki.synth.pipeline import resolve_backend, synthesize_new_sessions

TEMPLATE = "Summarize:\n{body}\nMeta:\n{meta}\n"


def _window_chars(tokens: int) -> int:
    return int((tokens - PROMPT_RESERVE_TOKENS - OUTPUT_RESERVE_TOKENS) * BODY_CHARS_PER_TOKEN)


# ─── formula ───────────────────────────────────────────────────────────


def test_budget_formula_reserves_prompt_and_output_then_converts_conservatively() -> None:
    assert usable_body_chars_for_window(8192) == _window_chars(8192)
    assert usable_body_chars_for_window(200_000) == _window_chars(200_000)
    # Bigger window, bigger budget.
    assert usable_body_chars_for_window(32_768) > usable_body_chars_for_window(16_384)


def test_budget_never_drops_below_the_floor_however_small_the_window() -> None:
    assert usable_body_chars_for_window(1) == MIN_USABLE_BODY_CHARS
    assert usable_body_chars_for_window(PROMPT_RESERVE_TOKENS + OUTPUT_RESERVE_TOKENS) == MIN_USABLE_BODY_CHARS


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


def _cfg(backend: str, **block: Any) -> dict[str, Any]:
    return {"synthesis": {"backend": backend, backend: block}}


@pytest.mark.parametrize("backend", ["claude", "cursor_cli", "ollama"])
def test_every_backend_honours_explicit_chars_over_window(backend: str) -> None:
    block = {"usable_body_chars": 12_345, "context_window_tokens": 100_000}
    assert resolve_backend(_cfg(backend, **block)).usable_body_chars() == 12_345


@pytest.mark.parametrize("backend", ["claude", "cursor_cli", "ollama"])
def test_every_backend_derives_from_a_configured_window(backend: str) -> None:
    got = resolve_backend(_cfg(backend, context_window_tokens=50_000)).usable_body_chars()
    assert got == _window_chars(50_000)


def test_claude_known_alias_table_gives_the_large_window() -> None:
    for model in ("sonnet", "haiku", "opus", "claude-sonnet-4-5"):
        assert known_claude_context_window(model) == 200_000
        backend = resolve_backend(_cfg("claude", model=model))
        assert backend.usable_body_chars() == _window_chars(200_000)
    assert known_claude_context_window("some-custom-model") is None
    assert known_claude_context_window(None) is None


def test_claude_unknown_model_falls_back_to_the_documented_default() -> None:
    assert resolve_backend(_cfg("claude", model="my-proxy-model")).usable_body_chars() == DEFAULT_USABLE_BODY_CHARS


def test_claude_configured_window_beats_the_alias_table() -> None:
    backend = resolve_backend(_cfg("claude", model="sonnet", context_window_tokens=16_384))
    assert backend.usable_body_chars() == _window_chars(16_384)


def test_cursor_has_no_alias_table_so_unconfigured_is_the_default() -> None:
    assert resolve_backend(_cfg("cursor_cli", model="composer-2.5")).usable_body_chars() == DEFAULT_USABLE_BODY_CHARS


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
    assert synth.usable_body_chars() == _window_chars(16_384)
    assert synth.usable_body_chars() == _window_chars(16_384)
    assert http.show_calls == 1, "detection runs once per backend instance"


def test_ollama_detected_num_ctx_is_capped_by_the_trained_context() -> None:
    synth, _ = _ollama(_show("num_ctx 32768", 8192))
    assert synth.usable_body_chars() == _window_chars(8192)


def test_ollama_without_num_ctx_does_not_adopt_the_trained_maximum() -> None:
    """The trained 131k window is not what the server loads by default — only the default window applies."""
    synth, _ = _ollama(_show("temperature 0.7", 131_072))
    assert synth.usable_body_chars() == DEFAULT_USABLE_BODY_CHARS


def test_ollama_small_trained_context_caps_the_default_window() -> None:
    synth, _ = _ollama(_show(None, 6000))
    assert synth.usable_body_chars() == _window_chars(6000)


@pytest.mark.parametrize(
    "show",
    [(404, ""), (500, "boom"), (200, "not json"), (200, "[]"), ConnectionError("down")],
    ids=["404", "500", "bad-json", "not-an-object", "raises"],
)
def test_ollama_detection_failure_falls_back_to_the_default(show: tuple[int, str] | Exception) -> None:
    synth, _ = _ollama(show)
    assert synth.usable_body_chars() == DEFAULT_USABLE_BODY_CHARS


def test_ollama_configured_window_or_chars_skip_detection_for_the_budget() -> None:
    synth, http = _ollama((404, ""), context_window_tokens=24_000)
    assert synth.usable_body_chars() == _window_chars(24_000)
    synth2, http2 = _ollama((404, ""), usable_body_chars=11_111)
    assert synth2.usable_body_chars() == 11_111
    assert http.show_calls == 0 and http2.show_calls == 0


def test_ollama_page_calls_ask_the_server_to_load_the_assumed_window() -> None:
    synth, http = _ollama(_show("num_ctx 16384", None))
    synth.synthesize_source_page("body", {}, TEMPLATE)
    assert http.generate_payloads[-1]["options"] == {"num_ctx": 16_384}

    synth_default, http_default = _ollama((404, ""))
    synth_default.synthesize_document_chunk("body", {}, TEMPLATE)
    assert http_default.generate_payloads[-1]["options"] == {"num_ctx": DEFAULT_CONTEXT_WINDOW_TOKENS}


def test_ollama_explicit_chars_raise_the_requested_window_to_fit() -> None:
    chars = 100_000
    synth, http = _ollama((404, ""), usable_body_chars=chars)
    synth.synthesize_document_chunk("body", {}, TEMPLATE)
    sent = http.generate_payloads[-1]["options"]["num_ctx"]
    assert sent > DEFAULT_CONTEXT_WINDOW_TOKENS
    assert _window_chars(sent) >= chars, "the window must hold the explicit budget plus the reserves"


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
