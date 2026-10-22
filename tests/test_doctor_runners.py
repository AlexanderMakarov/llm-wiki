"""Slice 5: runners + consent heal loop.

# @spec: 327-doctor
"""

from __future__ import annotations

import json
import shlex
import subprocess
import sys
from dataclasses import replace
from io import StringIO
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from llmwiki.cli import build_parser
from llmwiki.doctor import DoctorMode, _confirm_finding, run_doctor
from llmwiki.doctor import runners as runners_module
from llmwiki.doctor.kb import HealKBError, finding_from_entry, get_entry, validate_catalog
from llmwiki.doctor.models import Finding
from llmwiki.doctor.runners import (
    RunnerResult,
    command_requires_elevation,
    dispatch_runner,
    install_automation_argv,
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


# ─── install_automation runner (@spec: 330-doctor-automation-serves-vault) ───

_MAINTAIN_STATUS: dict[str, Any] = {
    "job": "maintain",
    "graph": "builtin",
    "lint_fail": "errors",
    "schedule": "30 7 * * 1-5",
    "synth_backend": "ollama",
    "watch_enabled": True,
}


def _write_status(vault: Path, status: dict[str, Any]) -> None:
    (vault / ".llmwiki").mkdir(parents=True, exist_ok=True)
    (vault / ".llmwiki" / "automation-status.json").write_text(json.dumps(status), encoding="utf-8")


def _automation_finding(vault: Path, status: dict[str, Any]) -> Finding:
    entry = get_entry("automation.points_elsewhere")
    assert entry is not None
    return replace(
        finding_from_entry(entry),
        runner_argv=tuple(install_automation_argv(vault, status)),
    )


def test_install_automation_argv_mirrors_status(tmp_path: Path) -> None:
    vault = _scaffold_vault(tmp_path / "vault")
    argv = install_automation_argv(vault, _MAINTAIN_STATUS)
    assert argv == [
        "install-automation",
        "--vault",
        str(vault.resolve()),
        "--yes",
        "--force",
        "--job",
        "maintain",
        "--graph",
        "builtin",
        "--lint-fail",
        "errors",
        "--schedule",
        "30 7 * * 1-5",
        "--synth-backend",
        "ollama",
        "--watch-enabled",
    ]


def test_install_automation_argv_omits_parser_defaults(tmp_path: Path) -> None:
    vault = _scaffold_vault(tmp_path / "vault")
    argv = install_automation_argv(vault, {"job": "ingest", "hour": 9, "minute": 15})
    assert argv == [
        "install-automation",
        "--vault",
        str(vault.resolve()),
        "--yes",
        "--force",
        "--job",
        "ingest",
        "--schedule",
        "15 9 * * *",
    ]


def test_install_automation_argv_without_job_uses_plan_defaults(tmp_path: Path) -> None:
    vault = _scaffold_vault(tmp_path / "vault")
    argv = install_automation_argv(vault, None)
    assert argv[argv.index("--job") + 1] == "ingest"
    assert argv[argv.index("--schedule") + 1] == "0 8 * * *"


@pytest.mark.parametrize(
    "status",
    [_MAINTAIN_STATUS, {"job": "ingest"}, {}],
    ids=["maintain-all-extras", "ingest", "empty"],
)
def test_install_automation_argv_parses_with_real_cli(tmp_path: Path, status: dict[str, Any]) -> None:
    vault = _scaffold_vault(tmp_path / "vault")
    args = build_parser().parse_args(install_automation_argv(vault, status))
    plan = install_automation_argv(vault, status)
    assert args.yes is True
    assert args.force is True
    assert args.vault is not None and Path(args.vault) == vault.resolve()
    assert args.job == plan[plan.index("--job") + 1]
    assert args.schedule == plan[plan.index("--schedule") + 1]


def test_dispatch_install_automation_runs_status_argv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault = _scaffold_vault(tmp_path / "vault")
    _write_status(vault, _MAINTAIN_STATUS)
    calls: list[tuple[list[str], dict[str, Any]]] = []

    def _fake_run(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 0, stdout="installed", stderr="")

    monkeypatch.setattr("llmwiki.doctor.runners.subprocess.run", _fake_run)
    result = dispatch_runner("install_automation", vault)
    assert result.ok is True
    assert result.mutated is True
    assert len(calls) == 1
    argv, kwargs = calls[0]
    assert argv == [sys.executable, "-m", "llmwiki", *install_automation_argv(vault, _MAINTAIN_STATUS)]
    assert "--yes" in argv
    assert kwargs["cwd"] == runners_module.REPO_ROOT


@pytest.mark.parametrize(
    ("git_kind", "warning"),
    [
        ("file", "installing from a git worktree — the scheduled job will keep using this copy"),
        ("dir", "installing from a development checkout — the scheduled job will keep using this copy"),
    ],
)
def test_confirm_shows_exact_argv_and_dev_checkout_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, git_kind: str, warning: str
) -> None:
    vault = _scaffold_vault(tmp_path / "vault")
    root = tmp_path / "checkout"
    root.mkdir()
    if git_kind == "file":
        (root / ".git").write_text("gitdir: /elsewhere\n", encoding="utf-8")
    else:
        (root / ".git").mkdir()
    monkeypatch.setattr("llmwiki.doctor.REPO_ROOT", root)
    finding = _automation_finding(vault, _MAINTAIN_STATUS)
    out = StringIO()
    assert _confirm_finding(
        finding, yes=False, is_tty=True, confirm_fn=lambda prompt: False, stdout=out
    ) is False
    text = out.getvalue()
    expected = shlex.join([sys.executable, "-m", "llmwiki", *install_automation_argv(vault, _MAINTAIN_STATUS)])
    assert f"will run: {expected}" in text
    assert f"runs from: {root}" in text
    assert warning in text


