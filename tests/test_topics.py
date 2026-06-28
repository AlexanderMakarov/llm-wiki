"""Tests for the topic-first knowledge graph (#54).

Covers vocabulary clustering, co-occurrence edges + bridging sessions, the
min-sessions threshold, topic-page generation, and the synth-prompt
vocabulary injection.
"""

from __future__ import annotations

from pathlib import Path

from llmwiki.topics import build_topic_graph, derive_vocabulary, topic_slug
from llmwiki.topics_page import build_topic_pages


def _session(body_links: list[str], *, stem: str, project: str = "proj") -> str:
    links = " ".join(f"[[{t}]]" for t in body_links)
    return (
        f"---\ntitle: {stem}\nproject: {project}\n"
        f"source_file: raw/sessions/2026-01-01T00-00-{project}-{stem}.md\n"
        f"---\n\n## Summary\n{links}\n"
    )


def _make_wiki(tmp_path: Path, sessions: dict[str, list[str]]) -> Path:
    wiki = tmp_path / "wiki"
    src = wiki / "sources" / "proj"
    src.mkdir(parents=True)
    for stem, links in sessions.items():
        (src / f"{stem}.md").write_text(_session(links, stem=stem), encoding="utf-8")
    return wiki


def test_vocabulary_clusters_case_and_near_duplicates(tmp_path: Path):
    wiki = _make_wiki(tmp_path, {
        "s1": ["OpenClaw", "openclaw", "LLM-Wiki"],
        "s2": ["OpenClaw", "LLMWiki"],
        "s3": ["llm wiki"],
    })
    topics, raw_to_canonical = derive_vocabulary(wiki)
    names = {t.canonical for t in topics}
    # All case/near-dup spellings of the two scopes collapse to one each.
    assert raw_to_canonical["openclaw"] == raw_to_canonical["OpenClaw"]
    llm = {raw_to_canonical[s] for s in ("LLM-Wiki", "LLMWiki", "llm wiki")}
    assert len(llm) == 1
    assert len(names) == 2  # OpenClaw + the LLM-Wiki cluster
    openclaw = next(t for t in topics if t.canonical == "OpenClaw")
    assert openclaw.count == 2  # s1, s2 (presence, not occurrence)


def test_cooccurrence_edges_and_bridging_sessions(tmp_path: Path):
    wiki = _make_wiki(tmp_path, {
        "s1": ["OpenClaw", "Bun"],
        "s2": ["OpenClaw", "Tailscale"],
        "s3": ["OpenClaw", "Bun", "Tailscale"],
    })
    g = build_topic_graph(wiki, min_sessions=2)
    assert g["mode"] == "topic"
    ids = {n["id"] for n in g["nodes"]}
    assert ids == {"OpenClaw", "Bun", "Tailscale"}
    # Every node carries a topic page URL + its session list.
    openclaw = next(n for n in g["nodes"] if n["id"] == "OpenClaw")
    assert openclaw["site_url"] == "topics/openclaw.html"
    assert openclaw["session_count"] == 3
    # OpenClaw↔Bun share s1 + s3.
    edge = next(e for e in g["edges"]
                if {e["source"], e["target"]} == {"OpenClaw", "Bun"})
    assert edge["weight"] == 2
    assert set(edge["sessions"]) == {"s1", "s3"}


def test_min_sessions_threshold_drops_one_offs(tmp_path: Path):
    wiki = _make_wiki(tmp_path, {
        "s1": ["OpenClaw", "OneOff"],
        "s2": ["OpenClaw"],
    })
    g = build_topic_graph(wiki, min_sessions=2)
    assert {n["id"] for n in g["nodes"]} == {"OpenClaw"}
    g_all = build_topic_graph(wiki, min_sessions=1)
    assert "OneOff" in {n["id"] for n in g_all["nodes"]}


def test_build_topic_pages_writes_pages_and_index(tmp_path: Path):
    wiki = _make_wiki(tmp_path, {
        "s1": ["OpenClaw", "Bun"],
        "s2": ["OpenClaw", "Bun"],
    })
    g = build_topic_graph(wiki, min_sessions=2)
    out = tmp_path / "site"
    written = build_topic_pages(g, out)
    assert (out / "topics" / "openclaw.html").is_file()
    assert (out / "topics" / "index.html").is_file()
    page = (out / "topics" / "openclaw.html").read_text(encoding="utf-8")
    assert "Connected topics" in page and "Sessions" in page
    # Links to the connected topic's page + the bridging sessions.
    assert f'{topic_slug("Bun")}.html' in page
    assert "sessions/proj/" in page
    assert len(written) == len(g["nodes"]) + 1  # + index


