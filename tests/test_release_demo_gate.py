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
        if "test_case_insensitive_paths" in joined:
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
