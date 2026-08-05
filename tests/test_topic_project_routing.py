"""Project topics route to their project page (#108, FR4).

A topic is ``kind == "projects"`` because it matched a page under
``wiki/projects/``, so the match already names the project. This suite covers
the URL rewrite, the neighbour links that must follow it, and the fallback for
a wiki project page the build wrote no site page for.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import llmwiki.build as build_mod
from llmwiki.build import build_site
from llmwiki.topics import build_topic_graph, resolve_project_topic_urls
from llmwiki.topics_page import _resolve_wikilinks, _topic_links

_GRAPH_JSON = re.compile(r"^const GRAPH = (\{.*\});$", re.M)


def _node(topic_id: str, kind: str, **extra) -> dict:
    node = {
        "id": topic_id,
        "kind": kind,
        "site_url": f"topics/{topic_id.lower()}.html",
    }
    node.update(extra)
    return node


# ── unit: resolve_project_topic_urls ────────────────────────────────────────


def test_only_built_project_nodes_are_rewritten():
    graph = {
        "nodes": [
            _node("shipped", "projects", wiki_slug="shipped",
                  wiki_site_url="projects/shipped.html"),
            _node("ghost", "projects", wiki_slug="ghost",
                  wiki_site_url="projects/ghost.html"),
        ]
    }
    assert resolve_project_topic_urls(graph, {"shipped"}) == 1
    by_id = {n["id"]: n for n in graph["nodes"]}
    assert by_id["shipped"]["site_url"] == "projects/shipped.html"
    # Not in the built set — a link there would 404.
    assert by_id["ghost"]["site_url"] == "topics/ghost.html"
    # The backing page's URL is never clobbered by the rewrite.
    assert by_id["ghost"]["wiki_site_url"] == "projects/ghost.html"


def test_non_project_nodes_are_never_touched():
    graph = {
        "nodes": [
            _node("Hazel", "entities", wiki_slug="Hazel",
                  wiki_site_url="projects/Hazel.html"),
            _node("Batching", "other"),
        ]
    }
    assert resolve_project_topic_urls(graph, {"Hazel", "Batching"}) == 0
    assert graph["nodes"][0]["site_url"] == "topics/hazel.html"
    assert graph["nodes"][1]["site_url"] == "topics/batching.html"


def test_project_node_without_a_backing_url_is_skipped():
    graph = {
        "nodes": [
            _node("nourl", "projects", wiki_slug="nourl"),
            _node("noslug", "projects", wiki_site_url="projects/noslug.html"),
        ]
    }
    assert resolve_project_topic_urls(graph, {"nourl", "noslug"}) == 0
    assert graph["nodes"][0]["site_url"] == "topics/nourl.html"
    assert graph["nodes"][1]["site_url"] == "topics/noslug.html"


def test_returned_count_covers_every_rewritten_node():
    graph = {
        "nodes": [
            _node(name, "projects", wiki_slug=name,
                  wiki_site_url=f"projects/{name}.html")
            for name in ("a", "b", "c")
        ]
    }
    assert resolve_project_topic_urls(graph, {"a", "c"}) == 2


def test_graph_without_nodes_is_accepted():
    assert resolve_project_topic_urls({}, {"a"}) == 0


# ── unit: neighbour links follow the resolved URL ───────────────────────────


def test_neighbour_link_to_a_routed_project_climbs_out_of_topics():
    urls = {"shipped": "projects/shipped.html", "Hazel": "topics/hazel.html"}
    rendered = _topic_links([("shipped", 4), ("Hazel", 2)], urls)
    # Topic pages live in `topics/`, so a project page needs the `../` prefix.
    assert 'href="../projects/shipped.html"' in rendered
    # An ordinary topic stays a sibling.
    assert 'href="hazel.html"' in rendered


def test_neighbour_link_falls_back_to_the_topic_slug_without_a_url():
    rendered = _topic_links([("Some Topic", 1)], {})
    assert 'href="some-topic.html"' in rendered


# ── unit: page-content wikilinks follow the resolved URL ────────────────────

_LINK_INDEX = {"shipped": "shipped", "hazel": "Hazel"}
_LINK_URLS = {"shipped": "projects/shipped.html", "Hazel": "topics/hazel.html"}


def test_wikilink_to_a_project_topic_routes_to_its_project_page():
    out = _resolve_wikilinks("see [[shipped]]", _LINK_INDEX, {}, _LINK_URLS)
    assert out == 'see <a href="../projects/shipped.html">shipped</a>'


def test_wikilink_to_an_ordinary_topic_stays_a_sibling_page():
    out = _resolve_wikilinks("see [[Hazel]]", _LINK_INDEX, {}, _LINK_URLS)
    assert out == 'see <a href="hazel.html">Hazel</a>'


# ── integration: a built vault ──────────────────────────────────────────────

# "shipped" has recorded sessions and therefore a site page; "ghost" is a
# hand-authored wiki project page with none. The rest pad the graph past
# _TOPIC_GRAPH_MIN_NODES. Spellings are far enough apart that the vocabulary's
# near-duplicate clustering keeps them separate.
_TOPICS = ["shipped", "ghost", "Hazel", "Batching", "Unfiled"]
_PROJECT = "shipped"


def _build_fixture_vault(tmp_path: Path, monkeypatch) -> Path:
    vault = tmp_path / "vault"
    wiki = vault / "wiki"
    raw = vault / "raw" / "sessions" / _PROJECT
    site = vault / "site"
    src = wiki / "sources" / _PROJECT
    src.mkdir(parents=True)
    raw.mkdir(parents=True)
    (vault / "raw" / "docs").mkdir(parents=True)
    site.mkdir()

    links = "\n".join(f"- [[{t}]]" for t in _TOPICS)
    for j in range(3):
        stem = f"s{j}"
        (src / f"{stem}.md").write_text(
            f'---\ntitle: "{stem}"\ntype: source\nproject: {_PROJECT}\n'
            f"date: 2026-04-01\nsource_file: raw/sessions/{_PROJECT}/{stem}.md\n"
            f"---\n\n## Connections\n\n{links}\n",
            encoding="utf-8",
        )
        (raw / f"{stem}.md").write_text(
            f'---\ntitle: "{stem}"\ntype: source\nproject: {_PROJECT}\n'
            f"slug: {stem}\ndate: 2026-04-01\n"
            f"source_file: raw/sessions/{_PROJECT}/{stem}.md\n"
            'token_totals: {"input": 1, "output": 1, "cache_creation": 0, "cache_read": 0}\n'
            f"---\n\n# {stem}\n",
            encoding="utf-8",
        )

    projects = wiki / "projects"
    projects.mkdir(parents=True)
    for stem in ("shipped", "ghost"):
        (projects / f"{stem}.md").write_text(
            f'---\ntitle: "{stem}"\ntype: project\ntags: []\n'
            f"last_updated: 2026-04-02\n---\n\n# {stem}\n\nA fixture project.\n",
            encoding="utf-8",
        )

    graph = build_topic_graph(wiki, min_sessions=2)
    assert len(graph["nodes"]) >= 5, "fixture must clear the sparse-graph floor"

    monkeypatch.setattr(build_mod, "REPO_ROOT", vault)
    monkeypatch.setattr(build_mod, "SOURCE_ROOT", vault)
    monkeypatch.setattr(build_mod, "RAW_DIR", vault / "raw")
    monkeypatch.setattr(build_mod, "RAW_SESSIONS", vault / "raw" / "sessions")
    monkeypatch.setattr(build_mod, "DEFAULT_OUT_DIR", site)
    monkeypatch.setattr(build_mod, "compile_docs_site", lambda *a, **k: [])

    rc = build_site(
        out_dir=site,
        raw_sessions=vault / "raw" / "sessions",
        raw_dir=vault / "raw",
        wiki_dir=wiki,
    )
    assert rc == 0
    return site


def _graph_nodes(site: Path) -> dict[str, dict]:
    text = (site / "graph.html").read_text(encoding="utf-8")
    m = _GRAPH_JSON.search(text)
    assert m, "graph.html carries no embedded graph payload"
    return {n["id"]: n for n in json.loads(m.group(1))["nodes"]}


def test_built_project_topic_routes_to_its_project_page(tmp_path: Path, monkeypatch):
    site = _build_fixture_vault(tmp_path, monkeypatch)
    nodes = _graph_nodes(site)
    assert nodes["shipped"]["site_url"] == "projects/shipped.html"
    assert (site / "projects" / "shipped.html").is_file()


def test_project_without_a_site_page_falls_back_to_its_topic_page(
    tmp_path: Path, monkeypatch
):
    site = _build_fixture_vault(tmp_path, monkeypatch)
    nodes = _graph_nodes(site)
    assert nodes["ghost"]["site_url"] == "topics/ghost.html"
    assert (site / "topics" / "ghost.html").is_file()
    assert not (site / "projects" / "ghost.html").exists()


def test_topic_pages_link_the_project_topic_to_its_project_page(
    tmp_path: Path, monkeypatch
):
    site = _build_fixture_vault(tmp_path, monkeypatch)
    page = (site / "topics" / "hazel.html").read_text(encoding="utf-8")
    assert 'href="../projects/shipped.html">shipped</a>' in page
    # The fallback project stays a sibling topic link.
    assert 'href="ghost.html">ghost</a>' in page
    # Every routed topic still has a page of its own, so no link can 404.
    assert (site / "topics" / "shipped.html").is_file()


def test_topic_index_routes_the_project_topic_to_its_project_page(
    tmp_path: Path, monkeypatch
):
    site = _build_fixture_vault(tmp_path, monkeypatch)
    page = (site / "topics" / "index.html").read_text(encoding="utf-8")
    assert 'href="../projects/shipped.html">shipped</a>' in page
    # A project with no site page, and an ordinary topic, stay siblings.
    assert 'href="ghost.html">ghost</a>' in page
    assert 'href="hazel.html">Hazel</a>' in page


def test_search_index_routes_the_project_topic_to_its_project_page(
    tmp_path: Path, monkeypatch
):
    site = _build_fixture_vault(tmp_path, monkeypatch)
    data = json.loads((site / "search-index.json").read_text(encoding="utf-8"))
    by_title = {
        e["title"]: e for e in data["entries"] if e.get("type") == "topic"
    }
    assert by_title["shipped"]["url"] == "projects/shipped.html"
    assert by_title["ghost"]["url"] == "topics/ghost.html"


def test_every_topic_page_link_resolves_to_a_real_file(tmp_path: Path, monkeypatch):
    site = _build_fixture_vault(tmp_path, monkeypatch)
    hrefs = re.compile(r'<li><a href="([^"]+)">')
    for path in sorted((site / "topics").glob("*.html")):
        page = path.read_text(encoding="utf-8")
        for href in hrefs.findall(page):
            assert (path.parent / href).resolve().is_file(), f"{href} in {path.name}"
