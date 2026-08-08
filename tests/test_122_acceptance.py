"""Acceptance tests for #122: Trace wiki pages back to raw transcripts.

# @layer: integration
# @spec: 007-trace-provenance
# @regression

Covers the end-to-end gaps across FR1–FR5 that the individual slice tests
(test_trace.py, test_cli_trace.py, test_provenance_sources_links.py,
test_lint_rules.py) address at unit level:

- FR4: every page *kind* that carries provenance (project, synthesis, multiple
  source slugs) resolves correctly — not just entity/concept.
- FR5 via run_all: lint plumbing (selected=, severity, doctor reference) when
  called through the shared ``run_all`` / ``load_pages`` runner, not just the
  rule class directly.
- Cross-FR: no body excerpt in CLI output; missing hop keeps rest of chain AND
  triggers lint; exit codes are consistent with the spec.
"""

from __future__ import annotations

from pathlib import Path

from llmwiki.cli import build_parser, cmd_trace
from llmwiki.lint import load_pages, run_all
from llmwiki.trace import trace_page

# ─── vault helpers ────────────────────────────────────────────────────────────


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "wiki").mkdir(parents=True)
    (vault / "raw" / "sessions").mkdir(parents=True)
    return vault


def _full_chain_vault(tmp_path: Path) -> tuple[Path, str]:
    """Vault with entity → source → raw chain; returns (vault, raw_name)."""
    vault = _vault(tmp_path)
    raw_name = "2026-06-01T09-00-proj-sess.md"
    _write(
        vault / "raw" / "sessions" / raw_name,
        '---\ntitle: "Session transcript"\ntype: source\n---\n\nSECRET BODY\n',
    )
    _write(
        vault / "wiki" / "sources" / "proj-sess.md",
        (
            '---\ntitle: "Project session"\ntype: source\n'
            f"source_file: raw/sessions/{raw_name}\n"
            "---\n\n## Summary\n\nThis summarises.\n"
        ),
    )
    return vault, raw_name


# ─── FR4: page-kind variety ───────────────────────────────────────────────────


def test_fr4_project_page_traces_sources(tmp_path: Path) -> None:
    """FR4: a *project* page (type: project) with sources: is fully traced."""
    vault, _raw = _full_chain_vault(tmp_path)
    _write(
        vault / "wiki" / "projects" / "my-project.md",
        (
            '---\ntitle: "My Project"\ntype: project\n'
            "sources: [proj-sess]\n---\n\n# My Project\n"
        ),
    )
    result = trace_page(vault, "my-project")
    roles = [(h.role, h.status) for h in result.hops]
    assert roles == [("page", "ok"), ("source", "ok"), ("raw", "ok")]
    assert result.hops[0].title == "My Project"
    assert result.hops[1].title == "Project session"


def test_fr4_synthesis_page_traces_sources(tmp_path: Path) -> None:
    """FR4: a synthesis page (type: synthesis, sources:) is fully traced."""
    vault, _raw = _full_chain_vault(tmp_path)
    _write(
        vault / "wiki" / "syntheses" / "my-synthesis.md",
        (
            '---\ntitle: "My Synthesis"\ntype: synthesis\n'
            "sources: [proj-sess]\n---\n\n## Answer\n\ntext\n"
        ),
    )
    result = trace_page(vault, "my-synthesis")
    roles = [(h.role, h.status) for h in result.hops]
    assert roles == [("page", "ok"), ("source", "ok"), ("raw", "ok")]


def test_fr4_multiple_sources_all_appear_in_chain(tmp_path: Path) -> None:
    """FR4: a page listing two sources emits both source hops (and their raws)."""
    vault = _vault(tmp_path)
    for slug in ("alpha", "beta"):
        _write(
            vault / "raw" / "sessions" / f"{slug}.md",
            f'---\ntitle: "{slug.title()} raw"\n---\n\nx\n',
        )
        _write(
            vault / "wiki" / "sources" / f"{slug}.md",
            (
                f'---\ntitle: "{slug.title()} src"\ntype: source\n'
                f"source_file: raw/sessions/{slug}.md\n---\n\n## Summary\n\nok\n"
            ),
        )
    _write(
        vault / "wiki" / "concepts" / "MultiSource.md",
        (
            '---\ntitle: "MultiSource"\ntype: concept\n'
            "sources: [alpha, beta]\n---\n\n# MultiSource\n"
        ),
    )
    result = trace_page(vault, "MultiSource")
    roles = [(h.role, h.status) for h in result.hops]
    assert roles == [
        ("page", "ok"),
        ("source", "ok"),
        ("raw", "ok"),
        ("source", "ok"),
        ("raw", "ok"),
    ]


