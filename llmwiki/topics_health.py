"""Curated topic health checks shared by lint and tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from llmwiki.topics import CURATED_KIND_FOLDERS, build_topic_graph
from llmwiki.topics_page import page_content


def connected_topic_ids(graph: dict[str, Any]) -> set[str]:
    """Topic ids that appear on at least one co-occurrence edge."""
    connected: set[str] = set()
    for edge in graph.get("edges") or ():
        connected.add(str(edge.get("source", "")))
        connected.add(str(edge.get("target", "")))
    connected.discard("")
    return connected


def hollow_isolated_curated_pages(
    wiki_dir: Path,
    *,
    graph: dict[str, Any] | None = None,
) -> list[tuple[str, str]]:
    """Return ``(relative_wiki_path, title)`` for each hollow isolated curated page.

    Hollow means :func:`page_content` is empty after topic-page rendering rules.
    Isolated means the topic has no edge in the co-occurrence graph (with
    ``include_curated_pages=True`` so every entity/concept file is a node).
    """
    g = graph if graph is not None else build_topic_graph(
        wiki_dir, include_curated_pages=True,
    )
    connected = connected_topic_ids(g)
    by_path = {
        str(n.get("wiki_path") or ""): str(n.get("id", ""))
        for n in g.get("nodes") or ()
        if n.get("kind") in CURATED_KIND_FOLDERS and n.get("wiki_path")
    }
    out: list[tuple[str, str]] = []
    for folder in ("entities", "concepts"):
        root = wiki_dir / folder
        if not root.is_dir():
            continue
        for path in sorted(root.glob("*.md")):
            if path.name == "_context.md" or path.name.startswith("_"):
                continue
            rel = f"wiki/{folder}/{path.name}"
            title = by_path.get(rel)
            if title is None:
                continue
            if title in connected:
                continue
            text = path.read_text(encoding="utf-8")
            if page_content(text) is not None:
                continue
            out.append((rel, title))
    return out


def topic_knowledge_metrics(graph: dict[str, Any] | None) -> dict[str, int]:
    """Entity / concept / other counts from a built topic graph (Topics index parity)."""
    nodes = (graph or {}).get("nodes") or []
    entities = sum(1 for n in nodes if n.get("kind") == "entities")
    concepts = sum(1 for n in nodes if n.get("kind") == "concepts")
    other = sum(1 for n in nodes if n.get("kind") not in CURATED_KIND_FOLDERS)
    return {
        "topic_entities": entities,
        "topic_concepts": concepts,
        "topic_other": other,
    }
