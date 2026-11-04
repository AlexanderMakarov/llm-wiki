"""Demo vault: Topics index grouping (#248 FR4).

# @layer: integration
# @spec: 248-wiki-site-search-corpus
"""

from __future__ import annotations

import re
from pathlib import Path

from tests.support.curated_topics_demo import DEMO_CURATED


def test_topics_index_counts_match_curated_pages(curated_demo_build: Path):
    html = (curated_demo_build / "topics" / "index.html").read_text(encoding="utf-8")
    n_entities = len(DEMO_CURATED["entities"])
    n_concepts = len(DEMO_CURATED["concepts"])
    heading = '<h2 class="topic-index-heading">{} <span class="muted">({})</span></h2>'
    assert heading.format("Entities", n_entities) in html
    assert heading.format("Concepts", n_concepts) in html
    assert 'Other topics <span class="muted">(' in html
    assert html.count('<span class="topic-kind-chip">Entity</span>') == n_entities
    assert html.count('<span class="topic-kind-chip">Concept</span>') == n_concepts
    for name in DEMO_CURATED["entities"] + DEMO_CURATED["concepts"]:
        assert f">{name}</a>" in html, f"{name} absent from listing"


def test_topics_index_links_only_written_pages(curated_demo_build: Path):
    listing = (curated_demo_build / "topics" / "index.html").read_text(encoding="utf-8")
    hrefs = set(re.findall(r'<li><a href="([^"]+)"', listing))
    assert hrefs
    for href in hrefs:
        assert (curated_demo_build / "topics" / href).resolve().is_file(), href
