"""Slice 1: doctor CLI skeleton + heal catalog load.

# @spec: 327-doctor
"""

from __future__ import annotations

import json
import re
from importlib import resources
from pathlib import Path

import pytest

from llmwiki.cli import build_parser, main
from llmwiki.doctor import DoctorMode, run_doctor
from llmwiki.doctor.kb import (
    HealKBError,
    list_areas,
    load_heal_kb,
    validate_catalog,
)

_FORBIDDEN = frozenset({"retired", "deprecated", "superseded_by"})
_AREAS = frozenset("ABCDEFGHIJKLMNO")


def _scaffold_vault(root: Path) -> Path:
    """Minimal usable vault: ``wiki/`` present (no personal paths)."""
    (root / "wiki").mkdir(parents=True)
    (root / "raw").mkdir(parents=True)
    return root


def test_heal_kb_loads_via_package_resources() -> None:
    kb = load_heal_kb()
    assert kb.version >= 1
    assert set(kb.areas) == _AREAS
    assert kb.get("vault.missing_or_unusable") is not None
    assert "issue_body" in kb.unknown_templates
    assert "ai_prompt" in kb.unknown_templates


def test_every_area_a_to_o_has_at_least_one_entry() -> None:
    kb = load_heal_kb()
    covered = {e["area"] for e in kb.entries}
    assert covered == _AREAS
    for letter in sorted(_AREAS):
        assert kb.entries_for_area(letter), f"area {letter} has no entries"


def test_catalog_has_no_retired_style_keys() -> None:
    kb = load_heal_kb()
    blob = json.dumps(
        {
            "version": kb.version,
            "areas": kb.areas,
            "entries": kb.entries,
            "unknown_templates": kb.unknown_templates,
            "matcher": kb.matcher,
        }
    )
    for key in _FORBIDDEN:
        assert f'"{key}"' not in blob


def test_validate_catalog_rejects_retired_keys() -> None:
    raw = {
        "version": 1,
        "areas": {
            letter: {"title": letter, "summary": letter} for letter in sorted(_AREAS)
        },
        "entries": [
            {
                "id": f"stub.{letter}",
                "area": letter,
                "patterns": ["x"],
                "message": "m",
                "fix": "f",
                "actionable": False,
                "severity": "info",
                "tier": "guided",
                "runner": None,
                "retired": True,
            }
            for letter in sorted(_AREAS)
        ],
        "unknown_templates": {"issue_body": "i", "ai_prompt": "a"},
    }
    with pytest.raises(HealKBError, match="forbidden"):
        validate_catalog(raw)


def test_list_areas_matches_catalog() -> None:
    areas = list_areas()
    assert set(areas) == _AREAS
    assert areas["C"]["title"]


def test_missing_vault_exit_code_2(tmp_path: Path) -> None:
    missing = tmp_path / "no-such-vault"
    report = run_doctor(missing, mode=DoctorMode.CHECK)
    assert report.exit_code == 2
    assert report.vault_error
    assert report.findings
    assert report.findings[0].id == "vault.missing_or_unusable"


def test_missing_wiki_exit_code_2(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    report = run_doctor(vault, mode=DoctorMode.HEAL)
    assert report.exit_code == 2
    assert "wiki" in (report.vault_error or "").lower()


def test_none_vault_exit_code_2() -> None:
    report = run_doctor(None, mode=DoctorMode.CHECK)
    assert report.exit_code == 2


def test_usable_vault_check_runs_without_crash(tmp_path: Path) -> None:
    """Usable vault: detectors may find issues (exit 0 or 1) but must not crash."""
    vault = _scaffold_vault(tmp_path / "vault")
    report = run_doctor(vault, mode=DoctorMode.CHECK)
    assert report.exit_code in (0, 1)
    assert report.vault_error is None
    assert "catalog_version" in report.env_summary or "python" in report.env_summary


def test_check_does_not_write(tmp_path: Path) -> None:
    vault = _scaffold_vault(tmp_path / "vault")
    marker = vault / "wiki" / "sentinel.md"
    marker.write_text("# sentinel\n", encoding="utf-8")
    before = {
        p.relative_to(vault).as_posix(): (p.stat().st_mtime_ns, p.read_bytes())
        for p in vault.rglob("*")
        if p.is_file()
    }
    code = main(["doctor", "--check", "--vault", str(vault)])
    # Findings may yield exit 1; --check must still never mutate the vault.
    assert code in (0, 1)
    after_paths = {p.relative_to(vault).as_posix() for p in vault.rglob("*") if p.is_file()}
    assert after_paths == set(before)
    for rel, (mtime_ns, payload) in before.items():
        path = vault / rel
        assert path.read_bytes() == payload
        assert path.stat().st_mtime_ns == mtime_ns


def test_cli_doctor_help_registered() -> None:
    parser = build_parser()
    help_text = parser.format_help()
    assert "doctor" in help_text
    sub = None
    for action in parser._actions:
        if hasattr(action, "choices") and isinstance(action.choices, dict):
            sub = action.choices
            break
    assert sub is not None and "doctor" in sub
    doctor_help = sub["doctor"].format_help()
    assert "--check" in doctor_help
    assert "--dry-run" in doctor_help
    assert "--error" in doctor_help
    assert "--yes" in doctor_help
    assert "--kit-dest" in doctor_help
    assert not re.findall(r"#\d+", doctor_help)


def test_cli_missing_vault_exit_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    missing = tmp_path / "absent-vault"
    code = main(["doctor", "--check", "--vault", str(missing)])
    assert code == 2
    out = capsys.readouterr().out
    assert "exit: 2" in out or "error:" in out


def test_package_resource_heal_kb_json_readable() -> None:
    text = resources.files("llmwiki.doctor").joinpath("heal_kb.json").read_text(encoding="utf-8")
    data = json.loads(text)
    assert data["version"] >= 1
    assert set(data["areas"]) == _AREAS
