"""`llmwiki all` records each part's latest outcome for the Home problems banner.

Drives ``cmd_all`` on a ``tmp_path`` vault with the backend and build stubbed,
then reads what the site sidecar would show.

# @spec: 374-no-silent-automation-failure
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from llmwiki import cli, pipeline, quarantine, run_outcomes
from llmwiki.cli import build_parser
from llmwiki.convert import save_sync_meta
from llmwiki.run_outcomes import Failure
from llmwiki.state_store import read_state


def _vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    for sub in ("raw/sessions", "raw/docs", "wiki", "site"):
        (vault / sub).mkdir(parents=True)
    return vault


def _backend(*, available: bool = True) -> MagicMock:
    backend = MagicMock()
    backend.name = "claude-cli"
    backend.is_available.return_value = available
    backend.unavailable_reason.return_value = "claude was not found on PATH — install Claude Code"
    return backend


def _run_all(vault: Path, *extra: str, backend: MagicMock | None = None,
             summary: dict | None = None, harvest_rc: int = 0,
             build: MagicMock | None = None, convert: MagicMock | None = None,
             stages: tuple[str, ...] = ("--no-sync", "--skip-graph", "--skip-lint")) -> int:
    args = build_parser().parse_args(["all", *stages, *extra, "--vault", str(vault)])
    with (
        patch.object(pipeline, "resolve_backend", return_value=backend or _backend()),
        patch.object(pipeline, "synthesize_new_sessions", return_value=summary or _clean_summary()),
        patch.object(pipeline, "run_harvest", return_value=harvest_rc),
        patch.object(pipeline, "stamp_last_synth_at"),
        patch.object(pipeline, "build_site", build or MagicMock(return_value=0)),
        patch.object(pipeline, "convert_all", convert or MagicMock(return_value=0)),
        patch.object(pipeline, "refresh_synth_pending"),
        patch.object(pipeline, "reindex_wiki", return_value=None),
        patch.object(pipeline, "_maybe_print_optout_notice"),
        patch.object(pipeline, "_load_sessions_config", return_value={}),
    ):
        return cli.cmd_all(args)


def _parts(vault: Path) -> dict:
    return read_state(vault / "llmwiki-state.json")["outcomes"]["parts"]


def _clean_summary(**over) -> dict:
    base = {"total_scanned": 7, "new_files": 7, "synthesized": 7, "skipped": 0,
            "errors": [], "deferred": 0, "backend": "claude-cli"}
    base.update(over)
    return base


def test_unavailable_backend_records_synth_did_not_run(tmp_path: Path, capsys):
    vault = _vault(tmp_path)
    rc = _run_all(vault, backend=_backend(available=False))
    assert rc == 1
    entry = _parts(vault)["synth"]
    assert entry["scope"] == "entire"
    assert entry["summary"] == "did not run: backend claude-cli is not available"
    assert "claude was not found on PATH" in entry["detail"]
    assert "error: backend claude-cli is not available: claude was not found on PATH" in capsys.readouterr().err


def test_one_failed_source_records_a_partial_synth(tmp_path: Path):
    vault = _vault(tmp_path)
    summary = _clean_summary(synthesized=6, errors=["doc-a: 'float' object has no attribute 'strip'"])
    assert _run_all(vault, backend=_backend(), summary=summary) == 1
    entry = _parts(vault)["synth"]
    assert (entry["scope"], entry["summary"], entry["items"]) == ("partial", "1 of 7 sources failed", ["doc-a"])


def test_usage_limit_stop_records_a_partial_synth_with_counts(tmp_path: Path):
    vault = _vault(tmp_path)
    summary = _clean_summary(synthesized=5, deferred=7, usage_limit={"reset": None})
    assert _run_all(vault, backend=_backend(), summary=summary) == 75
    assert _parts(vault)["synth"]["summary"] == (
        "stopped at the AI provider's usage limit after 5 of 12 sources"
    )


def test_failed_candidate_harvest_records_synth(tmp_path: Path):
    vault = _vault(tmp_path)
    assert _run_all(vault, backend=_backend(), summary=_clean_summary(), harvest_rc=1) == 1
    assert _parts(vault)["synth"]["summary"] == "candidate harvest failed (exit 1)"


def test_a_clean_synth_clears_the_previous_synth_entry(tmp_path: Path):
    vault = _vault(tmp_path)
    run_outcomes.record_failure(
        "synth", Failure(scope="entire", summary="did not run: x"),
        state_file=vault / "llmwiki-state.json",
    )
    assert _run_all(vault, backend=_backend(), summary=_clean_summary()) == 0
    assert "synth" not in _parts(vault)


def test_skipping_synth_leaves_its_entry_alone(tmp_path: Path):
    vault = _vault(tmp_path)
    run_outcomes.record_failure(
        "synth", Failure(scope="entire", summary="did not run: x"),
        state_file=vault / "llmwiki-state.json",
    )
    _run_all(vault, "--no-synth", backend=_backend(), summary=_clean_summary())
    assert _parts(vault)["synth"]["summary"] == "did not run: x"


@pytest.mark.parametrize("available", [False, True], ids=["unavailable", "source-error"])
def test_fail_fast_records_synth_before_stopping(tmp_path: Path, available: bool):
    vault = _vault(tmp_path)
    summary = _clean_summary(synthesized=6, errors=["doc-a: boom"])
    assert _run_all(vault, "--fail-fast", backend=_backend(available=available), summary=summary) == 1
    assert "synth" in _parts(vault)


# ─── Sync, Build and whole-run outcomes ───────────────────────────────────


def _convert_with(vault: Path, counters: dict, failures: list[tuple[str, str, str]]) -> MagicMock:
    """A ``convert_all`` stand-in that leaves this run's counters and quarantine rows."""
    state_file = vault / "llmwiki-state.json"

    def _convert(**_kwargs) -> int:
        for adapter, source, error in failures:
            quarantine.add_entry(adapter, source, error, path=state_file)
        save_sync_meta(state_file, meta={"last_sync": run_outcomes.utc_now()}, counters=counters)
        return 0

    return MagicMock(side_effect=_convert)


