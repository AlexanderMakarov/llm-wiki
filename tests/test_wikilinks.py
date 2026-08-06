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
from pathlib import Path

import pytest

from llmwiki.backlinks import build_reverse_index
from llmwiki.lint.rules.orphan_detection import OrphanDetection
from llmwiki.references import build_index
from llmwiki.wikilinks import WIKILINK_RE, wikilink_targets

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
