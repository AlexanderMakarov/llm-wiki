"""Whole-feature acceptance tests for #118: synth batch count + parallel synthesis.

# @layer: integration
# @spec: 005-synth-parallel-and-batch-count
# @regression

``tests/test_synth_parallel.py`` (backend thread-safety, concurrency resolution,
CLI flag validation) and ``tests/test_synth_run_summary.py`` (start-line
content, position formatting, failure isolation, stub protection, log/index
gating) already give this feature thorough **unit** coverage — but almost
every one of those tests drives ``synthesize_new_sessions`` directly, or
mocks it out from behind ``cmd_synthesize``. This file drives the same
guarantees through the **CLI entry point** instead — ``llmwiki.cli.main`` via
subprocess, or ``cmd_synthesize`` with a real ``argv`` — because that is what
an operator actually runs, and a few things (concurrency precedence end to
end, ``--force``/``--concurrency``/``--sources-only``/``--vault`` composing,
the post-harvest summary after a real parallel run, ``all --with-synth``
reading config with no matching flag) are only visible from there.

AC coverage matrix (functional-spec.md FR1-FR6; 24 acceptance criteria):

    FR1.1 start line precedes first page line   -> test_start_line_precedes_first_page_line_over_the_cli
    FR1.2 start line names backend + concurrency -> test_start_line_precedes_first_page_line_over_the_cli
    FR1.3 empty backlog says so plainly          -> test_empty_backlog_reports_nothing_to_synthesize_over_the_cli
    FR1.4 count excludes dedup-claimed sources   -> test_start_count_excludes_dedup_claimed_sources_over_the_cli
    FR2.1 more than one page at once (default)   -> test_default_run_overlaps_two_pages_over_the_cli
    FR2.2 default run is faster than serial      -> not timing-tested (spec forbids wall-clock asserts);
                                                     satisfied deterministically by FR2.1 + FR3 overlap/bound tests
    FR2.3 parallel run matches sequential run    -> test_parallel_and_sequential_cli_runs_produce_identical_results
    FR3.1 no pref/no flag -> 2, start line says  -> test_start_line_precedes_first_page_line_over_the_cli (+ FR2.1)
    FR3.2 flag sets the count, start line reflects -> test_flag_sets_and_caps_the_worker_count
    FR3.3 saved pref used, no flag given         -> test_saved_preference_is_used_and_enforced_without_a_flag
    FR3.4 flag wins over saved pref              -> test_flag_overrides_the_saved_preference
    FR3.5 concurrency=1 is strictly sequential   -> test_concurrency_one_runs_strictly_sequentially
    FR3.6 out-of-range/non-integer -> clear msg  -> already CLI-level: test_synth_parallel.py::
                                                     test_cli_refuses_an_out_of_range_concurrency /
                                                     test_cli_rejects_a_non_integer_concurrency — not duplicated
    FR4.1 result line shows completed/total      -> test_progress_positions_count_completions_and_end_at_batch_total
    FR4.2 last completed position == total       -> test_progress_positions_count_completions_and_end_at_batch_total
    FR4.3 error line also carries a position     -> test_error_lines_carry_a_position_too
    FR5.1 one failure -> rest complete, reported, not recorded done -> test_one_failure_leaves_rest_complete_and_resumes_only_it
    FR5.2 interrupted run resumes only the remainder                -> test_one_failure_leaves_rest_complete_and_resumes_only_it
    FR5.3 placeholder never replaces a real page, same message      -> test_placeholder_protection_survives_force_and_concurrency_composed
    FR5.4 harvest accounts for every page the run wrote              -> test_harvest_and_end_of_run_accounting_match_a_real_parallel_run
    FR5.5 log entry + end-of-run summary match pages written         -> test_harvest_and_end_of_run_accounting_match_a_real_parallel_run
                                                                         (summary line only — the log entry's own producer
                                                                         breakdown is unreachable through cmd_synthesize
                                                                         without writing into the real repo, see
                                                                         _isolate_synth_log; already covered at the pipeline
                                                                         layer by test_synth_parallel.py::
                                                                         test_a_parallel_run_matches_a_sequential_one)
    FR6.1 help text names the option + default   -> already CLI-level: test_synth_parallel.py::
                                                     test_help_names_the_default_and_the_range — not duplicated
    FR6.2 CLI reference doc lists option + default -> test_cli_reference_documents_the_concurrency_flag
    FR6.3 release notes describe the change      -> test_changelog_unreleased_section_describes_the_change

Also covered (Scope: "applies wherever synth runs as part of a larger
pipeline run" / "`all --with-synth` reads config only (no flag)"):

    test_all_with_synth_has_no_concurrency_flag_on_the_command_line
    test_all_with_synth_honours_config_concurrency_with_no_flag_to_set_it

And composition, called out explicitly for this slice:

    test_sources_only_force_concurrency_and_vault_compose
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from llmwiki import cli as cli_mod
from llmwiki import pipeline as pipeline_mod
from llmwiki.cli import build_parser, cmd_synthesize
from llmwiki.synth import pipeline as synth_pipeline
from llmwiki.synth.base import DummySynthesizer

REPO_ROOT = Path(__file__).resolve().parents[1]

_START_LINE = re.compile(
    r"(?m)^Synthesizing (\d+) source\(s\) with (\S+) \((\d+) at a time\)$"
)
_NOTHING_LINE = "Nothing to synthesize — every source is already up to date."
_SYNTH_LINE = re.compile(r"(?m)^  \[(\d+)/(\d+)\] synthesized: ")
_ERROR_LINE = re.compile(r"(?m)^  \[(\d+)/(\d+)\] error: (\S+): ")
_PROTECTED_LINE = re.compile(r"(?m)^  \[(\d+)/(\d+)\] protected: ")
_SUMMARY_LINE = re.compile(r"(?m)^Synthesized:\s+(\d+)\s*$")


# ─── shared fixtures ──────────────────────────────────────────────────────

_DOC = """---
title: "{slug} notes"
slug: {slug}
---

