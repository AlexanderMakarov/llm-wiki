"""Manual full runs of sync / synth / build record and clear their Home entry.

A narrowed or trial run (one file, a cost estimate, a backend check, a custom
output directory, a filtered sync) neither adds nor clears anything.

# @spec: 374-no-silent-automation-failure
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from llmwiki import run_outcomes
from llmwiki.cli import build_parser, cmd_build, cmd_sync, cmd_synthesize
from llmwiki.convert import save_sync_meta
from llmwiki.run_outcomes import Failure
from llmwiki.state_store import read_state


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    root = tmp_path / "vault"
    for sub in ("raw/sessions", "raw/docs", "wiki/sources", "site"):
        (root / sub).mkdir(parents=True)
    return root


def _parts(vault: Path) -> dict:
    return read_state(vault / "llmwiki-state.json")["outcomes"]["parts"]


def _seed(vault: Path, part: str) -> None:
    run_outcomes.record_failure(
        part, Failure(scope="entire", summary="failed earlier"),
        state_file=vault / "llmwiki-state.json",
    )


def _summary(**over) -> dict:
    base = {"total_scanned": 2, "new_files": 2, "synthesized": 2, "skipped": 0,
            "errors": [], "deferred": 0}
    base.update(over)
    return base


def _synth(vault: Path, *argv: str, available: bool = True, summary: dict | None = None,
           harvest_rc: int = 0) -> int:
    args = build_parser().parse_args(["synth", *argv, "--vault", str(vault)])
    backend = MagicMock()
    backend.name = "claude-cli"
    backend.is_available.return_value = available
    backend.unavailable_reason.return_value = "claude was not found on PATH"
    with (
        patch("llmwiki.cli.resolve_backend", return_value=backend),
        patch("llmwiki.cli.synthesize_new_sessions", return_value=summary or _summary()),
        patch("llmwiki.cli.run_harvest", return_value=harvest_rc),
        patch("llmwiki.cli._refresh_review_counts"),
        patch("llmwiki.cli._synthesize_estimate", return_value=0),
        patch("llmwiki.cli.stamp_last_synth_at"),
    ):
        return cmd_synthesize(args)


# ─── synth ────────────────────────────────────────────────────────────────


def test_a_clean_manual_synth_clears_the_synth_entry(vault: Path):
    _seed(vault, "synth")
    assert _synth(vault) == 0
    assert "synth" not in _parts(vault)


def test_a_failing_manual_synth_records_its_outcome(vault: Path):
    assert _synth(vault, summary=_summary(synthesized=1, errors=["doc-a: boom"])) == 1
    assert _parts(vault)["synth"]["summary"] == "1 of 2 sources failed"


def test_a_manual_synth_with_no_backend_records_did_not_run(vault: Path):
    assert _synth(vault, available=False) == 1
    assert _parts(vault)["synth"]["summary"] == "did not run: backend claude-cli is not available"


def test_a_failed_harvest_in_a_manual_synth_records_synth(vault: Path):
    assert _synth(vault, harvest_rc=1) == 1
    assert _parts(vault)["synth"]["summary"] == "candidate harvest failed (exit 1)"


@pytest.mark.parametrize(
    "argv",
    [
        ("--sources-only",),
        ("--sessions-only",),
        ("--docs-only",),
        ("--estimate",),
        ("--check",),
    ],
    ids=["sources-only", "sessions-only", "docs-only", "estimate", "check"],
)
def test_narrowed_or_trial_synth_leaves_the_entry(vault: Path, argv: tuple[str, ...]):
    _seed(vault, "synth")
    _synth(vault, *argv)
    assert _parts(vault)["synth"]["summary"] == "failed earlier"


def test_synth_of_one_chosen_file_leaves_the_entry(vault: Path):
    doc = vault / "raw" / "docs" / "one.md"
    doc.write_text("---\ntitle: One\n---\n\nbody\n", encoding="utf-8")
    _seed(vault, "synth")
    with patch("llmwiki.cli._resolve_synthesize_only_paths", return_value={doc}), \
         patch("llmwiki.cli._validate_synthesize_path_kinds"):
        _synth(vault, "--path", "raw/docs/one.md")
    assert _parts(vault)["synth"]["summary"] == "failed earlier"


def test_a_narrowed_synth_that_fails_adds_nothing(vault: Path):
    _synth(vault, "--sources-only", summary=_summary(synthesized=1, errors=["doc-a: boom"]))
    assert "synth" not in _parts(vault)


# ─── sync ─────────────────────────────────────────────────────────────────


def _sync(vault: Path, *argv: str, errored: int = 0, build_rc: int = 0) -> int:
    args = build_parser().parse_args(["sync", *argv, "--vault", str(vault)])
    state_file = vault / "llmwiki-state.json"

    def _convert(**_kwargs) -> int:
        save_sync_meta(
            state_file,
            meta={"last_sync": run_outcomes.utc_now()},
            counters={"claude_code": {"discovered": 2, "errored": errored}},
        )
        return 0

    with (
        patch("llmwiki.cli.convert_all", side_effect=_convert),
        patch("llmwiki.cli.refresh_synth_pending"),
        patch("llmwiki.cli.build_site", return_value=build_rc),
        patch("llmwiki.cli.plan_reindex", return_value=None),
        patch("llmwiki.cli._load_schedule_config", return_value={"build": "on-sync", "lint": "manual"}),
    ):
        return cmd_sync(args)


def test_a_clean_full_sync_clears_the_sync_entry(vault: Path):
    _seed(vault, "sync")
    assert _sync(vault, "--no-auto-build") == 0
    assert "sync" not in _parts(vault)


def test_a_full_sync_with_file_errors_records_a_partial_sync(vault: Path):
    _sync(vault, "--no-auto-build", errored=1)
    assert _parts(vault)["sync"]["summary"] == "1 of 1 session sources failed (claude_code)"


@pytest.mark.parametrize(
    "argv",
    [("--adapter", "claude_code"), ("--since", "2026-10-01"), ("--project", "demo")],
    ids=["adapter", "since", "project"],
)
def test_a_filtered_sync_leaves_the_entry(vault: Path, argv: tuple[str, ...]):
    _seed(vault, "sync")
    _sync(vault, "--no-auto-build", *argv, errored=0)
    assert _parts(vault)["sync"]["summary"] == "failed earlier"


def test_the_build_after_a_sync_records_build(vault: Path):
    assert _sync(vault, build_rc=2) == 0
    assert _parts(vault)["build"]["summary"] == "failed (exit 2)"


# ─── build ────────────────────────────────────────────────────────────────


def _build(vault: Path, *argv: str, rc: int = 0) -> int:
    args = build_parser().parse_args(["build", *argv, "--vault", str(vault)])
    with patch("llmwiki.cli.build_site", return_value=rc):
        return cmd_build(args)


def test_a_clean_build_clears_the_build_entry(vault: Path):
    _seed(vault, "build")
    assert _build(vault) == 0
    assert "build" not in _parts(vault)


def test_a_failed_build_records_build(vault: Path):
    assert _build(vault, rc=2) == 2
    assert _parts(vault)["build"]["summary"] == "failed (exit 2)"


def test_a_build_into_another_folder_leaves_the_entry(vault: Path, tmp_path: Path):
    _seed(vault, "build")
    _build(vault, "--out", str(tmp_path / "elsewhere"))
    assert _parts(vault)["build"]["summary"] == "failed earlier"