def _counters(**errored: int) -> dict:
    return {name: {"discovered": 3, "converted": 3 - n, "errored": n} for name, n in errored.items()}


def test_an_adapter_with_errors_records_a_partial_sync(tmp_path: Path):
    vault = _vault(tmp_path)
    state_file = vault / "llmwiki-state.json"
    quarantine.add_entry("codex_cli", "old.jsonl", "stale error", path=state_file)
    convert = _convert_with(
        vault,
        _counters(claude_code=0, codex_cli=0, cursor_cli=1, openclaw=0),
        [("cursor_cli", "store.db#chat-7", "database is locked")],
    )
    assert _run_all(vault, stages=("--no-synth", "--skip-graph", "--skip-lint"), convert=convert) == 0
    entry = _parts(vault)["sync"]
    assert entry["scope"] == "partial"
    assert entry["summary"] == "1 of 4 session sources failed (cursor_cli)"
    assert "cursor_cli: store.db#chat-7: database is locked" in entry["detail"]
    assert "old.jsonl" not in entry["detail"]
    assert "run" not in _parts(vault)


def test_sync_that_cannot_start_records_an_entire_failure(tmp_path: Path):
    vault = _vault(tmp_path)
    rc = _run_all(vault, stages=("--no-synth", "--skip-graph", "--skip-lint"),
                  convert=MagicMock(return_value=2))
    assert rc == 2
    entry = _parts(vault)["sync"]
    assert (entry["scope"], entry["summary"]) == ("entire", "did not run (exit 2)")


def test_a_clean_sync_clears_the_previous_sync_entry(tmp_path: Path):
    vault = _vault(tmp_path)
    run_outcomes.record_failure("sync", Failure(scope="entire", summary="failed"),
                                state_file=vault / "llmwiki-state.json")
    convert = _convert_with(vault, _counters(claude_code=0), [])
    _run_all(vault, stages=("--no-synth", "--skip-graph", "--skip-lint"), convert=convert)
    assert "sync" not in _parts(vault)


