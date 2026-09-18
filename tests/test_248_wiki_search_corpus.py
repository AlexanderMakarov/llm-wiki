"""The build emits the wiki corpus `wiki_search` match mode scans (#248 FR7).

Slice 5 is the build half of FR7: it ships the data the palette's WIKI result
group will search, and nothing user-visible changes yet. Two properties carry
the whole slice — the payload must cover *exactly* what MCP covers, and it
must stay off the eager path that every page view pays for.
"""

from __future__ import annotations

import json
from pathlib import Path

from llmwiki.build import (
    WIKI_CORPUS_MANIFEST_KEY,
    WIKI_CORPUS_REL,
    WIKI_CORPUS_STATUS_KEY,
    build_search_index,
    build_wiki_corpus_entries,
)
from llmwiki.search import corpus as corpus_mod
from llmwiki.search.corpus import (
    DEFAULT_AGGREGATE_BUDGET,
    DEFAULT_PER_FILE_CAP,
    CorpusWalkStats,
    iter_scan_files,
    scan_corpus,
)

_MARKER = "zanzibarine telemetry cadence"


def _sources(tmp_path: Path) -> tuple[list, dict]:
    """One session so `build_search_index` has a chunk to write."""
    src = tmp_path / "raw" / "sessions" / "demo" / "2026-01-01-alpha.md"
    src.parent.mkdir(parents=True, exist_ok=True)
    body = "# alpha\nsession body\n"
    src.write_text(body, encoding="utf-8")
    sources = [(src, {"project": "demo", "slug": "alpha", "date": "2026-01-01"}, body)]
    return sources, {"demo": sources}


def _page(wiki: Path, rel: str, frontmatter: str, body: str) -> Path:
    path = wiki / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{frontmatter}---\n\n{body}", encoding="utf-8")
    return path


def _wiki(tmp_path: Path) -> Path:
    """A vault wiki covering every folder whose reader URL differs."""
    wiki = tmp_path / "wiki"
    _page(wiki, "index.md", 'title: "Wiki Index"\ntype: index\n', "# Index\n")
    _page(wiki, "overview.md", 'title: "Overview"\ntype: overview\n', "# Overview\n")
    _page(wiki, "log.md", 'title: "Log"\ntype: log\n', "## [2026-01-01] build | x\n")
    _page(
        wiki,
        "sources/2026-01-01-alpha.md",
        'title: "Alpha"\ntype: source\nproject: demo\n'
        "source_file: raw/sessions/demo/2026-01-01-alpha.md\n",
        f"# Alpha\n\n{_MARKER}\n",
    )
    _page(wiki, "entities/Hazel.md", 'title: "Hazel"\ntype: entity\n', "# Hazel\n")
    # No underscore filter in `iter_scan_files` — MCP scans folder-context
    # stubs, so the site must too or the two corpora diverge.
    _page(wiki, "entities/_context.md", 'title: "Entities"\ntype: context\n', "stub\n")
    _page(wiki, "concepts/Batching.md", 'title: "Batching"\ntype: concept\n', "# B\n")
    _page(wiki, "projects/demo.md", 'title: "demo"\ntype: project\n', "# demo\n")
    _page(wiki, "candidates/Maybe.md", 'title: "Maybe"\ntype: entity\n', "# Maybe\n")
    _page(wiki, "syntheses/why.md", 'title: "Why"\ntype: synthesis\n', "# Why\n")
    _page(wiki, "categories/People.md", 'title: "People"\ntype: category\n', "# P\n")
    # Cold storage (#140): never scanned by MCP, never emitted here.
    _page(wiki, "archive/Dropped.md", 'title: "Dropped"\ntype: entity\n', "# Dropped\n")
    return wiki


def _build(tmp_path: Path, wiki: Path | None, out_name: str = "site", **kwargs) -> Path:
    sources, groups = _sources(tmp_path)
    out = tmp_path / out_name
    out.mkdir(parents=True, exist_ok=True)
    build_search_index(sources, groups, out, wiki_dir=wiki, **kwargs)
    return out


