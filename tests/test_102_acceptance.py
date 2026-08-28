"""Whole-feature acceptance tests for #102: drop the entity-type taxonomy,
make Project a page kind, unify wiki search.

# @layer: integration
# @spec: 003-drop-entity-type-taxonomy
# @regression

Slices 1-5 each carry unit coverage for their own change; this file verifies
the feature as a whole against functional-spec.md, with the headline claim
(a fully-reviewed vault lints clean) driven end-to-end through the real
library entry points rather than through any single slice's fixtures.

AC coverage matrix (R<requirement>-AC<n>, in functional-spec.md bullet order):

    R1-AC1  → test_headline_red_old_stamped_entity_type_would_have_failed_pre_fix
    R1-AC2  → covered by tests/test_lint_rules.py::test_validity_entity_page_without_entity_type_is_clean
    R1-AC3  → test_headline_full_review_cycle_promotes_and_lints_clean   [headline]
    R1-AC4  → test_r1_ac4_cli_lint_unknown_rule_name_errors_end_to_end
    R2-AC1  → covered by tests/test_candidates_harvest.py::test_stub_carries_no_entity_type
    R2-AC2  → covered by tests/test_project_stubs.py::test_ensure_project_stubs_creates_missing
    R2-AC3  → test_r2_no_writer_stamps_entity_type_across_full_pipeline
    R3-AC1  → test_r3_project_page_is_lint_clean_claim_checked_ranked_and_cataloged
    R3-AC2  → covered by tests/test_project_stubs.py (stub emits type: project)
    R3-AC3  → covered by the wiki/projects/*.md migration + tests/test_reindex.py
    R3-AC4  → test_r3_project_page_is_lint_clean_claim_checked_ranked_and_cataloged
    R3-AC5  → test_r3_project_page_is_lint_clean_claim_checked_ranked_and_cataloged
    R3-AC6  → test_r3_project_page_is_lint_clean_claim_checked_ranked_and_cataloged
    R4-AC1  → covered by tests/test_mcp_enhanced.py::test_search_is_the_only_search_tool
    R4-AC2..AC6 → covered by tests/test_mcp_enhanced.py (kind filter / ranking /
                  kind+include_raw composition)
    R4-AC7  → test_r4_old_entity_search_tool_name_is_now_unknown
    R5-AC1..AC5 → covered by tests/test_cli_candidates_only.py + tests/test_synth_pipeline.py
    R6-AC1  → covered by tests/test_search_facets.py + tests/test_dashboard.py
    R6-AC2  → covered by tests/test_search_facets.py (aggregate_facets has no key)
    R7-AC1  → test_r7_docs_sweep_teaches_neither_the_field_nor_a_filter_on_it
    R7-AC2  → test_r7_docs_sweep_teaches_neither_the_field_nor_a_filter_on_it
    R7-AC3  → covered by tests/test_obsidian_templates.py

Notes on RED validation (see each test's docstring for detail): this branch's
fix is uncommitted, so ``git show HEAD:<path>`` still returns the pre-fix
source for every file this change touches. Where a test can be driven
directly against that historical source without executing it (reading the
literal old logic/strings), RED is validated genuinely by diff, not
reconstructed from memory. Where a historical fact is asserted without
re-running the old code (R1-AC4, R4-AC7), that is called out explicitly as a
documented-not-executed RED check.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from llmwiki import REPO_ROOT
from llmwiki.build import ensure_project_stubs
from llmwiki.candidates import promote
from llmwiki.candidates_harvest import harvest_targets, write_stubs
from llmwiki.graphify_bridge import _extract_wiki_nodes, node_type_bonus
from llmwiki.lint import load_pages, run_all
from llmwiki.mcp.server import TOOL_IMPLS, handle_tools_call
from llmwiki.reindex import reindex_wiki, seed_index_text
from llmwiki.synth.base import BaseSynthesizer, DummySynthesizer
from llmwiki.synth.pipeline import synthesize_new_sessions
from tests.changelog_notes import shipping_section_text


def _mk_source(wiki: Path, slug: str, links: list[str]) -> None:
    """Write a minimal source page whose Connections list the given links."""
    path = wiki / "sources" / f"{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(f"- [[{name}]] — why it connects" for name in links)
    path.write_text(
        f"---\ntitle: {slug}\ntype: source\n---\n\n## Connections\n{body}\n",
        encoding="utf-8",
    )


class _FakeSynthesizer(BaseSynthesizer):
    """LLM stand-in for `promote()`'s Key Facts backend requirement."""

    def __init__(self, response: str = "- A real fact about it. [[a]]\n") -> None:
        self.response = response

    def synthesize_source_page(self, raw_body, meta, prompt_template) -> str:  # noqa: ARG002
        return self.response

    def is_available(self) -> bool:
        return True


