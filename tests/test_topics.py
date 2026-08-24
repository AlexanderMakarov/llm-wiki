"""Tests for the topic-first knowledge graph (#54).

Covers vocabulary clustering, co-occurrence edges + bridging sessions, the
min-sessions threshold, topic-page generation, and the synth-prompt
vocabulary injection.
"""

from __future__ import annotations

from pathlib import Path

from llmwiki.synth.pipeline import _inject_vocabulary
from llmwiki.topics import (
    Topic,
    TopicPage,
    build_topic_graph,
    derive_vocabulary,
    resolve_topic_page,
    topic_kind_lookup,
    topic_slug,
)
from llmwiki.topics_consolidate import (
    parse_and_cache,
    prepare_known_names,
    render_consolidation_prompt,
)
from llmwiki.topics_page import (
    KIND_OTHER_LABEL,
    _display_aliases,
    _identity_line,
    build_topic_pages,
)


def _session(
    body_links: list[str], *, stem: str, project: str = "proj", date: str = ""
) -> str:
    links = " ".join(f"[[{t}]]" for t in body_links)
    date_line = f"date: {date}\n" if date else ""
    return (
        f"---\ntitle: {stem}\nproject: {project}\n{date_line}"
        f"source_file: raw/sessions/2026-01-01T00-00-{project}-{stem}.md\n"
        f"---\n\n## Summary\n{links}\n"
    )


def _make_wiki(
    tmp_path: Path,
    sessions: dict[str, list[str]],
    *,
    dates: dict[str, str] | None = None,
) -> Path:
    wiki = tmp_path / "wiki"
    src = wiki / "sources" / "proj"
    src.mkdir(parents=True)
    for stem, links in sessions.items():
        (src / f"{stem}.md").write_text(
            _session(links, stem=stem, date=(dates or {}).get(stem, "")),
            encoding="utf-8",
        )
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
    assert "Connected topics" in page
    assert '<h2>Connected topics</h2>\n<div class="content">\n<ul>' in page
    assert 'class="collapse-section topic-sources"' in page
    assert 'summary>Sources<span class="collapse-section-count"' in page
    assert "<h3>Sessions</h3>" in page
    assert "topic-neighbor-list" not in page
    assert "provenance-sources" not in page
    # Links to the connected topic's page + the bridging sessions.
    assert f'{topic_slug("Bun")}.html' in page
    assert "sessions/proj/" in page
    assert len(written) == len(g["nodes"]) + 1  # + index


def test_topic_page_sources_splits_sessions_and_documents(tmp_path: Path):
    """Graph evidence under Sources partitions by compiled URL (#122 UX)."""
    graph = {
        "nodes": [
            {
                "id": "Mixed",
                "kind": "concepts",
                "session_count": 2,
                "degree": 0,
                "sessions": ["sess-a", "doc-b"],
                "aliases": [],
                "site_url": "topics/mixed.html",
            }
        ],
        "edges": [],
        "sessions": {
            "sess-a": {
                "title": "Chat session",
                "url": "sessions/demo/sess-a.html",
                "date": "2026-01-01",
            },
            "doc-b": {
                "title": "Spec doc",
                "url": "documents/demo/doc-b.html",
                "date": "2026-01-02",
            },
        },
        "stats": {"total_sessions": 2},
    }
    out = tmp_path / "site"
    written = build_topic_pages(graph, out)
    page = (out / "topics" / "mixed.html").read_text(encoding="utf-8")
    assert 'class="collapse-section topic-sources"' in page
    assert 'summary>Sources<span class="collapse-section-count">2</span>' in page
    assert "<h3>Sessions</h3>" in page
    assert "<h3>Documents</h3>" in page
    assert 'class="collapse-section-list"' in page
    assert "topic-session-list" not in page
    assert "topic-document-list" not in page
    assert 'href="../sessions/demo/sess-a.html"' in page
    assert 'href="../documents/demo/doc-b.html"' in page
    assert "provenance-sources" not in page
    assert "<h2>Sources</h2>" not in page
    assert (out / "topics" / "index.html") in written


def test_synth_prompt_injects_vocabulary(tmp_path: Path):

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


