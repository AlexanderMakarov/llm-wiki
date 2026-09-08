"""Unit tests for #234 Slice 1 — shared ops stamps + lint record helpers.

# @spec: 234-home-timeline-automation-stamps
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from llmwiki import cli, pipeline
from llmwiki.state_store import (
    configure_state_file,
    copy_state_sidecar_to_site,
    default_state,
    format_lint_error_for_ops,
    read_state,
    record_lint_ops,
    resolve_sidecar_file,
    stamp_last_build_at,
    stamp_last_synth_at,
    write_state,
)

# Ops keys Slice 1 adds (plus existing lint-run stamp already in defaults).
_NEW_OPS_KEYS = (
    "last_synth_at",
    "last_build_at",
    "last_lint_status",
    "last_lint_error",
)


def _vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    vault.mkdir()
    configure_state_file(vault)
    write_state(default_state(), vault / "llmwiki-state.json")
    return vault


# ─── Shape defaults ───────────────────────────────────────────────────────


def test_default_state_ops_includes_stage_stamp_keys_empty():
    """# @layer: unit  # @spec: 234-home-timeline-automation-stamps"""
    ops = default_state()["ops"]
    for key in _NEW_OPS_KEYS:
        assert key in ops
        assert ops[key] == ""
    assert ops["last_lint_run_at"] == ""


def test_ensure_shape_fills_missing_ops_stamp_keys(tmp_path: Path):
    """Legacy snapshots missing new ops keys get empty-string defaults.

    # @layer: unit  # @spec: 234-home-timeline-automation-stamps
    """
    vault = tmp_path / "vault"
    vault.mkdir()
    state_file = vault / "llmwiki-state.json"
    # Minimal / legacy-shaped payload — omit the Slice 1 keys entirely.
    state_file.write_text(
        json.dumps(
            {
                "queue": {"items": [], "legacy_pending_paths": []},
                "sync": {"files": {}, "meta": {}, "counters": {}},
                "synth": {
                    "files": {},
                    "pending": [],
                    "pending_total": 0,
                    "pending_updated_at": "",
                    "estimate": {},
                },
                "quarantine": {"entries": []},
                "ops": {"last_queue_run_at": "", "last_lint_run_at": ""},
                "meta": {"schema_version": 1, "updated_at": "", "revision": 0},
            }
        ),
        encoding="utf-8",
    )
    configure_state_file(vault)
    ops = read_state(state_file)["ops"]
    for key in _NEW_OPS_KEYS:
        assert ops[key] == ""


def test_ensure_shape_coerces_non_string_ops_stamp_values(tmp_path: Path):
    """# @layer: unit  # @spec: 234-home-timeline-automation-stamps"""
    vault = _vault(tmp_path)
    state_file = vault / "llmwiki-state.json"
    raw = read_state(state_file)
    raw["ops"]["last_synth_at"] = None
    raw["ops"]["last_lint_status"] = 0
    raw["ops"]["last_lint_error"] = ["not", "a", "string"]
    state_file.write_text(json.dumps(raw), encoding="utf-8")
    ops = read_state(state_file)["ops"]
    assert ops["last_synth_at"] == ""
    assert ops["last_lint_status"] == ""
    assert ops["last_lint_error"] == ""


# ─── Stamp writers ────────────────────────────────────────────────────────


def test_stamp_last_synth_at_sets_iso_z(tmp_path: Path):
    """# @layer: unit  # @spec: 234-home-timeline-automation-stamps"""
    vault = _vault(tmp_path)
    state_file = vault / "llmwiki-state.json"
    when = "2026-09-08T12:00:00Z"
    updated = stamp_last_synth_at(state_file, when=when)
    assert updated["ops"]["last_synth_at"] == when
    assert read_state(state_file)["ops"]["last_synth_at"] == when