def test_fr4_page_with_no_provenance_does_not_crash(tmp_path: Path) -> None:
    """FR4: tracing a page that has no provenance metadata must not raise."""
    vault = _vault(tmp_path)
    _write(
        vault / "wiki" / "projects" / "empty-proj.md",
        '---\ntitle: "Empty"\ntype: project\n---\n\n# Empty\n',
    )
    result = trace_page(vault, "empty-proj")
    assert len(result.hops) == 1
    assert result.hops[0].status == "ok"
    assert result.hops[0].role == "page"


def test_fr4_source_summary_page_emits_raw_hop(tmp_path: Path) -> None:
    """FR4: tracing a wiki/sources/ page directly finds the raw transcript."""
    vault, raw_name = _full_chain_vault(tmp_path)
    result = trace_page(vault, "wiki/sources/proj-sess.md")
    roles = [(h.role, h.status) for h in result.hops]
    assert roles == [("page", "ok"), ("raw", "ok")]
    assert result.hops[1].location == f"raw/sessions/{raw_name}"


# ─── FR1: no body excerpts in CLI output ──────────────────────────────────────


def test_fr1_cli_output_excludes_body_text(tmp_path: Path, capsys) -> None:
    """FR1: stdout from trace must never include transcript body text."""
    vault, _raw = _full_chain_vault(tmp_path)
    _write(
        vault / "wiki" / "entities" / "E.md",
        '---\ntitle: "E"\ntype: entity\nsources: [proj-sess]\n---\n\n# E\n',
    )
    args = build_parser().parse_args(
        ["trace", "wiki/entities/E.md", "--vault", str(vault)],
    )
    rc = cmd_trace(args)
    out = capsys.readouterr().out
    assert rc == 0
    assert "SECRET BODY" not in out
    assert "This summarises" not in out  # source summary body also excluded


def test_fr1_cli_titles_and_locations_present(tmp_path: Path, capsys) -> None:
    """FR1: stdout must include titles and locations for each hop."""
    vault, raw_name = _full_chain_vault(tmp_path)
    _write(
        vault / "wiki" / "entities" / "E.md",
        '---\ntitle: "E"\ntype: entity\nsources: [proj-sess]\n---\n\n# E\n',
    )
    args = build_parser().parse_args(
        ["trace", "E", "--vault", str(vault)],
    )
    cmd_trace(args)
    out = capsys.readouterr().out
    assert "E" in out
    assert "Project session" in out
    assert f"raw/sessions/{raw_name}" in out


# ─── FR3: missing hop keeps chain intact ─────────────────────────────────────


def test_fr3_missing_source_keeps_valid_raw_hop(tmp_path: Path) -> None:
    """FR3: chain with one missing slug still includes the valid source+raw."""
    vault, _raw = _full_chain_vault(tmp_path)
    _write(
        vault / "wiki" / "entities" / "Mixed.md",
        (
            '---\ntitle: "Mixed"\ntype: entity\n'
            "sources: [gone-slug, proj-sess]\n---\n\n# Mixed\n"
        ),
    )
    result = trace_page(vault, "Mixed")
    roles = [(h.role, h.status) for h in result.hops]
    assert ("source", "missing") in roles
    assert ("source", "ok") in roles
    assert ("raw", "ok") in roles


def test_fr3_cli_exit_0_on_missing_hop(tmp_path: Path, capsys) -> None:
    """FR3: CLI exits 0 even when a hop is missing; missing marker appears."""
    vault = _vault(tmp_path)
    _write(
        vault / "wiki" / "entities" / "Partial.md",
        (
            '---\ntitle: "Partial"\ntype: entity\n'
            "sources: [totally-gone]\n---\n\n# Partial\n"
        ),
    )
    args = build_parser().parse_args(
        ["trace", "Partial", "--vault", str(vault)],
    )
    rc = cmd_trace(args)
    out = capsys.readouterr().out
    assert rc == 0
    assert "(missing)" in out
    assert "totally-gone" in out


def test_fr3_cli_exit_1_only_when_start_page_absent(tmp_path: Path, capsys) -> None:
    """FR3 / FR1: exit non-zero only when the starting page cannot resolve."""
    vault = _vault(tmp_path)
    args = build_parser().parse_args(
        ["trace", "AbsolutelyNonExistent", "--vault", str(vault)],
    )
    rc = cmd_trace(args)
    assert rc == 1


# ─── FR5: lint via run_all plumbing ───────────────────────────────────────────


def test_fr5_lint_run_all_reports_missing_source_as_error(tmp_path: Path) -> None:
    """FR5: run_all(selected=['provenance_integrity']) emits severity=error."""
    vault = _vault(tmp_path)
    ent = vault / "wiki" / "entities" / "Orphan.md"
    ent.parent.mkdir(parents=True, exist_ok=True)
    ent.write_text(
        '---\ntitle: "Orphan"\ntype: entity\nsources: [gone]\n---\n\n# Orphan\n',
        encoding="utf-8",
    )
    pages = load_pages(vault / "wiki")
    issues = run_all(pages, selected=["provenance_integrity"])
    assert len(issues) == 1
    issue = issues[0]
    assert issue["rule"] == "provenance_integrity"
    assert issue["severity"] == "error"
    assert "gone" in issue["message"]


