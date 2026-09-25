"""Tests for ``llmwiki/wikilinks.py`` — the canonical wikilink parser.

Covers:
* ``wikilink_targets`` over every wikilink form the wiki uses
* Agreement between the canonical pattern (plus anchor stripping) and an
  anchor-excluding pattern variant, so consumers of either read the same links
* The one form on which the two shapes diverge
* A guardrail: the package declares the pattern in exactly one place
* One link per distinct target in each consumer that counts links
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import pytest

from llmwiki.backlinks import build_reverse_index
from llmwiki.lint.rules.orphan_detection import OrphanDetection
from llmwiki.references import build_index
from llmwiki.wikilinks import (
    WIKILINK_RE,
    build_page_alias_map,
    format_alias_bullet,
    norm_page_key,
    parse_page_aliases,
    resolve_wikilink_target,
    rewrite_wikilinks,
    wikilink_targets,
)

#: A pattern shape that keeps ``#`` out of the captured target instead of
#: stripping it afterwards. Consumers must not be able to tell the two apart.
_ANCHOR_EXCLUDING_RE = re.compile(r"\[\[([^\]|#]+?)(?:#[^\]]*)?(?:\|[^\]]+)?\]\]")

#: ``(case id, markdown, expected targets)``.
_CASES: list[tuple[str, str, set[str]]] = [
    ("plain", "[[a]]", {"a"}),
    ("alias", "[[a|b]]", {"a"}),
    ("anchor", "[[a#b]]", {"a"}),
    ("anchor-then-alias", "[[a#b|c]]", {"a"}),
    ("alias-containing-hash", "[[a|b#c]]", {"a"}),
    ("anchor-only", "[[#x]]", set()),
    ("several-on-one-line", "see [[a]], [[b|B]] and [[c#s]] below", {"a", "b", "c"}),
]

_ORDINARY = [c for c in _CASES if c[0] != "anchor-only"]


@pytest.mark.parametrize(
    ("text", "expected"),
    [(text, expected) for _, text, expected in _CASES],
    ids=[case_id for case_id, _, _ in _CASES],
)
def test_wikilink_targets(text: str, expected: set[str]) -> None:
    assert wikilink_targets(text) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("LLM-Wiki", "llmwiki"),
        ("llm-wiki", "llmwiki"),
        ("llm wiki", "llmwiki"),
        ("OpenAI", "openai"),
        ("Open AI", "openai"),
        ("Мой-Проект", "мойпроект"),
        ("мой проект", "мойпроект"),
    ],
)
def test_norm_page_key_folds_case_and_punctuation(raw: str, expected: str) -> None:
    """Page-identity fold shared by lint, harvest, and wikilink-titles migrate."""
    assert norm_page_key(raw) == expected


def test_norm_page_key_folds_unicode_spellings_and_full_case() -> None:
    """One identity per name: NFC == NFD, and case folding beyond ``.lower()``."""
    nfc = unicodedata.normalize("NFC", "Café Münster")
    nfd = unicodedata.normalize("NFD", "Café Münster")
    assert nfc != nfd  # two spellings of the same name
    assert norm_page_key(nfc) == norm_page_key(nfd)
    # Full case folding: ß and the Greek final sigma fold like their peers.
    assert norm_page_key("Straße") == norm_page_key("STRASSE") == "strasse"
    assert norm_page_key("Οδός") == norm_page_key("οδόσ")


@pytest.mark.parametrize(
    ("text", "expected"),
    [(text, expected) for _, text, expected in _ORDINARY],
    ids=[case_id for case_id, _, _ in _ORDINARY],
)
def test_agrees_with_anchor_excluding_variant(text: str, expected: set[str]) -> None:
    assert {t.strip() for t in _ANCHOR_EXCLUDING_RE.findall(text)} == expected
    assert wikilink_targets(text) == expected


def test_anchor_only_link_is_the_one_divergence() -> None:
    # The anchor-excluding variant needs at least one character before the
    # ``#``, so ``[[#x]]`` is not a match for it at all. The canonical pattern
    # does match and captures ``#x``, which anchor-stripping reduces to the
    # empty string — discarded. Both shapes end with no target, by two routes.
    assert _ANCHOR_EXCLUDING_RE.findall("[[#x]]") == []
    assert WIKILINK_RE.findall("[[#x]]") == ["#x"]
    assert wikilink_targets("[[#x]]") == set()


# ── one link per distinct target, across every consumer ────────────────────
#
# ``wikilink_targets`` returns a *set* of stripped targets, so a page naming
# the same page twice — once bare, once with a ``#section`` anchor — is one
# link, not two. These pin that in each consumer that counts links.

_ANCHOR_DUPLICATE = "See [[Hazel]] and [[Hazel#history]] for detail.\n"


def test_backlinks_lists_a_referrer_once_per_distinct_target() -> None:
    pages = {
        "batching": {
            "path": Path("batching.md"),
            "meta": {"title": "Batching", "date": "2026-04-01"},
            "body": _ANCHOR_DUPLICATE,
            "text": _ANCHOR_DUPLICATE,
        },
    }
    entries = build_reverse_index(pages)["Hazel"]
    assert [e.slug for e in entries] == ["batching"]


def test_references_records_one_row_per_distinct_target() -> None:
    pages = {
        "concepts/Batching.md": {"meta": {}, "body": _ANCHOR_DUPLICATE},
        "entities/Hazel.md": {"meta": {}, "body": ""},
    }
    rows = build_index(pages)["Hazel"]
    assert [(r.source, r.target_rel) for r in rows] == [
        ("concepts/Batching.md", "entities/Hazel.md")
    ]


def test_orphan_detection_counts_one_inbound_per_distinct_target() -> None:
    pages = {
        "concepts/Batching.md": {"meta": {}, "body": _ANCHOR_DUPLICATE},
        "entities/Hazel.md": {"meta": {}, "body": ""},
    }
    # One inbound link is still an inbound link: the anchor variant collapses
    # into it rather than adding a second, and Hazel is not an orphan either way.
    issues = OrphanDetection().run(pages)
    assert [i["page"] for i in issues] == ["concepts/Batching.md"]
    assert wikilink_targets(_ANCHOR_DUPLICATE) == {"Hazel"}


_DECLARATION_RE = re.compile(r"^\s*_?WIKILINK_RE\s*=\s*re\.compile", re.MULTILINE)
_PACKAGE = Path(__file__).resolve().parents[1] / "llmwiki"


def test_wikilink_pattern_is_declared_exactly_once() -> None:
    """A second copy of the pattern would let two parsers drift apart."""
    canonical = _PACKAGE / "wikilinks.py"
    assert _DECLARATION_RE.search(canonical.read_text(encoding="utf-8"))
    elsewhere = [
        p.relative_to(_PACKAGE).as_posix()
        for p in sorted(_PACKAGE.rglob("*.py"))
        if p != canonical and _DECLARATION_RE.search(p.read_text(encoding="utf-8"))
    ]
    assert elsewhere == []


def test_canonical_parser_imports_nothing_from_the_package() -> None:
    """It stays a leaf so every consumer can import it without a cycle."""
    source = (_PACKAGE / "wikilinks.py").read_text(encoding="utf-8")
    assert not re.search(r"^\s*(?:from|import)\s+llmwiki", source, re.MULTILINE)


# ─── merge aliases (#139) ─────────────────────────────────────────────────


def test_parse_page_aliases_accepts_merge_bullets() -> None:  # @regression
    """# @layer: unit  # @spec: 139-candidates-merge-aliases"""
    body = (
        "## Aliases\n\n"
        "- Tailnet — merged 2026-08-27 (2 source pages)\n"
        "- [[OldName]]\n"
    )
    assert parse_page_aliases(body) == ["Tailnet", "OldName"]


