"""The palette's WIKI group is `wiki_search` match mode, in the browser (#248).

Slice 6 ports one algorithm across one language boundary, so the tests assert
the port against the original rather than against a description of it: the
JavaScript is lifted out of ``llmwiki/render/js.py`` and run under ``node``
over the same corpus that :func:`llmwiki.search.engine.search_match` is given,
and the two answers must be equal. ``llmwiki/search/**`` is never imported to
be patched here — it is the reference.

The second half covers presentation, which has one rule the parity tests
cannot express: both groups always render, and a wiki page with no reader page
is listed without becoming clickable.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from llmwiki.build import WIKI_CORPUS_MANIFEST_KEY, build_wiki_corpus_entries
from llmwiki.render.js import JS
from llmwiki.search.corpus import ScannedPage
from llmwiki.search.engine import DEFAULT_HIT_CAP, DEFAULT_PAGE_CAP, search_match

REPO_ROOT = Path(__file__).resolve().parents[1]
DEMO_WIKI = REPO_ROOT / "demo" / "wiki"

_BEGIN = "// ─── Wiki match mode (#248) ── BEGIN"
_END = "// ─── Wiki match mode (#248) ── END"

_DRIVER = """const fs = require("fs");
const M = require("./matcher.cjs");
const input = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
if (input.op === "match") {
  const out = {};
  for (const term of input.terms) {
    const r = M.searchMatch(input.corpus, term, input.kind || "");
    out[term] = {
      pages: r.pages.map(function (p) {
        return { path: p.path, name_match: p.nameMatch, lines: p.lines };
      }),
      truncated: r.truncated,
    };
  }
  process.stdout.write(JSON.stringify(out));
} else {
  process.stdout.write(JSON.stringify(M.buildHtml(input.view)));
}
"""


# ── harness ───────────────────────────────────────────────────────────────


def _matcher_source() -> str:
    """The marked, DOM-free region of the viewer JS, verbatim.

    Lifting the shipped source is the point: a copy of the algorithm in the
    test directory could pass while the site shipped something else.
    """
    start = JS.index(_BEGIN)
    end = JS.index(_END)
    return JS[start:end]


@pytest.fixture(scope="module")
def node_runner(tmp_path_factory: pytest.TempPathFactory):
    """Return ``run(payload) -> dict``, evaluating the shipped JS under node."""
    node = shutil.which("node")
    if node is None:  # pragma: no cover - environment-dependent
        pytest.skip("node is not installed — the JS half of FR7 cannot be exercised")
    work = tmp_path_factory.mktemp("palette_match")
    (work / "matcher.cjs").write_text(
        _matcher_source() + "\nmodule.exports = LLMWIKI_MATCH;\n", encoding="utf-8"
    )
    (work / "driver.cjs").write_text(_DRIVER, encoding="utf-8")
    counter = {"n": 0}

    def run(payload: dict) -> dict:
        counter["n"] += 1
        arg = work / f"in-{counter['n']}.json"
        arg.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        proc = subprocess.run(
            [node, str(work / "driver.cjs"), str(arg)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0, proc.stderr
        return json.loads(proc.stdout)

    return run


def _scanned(entry: dict) -> ScannedPage:
    """The corpus payload as the engine's own input type.

    ``meta`` carries only ``type`` because that is the single frontmatter
    field match mode reads (its ``kind`` filter).
    """
    text = entry["text"]
    return ScannedPage(
        rel_path=entry["path"],
        path=Path(entry["path"]),
        text=text,
        text_lower=text.lower(),
        title=entry["title"],
        meta={"type": entry["kind"]},
        size=len(text),
        is_raw=False,
    )


def _python_match(corpus: list[dict], term: str, kind: str = "") -> dict:
    result = search_match([_scanned(e) for e in corpus], [term], kind=kind)[term]
    return {
        "pages": [
            {"path": p.rel_path, "name_match": p.name_match, "lines": [list(x) for x in p.lines]}
            for p in result.pages
        ],
        "truncated": result.truncated,
    }


def _assert_parity(node_runner, corpus: list[dict], terms: list[str], kind: str = "") -> dict:
    """Run both implementations over one corpus and assert they agree."""
    js = node_runner({"op": "match", "corpus": corpus, "terms": terms, "kind": kind})
    for term in terms:
        assert js[term] == _python_match(corpus, term, kind), f"parity broke on {term!r}"
    return js


# ── corpora ───────────────────────────────────────────────────────────────


def _page(path: str, title: str, text: str, kind: str = "source", url: str | None = None) -> dict:
    return {"path": path, "title": title, "url": url, "kind": kind, "text": text}


@pytest.fixture(scope="module")
def corpus() -> list[dict]:
    """A small wiki shaped around the six behaviours match mode has to get right."""
    return [
        # Name match only: "Hazel" is in the title and path, in no body.
        _page(
            "wiki/entities/Hazel.md",
            "Hazel",
            "A build tool that no page names in its body.\n",
            kind="entity",
            url="topics/hazel.html",
        ),
        # Body match only: the marker appears nowhere in a name.
        _page(
            "wiki/sources/2026-01-01-alpha.md",
            "Alpha",
            "# Alpha\n\nWe measured the zanzibarine throughput.\nSecond zanzibarine line.\n",
            url="sessions/demo/alpha.html",
        ),
        # Ordering: "cadence" is a body hit here and a name hit below. This
        # page sorts first by path, so only the name-before-body rule can put
        # the other one first.
        _page(
            "wiki/concepts/Batching.md",
            "Batching",
            "# Batching\n\nWe tuned the cadence of the writer loop.\n",
            kind="concept",
            url="topics/batching.html",
        ),
        _page(
            "wiki/entities/Cadence.md",
            "Cadence",
            "# Cadence\n\nNo other occurrence of the word in this body.\n",
            kind="entity",
            url="topics/cadence.html",
        ),
        # Multi-word: both words are present, the phrase is not.
        _page(
            "wiki/sources/2026-02-02-beta.md",
            "Beta",
            "# Beta\n\nPagination is keyset based.\nThe cursors are opaque.\n",
            url="sessions/demo/beta.html",
        ),
        # Case folding outside ASCII.
        _page(
            "wiki/concepts/Кириллица.md",
            "Кириллица",
            "# Кириллица\n\nСтрока про КОДИРОВКУ текста.\n",
            kind="concept",
            url="topics/kirillitsa.html",
        ),
        # No reader page — overview.md has none, and the row must survive it.
        _page(
            "wiki/overview.md",
            "Overview",
            "# Overview\n\nThe zanzibarine programme, summarised.\n",
            kind="overview",
            url=None,
        ),
    ]


# ── parity with llmwiki.search.engine.search_match ─────────────────────────


def test_a_title_and_path_match_is_returned_without_a_body_hit(node_runner, corpus):
    """# @spec: 248-wiki-site-search-corpus @regression"""
    js = _assert_parity(node_runner, corpus, ["hazel"])
    assert [p["path"] for p in js["hazel"]["pages"]] == ["wiki/entities/Hazel.md"]
    assert js["hazel"]["pages"][0]["lines"] == []


