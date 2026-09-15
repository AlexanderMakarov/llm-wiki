"""#181 — synth stops cleanly on a backend usage limit or Ctrl+C.

# @layer: integration
# @spec: 009-one-call-per-source-synth

Covers the stop in the sources pass (queue cancelled, in-flight pages
recorded, idempotent bookkeeping, a limit during known-names preparation),
the second-Ctrl+C kill of in-flight synthesizer processes, usage-limit
detection by message text in every backend, the ``synth`` / ``all`` exit
codes, and the automation wrapper's real exit code.

New names (``BackendUsageLimitError``) are resolved at call time rather than
imported, so on a build without the fix each test fails on the missing
behaviour instead of the whole module failing to import.

Backends are in-process fakes; the ``claude`` CLI and the network are never
reached. Every vault lives under ``tmp_path``.
"""

from __future__ import annotations

import builtins
import json
import os
import subprocess
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from llmwiki import cli, topics_consolidate
from llmwiki import pipeline as all_pipeline
from llmwiki.automation_install import render_wrapper_script
from llmwiki.automation_plan import AutomationPlan
from llmwiki.cli import build_parser, cmd_synthesize
from llmwiki.synth import base as synth_base
from llmwiki.synth import cursor_cli
from llmwiki.synth import pipeline as synth_pipeline
from llmwiki.synth.child_processes import TrackedChildren
from llmwiki.synth.claude_cli import ClaudeCLIError, ClaudeCLISynthesizer
from llmwiki.synth.cursor_cli import CursorCLIError, CursorCLISynthesizer
from llmwiki.synth.ollama import OllamaConfig, OllamaHTTPError, OllamaSynthesizer
from tests import test_synth_claude_cli as claude_tests
from tests import test_synth_parallel as parallel_tests
from tests import test_synth_run_summary as summary_tests
from tests import test_topics as topics_tests

_RESET = "1:20pm (Etc/UTC)"
_LIMIT_TEXT = f"You've hit your session limit · resets {_RESET}"


def _usage_limit_error(reset: str | None = _RESET) -> Exception:
    """A backend usage-limit error, looked up when the test runs."""
    return synth_base.BackendUsageLimitError("usage limit", reset=reset)


def _state_file(vault: Path) -> dict:
    """The raw unified state written for the vault."""
    return json.loads((vault / "state.json").read_text(encoding="utf-8"))


def _synthesize_entries(vault: Path) -> list[str]:
    """``wiki/log.md`` headings written by synth runs."""
    log = (vault / "wiki" / "log.md").read_text(encoding="utf-8")
    return [ln for ln in log.splitlines() if "] synthesize | " in ln]


# ─── pipeline: usage limit stops the queue ───────────────────────────────


class _LimitAfterBackend(parallel_tests._RealPageBackend):
    """Writes real pages for the first ``ok`` calls; every later call hits the limit."""

    def __init__(self, ok: int) -> None:
        self._lock = threading.Lock()
        self._ok = ok
        self.calls = 0

    def synthesize_source_page(self, raw_body, meta, prompt_template):  # noqa: D102
        with self._lock:
            self.calls += 1
            limited = self.calls > self._ok
        if limited:
            raise _usage_limit_error()
        return super().synthesize_source_page(raw_body, meta, prompt_template)


# @regression
def test_usage_limit_stops_dispatch_and_defers_the_rest(tmp_path: Path, capsys) -> None:
    """The first limit result stops new backend calls; landed pages are recorded, the rest stay pending."""
    vault = parallel_tests._mk_vault(tmp_path)
    slugs = tuple(f"doc{i:02d}" for i in range(12))
    parallel_tests._seed_docs(vault, slugs)
    ok, concurrency = 3, 2
    backend = _LimitAfterBackend(ok=ok)

    summary = parallel_tests._run_synth(vault, backend, concurrency=concurrency)

    # A worker checks the stop before calling the backend, so beyond the
    # successes only the limit call and one call per other worker can land.
    assert backend.calls <= ok + concurrency
    assert summary["errors"] == []
    assert summary["synthesized"] == ok
    assert summary["deferred"] == len(slugs) - ok
    assert summary["usage_limit"] == {"reset": _RESET}
    assert not summary.get("interrupted")
    assert synth_pipeline.synth_stop_exit_code(summary) == 75

    pages = parallel_tests._pages(vault)
    recorded = parallel_tests._synth_state(vault)
    assert len(pages) == ok
    assert len(recorded) == ok
    for rel in recorded:
        # State keys carry a corpus prefix, e.g. ``docs::doc00.md``.
        slug = Path(rel.rsplit("::", 1)[-1]).stem
        assert any(path.endswith(f"-{slug}.md") for path in pages), rel

    pending = _state_file(vault)["synth"]["pending"]
    assert len(pending) == summary["deferred"]
    assert not {row["rel"] for row in pending} & set(recorded)

    entries = _synthesize_entries(vault)
    assert len(entries) == 1
    assert "stopped early (backend usage limit)" in entries[0]
    log = (vault / "wiki" / "log.md").read_text(encoding="utf-8")
    assert f"- Deferred: {len(slugs) - ok}" in log
    assert "- Errors:" not in log
    assert f"usage limit (resets {_RESET})" in capsys.readouterr().out


