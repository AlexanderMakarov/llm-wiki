"""Whole-feature acceptance tests for #248: curated knowledge reaches the
browsing reader.

# @layer: integration
# @spec: 248-wiki-site-search-corpus
# @regression

Per-slice suites (``test_topics.py``, ``test_topic_graph_sparse_fallback.py``,
``test_248_wiki_search_corpus.py``, ``test_248_palette_match.py``,
``test_mobile_hamburger_nav.py``, ``test_reference_coverage.py``,
``tests/e2e/test_search_palette.py``) already cover FR1-FR7's per-slice
mechanics against synthetic fixtures, each calling the narrowest function the
slice touches (``build_topic_graph``, ``build_search_index``, the JS matcher
under ``node``, ...).

This file drives ``build_site()`` itself — the function ``llmwiki build``
calls — over a private copy of the committed ``demo/`` vault (never the
repo's own ``demo/site`` or ``demo/llmwiki-state.json``), plus one
purpose-built scratch vault, to check the properties that only hold once
every slice is wired together through the real pipeline:

* the functional spec's own "How we measure success" bullets (9 entities +
  4 concepts = 13 curated pages, all with a page and a correctly labelled
  search entry, against 12 of 13 today) hold on the actual vault a build
  produces — not a fixture shaped to make them true;
* the grouped listing (FR4) counts the same 13 pages the bypass (FR1)
  creates, the nav (FR3) points at that listing, and the wiki corpus (FR7)
  routes the previously-invisible page to the topic page the same build
  wrote (FR1+FR7 chained through ``_compute_site_url``'s fallback);
* cold storage and folder-context stubs (FR5) stay out of the topic graph,
  the topic pages, and the search index when driven through the real
  ``build.py:3321`` call site rather than through ``build_topic_graph``
  directly;
* the curated bypass ``build.py:3321`` opts into does not leak into
  ``topics_consolidate.build_candidates`` when both are run against the one
  wiki dir a real build touches (technical-considerations.md §3's named
  largest risk, asserted at the call sites the risk is actually about);
* two full builds of one vault are byte-identical (#150), for the whole
  output this feature touches, not only the wiki-corpus payload in
  isolation.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

import llmwiki.build as build_mod
from llmwiki.build import WIKI_CORPUS_REL, build_site
from llmwiki.topics import topic_slug
from llmwiki.topics_consolidate import build_candidates

REPO_ROOT = Path(__file__).resolve().parents[1]
DEMO = REPO_ROOT / "demo"

# The demo vault's 9 entities + 4 concepts = 13, per functional-spec.md §1.
_CURATED = {
    "entities": [
        "Claude Code", "Codex CLI", "Frontmatter", "GitHub Actions",
        "GitHub Pages", "Obsidian", "Ollama", "Python", "SQLite",
    ],
    "concepts": ["Adapters", "Knowledge Graph", "Observability", "Static Site"],
}


# ── build harness ────────────────────────────────────────────────────────


def _copy_demo_vault(tmp_path: Path) -> Path:
    """A private copy of the committed demo/ vault.

    Building against ``demo/`` itself would write ``demo/llmwiki-state.json``
    — forbidden by the vault-safety rule for this task. Only ``wiki/`` and
    ``raw/`` are needed by ``build_site``.
    """
    vault = tmp_path / "vault"
    shutil.copytree(DEMO / "wiki", vault / "wiki")
    shutil.copytree(DEMO / "raw", vault / "raw")
    return vault


def _run_build(vault: Path, out: Path, monkeypatch: pytest.MonkeyPatch) -> int:
    out.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(build_mod, "REPO_ROOT", vault)
    monkeypatch.setattr(build_mod, "SOURCE_ROOT", vault)
    monkeypatch.setattr(build_mod, "RAW_DIR", vault / "raw")
    monkeypatch.setattr(build_mod, "RAW_SESSIONS", vault / "raw" / "sessions")
    monkeypatch.setattr(build_mod, "DEFAULT_OUT_DIR", out)
    monkeypatch.setattr(build_mod, "PROJECTS_META_DIR", vault / "wiki" / "projects")
    monkeypatch.setattr(build_mod, "compile_docs_site", lambda *a, **k: [])
    return build_site(
        out_dir=out,
        raw_sessions=vault / "raw" / "sessions",
        raw_dir=vault / "raw",
        wiki_dir=vault / "wiki",
    )


@pytest.fixture(scope="module")
def demo_build(tmp_path_factory: pytest.TempPathFactory, request: pytest.FixtureRequest) -> Path:
    """One real ``build_site()`` pass over a private demo-vault copy.

    Module-scoped and read-only from every test below — building the demo
    vault synthesizes nothing and takes real wall-clock time, and nothing
    here mutates the output.
    """
    tmp_path = tmp_path_factory.mktemp("demo248")
    vault = _copy_demo_vault(tmp_path)
    out = tmp_path / "site"
    mp = pytest.MonkeyPatch()
    request.addfinalizer(mp.undo)
    rc = _run_build(vault, out, mp)
    assert rc == 0, "demo vault build failed"
    return out


def _search_index(site: Path) -> dict:
    return json.loads((site / "search-index.json").read_text(encoding="utf-8"))


def _wiki_corpus(site: Path) -> list[dict]:
    return json.loads((site / WIKI_CORPUS_REL).read_text(encoding="utf-8"))


# ── FR1 + FR2: the demo vault's own success metric ─────────────────────────


def test_all_13_demo_curated_pages_open(demo_build: Path):
    """functional-spec.md §1: "all 13 curated entities and concepts have a
    page a reader can open ... against 12 of 13 today".
    """
    for kind, names in _CURATED.items():
        for name in names:
            page = demo_build / "topics" / f"{topic_slug(name)}.html"
            assert page.is_file(), f"{name} ({kind}) has no page a reader can open"
            assert name in page.read_text(encoding="utf-8")


def test_python_specifically_is_no_longer_the_missing_thirteenth(demo_build: Path):
    """The functional spec names this exact page as today's one gap — the
    demo entity three sources cite but no session's ``[[wikilink]]`` reaches
    (technical-considerations.md §2.1).
    """
    page = demo_build / "topics" / "python.html"
    assert page.is_file()
    idx = _search_index(demo_build)
    python_entries = [
        e for e in idx["entries"] if e.get("type") == "topic" and e.get("title") == "Python"
    ]
    assert python_entries, "Python has no palette entry"
    assert python_entries[0]["kind"] == "Entity"
    assert (demo_build / python_entries[0]["url"]).is_file()


def test_all_13_curated_entries_are_labelled_and_resolve_to_a_real_page(demo_build: Path):
    """FR2, for every one of the 13 named in the spec — not a sample."""
    idx = _search_index(demo_build)
    topic_entries = {e["title"]: e for e in idx["entries"] if e.get("type") == "topic"}
    for kind, names in _CURATED.items():
        expected_kind = "Entity" if kind == "entities" else "Concept"
        for name in names:
            entry = topic_entries.get(name)
            assert entry is not None, f"{name} missing from search-index.json"
            assert entry["kind"] == expected_kind, name
            assert (demo_build / entry["url"]).is_file(), f"{name} points at a page that does not exist"


# ── FR4: the grouped listing counts what FR1's bypass actually created ────


def test_demo_topics_index_groups_all_9_entities_and_4_concepts(demo_build: Path):
    """FR4 chained onto FR1: the same 13 pages the bypass creates must be
    the same 13 the index counts and chips — not merely equal counts by
    coincidence.
    """
    html = (demo_build / "topics" / "index.html").read_text(encoding="utf-8")
    assert '<h2 class="topic-index-heading">Entities <span class="muted">(9)</span></h2>' in html
    assert '<h2 class="topic-index-heading">Concepts <span class="muted">(4)</span></h2>' in html
    assert 'Other topics <span class="muted">(' in html
    assert html.count('<span class="topic-kind-chip">Entity</span>') == 9
    assert html.count('<span class="topic-kind-chip">Concept</span>') == 4
    for name in _CURATED["entities"] + _CURATED["concepts"]:
        assert f">{name}</a>" in html, f"{name} absent from the grouped listing"


# ── FR3: navigation, on real generated pages ───────────────────────────────


def test_demo_nav_carries_topics_and_marks_it_active_only_on_the_index(demo_build: Path):
    topics_html = (demo_build / "topics" / "index.html").read_text(encoding="utf-8")
    assert '<a href="../topics/index.html" class="active">Topics</a>' in topics_html
    assert 'class="nav-drawer-link active">Topics</a>' in topics_html

    root_html = (demo_build / "index.html").read_text(encoding="utf-8")
    assert '<a href="topics/index.html">Topics</a>' in root_html
    assert 'class="nav-drawer-link">Topics</a>' in root_html


# ── FR1 + FR7 chained: the corpus adopts the page the bypass wrote ────────


def test_demo_wiki_corpus_routes_python_to_the_topic_page_this_build_wrote(demo_build: Path):
    """technical-considerations.md §2.6: ``_compute_site_url`` returns
    ``None`` for ``entities``/``concepts``, so the corpus falls back to the
    backing topic node's own ``site_url``. That fallback only has a URL to
    adopt because FR1's bypass wrote the page in the same build — this is
    the one place FR1 and FR7 depend on each other.
    """
    by_path = {e["path"]: e for e in _wiki_corpus(demo_build)}
    entry = by_path["wiki/entities/Python.md"]
    assert entry["url"] == "topics/python.html"
    assert (demo_build / entry["url"]).is_file()


# ── determinism (#150), for the whole pipeline ────────────────────────────


def test_two_full_demo_builds_are_byte_identical(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Slice-level tests pin determinism for the wiki-corpus payload and for
    the topic graph's own node/edge ordering in isolation. This drives two
    full ``build_site()`` passes and diffs the outputs those slices feed —
    the property that actually matters to a reader running ``build`` twice.
    """
    vault_a = _copy_demo_vault(tmp_path / "a")
    vault_b = _copy_demo_vault(tmp_path / "b")
    out_a, out_b = tmp_path / "site_a", tmp_path / "site_b"
    assert _run_build(vault_a, out_a, monkeypatch) == 0
    assert _run_build(vault_b, out_b, monkeypatch) == 0

    idx_a = (out_a / "search-index.json").read_bytes()
    idx_b = (out_b / "search-index.json").read_bytes()
    assert idx_a == idx_b

    corpus_a = (out_a / WIKI_CORPUS_REL).read_bytes()
    corpus_b = (out_b / WIKI_CORPUS_REL).read_bytes()
    assert corpus_a == corpus_b

    topics_index_a = (out_a / "topics" / "index.html").read_bytes()
    topics_index_b = (out_b / "topics" / "index.html").read_bytes()
    assert topics_index_a == topics_index_b