def test_stamp_last_build_at_sets_iso_and_copies_site_sidecar(tmp_path: Path):
    """# @layer: unit  # @spec: 234-home-timeline-automation-stamps"""
    vault = _vault(tmp_path)
    site = vault / "site"
    site.mkdir()
    # Stale site sidecar so we can prove the copy ran.
    (site / "llmwiki-state.js").write_text(
        "window.LLMWIKI_STATE_SNAPSHOT = {\"stale\": true};\n",
        encoding="utf-8",
    )
    state_file = vault / "llmwiki-state.json"
    when = "2026-09-08T12:30:00Z"
    stamp_last_build_at(state_file, when=when, site_dir=site)
    assert read_state(state_file)["ops"]["last_build_at"] == when
    site_text = (site / "llmwiki-state.js").read_text(encoding="utf-8")
    assert "stale" not in site_text
    payload = json.loads(site_text.split("=", 1)[1].rstrip().rstrip(";"))
    assert payload["ops"]["last_build_at"] == when


def test_record_lint_ops_ok_clears_prior_error(tmp_path: Path):
    """Failed lint leaves multiline error; a later ok run clears it.

    # @layer: unit  # @spec: 234-home-timeline-automation-stamps
    """
    vault = _vault(tmp_path)
    state_file = vault / "llmwiki-state.json"
    multiline = "\n".join(
        [
            "wiki/concepts/Foo.md:1: broken_wikilink: [[Missing]]",
            "wiki/entities/Bar.md:2: orphan: no inbound links",
            "summary: 2 issue(s)",
        ]
    )
    record_lint_ops(
        failed=True,
        error_text=multiline,
        state_file=state_file,
        when="2026-09-08T13:00:00Z",
    )
    ops = read_state(state_file)["ops"]
    assert ops["last_lint_status"] == "failed"
    assert ops["last_lint_run_at"] == "2026-09-08T13:00:00Z"
    assert "broken_wikilink" in ops["last_lint_error"]
    assert "\n" in ops["last_lint_error"]

    record_lint_ops(
        failed=False,
        error_text="should be ignored on success",
        state_file=state_file,
        when="2026-09-08T13:05:00Z",
    )
    ops = read_state(state_file)["ops"]
    assert ops["last_lint_status"] == "ok"
    assert ops["last_lint_run_at"] == "2026-09-08T13:05:00Z"
    assert ops["last_lint_error"] == ""


def test_format_lint_error_for_ops_truncates_past_six_lines():
    """# @layer: unit  # @spec: 234-home-timeline-automation-stamps"""
    lines = [f"line-{i}" for i in range(1, 10)]
    stored = format_lint_error_for_ops("\n".join(lines))
    out_lines = stored.split("\n")
    assert out_lines[:6] == lines[:6]
    assert out_lines[-1] == "…"
    assert len(out_lines) == 7


def test_format_lint_error_skips_long_skipped_rules_preamble():
    """Long skipped-rules block must not crowd out ## finding lines on Home.

    # @layer: unit  # @spec: 234-home-timeline-automation-stamps
    """
    preamble = [
        "  scanned 12 pages",
        "  2 issues: 2 errors, 0 warnings, 0 info",
        "  skipped 9 of 11 rules (disabled in llmwiki.json):",
        "    - alpha: off",
        "    - beta: off",
        "    - gamma: off",
        "    - delta: off",
        "    - epsilon: off",
        "",
        "## frontmatter_validity (2)",
        "  [error] entities/Bogus.md: confidence must be a number",
        "  [error] entities/Other.md: missing title",
    ]
    stored = format_lint_error_for_ops("\n".join(preamble))
    assert "skipped 9 of 11" not in stored
    assert "frontmatter_validity" in stored
    assert "[error] entities/Bogus.md" in stored
    assert "2 issues: 2 errors" in stored
    # Still respects the ~6 line budget + ellipsis when findings are long.
    long_findings = preamble[:2] + [""] + [
        "## frontmatter_validity (8)",
        *[f"  [error] entities/E{i}.md: bad" for i in range(8)],
    ]
    truncated = format_lint_error_for_ops("\n".join(long_findings))
    assert truncated.endswith("…")
    assert "skipped" not in truncated