def test_parse_and_cache_persists_kind_when_present(tmp_path: Path):
    wiki = _make_wiki(tmp_path, {"s1": ["OpenClaw"], "s2": ["OpenClaw"]})
    reply = (
        '{"topics": [{"canonical": "OpenClaw", "kind": "entity",'
        ' "description": "Agent platform.", "aliases": []}], "dropped": []}'
    )
    cache = parse_and_cache(reply, wiki)
    assert cache["topics"][0]["kind"] == "entity"


def test_parse_and_cache_tolerates_missing_kind(tmp_path: Path):
    wiki = _make_wiki(tmp_path, {"s1": ["OpenClaw"], "s2": ["OpenClaw"]})
    reply = (
        '{"topics": [{"canonical": "OpenClaw", "description": "Agent platform.",'
        ' "aliases": []}], "dropped": []}'
    )
    cache = parse_and_cache(reply, wiki)
    assert "kind" not in cache["topics"][0]


def test_prepare_known_names_skips_non_llm_backend(tmp_path: Path):
    wiki = _make_wiki(tmp_path, {
        "s1": ["OpenClaw", "Bun"],
        "s2": ["OpenClaw", "Bun"],
    })

    class _Spy:
        is_llm = False
        calls = 0

        def synthesize_source_page(self, *a, **k):
            self.calls += 1
            raise AssertionError("non-LLM backend must not be called")

    spy = _Spy()
    prepare_known_names(wiki, spy)
    assert spy.calls == 0
    assert not (tmp_path / ".llmwiki-topics.json").is_file()


def test_prepare_known_names_calls_llm_once_and_caches(tmp_path: Path):
    wiki = _make_wiki(tmp_path, {
        "s1": ["OpenClaw", "Bun"],
        "s2": ["OpenClaw", "Bun"],
    })

    class _FakeLlm:
        is_llm = True

        def __init__(self) -> None:
            self.calls: list[dict] = []

        def synthesize_source_page(self, raw_body, meta, prompt_template):
            self.calls.append({"slug": meta.get("slug"), "prompt": prompt_template})
            return (
                '{"topics": [{"canonical": "OpenClaw", "kind": "entity",'
                ' "description": "Agent platform.", "aliases": []},'
                '{"canonical": "Bun", "kind": "entity",'
                ' "description": "JS runtime.", "aliases": []}],'
                ' "dropped": []}'
            )

    backend = _FakeLlm()
    prepare_known_names(wiki, backend)
    assert len(backend.calls) == 1
    assert backend.calls[0]["slug"] == "known-names"
    assert "<candidate" in backend.calls[0]["prompt"]
    cache = (tmp_path / ".llmwiki-topics.json").read_text(encoding="utf-8")
    assert '"kind": "entity"' in cache
    assert "OpenClaw" in cache


def test_prepare_known_names_warns_on_failure_without_raising(tmp_path: Path, capsys):
    wiki = _make_wiki(tmp_path, {
        "s1": ["OpenClaw"],
        "s2": ["OpenClaw"],
    })

    class _Boom:
        is_llm = True

        def synthesize_source_page(self, *a, **k):
            raise RuntimeError("provider down")

    prepare_known_names(wiki, _Boom())  # must not raise
    err = capsys.readouterr().err
    assert "prepare_known_names failed" in err
    assert not (tmp_path / ".llmwiki-topics.json").is_file()


def test_consolidation_dropped_excluded_from_graph(tmp_path: Path):

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

    out = _display_aliases(
        "Evrika",
        ["Evrika", "Armenian Language", "ArmenianLanguage", "Bilingual-Education",
         "Bilingual Education"],
    )
    assert out == ["Armenian Language", "Bilingual Education"]


def _page(kind: str, slug: str) -> TopicPage:
    return TopicPage(kind=kind, slug=slug, path=f"wiki/{kind}/{slug}.md")


def test_resolve_topic_page_prefers_canonical_spelling():
    lookup = {"hazel": _page("entities", "Hazel"),
              "batching": _page("concepts", "Batching")}
    topic = Topic(canonical="Hazel", aliases={"Hazel", "Batching"})
    found = resolve_topic_page(topic, lookup)
    assert found is not None
    assert (found.kind, found.slug) == ("entities", "Hazel")