# {slug}

Synthetic fixture body for the #118 acceptance suite.
"""

_CLAIMING_PAGE = """---
title: "Hand-written notes"
type: source
tags: [manual]
source_file: raw/docs/{slug}.md
project: manual
---

## Summary

A real page with link data, filed outside the derived slug scheme.

## Connections

- [[Synthesis]] — the pipeline that would otherwise duplicate this page
"""


def _mk_vault(tmp_path: Path) -> Path:
    """Empty vault with the directory shape ``synthesize_new_sessions`` expects."""
    vault = tmp_path / "vault"
    (vault / "raw" / "sessions").mkdir(parents=True, exist_ok=True)
    (vault / "raw" / "docs").mkdir(parents=True, exist_ok=True)
    (vault / "wiki" / "sources").mkdir(parents=True, exist_ok=True)
    return vault


def _seed_docs(vault: Path, slugs: tuple[str, ...]) -> None:
    """Write one synthetic raw doc per slug into ``<vault>/raw/docs``."""
    for slug in slugs:
        (vault / "raw" / "docs" / f"{slug}.md").write_text(
            _DOC.format(slug=slug), encoding="utf-8"
        )


def _claim_source(vault: Path, slug: str) -> None:
    """Add a real source page claiming ``raw/docs/<slug>.md`` (dedup guard)."""
    page = vault / "wiki" / "sources" / "manual" / f"{slug}-notes.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(_CLAIMING_PAGE.format(slug=slug), encoding="utf-8")


def _pages(vault: Path) -> dict[str, str]:
    """Every written source page, keyed by its path relative to the vault."""
    root = vault / "wiki" / "sources"
    return {
        p.relative_to(vault).as_posix(): p.read_text(encoding="utf-8")
        for p in sorted(root.rglob("*.md"))
    }


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    """Invoke the real ``python3 -m llmwiki`` entry point as a subprocess."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT) + (
        os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )
    return subprocess.run(
        [sys.executable, "-m", "llmwiki", *args],
        capture_output=True,
        text=True,
        check=False,
        env=env,
        cwd=str(REPO_ROOT),
    )


