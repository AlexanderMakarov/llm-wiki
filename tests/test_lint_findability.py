"""Tests for #197 findability lint rules and SearchContext wiring."""

from __future__ import annotations

from pathlib import Path

import pytest

import llmwiki.lint.rules.page_findability as page_findability_mod
import llmwiki.lint.rules.search_consistency as search_consistency_mod
import llmwiki.search.context as search_context_mod
from llmwiki.lint import (
    REGISTRY,
    LintOptions,
    load_pages,
    rules,  # noqa: F401
    run_lint,
)
from llmwiki.lint.rules.page_findability import PageFindability
from llmwiki.lint.rules.search_consistency import SearchConsistency
from llmwiki.lint.rules.title_ambiguity import TitleAmbiguity
from llmwiki.search.context import SearchContext
from llmwiki.search.corpus import DEFAULT_PER_FILE_CAP
from llmwiki.search.engine import MatchResult
from llmwiki.search.evaluate import (
    collect_wikilink_lookups,
    sample_evenly,
    select_absent_terms,
    select_present_terms,
)
from llmwiki.search.scoring import match_page, score_extract


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _wiki_page(vault: Path, rel: str, title: str, body: str = "Body.\n") -> None:
    _write(
        vault / "wiki" / rel,
        f"---\ntitle: {title}\ntype: entity\n---\n\n{body}",
    )


def _lint_options(vault: Path, *, sample_max: int = 300) -> LintOptions:
    return LintOptions(
        content_root=vault,
        search_context=SearchContext(content_root=vault),
        findability_sample_max=sample_max,
    )


_SEARCH_RULES = ("page_findability", "title_ambiguity", "search_consistency")


# ── registry ────────────────────────────────────────────────────────────


def test_search_findability_rules_registered():
    for name in _SEARCH_RULES:
        assert name in REGISTRY
    assert len(REGISTRY) == 20


# ── skip when options absent ────────────────────────────────────────────


def test_findability_rules_skip_when_options_absent(tmp_path: Path):
    _wiki_page(tmp_path, "entities/Foo.md", "Foo")
    pages = load_pages(tmp_path / "wiki")
    outcome = run_lint(pages, selected=list(_SEARCH_RULES))
    assert outcome.ran == []
    for name in _SEARCH_RULES:
        assert name in outcome.skipped
        assert "search options" in outcome.skipped[name]
    assert outcome.issues == []


def test_direct_rule_construction_skip_reason():
    for cls in (PageFindability, TitleAmbiguity, SearchConsistency):
        rule = cls()
        assert rule.skip_reason() == "search options not provided"


# ── page_findability ────────────────────────────────────────────────────


def test_page_findability_clean_vault(tmp_path: Path):
    _wiki_page(tmp_path, "entities/Alpha.md", "AlphaUniqueTitle")
    _wiki_page(tmp_path, "entities/Beta.md", "BetaUniqueTitle")
    pages = load_pages(tmp_path / "wiki")
    outcome = run_lint(
        pages,
        selected=["page_findability"],
        options=_lint_options(tmp_path),
    )
    assert "page_findability" in outcome.ran
    errors = [i for i in outcome.issues if i["severity"] == "error"]
    assert errors == []
    infos = [i for i in outcome.issues if i["severity"] == "info"]
    assert any("checked 2 of 2" in i["message"] for i in infos)