def test_build_page_alias_map_maps_merged_names_to_survivor() -> None:  # @regression
    """# @layer: unit  # @spec: 139-candidates-merge-aliases"""
    bodies = {
        "Tailscale": (
            "## Connections\n- [[s1]]\n\n"
            "## Aliases\n\n- Tailnet — merged 2026-08-27 (2 source pages)\n"
        ),
    }
    assert build_page_alias_map(bodies) == {"Tailnet": "Tailscale"}


def test_resolve_wikilink_target_follows_alias_map() -> None:  # @regression
    """# @layer: unit  # @spec: 139-candidates-merge-aliases"""
    slugs = {"Tailscale"}
    alias_map = {"Tailnet": "Tailscale"}
    assert resolve_wikilink_target("Tailnet", slugs, alias_map) == "Tailscale"
    assert resolve_wikilink_target("Tailnet#history", slugs, alias_map) == "Tailscale"
    assert resolve_wikilink_target("Missing", slugs, alias_map) is None


def test_backlinks_attribute_alias_links_to_canonical() -> None:  # @regression
    """# @layer: unit  # @spec: 139-candidates-merge-aliases"""
    pages = {
        "Tailscale": {
            "path": Path("entities/Tailscale.md"),
            "meta": {"title": "Tailscale"},
            "body": "## Aliases\n\n- Tailnet — merged 2026-08-27\n",
            "text": "",
        },
        "older": {
            "path": Path("sources/older.md"),
            "meta": {"title": "Older"},
            "body": "Historical note on [[Tailnet]].\n",
            "text": "",
        },
    }
    rev = build_reverse_index(pages)
    assert list(rev) == ["Tailscale"]
    assert rev["Tailscale"][0].slug == "older"