# @regression
def test_a_generic_backend_failure_does_not_stop_the_run(tmp_path: Path) -> None:
    """A non-limit failure is one source's error; the others still complete and nothing is deferred."""
    vault = parallel_tests._mk_vault(tmp_path)
    slugs = tuple(f"doc{i:02d}" for i in range(6))
    parallel_tests._seed_docs(vault, slugs)

    summary = parallel_tests._run_synth(
        vault, parallel_tests._FlakyBackend({"doc02"}), concurrency=2
    )

    assert summary["synthesized"] == len(slugs) - 1
    assert [err.split(":", 1)[0] for err in summary["errors"]] == ["doc02"]
    assert summary["deferred"] == 0
    assert "usage_limit" not in summary
    assert synth_pipeline.synth_stop_exit_code(summary) == 0
    assert len(parallel_tests._synth_state(vault)) == len(slugs) - 1
    entries = _synthesize_entries(vault)
    assert len(entries) == 1
    assert "stopped early" not in entries[0]


# ─── pipeline: Ctrl+C takes the same tail ────────────────────────────────


class _HeldBackend(parallel_tests._RealPageBackend):
    """Holds every call at ``gate`` and signals ``entered`` once ``parties`` calls are in flight."""

    def __init__(self, parties: int) -> None:
        self._lock = threading.Lock()
        self._parties = parties
        self._live = 0
        self.entered = threading.Event()
        self.gate = threading.Event()

    def synthesize_source_page(self, raw_body, meta, prompt_template):  # noqa: D102
        with self._lock:
            self._live += 1
            if self._live >= self._parties:
                self.entered.set()
        self.gate.wait(timeout=2.0)
        return super().synthesize_source_page(raw_body, meta, prompt_template)