# ─── R1 — the headline claim ───────────────────────────────────────────
#
# The issue (#102) reports that approving every pending page after a
# harvest was *guaranteed* to produce one lint error per promoted entity.
# This is the scenario that must be demonstrably fixed: sync/synth →
# harvest → promote every candidate → lint, zero errors attributable to
# the approval.


def test_headline_full_review_cycle_promotes_and_lints_clean(tmp_path: Path) -> None:
    """R1-AC3: a vault where every pending page has been approved lints clean.

    Builds a tmp vault (never the operator's), harvests one entity and one
    concept candidate from three source pages each, promotes both through
    the real `candidates.promote()` path (status: candidate → reviewed,
    Key Facts filled from evidence), then runs the *entire* lint registry
    and asserts zero issues of any severity — not just zero errors — so the
    vault is provably clean after approval, matching "reports no problems
    caused by that approval" in the functional spec.
    """
    # @regression
    wiki = tmp_path / "wiki"
    (wiki / "sources").mkdir(parents=True)
    (wiki / "overview.md").write_text("# Overview\n", encoding="utf-8")

    for slug in ("a", "b", "c"):
        _mk_source(wiki, slug, ["Subject", "Compounding"])

    targets = harvest_targets(wiki)
    written = write_stubs(
        wiki, targets,
        classify=lambda names: {"Subject": "entity", "Compounding": "concept"},
    )
    assert {p.stem for p in written} == {"Subject", "Compounding"}

    fake = _FakeSynthesizer()
    promoted = [
        promote(p.stem, wiki, kind=p.parent.name, synthesizer=fake)
        for p in written
    ]
    assert {p.parent.name for p in promoted} == {"entities", "concepts"}
    for path in promoted:
        text = path.read_text(encoding="utf-8")
        assert "status: reviewed" in text
        assert "entity_type" not in text

    pages = load_pages(wiki)
    issues = run_all(pages)

    assert issues == [], (
        f"expected zero lint issues after promoting every candidate, got: {issues}"
    )


def test_headline_red_old_stamped_entity_type_would_have_failed_pre_fix() -> None:
    """RED for the headline test.

    Before this change (verified by ``git show HEAD:llmwiki/candidates_harvest.py``,
    which still returns the pre-fix source on this branch), ``write_stubs``
    stamped ``entity_type: unknown`` on every entity candidate, and
    ``frontmatter_validity`` (``git show HEAD:llmwiki/lint/rules/frontmatter_validity.py``)
    rejected any `entity_type` value outside a fixed seven-value tuple that
    did not include ``"unknown"``. So the exact frontmatter shape the old
    pipeline produced for every approved entity would have failed lint.

    This test reproduces that historical rejection rule verbatim (frozen
    here, not imported from production — the real check no longer exists)
    against that exact stamped shape to prove the failure was real, then
    runs the *current* `frontmatter_validity` rule over the same page and
    asserts it reports nothing — the assertion that flips is "does lint
    reject this page", true pre-fix and false post-fix.
    """
    # @regression
    # Frozen copy of the deleted `llmwiki.schema.ENTITY_TYPES` tuple
    # (git show HEAD:llmwiki/schema.py) — for RED demonstration only.
    old_entity_types = ("person", "org", "tool", "concept", "api", "library", "project")

    # Frozen copy of the deleted `entity_type` validation block from
    # `llmwiki/lint/rules/frontmatter_validity.py` (git show HEAD).
    def old_entity_type_issue(meta: dict) -> str | None:
        et = str(meta.get("entity_type", "")).lower()
        if et and et not in old_entity_types:
            return f"invalid entity_type {et!r} (expected one of {list(old_entity_types)})"
        return None

    # What write_stubs used to write for an entity candidate
    # (git show HEAD:llmwiki/candidates_harvest.py, line ~220):
    #   entity_type = "entity_type: unknown\n" if kind == "entity" else ""
    pre_fix_meta = {"type": "entity", "title": "Subject", "entity_type": "unknown"}

    assert old_entity_type_issue(pre_fix_meta) is not None, (
        "the pre-fix validator must reject the pre-fix stamped shape — "
        "if this fails, the RED reconstruction itself is wrong"
    )

    page = {
        "path": Path("entities/Subject.md"),
        "rel": "entities/Subject.md",
        "text": "",
        "meta": pre_fix_meta,
        "body": "",
    }
    issues = run_all({"entities/Subject.md": page}, selected=["frontmatter_validity"])

    assert issues == [], (
        "current frontmatter_validity must not flag the field that used to "
        f"be rejected pre-fix, but got: {issues}"
    )


