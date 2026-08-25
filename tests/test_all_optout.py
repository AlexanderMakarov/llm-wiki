"""`llmwiki all` runs every stage by default, with a per-stage opt-out (#156).

The stage guards inside ``run_pipeline`` are unchanged — the flip lives at the
argparse default, so these tests pin both halves: what the parser produces, and
what ``run_pipeline`` does with it.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from llmwiki import cli, pipeline
from llmwiki.cli import build_parser


class _FakeTTY(io.StringIO):
    """Stand-in for an interactive stdout: captures text, reports a TTY."""

    def isatty(self) -> bool:
        return True


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    """A throwaway vault root so no test can touch a real one."""
    (tmp_path / "raw" / "sessions").mkdir(parents=True)
    (tmp_path / "wiki").mkdir()
    return tmp_path


def _parse(*argv: str):
    return build_parser().parse_args(["all", *argv])


def _run(args, *, lint: tuple[int, dict[str, int]] = (0, {})) -> int:
    """Run ``cmd_all`` with every step stubbed out, returning its exit code."""
    with (
        patch.object(pipeline, "_maybe_print_optout_notice"),
        patch.object(pipeline, "convert_all", return_value=0),
        patch.object(pipeline, "refresh_synth_pending"),
        patch.object(pipeline, "reindex_wiki", return_value=None),
        patch.object(pipeline, "build_site", return_value=0),
        patch.object(pipeline, "_run_lint_step", return_value=lint),
    ):
        return cli.cmd_all(args)


# ─── Defaults and opt-outs ───────────────────────────────────────────────


def test_bare_all_enables_every_stage():
    args = _parse()
    assert args.with_sync is True
    assert args.with_synth is True
    assert args.skip_graph is False
    assert args.skip_lint is False
    assert args.lint_fail == "never"


def test_no_sync_leaves_synth_on():
    args = _parse("--no-sync")
    assert args.with_sync is False
    assert args.with_synth is True


def test_no_synth_leaves_sync_on():
    args = _parse("--no-synth")
    assert args.with_sync is True
    assert args.with_synth is False


# ─── Deprecated aliases ──────────────────────────────────────────────────


def test_legacy_command_line_still_parses_and_runs_every_stage(vault: Path, capsys):
    """An already-installed scheduled command must not die on argparse."""
    args = _parse("--with-sync", "--with-synth", "--skip-graph", "--vault", str(vault))
    assert args.with_sync is True
    assert args.with_synth is True
    assert args.legacy_with_sync is True
    assert args.legacy_with_synth is True

    order: list[str] = []
    backend = MagicMock()
    backend.name = "dummy"
    backend.is_available.return_value = True

    def track(name: str, result):
        def _stub(*_a, **_k):
            order.append(name)
            return result
        return _stub

    synth_summary = {
        "total_scanned": 0, "new_files": 0,
        "synthesized": 0, "skipped": 0, "errors": [],
    }

    with (
        patch.object(pipeline, "_maybe_print_optout_notice"),
        patch.object(pipeline, "convert_all", side_effect=track("sync", 0)),
        patch.object(pipeline, "refresh_synth_pending"),
        patch.object(pipeline, "reindex_wiki", return_value=None),
        patch.object(pipeline, "resolve_backend", return_value=backend),
        patch.object(pipeline, "synthesize_new_sessions",
                     side_effect=track("synth", synth_summary)),
        patch.object(pipeline, "run_harvest", side_effect=track("harvest", 0)),
        patch.object(pipeline, "build_site", side_effect=track("build", 0)),
        patch.object(pipeline, "_run_lint_step", side_effect=track("lint", (0, {}))),
    ):
        rc = cli.cmd_all(args)

    assert rc == 0
    assert order == ["sync", "synth", "harvest", "build", "lint"]
    assert "--with-sync / --with-synth are no longer needed" in capsys.readouterr().err


def test_no_synth_wins_over_with_synth(vault: Path):
    """Documented resolution: the opt-out wins, whatever the flag order."""
    args = _parse("--no-synth", "--with-synth", "--skip-graph", "--vault", str(vault))
    assert args.with_synth is False

    synth = MagicMock()
    with patch.object(pipeline, "synthesize_new_sessions", synth):
        assert _run(args) == 0
    assert synth.call_count == 0


# ─── Lint step ───────────────────────────────────────────────────────────


def test_skip_lint_skips_the_lint_step(vault: Path):
    args = _parse("--no-sync", "--no-synth", "--skip-graph",
                  "--skip-lint", "--vault", str(vault))
    lint = MagicMock(return_value=(0, {}))
    with (
        patch.object(pipeline, "build_site", return_value=0),
        patch.object(pipeline, "_run_lint_step", lint),
    ):
        rc = cli.cmd_all(args)

    assert rc == 0
    assert lint.call_count == 0


@pytest.mark.parametrize(
    ("policy", "summary", "expected_rc"),
    [
        ("never", {}, 0),
        ("never", {"error": 1}, 0),
        ("never", {"warning": 1}, 0),
        ("errors", {}, 0),
        ("errors", {"error": 1}, 2),
        ("errors", {"warning": 1}, 0),
        ("warnings", {}, 0),
        ("warnings", {"error": 1}, 2),
        ("warnings", {"warning": 1}, 2),
    ],
)
def test_lint_fail_policy_matrix(vault: Path, policy: str,
                                 summary: dict[str, int], expected_rc: int):
    args = _parse("--no-sync", "--no-synth", "--skip-graph",
                  "--lint-fail", policy, "--vault", str(vault))
    assert _run(args, lint=(0, summary)) == expected_rc


@pytest.mark.parametrize("summary", [{}, {"error": 1}, {"warning": 1}])
def test_strict_matches_lint_fail_warnings(vault: Path, summary: dict[str, int]):
    strict = _parse("--no-sync", "--no-synth", "--skip-graph",
                    "--strict", "--vault", str(vault))
    explicit = _parse("--no-sync", "--no-synth", "--skip-graph",
                      "--lint-fail", "warnings", "--vault", str(vault))

    assert pipeline.resolve_lint_fail(strict) == "warnings"
    assert pipeline.resolve_lint_fail(explicit) == "warnings"
    assert _run(strict, lint=(0, summary)) == _run(explicit, lint=(0, summary))


def test_resolve_lint_fail_takes_the_stricter_of_both_flags():
    args = _parse("--strict", "--lint-fail", "errors")
    assert pipeline.resolve_lint_fail(args) == "warnings"


# ─── First-run notice ────────────────────────────────────────────────────


def test_notice_is_silent_when_stdout_is_not_a_tty(tmp_path: Path, capsys, monkeypatch):
    monkeypatch.setattr(pipeline, "load_synthesis_backend", lambda: "ollama")
    monkeypatch.setattr(pipeline, "resolve_state_file",
                        lambda *_a, **_k: tmp_path / "state.json")

    pipeline._maybe_print_optout_notice()

    assert capsys.readouterr().out == ""


def test_notice_is_silent_for_the_dummy_backend_on_a_tty(tmp_path: Path, monkeypatch):
    fake = _FakeTTY()
    monkeypatch.setattr(sys, "stdout", fake)
    monkeypatch.setattr(pipeline, "load_synthesis_backend", lambda: "dummy")
    monkeypatch.setattr(pipeline, "resolve_state_file",
                        lambda *_a, **_k: tmp_path / "state.json")

    pipeline._maybe_print_optout_notice()

    assert fake.getvalue() == ""


def test_notice_prints_once_on_a_tty_with_a_real_backend(tmp_path: Path, monkeypatch):
    fake = _FakeTTY()
    monkeypatch.setattr(sys, "stdout", fake)
    monkeypatch.setattr(pipeline, "load_synthesis_backend", lambda: "ollama")
    monkeypatch.setattr(pipeline, "resolve_state_file",
                        lambda *_a, **_k: tmp_path / "state.json")

    pipeline._maybe_print_optout_notice()
    first = fake.getvalue()
    pipeline._maybe_print_optout_notice()

    assert "--no-synth" in first
    assert fake.getvalue() == first
