"""Topic pages open with an identity line naming the kind (#108, FR1 + FR8).

Builds a fixture vault holding an entity, a concept, a project and a topic
that no wiki page describes, then asserts the first three render their kind
chip and the fourth renders the unclassified one — with no empty heading and
no dangling label.
"""

from __future__ import annotations

import re
from pathlib import Path

import llmwiki.build as build_mod
from llmwiki.build import build_site
from llmwiki.topics import build_topic_graph
from llmwiki.topics_page import KIND_OTHER_LABEL

# Distinct enough that the vocabulary's near-duplicate clustering keeps them apart.
_TOPICS = ["Hazel", "Batching", "toolkit", "Unfiled", "Gamma"]
_EMPTY_HEADING = re.compile(r"<h(\d)[^>]*>\s*</h\1>")
_HERO_SUB = re.compile(r'<p class="hero-sub">(.*?)</p>', re.S)


def _wiki_page(folder: str, stem: str, type_: str) -> tuple[str, str]:
    body = (
        f'---\ntitle: "{stem}"\ntype: {type_}\ntags: []\n'
        f"last_updated: 2026-04-02\n---\n\n# {stem}\n\nA fixture page.\n"
    )
    return f"{folder}/{stem}.md", body


def _build_fixture_vault(tmp_path: Path, monkeypatch) -> Path:
    vault = tmp_path / "vault"
    wiki = vault / "wiki"
    raw = vault / "raw" / "sessions" / "proj"
    site = vault / "site"
    src = wiki / "sources" / "proj"
    src.mkdir(parents=True)
    raw.mkdir(parents=True)
    (vault / "raw" / "docs").mkdir(parents=True)
    site.mkdir()

    # Three sessions each mentioning every topic → 5 nodes (clears
    # _TOPIC_GRAPH_MIN_NODES) with 3 sessions apiece (clears min_sessions).
    links = "\n".join(f"- [[{t}]]" for t in _TOPICS)
    for j in range(3):
        stem = f"s{j}"
        (src / f"{stem}.md").write_text(
            f'---\ntitle: "{stem}"\ntype: source\nproject: proj\n'
            f"date: 2026-04-01\nsource_file: raw/sessions/proj/{stem}.md\n"
            f"---\n\n## Connections\n\n{links}\n",
            encoding="utf-8",
        )
        (raw / f"{stem}.md").write_text(
            f'---\ntitle: "{stem}"\ntype: source\nproject: proj\n'
            f"slug: {stem}\ndate: 2026-04-01\n"
            f"source_file: raw/sessions/proj/{stem}.md\n"
            'token_totals: {"input": 1, "output": 1, "cache_creation": 0, "cache_read": 0}\n'
            f"---\n\n# {stem}\n",
            encoding="utf-8",
        )

    # Three of the five topics get a backing page; Unfiled and Gamma get none.
    for folder, stem, type_ in (
        ("entities", "Hazel", "entity"),
        ("concepts", "Batching", "concept"),
        ("projects", "toolkit", "project"),
    ):
        rel, body = _wiki_page(folder, stem, type_)
        page = wiki / rel
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text(body, encoding="utf-8")

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


def test_described_topics_show_a_kind_chip(tmp_path: Path, monkeypatch):
    site = _build_fixture_vault(tmp_path, monkeypatch)
    for slug, label in (("hazel", "Entity"), ("batching", "Concept"),
                        ("toolkit", "Project")):
        page = (site / "topics" / f"{slug}.html").read_text(encoding="utf-8")
        assert f'<span class="topic-kind-chip">{label}</span>' in page
        assert "connected topics" in page and "sources" in page
        assert f"<code>{slug}</code>" in page


def test_undescribed_topic_is_labelled_unclassified(tmp_path: Path, monkeypatch):
    """No backing page is itself a fact, so the chip names it (FR1, FR8).

    A missing chip would leave the reader unable to tell an unclassified topic
    from a page that failed to render one.
    """
    site = _build_fixture_vault(tmp_path, monkeypatch)
    page = (site / "topics" / "unfiled.html").read_text(encoding="utf-8")
    assert (
        f'<span class="topic-kind-chip">{KIND_OTHER_LABEL}</span>' in page
    )
    # The rest of the identity line still renders.
    assert "connected topics" in page
    assert "<code>unfiled</code>" in page


def test_no_empty_heading_or_separator_on_any_topic_page(tmp_path: Path, monkeypatch):
    site = _build_fixture_vault(tmp_path, monkeypatch)
    for path in sorted((site / "topics").glob("*.html")):
        page = path.read_text(encoding="utf-8")
        assert not _EMPTY_HEADING.search(page), f"empty heading in {path.name}"
        sub = _HERO_SUB.search(page)
        assert sub, f"no identity line in {path.name}"
        line = sub.group(1).strip()
        assert "· ·" not in line
        assert not line.startswith("·") and not line.endswith("·")