def test_a_build_that_raises_records_build_and_the_run(tmp_path: Path):
    vault = _vault(tmp_path)
    build = MagicMock(side_effect=OSError("No space left on device"))
    with pytest.raises(OSError):
        _run_all(vault, build=build)
    parts = _parts(vault)
    assert parts["build"]["detail"] == "OSError: No space left on device"
    assert parts["run"]["summary"] == "run failed: it stopped on an unexpected error"


def test_a_build_exit_code_records_build_but_no_run_entry(tmp_path: Path):
    vault = _vault(tmp_path)
    assert _run_all(vault, build=MagicMock(return_value=2)) == 2
    parts = _parts(vault)
    assert parts["build"]["summary"] == "failed (exit 2)"
    assert "run" not in parts


def test_a_build_into_a_custom_out_leaves_build_alone(tmp_path: Path):
    vault = _vault(tmp_path)
    rc = _run_all(vault, "--out", str(tmp_path / "elsewhere"), build=MagicMock(return_value=2))
    assert rc == 2
    parts = _parts(vault)
    assert "build" not in parts
    assert parts["run"]["detail"] == f"build into {tmp_path / 'elsewhere'} exited 2"


def test_a_lock_timeout_records_the_run(tmp_path: Path):
    vault = _vault(tmp_path)
    with (
        patch.object(pipeline, "pipeline_lock", side_effect=RuntimeError("pipeline lock busy (pid 42)")),
        pytest.raises(RuntimeError),
    ):
        _run_all(vault)
    assert _parts(vault)["run"]["detail"] == "RuntimeError: pipeline lock busy (pid 42)"


def test_lint_policy_failure_alone_adds_no_run_entry(tmp_path: Path):
    vault = _vault(tmp_path)
    with patch.object(pipeline, "_run_lint_step", return_value=(0, {"error": 3, "warning": 0})):
        rc = _run_all(vault, "--lint-fail", "errors", stages=("--no-sync", "--skip-graph"))
    assert rc == 2
    assert "run" not in _parts(vault)


def test_lint_that_cannot_run_records_the_run(tmp_path: Path):
    vault = _vault(tmp_path)
    with patch.object(pipeline, "_run_lint_step", return_value=(2, {})):
        rc = _run_all(vault, stages=("--no-sync", "--skip-graph"))
    assert rc == 2
    assert _parts(vault)["run"]["detail"] == "lint could not run (exit 2)"


def test_a_failed_graph_step_records_the_run(tmp_path: Path):
    vault = _vault(tmp_path)
    with patch.object(pipeline, "_run_graph_step", return_value=1):
        rc = _run_all(vault, stages=("--no-sync", "--skip-lint"))
    assert rc == 1
    assert _parts(vault)["run"]["detail"] == "graph step exited 1"


def test_a_clean_run_clears_the_previous_run_entry(tmp_path: Path):
    vault = _vault(tmp_path)
    run_outcomes.record_failure("run", Failure(scope="entire", summary="run failed (exit 1)"),
                                state_file=vault / "llmwiki-state.json")
    assert _run_all(vault) == 0
    assert "run" not in _parts(vault)


def test_a_non_zero_exit_nothing_explains_still_records_the_run():
    failure = run_outcomes.run_failure(1, [], explained=False)
    assert failure is not None
    assert failure.summary == "run failed (exit 1)"
    assert run_outcomes.run_failure(1, [], explained=True) is None


def test_outcomes_refresh_the_vault_site_when_out_points_elsewhere(tmp_path: Path):
    """Home reads the vault's site/, so outcomes land there even with --out."""
    vault = _vault(tmp_path)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    _run_all(vault, "--out", str(elsewhere), backend=_backend(available=False))
    vault_sidecar = (vault / "site" / "llmwiki-state.js").read_text(encoding="utf-8")
    assert "did not run: backend claude-cli is not available" in vault_sidecar
    assert not (elsewhere / "llmwiki-state.js").exists() or "did not run" not in (
        elsewhere / "llmwiki-state.js"
    ).read_text(encoding="utf-8")