def test_page_findability_reports_unscored_title(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _wiki_page(tmp_path, "entities/Ghost.md", "GhostTitle")
    pages = load_pages(tmp_path / "wiki")
    real = score_extract

    def _zero_ghost(page, query):
        if "Ghost" in page.rel_path:
            return 0.0
        return real(page, query)

    monkeypatch.setattr(
        "llmwiki.search.evaluate.score_extract", _zero_ghost
    )
    outcome = run_lint(
        pages,
        selected=["page_findability"],
        options=_lint_options(tmp_path),
    )
    errors = [i for i in outcome.issues if i["severity"] == "error"]
    assert len(errors) == 1
    assert "Ghost.md" in errors[0]["page"]
    assert "not returned" in errors[0]["message"]


# ── title_ambiguity ─────────────────────────────────────────────────────


def test_title_ambiguity_names_outranker(tmp_path: Path):
    # Long page with a short title loses to a shorter near-duplicate whose
    # title still contains the query (length normalisation + shared phrase).
    long_body = ("lorem ipsum dolor sit amet " * 80) + "\n"
    _wiki_page(
        tmp_path,
        "entities/Config.md",
        "Configuration",
        body=long_body,
    )
    _wiki_page(
        tmp_path,
        "entities/Aaa.md",
        "Configuration Guide",
        body="Configuration\n",
    )
    pages = load_pages(tmp_path / "wiki")
    outcome = run_lint(
        pages,
        selected=["title_ambiguity"],
        options=_lint_options(tmp_path),
    )
    warnings = [i for i in outcome.issues if i["severity"] == "warning"]
    assert warnings, outcome.issues
    config = [w for w in warnings if "Config.md" in w["page"]]
    assert config
    assert "outranked by" in config[0]["message"]
    assert "Aaa.md" in config[0]["message"]


def test_title_ambiguity_reports_tie(tmp_path: Path):
    # Same title on two pages → equal title scores; earlier path wins.
    _wiki_page(tmp_path, "entities/Aaa.md", "SharedTieTitle", body="x\n")
    _wiki_page(tmp_path, "entities/Zzz.md", "SharedTieTitle", body="x\n")
    pages = load_pages(tmp_path / "wiki")
    outcome = run_lint(
        pages,
        selected=["title_ambiguity"],
        options=_lint_options(tmp_path),
    )
    warnings = [i for i in outcome.issues if i["severity"] == "warning"]
    zzz = [w for w in warnings if "Zzz.md" in w["page"]]
    assert zzz
    assert "tied with" in zzz[0]["message"]
    assert "Aaa.md" in zzz[0]["message"]


# ── search_consistency ──────────────────────────────────────────────────


def test_search_consistency_agrees_and_prints_terms(tmp_path: Path):
    _wiki_page(tmp_path, "entities/Keep.md", "Keep")
    sessions = tmp_path / "raw" / "sessions"
    _write(
        sessions / "2026-01-01T00-00-alpha-session.md",
        "---\ntitle: Alpha\ntype: source\n---\n\n"
        "Conversation mentions PlantedLexeme and WidgetFactory.\n",
    )
    _write(
        sessions / "2026-01-02T00-00-zeta-session.md",
        "---\ntitle: Zeta\ntype: source\n---\n\n"
        "Also discusses PlantedLexeme again.\n",
    )
    pages = load_pages(tmp_path / "wiki")
    outcome = run_lint(
        pages,
        selected=["search_consistency"],
        options=_lint_options(tmp_path),
    )
    assert "search_consistency" in outcome.ran
    errors = [i for i in outcome.issues if i["severity"] == "error"]
    assert errors == []
    infos = [i["message"] for i in outcome.issues if i["severity"] == "info"]
    assert any(m.startswith("present terms:") for m in infos)
    assert any(m.startswith("absent terms:") for m in infos)
    assert any("survival share:" in m for m in infos)
    present_line = next(m for m in infos if m.startswith("present terms:"))
    assert "PlantedLexeme" in present_line


def test_search_consistency_errors_when_search_misses_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _wiki_page(tmp_path, "entities/Keep.md", "Keep")
    _write(
        tmp_path / "raw" / "sessions" / "2026-01-01T00-00-only-session.md",
        "---\ntitle: Only\ntype: source\n---\n\nUniquePresentTokenXYZ\n",
    )
    pages = load_pages(tmp_path / "wiki")

    real = search_consistency_mod.search_match

    def _drop_present(corpus_pages, terms, **kwargs):
        out = real(corpus_pages, terms, **kwargs)
        for term in terms:
            if term == "UniquePresentTokenXYZ":
                out[term] = MatchResult(pages=(), truncated=False)
        return out

    monkeypatch.setattr(search_consistency_mod, "search_match", _drop_present)
    outcome = run_lint(
        pages,
        selected=["search_consistency"],
        options=_lint_options(tmp_path),
    )
    errors = [i for i in outcome.issues if i["severity"] == "error"]
    assert any("UniquePresentTokenXYZ" in e["message"] for e in errors)


# ── sampling / term-selection determinism ───────────────────────────────


def test_sample_evenly_deterministic_and_capped():
    items = [f"p{i:03d}" for i in range(500)]
    a = sample_evenly(items, 300)
    b = sample_evenly(items, 300)
    assert a == b
    assert len(a) == 300
    assert a[0] == items[0]
    assert a[-1] == items[-1]


def test_present_and_absent_term_selection_stable(tmp_path: Path):
    sessions = tmp_path / "raw" / "sessions"
    _write(
        sessions / "2026-01-01T00-00-a.md",
        "AlphaToken BetaToken GammaToken DeltaToken EpsilonTok\n",
    )
    _write(
        sessions / "2026-01-09T00-00-z.md",
        "ZuluToken YankeeTok XrayToken WhiskeyT VictorToken\n",
    )
    _wiki_page(tmp_path, "entities/E.md", "E")
    ctx = SearchContext(content_root=tmp_path)
    pages = ctx.corpus().pages
    p1 = select_present_terms(pages, count=40)
    p2 = select_present_terms(pages, count=40)
    assert p1 == p2
    assert p1  # extracted something
    a1 = select_absent_terms(pages, count=5)
    a2 = select_absent_terms(pages, count=5)
    assert a1 == a2
    assert len(a1) == 5
    blob = "\n".join(p.text_lower for p in pages)
    for term in a1:
        assert term.lower() not in blob


def test_present_terms_ignore_oversize_unscanned_sessions(tmp_path: Path):
    """Terms from files skipped by scan_corpus must not enter the answer key."""
    sessions = tmp_path / "raw" / "sessions"
    _write(
        sessions / "2026-01-01T00-00-small.md",
        "ScannedPresentTokenABCDEF appears in a normal session.\n",
    )
    # Oversize relative to the per-file cap — never partial-read by scan.
    oversize = sessions / "2026-01-02T00-00-huge.md"
    oversize.parent.mkdir(parents=True, exist_ok=True)
    unique = "OversizeOnlyTokenXYZ999"
    # Keep under DEFAULT_PER_FILE_CAP + a little? We need size > per_file_cap.
    pad = "x" * (DEFAULT_PER_FILE_CAP + 64)
    oversize.write_text(f"{unique}\n{pad}", encoding="utf-8")
    assert oversize.stat().st_size > DEFAULT_PER_FILE_CAP

    _wiki_page(tmp_path, "entities/Keep.md", "Keep")
    ctx = SearchContext(content_root=tmp_path)
    scan = ctx.corpus()
    assert scan.skipped_oversize >= 1
    assert not any(unique.lower() in p.text_lower for p in scan.pages)

    terms = select_present_terms(scan.pages, count=40)
    assert "ScannedPresentTokenABCDEF" in terms
    assert unique not in terms


def test_page_findability_wikilink_alias_resolves_to_target(tmp_path: Path):
    """[[AliasName]] answer key is the survivor page; archive stays out."""
    _write(
        tmp_path / "wiki" / "entities" / "CanonicalThing.md",
        "---\ntitle: Canonical Thing\ntype: entity\n---\n\n"
        "Body about the survivor.\n\n"
        "## Aliases\n"
        "- UniqueAliasNameXYZ — merged from harvest\n\n"
        "## Connections\n"
        "- [[ReferrerPage]]\n",
    )
    _write(
        tmp_path / "wiki" / "entities" / "ReferrerPage.md",
        "---\ntitle: Referrer Page\ntype: entity\n---\n\n"
        "See [[UniqueAliasNameXYZ]] for the canonical page.\n",
    )
    # Cold storage: must not appear in wikilink answer key or scan.
    _write(
        tmp_path / "wiki" / "archive" / "entities" / "DiscardedCold.md",
        "---\ntitle: Discarded Cold\ntype: entity\n---\n\n"
        "[[ColdOnlyAliasZZZ]] and ColdOnlyTokenNeverScanned.\n\n"
        "## Aliases\n"
        "- ColdOnlyAliasZZZ\n",
    )

    ctx = SearchContext(content_root=tmp_path)
    pages = ctx.corpus().pages
    assert not any("archive" in p.rel_path.replace("\\", "/") for p in pages)
    assert not any("ColdOnly" in p.text for p in pages)

    lookups = collect_wikilink_lookups(pages)
    by_anchor = dict(lookups)
    assert "UniqueAliasNameXYZ" in by_anchor
    assert by_anchor["UniqueAliasNameXYZ"].endswith("CanonicalThing.md")
    assert "ColdOnlyAliasZZZ" not in by_anchor
    assert not any("DiscardedCold" in rel for _, rel in lookups)

    loaded = load_pages(tmp_path / "wiki")
    outcome = run_lint(
        loaded,
        selected=["page_findability"],
        options=_lint_options(tmp_path),
    )
    errors = [i for i in outcome.issues if i["severity"] == "error"]
    assert errors == [], errors
    infos = [i["message"] for i in outcome.issues if i["severity"] == "info"]
    assert any("wikilink lookups" in m for m in infos)
    wl_info = next(m for m in infos if "wikilink lookups" in m)
    assert "checked " in wl_info
    assert "UniqueAliasNameXYZ" not in wl_info  # counts only; failures name anchors


def test_page_findability_bare_wikilink_uses_corpus_cap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Bare anchors must go through capped search_match, not match_page(target) alone.

    With page_cap=1, an earlier decoy body hit fills the result; the real
    alias target still matches in isolation but is cut short in corpus search.
    """
    monkeypatch.setattr(page_findability_mod, "PAGE_CAP_FOR_FINDABILITY", 1)
    _wiki_page(
        tmp_path,
        "entities/AaaDecoy.md",
        "Decoy",
        body="body mentions SharedTokBareXYZ once\n",
    )
    _write(
        tmp_path / "wiki" / "entities" / "ZzzTarget.md",
        "---\ntitle: Real Target\ntype: entity\n---\n\n"
        "## Aliases\n"
        "- SharedTokBareXYZ\n\n"
        "Canonical page for the alias.\n",
    )
    _wiki_page(
        tmp_path,
        "concepts/Linker.md",
        "Linker",
        body="See [[SharedTokBareXYZ]].\n",
    )

    ctx = SearchContext(content_root=tmp_path)
    target = next(p for p in ctx.corpus().pages if p.rel_path.endswith("ZzzTarget.md"))
    assert match_page(target, "sharedtokbarexyz") is not None

    outcome = run_lint(
        load_pages(tmp_path / "wiki"),
        selected=["page_findability"],
        options=_lint_options(tmp_path),
    )
    errors = [i for i in outcome.issues if i["severity"] == "error"]
    assert any(
        "SharedTokBareXYZ" in e["message"] and "cut short" in e["message"]
        for e in errors
    ), errors


def test_findability_sample_max_stated_in_output(tmp_path: Path):
    for i in range(12):
        _wiki_page(tmp_path, f"entities/P{i:02d}.md", f"Title{i:02d}")
    pages = load_pages(tmp_path / "wiki")
    outcome = run_lint(
        pages,
        selected=["page_findability"],
        options=_lint_options(tmp_path, sample_max=5),
    )
    infos = [i for i in outcome.issues if i["severity"] == "info"]
    assert any("checked 5 of 12" in i["message"] for i in infos)


def test_search_context_scans_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _wiki_page(tmp_path, "entities/One.md", "One")
    _write(
        tmp_path / "raw" / "sessions" / "2026-01-01T00-00-s.md",
        "SessionTokenABCDEF\n",
    )
    ctx = SearchContext(content_root=tmp_path)
    calls = {"n": 0}

    real = search_context_mod.scan_corpus

    def _counting(*args, **kwargs):
        calls["n"] += 1
        return real(*args, **kwargs)

    monkeypatch.setattr(search_context_mod, "scan_corpus", _counting)
    pages = load_pages(tmp_path / "wiki")
    options = LintOptions(content_root=tmp_path, search_context=ctx)
    run_lint(pages, selected=list(_SEARCH_RULES), options=options)
    assert calls["n"] == 1
