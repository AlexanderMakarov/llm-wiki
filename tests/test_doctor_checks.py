"""Slice 3: live detectors A–F + env summary + check-mode mapping.

# @spec: 327-doctor
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from llmwiki.cli import main
from llmwiki.doctor import DoctorMode, run_doctor
from llmwiki.doctor.checks import (
    DETECTOR_IDS_A_TO_F,
    collect_env_summary,
    run_checks_a_to_f,
)
from llmwiki.doctor.kb import load_heal_kb
from llmwiki.install_hint import PythonEnv
from llmwiki.synth.base import DummySynthesizer


def _scaffold_vault(root: Path) -> Path:
    (root / "wiki").mkdir(parents=True)
    (root / "raw").mkdir(parents=True)
    return root


def _available_non_dummy() -> Any:
    backend = MagicMock()
    backend.is_available.return_value = True
    backend.is_llm = True
    type(backend).__name__ = "ClaudeCLISynthesizer"
    return backend


def _healthy_env() -> PythonEnv:
    return PythonEnv(
        executable="/usr/bin/python3",
        has_pip=True,
        uv_managed=False,
        has_uv=True,
        project_root=None,
    )


def _patch_healthy_deps(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("llmwiki.doctor.checks.find_spec", lambda name: object())
    monkeypatch.setattr("llmwiki.doctor.checks.discover_all", lambda: None)
    monkeypatch.setattr(
        "llmwiki.doctor.checks.get_available",
        lambda: {"claude_code": object()},
    )
    monkeypatch.setattr(
        "llmwiki.doctor.checks.resolve_backend",
        lambda cfg=None: _available_non_dummy(),
    )
    monkeypatch.setattr("llmwiki.doctor.checks.detect_env", _healthy_env)


def test_detector_ids_subset_of_heal_kb() -> None:
    kb = load_heal_kb()
    catalog_ids = {e["id"] for e in kb.entries}
    missing = DETECTOR_IDS_A_TO_F - catalog_ids
    assert not missing, f"detector ids missing from heal_kb.json: {sorted(missing)}"


def test_missing_add_extra_emits_catalog_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault = _scaffold_vault(tmp_path / "vault")

    def _fake_find_spec(name: str) -> Any:
        if name == "markitdown":
            return None
        if name == "graphify":
            return object()
        return object()

    monkeypatch.setattr("llmwiki.doctor.checks.find_spec", _fake_find_spec)
    monkeypatch.setattr(
        "llmwiki.doctor.checks.resolve_backend",
        lambda cfg=None: _available_non_dummy(),
    )
    monkeypatch.setattr(
        "llmwiki.doctor.checks.get_available",
        lambda: {"claude_code": object()},
    )
    monkeypatch.setattr("llmwiki.doctor.checks.discover_all", lambda: None)
    monkeypatch.setattr("llmwiki.doctor.checks.detect_env", _healthy_env)

    findings = run_checks_a_to_f(vault, cfg={"synthesis": {"backend": "claude"}})
    ids = {f.id for f in findings}
    assert "env.extra_add_missing" in ids
    assert "env.extra_graph_missing" not in ids


def test_dummy_backend_finding(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    vault = _scaffold_vault(tmp_path / "vault")
    monkeypatch.setattr("llmwiki.doctor.checks.find_spec", lambda name: object())
    monkeypatch.setattr("llmwiki.doctor.checks.discover_all", lambda: None)
    monkeypatch.setattr(
        "llmwiki.doctor.checks.get_available",
        lambda: {"claude_code": object()},
    )
    monkeypatch.setattr(
        "llmwiki.doctor.checks.resolve_backend",
        lambda cfg=None: DummySynthesizer(),
    )
    monkeypatch.setattr("llmwiki.doctor.checks.detect_env", _healthy_env)

    report = run_doctor(
        vault,
        mode=DoctorMode.CHECK,
        cfg={"synthesis": {"backend": "dummy"}},
    )
    ids = {f.id for f in report.findings}
    assert "synth.backend_dummy" in ids
    assert report.exit_code == 1


def test_good_vault_smoke_exit_0(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault = _scaffold_vault(tmp_path / "vault")
    _patch_healthy_deps(monkeypatch)

    report = run_doctor(
        vault,
        mode=DoctorMode.CHECK,
        cfg={"synthesis": {"backend": "claude"}},
    )
    assert report.exit_code == 0
    assert not any(f.actionable for f in report.findings)
    assert "python" in report.env_summary
    assert "synthesis_backend" in report.env_summary or "catalog_version" in report.env_summary


def test_env_summary_keys(tmp_path: Path) -> None:
    vault = _scaffold_vault(tmp_path / "vault")
    summary = collect_env_summary(vault, cfg={"synthesis": {"backend": "dummy"}})
    for key in (
        "llmwiki_version",
        "python",
        "os",
        "catalog_version",
        "extra_add",
        "extra_graph",
        "synthesis_backend_config",
    ):
        assert key in summary


def test_cli_check_shows_environment(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    vault = _scaffold_vault(tmp_path / "vault")
    _patch_healthy_deps(monkeypatch)
    code = main(["doctor", "--check", "--vault", str(vault)])
    assert code == 0
    out = capsys.readouterr().out
    assert "environment:" in out
    assert "llmwiki_version:" in out