def test_resolve_topic_page_falls_back_to_aliases_in_sorted_order():
    lookup = {"alpha": _page("concepts", "Alpha"), "zeta": _page("entities", "Zeta")}
    topic = Topic(canonical="Unlisted", aliases={"Zeta", "Alpha"})
    found = resolve_topic_page(topic, lookup)
    assert found is not None
    assert found.slug == "Alpha"  # sorted() puts Alpha before Zeta


def test_resolve_topic_page_returns_none_when_nothing_matches():
    topic = Topic(canonical="Unfiled", aliases={"unfiled"})
    assert resolve_topic_page(topic, {"hazel": _page("entities", "Hazel")}) is None


def test_topic_kind_lookup_derives_kind_from_the_folder_not_frontmatter(
    tmp_path: Path,
):
    """Pre-#102 project pages carry `type: entity`; the folder still wins."""
    wiki = tmp_path / "wiki"
    (wiki / "projects").mkdir(parents=True)
    (wiki / "projects" / "legacy-app.md").write_text(
        '---\ntitle: "legacy-app"\ntype: entity\nentity_type: project\n---\n\n'
        "# legacy-app\n",
        encoding="utf-8",
    )
    lookup = topic_kind_lookup(wiki)
    record = lookup["legacy-app"]
    assert record.kind == "projects"
    assert record.slug == "legacy-app"
    assert record.path == "wiki/projects/legacy-app.md"
    assert record.site_url == "projects/legacy-app.html"
    # The page records no review date, so none is invented.
    assert record.last_updated is None


def test_nodes_carry_the_backing_page_and_omit_it_when_undescribed(tmp_path: Path):
    wiki = _make_wiki(tmp_path, {
        "s1": ["Hazel", "Unfiled"],
        "s2": ["Hazel", "Unfiled"],
    })
    (wiki / "entities").mkdir(parents=True)
    (wiki / "entities" / "Hazel.md").write_text(
        '---\ntitle: "Hazel"\ntype: entity\n---\n\n# Hazel\n', encoding="utf-8"
    )
    g = build_topic_graph(wiki, min_sessions=2)
    hazel = next(n for n in g["nodes"] if n["id"] == "Hazel")
    assert hazel["kind"] == "entities"
    assert hazel["wiki_slug"] == "Hazel"
    assert hazel["wiki_path"] == "wiki/entities/Hazel.md"
    # Entity pages compile to no site page, so no backing URL is carried.
    assert "wiki_site_url" not in hazel
    # The node's own site_url still points at the generated topic page.
    assert hazel["site_url"] == "topics/hazel.html"

    unfiled = next(n for n in g["nodes"] if n["id"] == "Unfiled")
    assert unfiled["kind"] == "other"
    assert "wiki_slug" not in unfiled
    assert "wiki_path" not in unfiled
    assert "wiki_site_url" not in unfiled


def test_identity_line_renders_only_the_elements_present():
    full = _identity_line(
        {"id": "Hazel", "kind": "entities", "session_count": 4}, 3
    )
    assert full == (
        '<span class="topic-kind-chip">Entity</span> · 3 connected topics'
        " · 4 sources · <code>hazel</code>"
    )
    # No backing page → the chip names that state rather than disappearing.
    unfiled = f'<span class="topic-kind-chip">{KIND_OTHER_LABEL}</span>'
    assert _identity_line({"id": "Unfiled", "kind": "other"}, 0) == (
        f"{unfiled} · 0 connected topics · <code>unfiled</code>"
    )
    # A node missing `kind` entirely behaves the same way.
    assert unfiled in _identity_line({"id": "Unfiled"}, 1)


# ─── FR2: activity vs review dates ────────────────────────────────────


def test_nodes_derive_first_and_last_seen_from_the_session_dates(tmp_path: Path):
    wiki = _make_wiki(
        tmp_path,
        {"s1": ["Hazel"], "s2": ["Hazel"], "s3": ["Hazel"]},
        dates={"s1": "2026-03-04", "s2": "2026-01-09", "s3": "2026-02-17"},
    )
    g = build_topic_graph(wiki, min_sessions=2)
    hazel = next(n for n in g["nodes"] if n["id"] == "Hazel")
    assert hazel["first_seen"] == "2026-01-09"
    assert hazel["last_seen"] == "2026-03-04"
    # The per-session date is carried so nothing has to re-scan the wiki.
    assert g["sessions"]["s2"]["date"] == "2026-01-09"