def test_a_body_only_match_is_returned_with_its_lines(node_runner, corpus):
    """# @spec: 248-wiki-site-search-corpus @regression"""
    js = _assert_parity(node_runner, corpus, ["zanzibarine"])
    assert [p["path"] for p in js["zanzibarine"]["pages"]] == [
        "wiki/overview.md",
        "wiki/sources/2026-01-01-alpha.md",
    ]
    assert all(not p["name_match"] for p in js["zanzibarine"]["pages"])
    assert len(js["zanzibarine"]["pages"][1]["lines"]) == 2


def test_name_matches_sort_ahead_of_body_matches(node_runner, corpus):
    """The ordering rule, proven against a term that does both.

    ``wiki/concepts/Batching.md`` sorts first by path, so seeing
    ``wiki/entities/Cadence.md`` first can only be the name-first rule.

    # @spec: 248-wiki-site-search-corpus @regression
    """
    js = _assert_parity(node_runner, corpus, ["cadence"])
    assert [p["path"] for p in js["cadence"]["pages"]] == [
        "wiki/entities/Cadence.md",
        "wiki/concepts/Batching.md",
    ]


def test_a_multi_word_term_is_one_literal_substring(node_runner, corpus):
    """Both words appear; the phrase does not, so nothing matches.

    Documented in the functional spec's Out-of-Scope: match mode has no
    per-word fallback, and adding one to the site would diverge from MCP.

    # @spec: 248-wiki-site-search-corpus @regression
    """
    js = _assert_parity(node_runner, corpus, ["pagination cursors", "pagination"])
    assert js["pagination cursors"]["pages"] == []
    assert [p["path"] for p in js["pagination"]["pages"]] == ["wiki/sources/2026-02-02-beta.md"]


