"""Tests for the `llmwiki all` orchestrator (closes #422 and #583).

#422: `cmd_all` was calling `build_parser()` once *per step* (4× per
invocation). Wasteful argparse work AND a coupling smell.

#py-h4 (#583): `cmd_all` then re-parsed argv lists via the global
parser — semantically correct but the global parser still leaked into
`cmd_all`'s contract. Rewritten to direct-dispatch: each step gets a
Namespace constructed in-place with the defaults that subcommand
expects, and we call `cmd_build` / `cmd_graph` / `cmd_lint` directly.

#pipeline-lock-h1: that direct-dispatch design still called `cmd_build`
/ `cmd_sync` / `cmd_synthesize` from inside `llmwiki.pipeline.run_pipeline`,
each of which acquires the (non-reentrant) `pipeline_lock` itself — so
`llmwiki all` self-deadlocked the moment it tried to acquire a lock it
already held. `run_pipeline` now acquires `pipeline_lock` exactly once
and calls the **library** functions those `cmd_*` wrappers are thin
shims over directly (`convert_all`, `synthesize_new_sessions`,
`build_site`, plus the private `_run_graph_step` / `_run_lint_step`
helpers). These tests patch those library-level names on the
`llmwiki.pipeline` module — patching `cli.cmd_build` etc. no longer
intercepts anything, since `cmd_all` never calls them.

Export is no longer a separate pipeline step (part of build).
"""

from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import MagicMock, patch

from llmwiki import REPO_ROOT, cli, pipeline


def _mk_args(**overrides) -> argparse.Namespace:
    """Build a minimal Namespace that cmd_all / run_pipeline expects."""
    base = {
        "out": Path("/tmp/site-test"),
        "search_mode": "auto",
        "skip_graph": True,        # don't actually build a graph
        "graph_engine": "builtin",
        "strict": False,
        "fail_fast": False,
        "with_sync": False,
        "with_synth": False,
        "synth_force": False,
        "vault": None,
    }
    base.update(overrides)
    return argparse.Namespace(**base)


def test_cmd_all_does_not_use_global_parser():
    """#py-h4 (#583): cmd_all must NOT call build_parser() at all."""

    call_count = {"n": 0}
    original_build_parser = cli.build_parser

    def counting_build_parser():
        call_count["n"] += 1
        return original_build_parser()

    with patch.object(cli, "build_parser", side_effect=counting_build_parser):
        with patch.object(pipeline, "build_site", return_value=0):
            with patch.object(pipeline, "_run_lint_step", return_value=(0, {})):
                cli.cmd_all(_mk_args())

    assert call_count["n"] == 0, (
        f"cmd_all called build_parser() {call_count['n']} times "
        f"(expected 0 — see #583)"
    )


def test_cmd_all_default_returns_zero():
    """Smoke: with all sub-steps stubbed to succeed, cmd_all returns 0."""

    with patch.object(pipeline, "build_site", return_value=0):
        with patch.object(pipeline, "_run_lint_step", return_value=(0, {})):
            rc = cli.cmd_all(_mk_args())

    assert rc == 0


def test_cmd_all_propagates_failure_when_not_fail_fast():
    """Without --fail-fast, a non-zero step shouldn't abort early but
    the overall exit reflects the failure."""

    lint_stub = MagicMock(return_value=(0, {}))
    with patch.object(pipeline, "build_site", return_value=2):
        with patch.object(pipeline, "_run_lint_step", lint_stub):
            rc = cli.cmd_all(_mk_args(fail_fast=False))

    assert rc != 0
    assert lint_stub.call_count == 1


def test_cmd_all_fail_fast_aborts_on_first_failure():
    """With --fail-fast, the first non-zero step short-circuits."""

    lint_stub = MagicMock(return_value=(0, {}))
    with patch.object(pipeline, "build_site", return_value=2):
        with patch.object(pipeline, "_run_lint_step", lint_stub):
            rc = cli.cmd_all(_mk_args(fail_fast=True))

    assert rc == 2
    assert lint_stub.call_count == 0


def test_cmd_all_skip_graph_omits_graph_step():
    """--skip-graph (default in our test) → graph step never invoked."""

    graph_stub = MagicMock(return_value=0)
    with patch.object(pipeline, "_run_graph_step", graph_stub):
        with patch.object(pipeline, "build_site", return_value=0):
            with patch.object(pipeline, "_run_lint_step", return_value=(0, {})):
                rc = cli.cmd_all(_mk_args(skip_graph=True))

    assert rc == 0
    assert graph_stub.call_count == 0


def test_cmd_all_includes_graph_step_when_not_skipped():
    """Without --skip-graph, the graph step runs."""

    graph_stub = MagicMock(return_value=0)
    with patch.object(pipeline, "_run_graph_step", graph_stub):
        with patch.object(pipeline, "build_site", return_value=0):
            with patch.object(pipeline, "_run_lint_step", return_value=(0, {})):
                rc = cli.cmd_all(_mk_args(skip_graph=False))

    assert rc == 0
    assert graph_stub.call_count == 1


def test_cmd_all_strict_escalates_lint_warnings_to_failure():
    """--strict turns any lint error/warning into a pipeline failure,
    independent of lint's own (informational) exit code."""

    lint_stub = MagicMock(return_value=(0, {"error": 0, "warning": 1}))
    with patch.object(pipeline, "build_site", return_value=0):
        with patch.object(pipeline, "_run_lint_step", lint_stub):
            rc = cli.cmd_all(_mk_args(strict=True))

    assert rc == 2


