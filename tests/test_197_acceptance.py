"""Whole-feature acceptance gate for #197 search quality (Slice 4 / R5–R6).

# @layer: integration
# @spec: 197-search-quality-eval
# @regression

Reads only: prepared fixtures under ``tests/fixtures/`` and the committed
``demo/`` vault. Writes nothing — required by CI's
``git diff --exit-code`` after pytest.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import pytest

from llmwiki.search import (
    scan_corpus,
    search_extract,
    search_match,
)
from llmwiki.search.evaluate import (
    rank_of,
    titled_wiki_pages,
    unique_title_queries,
)

REPO = Path(__file__).resolve().parent.parent
DEMO = REPO / "demo"
TERMS_FIXTURE = REPO / "tests" / "fixtures" / "demo_search_terms.json"
BASELINE_FIXTURE = REPO / "tests" / "fixtures" / "demo_search_baseline.json"


@pytest.fixture(scope="module")
def demo_scan():
    """Wiki + raw/sessions scan of the committed demo vault."""
    root = DEMO.resolve()
    wiki = root / "wiki"
    sessions = root / "raw" / "sessions"
    assert wiki.is_dir() and sessions.is_dir(), "committed demo/ vault required"
    return scan_corpus(
        [wiki, sessions],
        content_root=root,
        cold_storage_root=wiki,
    )


@pytest.fixture(scope="module")
def terms_fixture() -> dict:
    return json.loads(TERMS_FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def baseline_fixture() -> dict:
    return json.loads(BASELINE_FIXTURE.read_text(encoding="utf-8"))


def _round6(value: float) -> float:
    return round(value, 6)


def _mrr_and_rank1(ranks: list[int]) -> tuple[float, float]:
    assert ranks, "no ranks to aggregate"
    mrr = sum(1.0 / r for r in ranks) / len(ranks)
    rank1 = sum(1 for r in ranks if r == 1) / len(ranks)
    return _round6(mrr), _round6(rank1)


def _match_title_ranks(wiki_pages) -> dict[str, int]:
    """1-based match-mode rank of each titled page for its own title."""
    titled = titled_wiki_pages(wiki_pages)
    by_title: dict[str, list] = defaultdict(list)
    for page in titled:
        by_title[page.title].append(page)
    unique_titles = sorted(by_title)
    # High caps so rank is not truncated before the target.
    results = search_match(
        wiki_pages, unique_titles, page_cap=10_000, hit_cap=10_000
    )
    ranks: dict[str, int] = {}
    for title, pages in by_title.items():
        order = [p.rel_path for p in results[title].pages]
        for page in pages:
            assert page.rel_path in order, (
                f"titled page {page.rel_path!r} not returned for title {title!r}"
            )
            ranks[page.rel_path] = order.index(page.rel_path) + 1
    return ranks


def test_every_present_entry_is_found(demo_scan, terms_fixture):
    """R5/R6: present terms via match mode, phrases via extract mode."""
    pages = demo_scan.pages
    for row in terms_fixture["present"]:
        value = row["value"]
        kind = row["kind"]
        if kind == "term":
            hits = search_match(pages, [value])[value].pages
            assert hits, f"present term {value!r} ({row['session']}/{row['placement']}) returned nothing"
        elif kind == "phrase":
            hits = search_extract(pages, [value])[value]
            assert hits, (
                f"present phrase {value!r} ({row['session']}/{row['placement']}) returned nothing"
            )
        else:
            pytest.fail(f"unknown kind {kind!r} for present entry {row}")


def test_no_absent_entry_returns_results(demo_scan, terms_fixture):
    """R6: absent terms and phrases return nothing in either mode."""
    pages = demo_scan.pages
    for row in terms_fixture["absent"]:
        value = row["value"]
        match_hits = search_match(pages, [value])[value].pages
        extract_hits = search_extract(pages, [value])[value]
        assert not match_hits, f"absent {value!r} returned match hits"
        assert not extract_hits, f"absent {value!r} returned extract hits"


def test_every_titled_demo_page_findable_by_title(demo_scan):
    """R6: every titled wiki page is returned for its own title (extract)."""
    wiki_pages = [p for p in demo_scan.pages if not p.is_raw]
    titled = titled_wiki_pages(wiki_pages)
    assert titled, "demo vault has no titled wiki pages"
    queries, targets = unique_title_queries(titled)
    ranks = rank_of(wiki_pages, queries, targets)
    missing = [targets[raw] for raw, rank in ranks.items() if rank is None]
    assert not missing, f"titled pages not findable by title: {missing[:10]}"


def test_mrr_and_rank1_match_baseline(demo_scan, baseline_fixture):
    """R6: exact MRR / rank-1 share vs recorded baseline (no tolerance)."""
    wiki_pages = [p for p in demo_scan.pages if not p.is_raw]
    titled = titled_wiki_pages(wiki_pages)
    queries, targets = unique_title_queries(titled)
    extract_ranks = rank_of(wiki_pages, queries, targets)
    extract_list = [r for r in extract_ranks.values() if r is not None]
    assert len(extract_list) == len(extract_ranks)
    mrr_e, r1_e = _mrr_and_rank1(extract_list)

    match_ranks = _match_title_ranks(wiki_pages)
    mrr_m, r1_m = _mrr_and_rank1(list(match_ranks.values()))

    assert mrr_e == baseline_fixture["mrr_extract"]
    assert mrr_m == baseline_fixture["mrr_match"]
    assert r1_e == baseline_fixture["rank1_extract"]
    assert r1_m == baseline_fixture["rank1_match"]


def test_report_survival_by_placement_and_adapter(demo_scan, terms_fixture, capsys):
    """R5: report survival × placement × adapter; never assert the share."""
    wiki_blob = "\n".join(
        p.text_lower for p in demo_scan.pages if not p.is_raw
    )
    # (placement, adapter) -> [survived bool, ...]
    buckets: dict[tuple[str, str], list[bool]] = defaultdict(list)
    for row in terms_fixture["present"]:
        survived = row["value"].lower() in wiki_blob
        buckets[(row["placement"], row["adapter"])].append(survived)

    lines = ["survival share by placement × adapter (informational):"]
    for (placement, adapter), flags in sorted(buckets.items()):
        n = len(flags)
        k = sum(flags)
        pct = round(100 * k / n) if n else 0
        lines.append(f"  {placement:<10} {adapter:<12} {k}/{n} ({pct}%)")
    overall = [f for flags in buckets.values() for f in flags]
    if overall:
        ok = sum(overall)
        lines.append(
            f"  overall              {ok}/{len(overall)} "
            f"({round(100 * ok / len(overall))}%)"
        )
    report = "\n".join(lines)
    print(report)
    # Touch capsys so the print is captured; no assertion on the share.
    assert "survival share" in capsys.readouterr().out