# ─── R1-AC4 — asking for the removed check by name fails loudly ───────


def test_r1_ac4_cli_lint_unknown_rule_name_errors_end_to_end(tmp_path: Path) -> None:
    """R1-AC4, driven through the real ``python3 -m llmwiki`` binary.

    RED (documented, not executed): ``git show HEAD:llmwiki/lint/rules/entity_consistency.py``
    shows the rule still exists at HEAD and is imported by
    ``git show HEAD:llmwiki/lint/rules/__init__.py`` — pre-fix,
    ``--rules entity_consistency`` named a real, registered rule and this
    exact command would have exited 0. The in-process equivalent of this
    scenario (``tests/test_lint_rules.py::test_cli_lint_exits_non_zero_on_unknown_rule``)
    already went red-then-green during slice 1's own development; this test
    adds the subprocess-level (true end-to-end CLI) version.
    """
    # @regression
    wiki = tmp_path / "wiki" / "entities"
    wiki.mkdir(parents=True)
    (wiki / "Foo.md").write_text(
        "---\ntitle: Foo\ntype: entity\n---\n\nBody.\n", encoding="utf-8"
    )

    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT) + (
        os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )
    cp = subprocess.run(
        [sys.executable, "-m", "llmwiki", "lint",
         "--wiki-dir", str(wiki.parent), "--rules", "entity_consistency"],
        capture_output=True, text=True, check=False, env=env, cwd=str(REPO_ROOT),
    )

    assert cp.returncode != 0, cp.stdout + cp.stderr
    assert "entity_consistency" in cp.stderr
    assert "frontmatter_validity" in cp.stderr  # lists the valid rules


# ─── R2 — nothing creates the label any more ───────────────────────────


def test_r2_no_writer_stamps_entity_type_across_full_pipeline(tmp_path: Path) -> None:
    """R2-AC3: after a full run touching every writer, no file under
    wiki/ contains an entity_type field.

    Drives all three page-writing paths against one tmp vault: a real
    session synthesis (``synthesize_new_sessions`` with the dummy backend,
    exercising the source-page writer), a harvest + stub write (the
    candidates writer named in R2-AC1), and project-stub seeding (the
    build-time writer named in R2-AC2). Then walks every file the run
    produced and asserts none of them carry the field.

    RED (verified via source diff, not executed): ``git show
    HEAD:llmwiki/candidates_harvest.py`` stamps ``entity_type: unknown`` for
    entity candidates, and ``git show HEAD:llmwiki/build.py`` writes
    ``entity_type: project\\n`` in the project-stub template — so this same
    scan over the pre-fix writers' output would have found hits.
    """
    # @regression
    raw = tmp_path / "raw" / "sessions" / "demo-proj"
    raw.mkdir(parents=True)
    (raw / "2026-05-01-first.md").write_text(
        '---\ntitle: "Session: first"\ntype: source\ntags: [claude-code]\n'
        "date: 2026-05-01\n"
        "source_file: raw/sessions/demo-proj/2026-05-01-first.md\n"
        "slug: first\nproject: demo-proj\nmodel: claude-sonnet-4-6\n---\n\n"
        "# Session: first\n\n## Summary\n\nDid some work.\n",
        encoding="utf-8",
    )

    wiki = tmp_path / "wiki"
    sources = wiki / "sources"
    sources.mkdir(parents=True)
    log_file = wiki / "log.md"
    log_file.write_text("# Log\n", encoding="utf-8")

    summary = synthesize_new_sessions(
        backend=DummySynthesizer(),
        raw_dir=raw.parent,
        wiki_sources_dir=sources,
        log_path=log_file,
    )
    assert summary["synthesized"] == 1

    # Give harvest something to find: three more source pages naming a
    # shared target, clearing the default --min-refs 3 threshold.
    for slug in ("extra-a", "extra-b", "extra-c"):
        _mk_source(wiki, slug, ["Widget"])
    targets = harvest_targets(wiki)
    stubs = write_stubs(wiki, targets, classify=lambda names: dict.fromkeys(names, "entity"))
    assert stubs, "fixture must actually exercise the candidates writer"

    project_stubs = ensure_project_stubs({"demo-proj": []}, wiki / "projects")
    assert project_stubs, "fixture must actually exercise the project-stub writer"

    hits = [
        p for p in wiki.rglob("*.md")
        if "entity_type" in p.read_text(encoding="utf-8", errors="replace")
    ]
    assert hits == [], f"entity_type leaked into: {hits}"


