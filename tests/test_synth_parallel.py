"""Tests for parallel source synthesis — spec 005-synth-parallel-and-batch-count (#118).

Grouped by slice so later slices can append their own sections:

* backend thread-safety — ``ClaudeCLISynthesizer`` usage accounting stays
  exact when pages are synthesized from several threads at once.
* concurrency setting — how the worker count is resolved from config, from
  the ``--concurrency`` flag, and from neither.
* parallel execution — pages genuinely overlap, and a parallel run produces
  exactly what a sequential one does.
* abandoned drains — an interrupt or any other escape stops the queue and
  still accounts for the pages that reached disk.

The ``claude`` CLI is never launched: the subprocess module the backend
reaches for is replaced with an in-process stub, so there is no CLI
invocation and no network.
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
import threading
import time
import types
from pathlib import Path
from unittest.mock import patch

import pytest

from llmwiki.cli import build_parser, cmd_synthesize
from llmwiki.synth import claude_cli, pipeline
from llmwiki.synth.base import DummySynthesizer
from llmwiki.synth.claude_cli import ClaudeCLISynthesizer
from llmwiki.synth.pipeline import (
    DEFAULT_SYNTH_CONCURRENCY,
    MAX_SYNTH_CONCURRENCY,
    resolve_synth_concurrency,
    synthesize_new_sessions,
)

# ─── backend thread-safety (#118 Slice 3) ────────────────────────────────

_TEMPLATE = "Summarize:\n{body}\nMeta:\n{meta}\n"

#: Token fields sum to a round number so the expected total is arithmetic,
#: and the cost is a dyadic fraction so repeated addition of it in binary
#: floating point is exact — a dropped update is then the only way the
#: totals can come out wrong.
_TOKENS_PER_CALL = 10
_COST_PER_CALL = 0.25

_STUB_STDOUT = json.dumps(
    {
        "subtype": "success",
        "result": "## Summary\n\nSynthetic page.\n",
        "usage": {
            "input_tokens": 3,
            "output_tokens": 4,
            "cache_creation_input_tokens": 2,
            "cache_read_input_tokens": 1,
        },
        "total_cost_usd": _COST_PER_CALL,
    }
)

_THREADS = 8
_CALLS_PER_THREAD = 25


class _YieldingCounters(ClaudeCLISynthesizer):
    """Backend whose usage counters hand off the GIL mid-update.

    CPython does not switch threads inside a straight-line
    ``self._run_tokens += tokens``, so a plain stress loop passes whether
    or not the arithmetic is guarded. Reading each counter through a
    property that takes the value and *then* yields puts a real thread
    switch between the read and the store, so the backend's lock becomes
    the only thing keeping the totals exact — which is what these tests
    are here to check. Verified: with the lock neutralized these counters
    lose ~85% of their updates.
    """

    @property
    def _run_tokens(self) -> int:
        value = self._tokens
        time.sleep(0.000001)
        return value

    @_run_tokens.setter
    def _run_tokens(self, value: int) -> None:
        self._tokens = value

    @property
    def _run_cost_usd(self) -> float:
        value = self._cost_usd
        time.sleep(0.000001)
        return value

    @_run_cost_usd.setter
    def _run_cost_usd(self, value: float) -> None:
        self._cost_usd = value


@pytest.fixture
def stubbed_backend(monkeypatch: pytest.MonkeyPatch) -> _YieldingCounters:
    """A claude-CLI backend whose CLI call is answered in-process."""

    def _fake_run(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 0, stdout=_STUB_STDOUT, stderr="")

    monkeypatch.setattr(
        claude_cli,
        "subprocess",
        types.SimpleNamespace(
            run=_fake_run,
            TimeoutExpired=subprocess.TimeoutExpired,
            SubprocessError=subprocess.SubprocessError,
        ),
    )
    monkeypatch.setattr(
        claude_cli,
        "_resolve_claude_path",
        lambda *_args, **_kwargs: "/usr/bin/claude-stub",
    )
    return _YieldingCounters(claude_path="/usr/bin/claude-stub")


def _drive_from_threads(
    backend: ClaudeCLISynthesizer, *, threads: int, calls_per_thread: int
) -> None:
    """Call ``synthesize_source_page`` concurrently, failing on any error."""
    ready = threading.Barrier(threads)
    failures: list[BaseException] = []

    def _worker(index: int) -> None:
        try:
            ready.wait(timeout=10)
            for call in range(calls_per_thread):
                backend.synthesize_source_page(
                    "session body", {"slug": f"s{index}-{call}"}, _TEMPLATE
                )
        except BaseException as exc:  # noqa: BLE001 — surfaced in the main thread
            failures.append(exc)

    workers = [threading.Thread(target=_worker, args=(i,)) for i in range(threads)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=60)
    assert not any(w.is_alive() for w in workers), "worker thread did not finish"
    assert not failures, failures


def test_concurrent_usage_accumulation_is_exact(
    stubbed_backend: _YieldingCounters,
) -> None:
    """Every concurrent call's tokens and cost land in the run totals.

    An unguarded ``+=`` drops updates under contention and silently
    under-reports the operator's spend, so the totals are asserted exactly.
    """
    total_calls = _THREADS * _CALLS_PER_THREAD

    _drive_from_threads(
        stubbed_backend, threads=_THREADS, calls_per_thread=_CALLS_PER_THREAD
    )

    tokens, cost = stubbed_backend.take_usage()
    assert tokens == _TOKENS_PER_CALL * total_calls
    assert cost == _COST_PER_CALL * total_calls


def test_reset_usage_clears_concurrently_accumulated_totals(
    stubbed_backend: _YieldingCounters,
) -> None:
    """After ``reset_usage`` the backend reports no usage at all."""
    _drive_from_threads(stubbed_backend, threads=_THREADS, calls_per_thread=5)
    assert stubbed_backend.take_usage() != (None, None)

    stubbed_backend.reset_usage()

    assert stubbed_backend.take_usage() == (None, None)


# ─── concurrency setting (#118 Slice 2) ──────────────────────────────────


def _mk_vault(tmp_path: Path) -> Path:
    """Empty vault: nothing to synthesize, so no backend is ever called."""
    vault = tmp_path / "vault"
    (vault / "raw" / "sessions").mkdir(parents=True, exist_ok=True)
    (vault / "raw" / "docs").mkdir(parents=True, exist_ok=True)
    (vault / "wiki" / "sources").mkdir(parents=True, exist_ok=True)
    return vault


def _announced_concurrency(tmp_path: Path, **kwargs) -> int:
    """Run synth over an empty backlog; return the announced worker count."""
    vault = _mk_vault(tmp_path)
    with patch("llmwiki.synth.pipeline.print_synth_run_start") as start:
        synthesize_new_sessions(
            backend=DummySynthesizer(),
            raw_dir=vault / "raw" / "sessions",
            docs_dir=vault / "raw" / "docs",
            wiki_sources_dir=vault / "wiki" / "sources",
            state_file=vault / "state.json",
            log_path=vault / "wiki" / "log.md",
            **kwargs,
        )
    return start.call_args.kwargs["concurrency"]


@pytest.mark.parametrize("cfg", [None, {}, {"synthesis": {}}, {"synthesis": None}])
def test_concurrency_without_the_key_is_the_shipped_default(
    cfg: dict | None, caplog: pytest.LogCaptureFixture
) -> None:
    """No saved preference means the default — and no warning about it.

    The key is absent from every stock config, so warning here would put a
    line on stderr for every operator who never touched the setting.
    """
    with caplog.at_level(logging.WARNING, logger="llmwiki.synth.pipeline"):
        assert resolve_synth_concurrency(cfg) == DEFAULT_SYNTH_CONCURRENCY
    assert caplog.records == []


@pytest.mark.parametrize("value", [1, 2, 4, MAX_SYNTH_CONCURRENCY])
def test_in_range_concurrency_passes_through(
    value: int, caplog: pytest.LogCaptureFixture
) -> None:
    """A usable value is taken as written, silently."""
    with caplog.at_level(logging.WARNING, logger="llmwiki.synth.pipeline"):
        resolved = resolve_synth_concurrency({"synthesis": {"concurrency": value}})
    assert resolved == value
    assert caplog.records == []


@pytest.mark.parametrize("value", [0, -1, "two", 2.5, True, False, None, []])
def test_unusable_concurrency_falls_back_with_a_warning(
    value: object, caplog: pytest.LogCaptureFixture
) -> None:
    """A typo in config.json degrades to the default instead of crashing sync.

    ``True``/``False`` are covered because ``bool`` is an ``int`` subclass —
    unguarded, ``True`` would quietly mean "one worker".
    """
    with caplog.at_level(logging.WARNING, logger="llmwiki.synth.pipeline"):
        resolved = resolve_synth_concurrency({"synthesis": {"concurrency": value}})

    assert resolved == DEFAULT_SYNTH_CONCURRENCY
    assert len(caplog.records) == 1
    message = caplog.records[0].getMessage()
    assert "synthesis.concurrency" in message
    assert "1" in message and str(MAX_SYNTH_CONCURRENCY) in message


def test_oversized_concurrency_is_clamped_with_a_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The cap holds: the number bounds concurrent backend subprocesses."""
    with caplog.at_level(logging.WARNING, logger="llmwiki.synth.pipeline"):
        resolved = resolve_synth_concurrency({"synthesis": {"concurrency": 999}})

    assert resolved == MAX_SYNTH_CONCURRENCY
    assert len(caplog.records) == 1
    message = caplog.records[0].getMessage()
    assert str(MAX_SYNTH_CONCURRENCY) in message


