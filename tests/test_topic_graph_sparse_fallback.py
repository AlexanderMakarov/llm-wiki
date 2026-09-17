"""Sparse topic graphs must fall back to the page graph (#69 demo).

Seeding a few Claude-synthesized wiki sources can flip the site into
topic-graph mode while ``min_sessions=2`` keeps only 1–2 topics — which
looks broken on graph.html. Prefer the page graph until the vocabulary
is rich enough.

#248 splits that one decision in two: graph.html keeps falling back, but a
curated entity or concept still gets its topic page — and the palette entry
that points at it — because the topic page is the only page the reader has
for it. Either way the standing invariant holds: the search index never
carries a topic URL this build did not write.
"""

from __future__ import annotations

import json
from pathlib import Path

import llmwiki.build as build_mod
from llmwiki.build import build_site


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


def _curated_entity(name: str) -> str:
    return (
        f'---\ntitle: "{name}"\ntype: entity\ntags: []\n'
        "last_updated: 2026-07-01\n---\n\n"
        f"# {name}\n\n## Key Facts\n\n- A reviewed page no session cites.\n"
    )


def _build_sparse_vault(
    tmp_path: Path, monkeypatch, *, curated_entities: tuple[str, ...] = ()
) -> Path:
    """Build a vault whose topic graph stays under ``_TOPIC_GRAPH_MIN_NODES``.

    Two source pages share only Claude + llm-wiki → the topic graph keeps 2
    nodes after ``min_sessions=2`` (the same failure mode as the Pages demo).
    Each name in ``curated_entities`` adds a ``wiki/entities/`` page nothing
    links to, which #248 admits as a node without lifting the graph over the
    floor. Returns the site directory.
    """
    vault = tmp_path / "vault"
    raw = vault / "raw" / "sessions" / "demo"
    wiki_src = vault / "wiki" / "sources" / "demo"
    raw.mkdir(parents=True)
    wiki_src.mkdir(parents=True)
    (vault / "raw" / "docs").mkdir(parents=True)
    (vault / "site").mkdir()

    (raw / "2026-07-01T10-00-demo-a.md").write_text(
        _raw_session("demo", "a"), encoding="utf-8"
    )
    (wiki_src / "a.md").write_text(
        _wiki_source("a", ["Claude", "llm-wiki"]), encoding="utf-8"
    )
    (wiki_src / "b.md").write_text(
        _wiki_source("b", ["Claude", "llm-wiki"]), encoding="utf-8"
    )

    if curated_entities:
        entities = vault / "wiki" / "entities"
        entities.mkdir(parents=True)
        for name in curated_entities:
            (entities / f"{name}.md").write_text(_curated_entity(name), encoding="utf-8")

    monkeypatch.setattr(build_mod, "REPO_ROOT", vault)
    monkeypatch.setattr(build_mod, "SOURCE_ROOT", vault)
    monkeypatch.setattr(build_mod, "RAW_DIR", vault / "raw")
    monkeypatch.setattr(build_mod, "RAW_SESSIONS", vault / "raw" / "sessions")
    monkeypatch.setattr(build_mod, "DEFAULT_OUT_DIR", vault / "site")
    monkeypatch.setattr(build_mod, "compile_docs_site", lambda *a, **k: [])

    rc = build_site(
        out_dir=vault / "site",
        raw_sessions=vault / "raw" / "sessions",
        raw_dir=vault / "raw",
        wiki_dir=vault / "wiki",
    )
    assert rc == 0
    return vault / "site"


def test_sparse_topic_graph_falls_back_to_page_graph(tmp_path: Path, monkeypatch, capsys):
    site = _build_sparse_vault(tmp_path, monkeypatch)
    out = capsys.readouterr().out
    assert "topic graph too sparse" in out
    assert "interactive graph viewer" in out
    html = (site / "graph.html").read_text(encoding="utf-8")
    # Page-graph payload has no mode:"topic"; topic graph embeds '"mode": "topic"'.
    assert '"mode": "topic"' not in html
    # #50: sparse fallback must not index topic URLs that were never written —
    # with no curated page, this build writes none, so it indexes none.
    idx = json.loads((site / "search-index.json").read_text(encoding="utf-8"))
    assert not any(e.get("type") == "topic" for e in idx["entries"])
    assert not (site / "topics").exists()


def test_a_curated_page_gets_a_topic_page_under_the_sparse_floor(
    tmp_path: Path, monkeypatch, capsys
):
    """#248: a small vault keeps the page-graph map *and* its curated pages.

    The curated entity is cited by no session at all, so it neither lifts the
    graph over ``_TOPIC_GRAPH_MIN_NODES`` nor renders as anything but an
    isolated node — but it is a reviewed page, and the reader must be able to
    open it.
    """
    site = _build_sparse_vault(tmp_path, monkeypatch, curated_entities=("Hazel",))
    out = capsys.readouterr().out

    # Graph side is unchanged: still the page graph, still says why.
    assert "topic graph too sparse" in out
    assert "interactive graph viewer" in out
    assert '"mode": "topic"' not in (site / "graph.html").read_text(encoding="utf-8")

    # Page side is decoupled: the curated entity has a page, and the console
    # says so rather than leaving it implied.
    assert "topic pages" in out
    assert (site / "topics" / "index.html").is_file()
    hazel = site / "topics" / "hazel.html"
    assert hazel.is_file()
    assert "Hazel" in hazel.read_text(encoding="utf-8")

    # FR2: the reader can type the entity's name into the palette and find it.
    idx = json.loads((site / "search-index.json").read_text(encoding="utf-8"))
    topic_entries = [e for e in idx["entries"] if e.get("type") == "topic"]
    assert [e for e in topic_entries if e.get("title") == "Hazel"]
    # The same invariant the no-curated case pins, read from the other side:
    # every indexed topic URL resolves to a page this build actually wrote, so
    # the palette can never offer a 404.
    for entry in topic_entries:
        assert (site / entry["url"]).is_file(), entry["url"]
