"""``hollow_curated_pages`` lint rule and topic graph parity (#248 amendment).

# @layer: unit
# @spec: 248-wiki-site-search-corpus
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from llmwiki.lint import load_pages, run_all
from llmwiki.topics import build_topic_graph
from llmwiki.topics_health import hollow_isolated_curated_pages
from llmwiki.topics_page import build_topic_pages


def _page(name: str, *, content: bool) -> str:
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
        "stats": {"total_topics": len(nodes), "total_edges": len(edges), "kinds": {}},
    }


def _vault(tmp_path: Path, pages: dict[str, bool]) -> Path:
    entities = tmp_path / "wiki" / "entities"
    entities.mkdir(parents=True)
    for name, content in pages.items():
        (entities / f"{name}.md").write_text(_page(name, content=content), encoding="utf-8")
    return tmp_path / "wiki"


def test_hollow_detector_flags_isolated_empty_page(tmp_path: Path):
    wiki = _vault(tmp_path, {"Hollow": False})
    hollow = hollow_isolated_curated_pages(wiki)
    assert hollow == [("wiki/entities/Hollow.md", "Hollow")]


def test_hollow_detector_skips_connected_or_contentful(tmp_path: Path):
    wiki = _vault(tmp_path, {"Hollow": False, "Written": True})
    graph = build_topic_graph(wiki, include_curated_pages=True)
    graph["edges"] = [{"source": "Hollow", "target": "Written", "weight": 1, "sessions": []}]
    assert hollow_isolated_curated_pages(wiki, graph=graph) == []


def test_lint_rule_warns_on_hollow_page(tmp_path: Path):
    wiki = _vault(tmp_path, {"Hollow": False})
    pages = load_pages(wiki.parent)
    issues = run_all(pages, selected=["hollow_curated_pages"])
    assert any(i["rule"] == "hollow_curated_pages" and i["severity"] == "warning" for i in issues)


def test_build_writes_topic_page_for_hollow_curated_node(tmp_path: Path):
    wiki = _vault(tmp_path, {"Hollow": False})
    graph = _graph([_node("Hollow", wiki_path="wiki/entities/Hollow.md")], [])
    written = build_topic_pages(graph, tmp_path / "site", wiki_dir=wiki)
    assert "hollow.html" in {p.name for p in written}


