"""Slice 5: runners + consent heal loop.

# @spec: 327-doctor
"""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from llmwiki.doctor import DoctorMode, run_doctor
from llmwiki.doctor.kb import HealKBError, finding_from_entry, get_entry, validate_catalog
from llmwiki.doctor.models import Finding
from llmwiki.doctor.runners import (
    RunnerResult,
    command_requires_elevation,
    dispatch_runner,
    runner_is_dangerous,
)
from llmwiki.install_hint import PythonEnv


def _scaffold_vault(root: Path) -> Path:
    (root / "wiki").mkdir(parents=True)
    (root / "raw").mkdir(parents=True)
    return root


def _dirty_index_vault(root: Path) -> Path:
    vault = _scaffold_vault(root)
    (vault / "wiki" / "entities").mkdir()
    (vault / "wiki" / "entities" / "Foo.md").write_text(
        "---\ntitle: Foo\ntype: entity\n---\n\n# Foo\n",
        encoding="utf-8",
    )
    (vault / "wiki" / "index.md").write_text(
        "# Wiki Index\n\n## Overview (0)\n",
        encoding="utf-8",
    )
    return vault


def _healthy_env() -> PythonEnv:
    return PythonEnv(
        executable="/usr/bin/python3",
        has_pip=True,
        uv_managed=False,
        has_uv=True,
        project_root=None,
    )


def _available_non_dummy() -> Any:
    backend = MagicMock()
    backend.is_available.return_value = True
    backend.is_llm = True
    type(backend).__name__ = "ClaudeCLISynthesizer"
    return backend


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


def test_candidates_review_action_is_rejected() -> None:
    result = dispatch_runner("candidates:review", Path("."))
    assert result.ok is False
    assert "Unknown candidates action" in result.message


def test_dangerous_tier_requires_runner() -> None:
    areas = {
        letter: {"title": letter, "summary": letter}
        for letter in "ABCDEFGHIJKLMNO"
    }
    raw = {
        "version": 1,
        "areas": areas,
        "entries": [
            {
                "id": "stub.x",
                "area": "K",
                "patterns": ["x"],
                "message": "m",
                "fix": "f",
                "actionable": True,
                "severity": "warning",
                "tier": "dangerous",
                "runner": None,
            }
        ],
        "unknown_templates": {"issue_body": "i", "ai_prompt": "a"},
    }
    with pytest.raises(HealKBError, match="non-null runner"):
        validate_catalog(raw)


def test_command_requires_elevation_detects_sudo() -> None:
    assert command_requires_elevation(["sudo", "pip", "install", "x"]) is True
    assert command_requires_elevation(["python3", "-m", "pip", "install", "x"]) is False


def test_runner_is_dangerous_synth() -> None:
    assert runner_is_dangerous("synth") is True
    assert runner_is_dangerous("reindex") is False
    assert runner_is_dangerous("install_extra:add") is True
    assert runner_is_dangerous("migrate:broken-provenance") is True


def test_dispatch_refuses_sudo_runner(tmp_path: Path) -> None:
    vault = _scaffold_vault(tmp_path / "vault")
    result = dispatch_runner("sudo", vault)
    assert result.ok is False
    assert result.refused_elevation is True
    assert result.mutated is False


def test_reindex_runner_mutates_dirty_index(tmp_path: Path) -> None:
    vault = _dirty_index_vault(tmp_path / "vault")
    before = (vault / "wiki" / "index.md").read_text(encoding="utf-8")
    result = dispatch_runner("reindex", vault)
    assert result.ok is True
    assert result.mutated is True
    after = (vault / "wiki" / "index.md").read_text(encoding="utf-8")
    assert after != before
    assert "Foo" in after or "entities/Foo.md" in after