# ─── R3 — Project as a first-class page kind, combined ─────────────────


def test_r3_project_page_is_lint_clean_claim_checked_ranked_and_cataloged(
    tmp_path: Path,
) -> None:
    """R3-AC1, AC4, AC5, AC6 in one flow: a `type: project` page is accepted
    by lint, claim-checked like entity/concept pages, carries the same
    graph relevance bonus as a real page (while its synthetic project hub
    does not), and shows up in the regenerated catalog with an accurate
    count.

    RED: this test executes frozen reconstructions of the two deleted
    checks (not imports from production — both are gone) against the exact
    same page/node data the assertions above use, to prove the pre-fix
    behaviour really would have differed:
      * ``git show HEAD:llmwiki/lint/rules/frontmatter_validity.py`` — old
        ``VALID_TYPES`` has no ``"project"``.
      * ``git show HEAD:llmwiki/graphify_bridge.py`` — old bonus line reads
        ``type_bonus = 0.5 if ndata.get("type") in ("entity", "concept") else 0``,
        with no ``"project"`` and no ``file`` gate at all.
    """
    # @regression
    old_valid_types = {"source", "entity", "concept", "synthesis",
                        "comparison", "question", "navigation", "context"}
    assert "project" not in old_valid_types, (
        "RED sanity: the frozen old VALID_TYPES must not include project"
    )

    def old_type_bonus(ndata: dict) -> float:
        return 0.5 if ndata.get("type") in ("entity", "concept") else 0.0

    wiki = tmp_path / "wiki"
    (wiki / "sources").mkdir(parents=True)
    (wiki / "projects").mkdir(parents=True)
    (wiki / "overview.md").write_text("# Overview\n", encoding="utf-8")
    (wiki / "index.md").write_text(seed_index_text(), encoding="utf-8")

    (wiki / "sources" / "kickoff.md").write_text(
        "---\ntitle: kickoff\ntype: source\nproject: myproj\n---\n\n"
        "## Summary\nKicked off myproj.\n",
        encoding="utf-8",
    )
    (wiki / "projects" / "myproj.md").write_text(
        '---\ntitle: "myproj"\ntype: project\nproject: myproj\n'
        "sources: [kickoff]\n---\n\n# myproj\n\n"
        "## Key Facts\n\n- Uses Python. [[kickoff]]\n",
        encoding="utf-8",
    )

    pages = load_pages(wiki)
    issues = run_all(pages, selected=["frontmatter_validity", "claim_verification"])
    assert issues == [], (
        f"project page must pass validity + claim checks like entity/concept, got: {issues}"
    )

    project_meta = pages["projects/myproj.md"]["meta"]
    assert project_meta["type"].lower() not in old_valid_types, (
        "RED sanity: the pre-fix VALID_TYPES rule would have rejected this "
        "exact page's `type: project` as invalid"
    )

    nodes = _extract_wiki_nodes(wiki)["nodes"]
    page_node = next(n for n in nodes if n["file"] == "projects/myproj.md")
    hub_node = next(n for n in nodes if n["id"] == "project__myproj")
    assert page_node["type"] == "project"
    assert hub_node["file"] == ""

    assert node_type_bonus(page_node) == 0.5, "a real project page must be boosted"
    assert node_type_bonus(hub_node) == 0.0, "the synthetic project hub must not be"

    # RED: under the pre-fix formula, the project *page* would have scored
    # the same 0.0 as its own hub — the boost this test just proved exists
    # did not exist before the change.
    assert old_type_bonus(page_node) == 0.0, (
        "RED sanity: the pre-fix formula must not have boosted project pages either"
    )
    assert old_type_bonus(page_node) != node_type_bonus(page_node), (
        "the fix must actually change the project page's score"
    )

    reindex_wiki(wiki)
    catalog = (wiki / "index.md").read_text(encoding="utf-8")
    assert "## Projects (1)" in catalog
    assert "- [myproj](projects/myproj.md)" in catalog