def test_record_lint_ops_failed_stores_truncated_multiline(tmp_path: Path):
    """# @layer: unit  # @spec: 234-home-timeline-automation-stamps"""
    vault = _vault(tmp_path)
    state_file = vault / "llmwiki-state.json"
    long_report = "\n".join(f"finding-{i}: detail" for i in range(1, 12))
    record_lint_ops(failed=True, error_text=long_report, state_file=state_file)
    err = read_state(state_file)["ops"]["last_lint_error"]
    parts = err.split("\n")
    assert parts[:6] == [f"finding-{i}: detail" for i in range(1, 7)]
    assert parts[-1] == "…"
    assert "finding-7:" not in err


# ─── Site sidecar without HTML rewrite ────────────────────────────────────


def test_copy_state_sidecar_to_site_updates_js_not_html(tmp_path: Path):
    """Lint/build helpers refresh site data only — leave HTML bytes alone.

    # @layer: unit  # @spec: 234-home-timeline-automation-stamps
    """
    vault = _vault(tmp_path)
    site = vault / "site"
    site.mkdir()
    html = site / "index.html"
    html_body = "<!DOCTYPE html><title>home</title><p>untouched</p>\n"
    html.write_text(html_body, encoding="utf-8")
    (site / "llmwiki-state.js").write_text(
        "window.LLMWIKI_STATE_SNAPSHOT = {};\n", encoding="utf-8"
    )

    stamp_last_synth_at(vault / "llmwiki-state.json", when="2026-09-08T14:00:00Z")
    # Vault sidecar exists from write_state / update_state; copy into site/.
    copy_state_sidecar_to_site(vault, site_dir=site)

    assert html.read_text(encoding="utf-8") == html_body
    site_payload = json.loads(
        (site / "llmwiki-state.js").read_text(encoding="utf-8").split("=", 1)[1].rstrip().rstrip(";")
    )
    assert site_payload["ops"]["last_synth_at"] == "2026-09-08T14:00:00Z"


def test_record_lint_ops_syncs_site_sidecar_without_touching_html(tmp_path: Path):
    """# @layer: unit  # @spec: 234-home-timeline-automation-stamps"""
    vault = _vault(tmp_path)
    site = vault / "site"
    site.mkdir()
    html = site / "other.html"
    html.write_text("<html>keep-me</html>\n", encoding="utf-8")
    before = html.read_bytes()

    record_lint_ops(
        failed=True,
        error_text="line-a\nline-b\nline-c",
        state_file=vault / "llmwiki-state.json",
        site_dir=site,
        when="2026-09-08T14:10:00Z",
    )

    assert html.read_bytes() == before
    site_text = (site / "llmwiki-state.js").read_text(encoding="utf-8")
    payload = json.loads(site_text.split("=", 1)[1].rstrip().rstrip(";"))
    assert payload["ops"]["last_lint_status"] == "failed"
    assert "line-a" in payload["ops"]["last_lint_error"]
    # Vault + site sidecars both present after the helper.
    assert resolve_sidecar_file(vault / "llmwiki-state.json").is_file()


def test_copy_state_sidecar_noop_when_site_missing(tmp_path: Path):
    """# @layer: unit  # @spec: 234-home-timeline-automation-stamps"""
    vault = _vault(tmp_path)
    # No site/ directory — must not raise.
    copy_state_sidecar_to_site(vault)
    assert not (vault / "site").exists()


# ─── Backend unavailable → no synth stamp ─────────────────────────────────