@pytest.mark.parametrize("value", ["0", "-1", str(MAX_SYNTH_CONCURRENCY + 1), "999"])
def test_cli_refuses_an_out_of_range_concurrency(
    value: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A hand-typed flag is refused, not normalized: exit 2 naming the range."""
    vault = _mk_vault(tmp_path)
    args = build_parser().parse_args(
        ["synth", "--vault", str(vault), "--concurrency", value]
    )

    assert cmd_synthesize(args) == 2

    err = capsys.readouterr().err
    assert "--concurrency" in err
    assert "1" in err and str(MAX_SYNTH_CONCURRENCY) in err


def test_cli_rejects_a_non_integer_concurrency(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """argparse refuses a non-numeric value at parse time with exit 2."""
    with pytest.raises(SystemExit) as excinfo:
        build_parser().parse_args(["synth", "--concurrency", "abc"])

    assert excinfo.value.code == 2
    assert "--concurrency" in capsys.readouterr().err


@pytest.mark.parametrize("command", ["synth", "synthesize"])
def test_help_names_the_default_and_the_range(
    command: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """The operator can find the setting without reading source.

    The deprecated alias shares the flag, so both parsers are checked.
    """
    with pytest.raises(SystemExit):
        build_parser().parse_args([command, "--help"])

    out = capsys.readouterr().out
    assert "--concurrency" in out
    assert str(DEFAULT_SYNTH_CONCURRENCY) in out
    assert f"1-{MAX_SYNTH_CONCURRENCY}" in out


def _captured_pipeline_concurrency(argv: list[str]) -> object:
    """Run ``cmd_synthesize`` with a stubbed pipeline; return its kwarg."""
    args = build_parser().parse_args(argv)
    summary = {
        "total_scanned": 0,
        "new_files": 0,
        "synthesized": 0,
        "skipped": 0,
        "errors": [],
    }
    with (
        patch("llmwiki.cli.resolve_backend", return_value=DummySynthesizer()),
        patch("llmwiki.cli.synthesize_new_sessions", return_value=summary) as synth,
    ):
        assert cmd_synthesize(args) == 0
    return synth.call_args.kwargs["concurrency"]


def test_cli_flag_wins_over_the_saved_preference(tmp_path: Path) -> None:
    """Flag beats config: the typed number is what the run receives."""
    vault = _mk_vault(tmp_path)
    argv = ["synth", "--sources-only", "--vault", str(vault), "--concurrency", "4"]

    assert _captured_pipeline_concurrency(argv) == 4


def test_cli_without_the_flag_defers_to_the_pipeline(tmp_path: Path) -> None:
    """No flag hands the pipeline ``None``, which resolves the saved value."""
    vault = _mk_vault(tmp_path)
    argv = ["synth", "--sources-only", "--vault", str(vault)]

    assert _captured_pipeline_concurrency(argv) is None


def test_saved_preference_beats_the_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Config beats default when no flag is given."""
    monkeypatch.setattr(
        pipeline, "_load_sessions_config", lambda: {"synthesis": {"concurrency": 5}}
    )

    assert _announced_concurrency(tmp_path) == 5


def test_default_applies_when_nothing_is_configured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Neither flag nor config: the run uses the shipped default."""
    monkeypatch.setattr(pipeline, "_load_sessions_config", lambda: {})

    assert _announced_concurrency(tmp_path) == DEFAULT_SYNTH_CONCURRENCY


def test_library_caller_cannot_inject_an_out_of_range_worker_count(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An explicit argument goes through the same normalization as config."""
    monkeypatch.setattr(pipeline, "_load_sessions_config", lambda: {})

    assert _announced_concurrency(tmp_path, concurrency=999) == MAX_SYNTH_CONCURRENCY
    assert _announced_concurrency(tmp_path, concurrency=0) == DEFAULT_SYNTH_CONCURRENCY


# ─── parallel execution (#118 Slice 4) ───────────────────────────────────

_DOC = """---
title: "{slug} notes"
slug: {slug}
date: 2026-08-07
project: demo
---

# {slug}

Synthetic body for {slug}.
"""


def _seed_docs(vault: Path, slugs: tuple[str, ...]) -> None:
    """Write one synthetic raw doc per slug into the vault's docs corpus."""
    docs = vault / "raw" / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    for slug in slugs:
        (docs / f"{slug}.md").write_text(_DOC.format(slug=slug), encoding="utf-8")


def _run_synth(vault: Path, backend, **kwargs) -> dict:
    """Drive a real synthesize of the vault's docs corpus."""
    return synthesize_new_sessions(
        backend=backend,
        raw_dir=vault / "raw" / "sessions",
        docs_dir=vault / "raw" / "docs",
        wiki_sources_dir=vault / "wiki" / "sources",
        state_file=vault / "state.json",
        log_path=vault / "wiki" / "log.md",
        **kwargs,
    )


def _pages(vault: Path) -> dict[str, str]:
    """Every written source page, keyed by its path relative to the vault."""
    root = vault / "wiki" / "sources"
    return {
        p.relative_to(vault).as_posix(): p.read_text(encoding="utf-8")
        for p in sorted(root.rglob("*.md"))
    }


class _RealPageBackend(DummySynthesizer):
    """Deterministic page body that carries none of the stub markers.

    The shipped dummy backend writes filler the stub guard recognises, which
    would make every one of these runs exercise the protection path instead
    of the write path.
    """

    is_llm = True

    def synthesize_source_page(self, raw_body, meta, prompt_template):  # noqa: D102
        return f"## Summary\n\nPage for {meta.get('slug')}.\n"


class _BarrierBackend(_RealPageBackend):
    """Each call waits for ``parties`` peers, so it can only finish in parallel.

    This is what makes the overlap assertion deterministic: no sleep, no
    wall-clock comparison. Either the calls genuinely run at the same time or
    the barrier times out and the run reports errors.
    """

    def __init__(self, parties: int, timeout: float = 10.0) -> None:
        self._barrier = threading.Barrier(parties, timeout=timeout)

    def synthesize_source_page(self, raw_body, meta, prompt_template):  # noqa: D102
        self._barrier.wait()
        return super().synthesize_source_page(raw_body, meta, prompt_template)


class _TrackingBackend(_RealPageBackend):
    """Records the high-water mark of calls running at the same time."""

    def __init__(self, hold_s: float = 0.02) -> None:
        self._lock = threading.Lock()
        self._live = 0
        self._hold_s = hold_s
        self.peak = 0

    def synthesize_source_page(self, raw_body, meta, prompt_template):  # noqa: D102
        with self._lock:
            self._live += 1
            self.peak = max(self.peak, self._live)
        try:
            time.sleep(self._hold_s)
            return super().synthesize_source_page(raw_body, meta, prompt_template)
        finally:
            with self._lock:
                self._live -= 1


class _FlakyBackend(_RealPageBackend):
    """Refuses the named slugs and synthesizes everything else."""

    def __init__(self, failing: set[str]) -> None:
        self._failing = failing

    def synthesize_source_page(self, raw_body, meta, prompt_template):  # noqa: D102
        slug = str(meta.get("slug"))
        if slug in self._failing:
            raise RuntimeError(f"backend refused {slug}")
        return super().synthesize_source_page(raw_body, meta, prompt_template)


def test_pages_overlap_when_concurrency_allows_it(tmp_path: Path) -> None:
    """Two pages reach the backend at once, so a two-party barrier releases."""
    vault = _mk_vault(tmp_path)
    _seed_docs(vault, ("alpha", "beta"))

    summary = _run_synth(vault, _BarrierBackend(2), concurrency=2)

    assert summary["synthesized"] == 2, summary["errors"]


def test_pages_do_not_overlap_at_concurrency_one(tmp_path: Path) -> None:
    """One worker can never satisfy a two-party barrier — the calls are serial."""
    vault = _mk_vault(tmp_path)
    _seed_docs(vault, ("alpha", "beta"))

    summary = _run_synth(vault, _BarrierBackend(2, timeout=0.5), concurrency=1)

    assert summary["synthesized"] == 0
    assert len(summary["errors"]) == 2


def test_in_flight_pages_stay_within_the_worker_count(tmp_path: Path) -> None:
    """Peak overlap rises with the setting and is exactly one when it is one."""
    slugs = tuple(f"doc{i:02d}" for i in range(6))

    parallel = _TrackingBackend()
    vault = _mk_vault(tmp_path / "parallel")
    _seed_docs(vault, slugs)
    _run_synth(vault, parallel, concurrency=4)

    serial = _TrackingBackend()
    vault = _mk_vault(tmp_path / "serial")
    _seed_docs(vault, slugs)
    _run_synth(vault, serial, concurrency=1)

    assert parallel.peak > 1
    assert parallel.peak <= 4
    assert serial.peak == 1


def test_a_parallel_run_matches_a_sequential_one(tmp_path: Path) -> None:
    """The guarantee the whole change rests on: only speed differs.

    Same corpus, same backend, different worker counts — identical pages,
    identical counters, identical producer breakdown in the log.
    """
    slugs = tuple(f"doc{i:02d}" for i in range(8))
    seen = {}
    for label, concurrency in (("serial", 1), ("parallel", 4)):
        vault = _mk_vault(tmp_path / label)
        _seed_docs(vault, slugs)
        summary = _run_synth(vault, _RealPageBackend(), concurrency=concurrency)
        log = (vault / "wiki" / "log.md").read_text(encoding="utf-8")
        processed = [ln for ln in log.splitlines() if ln.startswith("- Processed:")]
        seen[label] = (summary, _pages(vault), processed)

    serial_summary, serial_pages, serial_log = seen["serial"]
    parallel_summary, parallel_pages, parallel_log = seen["parallel"]

    assert parallel_pages == serial_pages
    assert parallel_pages  # the comparison would be vacuous on an empty run
    for key in ("total_scanned", "new_files", "synthesized", "skipped", "protected"):
        assert parallel_summary[key] == serial_summary[key], key
    assert parallel_log == serial_log


def test_every_result_line_carries_its_position(tmp_path: Path, capsys) -> None:
    """Positions count completed sources and end at the announced total."""
    vault = _mk_vault(tmp_path)
    slugs = tuple(f"doc{i:02d}" for i in range(5))
    _seed_docs(vault, slugs)

    _run_synth(vault, _RealPageBackend(), concurrency=3)

    out = capsys.readouterr().out
    positions = [int(n) for n in re.findall(r"(?m)^  \[(\d+)/5\] synthesized: ", out)]
    # Completion order is not deterministic above one worker, so compare the
    # set of positions rather than the sequence they arrived in.
    assert sorted(positions) == [1, 2, 3, 4, 5]


def test_one_failing_source_does_not_stop_the_batch(
    tmp_path: Path, capsys
) -> None:
    """A refused page is reported and left unrecorded; the rest still land."""
    vault = _mk_vault(tmp_path)
    _seed_docs(vault, ("alpha", "beta", "gamma"))

    summary = _run_synth(vault, _FlakyBackend({"beta"}), concurrency=3)

    assert summary["synthesized"] == 2
    assert summary["skipped"] == 1
    assert any("beta" in err for err in summary["errors"])
    assert re.search(r"(?m)^  \[\d+/3\] error: beta: ", capsys.readouterr().out)

    # The failed source keeps no state entry, so a re-run retries exactly it.
    files = json.loads((vault / "state.json").read_text(encoding="utf-8"))["synth"]["files"]
    assert len(files) == 2
    assert not any("beta" in key for key in files)


def test_a_placeholder_never_replaces_a_real_page_under_concurrency(
    tmp_path: Path,
) -> None:
    """Stub protection survives the move onto worker threads."""
    vault = _mk_vault(tmp_path)
    _seed_docs(vault, ("alpha", "beta"))
    _run_synth(vault, _RealPageBackend(), concurrency=2)
    before = _pages(vault)
    assert before

    summary = _run_synth(vault, DummySynthesizer(), concurrency=2, force=True)

    assert summary["protected"] == len(before)
    assert _pages(vault) == before


def test_the_run_appends_exactly_one_log_entry(tmp_path: Path) -> None:
    """One entry per invocation, not one per page, however many ran at once."""
    vault = _mk_vault(tmp_path)
    _seed_docs(vault, ("alpha", "beta", "gamma"))

    _run_synth(vault, _RealPageBackend(), concurrency=3)

    log = (vault / "wiki" / "log.md").read_text(encoding="utf-8")
    assert log.count("] synthesize | ") == 1


def test_the_index_is_not_rebuilt_when_nothing_was_synthesized(
    tmp_path: Path,
) -> None:
    """The empty-queue run skips the whole-wiki index walk."""
    vault = _mk_vault(tmp_path)

    with patch("llmwiki.synth.pipeline._rebuild_index") as rebuild:
        summary = _run_synth(vault, _RealPageBackend(), concurrency=2)

    assert summary["synthesized"] == 0
    rebuild.assert_not_called()


# ─── an abandoned drain leaves the queue alone (#118) ─────────────────────


class _GatedBackend(_RealPageBackend):
    """Lets the first ``free`` calls through, then holds the rest at a gate.

    Counting the calls that reach the backend is how these tests see what an
    abandoned drain cost: with the queue cancelled the count cannot exceed
    the pages already in flight, and without cancellation every source in the
    batch reaches the backend before the failure surfaces.
    """

    def __init__(self, free: int) -> None:
        self._lock = threading.Lock()
        self._free = free
        self.gate = threading.Event()
        self.calls = 0

    def synthesize_source_page(self, raw_body, meta, prompt_template):  # noqa: D102
        with self._lock:
            self.calls += 1
            held = self.calls > self._free
        if held and not self.gate.wait(timeout=10.0):
            raise AssertionError("the gate was never released")
        return super().synthesize_source_page(raw_body, meta, prompt_template)


def _synth_state(vault: Path) -> dict:
    """The synth file map recorded for the vault; empty when never written."""
    path = vault / "state.json"
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    return raw.get("synth", {}).get("files", {})


def test_a_drain_side_failure_does_not_run_the_rest_of_the_queue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An escape from the drain stops the batch instead of paying it out.

    ``ThreadPoolExecutor.__exit__`` shuts down with ``wait=True`` and no
    cancellation, so an unhandled drain failure would work through every page
    still queued — a whole catch-up backlog of billed backend calls — before
    the traceback ever surfaced.
    """
    vault = _mk_vault(tmp_path)
    slugs = tuple(f"doc{i:02d}" for i in range(12))
    _seed_docs(vault, slugs)
    backend = _GatedBackend(free=2)
    real_save_state = pipeline._save_state
    saves = {"n": 0}

    def _save_state(state, state_file=None):
        saves["n"] += 1
        if saves["n"] == 2:
            # Release first: the workers already running then finish on their
            # own, so what the batch costs is decided by cancelling the queue
            # rather than by how fast the drain wins a race against it.
            backend.gate.set()
            raise OSError("state file is read-only")
        real_save_state(state, state_file)

    monkeypatch.setattr(pipeline, "_save_state", _save_state)

    with pytest.raises(OSError, match="read-only"):
        _run_synth(vault, backend, concurrency=2)

    # Two workers: the two drained completions plus the two items those
    # workers picked up next is everything that can have reached the backend.
    assert backend.calls <= 4
    assert backend.calls < len(slugs)
    # The sources never touched stay out of the state, so a re-run does them.
    written = _pages(vault)
    assert len(written) <= 4
    assert len(_synth_state(vault)) == len(written)


def test_a_failure_deriving_the_page_is_reported_not_raised(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Chunking one source can fail without tearing down the whole drain.

    The work a source needs before its first backend call is inside the same
    guard as the call itself, so a failure there is an ordinary ``error``
    record — one bad source, not a lost batch.
    """
    vault = _mk_vault(tmp_path)
    _seed_docs(vault, ("alpha", "beta", "gamma"))
    real_chunk = pipeline._chunk_markdown
    # The estimate pass chunks the same bodies with the module default, so
    # the run carries its own budget and only that one is made to fail.
    budget = 123_456

    def _chunk_markdown(text: str, max_chars: int) -> list[str]:
        if max_chars == budget and "beta" in text:
            raise ValueError("cannot chunk beta")
        return real_chunk(text, max_chars)

    monkeypatch.setattr(pipeline, "_chunk_markdown", _chunk_markdown)

    summary = _run_synth(
        vault, _RealPageBackend(), concurrency=3, doc_chunk_max_chars=budget
    )

    assert summary["synthesized"] == 2
    assert summary["skipped"] == 1
    assert any(err.startswith("beta: ") for err in summary["errors"])
    assert not any("beta" in key for key in _synth_state(vault))


def test_an_interrupt_records_the_pages_that_reached_disk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """A written page is never invisible to the resume.

    Ctrl-C cancels the queue, but every worker already running writes its
    page all the same, and its future is never drained. Unrecorded, those
    pages are synthesized — and billed — a second time on the next run.
    """
    vault = _mk_vault(tmp_path)
    slugs = ("alpha", "beta", "gamma")
    _seed_docs(vault, slugs)
    real_save_state = pipeline._save_state
    saves = {"n": 0}

    def _save_state(state, state_file=None):
        saves["n"] += 1
        if saves["n"] == 1:
            raise KeyboardInterrupt
        real_save_state(state, state_file)

    monkeypatch.setattr(pipeline, "_save_state", _save_state)

    with pytest.raises(KeyboardInterrupt):
        _run_synth(vault, _RealPageBackend(), concurrency=3)

    assert f"Interrupted after 1/{len(slugs)} source(s)" in capsys.readouterr().out
    assert len(_pages(vault)) == len(slugs)
    assert len(_synth_state(vault)) == len(slugs)

    # The resume has nothing left to do — no page is synthesized twice.
    monkeypatch.setattr(pipeline, "_save_state", real_save_state)
    resumed = _run_synth(vault, _RealPageBackend(), concurrency=3)

    assert resumed["new_files"] == 0
    assert resumed["synthesized"] == 0


# ─── log entry stays inside the vault it describes ───────────────────────


def test_the_log_entry_lands_in_the_vault_that_was_synthesized(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A vault-scoped run records its history in that vault, not the fallback.

    Callers scope a run by passing ``wiki_sources_dir`` alone, so a log path
    taken from the module-level fallback would file every vault's entry into
    whichever wiki the package happens to sit next to.
    """
    fallback = tmp_path / "fallback-wiki"
    (fallback / "sources").mkdir(parents=True)
    monkeypatch.setattr(pipeline, "WIKI_LOG", fallback / "log.md")
    monkeypatch.setattr(pipeline, "WIKI_SOURCES", fallback / "sources")

    vault = _mk_vault(tmp_path)
    _seed_docs(vault, ("alpha", "beta"))

    summary = synthesize_new_sessions(
        backend=_RealPageBackend(),
        raw_dir=vault / "raw" / "sessions",
        docs_dir=vault / "raw" / "docs",
        wiki_sources_dir=vault / "wiki" / "sources",
        state_file=vault / "state.json",
        concurrency=2,
    )

    assert summary["synthesized"] == 2
    vault_log = vault / "wiki" / "log.md"
    assert vault_log.exists()
    assert "] synthesize | " in vault_log.read_text(encoding="utf-8")
    assert not (fallback / "log.md").exists()


def test_an_explicit_log_path_still_wins(tmp_path: Path) -> None:
    """The override callers already pass keeps taking precedence."""
    vault = _mk_vault(tmp_path)
    _seed_docs(vault, ("alpha",))
    chosen = tmp_path / "chosen-wiki"
    chosen.mkdir()

    synthesize_new_sessions(
        backend=_RealPageBackend(),
        raw_dir=vault / "raw" / "sessions",
        docs_dir=vault / "raw" / "docs",
        wiki_sources_dir=vault / "wiki" / "sources",
        state_file=vault / "state.json",
        log_path=chosen / "log.md",
        concurrency=1,
    )

    assert "] synthesize | " in (chosen / "log.md").read_text(encoding="utf-8")
    assert not (vault / "wiki" / "log.md").exists()