# ─── R4-AC7 — the removed tool name is now unknown, not a silent no-op ──


def test_r4_old_entity_search_tool_name_is_now_unknown() -> None:
    """R4-AC7: calling the removed `wiki_entity_search` tool by its old
    name returns an unknown-tool error via the real dispatch path
    (`handle_tools_call`), not a silent no-op or a stale alias.

    RED (documented, not executed): ``git show HEAD:llmwiki/mcp/server.py``
    lists ``"wiki_entity_search": tool_wiki_entity_search`` in ``TOOL_IMPLS``
    (line 1257) and a matching schema entry in ``TOOLS`` (line 419) — pre-fix,
    ``TOOL_IMPLS.get("wiki_entity_search")`` was not ``None``, so
    ``handle_tools_call`` would have executed the tool and returned a normal
    (``isError: False``) result instead of the "Unknown tool" branch this
    test asserts.
    """
    # @regression
    assert "wiki_entity_search" not in TOOL_IMPLS

    result = handle_tools_call({"name": "wiki_entity_search", "arguments": {"term": "x"}})

    assert result.get("isError") is True
    text = result["content"][0]["text"]
    assert "wiki_entity_search" in text
    assert "unknown tool" in text.lower()


# ─── R7 — documentation matches the new behaviour ──────────────────────


def test_r7_docs_sweep_teaches_neither_the_field_nor_a_filter_on_it() -> None:
    """R7-AC1: none of the command reference, agent-facing reference,
    contributor schema guide, setup tutorial, or vault templates instructs
    anyone to set an entity type or filter by one. R7-AC2: the release
    notes record all four breaking changes from this feature.

    Sweeps every doc the technical spec names for this requirement in one
    test, rather than the per-file spot checks slices 1-5 already carry —
    this is the "read all of them" acceptance claim R7-AC1 literally makes.

    RED (verified via source diff, not executed): ``git show
    HEAD:docs/reference/cli.md`` documents ``--allow-unclassified`` filing
    ``entity_type: unknown``; ``git show HEAD:docs/tutorials/setup-guide.md``
    has two `entity_type: …` examples; ``git show
    HEAD:docs/reference/reader-shell.md`` and ``git show
    HEAD:docs/reference/ui.md`` both name `entity_type` as a browsable
    field/facet. Every one of those hits is gone in the current tree.
    """
    # @regression
    docs_that_must_not_teach_it = [
        "AGENTS.md",
        "docs/reference/cli.md",
        "docs/reference/reader-api.md",
        "docs/reference/reader-shell.md",
        "docs/reference/ui.md",
        "docs/tutorials/setup-guide.md",
        "examples/obsidian-templates/entity-template.md",
        "examples/obsidian-templates/README.md",
        "examples/wiki_dashboard.md",
        "CLAUDE.md",
    ]
    offenders = []
    for rel in docs_that_must_not_teach_it:
        path = REPO_ROOT / rel
        text = path.read_text(encoding="utf-8")
        if "entity_type" in text:
            offenders.append(rel)
    assert offenders == [], f"still teaches entity_type: {offenders}"

    changelog = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    unreleased = shipping_section_text(changelog)
    for marker in (
        "entity_consistency",
        "--allow-unclassified",
        "wiki_entity_search",
        "project` is a first-class page kind",
    ):
        assert marker in unreleased, (
            f"CHANGELOG's Unreleased section must record {marker!r} as a "
            "breaking change for #102"
        )