# ── FR5, driven through the real build_site() call site ──────────────────


def _raw_session(project: str, stem: str) -> str:
    return (
        f'---\ntitle: "{stem}"\ntype: source\nproject: {project}\n'
        f"slug: {stem}\ndate: 2026-07-01\n"
        f"source_file: raw/sessions/{project}/{stem}.md\n"
        "tools_used: [Bash]\n"
        'token_totals: {"input": 1, "output": 1, "cache_creation": 0, "cache_read": 0}\n'
        "---\n\n# demo\n"
    )


def _wiki_source(stem: str, links: list[str]) -> str:
    body = "\n".join(f"- [[{t}]]" for t in links)
    return (
        f'---\ntitle: "{stem}"\ntype: source\nproject: demo\n'
        f"date: 2026-07-01\nsource_file: raw/sessions/demo/{stem}.md\n"
        f"---\n\n## Connections\n\n{body}\n"
    )


def _curated_page(name: str) -> str:
    return (
        f'---\ntitle: "{name}"\ntype: entity\ntags: []\n'
        "last_updated: 2026-07-01\n---\n\n"
        f"# {name}\n\n## Key Facts\n\n- A reviewed page.\n"
    )


def _scaffold_fr5_vault(tmp_path: Path) -> Path:
    """A vault with one legitimate curated page, one archived curated page,
    one folder-context stub, and one derived one-off mention with no curated
    page — the four cases FR1's scoping guard and FR5's cold-storage guard
    must tell apart, wired through the real build entry point rather than
    through ``build_topic_graph`` called directly.
    """
    vault = tmp_path / "vault"
    raw = vault / "raw" / "sessions" / "demo"
    wiki_src = vault / "wiki" / "sources" / "demo"
    raw.mkdir(parents=True)
    wiki_src.mkdir(parents=True)
    (vault / "raw" / "docs").mkdir(parents=True)

    (raw / "2026-07-01T10-00-demo-a.md").write_text(_raw_session("demo", "a"), encoding="utf-8")
    # A one-off derived mention, cited by exactly one source and backed by no
    # curated page — FR1 must not admit it even under the bypass.
    (wiki_src / "a.md").write_text(_wiki_source("a", ["OneOff"]), encoding="utf-8")

    entities = vault / "wiki" / "entities"
    entities.mkdir(parents=True)
    (entities / "Hazel.md").write_text(_curated_page("Hazel"), encoding="utf-8")
    (entities / "_context.md").write_text(
        '---\ntitle: "Entities"\ntype: context\n---\n\nStub for assistants.\n',
        encoding="utf-8",
    )
    archive = vault / "wiki" / "archive" / "entities"
    archive.mkdir(parents=True)
    (archive / "Dismissed.md").write_text(_curated_page("Dismissed"), encoding="utf-8")

    return vault