def _corpus(out: Path) -> list[dict]:
    return json.loads((out / WIKI_CORPUS_REL).read_text(encoding="utf-8"))


def _index(out: Path) -> dict:
    return json.loads((out / "search-index.json").read_text(encoding="utf-8"))


# ── the corpus is exactly MCP's ────────────────────────────────────────────


def test_emitted_corpus_equals_the_file_set_mcp_scans(tmp_path: Path):
    """Asserted against `iter_scan_files` itself, not a reimplementation.

    That function *is* the exclusion rule MCP applies (`cold_storage_root`
    withholds the wiki's own `archive/` and nothing else), so reusing it here
    is what makes drift between the two corpora impossible.
    """
    # @regression
    wiki = _wiki(tmp_path)
    out = _build(tmp_path, wiki)

    expected = {
        str(p.resolve().relative_to(wiki.parent.resolve()))
        for p in iter_scan_files([wiki], cold_storage_root=wiki)
    }
    assert {e["path"] for e in _corpus(out)} == expected


def test_context_stubs_are_in_and_archived_pages_are_out(tmp_path: Path):
    """The two ends of the exclusion rule, named so a regression reads plainly."""
    # @regression
    wiki = _wiki(tmp_path)
    paths = {e["path"] for e in _corpus(_build(tmp_path, wiki))}
    assert "wiki/entities/_context.md" in paths
    assert not any(p.startswith("wiki/archive/") for p in paths)


def test_paths_are_reported_as_mcp_reports_them(tmp_path: Path):
    """Vault-relative, so a payload path is MCP's `rel_path` verbatim."""
    wiki = _wiki(tmp_path)
    paths = {e["path"] for e in _corpus(_build(tmp_path, wiki))}
    assert "wiki/sources/2026-01-01-alpha.md" in paths


# ── entry shape ───────────────────────────────────────────────────────────


def test_entries_carry_a_full_page_that_fits_the_shared_caps(tmp_path: Path):
    """Retained pages are whole, never partial reads at a cap boundary."""
    wiki = _wiki(tmp_path)
    long_body = "\n".join(f"line {i} {_MARKER}" for i in range(5000))
    _page(wiki, "sources/2026-02-02-long.md", 'title: "Long"\ntype: source\n', long_body)
    entry = next(
        e for e in _corpus(_build(tmp_path, wiki))
        if e["path"] == "wiki/sources/2026-02-02-long.md"
    )
    assert entry["text"].count(_MARKER) == 5000
    assert entry["text"].endswith("line 4999 " + _MARKER)


def test_build_and_search_share_deterministic_cap_aware_traversal(tmp_path: Path):
    """Ordering decides which pages fit, so it is part of browser/MCP parity."""
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    # Deliberately create these out of lexical order. The first path is too
    # large, the second exactly consumes the aggregate budget, and the third
    # proves the shared walk stops at the same deterministic boundary.
    (wiki / "30-last.md").write_text("last\n", encoding="utf-8")
    (wiki / "10-too-large.md").write_text("x" * 20, encoding="utf-8")
    (wiki / "20-kept.md").write_text("kept\n", encoding="utf-8")

    assistant = scan_corpus(
        [wiki], content_root=tmp_path, cold_storage_root=wiki,
        per_file_cap=10, aggregate_budget=5,
    )
    browser_stats = CorpusWalkStats()
    browser = build_wiki_corpus_entries(
        wiki, per_file_cap=10, aggregate_budget=5, stats=browser_stats
    )

    assert [entry["path"] for entry in browser] == [p.rel_path for p in assistant.pages]
    assert [entry["path"] for entry in browser] == ["wiki/20-kept.md"]
    assert browser_stats.budget_exhausted == assistant.budget_exhausted is True
    assert browser_stats.skipped_oversize == assistant.skipped_oversize == 1


