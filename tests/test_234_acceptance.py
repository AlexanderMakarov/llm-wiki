"""Whole-feature acceptance tests for #234: Home pipeline stamps + lint banner.

# @layer: integration
# @spec: 234-home-timeline-automation-stamps
# @regression

Maps functional-spec.md acceptance criteria not already covered in slice
tests. Slice tests in ``test_234_ops_stamps.py``, ``test_234_pipeline_acceptance.py``,
``test_state_widget.py``, and ``test_automation_install.py`` own individual
layers; this file closes end-to-end gaps:

    R1  → sync-only empty stamps; full pipeline four stamps + monotonic order
    R2  → never-run lint; successful lint ok path (no error stored)
    R3  → standalone lint refreshes site sidecar; lint-fail never keeps ok status
    R4  → cli.md documents ``--fail-fast`` vs continue-after-failure
    R5  → cli.md / ui.md document Maintain site-once-after-synth wording
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from llmwiki import build as build_mod
from llmwiki import cli, pipeline
from llmwiki.build import build_site
from llmwiki.cli import build_parser
from llmwiki.state_store import (
    configure_state_file,
    default_state,
    read_state,
    update_state,
    write_state,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def _vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "raw" / "sessions").mkdir(parents=True)
    (vault / "raw" / "docs").mkdir(parents=True)
    (vault / "wiki" / "sources").mkdir(parents=True)
    configure_state_file(vault)
    write_state(default_state(), vault / "llmwiki-state.json")
    return vault


def _write_buildable_source(vault: Path, *, marker: str = "ACCEPT234_MARKER") -> None:
    project = "proj"
    stem = "s1"
    src_dir = vault / "wiki" / "sources" / project
    raw_dir = vault / "raw" / "sessions" / project
    src_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / f"{stem}.md").write_text(
        f'---\ntitle: "{stem}"\ntype: source\nproject: {project}\ndate: 2026-01-01\n'
        f"source_file: raw/sessions/{project}/{stem}.md\n---\n\n"
        f"## Summary\n\n{marker}\n\n## Connections\n",
        encoding="utf-8",
    )
    (raw_dir / f"{stem}.md").write_text(
        f'---\ntitle: "{stem}"\ntype: source\nproject: {project}\nslug: {stem}\n'
        f"date: 2026-01-01\nsource_file: raw/sessions/{project}/{stem}.md\n"
        'token_totals: {"input": 1, "output": 1, "cache_creation": 0, "cache_read": 0}\n'
        f"---\n\n# {stem}\n\n{marker}\n",
        encoding="utf-8",
    )


def _write_clean_wiki_page(vault: Path) -> None:
    entities = vault / "wiki" / "entities"
    entities.mkdir(parents=True, exist_ok=True)
    (entities / "Clean.md").write_text(
        '---\ntitle: "Clean"\ntype: entity\ntags: []\nsources: []\n'
        "last_updated: 2026-09-08\n---\n\n# Clean\n",
        encoding="utf-8",
    )


def _plant_lint_error(vault: Path) -> None:
    entities = vault / "wiki" / "entities"
    entities.mkdir(parents=True, exist_ok=True)
    (entities / "Bogus.md").write_text(
        '---\ntitle: "Bogus"\ntype: entity\nconfidence: 2.5\n---\n\n# Bogus\n',
        encoding="utf-8",
    )


def _parse_site_sidecar(site: Path) -> dict:
    text = (site / "llmwiki-state.js").read_text(encoding="utf-8")
    payload = text.split("=", 1)[1].rstrip().rstrip(";")
    return json.loads(payload)


def _patch_build_roots(monkeypatch: pytest.MonkeyPatch, vault: Path) -> None:
    monkeypatch.setattr(build_mod, "REPO_ROOT", vault)
    monkeypatch.setattr(build_mod, "RAW_DIR", vault / "raw")
    monkeypatch.setattr(build_mod, "RAW_SESSIONS", vault / "raw" / "sessions")
    monkeypatch.setattr(build_mod, "DEFAULT_OUT_DIR", vault / "site")


def _iso_le(a: str, b: str) -> bool:
    """Lexicographic ISO-8601 Z ordering matches chronological order."""
    return a <= b


# ─── R1 — Pipeline state stage stamps ───────────────────────────────────────


def test_r1_sync_only_leaves_synth_build_lint_stamps_empty(tmp_path: Path):
    """R1: only sync completed → Last sync set; other stage stamps empty.

    # @layer: integration  # @spec: 234-home-timeline-automation-stamps
    # @regression
    """
    vault = _vault(tmp_path)
    state_file = vault / "llmwiki-state.json"

    def _stamp_sync(state: dict) -> dict:
        state.setdefault("sync", {}).setdefault("meta", {})["last_sync"] = (
            "2026-09-08T10:00:00Z"
        )
        return state

    update_state(_stamp_sync, state_file)
    state = read_state(state_file)
    assert state["sync"]["meta"]["last_sync"] == "2026-09-08T10:00:00Z"
    ops = state["ops"]
    assert ops["last_synth_at"] == ""
    assert ops["last_build_at"] == ""
    assert ops["last_lint_run_at"] == ""
    assert ops["last_lint_status"] == ""
    assert ops["last_lint_error"] == ""


def test_r1_full_pipeline_populates_monotonic_stage_stamps(tmp_path: Path, monkeypatch):
    """R1: Maintain-equivalent ``all`` run stamps sync≤synth≤build≤lint.

    # @layer: integration  # @spec: 234-home-timeline-automation-stamps
    # @regression
    """
    vault = _vault(tmp_path)
    _write_buildable_source(vault)
    _patch_build_roots(monkeypatch, vault)

    def _seed_sync(state: dict) -> dict:
        # Prior sync from an earlier cycle — must precede this run's stamps.
        state.setdefault("sync", {}).setdefault("meta", {})["last_sync"] = (
            "2020-01-01T00:00:00Z"
        )
        return state

    update_state(_seed_sync, vault / "llmwiki-state.json")

    backend = MagicMock()
    backend.name = "dummy"
    backend.is_available.return_value = True
    summary = {
        "total_scanned": 1,
        "new_files": 0,
        "synthesized": 0,
        "skipped": 1,
        "errors": [],
    }

    args = build_parser().parse_args(
        ["all", "--no-sync", "--skip-graph", "--vault", str(vault)]
    )

    with (
        patch.object(pipeline, "resolve_backend", return_value=backend),
        patch.object(pipeline, "synthesize_new_sessions", return_value=summary),
        patch.object(pipeline, "run_harvest", return_value=0),
        patch.object(pipeline, "_maybe_print_optout_notice"),
        patch.object(pipeline, "_load_sessions_config", return_value={}),
    ):
        rc = cli.cmd_all(args)

    assert rc == 0
    state = read_state(vault / "llmwiki-state.json")
    last_sync = state["sync"]["meta"]["last_sync"]
    ops = state["ops"]
    assert last_sync
    assert ops["last_synth_at"]
    assert ops["last_build_at"]
    assert ops["last_lint_run_at"]
    assert _iso_le(last_sync, ops["last_synth_at"])
    assert _iso_le(ops["last_synth_at"], ops["last_build_at"])
    assert _iso_le(ops["last_build_at"], ops["last_lint_run_at"])


# ─── R2 — Lint pass/fail banner fields ──────────────────────────────────────


def test_r2_never_run_lint_leaves_lint_fields_empty(tmp_path: Path):
    """R2: quality never run → Last lint empty and no stored error.

    # @layer: unit  # @spec: 234-home-timeline-automation-stamps
    # @regression
    """
    vault = _vault(tmp_path)
    ops = read_state(vault / "llmwiki-state.json")["ops"]
    assert ops["last_lint_run_at"] == ""
    assert ops["last_lint_status"] == ""
    assert ops["last_lint_error"] == ""


def test_r2_successful_lint_records_ok_and_clears_error(tmp_path: Path):
    """R2: passing lint → status ok, no multiline error for Home banner.

    # @layer: integration  # @spec: 234-home-timeline-automation-stamps
    # @regression
    """
    vault = _vault(tmp_path)
    _write_clean_wiki_page(vault)
    args = build_parser().parse_args(["lint", "--vault", str(vault)])
    rc = cli.cmd_lint(args)
    assert rc == 0
    ops = read_state(vault / "llmwiki-state.json")["ops"]
    assert ops["last_lint_run_at"]
    assert ops["last_lint_status"] == "ok"
    assert ops["last_lint_error"] == ""


# ─── R3 — Build stays published; standalone lint data-only refresh ──────────


def test_r3_standalone_lint_refreshes_site_sidecar_without_html_rewrite(
    tmp_path: Path, monkeypatch
):
    """R3: ``llmwiki lint`` updates site data sidecar; HTML bytes unchanged.

    # @layer: integration  # @spec: 234-home-timeline-automation-stamps
    # @regression
    """
    vault = _vault(tmp_path)
    _write_buildable_source(vault)
    site = vault / "site"
    _patch_build_roots(monkeypatch, vault)
    assert build_site(out_dir=site, synthesize=False) == 0

    index = site / "index.html"
    html_before = index.read_bytes()
    stale = "window.LLMWIKI_STATE_SNAPSHOT = {\"stale\": true};\n"
    (site / "llmwiki-state.js").write_text(stale, encoding="utf-8")

    _plant_lint_error(vault)
    args = build_parser().parse_args(
        ["lint", "--vault", str(vault), "--fail-on-errors"]
    )
    rc = cli.cmd_lint(args)
    assert rc == 1

    assert index.read_bytes() == html_before
    sidecar = _parse_site_sidecar(site)
    vault_ops = read_state(vault / "llmwiki-state.json")["ops"]
    assert sidecar["ops"]["last_lint_status"] == "failed"
    assert sidecar["ops"]["last_lint_error"] == vault_ops["last_lint_error"]
    assert sidecar["ops"]["last_lint_run_at"] == vault_ops["last_lint_run_at"]
    # Sidecar was refreshed from vault JSON — not the planted ``{"stale": true}`` stub.
    assert sidecar.get("stale") is not True
    assert vault_ops["last_lint_status"] == "failed"


def test_r3_lint_fail_never_policy_records_ok_despite_findings(tmp_path: Path):
    """R3: findings under ``never`` fail policy → site ok path, no banner text.

    # @layer: integration  # @spec: 234-home-timeline-automation-stamps
    # @regression
    """
    vault = _vault(tmp_path)
    _plant_lint_error(vault)
    args = build_parser().parse_args(["lint", "--vault", str(vault)])
    rc = cli.cmd_lint(args)
    assert rc == 0
    ops = read_state(vault / "llmwiki-state.json")["ops"]
    assert ops["last_lint_run_at"]
    assert ops["last_lint_status"] == "ok"
    assert ops["last_lint_error"] == ""


# ─── R4 / R5 — Docs contract ────────────────────────────────────────────────


def test_r4_cli_docs_describe_fail_fast_vs_continue():
    """R4: ``docs/reference/cli.md`` documents ``--fail-fast`` stop-on-first-failure.

    # @layer: unit  # @spec: 234-home-timeline-automation-stamps
    # @regression
    """
    text = (REPO_ROOT / "docs" / "reference" / "cli.md").read_text(encoding="utf-8")
    assert "--fail-fast" in text
    assert "Stop at the first non-zero step" in text
    assert "build still runs" in text.lower()


def test_r5_docs_maintain_site_once_after_summarization():
    """R5: install-automation / Maintain docs say site rebuilds once after synth.

    # @layer: unit  # @spec: 234-home-timeline-automation-stamps
    # @regression
    """
    cli_doc = (REPO_ROOT / "docs" / "reference" / "cli.md").read_text(encoding="utf-8")
    ui_doc = (REPO_ROOT / "docs" / "reference" / "ui.md").read_text(encoding="utf-8")
    assert "once after summarization" in cli_doc
    assert "once after summarization" in ui_doc