def test_case_folding_holds_outside_ascii(node_runner, corpus):
    """Cyrillic, lowercased on both sides — the one non-ASCII risk left once
    tokenisation is out of the picture.

    # @spec: 248-wiki-site-search-corpus @regression
    """
    js = _assert_parity(node_runner, corpus, ["кириллица", "КОДИРОВКУ", "кодировку"])
    assert js["кириллица"]["pages"][0]["name_match"] is True
    assert [p["path"] for p in js["кодировку"]["pages"]] == ["wiki/concepts/Кириллица.md"]
    assert js["КОДИРОВКУ"] == js["кодировку"]


def test_the_page_cap_drops_matches_and_says_so(node_runner):
    """# @spec: 248-wiki-site-search-corpus @regression"""
    big = [
        _page(f"wiki/sources/{i:04d}-widget.md", f"Widget {i}", "# body\n")
        for i in range(DEFAULT_PAGE_CAP + 50)
    ]
    js = _assert_parity(node_runner, big, ["widget"])
    assert len(js["widget"]["pages"]) == DEFAULT_PAGE_CAP
    assert js["widget"]["truncated"] is True


def test_the_hit_cap_drops_lines_and_says_so(node_runner):
    """# @spec: 248-wiki-site-search-corpus @regression"""
    body = "\n".join(f"widget line {i}" for i in range(DEFAULT_HIT_CAP + 50))
    js = _assert_parity(node_runner, [_page("wiki/sources/long.md", "Long", body)], ["widget"])
    assert sum(len(p["lines"]) for p in js["widget"]["pages"]) == DEFAULT_HIT_CAP
    assert js["widget"]["truncated"] is True


def test_the_kind_filter_is_mcps_frontmatter_type_filter(node_runner, corpus):
    """# @spec: 248-wiki-site-search-corpus @regression"""
    js = _assert_parity(node_runner, corpus, ["cadence"], kind="entity")
    assert [p["path"] for p in js["cadence"]["pages"]] == ["wiki/entities/Cadence.md"]


@pytest.mark.skipif(not DEMO_WIKI.is_dir(), reason="demo vault not checked out")
@pytest.mark.parametrize(
    "term", ["python", "session", "pagination", "Wiki", "the", "llmwiki build"]
)
def test_parity_over_the_committed_demo_vault(node_runner, term):
    """The synthetic corpora above are shaped to trip specific rules; this one
    is the real thing, with real frontmatter, real prose and 200+ pages.

    # @spec: 248-wiki-site-search-corpus @regression
    """
    _assert_parity(node_runner, build_wiki_corpus_entries(DEMO_WIKI), [term])


# ── presentation ──────────────────────────────────────────────────────────


def _view(*, wiki: dict | None = None, site: dict | None = None, term: str = "") -> dict:
    base = {"rows": [], "truncated": False, "message": None, "messageKind": "info"}
    return {
        "term": term,
        "wiki": {**base, "id": "wiki", "label": "Wiki", **(wiki or {})},
        "site": {**base, "id": "site", "label": "Site", **(site or {})},
    }


def _wiki_row(entry: dict, *, name_match: bool = True, lines: list | None = None) -> dict:
    return {"page": entry, "path": entry["path"], "title": entry["title"],
            "nameMatch": name_match, "lines": lines or []}


def test_both_groups_render_when_only_one_has_hits(node_runner, corpus):
    """The point of the two-group layout: a reader can tell "nothing in the
    wiki" from "search is broken" only if the empty group still shows up.

    # @spec: 248-wiki-site-search-corpus @regression
    """
    built = node_runner({"op": "html", "view": _view(
        wiki={"rows": [_wiki_row(corpus[0])]},
        site={"message": 'No site page contains "hazel".'},
    )})
    assert 'data-group="wiki"' in built["html"]
    assert 'data-group="site"' in built["html"]
    assert 'data-group-message="site"' in built["html"]
    assert "No site page contains" in built["html"]


