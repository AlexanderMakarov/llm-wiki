"""Unit tests for llmwiki.search (#197 package extract)."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from llmwiki.search import (
    CorpusWalkStats,
    ExtractQuery,
    ScannedPage,
    extract_snippet,
    iter_scanned_pages,
    match_page,
    rank_of,
    scan_corpus,
    score_extract,
    search_extract,
    search_match,
)
from llmwiki.search import corpus as corpus_mod


def _page(
    rel: str,
    text: str,
    *,
    title: str = "",
    meta: dict | None = None,
    path: Path | None = None,
) -> ScannedPage:
    meta = dict(meta or {})
    if title and "title" not in meta:
        meta["title"] = title
    title_val = title or str(meta.get("title", "") or "")
    p = path or Path(rel)
    return ScannedPage(
        rel_path=rel,
        path=p,
        text=text,
        text_lower=text.lower(),
        title=title_val,
        meta=meta,
        size=len(text.encode()),
        is_raw=rel.startswith("raw/"),
    )


# ── scoring arithmetic ──────────────────────────────────────────────────


def test_score_extract_body_phrase_and_tokens_normalised():
    """Body +50 phrase +10/token, ÷ log2(max(len, 256))."""
    body = "alpha beta gamma " * 20  # len > 256
    page = _page("wiki/a.md", body)
    query = ExtractQuery.parse("alpha beta")
    raw = 50 + 10 + 10  # phrase + each token
    expected = raw / math.log2(len(body))
    assert score_extract(page, query) == pytest.approx(expected)


def test_score_extract_title_bonus_unnormalised():
    page = _page("wiki/Ferry.md", "unrelated body text here", title="Ferry Line")
    query = ExtractQuery.parse("Ferry")
    # title phrase +100, token +20; body has no "ferry"
    assert score_extract(page, query) == pytest.approx(120.0)


def test_score_extract_short_page_uses_256_floor():
    page = _page("wiki/x.md", "cat")  # len 3
    query = ExtractQuery.parse("cat")
    expected = 50 / math.log2(256)  # phrase only; token "cat" also in body → +10
    # phrase + token both fire
    expected = (50 + 10) / math.log2(256)
    assert score_extract(page, query) == pytest.approx(expected)


def test_extract_query_parse_tokenises_once():
    q = ExtractQuery.parse("Hello, World!")
    assert q.raw == "Hello, World!"
    assert q.lower == "hello, world!"
    assert q.tokens == ["hello", "world"]


# ── match_page ──────────────────────────────────────────────────────────


def test_match_page_name_and_body():
    page = _page(
        "wiki/entities/Lighthouse.md",
        "---\ntitle: Lighthouse\ntype: entity\n---\nbeam of light\n",
        title="Lighthouse",
        meta={"title": "Lighthouse", "type": "entity"},
    )
    hit = match_page(page, "light")
    assert hit is not None
    assert hit.name_match is True  # in title
    assert any("beam of light" in t for _, t in hit.lines)


def test_match_and_extract_share_centred_snippet_window():
    """Term and phrase modes both use extract_snippet (~400 chars centred)."""
    prefix = "tags: [" + ", ".join(f"tag-{i:03d}" for i in range(40)) + ", "
    assert len(prefix) > 200
    line = prefix + "openspec-evaluation, trailing-tag]"
    preview = extract_snippet(line, ["openspec"])
    assert "openspec" in preview.lower()
    assert preview.startswith("…")
    assert "openspec-evaluation" in preview
    # Same helper match_page uses for line text.
    page = _page("wiki/x.md", line + "\n", title="X")
    hit = match_page(page, "openspec")
    assert hit is not None
    assert hit.lines[0][1] == preview


def test_match_page_kind_filter():
    page = _page(
        "wiki/x.md",
        "hello",
        title="Hello",
        meta={"type": "entity"},
    )
    assert match_page(page, "hello", kind="concept") is None
    assert match_page(page, "hello", kind="entity") is not None


# ── corpus caps ─────────────────────────────────────────────────────────


def test_scan_corpus_skips_cold_storage(tmp_path: Path):
    wiki = tmp_path / "wiki"
    (wiki / "live.md").parent.mkdir(parents=True)
    (wiki / "live.md").write_text("---\ntitle: Live\n---\nok\n", encoding="utf-8")
    archived = wiki / "archive" / "gone.md"
    archived.parent.mkdir(parents=True)
    archived.write_text("---\ntitle: Gone\n---\nsecret\n", encoding="utf-8")
    scan = scan_corpus([wiki], content_root=tmp_path, cold_storage_root=wiki)
    paths = {p.rel_path for p in scan.pages}
    assert paths == {"wiki/live.md"}
    assert scan.skipped_oversize == 0


def test_scan_corpus_per_file_cap_and_budget(tmp_path: Path):
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "small.md").write_text("findme\n", encoding="utf-8")
    (wiki / "huge.md").write_text("x" * 1000, encoding="utf-8")
    scan = scan_corpus(
        [wiki],
        content_root=tmp_path,
        cold_storage_root=wiki,
        per_file_cap=100,
        aggregate_budget=10_000,
    )
    assert scan.skipped_oversize == 1
    assert len(scan.pages) == 1
    assert scan.pages[0].rel_path == "wiki/small.md"


def test_scan_corpus_budget_exhausted(tmp_path: Path):
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "a.md").write_text("aaaa\n", encoding="utf-8")
    (wiki / "b.md").write_text("bbbb\n", encoding="utf-8")
    scan = scan_corpus(
        [wiki],
        content_root=tmp_path,
        cold_storage_root=wiki,
        per_file_cap=100,
        aggregate_budget=3,  # too small to read either full file under read rules
    )
    # Files of size 5 with budget 3 → skipped, budget_exhausted set
    assert scan.budget_exhausted is True
    assert scan.pages == []


# ── extract tiebreak ────────────────────────────────────────────────────


def test_search_extract_tiebreak_orders_by_rel_path():
    """Equal scores must sort by rel_path, not insertion / filesystem order."""
    # Same body length + same token hits → identical scores
    body = "token " * 40
    pages = [
        _page("wiki/z-last.md", body, title="Z"),
        _page("wiki/a-first.md", body, title="A"),
        _page("wiki/m-mid.md", body, title="M"),
    ]
    hits = search_extract(pages, ["token"], max_pages=10)["token"]
    assert [h.rel_path for h in hits] == [
        "wiki/a-first.md",
        "wiki/m-mid.md",
        "wiki/z-last.md",
    ]
    assert hits[0].score == hits[1].score == hits[2].score


def test_search_extract_tiebreak_stable_under_shuffle():
    body = "sharedphrase here"
    pages_a = [
        _page("wiki/b.md", body, title="B"),
        _page("wiki/a.md", body, title="A"),
    ]
    pages_b = list(reversed(pages_a))
    order_a = [h.rel_path for h in search_extract(pages_a, ["sharedphrase"])["sharedphrase"]]
    order_b = [h.rel_path for h in search_extract(pages_b, ["sharedphrase"])["sharedphrase"]]
    assert order_a == order_b == ["wiki/a.md", "wiki/b.md"]


# ── multi-query isolation ───────────────────────────────────────────────


def test_search_extract_multi_query_matches_solo():
    pages = [
        _page("wiki/alpha.md", "alpha content", title="Alpha"),
        _page("wiki/beta.md", "beta content", title="Beta"),
        _page("wiki/both.md", "alpha and beta", title="Both"),
    ]
    together = search_extract(pages, ["alpha", "beta"], max_pages=5)
    solo_a = search_extract(pages, ["alpha"], max_pages=5)["alpha"]
    solo_b = search_extract(pages, ["beta"], max_pages=5)["beta"]
    assert [(h.rel_path, h.score) for h in together["alpha"]] == [
        (h.rel_path, h.score) for h in solo_a
    ]
    assert [(h.rel_path, h.score) for h in together["beta"]] == [
        (h.rel_path, h.score) for h in solo_b
    ]


def test_search_match_multi_query_matches_solo():
    pages = [
        _page("wiki/a.md", "---\ntitle: Apple\n---\napple pie\n", title="Apple"),
        _page("wiki/b.md", "---\ntitle: Berry\n---\nberry jam\n", title="Berry"),
        _page("wiki/c.md", "---\ntitle: Mixed\n---\napple and berry\n", title="Mixed"),
    ]
    together = search_match(pages, ["apple", "berry"])
    solo_a = search_match(pages, ["apple"])["apple"]
    solo_b = search_match(pages, ["berry"])["berry"]
    assert together["apple"].pages == solo_a.pages
    assert together["apple"].truncated == solo_a.truncated
    assert together["berry"].pages == solo_b.pages
    assert together["berry"].truncated == solo_b.truncated


def test_search_match_multi_query_saturation_isolation():
    """One query filling its caps must not starve another."""
    pages = [
        _page(f"wiki/p{i:03d}.md", f"needle line {i}\n", title=f"P{i}")
        for i in range(10)
    ]
    # Also pages that only match "other"
    pages.append(_page("wiki/other.md", "other term here\n", title="Other"))
    together = search_match(
        pages, ["needle", "other"], page_cap=3, hit_cap=3
    )
    solo_other = search_match(pages, ["other"], page_cap=3, hit_cap=3)["other"]
    assert together["other"].pages == solo_other.pages
    assert len(together["needle"].pages) <= 3
    assert together["needle"].truncated is True


# ── rank_of ↔ engine ────────────────────────────────────────────────────


def test_rank_of_agrees_with_engine_order():
    pages = [
        _page("wiki/low.md", "x", title="Low"),
        _page("wiki/mid.md", "target word here", title="Mid"),
        _page("wiki/high.md", "target", title="Target Exact"),
    ]
    query = "target"
    hits = search_extract(pages, [query], max_pages=10)[query]
    ranks = rank_of(pages, [query], {query: "wiki/mid.md"})
    # mid's position in engine results (1-based)
    engine_rank = next(
        i for i, h in enumerate(hits, start=1) if h.rel_path == "wiki/mid.md"
    )
    assert ranks[query] == engine_rank


def test_rank_of_none_when_target_unscored():
    pages = [_page("wiki/a.md", "hello", title="Hello")]
    assert rank_of(pages, ["zzz"], {"zzz": "wiki/a.md"})["zzz"] is None


def test_match_streaming_stops_disk_walk_when_saturated(tmp_path: Path, monkeypatch):
    """Match caps must stop opening further files (N1 / pre-#197 I/O)."""
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    # Deterministic walk: matching file first, then many unrelated pages.
    files = [wiki / "00-needle.md"] + [wiki / f"{i:02d}-later.md" for i in range(1, 31)]
    files[0].write_text(
        "---\ntitle: Needle Page\n---\n"
        + "\n".join(f"needle line {i}" for i in range(20)),
        encoding="utf-8",
    )
    for path in files[1:]:
        path.write_text("---\ntitle: Later\n---\nunrelated\n", encoding="utf-8")

    monkeypatch.setattr(
        corpus_mod,
        "iter_scan_files",
        lambda roots, cold_storage_root=None: iter(files),
    )

    reads: list[Path] = []
    real_read = corpus_mod.read_capped

    def counting_read(path, **kwargs):
        reads.append(path)
        return real_read(path, **kwargs)

    monkeypatch.setattr(corpus_mod, "read_capped", counting_read)
    stats = CorpusWalkStats()
    result = search_match(
        iter_scanned_pages(
            [wiki],
            content_root=tmp_path,
            cold_storage_root=wiki,
            stats=stats,
        ),
        ["needle"],
        page_cap=1,
        hit_cap=1,
    )["needle"]
    assert result.pages
    assert result.pages[0].name_match is True
    assert len(reads) == 1, f"expected early stop, opened {len(reads)} files"
    assert stats.budget_exhausted is False