def test_check_mode_never_calls_runners(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault = _dirty_index_vault(tmp_path / "vault")
    _patch_healthy_deps(monkeypatch)
    called: list[str] = []

    def _track(runner: str, vault_path: Path, **kwargs: Any):
        called.append(runner)
        raise AssertionError("runners must not run in --check")

    monkeypatch.setattr("llmwiki.doctor.dispatch_runner", _track)
    before = (vault / "wiki" / "index.md").read_text(encoding="utf-8")
    report = run_doctor(
        vault,
        mode=DoctorMode.CHECK,
        yes=True,
        cfg={"synthesis": {"backend": "claude"}},
    )
    assert called == []
    assert (vault / "wiki" / "index.md").read_text(encoding="utf-8") == before
    assert any(f.id == "lint.index_sync" for f in report.findings)


def test_non_tty_without_yes_no_mutate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault = _dirty_index_vault(tmp_path / "vault")
    _patch_healthy_deps(monkeypatch)
    before = (vault / "wiki" / "index.md").read_text(encoding="utf-8")
    report = run_doctor(
        vault,
        mode=DoctorMode.HEAL,
        yes=False,
        is_tty=False,
        cfg={"synthesis": {"backend": "claude"}},
        stdout=StringIO(),
    )
    assert (vault / "wiki" / "index.md").read_text(encoding="utf-8") == before
    assert any(f.id == "lint.index_sync" for f in report.findings)
    assert report.exit_code == 1


def test_yes_applies_reindex_safe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault = _dirty_index_vault(tmp_path / "vault")
    _patch_healthy_deps(monkeypatch)
    report = run_doctor(
        vault,
        mode=DoctorMode.HEAL,
        yes=True,
        is_tty=False,
        cfg={"synthesis": {"backend": "claude"}},
        stdout=StringIO(),
    )
    text = (vault / "wiki" / "index.md").read_text(encoding="utf-8")
    assert "Foo" in text or "entities/Foo.md" in text
    # Re-check should clear index_sync when reindex succeeded.
    assert not any(f.id == "lint.index_sync" for f in report.findings)


def test_yes_does_not_invoke_synth(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault = _scaffold_vault(tmp_path / "vault")
    (vault / "wiki" / "index.md").write_text("# Wiki Index\n", encoding="utf-8")
    _patch_healthy_deps(monkeypatch)

    # Force a dangerous synth finding into diagnose.
    entry = get_entry("pipeline.backlog_overdue")
    assert entry is not None
    synth_finding = finding_from_entry(entry)

    def _fake_diagnose(vault_path: Path, **kwargs: Any) -> list[Finding]:
        return [synth_finding]

    called: list[str] = []

    def _track(runner: str, vault_path: Path, **kwargs: Any):
        called.append(runner)
        return RunnerResult(ok=True, runner=runner, message="ok", mutated=True)

    monkeypatch.setattr("llmwiki.doctor.diagnose", _fake_diagnose)
    monkeypatch.setattr("llmwiki.doctor.dispatch_runner", _track)

    run_doctor(
        vault,
        mode=DoctorMode.HEAL,
        yes=True,
        is_tty=False,
        cfg={"synthesis": {"backend": "claude"}},
        stdout=StringIO(),
    )
    assert "synth" not in called


def test_tty_confirm_can_apply_reindex(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault = _dirty_index_vault(tmp_path / "vault")
    _patch_healthy_deps(monkeypatch)
    report = run_doctor(
        vault,
        mode=DoctorMode.HEAL,
        yes=False,
        is_tty=True,
        confirm_fn=lambda prompt: True,
        cfg={"synthesis": {"backend": "claude"}},
        stdout=StringIO(),
    )
    text = (vault / "wiki" / "index.md").read_text(encoding="utf-8")
    assert "Foo" in text or "entities/Foo.md" in text
    assert not any(f.id == "lint.index_sync" for f in report.findings)


def test_elevation_refused_via_dispatch(tmp_path: Path) -> None:
    vault = _scaffold_vault(tmp_path / "vault")
    result = dispatch_runner("sudo rm -rf /", vault)
    assert result.refused_elevation is True
    assert result.mutated is False