def test_an_empty_wiki_group_keeps_its_heading(node_runner):
    """# @spec: 248-wiki-site-search-corpus @regression"""
    built = node_runner({"op": "html", "view": _view(
        wiki={"message": 'No wiki page contains "widget".'},
        site={"rows": [{"title": "Sessions", "url": "sessions/index.html", "type": "page"}]},
    )})
    assert 'data-group="wiki"' in built["html"]
    assert 'data-group-message="wiki"' in built["html"]
    assert "0 results" in built["html"]


def test_a_page_with_no_reader_page_is_listed_but_not_clickable(node_runner, corpus):
    """Full MCP coverage without dead-end navigation: the row is inert, not an
    anchor, and carries no ``data-i`` — so click and the arrow keys skip it.

    # @spec: 248-wiki-site-search-corpus @regression
    """
    overview = next(e for e in corpus if e["url"] is None)
    built = node_runner({"op": "html", "view": _view(
        wiki={"rows": [_wiki_row(corpus[0]), _wiki_row(overview, name_match=False,
                                                       lines=[[3, "the zanzibarine programme"]])]},
    )})
    rows = built["html"].split('<li class="palette-row')
    inert = next(r for r in rows if "wiki/overview.md" in r)
    assert "palette-row-static" in inert
    assert 'aria-disabled="true"' in inert
    assert "data-i=" not in inert
    assert "<a " not in inert and "<a>" not in inert
    assert "wiki/overview.md" in inert
    assert "zanzibarine programme" in inert
    # Only the page that has a URL is openable, and `data-i` indexes into it.
    assert [o["url"] for o in built["openable"]] == ["topics/hazel.html"]
    assert 'data-i="0"' in built["html"]


def test_a_capped_group_says_that_matches_were_dropped(node_runner):
    """# @spec: 248-wiki-site-search-corpus @regression"""
    built = node_runner({"op": "html", "view": _view(wiki={"truncated": True})})
    assert 'data-group-truncated="wiki"' in built["html"]
    assert str(DEFAULT_PAGE_CAP) in built["html"]


def test_a_failed_corpus_renders_the_error_row_not_an_empty_list(node_runner):
    """CONTRIBUTING rule 9 in the browser: the group says it is broken.

    # @spec: 248-wiki-site-search-corpus @regression
    """
    built = node_runner({"op": "html", "view": _view(
        wiki={"message": "Wiki search data could not be loaded — this group is broken, not empty.",
              "messageKind": "error"},
    )})
    assert "palette-note" in built["html"]
    assert built["openable"] == []


# ── highlighting (FR7) ────────────────────────────────────────────────────
#
# Presentation only: `view.term` reaches the renderer, never the matcher, so
# none of the parity assertions above may move. These assert the marking
# itself — every occurrence, original casing, and escaping that holds when
# the term matches inside markup the page happens to contain.


def _row_for(html: str, needle: str) -> str:
    """The one ``palette-row`` fragment that mentions ``needle``."""
    rows = [r for r in html.split('<li class="palette-row') if needle in r]
    assert len(rows) == 1, f"expected one row mentioning {needle!r}, got {len(rows)}"
    return rows[0]


def test_every_occurrence_in_a_line_is_marked(node_runner, corpus):
    """One line usually carries the term more than once.

    # @spec: 248-wiki-site-search-corpus @regression
    """
    row = _wiki_row(corpus[1], name_match=False,
                    lines=[[4, "widget beside widget beside widget"]])
    built = node_runner({"op": "html", "view": _view(wiki={"rows": [row]}, term="widget")})
    assert built["html"].count("<mark>widget</mark>") == 3


def test_a_case_insensitive_match_keeps_the_pages_own_casing(node_runner, corpus):
    """Matching folds case; the reader still sees what the page wrote.

    # @spec: 248-wiki-site-search-corpus @regression
    """
    row = _wiki_row(corpus[1], name_match=False,
                    lines=[[4, "Widget, then WIDGET, then widget"]])
    built = node_runner({"op": "html", "view": _view(wiki={"rows": [row]}, term="WiDgEt")})
    html = built["html"]
    assert "<mark>Widget</mark>" in html
    assert "<mark>WIDGET</mark>" in html
    assert "<mark>widget</mark>" in html


