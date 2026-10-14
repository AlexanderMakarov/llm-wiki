"""Whole-feature acceptance for ``llmwiki doctor`` (#110 / 327-doctor).

Cross-cuts the heal loop against functional-spec.md. Slice-level detail lives
in ``test_doctor_{skeleton,kb_match,checks,lint_fold,runners}.py``; this module
asserts the end-to-end contracts a user/script relies on.

# @spec: 327-doctor
# @regression
"""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from llmwiki.cli import main
from llmwiki.doctor import DoctorMode, run_doctor
from llmwiki.doctor import runners as runners_mod
from llmwiki.doctor.anon import agents_md_github_url, heal_kb_github_url
from llmwiki.doctor.kb import load_heal_kb
from llmwiki.doctor.runners import CANDIDATES_ACTIONS, KNOWN_BARE_RUNNERS
from llmwiki.install_hint import PythonEnv

_AREAS = frozenset("ABCDEFGHIJKLMNO")


def _scaffold(root: Path) -> Path:
    (root / "wiki").mkdir(parents=True)
    (root / "raw").mkdir(parents=True)
    return root


def _dirty_index(root: Path) -> Path:
    vault = _scaffold(root)
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


def _available_backend() -> Any:
    backend = MagicMock()
    backend.is_available.return_value = True
    backend.is_llm = True
    type(backend).__name__ = "ClaudeCLISynthesizer"
    return backend


def _patch_healthy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("llmwiki.doctor.checks.find_spec", lambda name: object())
    monkeypatch.setattr("llmwiki.doctor.checks.discover_all", lambda: None)
    monkeypatch.setattr(
        "llmwiki.doctor.checks.get_available",
        lambda: {"claude_code": object()},
    )
    monkeypatch.setattr(
        "llmwiki.doctor.checks.resolve_backend",
        lambda cfg=None: _available_backend(),
    )
    monkeypatch.setattr("llmwiki.doctor.checks.detect_env", _healthy_env)


def test_acceptance_exit_2_when_vault_missing(tmp_path: Path) -> None:
    """R9: unusable vault → exit 2."""
    assert main(["doctor", "--vault", str(tmp_path / "nope")]) == 2


def test_acceptance_check_never_mutates_index(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R2: --check is diagnose-only."""
    _patch_healthy(monkeypatch)
    vault = _dirty_index(tmp_path / "v")
    before = (vault / "wiki" / "index.md").read_text(encoding="utf-8")
    code = main(["doctor", "--check", "--vault", str(vault)])
    assert code in (0, 1)
    assert (vault / "wiki" / "index.md").read_text(encoding="utf-8") == before


def test_acceptance_error_unknown_assist_uses_github_urls(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """R5/R6: unmatched --error → assist with public AGENTS.md + KB URLs, no runner."""
    vault = _scaffold(tmp_path / "v")
    code = main(
        [
            "doctor",
            "--vault",
            str(vault),
            "--error",
            "completely-unknown-zyx-symptom-999",
        ]
    )
    out = capsys.readouterr().out
    assert code != 0
    assert "https://" in out
    assert "AGENTS.md" in out or agents_md_github_url() in out
    assert "heal_kb.json" in out or heal_kb_github_url() in out
    assert "/home/" not in out


def test_acceptance_error_match_known_extra(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """R6: known paste matches catalog (no invented fix beyond KB)."""
    vault = _scaffold(tmp_path / "v")
    code = main(
        [
            "doctor",
            "--vault",
            str(vault),
            "--error",
            "No module named 'markitdown'",
        ]
    )
    out = capsys.readouterr().out.lower()
    assert code != 0
    assert "markitdown" in out or "add" in out or "extra" in out


def test_acceptance_yes_heals_index_sync_not_synth(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R3/R4: --yes applies safe reindex; never auto-starts synth."""
    _patch_healthy(monkeypatch)
    vault = _dirty_index(tmp_path / "v")
    calls: list[str] = []
    real = runners_mod.dispatch_runner

    def _wrap(runner: str, vault_path: Path, **kwargs: Any) -> Any:
        calls.append(runner)
        return real(runner, vault_path, **kwargs)

    monkeypatch.setattr(runners_mod, "dispatch_runner", _wrap)
    monkeypatch.setattr("llmwiki.doctor.dispatch_runner", _wrap)

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
    assert not any(f.id == "lint.index_sync" for f in report.findings)
    assert not any(c.startswith("synth") for c in calls)


def test_acceptance_non_tty_without_yes_plan_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R3: non-TTY without --yes does not mutate."""
    _patch_healthy(monkeypatch)
    vault = _dirty_index(tmp_path / "v")
    before = (vault / "wiki" / "index.md").read_text(encoding="utf-8")
    run_doctor(
        vault,
        mode=DoctorMode.HEAL,
        yes=False,
        is_tty=False,
        cfg={"synthesis": {"backend": "claude"}},
        stdout=StringIO(),
    )
    assert (vault / "wiki" / "index.md").read_text(encoding="utf-8") == before


def test_acceptance_catalog_current_package_invariants() -> None:
    """R10 / CONTRIBUTING: A–O coverage; no retired museum; public URL shape."""
    kb = load_heal_kb()
    assert set(kb.areas) == _AREAS
    for letter in sorted(_AREAS):
        assert kb.entries_for_area(letter), f"area {letter} empty"
        for entry in kb.entries_for_area(letter):
            for bad in ("retired", "deprecated", "superseded_by"):
                assert bad not in entry
    assert heal_kb_github_url().startswith("https://github.com/")
    assert agents_md_github_url().endswith("AGENTS.md")


def test_acceptance_check_error_never_mutates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """B2: --check --error is diagnose-only even for a matched safe fix."""
    _patch_healthy(monkeypatch)
    vault = _dirty_index(tmp_path / "v")
    before = (vault / "wiki" / "index.md").read_text(encoding="utf-8")
    code = main(
        [
            "doctor",
            "--check",
            "--error",
            "rule=index_sync",
            "--vault",
            str(vault),
        ]
    )
    assert code in (0, 1)
    assert (vault / "wiki" / "index.md").read_text(encoding="utf-8") == before


def test_acceptance_yes_error_reindexes_index_sync(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """B2: --yes --error matching lint.index_sync applies reindex."""
    _patch_healthy(monkeypatch)
    vault = _dirty_index(tmp_path / "v")
    code = main(
        [
            "doctor",
            "--yes",
            "--error",
            "rule=index_sync",
            "--vault",
            str(vault),
        ]
    )
    assert code in (0, 1)
    text = (vault / "wiki" / "index.md").read_text(encoding="utf-8")
    assert "Foo" in text or "entities/Foo.md" in text


def test_acceptance_catalog_runners_are_dispatchable() -> None:
    """B1: every non-null catalog runner is a known bare id or valid prefix."""
    kb = load_heal_kb()
    for entry in kb.entries:
        runner = entry.get("runner")
        if runner is None:
            assert entry.get("tier") == "guided"
            continue
        assert entry.get("tier") in {"safe", "dangerous"}
        if runner in KNOWN_BARE_RUNNERS:
            continue
        if runner.startswith("migrate:"):
            assert runner.split(":", 1)[1].strip()
            continue
        if runner.startswith("install_extra:"):
            assert runner.split(":", 1)[1].strip()
            continue
        if runner.startswith("candidates:"):
            action = runner.split(":", 1)[1].strip()
            assert action in CANDIDATES_ACTIONS, runner
            continue
        raise AssertionError(f"unknown catalog runner {runner!r} on {entry['id']}")
