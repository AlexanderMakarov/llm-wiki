"""Demo vault: nav, wiki corpus routing, build determinism (#248).

# @layer: integration
# @spec: 248-wiki-site-search-corpus
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from llmwiki.build import WIKI_CORPUS_REL
from llmwiki.topics import topic_slug
from tests.support.curated_topics_demo import DEMO_CURATED, copy_demo_vault, run_build


def test_nav_topics_link_and_active_state(curated_demo_build: Path):
    topics_html = (curated_demo_build / "topics" / "index.html").read_text(encoding="utf-8")
    assert '<a href="../topics/index.html" class="active">Topics</a>' in topics_html
    root_html = (curated_demo_build / "index.html").read_text(encoding="utf-8")
    assert '<a href="topics/index.html">Topics</a>' in root_html


def test_wiki_corpus_routes_curated_pages_to_topic_pages(curated_demo_build: Path):
    by_path = {e["path"]: e for e in json.loads((curated_demo_build / WIKI_CORPUS_REL).read_text())}
    for kind, names in DEMO_CURATED.items():
        for name in names:
            entry = by_path[f"wiki/{kind}/{name}.md"]
            assert entry["url"] == f"topics/{topic_slug(name)}.html", name
            assert (curated_demo_build / entry["url"]).is_file(), name


def test_two_full_demo_builds_are_byte_identical(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    vault_a = copy_demo_vault(tmp_path / "a")
    vault_b = copy_demo_vault(tmp_path / "b")
    out_a, out_b = tmp_path / "site_a", tmp_path / "site_b"
    assert run_build(vault_a, out_a, monkeypatch) == 0
    assert run_build(vault_b, out_b, monkeypatch) == 0
    assert (out_a / "search-index.json").read_bytes() == (out_b / "search-index.json").read_bytes()
    assert (out_a / WIKI_CORPUS_REL).read_bytes() == (out_b / WIKI_CORPUS_REL).read_bytes()
    assert (
        (out_a / "topics" / "index.html").read_bytes()
        == (out_b / "topics" / "index.html").read_bytes()
    )