def test_fr5_lint_run_all_mentions_doctor_110(tmp_path: Path) -> None:
    """FR5: lint message references doctor (#110) for guided repair."""
    vault = _vault(tmp_path)
    (vault / "wiki" / "entities").mkdir(parents=True, exist_ok=True)
    (vault / "wiki" / "entities" / "Bad.md").write_text(
        '---\ntitle: "Bad"\ntype: entity\nsources: [no-such-src]\n---\n\n# Bad\n',
        encoding="utf-8",
    )
    pages = load_pages(vault / "wiki")
    issues = run_all(pages, selected=["provenance_integrity"])
    assert issues
    msg = issues[0]["message"]
    assert "doctor" in msg.lower() or "#110" in msg


def test_fr5_lint_run_all_silent_on_valid_chain(tmp_path: Path) -> None:
    """FR5: no errors when every provenance hop resolves."""
    vault, _raw = _full_chain_vault(tmp_path)
    (vault / "wiki" / "entities").mkdir(parents=True, exist_ok=True)
    (vault / "wiki" / "entities" / "Good.md").write_text(
        '---\ntitle: "Good"\ntype: entity\nsources: [proj-sess]\n---\n\n# Good\n',
        encoding="utf-8",
    )
    pages = load_pages(vault / "wiki")
    issues = run_all(pages, selected=["provenance_integrity"])
    assert issues == []


def test_fr5_lint_run_all_skips_page_without_provenance(tmp_path: Path) -> None:
    """FR5: pages without sources:/source_file: produce no lint errors."""
    vault = _vault(tmp_path)
    (vault / "wiki" / "entities").mkdir(parents=True, exist_ok=True)
    (vault / "wiki" / "entities" / "Clean.md").write_text(
        '---\ntitle: "Clean"\ntype: entity\n---\n\n# Clean\n',
        encoding="utf-8",
    )
    pages = load_pages(vault / "wiki")
    issues = run_all(pages, selected=["provenance_integrity"])
    assert issues == []


def test_fr5_lint_missing_raw_flagged_as_error(tmp_path: Path) -> None:
    """FR5: a source summary whose source_file: doesn't exist is an error."""
    vault = _vault(tmp_path)
    (vault / "wiki" / "sources").mkdir(parents=True, exist_ok=True)
    (vault / "wiki" / "sources" / "dangling.md").write_text(
        '---\ntitle: "Dangling"\ntype: source\n'
        "source_file: raw/sessions/no-such-file.md\n---\n\n## Summary\nx\n",
        encoding="utf-8",
    )
    pages = load_pages(vault / "wiki")
    issues = run_all(pages, selected=["provenance_integrity"])
    assert len(issues) == 1
    assert issues[0]["severity"] == "error"
    assert "no-such-file.md" in issues[0]["message"]


# ─── Cross-FR: lint + CLI agree on same vault ─────────────────────────────────


def test_cross_fr_lint_and_cli_consistent_on_broken_vault(tmp_path: Path, capsys) -> None:
    """Cross-FR1+FR5: vault with missing hop → CLI exits 0, lint fires error."""
    vault = _vault(tmp_path)
    (vault / "wiki" / "entities").mkdir(parents=True, exist_ok=True)
    (vault / "wiki" / "entities" / "Broken.md").write_text(
        '---\ntitle: "Broken"\ntype: entity\nsources: [ghost]\n---\n\n# Broken\n',
        encoding="utf-8",
    )
    # CLI: exits 0 (missing hop is not a fatal error)
    args = build_parser().parse_args(
        ["trace", "Broken", "--vault", str(vault)],
    )
    rc = cmd_trace(args)
    out = capsys.readouterr().out
    assert rc == 0
    assert "(missing)" in out

    # Lint: the same vault surfaces an error
    pages = load_pages(vault / "wiki")
    issues = run_all(pages, selected=["provenance_integrity"])
    assert any(i["severity"] == "error" for i in issues)
    assert any("ghost" in i["message"] for i in issues)


def test_cross_fr_cli_and_trace_agree_on_full_chain(tmp_path: Path, capsys) -> None:
    """Cross-FR1+FR4: CLI output matches trace_page hops for a project page."""
    vault, raw_name = _full_chain_vault(tmp_path)
    _write(
        vault / "wiki" / "projects" / "my-proj.md",
        '---\ntitle: "My Proj"\ntype: project\nsources: [proj-sess]\n---\n\n# My Proj\n',
    )
    args = build_parser().parse_args(
        ["trace", "my-proj", "--vault", str(vault)],
    )
    rc = cmd_trace(args)
    out = capsys.readouterr().out
    assert rc == 0

    result = trace_page(vault, "my-proj")
    for hop in result.hops:
        assert hop.title in out
        assert hop.location in out