def test_more_than_the_match_cap_is_emitted_in_path_order(tmp_path: Path):
    """The match engine caps while walking, so corpus order must be stable."""
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    for i in reversed(range(250)):
        (wiki / f"{i:04d}.md").write_text("widget\n", encoding="utf-8")

    paths = [entry["path"] for entry in build_wiki_corpus_entries(wiki)]

    assert len(paths) == 250
    assert paths == sorted(paths)


def test_build_skips_a_page_over_the_default_four_mib_limit(tmp_path: Path):
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "small.md").write_text("small\n", encoding="utf-8")
    (wiki / "oversize.md").write_bytes(b"x" * (DEFAULT_PER_FILE_CAP + 1))
    stats = CorpusWalkStats()

    entries = build_wiki_corpus_entries(wiki, stats=stats)

    assert [entry["path"] for entry in entries] == ["wiki/small.md"]
    assert stats.skipped_oversize == 1


def test_build_stops_at_the_default_fifty_mib_aggregate_limit(
    tmp_path: Path, monkeypatch
):
    """Exercise the production-size accounting without reading 50 MiB in CI."""
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    for i in reversed(range(13)):
        path = wiki / f"{i:02d}.md"
        with path.open("wb") as handle:
            handle.truncate(DEFAULT_PER_FILE_CAP)

    def sparse_reader(path: Path, *, remaining_budget: int, per_file_cap: int):
        if remaining_budget < DEFAULT_PER_FILE_CAP:
            return "", 0
        return f"---\ntitle: {path.stem}\n---\n", DEFAULT_PER_FILE_CAP

    monkeypatch.setattr(corpus_mod, "read_capped", sparse_reader)
    stats = CorpusWalkStats()
    entries = build_wiki_corpus_entries(wiki, stats=stats)

    assert DEFAULT_AGGREGATE_BUDGET == 50 * 1024 * 1024
    assert len(entries) == 12  # 12 × 4 MiB fit; the 13th exceeds the 2 MiB remainder.
    assert [entry["path"] for entry in entries] == sorted(entry["path"] for entry in entries)
    assert stats.budget_exhausted is True


def test_entries_carry_title_and_kind_from_frontmatter(tmp_path: Path):
    """`kind` is MCP's own filter — frontmatter `type`, case-folded."""
    wiki = _wiki(tmp_path)
    by_path = {e["path"]: e for e in _corpus(_build(tmp_path, wiki))}
    assert by_path["wiki/entities/Hazel.md"]["title"] == "Hazel"
    assert by_path["wiki/entities/Hazel.md"]["kind"] == "entity"
    assert by_path["wiki/sources/2026-01-01-alpha.md"]["kind"] == "source"


def test_pages_with_no_reader_page_carry_a_null_url(tmp_path: Path):
    """Carried through as null rather than dropped — full MCP coverage, no
    dead-end navigation (technical-considerations §2.6)."""
    # @regression
    by_path = {e["path"]: e for e in _corpus(_build(tmp_path, _wiki(tmp_path)))}
    for rel in (
        "wiki/overview.md",
        "wiki/log.md",
        "wiki/candidates/Maybe.md",
        "wiki/syntheses/why.md",
        "wiki/categories/People.md",
    ):
        assert by_path[rel]["url"] is None, rel


def test_pages_with_a_reader_page_carry_its_url(tmp_path: Path):
    by_path = {e["path"]: e for e in _corpus(_build(tmp_path, _wiki(tmp_path)))}
    assert by_path["wiki/index.md"]["url"] == "index.html"
    assert by_path["wiki/projects/demo.md"]["url"] == "projects/demo.html"
    assert by_path["wiki/sources/2026-01-01-alpha.md"]["url"] == (
        "sessions/demo/2026-01-01-alpha.html"
    )


