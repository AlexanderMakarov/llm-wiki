"""Slice 4: lint fold, backlog overdue-only, detectors G–O.

# @spec: 327-doctor
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from llmwiki.automation_status import save_status
from llmwiki.doctor import DoctorMode, run_doctor
from llmwiki.doctor.checks import (
    DETECTOR_IDS,
    DETECTOR_IDS_G_TO_O,
    check_candidates_review,
    check_pipeline_backlog,
    run_checks_a_to_f,
)
from llmwiki.doctor.kb import load_heal_kb
from llmwiki.doctor.lint_fold import (
    fold_lint_issues,
    run_lint_fold,
    should_skip_lint,
)
from llmwiki.doctor.models import Finding, FixTier
from llmwiki.install_hint import PythonEnv
from llmwiki.lint import rules as _lint_rules  # noqa: F401
from llmwiki.state_store import write_state

assert _lint_rules is not None  # register lint REGISTRY for fold tests


def _scaffold_vault(root: Path) -> Path:
    (root / "wiki").mkdir(parents=True)
    (root / "raw" / "sessions").mkdir(parents=True)
    return root


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


def test_detector_ids_g_to_o_subset_of_heal_kb() -> None:
    kb = load_heal_kb()
    catalog_ids = {e["id"] for e in kb.entries}
    missing = DETECTOR_IDS_G_TO_O - catalog_ids
    assert not missing, f"detector ids missing from heal_kb.json: {sorted(missing)}"
    missing_all = DETECTOR_IDS - catalog_ids
    assert not missing_all


def test_should_skip_lint_error_lookup() -> None:
    assert should_skip_lint(error_lookup=True, early_findings=[]) is True


def test_should_skip_lint_early_actionable_error() -> None:
    early = [
        Finding(
            id="synth.backend_unavailable",
            area="F",
            message="backend down",
            fix="fix",
            actionable=True,
            severity="error",
            tier=FixTier.GUIDED,
            runner=None,
        )
    ]
    assert should_skip_lint(error_lookup=False, early_findings=early) is True


def test_should_not_skip_lint_on_warning_only() -> None:
    early = [
        Finding(
            id="env.extra_graph_missing",
            area="B",
            message="no graph",
            fix="fix",
            actionable=True,
            severity="warning",
            tier=FixTier.DANGEROUS,
            runner="install_extra:graph",
        )
    ]
    assert should_skip_lint(error_lookup=False, early_findings=early) is False


def test_check_mode_skips_lint_when_early_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault = _scaffold_vault(tmp_path / "vault")
    (vault / "wiki" / "orphan.md").write_text("# Orphan\n", encoding="utf-8")
    (vault / "wiki" / "index.md").write_text("# Index\n", encoding="utf-8")

    monkeypatch.setattr("llmwiki.doctor.checks.find_spec", lambda name: object())
    monkeypatch.setattr("llmwiki.doctor.checks.discover_all", lambda: None)
    monkeypatch.setattr(
        "llmwiki.doctor.checks.get_available",
        lambda: {"claude_code": object()},
    )
    monkeypatch.setattr("llmwiki.doctor.checks.detect_env", _healthy_env)

    def _boom(cfg=None):
        raise RuntimeError("backend boom")

    monkeypatch.setattr("llmwiki.doctor.checks.resolve_backend", _boom)

    called = {"lint": False}

    def _fake_lint(vault_path: Path):
        called["lint"] = True
        return []

    monkeypatch.setattr("llmwiki.doctor.run_lint_fold", _fake_lint)

    report = run_doctor(
        vault,
        mode=DoctorMode.CHECK,
        cfg={"synthesis": {"backend": "claude"}},
    )
    assert called["lint"] is False
    assert any(f.id == "synth.backend_unavailable" for f in report.findings)


def test_error_mode_skips_lint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault = _scaffold_vault(tmp_path / "vault")
    _patch_healthy_deps(monkeypatch)
    called = {"lint": False}

    def _fake_lint(vault_path: Path):
        called["lint"] = True
        return []

    monkeypatch.setattr("llmwiki.doctor.run_lint_fold", _fake_lint)
    run_doctor(
        vault,
        mode=DoctorMode.ERROR,
        error_text="completely unknown xyzzy symptom",
        is_tty=False,
    )
    assert called["lint"] is False


def test_fold_index_sync_maps_to_catalog_reindex() -> None:
    findings = fold_lint_issues(
        [
            {
                "rule": "index_sync",
                "severity": "error",
                "page": "index.md",
                "message": "page 'entities/Foo.md' not listed in index.md",
            }
        ]
    )
    assert len(findings) == 1
    assert findings[0].id == "lint.index_sync"
    assert findings[0].runner == "reindex"
    assert findings[0].tier == FixTier.SAFE


def test_fold_provenance_maps_to_catalog() -> None:
    findings = fold_lint_issues(
        [
            {
                "rule": "provenance_integrity",
                "severity": "error",
                "page": "sources/x.md",
                "message": "missing raw file",
            }
        ]
    )
    assert findings[0].id == "provenance.broken_chain"


def test_run_lint_fold_index_sync_on_dirty_index(tmp_path: Path) -> None:
    vault = _scaffold_vault(tmp_path / "vault")
    (vault / "wiki" / "entities").mkdir()
    (vault / "wiki" / "entities" / "Foo.md").write_text(
        "---\ntitle: Foo\ntype: entity\n---\n\n# Foo\n",
        encoding="utf-8",
    )
    (vault / "wiki" / "index.md").write_text(
        "# Wiki Index\n\n## Overview (0)\n",
        encoding="utf-8",
    )
    findings = run_lint_fold(vault)
    ids = {f.id for f in findings}
    assert "lint.index_sync" in ids
    sync = next(f for f in findings if f.id == "lint.index_sync")
    assert sync.runner == "reindex"


def test_pipeline_backlog_only_when_overdue(tmp_path: Path) -> None:
    vault = _scaffold_vault(tmp_path / "vault")
    now = datetime(2026, 10, 13, tzinfo=UTC)
    # Fresh pending — not overdue.
    write_state(
        {
            "synth": {
                "files": {},
                "pending": [{"rel": "sessions/a.md"}],
                "pending_total": 1,
                "pending_updated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
        },
        vault,
    )
    assert check_pipeline_backlog(vault, now=now, overdue_days=7) == []

    # Stale pending — overdue.
    old = (now - timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    write_state(
        {
            "synth": {
                "files": {},
                "pending": [{"rel": "sessions/a.md"}],
                "pending_total": 1,
                "pending_updated_at": old,
            }
        },
        vault,
    )
    findings = check_pipeline_backlog(vault, now=now, overdue_days=7)
    assert any(f.id == "pipeline.backlog_overdue" for f in findings)
    assert "unsynthesized" in findings[0].message.casefold()


_SCHEDULE_HINT = "Scheduled maintenance is recorded for this vault but may not be reaching it"


@pytest.mark.parametrize(
    ("status", "hinted"),
    [
        pytest.param({"job": "llmwiki-maintain"}, True, id="job-recorded"),
        pytest.param({"scheduler_activated": False}, False, id="no-job"),
        pytest.param(None, False, id="no-status"),
    ],
)
def test_pipeline_backlog_points_at_schedule_when_job_recorded(
    tmp_path: Path, status: dict[str, Any] | None, hinted: bool
) -> None:
    """@spec: 330-doctor-automation-serves-vault R6."""
    vault = _scaffold_vault(tmp_path / "vault")
    now = datetime(2026, 10, 13, tzinfo=UTC)
    old = (now - timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    write_state(
        {"synth": {"files": {}, "pending": [{"rel": "sessions/a.md"}], "pending_total": 1, "pending_updated_at": old}},
        vault,
    )
    if status is not None:
        save_status(vault, status)
    (found,) = check_pipeline_backlog(vault, now=now, overdue_days=7)
    assert found.runner == "synth"
    assert (_SCHEDULE_HINT in found.message) is hinted
    assert ("see the automation findings in this report" in found.message) is hinted


def test_pipeline_backlog_ignores_old_raw_when_queue_empty(tmp_path: Path) -> None:
    """Already-synthesized old raw files must not fake a synth backlog."""
    vault = _scaffold_vault(tmp_path / "vault")
    now = datetime(2026, 10, 13, tzinfo=UTC)
    sessions = vault / "raw" / "sessions"
    sessions.mkdir(parents=True, exist_ok=True)
    old = sessions / "2026-01-01-ancient.md"
    old.write_text("# ancient\n", encoding="utf-8")
    # Empty pending queue — old raw alone must not alarm.
    write_state(
        {
            "synth": {
                "files": {},
                "pending": [],
                "pending_total": 0,
                "pending_updated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
        },
        vault,
    )
    # Harvestable stubs alone used to trip this finding — ensure they do not.
    sources = vault / "wiki" / "sources"
    sources.mkdir(parents=True)
    (sources / "stub.md").write_text(
        "---\ntitle: Stub\ntype: source\n---\n\nSee [[SomeEntity]].\n",
        encoding="utf-8",
    )
    assert check_pipeline_backlog(vault, now=now, overdue_days=7) == []


def test_candidates_review_only_when_overdue(tmp_path: Path) -> None:
    vault = _scaffold_vault(tmp_path / "vault")
    cand_dir = vault / "wiki" / "candidates" / "entities"
    cand_dir.mkdir(parents=True)
    now = datetime(2026, 10, 13, tzinfo=UTC)
    fresh = (now - timedelta(days=2)).strftime("%Y-%m-%d")
    (cand_dir / "Fresh.md").write_text(
        f"---\ntitle: Fresh\ntype: entity\nlast_updated: {fresh}\n---\n\n# Fresh\n",
        encoding="utf-8",
    )
    assert check_candidates_review(vault, now=now, overdue_days=30) == []

    old = (now - timedelta(days=40)).strftime("%Y-%m-%d")
    (cand_dir / "Stale.md").write_text(
        f"---\ntitle: Stale\ntype: entity\nlast_updated: {old}\n---\n\n# Stale\n",
        encoding="utf-8",
    )
    findings = check_candidates_review(vault, now=now, overdue_days=30)
    assert any(f.id == "candidates.review_pending" for f in findings)


def test_check_includes_index_sync_when_healthy_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault = _scaffold_vault(tmp_path / "vault")
    (vault / "wiki" / "entities").mkdir()
    (vault / "wiki" / "entities" / "Foo.md").write_text(
        "---\ntitle: Foo\ntype: entity\n---\n\n# Foo\n",
        encoding="utf-8",
    )
    (vault / "wiki" / "index.md").write_text("# Wiki Index\n", encoding="utf-8")
    _patch_healthy_deps(monkeypatch)

    report = run_doctor(
        vault,
        mode=DoctorMode.CHECK,
        cfg={"synthesis": {"backend": "claude"}},
    )
    assert any(f.id == "lint.index_sync" for f in report.findings)
    assert report.exit_code == 1


def test_early_findings_still_collected_when_lint_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault = _scaffold_vault(tmp_path / "vault")
    monkeypatch.setattr("llmwiki.doctor.checks.find_spec", lambda name: object())
    monkeypatch.setattr("llmwiki.doctor.checks.discover_all", lambda: None)
    monkeypatch.setattr(
        "llmwiki.doctor.checks.get_available",
        lambda: {"claude_code": object()},
    )
    monkeypatch.setattr("llmwiki.doctor.checks.detect_env", _healthy_env)
    monkeypatch.setattr(
        "llmwiki.doctor.checks.resolve_backend",
        lambda cfg=None: (_ for _ in ()).throw(RuntimeError("x")),
    )
    early = run_checks_a_to_f(vault)
    assert should_skip_lint(early_findings=early) is True
