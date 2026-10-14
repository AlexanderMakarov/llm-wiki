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
