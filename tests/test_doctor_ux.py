"""UX: progress stages, severity sort, human lint fixes, check→heal offer.

# @spec: 327-doctor
"""

from __future__ import annotations

from io import StringIO
from pathlib import Path

from llmwiki.doctor import (
    DoctorMode,
    ask_to_apply_heals,
    print_heal_summary,
    run_doctor,
)
from llmwiki.doctor.lint_fold import RULE_HUMAN_FIX, finding_from_lint_issue
from llmwiki.doctor.models import DoctorReport, Finding, FixTier, sort_findings
from llmwiki.doctor.progress import make_progress
from llmwiki.doctor.report import render_text


def test_sort_findings_error_warning_info() -> None:
    findings = [
        Finding("i", "I", "m", "f", True, "info", FixTier.GUIDED),
        Finding("e", "I", "m", "f", True, "error", FixTier.SAFE, "reindex"),
        Finding("w", "I", "m", "f", True, "warning", FixTier.GUIDED),
    ]
    assert [f.id for f in sort_findings(findings)] == ["e", "w", "i"]


def test_lint_human_fix_not_address_rule() -> None:
    assert "link_integrity" in RULE_HUMAN_FIX
    finding = finding_from_lint_issue(
        {
            "rule": "link_integrity",
            "severity": "warning",
            "page": "concepts/X.md",
            "message": "broken wikilink [[Y]]",
        }
    )
    assert "Address lint rule" not in finding.fix
    assert "wikilink" in finding.fix.casefold() or "link" in finding.fix.casefold()


def test_progress_prints_ellipsis() -> None:
    buf = StringIO()
    make_progress(buf)("running wiki lint")
    assert buf.getvalue() == "doctor: running wiki lint...\n"


def test_render_groups_and_sorts() -> None:
    report = DoctorReport(
        findings=[
            Finding("lint:orphan", "I", "orphan", "link it", True, "info", FixTier.GUIDED),
            Finding(
                "lint.index_sync",
                "I",
                "missing from index",
                "reindex",
                True,
                "error",
                FixTier.SAFE,
                "reindex",
            ),
            Finding(
                "env.extra_add_missing",
                "E",
                "no markitdown",
                "install add",
                True,
                "warning",
                FixTier.DANGEROUS,
                "install_extra:add",
            ),
        ],
        exit_code=1,
        mode=DoctorMode.CHECK,
    )
    text = render_text(report)
    assert "sorted by severity" in text
    assert text.index("[error]") < text.index("[warning]") < text.index("[info]")
    assert "doctor can apply" in text
    assert "manual / guided" in text
    assert "how to fix:" in text
    assert "after this report" in text


def test_index_sync_message_explains_catalog_not_bad_candidate() -> None:
    finding = finding_from_lint_issue(
        {
            "rule": "index_sync",
            "severity": "error",
            "page": "index.md",
            "message": (
                "page 'candidates/concepts/Configuration managements.md' "
                "not listed in index.md"
            ),
        }
    )
    assert "Catalog drift" in finding.message
    assert "promote" in finding.fix.casefold() or "catalog" in finding.fix.casefold()
    assert "Address lint rule" not in finding.fix


def test_heal_summary_explains_two_counts_without_prompt() -> None:
    findings = [
        Finding(
            "lint.index_sync", "I", "m", "f", True, "error", FixTier.SAFE, "reindex"
        ),
        Finding("lint:orphan", "I", "m", "f", True, "info", FixTier.GUIDED),
    ]
    buf = StringIO()
    assert print_heal_summary(findings, stdout=buf) is True
    text = buf.getvalue()
    assert "1 fix(es) doctor can apply" in text
    assert "confirm each" in text
    assert "1 finding(s) stay manual" in text
    # No outer yes/no — per-item confirms live in apply_heals.
    assert "[y/N]" not in text
    assert ask_to_apply_heals(findings, stdout=StringIO()) is True


def test_check_tty_declining_heal_stays_check(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    (vault / "wiki").mkdir(parents=True)
    (vault / "raw").mkdir()
    (vault / "wiki" / "index.md").write_text("# Wiki Index\n", encoding="utf-8")
    stages: list[str] = []

    def _prog(msg: str) -> None:
        stages.append(msg)

    report = run_doctor(
        vault,
        mode=DoctorMode.CHECK,
        is_tty=True,
        confirm_fn=lambda _p: False,
        progress=_prog,
        stdout=StringIO(),
    )
    assert report.mode == DoctorMode.CHECK
    assert any("lint" in s or "environment" in s for s in stages)
