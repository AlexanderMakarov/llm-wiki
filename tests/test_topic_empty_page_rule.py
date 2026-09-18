"""A topic with no connected topics and no content of its own gets no page.

# @layer: unit
# @spec: 248-wiki-site-search-corpus
# @regression

The rule (functional-spec.md §1, amended 2026-09-18) is a conjunction, and
both halves are load-bearing: a page with facts nobody co-cites is knowledge
someone reviewed, and a page with no facts but many connections is the hub of
a neighbourhood. Only a topic failing both would render a page carrying a
title, "No connected topics." and nothing else.

The suppression is computed once, in
:func:`llmwiki.topics_page.prune_empty_isolated_topics`, over the node list
every consumer reads. The build-level test below asserts the consequence that
matters: nothing on the site — no topic page, no search entry, no listing row,
no graph node, no wiki-corpus URL — points at a page the build did not write.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import llmwiki.build as build_mod
from llmwiki.build import WIKI_CORPUS_REL, build_site
from llmwiki.topics_page import build_topic_pages, prune_empty_isolated_topics

# ── unit: the rule itself ────────────────────────────────────────────────


def _page(name: str, *, content: bool) -> str:
    """A curated entity page, with or without anything of its own to say."""
    facts = "- A reviewed fact.\n" if content else ""
    return (
        f'---\ntitle: "{name}"\ntype: entity\ntags: []\n'
        f"last_updated: 2026-09-01\n---\n\n# {name}\n\n"
        f"## Key Facts\n{facts}\n## Connections\n- [[Elsewhere]]\n"
    )


def _node(name: str, **extra: Any) -> dict[str, Any]:
    node = {
        "id": name,
        "label": name,
        "type": "topic",
        "kind": "entities",
        "site_url": f"topics/{name.lower()}.html",
        "session_count": 1,
        "degree": 0,
        "aliases": [],
        "sessions": [],
    }
    node.update(extra)
    return node


def _graph(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "mode": "topic",
        "nodes": nodes,
        "edges": edges,
        "sessions": {},
        "stats": {
            "total_topics": len(nodes),
            "total_edges": len(edges),
            "total_sessions": 0,
            "kinds": {"entities": len(nodes)},
            "top_topics": [
                {"id": n["id"], "count": n["session_count"], "degree": n["degree"]}
                for n in nodes
            ],
        },
    }


def _vault(tmp_path: Path, pages: dict[str, bool]) -> Path:
    """Write ``wiki/entities/<name>.md`` per ``{name: has_content}``."""
    entities = tmp_path / "wiki" / "entities"
    entities.mkdir(parents=True)
    for name, content in pages.items():
        (entities / f"{name}.md").write_text(_page(name, content=content), encoding="utf-8")
    return tmp_path / "wiki"


def test_suppressed_when_it_has_neither_connections_nor_content(tmp_path: Path):
    wiki = _vault(tmp_path, {"Hollow": False})
    graph = _graph([_node("Hollow", wiki_path="wiki/entities/Hollow.md")], [])

    assert prune_empty_isolated_topics(graph, wiki) == ["Hollow"]
    assert graph["nodes"] == []


def test_written_when_it_has_connections_but_no_content(tmp_path: Path):
    wiki = _vault(tmp_path, {"Hollow": False, "Other": False})
    graph = _graph(
        [
            _node("Hollow", wiki_path="wiki/entities/Hollow.md", degree=1),
            _node("Other", wiki_path="wiki/entities/Other.md", degree=1),
        ],
        [{"source": "Hollow", "target": "Other", "weight": 1, "sessions": []}],
    )

    assert prune_empty_isolated_topics(graph, wiki) == []
    assert [n["id"] for n in graph["nodes"]] == ["Hollow", "Other"]


def test_written_when_it_has_content_but_no_connections(tmp_path: Path):
    wiki = _vault(tmp_path, {"Written": True})
    graph = _graph([_node("Written", wiki_path="wiki/entities/Written.md")], [])

    assert prune_empty_isolated_topics(graph, wiki) == []
    assert [n["id"] for n in graph["nodes"]] == ["Written"]


def test_written_when_it_has_both(tmp_path: Path):
    wiki = _vault(tmp_path, {"Written": True, "Other": False})
    graph = _graph(
        [
            _node("Written", wiki_path="wiki/entities/Written.md", degree=1),
            _node("Other", wiki_path="wiki/entities/Other.md", degree=1),
        ],
        [{"source": "Written", "target": "Other", "weight": 1, "sessions": []}],
    )

    assert prune_empty_isolated_topics(graph, wiki) == []
    assert len(graph["nodes"]) == 2


def test_a_topic_no_wiki_page_backs_has_no_content_of_its_own(tmp_path: Path):
    """A derived topic — nothing in ``wiki/`` describes it — fails the content
    half by definition, so an isolated one is suppressed like any other.
    """
    wiki = _vault(tmp_path, {})
    graph = _graph([_node("Derived", kind="other")], [])

    assert prune_empty_isolated_topics(graph, wiki) == ["Derived"]


def test_pruning_refreshes_the_counts_the_topics_index_renders(tmp_path: Path):
    """``stats["kinds"]`` is what the listing's section headings count, so a
    stale count would make a heading disagree with the list under it.
    """
    wiki = _vault(tmp_path, {"Hollow": False, "Written": True})
    kept = _node("Written", wiki_path="wiki/entities/Written.md")
    graph = _graph([kept, _node("Hollow", wiki_path="wiki/entities/Hollow.md")], [])

    prune_empty_isolated_topics(graph, wiki)

    assert graph["stats"]["total_topics"] == 1
    assert graph["stats"]["kinds"] == {"entities": 1}
    assert graph["stats"]["top_topics"] == [{"id": "Written", "count": 1, "degree": 0}]
    assert graph["stats"]["total_edges"] == 0


def test_pruning_writes_no_page_for_the_suppressed_topic(tmp_path: Path):
    """The listing and the pages come off the pruned list, so neither can
    mention a topic the build decided not to write.
    """
    wiki = _vault(tmp_path, {"Hollow": False, "Written": True})
    graph = _graph(
        [
            _node("Written", wiki_path="wiki/entities/Written.md"),
            _node("Hollow", wiki_path="wiki/entities/Hollow.md"),
        ],
        [],
    )
    prune_empty_isolated_topics(graph, wiki)

    written = build_topic_pages(graph, tmp_path / "site", wiki_dir=wiki)

    assert {p.name for p in written} == {"written.html", "index.html"}
    listing = (tmp_path / "site" / "topics" / "index.html").read_text(encoding="utf-8")
    assert "Hollow" not in listing
    assert 'Entities <span class="muted">(1)</span>' in listing


def test_pruning_a_graph_with_nothing_to_prune_leaves_it_alone(tmp_path: Path):
    wiki = _vault(tmp_path, {})
    graph = _graph([], [])
    before = json.dumps(graph, sort_keys=True)

    assert prune_empty_isolated_topics(graph, wiki) == []
    assert json.dumps(graph, sort_keys=True) == before


# ── integration: every consumer sees the same list ───────────────────────


def _raw_session(stem: str) -> str:
    return (
        f'---\ntitle: "{stem}"\ntype: source\nproject: demo\n'
        f"slug: {stem}\ndate: 2026-09-01\n"
        f"source_file: raw/sessions/demo/{stem}.md\n"
        "tools_used: [Bash]\n"
        'token_totals: {"input": 1, "output": 1, "cache_creation": 0, "cache_read": 0}\n'
        "---\n\n# demo\n"
    )


def _wiki_source(stem: str, links: list[str]) -> str:
    body = "\n".join(f"- [[{t}]]" for t in links)
    return (
        f'---\ntitle: "{stem}"\ntype: source\nproject: demo\n'
        f"date: 2026-09-01\nsource_file: raw/sessions/demo/{stem}.md\n"
        f"---\n\n## Connections\n\n{body}\n"
    )


def _build_vault(tmp_path: Path, monkeypatch) -> Path:
    """A vault with five co-cited topics plus two uncited curated pages.

    ``Written`` records a fact, ``Hollow`` records nothing — the only
    difference between the two, so anything that treats them differently is
    the rule under test and not an accident of the fixture.
    """
    vault = tmp_path / "vault"
    raw = vault / "raw" / "sessions" / "demo"
    wiki_src = vault / "wiki" / "sources" / "demo"
    raw.mkdir(parents=True)
    wiki_src.mkdir(parents=True)
    (vault / "raw" / "docs").mkdir(parents=True)
    (vault / "site").mkdir()

    cited = ["Alpha", "Batching", "Gamma", "Sparse", "Unfiled"]
    for stem in ("a", "b"):
        (raw / f"2026-09-01T10-00-demo-{stem}.md").write_text(
            _raw_session(stem), encoding="utf-8"
        )
        (wiki_src / f"{stem}.md").write_text(_wiki_source(stem, cited), encoding="utf-8")

    entities = vault / "wiki" / "entities"
    entities.mkdir(parents=True)
    (entities / "Written.md").write_text(_page("Written", content=True), encoding="utf-8")
    (entities / "Hollow.md").write_text(_page("Hollow", content=False), encoding="utf-8")

    monkeypatch.setattr(build_mod, "REPO_ROOT", vault)
    monkeypatch.setattr(build_mod, "SOURCE_ROOT", vault)
    monkeypatch.setattr(build_mod, "RAW_DIR", vault / "raw")
    monkeypatch.setattr(build_mod, "RAW_SESSIONS", vault / "raw" / "sessions")
    monkeypatch.setattr(build_mod, "DEFAULT_OUT_DIR", vault / "site")
    monkeypatch.setattr(build_mod, "compile_docs_site", lambda *a, **k: [])

    assert build_site(
        out_dir=vault / "site",
        raw_sessions=vault / "raw" / "sessions",
        raw_dir=vault / "raw",
        wiki_dir=vault / "wiki",
    ) == 0
    return vault / "site"


def test_a_full_build_suppresses_the_empty_page_everywhere_at_once(
    tmp_path: Path, monkeypatch
):
    site = _build_vault(tmp_path, monkeypatch)

    # 1. no topic page — while the page that differs only by one bullet gets one
    assert (site / "topics" / "written.html").is_file()
    assert not (site / "topics" / "hollow.html").exists()

    # 2. no `type: "topic"` search entry, and every remaining one resolves
    idx = json.loads((site / "search-index.json").read_text(encoding="utf-8"))
    topics = [e for e in idx["entries"] if e.get("type") == "topic"]
    assert "Written" in {e["title"] for e in topics}
    assert "Hollow" not in {e["title"] for e in topics}
    for entry in topics:
        assert (site / entry["url"]).is_file(), entry["url"]

    # 3. not listed and not counted on the listing
    listing = (site / "topics" / "index.html").read_text(encoding="utf-8")
    assert ">Written</a>" in listing
    assert "Hollow" not in listing
    assert 'Entities <span class="muted">(1)</span>' in listing

    # 4. in the wiki corpus — MCP scans the page — but with no URL to click
    corpus = {
        e["path"]: e
        for e in json.loads((site / WIKI_CORPUS_REL).read_text(encoding="utf-8"))
    }
    assert corpus["wiki/entities/Hollow.md"]["url"] is None
    assert corpus["wiki/entities/Written.md"]["url"] == "topics/written.html"

    # 5. the graph viewer opens `site_url` on double-click, so a suppressed
    #    node would be an isolated dot linking to nothing. It is dropped too.
    graph_html = (site / "graph.html").read_text(encoding="utf-8")
    assert '"mode": "topic"' in graph_html
    assert "Hollow" not in graph_html