def test_synth_prompt_injects_vocabulary(tmp_path: Path):
    from llmwiki.synth.pipeline import _inject_vocabulary

    wiki = _make_wiki(tmp_path, {
        "s1": ["OpenClaw", "Bun"],
        "s2": ["OpenClaw", "Bun"],
    })
    template = "Before\n{vocabulary}\n{body}\n{meta}\nAfter"
    out = _inject_vocabulary(template, wiki)
    assert "{vocabulary}" not in out
    # Lean regular-synth form: name + co-occurrence, NO aka noise.
    assert '<topic name="OpenClaw"' in out
    assert 'with="' in out  # OpenClaw co-occurs with Bun
    assert "aka=" not in out
    # Body/meta placeholders survive for the backend to fill.
    assert "{body}" in out and "{meta}" in out


def test_consolidation_cache_drives_merge_and_descriptions(tmp_path: Path):
    from llmwiki.topics_consolidate import parse_and_cache, render_consolidation_prompt
    from llmwiki.synth.pipeline import _inject_vocabulary

    wiki = _make_wiki(tmp_path, {
        "s1": ["kbbuilder", "code-kbbuilder", "OpenClaw"],
        "s2": ["kbbuilder", "OpenClaw"],
        "s3": ["code-kbbuilder", "OpenClaw"],
    })
    # The consolidation prompt is rendered from the live candidates.
    prompt = render_consolidation_prompt(wiki)
    assert "<candidate" in prompt and 'name="OpenClaw"' in prompt

    # Simulate the LLM reply: merge code-kbbuilder into kbbuilder + describe.
    reply = (
        '{"topics": ['
        '{"canonical": "kbbuilder", "description": "Doc-ingest CLI.",'
        ' "aliases": ["code-kbbuilder"]},'
        '{"canonical": "OpenClaw", "description": "VPS agent platform."}'
        '], "dropped": []}'
    )
    parse_and_cache(reply, wiki)

    g = build_topic_graph(wiki, min_sessions=1)
    ids = {n["id"] for n in g["nodes"]}
    assert "kbbuilder" in ids and "code-kbbuilder" not in ids  # merged via cache
    kb = next(n for n in g["nodes"] if n["id"] == "kbbuilder")
    assert kb["description"] == "Doc-ingest CLI."
    assert kb["session_count"] == 3  # s1, s2, s3 (code-kbbuilder folded in)

    # Regular synth vocab now carries the cached description.
    out = _inject_vocabulary("{vocabulary}\n{body}\n{meta}", wiki)
    assert 'name="kbbuilder" desc="Doc-ingest CLI."' in out


def test_consolidation_dropped_excluded_from_graph(tmp_path: Path):
    from llmwiki.topics_consolidate import parse_and_cache

    wiki = _make_wiki(tmp_path, {
        "s1": ["OpenClaw", "Bash"],
        "s2": ["OpenClaw", "Bash"],
    })
    reply = (
        '{"topics": [{"canonical": "OpenClaw", "description": "Agent platform.",'
        ' "aliases": []}], "dropped": ["Bash"]}'
    )
    parse_and_cache(reply, wiki)
    g = build_topic_graph(wiki, min_sessions=1)
    assert {n["id"] for n in g["nodes"]} == {"OpenClaw"}


def test_display_aliases_collapse_spelling_variants():
    from llmwiki.topics_page import _display_aliases

    out = _display_aliases(
        "Evrika",
        ["Evrika", "Armenian Language", "ArmenianLanguage", "Bilingual-Education",
         "Bilingual Education"],
    )
    assert out == ["Armenian Language", "Bilingual Education"]


def test_topic_page_alias_note_uses_hover_not_inline_explanation(tmp_path: Path):
    g = {
        "mode": "topic",
        "nodes": [{
            "id": "Evrika",
            "aliases": ["Evrika", "Armenian Language", "ArmenianLanguage"],
            "sessions": ["s1"],
            "session_count": 1,
            "degree": 0,
        }],
        "edges": [],
        "sessions": {"s1": {"title": "s1", "url": "sessions/proj/s1.html"}},
        "stats": {"total_sessions": 1},
    }
    out = tmp_path / "site"
    build_topic_pages(g, out)
    page = (out / "topics" / "evrika.html").read_text(encoding="utf-8")
    assert 'class="topic-aliases-label" title="' in page
    assert "Also tagged as</strong></span>:" in page
    assert "before consolidation merged them under this topic." in page
    assert "[[wikilinks]]</code> before consolidation" not in page