# @regression
def test_ctrl_c_drains_in_flight_pages_and_writes_the_log_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ctrl+C while pages run: they finish, are counted and recorded, and the run logs one stopped-early entry."""
    vault = parallel_tests._mk_vault(tmp_path)
    slugs = tuple(f"doc{i:02d}" for i in range(20))
    parallel_tests._seed_docs(vault, slugs)
    concurrency = 2
    backend = _HeldBackend(parties=concurrency)
    real_as_completed = synth_pipeline.as_completed
    waits = {"n": 0}

    def _as_completed(futures):
        # The first wait is where a terminal Ctrl+C lands; the pages are
        # released only once the run is already stopping.
        waits["n"] += 1
        if waits["n"] == 1:
            assert backend.entered.wait(timeout=10.0), "pages never started"
            raise KeyboardInterrupt
        backend.gate.set()
        return real_as_completed(futures)

    monkeypatch.setattr(synth_pipeline, "as_completed", _as_completed)

    summary = parallel_tests._run_synth(vault, backend, concurrency=concurrency)
    backend.gate.set()

    assert summary["interrupted"] is True
    assert summary["errors"] == []
    assert summary["synthesized"] >= 1
    assert len(parallel_tests._pages(vault)) == summary["synthesized"]
    assert len(parallel_tests._synth_state(vault)) == summary["synthesized"]
    assert summary["deferred"] == len(slugs) - summary["synthesized"]
    assert summary["deferred"] > 0

    entries = _synthesize_entries(vault)
    assert len(entries) == 1
    assert "stopped early (interrupted)" in entries[0]
    assert f"- Deferred: {summary['deferred']}" in (vault / "wiki" / "log.md").read_text(
        encoding="utf-8"
    )
    assert synth_pipeline.synth_stop_exit_code(summary) == 130


# @regression
@pytest.mark.parametrize("step", ["save-state", "progress-print"])
def test_ctrl_c_during_result_bookkeeping_still_records_the_written_page(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, step: str
) -> None:
    """Ctrl+C while a landed page is being recorded: it is recorded on the next wait, counted once."""
    vault = parallel_tests._mk_vault(tmp_path)
    slugs = tuple(f"doc{i:02d}" for i in range(8))
    parallel_tests._seed_docs(vault, slugs)
    fired = {"n": 0}

    if step == "save-state":
        real_save_state = synth_pipeline._save_state

        def _save_state(state, state_file=None):
            if fired["n"] == 0:
                fired["n"] = 1
                raise KeyboardInterrupt
            return real_save_state(state, state_file)

        monkeypatch.setattr(synth_pipeline, "_save_state", _save_state)
    else:

        def _print(*args, **kwargs):
            if fired["n"] == 0 and args and "synthesized:" in str(args[0]):
                fired["n"] = 1
                raise KeyboardInterrupt
            builtins.print(*args, **kwargs)

        monkeypatch.setattr(synth_pipeline, "print", _print, raising=False)

    summary = parallel_tests._run_synth(
        vault, parallel_tests._RealPageBackend(), concurrency=2
    )

    assert fired["n"] == 1
    assert summary["interrupted"] is True
    assert summary["errors"] == []
    assert summary["synthesized"] >= 1
    assert len(parallel_tests._pages(vault)) == summary["synthesized"]
    assert len(parallel_tests._synth_state(vault)) == summary["synthesized"]
    assert summary["deferred"] == len(slugs) - summary["synthesized"] - len(summary["errors"])


class _KillableBackend(_HeldBackend):
    """Holds every call until ``kill_in_flight``; a killed call fails like a killed child."""

    def __init__(self, parties: int) -> None:
        super().__init__(parties)
        self.kill_calls = 0

    def synthesize_source_page(self, raw_body, meta, prompt_template):  # noqa: D102
        with self._lock:
            self._live += 1
            if self._live >= self._parties:
                self.entered.set()
        self.gate.wait(timeout=10.0)
        raise RuntimeError("synthesizer process killed")

    def kill_in_flight(self) -> int:  # noqa: D102
        self.kill_calls += 1
        self.gate.set()
        return self._parties


# @regression
def test_second_ctrl_c_kills_in_flight_pages_and_reraises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A second Ctrl+C during the drain calls the backend's kill hook, records nothing killed, and re-raises."""
    vault = parallel_tests._mk_vault(tmp_path)
    parallel_tests._seed_docs(vault, tuple(f"doc{i:02d}" for i in range(6)))
    backend = _KillableBackend(parties=2)
    waits = {"n": 0}

    def _as_completed(futures):
        waits["n"] += 1
        if waits["n"] == 1:
            assert backend.entered.wait(timeout=10.0), "pages never started"
        raise KeyboardInterrupt

    monkeypatch.setattr(synth_pipeline, "as_completed", _as_completed)
    started = time.monotonic()

    with pytest.raises(KeyboardInterrupt):
        parallel_tests._run_synth(vault, backend, concurrency=2)

    assert time.monotonic() - started < 5.0
    assert backend.kill_calls == 1
    assert parallel_tests._pages(vault) == {}
    assert parallel_tests._synth_state(vault) == {}


@pytest.mark.skipif(os.name != "posix", reason="POSIX process groups and sh")
@pytest.mark.parametrize(
    "script",
    [
        pytest.param("sleep 30", id="exits-on-sigterm"),
        pytest.param("trap '' TERM; sleep 30", id="killed-after-grace"),
    ],
)
def test_kill_all_stops_a_tracked_child_promptly(script: str) -> None:
    """A live tracked child is gone within about a second of ``kill_all``, SIGTERM-deaf or not."""
    children = TrackedChildren()
    result: dict = {}
    worker = threading.Thread(
        target=lambda: result.setdefault(
            "proc", children.run(["sh", "-c", script], timeout=60)
        )
    )
    worker.start()
    deadline = time.monotonic() + 5.0
    while len(children) == 0 and time.monotonic() < deadline:
        time.sleep(0.01)
    assert len(children) == 1
    time.sleep(0.2)  # let the shell install its trap
    started = time.monotonic()

    assert children.kill_all(grace=0.3) == 1
    worker.join(timeout=5.0)

    assert not worker.is_alive()
    assert time.monotonic() - started < 1.5
    assert result["proc"].returncode != 0
    assert len(children) == 0