def test_nodes_derive_activity_only_from_the_sessions_mentioning_the_topic(
    tmp_path: Path,
):
    wiki = _make_wiki(
        tmp_path,
        {"s1": ["Hazel"], "s2": ["Hazel"], "s3": ["Batching"], "s4": ["Batching"]},
        dates={"s1": "2026-01-09", "s2": "2026-02-17",
               "s3": "2026-05-01", "s4": "2026-06-02"},
    )
    g = build_topic_graph(wiki, min_sessions=2)
    nodes = {n["id"]: n for n in g["nodes"]}
    assert (nodes["Hazel"]["first_seen"], nodes["Hazel"]["last_seen"]) == (
        "2026-01-09", "2026-02-17")
    assert (nodes["Batching"]["first_seen"], nodes["Batching"]["last_seen"]) == (
        "2026-05-01", "2026-06-02")


def test_nodes_omit_activity_dates_when_no_session_carries_one(tmp_path: Path):
    wiki = _make_wiki(tmp_path, {"s1": ["Hazel"], "s2": ["Hazel"]})
    g = build_topic_graph(wiki, min_sessions=2)
    hazel = next(n for n in g["nodes"] if n["id"] == "Hazel")
    assert "first_seen" not in hazel
    assert "last_seen" not in hazel
    assert g["sessions"]["s1"]["date"] == ""


def test_node_review_date_comes_from_the_backing_page_not_the_sessions(
    tmp_path: Path,
):
    wiki = _make_wiki(
        tmp_path,
        {"s1": ["Hazel", "Unfiled"], "s2": ["Hazel", "Unfiled"]},
        dates={"s1": "2026-01-09", "s2": "2026-02-17"},
    )
    (wiki / "entities").mkdir(parents=True)
    (wiki / "entities" / "Hazel.md").write_text(
        '---\ntitle: "Hazel"\ntype: entity\nlast_updated: 2026-07-30\n---\n\n# Hazel\n',
        encoding="utf-8",
    )
    g = build_topic_graph(wiki, min_sessions=2)
    nodes = {n["id"]: n for n in g["nodes"]}
    assert nodes["Hazel"]["last_updated"] == "2026-07-30"
    assert nodes["Hazel"]["last_seen"] == "2026-02-17"  # activity is separate
    # No backing page → no review date, and none borrowed from the sessions.
    assert "last_updated" not in nodes["Unfiled"]
    assert nodes["Unfiled"]["last_seen"] == "2026-02-17"


def test_identity_line_labels_activity_and_review_as_different_facts():
    line = _identity_line(
        {"id": "Hazel", "kind": "entities", "session_count": 4,
         "first_seen": "2026-01-09", "last_seen": "2026-02-17",
         "last_updated": "2026-07-30"},
        3,
    )
    assert line == (
        '<span class="topic-kind-chip">Entity</span>'
        ' · <span class="topic-activity">Active 2026-01-09 – 2026-02-17</span>'
        ' · <span class="topic-reviewed">Reviewed 2026-07-30</span>'
        " · 3 connected topics · 4 sources · <code>hazel</code>"
    )


def test_identity_line_collapses_a_single_day_of_activity():
    line = _identity_line(
        {"id": "Hazel", "first_seen": "2026-01-09", "last_seen": "2026-01-09"}, 0
    )
    assert '<span class="topic-activity">Active 2026-01-09</span>' in line
    assert "–" not in line


def test_identity_line_omits_each_date_independently():
    # Activity only — no review date, and no label standing in for one.
    activity_only = _identity_line(
        {"id": "Hazel", "first_seen": "2026-01-09", "last_seen": "2026-02-17"}, 1
    )
    assert "topic-activity" in activity_only
    assert "Reviewed" not in activity_only

    # Review only — the page was curated but no session carries a date.
    review_only = _identity_line({"id": "Hazel", "last_updated": "2026-07-30"}, 1)
    assert "topic-reviewed" in review_only
    assert "Active" not in review_only

    # Neither — no date, no placeholder, no dangling separator.
    neither = _identity_line({"id": "Unfiled"}, 0)
    assert neither == (
        f'<span class="topic-kind-chip">{KIND_OTHER_LABEL}</span>'
        " · 0 connected topics · <code>unfiled</code>"
    )


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
