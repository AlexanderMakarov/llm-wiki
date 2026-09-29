"""Tests for ``scripts/release_demo_gate.py`` (#240).

# @layer: unit
# @spec: 250-release-demo-local-review
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "release_demo_gate.py"


@pytest.fixture(scope="module")
def gate():
    spec = importlib.util.spec_from_file_location("release_demo_gate", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(autouse=True)
def fresh_demo(gate, monkeypatch):
    """Default: the committed demo is current, so step tests exercise the steps."""
    monkeypatch.setattr(gate, "stale_demo_docs", lambda: [])
    monkeypatch.setattr(gate, "pending_demo_sessions", lambda: [])


def test_stale_demo_docs_stop_the_gate_before_any_step(gate, monkeypatch, capsys, tmp_path: Path):
    """A docs change merged after the demo refresh re-stales it; the gate must
    say so instead of building and approving the old corpus."""
    monkeypatch.setattr(
        gate, "stale_demo_docs",
        lambda: ["remove docs/reference/cli.md", "add docs/reference/cli.md"],
    )
    usage = MagicMock(return_value=0)
    run = MagicMock(return_value=0)
    monkeypatch.setattr(gate, "_run_generate_usage", usage)
    monkeypatch.setattr(gate, "_run", run)

    code = gate.run_gate(today="2026-09-14", out=tmp_path / "site")

    assert code != 0
    assert "docs/reference/cli.md" in capsys.readouterr().err
    usage.assert_not_called()
    run.assert_not_called()


def test_pending_demo_sessions_stop_the_gate(gate, monkeypatch, capsys, tmp_path: Path):
    monkeypatch.setattr(gate, "pending_demo_sessions", lambda: ["llm-wiki/2026-09-07T23-12-x.md"])
    monkeypatch.setattr(gate, "_run_generate_usage", lambda today: 0)
    monkeypatch.setattr(gate, "_run", MagicMock(return_value=0))

    code = gate.run_gate(today="2026-09-14", out=tmp_path / "site")

    assert code != 0
    assert "2026-09-07T23-12-x.md" in capsys.readouterr().err


def test_allow_stale_demo_skips_only_the_freshness_checks(gate, monkeypatch, tmp_path: Path):
    """A version-only cut opts out explicitly; build, tests and lint still run."""
    monkeypatch.setattr(gate, "stale_demo_docs", lambda: ["add docs/x.md"])
    monkeypatch.setattr(gate, "pending_demo_sessions", lambda: ["p/s.md"])
    monkeypatch.setattr(gate, "_run_generate_usage", lambda today: 0)
    run = MagicMock(return_value=0)
    monkeypatch.setattr(gate, "_run", run)

    code = gate.run_gate(today="2026-09-14", out=tmp_path / "site", allow_stale_demo=True)

    assert code == 0
    assert run.call_count == 3


def test_gate_runs_the_demo_content_tests_and_strict_lint(gate, monkeypatch, tmp_path: Path):
    """Demo-content regressions (search baseline, #248, integrity guards,
    privacy) and lint warnings used to surface only in the full suite."""
    monkeypatch.setattr(gate, "_run_generate_usage", lambda today: 0)
    calls: list[list[str]] = []
    monkeypatch.setattr(gate, "_run", lambda argv: calls.append(argv) or 0)

    assert gate.run_gate(today="2026-09-14", out=tmp_path / "site") == 0

    pytest_argv = next(c for c in calls if "pytest" in c)
    for test in gate.DEMO_CONTENT_TESTS:
        assert test in pytest_argv
        assert (REPO / test).is_file(), test
    lint_argv = next(c for c in calls if "lint" in c)
    assert "--fail-on-errors" in lint_argv and "--fail-on-warnings" in lint_argv


def test_dry_run_exits_zero_and_prints_url(gate, capsys, tmp_path: Path):
    out = tmp_path / "demo-site"
    code = gate.run_gate(today="2026-09-14", out=out, dry_run=True)
    assert code == 0
    text = capsys.readouterr().out
    assert "dry-run" in text
    assert "generate_demo_usage --today 2026-09-14" in text
    assert "file://" in text and "index.html" in text
    assert str(out) in text or out.resolve().as_uri() in text or "Review:" in text


def test_dry_run_skip_usage_notes_skip(gate, capsys, tmp_path: Path):
    code = gate.run_gate(
        today="2026-09-14", out=tmp_path / "site", dry_run=True, skip_usage=True,
    )
    assert code == 0
    text = capsys.readouterr().out
    assert "skip usage" in text.lower()
    assert "generate_demo_usage --today" not in text


def test_today_forwarded_to_usage(gate, monkeypatch, tmp_path: Path):
    seen: list[str] = []

    def fake_usage(today: str) -> int:
        seen.append(today)
        return 0

    monkeypatch.setattr(gate, "_run_generate_usage", fake_usage)
    monkeypatch.setattr(gate, "_run", lambda argv: 0)

    code = gate.run_gate(today="2026-09-12", out=tmp_path / "site", dry_run=False)
    assert code == 0
    assert seen == ["2026-09-12"]


def test_usage_failure_returns_nonzero(gate, monkeypatch, tmp_path: Path):
    monkeypatch.setattr(gate, "_run_generate_usage", lambda today: 5)
    run_called = MagicMock(return_value=0)
    monkeypatch.setattr(gate, "_run", run_called)
    code = gate.run_gate(today="2026-09-14", out=tmp_path / "site")
    assert code == 5
    run_called.assert_not_called()


def test_lint_failure_returns_nonzero(gate, monkeypatch, tmp_path: Path):
    monkeypatch.setattr(gate, "_run_generate_usage", lambda today: 0)

    def fake_run(argv: list[str]) -> int:
        joined = " ".join(argv)
        if " lint " in f" {joined} " or joined.endswith(" lint"):
            return 4
        if "test_case_insensitive_paths" in joined:
            return 0
        return 0

    monkeypatch.setattr(gate, "_run", fake_run)
    code = gate.run_gate(today="2026-09-14", out=tmp_path / "site")
    assert code == 4


def test_build_failure_returns_nonzero(gate, monkeypatch, tmp_path: Path):
    monkeypatch.setattr(gate, "_run_generate_usage", lambda today: 0)

    def fake_run(argv: list[str]) -> int:
        if "build" in argv:
            return 7
        return 0

    monkeypatch.setattr(gate, "_run", fake_run)
    code = gate.run_gate(today="2026-09-14", out=tmp_path / "site")
    assert code == 7


def test_case_fold_failure_returns_nonzero(gate, monkeypatch, tmp_path: Path):
    monkeypatch.setattr(gate, "_run_generate_usage", lambda today: 0)

    def fake_run(argv: list[str]) -> int:
        joined = " ".join(argv)
        if "pytest" in joined:
            return 3
        return 0

    monkeypatch.setattr(gate, "_run", fake_run)
    code = gate.run_gate(today="2026-09-14", out=tmp_path / "site")
    assert code == 3


def test_skip_usage_does_not_call_generator(gate, monkeypatch, tmp_path: Path):
    called = MagicMock(return_value=0)
    monkeypatch.setattr(gate, "_run_generate_usage", called)
    monkeypatch.setattr(gate, "_run", lambda argv: 0)

    code = gate.run_gate(
        today="2026-09-14", out=tmp_path / "site", skip_usage=True,
    )
    assert code == 0
    called.assert_not_called()


def test_main_requires_today(gate):
    with pytest.raises(SystemExit) as exc:
        gate.main([])
    assert exc.value.code != 0


def test_main_dry_run_cli(gate, capsys):
    code = gate.main(["--today", "2026-09-14", "--dry-run", "--out", "/tmp/demo-site"])
    assert code == 0
    assert "file://" in capsys.readouterr().out


def _fresh_gate():
    """A second module copy, so its real checks survive the autouse stubs."""
    spec = importlib.util.spec_from_file_location("release_demo_gate_real", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _session(vault: Path, project: str, name: str, *, headless: bool = False) -> Path:
    raw = vault / "raw" / "sessions" / project / name
    raw.parent.mkdir(parents=True, exist_ok=True)
    flag = "is_headless: true\n" if headless else ""
    raw.write_text(f"---\nslug: s\n{flag}---\n\n# Session\n", encoding="utf-8")
    return raw


def test_session_coverage_reads_pages_not_synth_state(tmp_path: Path, monkeypatch):
    """Synth state records mtimes, so a fresh checkout makes every committed
    session look pending; coverage must come from the pages' source_file."""
    real = _fresh_gate()
    vault = tmp_path / "demo"
    monkeypatch.setattr(real, "DEMO", vault)
    covered = _session(vault, "proj", "2026-09-01T10-00-proj-a.md")
    _session(vault, "proj", "2026-09-02T10-00-proj-b.md")
    _session(vault, "proj", "2026-09-03T10-00-proj-c.md", headless=True)
    page = vault / "wiki" / "sources" / "proj" / "2026-09-01-a.md"
    page.parent.mkdir(parents=True)
    rel = covered.relative_to(vault).as_posix()
    page.write_text(f"---\ntype: source\nsource_file: {rel}\n---\n", encoding="utf-8")

    assert real.pending_demo_sessions() == ["raw/sessions/proj/2026-09-02T10-00-proj-b.md"]


def test_committed_demo_passes_the_freshness_session_check():
    """Guards the check against a false alarm on the demo as committed."""
    assert _fresh_gate().pending_demo_sessions() == []