# ─── known-names prep: usage limit and progress line ─────────────────────


class _PrepLimitBackend(parallel_tests._RealPageBackend):
    """The known-names call hits the usage limit; page calls are counted."""

    def __init__(self) -> None:
        self.page_calls = 0

    def synthesize_source_page(self, raw_body, meta, prompt_template):  # noqa: D102
        if meta.get("slug") == "known-names":
            raise _usage_limit_error()
        self.page_calls += 1
        return super().synthesize_source_page(raw_body, meta, prompt_template)


# @regression
def test_usage_limit_during_known_names_prep_defers_every_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """A limit on the prep call sends no page, defers the whole queue, and ``synth`` exits 75."""
    vault = parallel_tests._mk_vault(tmp_path)
    slugs = tuple(f"doc{i:02d}" for i in range(5))
    parallel_tests._seed_docs(vault, slugs)
    monkeypatch.setattr(topics_consolidate, "build_candidates", lambda wiki_dir=None: [{"name": "X"}])
    monkeypatch.setattr(topics_consolidate, "render_consolidation_prompt", lambda wiki_dir=None: "prompt")
    backend = _PrepLimitBackend()

    summary = parallel_tests._run_synth(vault, backend, concurrency=2)

    assert backend.page_calls == 0
    assert summary["synthesized"] == 0
    assert summary["errors"] == []
    assert summary["deferred"] == len(slugs)
    assert summary["usage_limit"] == {"reset": _RESET}
    assert parallel_tests._pages(vault) == {}
    assert len(_state_file(vault)["synth"]["pending"]) == len(slugs)
    entries = _synthesize_entries(vault)
    assert len(entries) == 1
    assert "stopped early (backend usage limit)" in entries[0]
    out = capsys.readouterr().out
    assert f"Stopped after 0/{len(slugs)} source(s)" in out
    assert f"usage limit (resets {_RESET})" in out

    rc, harvest = _run_cmd_synth(summary_tests._mk_vault(tmp_path / "cli"), [], summary)

    assert rc == 75
    harvest.assert_called_once()


def test_known_names_prep_prints_a_progress_line_before_the_call(tmp_path: Path, capsys) -> None:
    """The prep announces its candidate count and prompt size before the model call."""
    wiki = topics_tests._make_wiki(tmp_path, {"s1": ["OpenClaw", "Bun"], "s2": ["OpenClaw", "Bun"]})
    candidates = topics_consolidate.build_candidates(wiki)
    prompt = topics_consolidate.render_consolidation_prompt(wiki)
    seen: list[str] = []

    class _Llm:
        is_llm = True

        def synthesize_source_page(self, raw_body, meta, prompt_template):
            seen.append(capsys.readouterr().out)
            return '{"topics": [], "dropped": []}'

    topics_consolidate.prepare_known_names(wiki, _Llm())

    size = topics_consolidate.format_prompt_size(len(prompt.encode("utf-8")))
    assert len(seen) == 1
    assert f"Preparing known names from {len(candidates)} candidate topic(s)" in seen[0]
    assert f"({size} prompt)" in seen[0]


def test_known_names_prep_prints_nothing_without_candidates(tmp_path: Path, capsys) -> None:
    """No candidates: no model call and no progress line."""
    wiki = topics_tests._make_wiki(tmp_path, {})

    class _Llm:
        is_llm = True

        def synthesize_source_page(self, raw_body, meta, prompt_template):
            raise AssertionError("no candidates must not call the model")

    topics_consolidate.prepare_known_names(wiki, _Llm())

    assert "Preparing known names" not in capsys.readouterr().out


@pytest.mark.parametrize(
    ("n_bytes", "text"),
    [(10, "~1 KB"), (95 * 1024, "~95 KB"), (int(1.25 * 1024 * 1024), "~1.2 MB")],
)
def test_prompt_size_is_compact(n_bytes: int, text: str) -> None:
    """Prompt sizes print as whole KB below a megabyte and one-decimal MB above."""
    assert topics_consolidate.format_prompt_size(n_bytes) == text


# ─── Claude CLI backend: limit detection ─────────────────────────────────