def test_curated_pages_route_to_the_topic_page_this_build_writes(tmp_path: Path):
    """An entity's only reader page is its topic page, which the build knows
    by `wiki_path` — so the URL is adopted, never invented."""
    wiki = _wiki(tmp_path)
    topics = [
        {"id": "Hazel", "kind": "entities", "site_url": "topics/hazel.html",
         "wiki_path": "wiki/entities/Hazel.md"},
    ]
    by_path = {e["path"]: e for e in _corpus(_build(tmp_path, wiki, topics=topics))}
    assert by_path["wiki/entities/Hazel.md"]["url"] == "topics/hazel.html"
    # A curated page this build wrote no topic page for stays unlinked.
    assert by_path["wiki/concepts/Batching.md"]["url"] is None


# ── the eager path must not grow ──────────────────────────────────────────


def test_eager_index_does_not_grow_by_page_text(tmp_path: Path):
    """`search-index.json` is fetched on every page view; the corpus is not.

    Asserted on the meta entries themselves, not merely on the payload
    existing: every entry is byte-identical to the one a build without the
    corpus produces, so no page text leaked into a body.
    """
    # @regression
    wiki = _wiki(tmp_path)
    with_corpus = _index(_build(tmp_path, wiki, out_name="with"))
    without = _index(_build(tmp_path, None, out_name="without"))

    assert with_corpus["entries"] == without["entries"]
    assert _MARKER not in json.dumps(with_corpus["entries"])
    # The corpus rides its own payload, and that payload really does carry
    # the text the eager index refuses to.
    assert _MARKER in json.dumps(_corpus(tmp_path / "with"))


def test_manifest_key_is_optional(tmp_path: Path):
    """A site built without a wiki dir carries no key — Slice 6's loader must
    tolerate its absence, and cannot if the build always writes it."""
    # @regression
    out = _build(tmp_path, None)
    assert WIKI_CORPUS_MANIFEST_KEY not in _index(out)
    assert not (out / WIKI_CORPUS_REL).exists()


def test_manifest_key_points_at_the_payload(tmp_path: Path):
    out = _build(tmp_path, _wiki(tmp_path))
    index = _index(out)
    assert index[WIKI_CORPUS_MANIFEST_KEY] == WIKI_CORPUS_REL
    assert (out / index[WIKI_CORPUS_MANIFEST_KEY]).is_file()
    # Untouched: the corpus sits beside the chunk manifest, not inside it.
    assert WIKI_CORPUS_REL not in index["_chunks"]
    assert index[WIKI_CORPUS_STATUS_KEY] == {
        "budget_exhausted": False,
        "skipped_oversize_files": 0,
    }


def test_payload_ships_a_js_sidecar(tmp_path: Path):
    """#20: the site must work when opened over file://."""
    # @regression
    out = _build(tmp_path, _wiki(tmp_path))
    sidecar = (out / WIKI_CORPUS_REL).with_suffix(".js").read_text(encoding="utf-8")
    assert sidecar.startswith("window.llmwikiData = window.llmwikiData || {};")
    marker = f'window.llmwikiData["{WIKI_CORPUS_REL}"] = '
    assert marker in sidecar
    payload = sidecar.split(marker, 1)[1].rsplit(";", 1)[0].strip()
    assert json.loads(payload) == _corpus(out)


# ── determinism (#150) ────────────────────────────────────────────────────


def test_two_builds_of_one_vault_are_byte_identical(tmp_path: Path):
    """`rglob` yields filesystem order; the payload sorts by path."""
    # @regression
    wiki = _wiki(tmp_path)
    first = (_build(tmp_path, wiki, out_name="a") / WIKI_CORPUS_REL).read_bytes()
    second = (_build(tmp_path, wiki, out_name="b") / WIKI_CORPUS_REL).read_bytes()
    assert first == second
    paths = [e["path"] for e in json.loads(first)]
    assert paths == sorted(paths)
