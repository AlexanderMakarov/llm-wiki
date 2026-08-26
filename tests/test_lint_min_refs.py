"""``link_integrity`` honours the harvest significance threshold (#150).

``synth`` writes a ``[[wikilink]]`` for every topic it names; the candidate
harvest materializes a page only for targets named by ``DEFAULT_MIN_REFS``+
distinct source pages. Before this, ``link_integrity`` called every one of the
unmaterialized remainder a broken link — the only component in the product
that disagreed with the threshold. These tests pin the agreement.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from llmwiki.candidates_harvest import DEFAULT_MIN_REFS, harvest_targets
from llmwiki.cli import build_parser
from llmwiki.lint import (
    REGISTRY,
    LintOptions,
    load_pages,
    rules,  # noqa: F401 — force rule registration
    run_all,
)
from llmwiki.lint.rules import LinkIntegrity
from llmwiki.thresholds import DEFAULT_MIN_REFS as THRESHOLDS_DEFAULT_MIN_REFS
from llmwiki.wikilinks import count_source_refs

# ─── Fixtures ──────────────────────────────────────────────────────────


def _source(wiki: Path, slug: str, body: str) -> None:
    """Write ``wiki/sources/<slug>.md`` with minimal frontmatter."""
    path = wiki / "sources" / f"{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'---\ntitle: "{slug}"\ntype: source\n---\n\n{body}\n', encoding="utf-8"
    )


def _rule(min_refs: int) -> LinkIntegrity:
    """A ``LinkIntegrity`` instance carrying an explicit threshold."""
    rule = LinkIntegrity()
    rule.options = LintOptions(min_refs=min_refs)
    return rule


def _targets(issues: list[dict]) -> set[str]:
    """The wikilink targets named by ``broken wikilink [[X]]`` messages."""
    return {i["message"].removeprefix("broken wikilink [[").removesuffix("]]")
            for i in issues}


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    """Two sources naming ``[[Twice]]``, three naming ``[[Thrice]]``."""
    _source(tmp_path, "a", "See [[Twice]] and [[Thrice]].")
    _source(tmp_path, "b", "See [[Twice]] and [[Thrice]].")
    _source(tmp_path, "c", "See [[Thrice]].")
    return tmp_path


# ─── The threshold gate ────────────────────────────────────────────────


def test_one_definition_of_the_stock_threshold():
    """The harvester's constant *is* the neutral module's — not a copy."""
    assert DEFAULT_MIN_REFS is THRESHOLDS_DEFAULT_MIN_REFS
    assert LintOptions().min_refs == THRESHOLDS_DEFAULT_MIN_REFS


def test_below_threshold_target_is_not_reported(vault: Path):
    """Two refs at a threshold of three: the harvest declined it on purpose."""
    issues = _rule(DEFAULT_MIN_REFS).run(load_pages(vault))
    assert "Twice" not in _targets(issues)


def test_at_threshold_target_is_reported(vault: Path):
    """Three refs and no page: a genuine gap, and still a finding."""
    issues = _rule(DEFAULT_MIN_REFS).run(load_pages(vault))
    assert _targets(issues) == {"Thrice"}


def test_min_refs_one_restores_every_finding(vault: Path):
    """Nothing is permanently unreachable — lowering the bar shows it all."""
    issues = _rule(1).run(load_pages(vault))
    assert _targets(issues) == {"Twice", "Thrice"}


def test_materialized_target_is_never_reported(vault: Path):
    """The threshold gates *unresolved* links; a real page still resolves."""
    (vault / "entities").mkdir()
    (vault / "entities" / "Thrice.md").write_text(
        '---\ntitle: "Thrice"\ntype: entity\n---\n\n# Thrice\n', encoding="utf-8"
    )
    assert "Thrice" not in _targets(_rule(1).run(load_pages(vault)))


# ─── The zero case: never a harvest decision ───────────────────────────


@pytest.fixture
def dangling(tmp_path: Path) -> Path:
    """A non-source page linking to a target no source page ever names.

    Zero source references can only arise this way: a ``[[link]]`` written in
    a source page counts itself.
    """
    _source(tmp_path, "a", "A source that names nothing in particular.")
    (tmp_path / "concepts").mkdir()
    (tmp_path / "concepts" / "Foo.md").write_text(
        '---\ntitle: "Foo"\ntype: concept\n---\n\n# Foo\n\nSee [[Ghost]].\n',
        encoding="utf-8",
    )
    return tmp_path


def test_unnamed_target_is_reported_at_the_stock_threshold(dangling: Path):
    """No source names it, so the harvest never saw it and never declined it.

    Excusing everything below the threshold would swallow this link at every
    threshold — a whole class of genuine finding, silently deleted.
    """
    assert _targets(_rule(DEFAULT_MIN_REFS).run(load_pages(dangling))) == {"Ghost"}


@pytest.mark.parametrize("min_refs", [1, DEFAULT_MIN_REFS, 10])
def test_the_zero_case_is_threshold_independent(dangling: Path, min_refs: int):
    """Raising the bar excuses declined targets, never dangling ones."""
    assert _targets(_rule(min_refs).run(load_pages(dangling))) == {"Ghost"}


def test_link_from_a_non_source_page_is_reported(dangling: Path):
    """The concrete hole: entity/concept/project pages are outside the
    corpus harvest counts, so nothing they alone name is ever a decision."""
    issues = _rule(DEFAULT_MIN_REFS).run(load_pages(dangling))
    assert [(i["page"], i["message"]) for i in issues] == [
        ("concepts/Foo.md", "broken wikilink [[Ghost]]")
    ]


@pytest.mark.parametrize("min_refs", [2, 3, 5])
def test_one_reference_short_of_the_threshold_is_still_declined(
    tmp_path: Path, min_refs: int
):
    """Opening the zero case must not reopen the deliberate-decline band."""
    for i in range(min_refs - 1):
        _source(tmp_path, f"s{i}", "See [[Declined]].")
    assert _targets(_rule(min_refs).run(load_pages(tmp_path))) == set()


# ─── Resolution is unchanged ───────────────────────────────────────────


def test_pending_candidate_resolves(vault: Path):
    """A stub under ``candidates/`` is a real page to lint (opposite of
    harvest, which must keep re-proposing it so its evidence refreshes)."""
    stub = vault / "candidates" / "entities" / "Thrice.md"
    stub.parent.mkdir(parents=True)
    stub.write_text(
        '---\ntitle: "Thrice"\ntype: entity\nstatus: candidate\n---\n\n# Thrice\n',
        encoding="utf-8",
    )
    assert _rule(DEFAULT_MIN_REFS).run(load_pages(vault)) == []


def test_archived_slug_still_reads_as_broken(vault: Path):
    """A discarded page is cold storage (#140): the link wants a human
    decision, so it stays a finding — the mirror image of the harvest, which
    treats the same archived slug as resolved."""
    archived = vault / "archive" / "candidates" / "2026-08-01T13-22-06"
    archived.mkdir(parents=True)
    (archived / "Thrice.md").write_text(
        '---\ntitle: "Thrice"\ntype: entity\n---\n\n# Thrice\n', encoding="utf-8"
    )
    issues = _rule(DEFAULT_MIN_REFS).run(load_pages(vault))
    assert _targets(issues) == {"Thrice"}


# ─── Shared counting ───────────────────────────────────────────────────


def test_count_source_refs_counts_a_target_once_per_page():
    refs = count_source_refs({
        "sources/a.md": "[[Foo]] [[Foo]] and [[Foo]] again, plus [[Bar]].",
        "sources/b.md": "[[Foo]]",
    })
    assert refs["Foo"] == {"sources/a.md", "sources/b.md"}
    assert refs["Bar"] == {"sources/a.md"}


def test_rule_and_harvester_agree_on_the_threshold(vault: Path):
    """One corpus, one answer about which targets clear the bar."""
    harvested = {t.name for t in harvest_targets(vault, min_refs=DEFAULT_MIN_REFS)}
    reported = _targets(_rule(DEFAULT_MIN_REFS).run(load_pages(vault)))
    assert harvested == reported == {"Thrice"}


# ─── The runner passes options without breaking any rule ───────────────


def test_every_registered_rule_runs_under_the_new_runner(vault: Path):
    """Options travel on the instance, never as a new ``run()`` kwarg.

    The runner converts a rule exception into an error-severity issue, so a
    ``TypeError`` in 16 of the 17 rules would show up as findings on a clean
    vault while the suite still looked green.
    """
    issues = run_all(load_pages(vault), options=LintOptions(min_refs=1))
    raised = [i for i in issues if "rule raised exception" in i["message"]]
    assert raised == []
    # Sanity: the run really did exercise every rule.
    assert len(REGISTRY) == 17


def test_run_all_defaults_to_the_stock_threshold(vault: Path):
    """No ``options`` given → the harvest's stock value, with no second
    place to change it."""
    default = run_all(load_pages(vault), selected=["link_integrity"])
    explicit = run_all(
        load_pages(vault),
        selected=["link_integrity"],
        options=LintOptions(min_refs=DEFAULT_MIN_REFS),
    )
    assert _targets(default) == _targets(explicit) == {"Thrice"}


# ─── CLI surface ───────────────────────────────────────────────────────


def test_lint_parser_exposes_min_refs():
    """``lint --min-refs N`` exists and defaults to the stock threshold, so
    there is no second place to change it."""
    parser = build_parser()
    assert parser.parse_args(["lint"]).min_refs == DEFAULT_MIN_REFS
    assert parser.parse_args(["lint", "--min-refs", "1"]).min_refs == 1