def _claude_backend(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    returncode: int,
    payload: dict | None,
    stderr: str = "",
) -> tuple[ClaudeCLISynthesizer, list[list[str]]]:
    """A Claude backend whose page child is faked; returns it and the recorded argv."""
    script = claude_tests._script(tmp_path, "claude-stub", "#!/bin/sh\nexit 0\n")
    backend = ClaudeCLISynthesizer(claude_path=str(script))
    calls: list[list[str]] = []
    stdout = json.dumps(payload) + "\n" if payload is not None else ""

    def _run(argv, *, input=None, timeout):
        calls.append(list(argv))
        return subprocess.CompletedProcess(argv, returncode, stdout, stderr)

    monkeypatch.setattr(backend._children, "run", _run)
    return backend, calls


# @regression
@pytest.mark.parametrize(
    ("returncode", "payload", "stderr"),
    [
        pytest.param(
            1,
            {"type": "result", "subtype": "success", "is_error": True,
             "api_error_status": 429, "result": _LIMIT_TEXT},
            "",
            id="nonzero-exit-429-quota-text",
        ),
        pytest.param(
            0,
            {"type": "result", "subtype": "success", "is_error": True, "result": _LIMIT_TEXT},
            "",
            id="exit0-is-error-quota-text",
        ),
        pytest.param(1, None, _LIMIT_TEXT, id="nonzero-exit-stderr-quota-text"),
    ],
)
def test_claude_limit_result_raises_usage_limit_with_reset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, returncode: int, payload, stderr: str
) -> None:
    """Every failure branch maps quota wording to ``BackendUsageLimitError`` carrying the reset time."""
    backend, calls = _claude_backend(
        tmp_path, monkeypatch, returncode=returncode, payload=payload, stderr=stderr
    )

    with pytest.raises(synth_base.BackendUsageLimitError) as info:
        backend.synthesize_source_page("body", {"slug": "s1"}, claude_tests.TEMPLATE)

    assert info.value.reset == _RESET
    assert len(calls) == 1


# @regression
@pytest.mark.parametrize(
    ("returncode", "payload"),
    [
        pytest.param(
            1,
            {"type": "result", "is_error": True, "api_error_status": 500,
             "result": "Internal server error"},
            id="nonzero-exit-500",
        ),
        pytest.param(
            1,
            {"type": "result", "is_error": True, "api_error_status": 429,
             "result": "Rate limit exceeded"},
            id="nonzero-exit-bare-429",
        ),
        pytest.param(
            0,
            {"type": "result", "is_error": True, "api_error_status": 429,
             "result": "API Error: 429 Too Many Requests"},
            id="exit0-bare-429",
        ),
    ],
)
def test_claude_non_limit_failure_stays_a_plain_cli_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, returncode: int, payload: dict
) -> None:
    """A failure without quota wording — a bare 429 included — is a per-page ``ClaudeCLIError``."""
    backend, _calls = _claude_backend(
        tmp_path, monkeypatch, returncode=returncode, payload=payload
    )

    with pytest.raises(ClaudeCLIError) as info:
        backend.synthesize_source_page("body", {"slug": "s1"}, claude_tests.TEMPLATE)

    assert not isinstance(info.value, synth_base.BackendUsageLimitError)


# ─── shared matcher + Cursor / Ollama limit detection ────────────────────


# @regression
@pytest.mark.parametrize(
    ("text", "reset"),
    [
        pytest.param(_LIMIT_TEXT, _RESET, id="claude-session-limit"),
        pytest.param("Claude AI usage limit reached", None, id="usage-limit-reached"),
        pytest.param(
            "You've hit your usage limit. Your limit resets at 5pm.", "5pm",
            id="hit-your-limit-resets-at",
        ),
        pytest.param(
            '{"error": "you have reached your weekly usage limit"}', None,
            id="json-body-weekly-usage-limit",
        ),
        pytest.param("Error: quota exceeded for this account", None, id="quota-exceeded"),
        pytest.param(
            "You exceeded your current quota, please check your plan.", None,
            id="exceeded-your-quota",
        ),
        pytest.param("Out of credits", None, id="out-of-credits"),
    ],
)
def test_usage_limit_matcher_recognises_quota_wording(text: str, reset: str | None) -> None:
    """Account / session quota messages become a usage limit, with the reset time when given."""
    limit = synth_base.usage_limit_from_text(text, label="demo")

    assert isinstance(limit, synth_base.BackendUsageLimitError)
    assert limit.reset == reset
    assert str(limit).startswith("demo usage limit: ")


