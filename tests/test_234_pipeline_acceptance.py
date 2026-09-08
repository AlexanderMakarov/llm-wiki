"""#234 Slice 4 — pipeline continue / lint-fail keeps the built site.

# @spec: 234-home-timeline-automation-stamps

Acceptance for R3 (lint-fail does not undo build) and R4 (continue unless
``--fail-fast``). Uses pytest ``tmp_path`` vaults only — never a live Obsidian
path or the worktree's ``.worktree-vault``.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from llmwiki import cli, pipeline
from llmwiki.cli import build_parser
from llmwiki.state_store import read_state


def _vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "raw" / "sessions").mkdir(parents=True)
    (vault / "raw" / "docs").mkdir(parents=True)
    (vault / "wiki").mkdir()
    return vault


def _write_buildable_source(vault: Path, *, marker: str = "SLICE4_BUILD_MARKER") -> None:
    """Minimal raw + wiki source so ``build_site`` emits HTML containing *marker*."""
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


def _plant_lint_error(vault: Path) -> None:
    """``frontmatter_validity`` (severity=error) on out-of-range confidence."""
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


def test_synth_failure_without_fail_fast_still_runs_build(tmp_path: Path):
    """R4: synth fails → build (and later stages) still run when not fail-fast.

    # @layer: integration  # @spec: 234-home-timeline-automation-stamps
    """
    vault = _vault(tmp_path)
    site = vault / "site"
    site.mkdir()

    backend = MagicMock()
    backend.name = "dummy"
    backend.is_available.return_value = False

    args = build_parser().parse_args(
        ["all", "--no-sync", "--skip-graph", "--skip-lint", "--vault", str(vault)]
    )
    assert args.fail_fast is False

    build_stub = MagicMock(return_value=0)
    with (
        patch.object(pipeline, "resolve_backend", return_value=backend),
        patch.object(pipeline, "synthesize_new_sessions") as synth,
        patch.object(pipeline, "build_site", build_stub),
        patch.object(pipeline, "_maybe_print_optout_notice"),
        patch.object(pipeline, "_load_sessions_config", return_value={}),
    ):
        rc = cli.cmd_all(args)

    assert rc == 1
    synth.assert_not_called()
    assert build_stub.call_count == 1


def test_fail_fast_skips_later_stages_and_reports_on_console(tmp_path: Path, capsys):
    """R4: ``--fail-fast`` stops after synth failure; console names the abort.

    # @layer: integration  # @spec: 234-home-timeline-automation-stamps
    """
    vault = _vault(tmp_path)
    (vault / "site").mkdir()

    backend = MagicMock()
    backend.name = "dummy"
    backend.is_available.return_value = False

    args = build_parser().parse_args(
        [
            "all",
            "--no-sync",
            "--fail-fast",
            "--skip-graph",
            "--skip-lint",
            "--vault",
            str(vault),
        ]
    )

    build_stub = MagicMock(return_value=0)
    lint_stub = MagicMock(return_value=(0, {}))
    with (
        patch.object(pipeline, "resolve_backend", return_value=backend),
        patch.object(pipeline, "build_site", build_stub),
        patch.object(pipeline, "_run_lint_step", lint_stub),
        patch.object(pipeline, "_maybe_print_optout_notice"),
        patch.object(pipeline, "_load_sessions_config", return_value={}),
    ):
        rc = cli.cmd_all(args)

    err = capsys.readouterr().err
    assert rc == 1
    assert build_stub.call_count == 0
    assert lint_stub.call_count == 0
    assert "stopping (--fail-fast)" in err
    assert "synth" in err.lower()


def test_lint_fail_errors_keeps_built_site_and_records_banner_fields(tmp_path: Path):
    """R3: ``all --lint-fail errors`` exits 2; this build's HTML stays; ops + sidecar carry banner fields.

    # @layer: integration  # @spec: 234-home-timeline-automation-stamps
    # @regression
    """
    vault = _vault(tmp_path)
    marker = "SLICE4_BUILD_MARKER_9f3a"
    _write_buildable_source(vault, marker=marker)
    _plant_lint_error(vault)

    args = build_parser().parse_args(
        [
            "all",
            "--no-sync",
            "--no-synth",
            "--skip-graph",
            "--lint-fail",
            "errors",
            "--vault",
            str(vault),
        ]
    )

    rc = cli.cmd_all(args)
    assert rc == 2

    site = vault / "site"
    assert site.is_dir()
    html_hits = [
        p for p in site.rglob("*.html") if marker in p.read_text(encoding="utf-8", errors="replace")
    ]
    assert html_hits, "site HTML from this build (marker) must remain after lint-fail"

    ops = read_state(vault / "llmwiki-state.json")["ops"]
    assert ops["last_lint_status"] == "failed"
    assert ops["last_lint_error"]
    assert ops["last_build_at"]  # build stamped before lint failed the job
    assert "frontmatter" in ops["last_lint_error"].lower() or "confidence" in ops["last_lint_error"].lower() or "Bogus" in ops["last_lint_error"]

    sidecar = _parse_site_sidecar(site)
    assert sidecar["ops"]["last_lint_status"] == "failed"
    assert sidecar["ops"]["last_lint_error"] == ops["last_lint_error"]
    assert sidecar["ops"]["last_lint_run_at"] == ops["last_lint_run_at"]


def test_lint_fail_errors_refreshes_custom_out_sidecar(tmp_path: Path):
    """R3: ``all --out <custom>`` must stamp lint fields on that site sidecar (#234 B1).

    # @layer: integration  # @spec: 234-home-timeline-automation-stamps
    # @regression
    """
    vault = _vault(tmp_path)
    custom_out = tmp_path / "custom-site"
    marker = "SLICE4_CUSTOM_OUT_MARKER_a1b2"
    _write_buildable_source(vault, marker=marker)
    _plant_lint_error(vault)

    args = build_parser().parse_args(
        [
            "all",
            "--no-sync",
            "--no-synth",
            "--skip-graph",
            "--lint-fail",
            "errors",
            "--vault",
            str(vault),
            "--out",
            str(custom_out),
        ]
    )

    rc = cli.cmd_all(args)
    assert rc == 2

    assert custom_out.is_dir()
    html_hits = [
        p
        for p in custom_out.rglob("*.html")
        if marker in p.read_text(encoding="utf-8", errors="replace")
    ]
    assert html_hits, "custom --out HTML from this build must remain after lint-fail"

    ops = read_state(vault / "llmwiki-state.json")["ops"]
    assert ops["last_lint_status"] == "failed"
    assert ops["last_lint_error"]

    sidecar = _parse_site_sidecar(custom_out)
    assert sidecar["ops"]["last_lint_status"] == "failed"
    assert sidecar["ops"]["last_lint_error"] == ops["last_lint_error"]
    assert sidecar["ops"]["last_lint_run_at"] == ops["last_lint_run_at"]
    assert sidecar["ops"]["last_build_at"] == ops["last_build_at"]