def test_references_attribute_alias_links_to_canonical() -> None:  # @regression
    """# @layer: unit  # @spec: 139-candidates-merge-aliases"""
    pages = {
        "entities/Tailscale.md": {
            "meta": {},
            "body": "## Aliases\n\n- Tailnet — merged 2026-08-27\n",
        },
        "sources/older.md": {
            "meta": {},
            "body": "Historical note on [[Tailnet]].\n",
        },
    }
    idx = build_index(pages)
    assert "Tailscale" in idx
    assert idx["Tailscale"][0].source == "sources/older.md"
    assert "Tailnet" not in idx


# ─── rewrite_wikilinks (#282) ──────────────────────────────────────────


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("see [[Junk]] here", "see Junk here"),
        ("see [[junk]] here", "see junk here"),
        ("see [[Junk|the junk]] here", "see the junk here"),
        ("see [[Junk#Usage]] here", "see Junk here"),
        ("see [[Junk#Usage|how]] here", "see how here"),
        ("keep [[Other]] and [[Junk]]", "keep [[Other]] and Junk"),
    ],
    ids=["bare", "case-variant", "label", "anchor", "anchor-label", "untouched-peer"],
)
def test_rewrite_wikilinks_unlinks_to_visible_text(text: str, expected: str) -> None:
    """# @layer: unit  # @spec: 282-discarded-topic-links"""
    new, counts = rewrite_wikilinks(text, {norm_page_key("Junk"): None})
    assert new == expected
    assert counts == {"junk": 1}


def test_rewrite_wikilinks_redirect_keeps_display_text() -> None:
    """# @layer: unit  # @spec: 282-discarded-topic-links"""
    new, counts = rewrite_wikilinks(
        "[[Junk]], [[junk|the junk]], [[Other]]", {"junk": "Target"}
    )
    assert new == "[[Target|Junk]], [[Target|the junk]], [[Other]]"
    assert counts == {"junk": 2}


def test_rewrite_wikilinks_never_links_a_page_to_itself() -> None:
    """# @layer: unit  # @spec: 282-discarded-topic-links"""
    new, counts = rewrite_wikilinks(
        "- [[Junk]] and [[junk|the junk]]", {"junk": "Target"}, self_stem="tar-get",
    )
    assert new == "- Junk and the junk"
    assert counts == {"junk": 2}


def test_rewrite_wikilinks_still_retargets_on_other_pages() -> None:
    """# @layer: unit  # @spec: 282-discarded-topic-links"""
    new, _ = rewrite_wikilinks("[[Junk]]", {"junk": "Target"}, self_stem="Elsewhere")
    assert new == "[[Target|Junk]]"


def test_alias_bullet_round_trips_a_name_with_an_em_dash() -> None:
    """The writer and the reader of ``## Aliases`` agree. # @layer: unit  # @spec: 282-discarded-topic-links"""
    bullet = format_alias_bullet("A — B", "merged 2026-08-27 (2 source pages)")
    body = f"## Aliases\n\n{bullet}\n"
    assert parse_page_aliases(body) == ["A — B"]
    assert build_page_alias_map({"Survivor": body}) == {"A — B": "Survivor"}


def test_format_alias_bullet_refuses_a_note_that_breaks_the_round_trip() -> None:
    """# @layer: unit  # @spec: 282-discarded-topic-links"""
    with pytest.raises(ValueError, match="alias note"):
        format_alias_bullet("Name", "merged — 2026-08-27")


def test_rewrite_wikilinks_keeps_distinct_non_latin_names_apart() -> None:
    """A non-Latin name must not fold onto every other non-Latin name."""
    new, _ = rewrite_wikilinks("[[Мусор]] и [[Проект]]", {norm_page_key("Мусор"): None})
    assert new == "Мусор и [[Проект]]"


def test_alias_lookup_folds_case_and_punctuation() -> None:
    """# @layer: unit  # @spec: 282-discarded-topic-links"""
    alias_map = build_page_alias_map({"Target": "## Aliases\n\n- Old-Name — redirected\n"})
    assert resolve_wikilink_target("old name", {"Target"}, alias_map) == "Target"
    assert resolve_wikilink_target("Old-Name#x", {"Target"}, alias_map) == "Target"
    assert resolve_wikilink_target("Other", {"Target"}, alias_map) is None