def _run_synth(argv: list[str]) -> int:
    """Parse ``argv`` with the real parser and call ``cmd_synthesize`` — the
    same call shape ``llmwiki.cli.main`` uses. Prefer this over patching
    ``synthesize_new_sessions`` so tests exercise the real pipeline call."""
    return cmd_synthesize(build_parser().parse_args(argv))


@pytest.fixture(autouse=True)
def _isolate_synth_log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep every real synth run in this module off the checked-out repo's
    own ``wiki/log.md``.

    A ``--vault <tmp>`` run resolves its log entry inside that vault, so the
    tests here are already isolated by construction. This fixture is the
    belt-and-braces guard for anything that still reaches the pipeline's
    module-level ``WIKI_LOG`` fallback — an unscoped run, or a test added
    later that forgets to name a vault — because that constant points into
    this repository's own working tree.
    """
    monkeypatch.setattr(synth_pipeline, "WIKI_LOG", tmp_path / "unused-repo-log.md")


class _DeterministicBackend(DummySynthesizer):
    """Real (non-stub) page content with no randomness, for parity checks."""

    is_llm = True

    def __init__(self, marker: str = "content") -> None:
        self._marker = marker

    def synthesize_source_page(self, raw_body, meta, prompt_template):  # noqa: D102
        return f"## Summary\n\nPage for {meta.get('slug')} ({self._marker}).\n"


class _BarrierBackend(DummySynthesizer):
    """A page can only finish once ``parties`` calls are in flight together.

    Proves *at least* that many pages overlap without any wall-clock
    assertion: either the calls genuinely coincide or the barrier times out
    and the run reports errors instead of silently going serial.
    """

    is_llm = True

    def __init__(self, parties: int, timeout: float = 5.0) -> None:
        self._barrier = threading.Barrier(parties, timeout=timeout)

    def synthesize_source_page(self, raw_body, meta, prompt_template):  # noqa: D102
        self._barrier.wait()
        return f"## Summary\n\nPage for {meta.get('slug')}.\n"


class _TrackingBackend(DummySynthesizer):
    """Records the high-water mark of calls running at the same time.

    Used where the acceptance criterion is an *upper bound* ("no more than
    N at once") rather than "at least N" — a barrier can only prove a lower
    bound; only a live counter can prove pages never exceed the setting.
    """

    is_llm = True

    def __init__(self, hold_s: float = 0.03) -> None:
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
            return f"## Summary\n\nPage for {meta.get('slug')}.\n"
        finally:
            with self._lock:
                self._live -= 1


class _FlakyBackend(DummySynthesizer):
    """Refuses the named slugs and synthesizes everything else."""

    is_llm = True

    def __init__(self, failing: set[str]) -> None:
        self._failing = failing

    def synthesize_source_page(self, raw_body, meta, prompt_template):  # noqa: D102
        slug = str(meta.get("slug"))
        if slug in self._failing:
            raise RuntimeError(f"backend refused {slug}")
        return f"## Summary\n\nPage for {slug}.\n"


class _LinkedPageBackend(DummySynthesizer):
    """Writes real pages that reference ``[[Recurring]]``, and doubles as the
    harvest classifier — ``run_harvest`` classifies through the same
    ``synthesize_source_page`` call, distinguished by ``meta["slug"]``.
    """

    is_llm = True

    def synthesize_source_page(self, raw_body, meta, prompt_template):  # noqa: D102
        if meta.get("slug") == "candidate-classification":
            return "Recurring: entity\n"
        return (
            f"## Summary\n\nPage for {meta.get('slug')}.\n\n"
            "## Connections\n\n- [[Recurring]]\n"
        )


# ─── FR1 — batch size announced before the first page (CLI-driven) ───────


def test_start_line_precedes_first_page_line_over_the_cli(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR1.1/FR1.2/FR3.1: a real ``llmwiki synth`` prints the batch size,
    backend name, and worker count before any per-page result line reaches
    stdout — with no ``--concurrency`` flag and no saved preference."""
    monkeypatch.setattr(
        "llmwiki.cli.resolve_backend", lambda cfg: DummySynthesizer()
    )
    vault = _mk_vault(tmp_path)
    _seed_docs(vault, ("alpha", "beta"))

    rc = _run_synth(["synth", "--sources-only", "--vault", str(vault)])
    out = capsys.readouterr().out
    assert rc == 0, out

    start = _START_LINE.search(out)
    first_page = _SYNTH_LINE.search(out)
    assert start is not None, out
    assert first_page is not None, out
    assert start.start() < first_page.start()
    assert int(start.group(1)) == 2
    assert start.group(2) == DummySynthesizer().name
    assert int(start.group(3)) == 2  # documented default


def test_empty_backlog_reports_nothing_to_synthesize_over_the_cli(
    tmp_path: Path,
) -> None:
    """FR1.3: an up-to-date vault says so plainly through the real CLI, not
    silence and not an announced batch of zero."""
    vault = _mk_vault(tmp_path)

    cp = _run_cli("synth", "--sources-only", "--vault", str(vault))
    assert cp.returncode == 0, cp.stderr
    assert _NOTHING_LINE in cp.stdout
    assert _START_LINE.search(cp.stdout) is None, cp.stdout


def test_start_count_excludes_dedup_claimed_sources_over_the_cli(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """FR1.4: a source already claimed by a real hand-written page is
    skipped before the count is announced, and does not inflate it."""
    vault = _mk_vault(tmp_path)
    _seed_docs(vault, ("alpha", "beta", "gamma"))
    _claim_source(vault, "gamma")

    rc = _run_synth(["synth", "--sources-only", "--vault", str(vault)])
    out = capsys.readouterr().out
    assert rc == 0, out

    start = _START_LINE.search(out)
    assert start is not None, out
    assert int(start.group(1)) == 2
    assert "not duplicating)" in out
    assert len(_SYNTH_LINE.findall(out)) == 2


# ─── FR2 — several pages at once, and only speed/reporting differs ───────


def test_default_run_overlaps_two_pages_over_the_cli(tmp_path: Path) -> None:
    """FR2.1: with no ``--concurrency`` flag and no saved preference, a real
    ``cmd_synthesize`` call genuinely runs two pages at once — a two-party
    barrier can only release if both calls are in flight together."""
    vault = _mk_vault(tmp_path)
    _seed_docs(vault, ("alpha", "beta"))

    with patch("llmwiki.cli.resolve_backend", return_value=_BarrierBackend(2)):
        rc = _run_synth(["synth", "--sources-only", "--vault", str(vault)])

    assert rc == 0


def test_parallel_and_sequential_cli_runs_produce_identical_results(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """FR2.3: the guarantee the whole feature rests on, proven through the
    CLI's own printed summary — not just the pipeline's return dict. Same
    corpus, same backend, concurrency 1 vs 4: identical pages and identical
    ``Scanned``/``Synthesized:`` lines. (The log entry's own equivalence is
    covered at the pipeline layer in test_synth_parallel.py — ``cmd_synthesize``
    does not forward a vault-scoped log path, see ``_isolate_synth_log``
    above, so it has nothing to compare here without touching the real repo.)
    """
    slugs = tuple(f"doc{i:02d}" for i in range(6))
    seen: dict[str, tuple[str, dict[str, str]]] = {}

    for label, concurrency in (("serial", "1"), ("parallel", "4")):
        vault = _mk_vault(tmp_path / label)
        _seed_docs(vault, slugs)
        with patch(
            "llmwiki.cli.resolve_backend", return_value=_DeterministicBackend()
        ):
            rc = _run_synth(
                [
                    "synth",
                    "--sources-only",
                    "--vault",
                    str(vault),
                    "--concurrency",
                    concurrency,
                ]
            )
        assert rc == 0
        out = capsys.readouterr().out
        scanned_line = next(
            ln for ln in out.splitlines() if ln.startswith("Scanned ")
        )
        summary_line = _SUMMARY_LINE.search(out)
        assert summary_line is not None, out
        seen[label] = (scanned_line + "|" + summary_line.group(0), _pages(vault))

    serial_line, serial_pages = seen["serial"]
    parallel_line, parallel_pages = seen["parallel"]

    assert parallel_pages == serial_pages
    assert parallel_pages  # would be vacuous on an empty run
    assert parallel_line == serial_line


# ─── FR3 — the operator can change how many pages run at once ────────────


def test_flag_sets_and_caps_the_worker_count(tmp_path: Path) -> None:
    """FR3.2: ``--concurrency 3`` is both announced in the start line and
    actually enforced as an upper bound on in-flight pages."""
    vault = _mk_vault(tmp_path)
    _seed_docs(vault, tuple(f"doc{i:02d}" for i in range(6)))
    backend = _TrackingBackend()

    with patch("llmwiki.cli.resolve_backend", return_value=backend):
        rc = _run_synth(
            ["synth", "--sources-only", "--vault", str(vault), "--concurrency", "3"]
        )

    assert rc == 0
    assert backend.peak > 1, "no overlap observed — test would be vacuous"
    assert backend.peak <= 3


def test_saved_preference_is_used_and_enforced_without_a_flag(
    tmp_path: Path,
) -> None:
    """FR3.3: with no ``--concurrency`` on the command line, the saved
    ``synthesis.concurrency`` preference is what actually bounds in-flight
    pages — not just what the start line happens to print."""
    vault = _mk_vault(tmp_path)
    _seed_docs(vault, tuple(f"doc{i:02d}" for i in range(6)))
    backend = _TrackingBackend()

    with (
        patch("llmwiki.cli.resolve_backend", return_value=backend),
        patch.object(
            synth_pipeline,
            "_load_sessions_config",
            lambda: {"synthesis": {"concurrency": 3}},
        ),
    ):
        rc = _run_synth(["synth", "--sources-only", "--vault", str(vault)])

    assert rc == 0
    assert backend.peak > 1, "no overlap observed — test would be vacuous"
    assert backend.peak <= 3


def test_flag_overrides_the_saved_preference(tmp_path: Path) -> None:
    """FR3.4: a saved preference of 6 is present, but ``--concurrency 2`` on
    the command line is what actually governs the run — proven by an upper
    bound the larger config value would not have enforced."""
    vault = _mk_vault(tmp_path)
    _seed_docs(vault, tuple(f"doc{i:02d}" for i in range(6)))
    backend = _TrackingBackend()

    with (
        patch("llmwiki.cli.resolve_backend", return_value=backend),
        patch.object(
            synth_pipeline,
            "_load_sessions_config",
            lambda: {"synthesis": {"concurrency": 6}},
        ),
    ):
        rc = _run_synth(
            ["synth", "--sources-only", "--vault", str(vault), "--concurrency", "2"]
        )

    assert rc == 0
    assert backend.peak > 1, "no overlap observed — test would be vacuous"
    assert backend.peak <= 2, "the saved preference (6) leaked through the flag"


def test_concurrency_one_runs_strictly_sequentially(tmp_path: Path) -> None:
    """FR3.5: ``--concurrency 1`` behaves exactly as today — one page at a
    time, never two in flight together."""
    vault = _mk_vault(tmp_path)
    _seed_docs(vault, tuple(f"doc{i:02d}" for i in range(4)))
    backend = _TrackingBackend()

    with patch("llmwiki.cli.resolve_backend", return_value=backend):
        rc = _run_synth(
            ["synth", "--sources-only", "--vault", str(vault), "--concurrency", "1"]
        )

    assert rc == 0
    assert backend.peak == 1


# ─── FR4 — progress positions on every result and error line ─────────────


def test_progress_positions_count_completions_and_end_at_batch_total(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """FR4.1/FR4.2: every synthesized-page line carries a completed/total
    position, and the highest position reached equals the announced total."""
    vault = _mk_vault(tmp_path)
    slugs = tuple(f"doc{i:02d}" for i in range(5))
    _seed_docs(vault, slugs)

    with patch(
        "llmwiki.cli.resolve_backend", return_value=_DeterministicBackend()
    ):
        rc = _run_synth(
            ["synth", "--sources-only", "--vault", str(vault), "--concurrency", "3"]
        )

    assert rc == 0
    out = capsys.readouterr().out
    matches = _SYNTH_LINE.findall(out)
    totals = {int(total) for _pos, total in matches}
    positions = sorted(int(pos) for pos, _total in matches)

    assert totals == {5}
    assert positions == [1, 2, 3, 4, 5]
    assert max(positions) == 5  # last completed page's position == the batch total


def test_error_lines_carry_a_position_too(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """FR4.3: a failing page's error line still carries its position, so a
    run with a failure still reads as progressing rather than stalling."""
    vault = _mk_vault(tmp_path)
    _seed_docs(vault, ("alpha", "beta", "gamma"))

    with patch(
        "llmwiki.cli.resolve_backend", return_value=_FlakyBackend({"beta"})
    ):
        rc = _run_synth(
            ["synth", "--sources-only", "--vault", str(vault), "--concurrency", "3"]
        )

    assert rc == 1
    out = capsys.readouterr().out
    err_match = _ERROR_LINE.search(out)
    assert err_match is not None, out
    assert err_match.group(3) == "beta"
    assert int(err_match.group(2)) == 3  # total is still the full queue


# ─── FR5 — nothing else about the result changes ──────────────────────────


def test_one_failure_leaves_rest_complete_and_resumes_only_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """FR5.1/FR5.2: a failing source does not stop the rest of the batch and
    is not recorded as done — so a second real ``synth`` invocation (as an
    interrupted-run resume would look) synthesizes exactly the remainder."""
    vault = _mk_vault(tmp_path)
    _seed_docs(vault, ("alpha", "beta", "gamma"))

    with patch(
        "llmwiki.cli.resolve_backend", return_value=_FlakyBackend({"beta"})
    ):
        rc1 = _run_synth(
            ["synth", "--sources-only", "--vault", str(vault), "--concurrency", "3"]
        )
    out1 = capsys.readouterr().out

    assert rc1 == 1
    assert len(_SYNTH_LINE.findall(out1)) == 2
    assert "beta" in out1

    state = json.loads(
        (vault / "llmwiki-state.json").read_text(encoding="utf-8")
    )
    files = state.get("synth", {}).get("files", {})
    assert not any("beta" in key for key in files)

    with patch(
        "llmwiki.cli.resolve_backend", return_value=_DeterministicBackend()
    ):
        rc2 = _run_synth(["synth", "--sources-only", "--vault", str(vault)])
    out2 = capsys.readouterr().out

    assert rc2 == 0
    start2 = _START_LINE.search(out2)
    assert start2 is not None, out2
    assert int(start2.group(1)) == 1  # only the previously-failed source
    assert "beta" in out2
    assert "alpha" not in out2
    assert "gamma" not in out2


def test_placeholder_protection_survives_force_and_concurrency_composed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """FR5.3, composed with --force/--concurrency: a stub-producing backend
    must never clobber a real page, even under ``--force`` and several
    workers at once — and the operator sees the same 'kept real page'
    message as a sequential run would give."""
    vault = _mk_vault(tmp_path)
    _seed_docs(vault, ("alpha", "beta"))

    with patch(
        "llmwiki.cli.resolve_backend", return_value=_DeterministicBackend()
    ):
        rc1 = _run_synth(["synth", "--sources-only", "--vault", str(vault)])
    assert rc1 == 0
    before = _pages(vault)
    assert before

    with patch("llmwiki.cli.resolve_backend", return_value=DummySynthesizer()):
        rc2 = _run_synth(
            [
                "synth",
                "--sources-only",
                "--force",
                "--concurrency",
                "2",
                "--vault",
                str(vault),
            ]
        )
    out2 = capsys.readouterr().out

    assert rc2 == 0
    assert _pages(vault) == before
    protected = _PROTECTED_LINE.findall(out2)
    assert len(protected) == len(before)
    assert "kept real page; stub not written" in out2


def test_harvest_and_end_of_run_accounting_match_a_real_parallel_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """FR5.4/FR5.5: a default (non-``--sources-only``) run harvests candidates
    from the pages *this* run just wrote, and the end-of-run ``Synthesized:``
    line matches the pages actually on disk — proven against a real
    ``--concurrency 3`` run, not a mocked one. (The log entry's own producer
    breakdown is covered at the pipeline layer in
    ``test_synth_parallel.py::test_a_parallel_run_matches_a_sequential_one``;
    see ``_isolate_synth_log`` above for why this file cannot check it
    through ``cmd_synthesize`` without touching the real repo.)"""
    vault = _mk_vault(tmp_path)
    _seed_docs(vault, ("alpha", "beta", "gamma"))

    with patch("llmwiki.cli.resolve_backend", return_value=_LinkedPageBackend()):
        rc = _run_synth(["synth", "--concurrency", "3", "--vault", str(vault)])
    out = capsys.readouterr().out

    assert rc == 0, out
    pages = _pages(vault)
    assert len(pages) == 3

    start = _START_LINE.search(out)
    assert start is not None, out
    assert int(start.group(1)) == 3
    assert int(start.group(3)) == 3

    # Harvest ran on the pages this run just wrote (min-refs default is 3,
    # and exactly 3 sources reference [[Recurring]]).
    assert "Candidates: 1 stub(s) at --min-refs 3" in out, out

    summary = _SUMMARY_LINE.search(out)
    assert summary is not None, out
    assert int(summary.group(1)) == len(pages) == 3


def test_sources_only_force_concurrency_and_vault_compose(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Explicit composition check: ``--sources-only``, ``--force``,
    ``--concurrency``, and ``--vault`` all take effect together in one run —
    force re-synthesizes into the given vault at the given worker count,
    without triggering the harvest ``--sources-only`` skips."""
    vault = _mk_vault(tmp_path)
    _seed_docs(vault, ("alpha", "beta", "gamma"))

    with patch(
        "llmwiki.cli.resolve_backend", return_value=_DeterministicBackend("v1")
    ):
        rc1 = _run_synth(["synth", "--sources-only", "--vault", str(vault)])
    capsys.readouterr()
    assert rc1 == 0
    v1_pages = _pages(vault)
    assert all("v1" in body for body in v1_pages.values())

    with patch(
        "llmwiki.cli.resolve_backend", return_value=_DeterministicBackend("v2")
    ):
        rc2 = _run_synth(
            [
                "synth",
                "--sources-only",
                "--force",
                "--concurrency",
                "3",
                "--vault",
                str(vault),
            ]
        )
    out = capsys.readouterr().out

    assert rc2 == 0, out
    assert "Scanned 3, new 3, synthesized 3, skipped 0" in out
    start = _START_LINE.search(out)
    assert start is not None, out
    assert int(start.group(3)) == 3
    v2_pages = _pages(vault)
    assert set(v2_pages) == set(v1_pages)
    assert all("v2" in body for body in v2_pages.values())
    assert "Candidates:" not in out  # --sources-only still skips harvest


# ─── FR6 — the new setting is discoverable ────────────────────────────────


def test_cli_reference_documents_the_concurrency_flag() -> None:
    """FR6.2: ``docs/reference/cli.md`` lists ``--concurrency`` with its
    default and accepted range, and calls out that ``all`` has no matching
    flag."""
    text = (REPO_ROOT / "docs" / "reference" / "cli.md").read_text(encoding="utf-8")
    concurrency_row = next(
        (ln for ln in text.splitlines() if ln.startswith("| `--concurrency N`")),
        None,
    )
    assert concurrency_row is not None, "no --concurrency row in docs/reference/cli.md"
    assert "default: `2`" in concurrency_row
    assert "1" in concurrency_row and "16" in concurrency_row
    assert "`all` has no matching flag" in concurrency_row


def test_configuration_reference_documents_the_concurrency_key() -> None:
    """FR6.2: ``docs/configuration-reference.md`` lists the saved
    ``synthesis.concurrency`` preference with its default and range."""
    text = (REPO_ROOT / "docs" / "configuration-reference.md").read_text(
        encoding="utf-8"
    )
    concurrency_row = next(
        (
            ln
            for ln in text.splitlines()
            if ln.startswith("| `synthesis` | `concurrency`")
        ),
        None,
    )
    assert concurrency_row is not None, (
        "no synthesis.concurrency row in docs/configuration-reference.md"
    )
    assert "| 2 |" in concurrency_row
    assert "1" in concurrency_row and "16" in concurrency_row


def test_changelog_unreleased_section_describes_the_change() -> None:
    """FR6.3: the Unreleased section of the changelog describes #118 —
    batch announcement and parallel synthesis, not just a bullet mentioning
    the issue number in passing."""
    text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    match = re.search(r"(?ms)^## \[Unreleased\]\n(.*?)(?=^## \[)", text)
    assert match is not None, "no [Unreleased] section found in CHANGELOG.md"
    unreleased = match.group(1)
    assert "#118" in unreleased
    entry = next(
        (ln for ln in unreleased.splitlines() if "#118" in ln), ""
    )
    assert "concurrency" in entry.lower() or "parallel" in entry.lower()
    assert "--concurrency" in entry


# ─── Scope: synth's behavior inside `all --with-synth` ───────────────────


def test_all_with_synth_has_no_concurrency_flag_on_the_command_line() -> None:
    """``all --with-synth`` deliberately has no per-run ``--concurrency``
    flag — only the saved preference applies there."""
    with pytest.raises(SystemExit) as excinfo:
        build_parser().parse_args(
            ["all", "--with-synth", "--concurrency", "2"]
        )
    assert excinfo.value.code == 2


def test_all_with_synth_honours_config_concurrency_with_no_flag_to_set_it(
    tmp_path: Path,
) -> None:
    """The same worker-count setting applies when synth runs as part of
    ``llmwiki all --with-synth`` — proven with a real synth call (not
    mocked), while ``build_site``/lint are stubbed so the test stays about
    synth's concurrency, not the rest of the pipeline."""
    vault = _mk_vault(tmp_path)
    _seed_docs(vault, tuple(f"doc{i:02d}" for i in range(6)))
    backend = _TrackingBackend()

    args = build_parser().parse_args(
        ["all", "--with-synth", "--skip-graph", "--vault", str(vault)]
    )

    with (
        patch.object(pipeline_mod, "resolve_backend", return_value=backend),
        patch.object(
            pipeline_mod,
            "_load_sessions_config",
            lambda: {"synthesis": {"concurrency": 3}},
        ),
        patch.object(pipeline_mod, "build_site", return_value=0),
        patch.object(pipeline_mod, "_run_lint_step", return_value=(0, {})),
    ):
        rc = cli_mod.cmd_all(args)

    assert rc == 0
    assert backend.peak > 1, "no overlap observed — test would be vacuous"
    assert backend.peak <= 3