def test_pipeline_unavailable_backend_does_not_stamp_synth(tmp_path: Path):
    """When synth never runs, ``ops.last_synth_at`` stays empty.

    # @layer: unit  # @spec: 234-home-timeline-automation-stamps
    """
    vault = _vault(tmp_path)
    (vault / "raw" / "sessions").mkdir(parents=True)
    (vault / "wiki").mkdir()
    site = vault / "site"
    site.mkdir()

    backend = MagicMock()
    backend.name = "dummy"
    backend.is_available.return_value = False

    args = argparse.Namespace(
        out=site,
        search_mode="auto",
        skip_graph=True,
        graph_engine="builtin",
        strict=False,
        fail_fast=False,
        with_sync=False,
        with_synth=True,
        synth_force=False,
        skip_lint=True,
        vault=str(vault),
        lint_fail="never",
    )

    with (
        patch.object(pipeline, "resolve_backend", return_value=backend),
        patch.object(pipeline, "synthesize_new_sessions") as synth,
        patch.object(pipeline, "build_site", return_value=0),
        patch.object(pipeline, "_run_lint_step", return_value=(0, {})),
        patch.object(pipeline, "_maybe_print_optout_notice"),
        patch.object(pipeline, "_load_sessions_config", return_value={}),
    ):
        rc = cli.cmd_all(args)

    assert rc == 1
    synth.assert_not_called()
    assert read_state(vault / "llmwiki-state.json")["ops"]["last_synth_at"] == ""


def test_cmd_synthesize_unavailable_backend_does_not_stamp(tmp_path: Path, capsys):
    """Standalone ``synth`` exits before stamping when the backend is down.

    # @layer: unit  # @spec: 234-home-timeline-automation-stamps
    """
    vault = _vault(tmp_path)
    (vault / "raw" / "sessions").mkdir(parents=True)
    (vault / "wiki" / "sources").mkdir(parents=True)

    backend = MagicMock()
    backend.name = "ollama"
    backend.is_available.return_value = False

    args = argparse.Namespace(
        vault=str(vault),
        force=False,
        estimate=False,
        check=False,
        candidates_only=False,
        sources_only=True,
        paths=None,
        sessions_only=False,
        docs_only=False,
        concurrency=None,
        backend=None,
        cmd="synth",
    )

    with (
        patch.object(cli, "resolve_backend", return_value=backend),
        patch.object(cli, "_load_sessions_config", return_value={}),
        patch.object(cli, "synthesize_new_sessions") as synth,
    ):
        rc = cli.cmd_synthesize(args)

    assert rc == 1
    synth.assert_not_called()
    assert read_state(vault / "llmwiki-state.json")["ops"]["last_synth_at"] == ""
    assert "not available" in capsys.readouterr().err


def test_pipeline_available_backend_stamps_synth_even_with_file_errors(tmp_path: Path):
    """Backend ran → stamp even when some files errored (tech-spec assumption).

    # @layer: unit  # @spec: 234-home-timeline-automation-stamps
    """
    vault = _vault(tmp_path)
    (vault / "raw" / "sessions").mkdir(parents=True)
    (vault / "wiki").mkdir()
    site = vault / "site"
    site.mkdir()

    backend = MagicMock()
    backend.name = "dummy"
    backend.is_available.return_value = True

    args = argparse.Namespace(
        out=site,
        search_mode="auto",
        skip_graph=True,
        graph_engine="builtin",
        strict=False,
        fail_fast=False,
        with_sync=False,
        with_synth=True,
        synth_force=False,
        skip_lint=True,
        vault=str(vault),
        lint_fail="never",
    )

    summary = {
        "total_scanned": 1,
        "new_files": 1,
        "synthesized": 0,
        "skipped": 0,
        "errors": ["wiki/sources/x.md: boom"],
    }

    with (
        patch.object(pipeline, "resolve_backend", return_value=backend),
        patch.object(pipeline, "synthesize_new_sessions", return_value=summary),
        patch.object(pipeline, "run_harvest", return_value=0),
        patch.object(pipeline, "build_site", return_value=0),
        patch.object(pipeline, "_run_lint_step", return_value=(0, {})),
        patch.object(pipeline, "_maybe_print_optout_notice"),
        patch.object(pipeline, "_load_sessions_config", return_value={}),
    ):
        rc = cli.cmd_all(args)

    assert rc == 1  # synth reported errors
    stamped = read_state(vault / "llmwiki-state.json")["ops"]["last_synth_at"]
    assert stamped  # non-empty ISO stamp
    assert stamped.endswith("Z")