def test_markup_in_a_line_is_escaped_even_when_the_term_matches_inside_it(
    node_runner, corpus
):
    """Slices of the raw line are escaped and joined with literal tags, so a
    page that contains markup cannot inject any — including when the term
    lands inside a tag name and splits it.

    # @spec: 248-wiki-site-search-corpus @regression
    """
    line = [[4, "<script>alert(1)</script>"]]
    row = _wiki_row(corpus[1], name_match=False, lines=line)

    inside_tag = node_runner({"op": "html", "view": _view(
        wiki={"rows": [row]}, term="script")})["html"]
    assert "<script" not in inside_tag and "</script>" not in inside_tag
    assert "&lt;" in inside_tag and "&gt;" in inside_tag
    assert inside_tag.count("<mark>script</mark>") == 2

    between_tags = node_runner({"op": "html", "view": _view(
        wiki={"rows": [row]}, term="alert")})["html"]
    assert "<script" not in between_tags
    assert "&lt;script&gt;<mark>alert</mark>(1)&lt;/script&gt;" in between_tags


def test_the_title_and_the_path_are_highlighted_too(node_runner, corpus):
    """A name match is ``term in title`` OR ``term in path``, so both carry
    the mark — otherwise a path-only hit reads as unexplained.

    # @spec: 248-wiki-site-search-corpus @regression
    """
    built = node_runner({"op": "html", "view": _view(
        wiki={"rows": [_wiki_row(corpus[0])]}, term="hazel")})
    row = _row_for(built["html"], "wiki/entities/")
    assert '<span class="result-title"><mark>Hazel</mark></span>' in row
    assert 'wiki/entities/<mark>Hazel</mark>.md' in row


def test_site_rows_are_marked_the_same_way(node_runner):
    """Both groups read alike — the SITE group marks its title and meta.

    # @spec: 248-wiki-site-search-corpus @regression
    """
    built = node_runner({"op": "html", "view": _view(
        site={"rows": [{"title": "Widget notes", "url": "sessions/w.html",
                        "type": "session", "project": "widget-app", "date": "2026-01-01"}]},
        term="widget")})
    row = _row_for(built["html"], "notes")
    assert '<span class="result-title"><mark>Widget</mark> notes</span>' in row
    assert "<mark>widget</mark>-app" in row


def test_a_term_that_matches_nothing_renders_exactly_the_escaped_text(node_runner, corpus):
    """No hit, no markup change: the row is byte-identical to the unmarked one.

    # @spec: 248-wiki-site-search-corpus @regression
    """
    rows = {"rows": [_wiki_row(corpus[0], lines=[[4, "a & b < c"]])]}
    marked = node_runner({"op": "html", "view": _view(wiki=rows, term="zanzibarine")})
    plain = node_runner({"op": "html", "view": _view(wiki=rows)})
    assert marked["html"] == plain["html"]
    assert "<mark>" not in marked["html"]
    assert "a &amp; b &lt; c" in marked["html"]


# ── the viewer and the build agree on the manifest ────────────────────────


def test_the_viewer_reads_the_manifest_key_the_build_writes():
    """Drift between these two is invisible until the WIKI group is empty.

    # @spec: 248-wiki-site-search-corpus @regression
    """
    assert f'"{WIKI_CORPUS_MANIFEST_KEY}"' in JS


def test_a_site_without_the_manifest_key_reports_rather_than_goes_quiet():
    """A pre-#248 site has no key. The loader must survive that *and* say so."""
    marker = "function noteMissingWikiCorpus()"
    body = JS[JS.index(marker):JS.index("function loadWikiCorpus(")]
    assert "__llmwikiReportError" in body
    assert "wikiCorpusFailed = true" in body


def test_the_matcher_block_stays_dom_free():
    """The parity tests run it under node; a `document` reference would make
    the shipped code untestable against its Python original."""
    code = [
        line for line in _matcher_source().splitlines()
        if not line.lstrip().startswith("//")
    ]
    assert not [line for line in code if "document" in line]