# @regression
@pytest.mark.parametrize(
    "text",
    [
        "Rate limit exceeded",
        "429 Too Many Requests",
        "You've hit your rate limit, slow down",
        "API Error: 429 rate_limit_error: request throttled",
        "Internal server error",
        "",
        None,
    ],
)
def test_usage_limit_matcher_ignores_throttling_and_other_errors(text) -> None:
    """Short-lived throttling and unrelated failures are not a usage limit."""
    assert synth_base.usage_limit_from_text(text) is None


def _cursor_backend(monkeypatch: pytest.MonkeyPatch, *, returncode: int, stderr: str):
    backend = CursorCLISynthesizer()
    monkeypatch.setattr(cursor_cli, "resolve_cursor_agent_path", lambda: "/bin/agent")
    monkeypatch.setattr(
        backend._children,
        "run",
        lambda argv, *, input=None, timeout: subprocess.CompletedProcess(
            argv, returncode, "", stderr
        ),
    )
    return backend


# @regression
def test_cursor_quota_message_raises_usage_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    """A Cursor Agent CLI exit carrying quota wording stops the run instead of failing one page."""
    backend = _cursor_backend(monkeypatch, returncode=1, stderr=_LIMIT_TEXT)

    with pytest.raises(synth_base.BackendUsageLimitError) as info:
        backend.synthesize_source_page("body", {"slug": "s1"}, claude_tests.TEMPLATE)

    assert info.value.reset == _RESET


# @regression
def test_cursor_throttling_stays_a_cursor_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """A bare 429 from Cursor Agent CLI is its normal per-page error."""
    backend = _cursor_backend(monkeypatch, returncode=1, stderr="429 Too Many Requests")

    with pytest.raises(CursorCLIError) as info:
        backend.synthesize_source_page("body", {"slug": "s1"}, claude_tests.TEMPLATE)

    assert not isinstance(info.value, synth_base.BackendUsageLimitError)


def _ollama_backend(status: int, body: str) -> OllamaSynthesizer:
    return OllamaSynthesizer(
        config=OllamaConfig(max_retries=1, backoff_base=0.0),
        http_post=lambda url, payload, *, timeout: (status, body),
    )


# @regression
def test_ollama_429_with_quota_body_raises_usage_limit() -> None:
    """An Ollama error body with quota wording is a usage limit, not an HTTP error."""
    backend = _ollama_backend(429, '{"error": "you have reached your weekly usage limit"}')

    with pytest.raises(synth_base.BackendUsageLimitError):
        backend.synthesize_source_page("body", {"slug": "s1"}, claude_tests.TEMPLATE)


# @regression
def test_ollama_bare_429_stays_an_http_error() -> None:
    """A 429 whose body is plain throttling stays ``OllamaHTTPError``."""
    backend = _ollama_backend(429, '{"error": "Too Many Requests"}')

    with pytest.raises(OllamaHTTPError) as info:
        backend.synthesize_source_page("body", {"slug": "s1"}, claude_tests.TEMPLATE)

    assert info.value.status == 429


# ─── CLI: synth exit codes ───────────────────────────────────────────────


def _stopped_summary(**stop) -> dict:
    return {
        "total_scanned": 3,
        "new_files": 3,
        "synthesized": 1,
        "skipped": 0,
        "errors": [],
        "deferred": 2,
        **stop,
    }


def _run_cmd_synth(vault: Path, argv: list[str], summary: dict, harvest_rc: int = 0):
    args = build_parser().parse_args(["synth", *argv, "--vault", str(vault)])
    with (
        patch("llmwiki.cli.resolve_backend") as rb,
        patch("llmwiki.cli.synthesize_new_sessions", return_value=summary),
        patch("llmwiki.cli.run_harvest", return_value=harvest_rc) as harvest,
        patch("llmwiki.cli._refresh_review_counts"),
    ):
        backend = MagicMock()
        backend.name = "dummy"
        backend.is_available.return_value = True
        rb.return_value = backend
        rc = cmd_synthesize(args)
    return rc, harvest


