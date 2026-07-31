"""Tests for ``llmwiki/references.py`` + CLI + stale_reference_detection rule.

Covers:
* ``_extract_dated_claims``: every regex branch + unicode + no matches.
* ``_parse_date``: date / datetime / ISO / bad input.
* ``build_index``: target resolution, broken links, self-link, unicode,
  no-body / empty-body, multiple links per page.
* ``find_references_to``: empty hits, matching hits.
* ``find_stale_references``: needs all three (dated claim + older living
  page + newer target); missing any produces empty; unparseable dates
  skipped; ``wiki/sources/`` and ``type: source`` pages never stale (#87).
* ``format_references_table``: empty + sort order.
* Lint rule wired + fires on a synthetic corpus.
* CLI ``llmwiki references`` end-to-end.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

from llmwiki import references as r
from llmwiki.lint import REGISTRY, rules  # noqa: F401

REPO_ROOT = Path(__file__).resolve().parents[1]


def _run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "llmwiki", *args],
        capture_output=True,
        text=True,
        check=False,
    )


# ─── _extract_dated_claims ────────────────────────────────────────────────


@pytest.mark.parametrize(
    "body,expect_hit",
    [
        ("Latency is <100ms as of 2026-03-15.", True),
        ("as of 2026-03 the cache ratio was 72%.", True),
        ("since v4.6 the default is cached", True),
        ("Since 2026 we ship ARM builds", True),
        ("(last checked 2026-02-10) still broken", True),
        ("current as of 2026-04-19", True),
        ("works through 2026", True),
        ("Plain prose without time marker.", False),
        ("", False),
        ("as of something undefined", False),
        ("as of march 2026", True),
        ("as of September 2026", True),
    ],
)
def test_extract_dated_claims(body, expect_hit):
    hits = r._extract_dated_claims(body)
    if expect_hit:
        assert len(hits) >= 1
    else:
        assert hits == []


def test_extract_dated_claims_multiple_hits():
    body = "as of 2026-01-01 metrics were X. Since v4.6 they're Y."
    hits = r._extract_dated_claims(body)
    assert len(hits) == 2


def test_extract_dated_claims_includes_context():
    body = (
        "Some prior context here. Latency of [[RAG]] is 100ms as of 2026-03-15. "
        "Some trailing context."
    )
    hits = r._extract_dated_claims(body)
    assert hits
    assert "RAG" in hits[0]


# ─── _parse_date ─────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "value,expected",
    [
        (date(2026, 4, 19), date(2026, 4, 19)),
        ("2026-04-19", date(2026, 4, 19)),
        ("2026-04-19T12:00:00Z", date(2026, 4, 19)),
        ("2026-04-19T12:00:00", date(2026, 4, 19)),
        ("not-a-date", None),
        ("", None),
        (None, None),
        (0, None),
        ([], None),
    ],
)
def test_parse_date_boundary_inputs(value, expected):
    assert r._parse_date(value) == expected


# ─── build_index ─────────────────────────────────────────────────────────


def _p(rel: str, *, body: str = "", meta: dict = None) -> tuple[str, dict]:
    return rel, {"meta": meta or {}, "body": body}


def test_build_index_resolves_targets_to_rel_paths():
    pages = dict([
        _p("entities/RAG.md"),
        _p("sources/a.md", body="We use [[RAG]] heavily."),
    ])
    idx = r.build_index(pages)
    assert "RAG" in idx
    refs = idx["RAG"]
    assert len(refs) == 1
    assert refs[0].source == "sources/a.md"
    assert refs[0].target == "RAG"
    assert refs[0].target_rel == "entities/RAG.md"


def test_build_index_broken_link_has_none_target_rel():
    pages = dict([
        _p("sources/a.md", body="[[Nonexistent]] page."),
    ])
    idx = r.build_index(pages)
    assert "Nonexistent" in idx
    assert idx["Nonexistent"][0].target_rel is None


def test_build_index_multiple_links_same_page():
    pages = dict([
        _p("entities/RAG.md"),
        _p("entities/OpenAI.md"),
        _p("sources/a.md", body="[[RAG]] and [[OpenAI]] both."),
    ])
    idx = r.build_index(pages)
    assert set(idx.keys()) == {"RAG", "OpenAI"}


def test_build_index_ignores_empty_bodies():
    pages = dict([
        _p("entities/X.md"),
        _p("sources/a.md", body=""),
    ])
    idx = r.build_index(pages)
    assert idx == {}


def test_build_index_dedupes_within_source():
    pages = dict([
        _p("entities/RAG.md"),
        _p("sources/a.md", body="[[RAG]] and [[RAG]] again."),
    ])
    idx = r.build_index(pages)
    # Only one Reference per (source, target).
    assert len(idx["RAG"]) == 1


def test_build_index_preserves_dated_claims():
    pages = dict([
        _p("entities/RAG.md"),
        _p("sources/a.md", body="[[RAG]] is <100ms as of 2026-03-15."),
    ])
    idx = r.build_index(pages)
    assert idx["RAG"][0].dated_claims != ()


def test_build_index_handles_anchor_suffix():
    """[[RAG#pricing]] should resolve to RAG, anchor dropped."""
    pages = dict([
        _p("entities/RAG.md"),
        _p("sources/a.md", body="See [[RAG#pricing]] for details."),
    ])
    idx = r.build_index(pages)
    assert "RAG" in idx


# ─── find_references_to ──────────────────────────────────────────────────


def test_find_references_to_empty_when_no_links():
    pages = dict([_p("entities/X.md")])
    assert r.find_references_to("X", pages) == []


def test_find_references_to_returns_all_referrers():
    pages = dict([
        _p("entities/RAG.md"),
        _p("sources/a.md", body="[[RAG]]"),
        _p("sources/b.md", body="[[RAG]]"),
    ])
    refs = r.find_references_to("RAG", pages)
    assert {ref.source for ref in refs} == {"sources/a.md", "sources/b.md"}


# ─── find_stale_references ───────────────────────────────────────────────


def test_stale_detected_when_all_conditions_met():
    pages = dict([
        _p(
            "entities/RAG.md",
            meta={"last_updated": "2026-04-01"},
        ),
        _p(
            "concepts/Latency.md",
            meta={"type": "concept", "last_updated": "2026-01-01"},
            body="[[RAG]] latency is <100ms as of 2026-01-01.",
        ),
    ])
    stale = r.find_stale_references(pages)
    assert len(stale) == 1
    assert stale[0].source == "concepts/Latency.md"
    assert stale[0].target == "RAG"


def test_no_stale_when_referrer_is_source_page():
    """wiki/sources/ pages are dated session records — not re-verifiable (#87)."""
    pages = dict([
        _p("entities/RAG.md", meta={"last_updated": "2026-04-01"}),
        _p(
            "sources/a.md",
            meta={"type": "source", "last_updated": "2026-01-01"},
            body="[[RAG]] latency is <100ms as of 2026-01-01.",
        ),
    ])
    assert r.find_stale_references(pages) == []


def test_no_stale_when_frontmatter_type_is_source():
    """type: source skips even outside sources/ (#87)."""
    pages = dict([
        _p("entities/RAG.md", meta={"last_updated": "2026-04-01"}),
        _p(
            "archive/old-session.md",
            meta={"type": "source", "last_updated": "2026-01-01"},
            body="[[RAG]] latency is <100ms as of 2026-01-01.",
        ),
    ])
    assert r.find_stale_references(pages) == []


def test_no_stale_when_source_is_newer():
    pages = dict([
        _p("entities/RAG.md", meta={"last_updated": "2026-01-01"}),
        _p(
            "concepts/Latency.md",
            meta={"last_updated": "2026-04-01"},
            body="[[RAG]] as of 2026-04-01.",
        ),
    ])
    assert r.find_stale_references(pages) == []


def test_no_stale_without_dated_claim():
    pages = dict([
        _p("entities/RAG.md", meta={"last_updated": "2026-04-01"}),
        _p(
            "concepts/Latency.md",
            meta={"last_updated": "2026-01-01"},
            body="[[RAG]] is interesting.",  # no dated claim
        ),
    ])
    assert r.find_stale_references(pages) == []


def test_no_stale_without_target_last_updated():
    pages = dict([
        _p("entities/RAG.md"),  # no last_updated
        _p(
            "concepts/Latency.md",
            meta={"last_updated": "2026-01-01"},
            body="[[RAG]] as of 2026-01-01",
        ),
    ])
    assert r.find_stale_references(pages) == []


def test_no_stale_without_source_last_updated():
    pages = dict([
        _p("entities/RAG.md", meta={"last_updated": "2026-04-01"}),
        _p(
            "concepts/Latency.md",
            meta={},  # no last_updated
            body="[[RAG]] as of 2026-01-01",
        ),
    ])
    assert r.find_stale_references(pages) == []


def test_malformed_date_tolerated():
    pages = dict([
        _p("entities/RAG.md", meta={"last_updated": "garbage"}),
        _p(
            "concepts/Latency.md",
            meta={"last_updated": "2026-01-01"},
            body="[[RAG]] as of 2026-01-01",
        ),
    ])
    # Target date unparseable → skip the whole target.
    assert r.find_stale_references(pages) == []


def test_broken_link_never_stale():
    pages = dict([
        _p(
            "concepts/Latency.md",
            meta={"last_updated": "2026-01-01"},
            body="[[Nonexistent]] as of 2026-01-01",
        ),
    ])
    # Broken link → no target rel → skip.
    assert r.find_stale_references(pages) == []


def test_stale_populates_excerpt():
    pages = dict([
        _p("entities/RAG.md", meta={"last_updated": "2026-04-01"}),
        _p(
            "concepts/Latency.md",
            meta={"last_updated": "2026-01-01"},
            body="Context. [[RAG]] latency <100ms as of 2026-01-01. Trailing.",
        ),
    ])
    stale = r.find_stale_references(pages)
    assert len(stale) == 1
    assert "2026-01-01" in stale[0].dated_claim


# ─── format_references_table ─────────────────────────────────────────────


def test_format_references_table_empty():
    assert r.format_references_table([]) == "No references found."


def test_format_references_table_sorted():
    refs = [
        r.Reference(source="sources/zzz.md", target="X", target_rel=None),
        r.Reference(source="sources/aaa.md", target="X", target_rel=None),
    ]
    out = r.format_references_table(refs)
    lines = out.splitlines()
    # aaa row appears before zzz row
    aaa_idx = next(i for i, ln in enumerate(lines) if "aaa" in ln)
    zzz_idx = next(i for i, ln in enumerate(lines) if "zzz" in ln)
    assert aaa_idx < zzz_idx


# ─── Lint rule wired ─────────────────────────────────────────────────────


def test_lint_rule_registered():
    assert "stale_reference_detection" in REGISTRY


def test_lint_rule_fires_on_stale_pair():

    rule = REGISTRY["stale_reference_detection"]()
    pages = dict([
        _p("entities/RAG.md", meta={"last_updated": "2026-04-01"}),
        _p(
            "concepts/Latency.md",
            meta={"last_updated": "2026-01-01"},
            body="[[RAG]] is <100ms as of 2026-01-01.",
        ),
    ])
    issues = rule.run(pages)
    assert len(issues) == 1
    assert "RAG" in issues[0]["message"]
    assert "2026-01-01" in issues[0]["message"]


def test_lint_rule_silent_on_source_page():
    """Source-page residue must not become lint noise (#87)."""
    rule = REGISTRY["stale_reference_detection"]()
    pages = dict([
        _p("entities/RAG.md", meta={"last_updated": "2026-04-01"}),
        _p(
            "sources/a.md",
            meta={"type": "source", "last_updated": "2026-01-01"},
            body="[[RAG]] is <100ms as of 2026-01-01.",
        ),
    ])
    assert rule.run(pages) == []


def test_lint_rule_silent_on_fresh_pair():

    rule = REGISTRY["stale_reference_detection"]()
    pages = dict([
        _p("entities/RAG.md", meta={"last_updated": "2026-01-01"}),
        _p(
            "concepts/Latency.md",
            meta={"last_updated": "2026-04-01"},
            body="[[RAG]] as of 2026-04-01",
        ),
    ])
    assert rule.run(pages) == []


# ─── CLI ─────────────────────────────────────────────────────────────────


@pytest.mark.skip(reason="references CLI subcommand removed")
def test_cli_references_help():
    pass


@pytest.mark.skip(reason="references CLI subcommand removed")
def test_cli_references_prints_referrers(tmp_path):
    pass


@pytest.mark.skip(reason="references CLI subcommand removed")
def test_cli_references_empty_result(tmp_path):
    pass


@pytest.mark.skip(reason="references CLI subcommand removed")
def test_cli_references_missing_wiki_dir_errors(tmp_path):
    pass
