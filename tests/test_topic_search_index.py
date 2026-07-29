"""Topic pages must appear in the Cmd+K search index (#50).

Topic HTML under ``site/topics/`` and topic nodes in the graph were reachable
from the graph viewer but absent from ``search-index.json``, so a query for a
topic's canonical label (or any of its aliases) returned nothing.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from llmwiki import build as build_mod
from llmwiki.build import build_search_index, build_site
from llmwiki.topics import build_topic_graph, topic_slug


def _tiny_sources(tmp_path: Path) -> tuple[list, dict]:
    sources = []
    for slug in ("one", "two"):
        src = tmp_path / "sessions" / "demo" / f"{slug}.md"
        src.parent.mkdir(parents=True, exist_ok=True)
        body = f"# {slug}\nbody\n"
        src.write_text(body, encoding="utf-8")
        sources.append(
            (src, {"project": "demo", "slug": slug, "date": "2026-04-19"}, body)
        )
    groups = {"demo": sources}
    return sources, groups


def test_build_search_index_includes_topic_entries(tmp_path: Path):
    sources, groups = _tiny_sources(tmp_path)
    out = tmp_path / "site"
    out.mkdir()
    topics = [
        {
            "id": "OpenClaw",
            "site_url": "topics/openclaw.html",
            "session_count": 3,
            "aliases": ["openclaw", "Open Claw"],
            "description": "agent runtime",
        },
        {
            "id": "LLM-Wiki",
            "site_url": "topics/llm-wiki.html",
            "session_count": 2,
            "aliases": ["LLMWiki", "llm wiki"],
            "description": "",
        },
    ]
    build_search_index(sources, groups, out, topics=topics)
    data = json.loads((out / "search-index.json").read_text(encoding="utf-8"))
    topic_entries = [e for e in data["entries"] if e.get("type") == "topic"]
    assert len(topic_entries) == 2
    by_title = {e["title"]: e for e in topic_entries}

    oc = by_title["OpenClaw"]
    assert oc["id"] == "topic:openclaw"
    assert oc["url"] == "topics/openclaw.html"
    assert oc["type"] == "topic"
    # Aliases + description ride in body so fuzzy match finds non-canonical forms.
    body_l = oc["body"].lower()
    assert "open claw" in body_l
    assert "agent runtime" in body_l
    assert "3 sessions" in body_l

    lw = by_title["LLM-Wiki"]
    assert lw["url"] == "topics/llm-wiki.html"
    assert "llmwiki" in lw["body"].lower()


def test_topic_entries_ride_js_sidecar(tmp_path: Path):
    """#20: topic data must be in the .js sidecar, not only search-index.json."""
    sources, groups = _tiny_sources(tmp_path)
    out = tmp_path / "site"
    out.mkdir()
    topics = [
        {
            "id": "OpenClaw",
            "site_url": "topics/openclaw.html",
            "session_count": 1,
            "aliases": ["openclaw"],
            "description": "",
        }
    ]
    build_search_index(sources, groups, out, topics=topics)
    js = (out / "search-index.js").read_text(encoding="utf-8")
    m = re.search(r'window\.llmwikiData\["search-index"\]\s*=\s*(.*);\s*$', js, re.S)
    assert m, "search-index.js sidecar missing expected assignment"
    payload = json.loads(m.group(1))
    assert any(e.get("type") == "topic" and e.get("title") == "OpenClaw" for e in payload["entries"])


def test_build_site_indexes_topics_when_graph_is_rich(tmp_path: Path, monkeypatch):
    """End-to-end: a rich topic vocabulary must land in the built search index."""
    vault = tmp_path / "vault"
    wiki = vault / "wiki"
    raw = vault / "raw" / "sessions" / "proj"
    site = vault / "site"
    src = wiki / "sources" / "proj"
    src.mkdir(parents=True)
    raw.mkdir(parents=True)
    (vault / "raw" / "docs").mkdir(parents=True)
    site.mkdir()

    # Five topics × two sessions each → clears the sparse-fallback floor (≥5 nodes).
    topic_names = ["Alpha", "Beta", "Gamma", "Delta", "Epsilon"]
    for i, _name in enumerate(topic_names):
        for j in range(2):
            stem = f"s{i}-{j}"
            links = "\n".join(f"- [[{t}]]" for t in topic_names)
            page = (
                f'---\ntitle: "{stem}"\ntype: source\nproject: proj\n'
                f"date: 2026-04-01\nsource_file: raw/sessions/proj/{stem}.md\n"
                f"---\n\n## Connections\n\n{links}\n"
            )
            (src / f"{stem}.md").write_text(page, encoding="utf-8")
            (raw / f"{stem}.md").write_text(
                f'---\ntitle: "{stem}"\ntype: source\nproject: proj\n'
                f"slug: {stem}\ndate: 2026-04-01\n"
                f"source_file: raw/sessions/proj/{stem}.md\n"
                'token_totals: {"input": 1, "output": 1, "cache_creation": 0, "cache_read": 0}\n'
                f"---\n\n# {stem}\n",
                encoding="utf-8",
            )

    # Case variant so aliases land on the Alpha node.
    s0 = src / "s0-0.md"
    s0.write_text(
        s0.read_text(encoding="utf-8").replace("[[Alpha]]", "[[Alpha]]\n- [[alpha]]", 1),
        encoding="utf-8",
    )

    g = build_topic_graph(wiki, min_sessions=2)
    assert len(g["nodes"]) >= 5, "fixture must clear sparse-fallback threshold"

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
    data = json.loads((site / "search-index.json").read_text(encoding="utf-8"))
    topic_entries = [e for e in data["entries"] if e.get("type") == "topic"]
    assert len(topic_entries) == len(g["nodes"])
    urls = {e["url"] for e in topic_entries}
    for node in g["nodes"]:
        assert node["site_url"] in urls
        assert (site / node["site_url"]).is_file()

    alpha = next(
        e for e in topic_entries
        if e["title"] == "Alpha" or topic_slug(e["title"]) == "alpha"
    )
    # Canonical title or a case-folded alias must be searchable.
    haystack = (alpha["title"] + " " + alpha["body"]).lower()
    assert "alpha" in haystack
