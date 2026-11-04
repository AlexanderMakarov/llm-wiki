"""Demo vault: curated topic pages and search labels (#248).

# @layer: integration
# @spec: 248-wiki-site-search-corpus
"""

from __future__ import annotations

import json
from pathlib import Path

from llmwiki.topics import topic_slug
from llmwiki.topics_health import hollow_isolated_curated_pages
from tests.support.curated_topics_demo import DEMO, DEMO_CURATED


def test_demo_vault_has_no_hollow_curated_pages():
    """Release demo must not ship empty isolated entity/concept files."""
    assert hollow_isolated_curated_pages(DEMO / "wiki") == []


def test_every_demo_curated_page_opens(curated_demo_build: Path):
    for kind, names in DEMO_CURATED.items():
        for name in names:
            page = curated_demo_build / "topics" / f"{topic_slug(name)}.html"
            assert page.is_file(), f"{name} ({kind}) has no topic page"
            assert name in page.read_text(encoding="utf-8")


def test_obsidian_page_kept_for_connections_alone(curated_demo_build: Path):
    page = curated_demo_build / "topics" / "obsidian.html"
    assert page.is_file()
    assert "Connected topics" in page.read_text(encoding="utf-8")


def test_every_curated_topic_search_entry_labelled(curated_demo_build: Path):
    idx = json.loads((curated_demo_build / "search-index.json").read_text(encoding="utf-8"))
    topic_entries = {e["title"]: e for e in idx["entries"] if e.get("type") == "topic"}
    for kind, names in DEMO_CURATED.items():
        expected_kind = "Entity" if kind == "entities" else "Concept"
        for name in names:
            entry = topic_entries.get(name)
            assert entry is not None, f"{name} missing from search-index.json"
            assert entry["kind"] == expected_kind, name
            assert (curated_demo_build / entry["url"]).is_file(), name