def test_cmd_all_strict_false_keeps_lint_permissive():
    """Without --strict, lint warnings/errors don't fail the pipeline —
    only lint's own exit code (0 here) does."""

    lint_stub = MagicMock(return_value=(0, {"error": 0, "warning": 1}))
    with patch.object(pipeline, "build_site", return_value=0):
        with patch.object(pipeline, "_run_lint_step", lint_stub):
            rc = cli.cmd_all(_mk_args(strict=False))

    assert rc == 0


def test_cmd_all_out_dir_propagates_to_build():
    """--out flows through to build_site's out_dir kwarg."""

    build_stub = MagicMock(return_value=0)
    with patch.object(pipeline, "build_site", build_stub):
        with patch.object(pipeline, "_run_lint_step", return_value=(0, {})):
            cli.cmd_all(_mk_args(out=Path("/custom/out")))

    assert build_stub.call_args.kwargs["out_dir"] == Path("/custom/out")


def test_cmd_all_search_mode_propagates_to_build():
    """--search-mode flows through to build_site's search_mode kwarg."""

    build_stub = MagicMock(return_value=0)
    with patch.object(pipeline, "build_site", build_stub):
        with patch.object(pipeline, "_run_lint_step", return_value=(0, {})):
            cli.cmd_all(_mk_args(search_mode="tree"))

    assert build_stub.call_args.kwargs["search_mode"] == "tree"


def test_cmd_all_runs_build_graph_lint_by_default():
    """build → graph → lint, in that order (no separate export)."""

    order: list[str] = []

    def build_stub(**_kwargs):
        order.append("build")
        return 0

    def graph_stub(**_kwargs):
        order.append("graph")
        return 0

    def lint_stub(_wiki_dir, **_kwargs):
        order.append("lint")
        return 0, {}

    with patch.object(pipeline, "build_site", side_effect=build_stub):
        with patch.object(pipeline, "_run_graph_step", side_effect=graph_stub):
            with patch.object(pipeline, "_run_lint_step", side_effect=lint_stub):
                cli.cmd_all(_mk_args(skip_graph=False))

    assert order == ["build", "graph", "lint"]


def test_cmd_all_with_sync_and_synth_order():
    """--with-sync --with-synth → sync → synthesize → build → lint,
    with no separate export step."""

    order: list[str] = []

    def convert_all_stub(**_kwargs):
        order.append("sync:convert")
        return 0

    def refresh_synth_pending_stub(**_kwargs):
        order.append("sync:refresh_synth_pending")

    def reindex_wiki_stub(_wiki_dir):
        order.append("sync:reindex")
        return None

    def resolve_backend_stub(_config):
        order.append("synth:resolve_backend")
        backend = MagicMock()
        backend.name = "dummy"
        backend.is_available.return_value = True
        return backend

    def synthesize_new_sessions_stub(**_kwargs):
        order.append("synth:synthesize")
        return {"total_scanned": 0, "new_files": 0, "synthesized": 0, "skipped": 0, "errors": []}

    def build_stub(**_kwargs):
        order.append("build")
        return 0

    def lint_stub(_wiki_dir, **_kwargs):
        order.append("lint")
        return 0, {}

    with patch.object(pipeline, "convert_all", side_effect=convert_all_stub):
        with patch.object(pipeline, "refresh_synth_pending", side_effect=refresh_synth_pending_stub):
            with patch.object(pipeline, "reindex_wiki", side_effect=reindex_wiki_stub):
                with patch.object(pipeline, "resolve_backend", side_effect=resolve_backend_stub):
                    with patch.object(
                        pipeline, "synthesize_new_sessions", side_effect=synthesize_new_sessions_stub
                    ):
                        with patch.object(pipeline, "build_site", side_effect=build_stub):
                            with patch.object(pipeline, "_run_lint_step", side_effect=lint_stub):
                                rc = cli.cmd_all(
                                    _mk_args(with_sync=True, with_synth=True, skip_graph=True)
                                )

    assert rc == 0
    assert order == [
        "sync:convert",
        "sync:refresh_synth_pending",
        "sync:reindex",
        "synth:resolve_backend",
        "synth:synthesize",
        "build",
        "lint",
    ]


def test_cmd_all_vault_remaps_default_out_to_vault_site(tmp_path: Path):
    """Goal 4: when --vault is set and --out is still the repo-default
    site/, run_pipeline must remap the build's out_dir (and hence the
    printed banner) to <vault>/site — never the git clone's site/."""

    build_stub = MagicMock(return_value=0)
    with patch.object(pipeline, "build_site", build_stub):
        with patch.object(pipeline, "_run_lint_step", return_value=(0, {})):
            rc = cli.cmd_all(
                _mk_args(out=REPO_ROOT / "site", vault=str(tmp_path))
            )

    assert rc == 0
    assert build_stub.call_args.kwargs["out_dir"] == tmp_path / "site"
    assert build_stub.call_args.kwargs["wiki_dir"] == tmp_path / "wiki"


def test_cmd_all_vault_out_override_is_not_remapped(tmp_path: Path):
    """An explicit --out is never overridden, even in vault mode."""

    build_stub = MagicMock(return_value=0)
    custom_out = tmp_path / "custom-out"
    with patch.object(pipeline, "build_site", build_stub):
        with patch.object(pipeline, "_run_lint_step", return_value=(0, {})):
            cli.cmd_all(_mk_args(out=custom_out, vault=str(tmp_path)))

    assert build_stub.call_args.kwargs["out_dir"] == custom_out