def test_confirm_has_no_dev_warning_outside_a_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault = _scaffold_vault(tmp_path / "vault")
    root = tmp_path / "site-packages"
    root.mkdir()
    monkeypatch.setattr("llmwiki.doctor.REPO_ROOT", root)
    out = StringIO()
    _confirm_finding(
        _automation_finding(vault, _MAINTAIN_STATUS),
        yes=False,
        is_tty=True,
        confirm_fn=lambda prompt: False,
        stdout=out,
    )
    assert f"runs from: {root}" in out.getvalue()
    assert "warning:" not in out.getvalue()


def test_yes_non_tty_does_not_run_install_automation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault = _scaffold_vault(tmp_path / "vault")
    (vault / "wiki" / "index.md").write_text("# Wiki Index\n", encoding="utf-8")
    _patch_healthy_deps(monkeypatch)
    finding = _automation_finding(vault, _MAINTAIN_STATUS)
    monkeypatch.setattr("llmwiki.doctor.diagnose", lambda vault_path, **kwargs: [finding])
    called: list[str] = []

    def _track(runner: str, vault_path: Path, **kwargs: Any) -> RunnerResult:
        called.append(runner)
        return RunnerResult(ok=True, runner=runner, message="ok", mutated=True)

    monkeypatch.setattr("llmwiki.doctor.dispatch_runner", _track)
    out = StringIO()
    run_doctor(
        vault,
        mode=DoctorMode.HEAL,
        yes=True,
        is_tty=False,
        cfg={"synthesis": {"backend": "claude"}},
        stdout=out,
    )
    assert called == []
    assert "skip dangerous (need TTY confirm): automation.points_elsewhere" in out.getvalue()
    assert "--force" in out.getvalue()


def test_install_automation_argv_reproduces_a_custom_units_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    vault = _scaffold_vault(tmp_path / "vault")
    custom = tmp_path / "home" / "staging"
    argv = install_automation_argv(vault, {"job": "ingest", "units_written": [str(custom / "job.sh")]})
    assert argv[argv.index("--units-dir") + 1] == str(custom)
    default = tmp_path / "home" / ".automation"
    argv = install_automation_argv(vault, {"job": "ingest", "units_written": [str(default / "job.sh")]})
    assert "--units-dir" not in argv


def test_install_automation_argv_ignores_a_recorded_units_dir_outside_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    vault = _scaffold_vault(tmp_path / "vault")
    argv = install_automation_argv(vault, {"job": "ingest", "units_written": [str(tmp_path / "elsewhere" / "job.sh")]})
    assert "--units-dir" not in argv