def test_archived_and_underscore_curated_pages_stay_out_of_the_full_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """FR5, asserted at ``build.py:3321`` — the site's own call site — not
    only at ``build_topic_graph`` called directly.
    """
    vault = _scaffold_fr5_vault(tmp_path)
    out = tmp_path / "site"
    assert _run_build(vault, out, monkeypatch) == 0

    # Positive control: the legitimate curated page really was admitted.
    assert (out / "topics" / "hazel.html").is_file()

    # Cold storage never gets a page, however the build is driven.
    assert not (out / "topics" / "dismissed.html").exists()
    for html_file in (out / "topics").glob("*.html"):
        assert "Dismissed" not in html_file.read_text(encoding="utf-8")

    # A folder-context stub is not curated knowledge; the guard is a slug
    # check, not a kind check, so it must not surface under any spelling.
    assert not (out / "topics" / "context.html").exists()
    assert not (out / "topics" / "_context.html").exists()

    # A derived one-off with no curated page stays excluded even though the
    # site build enables the curated bypass (FR1's scoping requirement).
    assert not (out / "topics" / "oneoff.html").exists()

    idx = _search_index(out)
    topic_titles = {e["title"] for e in idx["entries"] if e.get("type") == "topic"}
    assert "Hazel" in topic_titles
    assert "Dismissed" not in topic_titles
    assert "OneOff" not in topic_titles
    assert not any(t.lower() in ("context", "_context") for t in topic_titles)


def test_full_build_curated_bypass_does_not_leak_into_synth_candidates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """technical-considerations.md §3's named largest risk: if the site's
    bypass leaked into the synth path, an already-promoted entity would
    re-enter the candidate stream and the consolidator would re-decide a
    settled name (the #146 bug class). ``test_topics.py`` pins this by
    calling ``build_topic_graph`` twice with the flag toggled; this asserts
    it at the two real call sites the risk describes — a full
    ``build_site()`` pass (which turns the bypass on) and
    ``topics_consolidate.build_candidates`` (which must keep it off) against
    the one wiki dir a real build produces.
    """
    vault = _scaffold_fr5_vault(tmp_path)
    out = tmp_path / "site"
    assert _run_build(vault, out, monkeypatch) == 0

    # The site did admit Hazel with zero qualifying sessions (positive control).
    assert (out / "topics" / "hazel.html").is_file()

    # The synth path, run against the same wiki dir afterwards, must not
    # re-propose it as a candidate — it is already a reviewed page.
    candidate_names = {c["name"] for c in build_candidates(vault / "wiki")}
    assert "Hazel" not in candidate_names
    assert "Dismissed" not in candidate_names
