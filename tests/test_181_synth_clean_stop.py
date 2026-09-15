"""#181 — synth stops cleanly on a backend usage limit or Ctrl+C.

# @layer: integration
# @spec: 009-one-call-per-source-synth

Covers the stop in the sources pass (queue cancelled, in-flight pages
recorded, success-path bookkeeping), the Claude CLI limit detection, the
``synth`` / ``all`` exit codes, and the automation wrapper's real exit code.

New names (``BackendUsageLimitError``) are resolved at call time rather than
imported, so on a build without the fix each test fails on the missing
behaviour instead of the whole module failing to import.

Backends are in-process fakes; the ``claude`` CLI and the network are never
reached. Every vault lives under ``tmp_path``.
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from llmwiki import cli
from llmwiki import pipeline as all_pipeline
from llmwiki.automation_install import render_wrapper_script
from llmwiki.automation_plan import AutomationPlan
from llmwiki.cli import build_parser, cmd_synthesize
from llmwiki.synth import base as synth_base
from llmwiki.synth import claude_cli
from llmwiki.synth import pipeline as synth_pipeline
from llmwiki.synth.claude_cli import ClaudeCLIError, ClaudeCLISynthesizer
from tests import test_synth_claude_cli as claude_tests
from tests import test_synth_parallel as parallel_tests
from tests import test_synth_run_summary as summary_tests

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


# ─── Claude CLI backend: limit detection ─────────────────────────────────


def _fake_claude_run(monkeypatch, *, returncode: int, payload: dict) -> list[dict]:
    """Replace ``subprocess.run`` in the backend; return the recorded call kwargs."""
    calls: list[dict] = []

    def _run(argv, **kwargs):
        calls.append(kwargs)
        return subprocess.CompletedProcess(argv, returncode, json.dumps(payload) + "\n", "")

    monkeypatch.setattr(claude_cli.subprocess, "run", _run)
    return calls


def _claude_backend(tmp_path: Path) -> ClaudeCLISynthesizer:
    script = claude_tests._script(tmp_path, "claude-stub", "#!/bin/sh\nexit 0\n")
    return ClaudeCLISynthesizer(claude_path=str(script))


# @regression
@pytest.mark.parametrize(
    ("returncode", "payload"),
    [
        pytest.param(
            1,
            {"type": "result", "subtype": "success", "is_error": True,
             "api_error_status": 429, "result": _LIMIT_TEXT},
            id="nonzero-exit-429",
        ),
        pytest.param(
            0,
            {"type": "result", "subtype": "success", "is_error": True, "result": _LIMIT_TEXT},
            id="exit0-is-error-limit-text",
        ),
    ],
)
def test_claude_limit_result_raises_usage_limit_with_reset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, returncode: int, payload: dict
) -> None:
    """Both CLI branches map the quota result to ``BackendUsageLimitError`` carrying the reset time."""
    calls = _fake_claude_run(monkeypatch, returncode=returncode, payload=payload)
    backend = _claude_backend(tmp_path)

    with pytest.raises(synth_base.BackendUsageLimitError) as info:
        backend.synthesize_source_page("body", {"slug": "s1"}, claude_tests.TEMPLATE)

    assert info.value.reset == _RESET
    assert len(calls) == 1
    assert calls[0].get("start_new_session") is True


# @regression
def test_claude_non_limit_failure_stays_a_plain_cli_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A non-zero exit without the quota signal is a per-page ``ClaudeCLIError``, never a usage limit."""
    _fake_claude_run(
        monkeypatch,
        returncode=1,
        payload={"type": "result", "is_error": True, "api_error_status": 500,
                 "result": "Internal server error"},
    )
    backend = _claude_backend(tmp_path)

    with pytest.raises(ClaudeCLIError) as info:
        backend.synthesize_source_page("body", {"slug": "s1"}, claude_tests.TEMPLATE)

    assert not isinstance(info.value, synth_base.BackendUsageLimitError)


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
