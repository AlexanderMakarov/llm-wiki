"""Slice 2: heal KB fingerprint / pattern / lexical match + unknown assist.

# @spec: 327-doctor
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from llmwiki.cli import main
from llmwiki.doctor import DoctorMode, run_doctor
from llmwiki.doctor.anon import (
    agents_md_github_url,
    build_unknown_assist,
    heal_kb_github_url,
    redact_symptom,
)
from llmwiki.doctor.kb import (
    HealKBError,
    fingerprint,
    load_heal_kb,
    match_symptom,
    validate_catalog,
)

_FORBIDDEN = frozenset({"retired", "deprecated", "superseded_by"})
_AREAS = frozenset("ABCDEFGHIJKLMNO")


def _scaffold_vault(root: Path) -> Path:
    (root / "wiki").mkdir(parents=True)
    (root / "raw").mkdir(parents=True)
    return root


def test_fingerprint_redacts_paths_and_casefolds() -> None:
    raw = "Error in /home/USER/vault/wiki/index.md: INDEX_SYNC failed"
    fp = fingerprint(raw)
    assert "/home/" not in fp
    assert "<path>" in fp
    assert "index_sync" in fp or "index_sync" in fp.casefold()
    assert fp == fp.casefold()


def test_match_by_catalog_id_token() -> None:
    result = match_symptom("see env.extra_add_missing in log")
    assert result.method == "id"
    assert result.entry is not None
    assert result.entry["id"] == "env.extra_add_missing"


def test_match_current_pattern_markitdown() -> None:
    result = match_symptom(
        "converting .pdf needs markitdown — install the optional extra"
    )
    assert result.entry is not None
    assert result.entry["id"] == "env.extra_add_missing"
    assert result.method == "pattern"


def test_match_wrong_pypi_name_not_plus() -> None:
    hit = match_symptom("pip install llm-wiki")
    assert hit.entry is not None
    assert hit.entry["id"] == "env.wrong_pypi_name"
    miss = match_symptom("pip install llm-wiki-plus")
    assert miss.entry is None or miss.entry["id"] != "env.wrong_pypi_name"


def test_match_rule_index_sync_hook() -> None:
    result = match_symptom("lint failed rule=index_sync on wiki/index.md")
    assert result.entry is not None
    assert result.entry["id"] == "lint.index_sync"


def test_lexical_fallback_high_threshold() -> None:
    # Strong overlap with dummy-backend messaging → accept.
    strong = match_symptom(
        "synthesis.backend is still the dummy backend DummySynthesizer"
    )
    assert strong.entry is not None
    assert strong.entry["id"] == "synth.backend_dummy"
    assert strong.method in {"pattern", "lexical"}

    # Weak / unrelated paste → unknown.
    weak = match_symptom("completely unrelated printer toner empty zebra")
    assert weak.entry is None
    assert weak.method == "none"


def test_unknown_assist_runner_null_and_github_urls(tmp_path: Path) -> None:
    vault = _scaffold_vault(tmp_path / "vault")
    report = run_doctor(
        vault,
        mode=DoctorMode.ERROR,
        error_text="totally novel failure mode xyzzy-12345",
    )
    assert report.exit_code == 1
    assert report.findings
    assert report.findings[0].runner is None
    assert report.unknown_assist is not None
    assist = report.unknown_assist
    assert "github.com" in assist["kb_url"]
    assert assist["kb_url"].endswith("llmwiki/doctor/heal_kb.json")
    assert assist["agents_url"].endswith("AGENTS.md")
    assert heal_kb_github_url() == assist["kb_url"]
    assert agents_md_github_url() == assist["agents_url"]
    assert "/home/" not in assist["issue_body"]
    assert "<path>" in redact_symptom("fail at /home/USER/secret/vault") or "path" in assist[
        "symptom_redacted"
    ]


def test_build_unknown_assist_privacy_placeholders_only() -> None:
    assist = build_unknown_assist(
        "boom at /home/USER/projects/my-vault/wiki/Page.md on host.example.com",
        env_summary={"llmwiki_version": "0.0.0", "os": "Linux", "python": "3.12"},
        counts={"findings": 1, "vault": "/home/USER/bad"},  # pathy count dropped
    )
    blob = assist["issue_body"] + assist["ai_prompt"]
    assert "/home/USER" not in blob
    assert "my-vault" not in blob
    assert "host.example.com" not in blob
    assert "findings=1" in assist["issue_body"] or "findings=1" in blob


def test_schema_forbids_retired_deprecated_superseded() -> None:
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
            }
            for letter in sorted(_AREAS)
        ],
        "unknown_templates": {"issue_body": "i", "ai_prompt": "a"},
    }
    for key in _FORBIDDEN:
        bad = json.loads(json.dumps(raw))
        bad["entries"][0][key] = True
        with pytest.raises(HealKBError, match="forbidden"):
            validate_catalog(bad)


def test_bundled_catalog_has_no_retired_keys() -> None:
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


def test_cli_error_match_and_unknown(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    vault = _scaffold_vault(tmp_path / "vault")
    code = main(
        [
            "doctor",
            "--vault",
            str(vault),
            "--error",
            "converting .pdf needs markitdown",
        ]
    )
    assert code == 1
    out = capsys.readouterr().out
    assert "env.extra_add_missing" in out

    code2 = main(
        [
            "doctor",
            "--vault",
            str(vault),
            "--error",
            "never-before-seen-error-token-qqq",
        ]
    )
    assert code2 == 1
    out2 = capsys.readouterr().out
    assert "unknown assist" in out2.lower() or "AI investigation" in out2
    assert re.search(r"github\.com/.+/AGENTS\.md", out2)
    assert "heal_kb.json" in out2


# Area L stems copied from the literal parts of the messages in doctor/checks.py,
# the install-automation guard in cli.py and DEV_CHECKOUT_WARNINGS, with placeholder names.
_AREA_L_CASES = [
    pytest.param(
        "Automation job 'llmwiki-sync' is recorded for this vault 'my-vault' "
        "but no schedule for it is installed.",
        "automation.unit_missing",
        id="unit_missing-message",
    ),
    pytest.param(
        "schedule llmwiki-sync-1a2b serves vault 'other-vault', not this vault 'my-vault'",
        "automation.points_elsewhere",
        id="points_elsewhere-message",
    ),
    pytest.param(
        "Schedule llmwiki-sync-1a2b serves this vault but runs from a checkout "
        "that no longer exists ('old-checkout').",
        "automation.checkout_missing",
        id="checkout_missing-dir",
    ),
    pytest.param(
        "Schedule llmwiki-sync-1a2b serves this vault but its wrapper script is gone "
        "('llmwiki-sync.sh').",
        "automation.checkout_missing",
        id="checkout_missing-wrapper",
    ),
    pytest.param(
        "Could not check the installed schedule for this vault: systemctl --user is unavailable.",
        "automation.check_unavailable",
        id="check_unavailable-message",
    ),
    pytest.param(
        "Automation job 'llmwiki-sync' is declared but not active: timer is disabled.",
        "automation.not_active",
        id="not_active-live",
    ),
    pytest.param(
        "Automation job 'llmwiki-sync' is declared but not active.",
        "automation.not_active",
        id="not_active-recorded",
    ),
    pytest.param(
        "Automation job 'llmwiki-sync' has not run since it was set up 3 days ago.",
        "automation.stale_run",
        id="stale_run-never",
    ),
    pytest.param(
        "Automation job 'llmwiki-sync': last run failed (exit 1); "
        "see /home/USER/vault/.llmwiki/automation.log.",
        "automation.last_run_failed",
        id="last_run_failed",
    ),
    pytest.param(
        "This vault is also scheduled by the earlier single llmwiki-maintain schedule "
        "(llmwiki-maintain), so two jobs run against it. Remove the old one with:",
        "automation.duplicate_legacy",
        id="duplicate_legacy",
    ),
    pytest.param(
        "Could not switch off the earlier single llmwiki-maintain schedule: "
        "systemctl --user disable --now llmwiki-maintain.timer failed",
        "automation.duplicate_legacy",
        id="legacy_adopt_failed",
    ),
    pytest.param(
        "Kept the existing schedule — no scheduler files or automation status written.",
        "automation.setup_other_checkout",
        id="setup_other_checkout-kept",
    ),
    pytest.param(
        "Automation job 'llmwiki-sync': last run was 5 days ago.",
        "automation.stale_run",
        id="stale_run-old",
    ),
    pytest.param(
        "Leftover schedules for vaults that no longer exist (doctor does not remove them):\n"
        "  llmwiki-sync-1a2b (vault 'gone-vault') — remove it with:\n"
        "    systemctl --user disable --now llmwiki-sync-1a2b.timer",
        "automation.orphan_unit",
        id="orphan_unit-message",
    ),
    pytest.param(
        "install-automation: existing schedule runs from a different checkout; "
        "pass --force to replace it",
        "automation.setup_other_checkout",
        id="setup_other_checkout-message",
    ),
    pytest.param(
        "warning: installing from a git worktree — the scheduled job will keep using this "
        "copy at /home/USER/repo/wt and stops working when the worktree is removed.",
        "automation.setup_dev_checkout",
        id="setup_dev_checkout-worktree",
    ),
    pytest.param(
        "warning: installing from a development checkout — the scheduled job will keep "
        "using this copy at /home/USER/repo; deleting or switching it breaks the schedule.",
        "automation.setup_dev_checkout",
        id="setup_dev_checkout-checkout",
    ),
    pytest.param("schedule points at another vault", "automation.points_elsewhere", id="sym-elsewhere"),
    pytest.param("automation not running", "automation.stale_run", id="sym-not-running"),
    pytest.param("scheduled maintenance missing", "automation.unit_missing", id="sym-missing"),
    pytest.param("last run failed", "automation.last_run_failed", id="sym-run-failed"),
    pytest.param("leftover schedule", "automation.orphan_unit", id="sym-leftover"),
    pytest.param(
        "existing schedule runs from a different checkout; pass --force to replace it",
        "automation.setup_other_checkout",
        id="sym-other-checkout",
    ),
    pytest.param(
        "installing from a git worktree", "automation.setup_dev_checkout", id="sym-worktree"
    ),
]


@pytest.mark.parametrize(("text", "expected_id"), _AREA_L_CASES)
def test_area_l_messages_and_symptoms_match_their_entry(text: str, expected_id: str) -> None:
    result = match_symptom(text)
    assert result.entry is not None
    assert result.entry["id"] == expected_id
    assert result.method == "pattern"


def test_generic_schedule_phrases_do_not_match_area_l() -> None:
    elsewhere = match_symptom("the lint said not this vault")
    assert elsewhere.entry is None or elsewhere.entry["id"] != "automation.points_elsewhere"
    stale = match_symptom("the deploy log says last run was 2 hours ago")
    assert stale.entry is None or stale.entry["id"] != "automation.stale_run"


def test_install_automation_setup_text_does_not_match_not_active() -> None:
    result = match_symptom(
        "Skipped install-automation — no scheduler files or automation status written."
    )
    assert result.entry is None or result.entry["id"] != "automation.not_active"


def test_raw_overwrite_force_refusal_does_not_match_setup_other_checkout() -> None:
    result = match_symptom(
        "refusing to overwrite existing raw file /home/USER/vault/raw/x.md "
        "(source: a.jsonl, adapter: claude_code); pass --force to bypass or delete the file first"
    )
    assert result.entry is None or result.entry["id"] != "automation.setup_other_checkout"


def test_cli_error_matches_points_elsewhere(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    vault = _scaffold_vault(tmp_path / "vault")
    code = main(["doctor", "--vault", str(vault), "--error", "schedule points at another vault"])
    assert code == 1
    assert "automation.points_elsewhere" in capsys.readouterr().out