# @regression
@pytest.mark.parametrize(
    ("stop", "expected"),
    [
        pytest.param({"usage_limit": {"reset": _RESET}}, 75, id="usage-limit"),
        pytest.param({"interrupted": True}, 130, id="interrupt"),
    ],
)
def test_synth_stop_harvests_then_exits_with_the_stop_code(
    tmp_path: Path, capsys, stop: dict, expected: int
) -> None:
    """A stop harvests what landed and exits 75 / 130 — even when a source also failed."""
    vault = summary_tests._mk_vault(tmp_path)
    summary = _stopped_summary(**stop)
    summary["errors"] = ["doc01: backend refused doc01"]

    rc, harvest = _run_cmd_synth(vault, [], summary)

    assert rc == expected
    harvest.assert_called_once()
    assert harvest.call_args.kwargs.get("require_sources") is False
    assert "Pending names collected from written sources." in capsys.readouterr().out


# @regression
def test_synth_sources_only_usage_limit_prints_the_candidates_hint(
    tmp_path: Path, capsys
) -> None:
    """``--sources-only`` on a usage-limit stop skips harvest, prints the retry command, exits 75."""
    vault = summary_tests._mk_vault(tmp_path)

    rc, harvest = _run_cmd_synth(
        vault, ["--sources-only"], _stopped_summary(usage_limit={"reset": None})
    )

    assert rc == 75
    harvest.assert_not_called()
    assert "llmwiki synth --candidates-only" in capsys.readouterr().out.splitlines()


# ─── `all`: stop codes survive later stages ──────────────────────────────


# @regression
@pytest.mark.parametrize(
    ("stop", "expected"),
    [
        pytest.param({"usage_limit": {"reset": _RESET}}, 75, id="usage-limit"),
        pytest.param({"interrupted": True}, 130, id="interrupt"),
    ],
)
def test_all_propagates_synth_stop_code_over_a_lint_failure(
    tmp_path: Path, stop: dict, expected: int
) -> None:
    """``all`` keeps harvesting and building after a stop, and a later lint policy failure does not mask 75 / 130."""
    vault = tmp_path / "vault"
    for sub in ("raw/sessions", "raw/docs", "wiki", "site"):
        (vault / sub).mkdir(parents=True)
    backend = MagicMock()
    backend.name = "dummy"
    backend.is_available.return_value = True
    args = build_parser().parse_args(
        ["all", "--no-sync", "--skip-graph", "--lint-fail", "errors", "--vault", str(vault)]
    )

    build_stub = MagicMock(return_value=0)
    lint_stub = MagicMock(return_value=(0, {"error": 1, "warning": 0}))
    with (
        patch.object(all_pipeline, "resolve_backend", return_value=backend),
        patch.object(all_pipeline, "synthesize_new_sessions", return_value=_stopped_summary(**stop)),
        patch.object(all_pipeline, "stamp_last_synth_at"),
        patch.object(all_pipeline, "run_harvest", return_value=0) as harvest,
        patch.object(all_pipeline, "build_site", build_stub),
        patch.object(all_pipeline, "_run_lint_step", lint_stub),
        patch.object(all_pipeline, "_maybe_print_optout_notice"),
        patch.object(all_pipeline, "_load_sessions_config", return_value={}),
    ):
        rc = cli.cmd_all(args)

    assert rc == expected
    harvest.assert_called_once()
    assert build_stub.call_count == 1
    assert lint_stub.call_count == 1


# ─── automation wrapper: real exit code ──────────────────────────────────


# @regression
@pytest.mark.skipif(os.name != "posix", reason="runs the generated bash wrapper")
@pytest.mark.parametrize("code", [1, 75])
def test_wrapper_logs_and_exits_with_the_command_exit_code(tmp_path: Path, code: int) -> None:
    """The scheduled wrapper ends its log with ``EXIT:<code>`` and exits with that code."""
    stub = claude_tests._script(tmp_path, "python-stub", f"#!/bin/sh\necho ran\nexit {code}\n")
    log_path = tmp_path / "logs" / "automation.log"
    wrapper = tmp_path / "wrapper.sh"
    wrapper.write_text(
        render_wrapper_script(
            plan=AutomationPlan(job="ingest"),
            python_bin=str(stub),
            working_dir=tmp_path,
            log_path=log_path,
        ),
        encoding="utf-8",
    )

    proc = subprocess.run(["bash", str(wrapper)], capture_output=True, text=True, timeout=30)

    assert proc.returncode == code
    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "ran"
    assert lines[-1] == f"EXIT:{code}"
