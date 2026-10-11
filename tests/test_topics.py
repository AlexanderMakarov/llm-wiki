"""Tests for the topic-first knowledge graph (#54).

Covers vocabulary clustering, co-occurrence edges + bridging sessions, the
min-sessions threshold, topic-page generation, and the synth-prompt
vocabulary injection.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

import pytest

from llmwiki.candidates import discard
from llmwiki.candidates_harvest import harvest_targets, write_stubs
from llmwiki.synth.pipeline import PROMPT_TEMPLATE_PATH, _inject_vocabulary
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
    CACHE_VERSION,
    DEFAULT_KNOWN_NAMES_CANDIDATE_CAP,
    DEFAULT_KNOWN_NAMES_TIMEOUT_FLOOR,
    KnownNamesConfig,
    build_candidates,
    cache_path,
    candidate_source_sig,
    cap_candidates,
    inputs_fingerprint,
    load_cache,
    parse_and_cache,
    prepare_known_names,
    reach_bucket,
    render_consolidation_prompt,
    resolve_known_names_config,
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


_CURATED_TYPE = {"entities": "entity", "concepts": "concept"}


def _curated_page_file(wiki: Path, kind: str, name: str, *, folder: str = "") -> Path:
    """Write one curated wiki page (`entities/`/`concepts/`) and return its path."""
    page = wiki / (folder or kind) / f"{name}.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(
        f'---\ntitle: "{name}"\ntype: {_CURATED_TYPE[kind]}\n'
        f"last_updated: 2026-02-03\n---\n\n# {name}\n",
        encoding="utf-8",
    )
    return page


def test_curated_entity_with_no_inbound_links_is_a_node_only_under_the_flag(
    tmp_path: Path,
):
    """#248 FR1: a reviewed page nothing cites still reaches the reader."""
    wiki = _make_wiki(tmp_path, {
        "s1": ["OpenClaw"],
        "s2": ["OpenClaw"],
    })
    _curated_page_file(wiki, "entities", "Python")

    default = build_topic_graph(wiki, min_sessions=2)
    assert "Python" not in {n["id"] for n in default["nodes"]}

    bypassed = build_topic_graph(wiki, min_sessions=2, include_curated_pages=True)
    assert {n["id"] for n in bypassed["nodes"]} == {"OpenClaw", "Python"}


def test_curated_concept_with_one_inbound_link_is_a_node_under_the_flag(
    tmp_path: Path,
):
    wiki = _make_wiki(tmp_path, {
        "s1": ["OpenClaw", "Batching"],
        "s2": ["OpenClaw"],
    })
    _curated_page_file(wiki, "concepts", "Batching")

    assert "Batching" not in {
        n["id"] for n in build_topic_graph(wiki, min_sessions=2)["nodes"]
    }
    g = build_topic_graph(wiki, min_sessions=2, include_curated_pages=True)
    batching = next(n for n in g["nodes"] if n["id"] == "Batching")
    assert batching["kind"] == "concepts"
    assert batching["session_count"] == 1


def test_derived_one_off_without_a_curated_page_stays_out_under_the_flag(
    tmp_path: Path,
):
    """The noise guard: the bypass admits curated pages, not every one-off."""
    wiki = _make_wiki(tmp_path, {
        "s1": ["OpenClaw", "OneOff"],
        "s2": ["OpenClaw"],
    })
    _curated_page_file(wiki, "entities", "Python")

    g = build_topic_graph(wiki, min_sessions=2, include_curated_pages=True)
    assert {n["id"] for n in g["nodes"]} == {"OpenClaw", "Python"}


def test_bypassed_node_carries_page_metadata_and_no_edges(tmp_path: Path):
    wiki = _make_wiki(tmp_path, {
        "s1": ["OpenClaw", "Bun"],
        "s2": ["OpenClaw", "Bun"],
    })
    _curated_page_file(wiki, "entities", "Python")

    g = build_topic_graph(wiki, min_sessions=2, include_curated_pages=True)
    python = next(n for n in g["nodes"] if n["id"] == "Python")
    assert python["kind"] == "entities"
    assert python["wiki_path"] == "wiki/entities/Python.md"
    assert python["site_url"] == "topics/python.html"
    assert python["session_count"] == 0
    assert python["degree"] == 0
    assert python["sessions"] == []
    assert python["last_updated"] == "2026-02-03"
    # Zero sessions means zero activity dates, not empty strings.
    assert "first_seen" not in python and "last_seen" not in python
    assert not [e for e in g["edges"]
                if "Python" in (e["source"], e["target"])]


def test_archived_curated_pages_never_become_nodes(tmp_path: Path):
    """`wiki/archive/` is cold storage — a dismissal must stay dismissed."""
    wiki = _make_wiki(tmp_path, {"s1": ["OpenClaw"], "s2": ["OpenClaw"]})
    _curated_page_file(wiki, "entities", "Dismissed", folder="archive/entities")

    g = build_topic_graph(wiki, min_sessions=2, include_curated_pages=True)
    assert {n["id"] for n in g["nodes"]} == {"OpenClaw"}


def test_underscore_context_stubs_never_become_nodes(tmp_path: Path):
    """`_context.md` orients assistants; it is not knowledge to publish."""
    wiki = _make_wiki(tmp_path, {"s1": ["OpenClaw"], "s2": ["OpenClaw"]})
    _curated_page_file(wiki, "entities", "_context")
    _curated_page_file(wiki, "concepts", "_context")

    g = build_topic_graph(wiki, min_sessions=2, include_curated_pages=True)
    assert {n["id"] for n in g["nodes"]} == {"OpenClaw"}


def test_curated_bypass_keeps_node_and_edge_order_deterministic(tmp_path: Path):
    """#150: two runs over one vault must agree byte for byte."""
    wiki = _make_wiki(tmp_path, {
        "s1": ["OpenClaw", "Bun", "Tailscale"],
        "s2": ["OpenClaw", "Bun"],
        "s3": ["OpenClaw", "Tailscale"],
    })
    for name in ("Python", "SQLite", "Ollama"):
        _curated_page_file(wiki, "entities", name)
    _curated_page_file(wiki, "concepts", "Batching")

    first = build_topic_graph(wiki, min_sessions=2, include_curated_pages=True)
    second = build_topic_graph(wiki, min_sessions=2, include_curated_pages=True)
    assert [n["id"] for n in first["nodes"]] == [n["id"] for n in second["nodes"]]
    assert first["edges"] == second["edges"]
    # Zero-count seeds land last, alphabetically, with no bespoke sort.
    assert [n["id"] for n in first["nodes"]][-4:] == [
        "Batching", "Ollama", "Python", "SQLite",
    ]


def test_build_candidates_ignores_the_curated_bypass(tmp_path: Path):
    """The synth path must keep the default — promoted names stay settled.

    If the site's bypass leaked into `topics_consolidate`, already-promoted
    entities and concepts would re-enter the candidate stream and the
    consolidator would be asked to re-decide them (the #146 bug class).
    """
    sessions = {"s1": ["OpenClaw", "Bun"], "s2": ["OpenClaw", "Bun"]}
    before = _make_wiki(tmp_path / "before", sessions)
    after = _make_wiki(tmp_path / "after", sessions)
    _curated_page_file(after, "entities", "Python")
    _curated_page_file(after, "concepts", "Batching")

    assert build_candidates(after) == build_candidates(before)
    assert {c["name"] for c in build_candidates(after)} == {"OpenClaw", "Bun"}


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


def _topic_page(wiki: Path, folder: str, name: str, *, page_type: str) -> None:
    path = wiki / folder / f"{name}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"---\ntitle: \"{name}\"\ntype: {page_type}\nlast_updated: 2026-08-01\n---\n\n"
        f"# {name}\n\n## Connections\n- [[demo]]\n",
        encoding="utf-8",
    )


def test_inject_vocabulary_emits_cache_kind(tmp_path: Path):
    wiki = _make_wiki(tmp_path, {
        "s1": ["OpenClaw", "Bun"],
        "s2": ["OpenClaw", "Bun"],
    })
    reply = (
        '{"topics": [{"canonical": "OpenClaw", "kind": "entity",'
        ' "description": "Agent platform.", "aliases": []},'
        '{"canonical": "Bun", "kind": "concept",'
        ' "description": "JS runtime.", "aliases": []}], "dropped": []}'
    )
    parse_and_cache(reply, wiki)
    out = _inject_vocabulary("{vocabulary}", wiki)
    assert 'name="OpenClaw" kind="entity"' in out
    assert 'name="Bun" kind="concept"' in out
    assert "aka=" not in out


def test_inject_vocabulary_page_filing_fallback(tmp_path: Path):
    wiki = _make_wiki(tmp_path, {
        "s1": ["OpenClaw", "Bun"],
        "s2": ["OpenClaw", "Bun"],
    })
    _topic_page(wiki, "entities", "OpenClaw", page_type="entity")
    _topic_page(wiki, "candidates/concepts", "Bun", page_type="concept")
    out = _inject_vocabulary("{vocabulary}", wiki)
    assert 'name="OpenClaw" kind="entity"' in out
    assert 'name="Bun" kind="concept"' in out


def test_inject_vocabulary_cache_kind_wins_over_page_filing(tmp_path: Path):
    wiki = _make_wiki(tmp_path, {
        "s1": ["OpenClaw", "Bun"],
        "s2": ["OpenClaw", "Bun"],
    })
    # Page says concept; cache says entity — cache wins.
    _topic_page(wiki, "concepts", "OpenClaw", page_type="concept")
    reply = (
        '{"topics": [{"canonical": "OpenClaw", "kind": "entity",'
        ' "description": "Agent platform.", "aliases": []},'
        '{"canonical": "Bun", "description": "JS runtime.", "aliases": []}],'
        ' "dropped": []}'
    )
    parse_and_cache(reply, wiki)
    out = _inject_vocabulary("{vocabulary}", wiki)
    assert 'name="OpenClaw" kind="entity"' in out
    assert 'name="OpenClaw" kind="concept"' not in out


def test_inject_vocabulary_omits_kind_on_ambiguous_dual_filing(tmp_path: Path):
    wiki = _make_wiki(tmp_path, {
        "s1": ["OpenClaw", "Bun"],
        "s2": ["OpenClaw", "Bun"],
    })
    _topic_page(wiki, "entities", "OpenClaw", page_type="entity")
    _topic_page(wiki, "concepts", "OpenClaw", page_type="concept")
    out = _inject_vocabulary("{vocabulary}", wiki)
    openclaw = next(
        line for line in out.splitlines() if 'name="OpenClaw"' in line
    )
    assert "kind=" not in openclaw
    # Bun has no filing and no cache kind — also omit.
    bun = next(line for line in out.splitlines() if 'name="Bun"' in line)
    assert "kind=" not in bun


def test_source_page_prompt_forbids_free_form_kinds_and_requires_copy() -> None:
    """#257 FR2: prompt documents kind= and forbids free-form Connections kinds."""
    text = PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")
    assert 'kind="entity|concept"' in text
    assert "no free-form type nouns" in text
    assert "copy that kind" in text


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

        def synthesize_source_page(self, raw_body, meta, prompt_template, **_kwargs):
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
    assert "mode=full" in err
    assert "sent=1" in err
    assert "reply=0 B" in err
    assert "duration=" in err
    assert not (tmp_path / ".llmwiki-topics.json").is_file()


# ─── #264 known-names config (# @spec: 325-known-names-prep) ─────────────


@pytest.mark.parametrize(
    "cfg",
    [None, {}, {"synthesis": {}}, {"synthesis": None}, {"synthesis": {"known_names": {}}}],
)
def test_known_names_config_defaults_when_unset(
    cfg: dict | None, caplog: pytest.LogCaptureFixture
) -> None:
    """Unset known_names keys resolve to cap 150 and max(600, page timeout)."""
    with caplog.at_level(logging.WARNING, logger="llmwiki.topics_consolidate"):
        resolved = resolve_known_names_config(cfg, backend_page_timeout=120)
    assert resolved == KnownNamesConfig(
        candidate_cap=DEFAULT_KNOWN_NAMES_CANDIDATE_CAP,
        timeout=DEFAULT_KNOWN_NAMES_TIMEOUT_FLOOR,
    )
    assert caplog.records == []


def test_known_names_timeout_default_tracks_higher_page_timeout(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """When the backend page timeout exceeds 600, the known-names default follows it."""
    with caplog.at_level(logging.WARNING, logger="llmwiki.topics_consolidate"):
        resolved = resolve_known_names_config(None, backend_page_timeout=900)
    assert resolved.timeout == 900
    assert resolved.candidate_cap == DEFAULT_KNOWN_NAMES_CANDIDATE_CAP
    assert caplog.records == []


def test_known_names_config_honours_explicit_values(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Explicit positive ints pass through without clamping or warnings."""
    cfg = {"synthesis": {"known_names": {"candidate_cap": 40, "timeout": 180}}}
    with caplog.at_level(logging.WARNING, logger="llmwiki.topics_consolidate"):
        resolved = resolve_known_names_config(cfg, backend_page_timeout=900)
    assert resolved == KnownNamesConfig(candidate_cap=40, timeout=180)
    assert caplog.records == []


@pytest.mark.parametrize("value", [0, -1, "two", 2.5, True, False, None, []])
def test_known_names_candidate_cap_falls_back_with_warning(
    value: object, caplog: pytest.LogCaptureFixture
) -> None:
    """Invalid candidate_cap warns and falls back to 150 rather than crashing synth."""
    cfg = {"synthesis": {"known_names": {"candidate_cap": value}}}
    with caplog.at_level(logging.WARNING, logger="llmwiki.topics_consolidate"):
        resolved = resolve_known_names_config(cfg, backend_page_timeout=120)
    assert resolved.candidate_cap == DEFAULT_KNOWN_NAMES_CANDIDATE_CAP
    assert resolved.timeout == DEFAULT_KNOWN_NAMES_TIMEOUT_FLOOR
    assert len(caplog.records) == 1
    assert "synthesis.known_names.candidate_cap" in caplog.records[0].getMessage()


@pytest.mark.parametrize("value", [0, -1, "slow", 1.5, True, False, None, {}])
def test_known_names_timeout_falls_back_with_warning(
    value: object, caplog: pytest.LogCaptureFixture
) -> None:
    """Invalid timeout warns and falls back to max(600, page timeout)."""
    cfg = {"synthesis": {"known_names": {"timeout": value}}}
    with caplog.at_level(logging.WARNING, logger="llmwiki.topics_consolidate"):
        resolved = resolve_known_names_config(cfg, backend_page_timeout=900)
    assert resolved.timeout == 900
    assert resolved.candidate_cap == DEFAULT_KNOWN_NAMES_CANDIDATE_CAP
    assert len(caplog.records) == 1
    assert "synthesis.known_names.timeout" in caplog.records[0].getMessage()


def test_known_names_config_rejects_non_mapping_block(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A mistyped known_names value (not a dict) falls back to both defaults."""
    cfg = {"synthesis": {"known_names": "cap=150"}}
    with caplog.at_level(logging.WARNING, logger="llmwiki.topics_consolidate"):
        resolved = resolve_known_names_config(cfg, backend_page_timeout=120)
    assert resolved == KnownNamesConfig(
        candidate_cap=DEFAULT_KNOWN_NAMES_CANDIDATE_CAP,
        timeout=DEFAULT_KNOWN_NAMES_TIMEOUT_FLOOR,
    )
    assert len(caplog.records) == 1
    assert "synthesis.known_names" in caplog.records[0].getMessage()


def test_cap_candidates_orders_by_reach_then_name() -> None:
    """Cap sorts sessions desc, name asc, then truncates (#264 / FR1)."""
    rows = [
        {"name": "Zebra", "sessions": 2},
        {"name": "Alpha", "sessions": 5},
        {"name": "MidB", "sessions": 3},
        {"name": "MidA", "sessions": 3},
        {"name": "Beta", "sessions": 4},
    ]
    capped = cap_candidates(rows, 3)
    assert [c["name"] for c in capped] == ["Alpha", "Beta", "MidA"]
    # Original list is not mutated; below-cut names stay available to callers.
    assert [c["name"] for c in rows] == ["Zebra", "Alpha", "MidB", "MidA", "Beta"]


@pytest.mark.parametrize(
    ("sessions", "expected"),
    [
        (1, "1"),
        (2, "2-3"),
        (3, "2-3"),
        (4, "4-7"),
        (7, "4-7"),
        (8, "8-15"),
        (15, "8-15"),
        (16, "16-31"),
        (31, "16-31"),
        (32, "32+"),
        (100, "32+"),
    ],
)
def test_reach_bucket_boundaries(sessions: int, expected: str) -> None:
    """Reach buckets only flip on meaningful growth (#264 / FR2).

    # @spec: 325-known-names-prep
    """
    assert reach_bucket(sessions) == expected


def test_candidate_source_sig_casefolds_and_sorts_aka() -> None:
    """Signature is casefold(name) | sorted casefold(aka) | bucket.

    # @spec: 325-known-names-prep
    """
    sig = candidate_source_sig(
        {"name": "OpenClaw", "sessions": 5, "aka": ["OC", "open-claw", "Bun"]}
    )
    assert sig == "openclaw | bun,oc,open-claw | 4-7"


def test_inputs_fingerprint_is_sha256_of_sorted_sigs() -> None:
    """Capped-set fingerprint is SHA-256 hex over sorted signatures.

    # @spec: 325-known-names-prep
    """
    rows = [
        {"name": "Zed", "sessions": 2, "aka": []},
        {"name": "Alpha", "sessions": 10, "aka": ["A"]},
    ]
    sigs = sorted(candidate_source_sig(c) for c in rows)
    expected = hashlib.sha256("\n".join(sigs).encode("utf-8")).hexdigest()
    assert inputs_fingerprint(rows) == expected
    assert len(inputs_fingerprint(rows)) == 64
    # Order of the input list must not change the fingerprint.
    assert inputs_fingerprint(list(reversed(rows))) == expected


def test_parse_and_cache_writes_v2_with_fingerprint_and_source_sig(
    tmp_path: Path,
) -> None:
    """Successful write emits version 2 + fingerprint + per-topic source_sig.

    # @spec: 325-known-names-prep
    """
    wiki = _make_wiki(tmp_path, {"s1": ["OpenClaw"], "s2": ["OpenClaw"]})
    candidate = {"name": "OpenClaw", "sessions": 2, "aka": ["OC"]}
    sig = candidate_source_sig(candidate)
    fp = inputs_fingerprint([candidate])
    reply = (
        '{"topics": [{"canonical": "OpenClaw", "kind": "entity",'
        ' "description": "Agent platform.", "aliases": ["OC"]}],'
        ' "dropped": []}'
    )
    cache = parse_and_cache(
        reply,
        wiki,
        inputs_fingerprint=fp,
        source_sigs={"OpenClaw": sig},
    )
    assert cache["version"] == CACHE_VERSION == 2
    assert cache["inputs_fingerprint"] == fp
    assert cache["topics"][0]["source_sig"] == sig
    assert cache["topics"][0]["kind"] == "entity"

    loaded = load_cache(wiki)
    assert loaded is not None
    assert loaded["inputs_fingerprint"] == fp
    assert loaded["kinds"]["OpenClaw"] == "entity"
    assert loaded["descriptions"]["OpenClaw"] == "Agent platform."
    assert loaded["alias_map"]["oc"] == "OpenClaw"
    assert loaded["topics"][0]["source_sig"] == sig


def test_parse_and_cache_migrates_v1_on_next_write(tmp_path: Path) -> None:
    """A v1 on-disk cache is rewritten as v2 on the next successful parse.

    # @spec: 325-known-names-prep
    """
    wiki = _make_wiki(tmp_path, {"s1": ["OpenClaw"], "s2": ["OpenClaw"]})
    v1 = {
        "version": 1,
        "topics": [
            {
                "canonical": "OpenClaw",
                "description": "old.",
                "aliases": [],
                "kind": "entity",
            }
        ],
        "dropped": [],
    }
    cache_path(wiki).write_text(json.dumps(v1), encoding="utf-8")

    # v1 still loads for consumers (kinds / descriptions / aliases).
    loaded_v1 = load_cache(wiki)
    assert loaded_v1 is not None
    assert loaded_v1["kinds"]["OpenClaw"] == "entity"
    assert loaded_v1["descriptions"]["OpenClaw"] == "old."
    assert "inputs_fingerprint" not in loaded_v1

    reply = (
        '{"topics": [{"canonical": "OpenClaw", "kind": "entity",'
        ' "description": "Agent platform.", "aliases": []}], "dropped": []}'
    )
    fp = "a" * 64
    cache = parse_and_cache(reply, wiki, inputs_fingerprint=fp)
    assert cache["version"] == 2
    assert cache["inputs_fingerprint"] == fp
    on_disk = json.loads(cache_path(wiki).read_text(encoding="utf-8"))
    assert on_disk["version"] == 2
    assert on_disk["inputs_fingerprint"] == fp


def test_load_cache_v1_without_fingerprint_exposes_consumer_fields(
    tmp_path: Path,
) -> None:
    """Legacy v1 files keep working until the next successful write.

    # @spec: 325-known-names-prep
    """
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    cache_path(wiki).write_text(
        json.dumps(
            {
                "version": 1,
                "topics": [
                    {
                        "canonical": "Bun",
                        "description": "JS runtime.",
                        "aliases": ["bun.js"],
                        "kind": "concept",
                    }
                ],
                "dropped": ["noise"],
            }
        ),
        encoding="utf-8",
    )
    loaded = load_cache(wiki)
    assert loaded is not None
    assert loaded["kinds"] == {"Bun": "concept"}
    assert loaded["descriptions"] == {"Bun": "JS runtime."}
    assert loaded["alias_map"]["bun.js"] == "Bun"
    assert loaded["dropped"] == ["noise"]
    assert "inputs_fingerprint" not in loaded


def test_prepare_known_names_sends_exactly_candidate_cap(tmp_path: Path) -> None:
    """Over-cap vault: prompt carries exactly the cap, highest reach first.

    # @spec: 325-known-names-prep
    """
    # Reach: High=5, Mid=4, LowA=3, LowB=3, Extra=2, Tiny=2 → cap 3 keeps
    # High, Mid, LowA (LowA before LowB on name tie-break).
    wiki = _make_wiki(
        tmp_path,
        {
            "s1": ["High", "Mid", "LowA", "LowB", "Extra", "Tiny"],
            "s2": ["High", "Mid", "LowA", "LowB", "Extra", "Tiny"],
            "s3": ["High", "Mid", "LowA", "LowB"],
            "s4": ["High", "Mid"],
            "s5": ["High"],
        },
    )
    all_names = {c["name"] for c in build_candidates(wiki)}
    assert all_names == {"High", "Mid", "LowA", "LowB", "Extra", "Tiny"}

    class _Spy:
        is_llm = True
        timeout = 120
        prompt: str = ""

        def synthesize_source_page(self, raw_body, meta, prompt_template, **_kwargs):
            self.prompt = prompt_template
            return (
                '{"topics": [{"canonical": "High", "description": "top.",'
                ' "aliases": []}], "dropped": []}'
            )

    spy = _Spy()
    prepare_known_names(
        wiki,
        spy,
        cfg={"synthesis": {"known_names": {"candidate_cap": 3}}},
    )

    # Exactly three <candidate> rows, in reach order.
    names_in_prompt = [
        line.split('name="', 1)[1].split('"', 1)[0]
        for line in spy.prompt.splitlines()
        if "<candidate " in line
    ]
    assert names_in_prompt == ["High", "Mid", "LowA"]
    assert 'name="LowB"' not in spy.prompt
    assert 'name="Extra"' not in spy.prompt
    assert 'name="Tiny"' not in spy.prompt


def test_prepare_known_names_passes_resolved_timeout(
    tmp_path: Path,
) -> None:
    """prepare_known_names passes kn.timeout into synthesize_source_page (#264).

    # @spec: 325-known-names-prep
    """
    wiki = _make_wiki(
        tmp_path,
        {
            "s1": ["OpenClaw"],
            "s2": ["OpenClaw"],
        },
    )

    class _Spy:
        is_llm = True
        timeout = 120
        kwargs: dict = {}

        def synthesize_source_page(self, raw_body, meta, prompt_template, **kwargs):
            self.kwargs = kwargs
            return (
                '{"topics": [{"canonical": "OpenClaw", "kind": "entity",'
                ' "description": "Agent platform.", "aliases": []}],'
                ' "dropped": []}'
            )

    spy = _Spy()
    prepare_known_names(
        wiki,
        spy,
        cfg={"synthesis": {"known_names": {"timeout": 777}}},
    )
    assert spy.kwargs.get("timeout") == 777.0


def test_prepare_known_names_skips_llm_when_fingerprint_and_coverage_match(
    tmp_path: Path,
) -> None:
    """Second identical prepare → zero synthesize_source_page calls; kinds still load.

    # @spec: 325-known-names-prep
    """
    wiki = _make_wiki(
        tmp_path,
        {
            "s1": ["OpenClaw", "Bun"],
            "s2": ["OpenClaw", "Bun"],
        },
    )

    class _Spy:
        is_llm = True
        timeout = 120
        calls = 0

        def synthesize_source_page(self, raw_body, meta, prompt_template, **_kwargs):
            self.calls += 1
            return (
                '{"topics": [{"canonical": "OpenClaw", "kind": "entity",'
                ' "description": "Agent platform.", "aliases": []},'
                '{"canonical": "Bun", "kind": "concept",'
                ' "description": "JS runtime.", "aliases": []}],'
                ' "dropped": []}'
            )

    spy = _Spy()
    cfg = {"synthesis": {"known_names": {"candidate_cap": 150}}}
    prepare_known_names(wiki, spy, cfg=cfg)
    assert spy.calls == 1
    loaded = load_cache(wiki)
    assert loaded is not None
    assert loaded["kinds"]["OpenClaw"] == "entity"
    assert loaded["kinds"]["Bun"] == "concept"
    assert "inputs_fingerprint" in loaded
    disk_after_first = cache_path(wiki).read_text(encoding="utf-8")

    prepare_known_names(wiki, spy, cfg=cfg)
    assert spy.calls == 1  # zero additional calls
    again = load_cache(wiki)
    assert again is not None
    assert again["kinds"]["OpenClaw"] == "entity"
    assert again["kinds"]["Bun"] == "concept"
    assert again["descriptions"]["OpenClaw"] == "Agent platform."
    assert again["descriptions"]["Bun"] == "JS runtime."
    # Skip path must not rewrite the on-disk cache.
    assert cache_path(wiki).read_text(encoding="utf-8") == disk_after_first


def test_prepare_known_names_one_new_candidate_delta_merges_prior_fields(
    tmp_path: Path,
) -> None:
    """One new candidate → one delta call; prior topic fields survive the merge.

    # @spec: 325-known-names-prep
    """
    wiki = _make_wiki(
        tmp_path,
        {
            "s1": ["OpenClaw", "Bun"],
            "s2": ["OpenClaw", "Bun"],
        },
    )
    cfg = {"synthesis": {"known_names": {"candidate_cap": 150}}}

    class _Spy:
        is_llm = True
        timeout = 120

        def __init__(self) -> None:
            self.calls = 0
            self.prompts: list[str] = []

        def synthesize_source_page(self, raw_body, meta, prompt_template, **_kwargs):
            self.calls += 1
            self.prompts.append(prompt_template)
            if self.calls == 1:
                return (
                    '{"topics": [{"canonical": "OpenClaw", "kind": "entity",'
                    ' "description": "Agent platform.", "aliases": ["OC"],'
                    ' "distinct_from": ["Claude"]},'
                    '{"canonical": "Bun", "kind": "concept",'
                    ' "description": "JS runtime.", "aliases": []}],'
                    ' "dropped": []}'
                )
            # Delta reply: only the new name; omit prior topics entirely.
            return (
                '{"topics": [{"canonical": "Zed", "kind": "entity",'
                ' "description": "Editor.", "aliases": []}],'
                ' "dropped": []}'
            )

    spy = _Spy()
    prepare_known_names(wiki, spy, cfg=cfg)
    assert spy.calls == 1
    prior = load_cache(wiki)
    assert prior is not None
    assert prior["kinds"]["OpenClaw"] == "entity"
    assert prior["kinds"]["Bun"] == "concept"
    assert prior["descriptions"]["OpenClaw"] == "Agent platform."
    assert prior["alias_map"]["oc"] == "OpenClaw"

    # Add one new candidate (Zed in two sessions) without changing prior reach.
    src = wiki / "sources" / "proj"
    (src / "s3.md").write_text(
        _session(["Zed"], stem="s3"), encoding="utf-8"
    )
    (src / "s4.md").write_text(
        _session(["Zed"], stem="s4"), encoding="utf-8"
    )

    prepare_known_names(wiki, spy, cfg=cfg)
    assert spy.calls == 2  # exactly one delta call
    delta_prompt = spy.prompts[1]
    names_in_prompt = [
        line.split('name="', 1)[1].split('"', 1)[0]
        for line in delta_prompt.splitlines()
        if "<candidate " in line
    ]
    assert names_in_prompt == ["Zed"]
    assert 'name="OpenClaw"' not in delta_prompt
    assert 'name="Bun"' not in delta_prompt

    merged = load_cache(wiki)
    assert merged is not None
    by_name = {t["canonical"]: t for t in merged["topics"]}
    assert by_name["OpenClaw"]["description"] == "Agent platform."
    assert by_name["OpenClaw"]["aliases"] == ["OC"]
    assert by_name["OpenClaw"]["kind"] == "entity"
    assert by_name["OpenClaw"]["distinct_from"] == ["Claude"]
    assert by_name["Bun"]["description"] == "JS runtime."
    assert by_name["Bun"]["kind"] == "concept"
    assert by_name["Zed"]["description"] == "Editor."
    assert by_name["Zed"]["kind"] == "entity"
    assert merged["kinds"]["OpenClaw"] == "entity"
    assert merged["kinds"]["Bun"] == "concept"
    assert merged["kinds"]["Zed"] == "entity"


def test_parse_and_cache_merge_into_preserves_untouched_kind(
    tmp_path: Path,
) -> None:
    """Delta merge keeps description/aliases/kind on names absent from the reply.

    # @spec: 325-known-names-prep
    """
    wiki = _make_wiki(
        tmp_path,
        {
            "s1": ["OpenClaw", "Bun"],
            "s2": ["OpenClaw", "Bun"],
        },
    )
    existing = {
        "version": 2,
        "inputs_fingerprint": "old",
        "topics": [
            {
                "canonical": "OpenClaw",
                "description": "keep me.",
                "aliases": ["OC"],
                "kind": "entity",
                "distinct_from": ["Claude"],
                "source_sig": "openclaw | oc | 2-3",
            },
            {
                "canonical": "Bun",
                "description": "stale bun.",
                "aliases": [],
                "kind": "concept",
                "source_sig": "bun |  | 2-3",
            },
        ],
        "dropped": ["noise"],
    }
    reply = (
        '{"topics": [{"canonical": "Bun", "description": "JS runtime.",'
        ' "aliases": ["bun.js"]}], "dropped": ["other"]}'
    )
    cache = parse_and_cache(
        reply,
        wiki,
        inputs_fingerprint="b" * 64,
        source_sigs={"Bun": "bun | bun.js | 2-3"},
        merge_into=existing,
    )
    by_name = {t["canonical"]: t for t in cache["topics"]}
    assert by_name["OpenClaw"]["description"] == "keep me."
    assert by_name["OpenClaw"]["aliases"] == ["OC"]
    assert by_name["OpenClaw"]["kind"] == "entity"
    assert by_name["OpenClaw"]["distinct_from"] == ["Claude"]
    assert by_name["Bun"]["description"] == "JS runtime."
    assert by_name["Bun"]["aliases"] == ["bun.js"]
    # Reply omitted kind → retain prior concept.
    assert by_name["Bun"]["kind"] == "concept"
    assert by_name["Bun"]["source_sig"] == "bun | bun.js | 2-3"
    assert "noise" in cache["dropped"]
    assert "other" in cache["dropped"]


def test_parse_and_cache_malformed_reply_does_not_corrupt_disk(
    tmp_path: Path,
) -> None:
    """Malformed consolidation JSON raises without rewriting .llmwiki-topics.json.

    # @spec: 325-known-names-prep
    """
    wiki = _make_wiki(
        tmp_path,
        {
            "s1": ["OpenClaw"],
            "s2": ["OpenClaw"],
        },
    )
    prior = {
        "version": 2,
        "inputs_fingerprint": "a" * 64,
        "topics": [
            {
                "canonical": "OpenClaw",
                "description": "keep me.",
                "aliases": ["OC"],
                "kind": "entity",
                "source_sig": "openclaw | oc | 2-3",
            }
        ],
        "dropped": [],
    }
    path = cache_path(wiki)
    path.write_text(json.dumps(prior, indent=2), encoding="utf-8")
    before = path.read_text(encoding="utf-8")

    with pytest.raises((ValueError, json.JSONDecodeError)):
        parse_and_cache("this is not consolidation json", wiki)
    assert path.read_text(encoding="utf-8") == before

    with pytest.raises(ValueError, match="topics"):
        parse_and_cache('{"topics": []}', wiki)
    assert path.read_text(encoding="utf-8") == before

    loaded = load_cache(wiki)
    assert loaded is not None
    assert loaded["kinds"]["OpenClaw"] == "entity"
    assert loaded["descriptions"]["OpenClaw"] == "keep me."


def test_prepare_known_names_malformed_reply_does_not_corrupt_cache(
    tmp_path: Path,
    capsys,
) -> None:
    """prepare_known_names warns on a bad reply and leaves the prior cache intact.

    # @spec: 325-known-names-prep
    """
    wiki = _make_wiki(
        tmp_path,
        {
            "s1": ["OpenClaw"],
            "s2": ["OpenClaw"],
        },
    )
    cfg = {"synthesis": {"known_names": {"candidate_cap": 150}}}

    class _Spy:
        is_llm = True
        timeout = 120
        calls = 0
        broken = False

        def synthesize_source_page(self, raw_body, meta, prompt_template, **_kwargs):
            self.calls += 1
            if self.broken:
                return "<<<truncated reply — not JSON>>>"
            return (
                '{"topics": [{"canonical": "OpenClaw", "kind": "entity",'
                ' "description": "Agent platform.", "aliases": ["OC"]}],'
                ' "dropped": []}'
            )

    spy = _Spy()
    prepare_known_names(wiki, spy, cfg=cfg)
    assert spy.calls == 1
    before = cache_path(wiki).read_text(encoding="utf-8")
    prior = load_cache(wiki)
    assert prior is not None
    assert prior["kinds"]["OpenClaw"] == "entity"

    # Force a second LLM call under fingerprint-alone skip (#264): clear
    # inputs_fingerprint / settled_sigs (and topic source_sig) so prepare
    # cannot skip, then fail the reply and assert the on-disk cache is unchanged.
    raw = json.loads(before)
    raw.pop("inputs_fingerprint", None)
    raw.pop("settled_sigs", None)
    for topic in raw["topics"]:
        topic.pop("source_sig", None)
    cache_path(wiki).write_text(json.dumps(raw, indent=2), encoding="utf-8")
    expected_disk = cache_path(wiki).read_text(encoding="utf-8")

    spy.broken = True
    prepare_known_names(wiki, spy, cfg=cfg)  # must not raise
    assert spy.calls == 2
    err = capsys.readouterr().err
    assert "prepare_known_names failed" in err
    assert cache_path(wiki).read_text(encoding="utf-8") == expected_disk
    again = load_cache(wiki)
    assert again is not None
    assert again["kinds"]["OpenClaw"] == "entity"
    assert again["descriptions"]["OpenClaw"] == "Agent platform."
    assert again["alias_map"]["oc"] == "OpenClaw"


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


# ─── #248 FR4: the topics listing separates curated from derived ──────


def _index_section(index_html: str, heading: str) -> str:
    """Return the markup between one index heading and the next (or the end)."""
    start = index_html.index(f">{heading} ")
    rest = index_html[start:]
    nxt = rest.find('<h2 class="topic-index-heading">', 1)
    return rest if nxt == -1 else rest[:nxt]


def _grouped_index(tmp_path: Path) -> str:
    """Build a listing holding two entities, two concepts and two derived
    topics, each pair with distinct reach so ordering is observable."""
    wiki = _make_wiki(tmp_path, {
        "s1": ["Hazel", "Bun", "Caching", "Batching", "Unfiled", "Gamma"],
        "s2": ["Hazel", "Bun", "Caching", "Batching", "Unfiled", "Gamma"],
        "s3": ["Hazel", "Caching", "Unfiled"],
    })
    for name in ("Hazel", "Bun"):
        _curated_page_file(wiki, "entities", name)
    for name in ("Caching", "Batching"):
        _curated_page_file(wiki, "concepts", name)
    g = build_topic_graph(wiki, min_sessions=2)
    out = tmp_path / "site"
    build_topic_pages(g, out, wiki_dir=wiki)
    return (out / "topics" / "index.html").read_text(encoding="utf-8")


def test_topics_index_groups_entities_concepts_and_derived_topics(tmp_path: Path):
    index = _grouped_index(tmp_path)
    headings = [
        '<h2 class="topic-index-heading">Entities <span class="muted">(2)</span></h2>',
        '<h2 class="topic-index-heading">Concepts <span class="muted">(2)</span></h2>',
        '<h2 class="topic-index-heading">Other topics <span class="muted">(2)</span></h2>',
    ]
    for h in headings:
        assert h in index
    positions = [index.index(h) for h in headings]
    assert positions == sorted(positions), "curated knowledge comes first (FR4)"

    assert "Hazel" in _index_section(index, "Entities")
    assert "Caching" in _index_section(index, "Concepts")
    assert "Unfiled" in _index_section(index, "Other topics")


def test_topics_index_chips_curated_rows_and_leaves_derived_rows_bare(
    tmp_path: Path,
):
    index = _grouped_index(tmp_path)
    entities = _index_section(index, "Entities")
    concepts = _index_section(index, "Concepts")
    other = _index_section(index, "Other topics")

    assert entities.count('<span class="topic-kind-chip">Entity</span>') == 2
    assert concepts.count('<span class="topic-kind-chip">Concept</span>') == 2
    # A derived topic carries no chip at all — the absence is the signal that
    # nobody reviewed it, so it must not fall back to `Unclassified topic`.
    assert "topic-kind-chip" not in other
    assert KIND_OTHER_LABEL not in other


def test_topics_index_keeps_reach_order_inside_each_section(tmp_path: Path):
    index = _grouped_index(tmp_path)
    for heading, first, second in (
        ("Entities", "Hazel", "Bun"),
        ("Concepts", "Caching", "Batching"),
        ("Other topics", "Unfiled", "Gamma"),
    ):
        section = _index_section(index, heading)
        assert section.index(f">{first}</a>") < section.index(f">{second}</a>"), (
            f"{heading}: the more widely referenced topic must come first"
        )


def test_topics_index_renders_every_section_even_when_one_is_empty(
    tmp_path: Path,
):
    """A missing section would read as a broken page; "(0)" reads as a fact."""
    wiki = _make_wiki(tmp_path, {
        "s1": ["Unfiled", "Gamma"],
        "s2": ["Unfiled", "Gamma"],
    })
    g = build_topic_graph(wiki, min_sessions=2)
    out = tmp_path / "site"
    build_topic_pages(g, out)
    index = (out / "topics" / "index.html").read_text(encoding="utf-8")
    assert '>Entities <span class="muted">(0)</span></h2>' in index
    assert '>Concepts <span class="muted">(0)</span></h2>' in index
    assert '>Other topics <span class="muted">(2)</span></h2>' in index
    assert index.count('<p class="muted">No topics in this group.</p>') == 2


# ─── Reviewer decisions outrank the vocabulary heuristics (#282) ────────


def _harvest_and_discard(wiki: Path, name: str, **kwargs) -> None:
    """Harvest stubs through the real code, then discard ``name``."""
    write_stubs(wiki, harvest_targets(wiki, min_refs=2))
    discard(name, wiki, reason="noise", **kwargs)


def _add_session(wiki: Path, stem: str, links: list[str]) -> None:
    """A later synth run naming ``links`` again."""
    (wiki / "sources" / "proj" / f"{stem}.md").write_text(
        _session(links, stem=stem), encoding="utf-8"
    )


def test_discarded_name_leaves_vocabulary_under_any_casing(tmp_path: Path):
    """# @layer: integration  # @spec: 282-discarded-topic-links"""
    wiki = _make_wiki(tmp_path, {
        "s1": ["OpenClaw", "Junk"],
        "s2": ["OpenClaw", "Junk"],
    })
    _harvest_and_discard(wiki, "Junk")
    # A later synth coins the name again, in other casings.
    _add_session(wiki, "s3", ["OpenClaw", "junk"])
    _add_session(wiki, "s4", ["OpenClaw", "JUNK"])

    topics, raw_to_canonical = derive_vocabulary(wiki)
    assert {t.canonical for t in topics} == {"OpenClaw"}
    assert "junk" not in raw_to_canonical and "JUNK" not in raw_to_canonical
    graph = build_topic_graph(wiki, min_sessions=1)
    assert {n["id"] for n in graph["nodes"]} == {"OpenClaw"}
    out = _inject_vocabulary("{vocabulary}", wiki)
    assert "junk" not in out.lower()


def test_redirected_name_maps_onto_the_target_topic(tmp_path: Path):
    """# @layer: integration  # @spec: 282-discarded-topic-links"""
    wiki = _make_wiki(tmp_path, {
        "s1": ["OpenClaw", "Claw Thing"],
        "s2": ["OpenClaw", "Claw Thing"],
    })
    (wiki / "entities").mkdir()
    (wiki / "entities" / "OpenClaw.md").write_text(
        '---\ntitle: "OpenClaw"\n---\n\n# OpenClaw\n', encoding="utf-8"
    )
    _harvest_and_discard(wiki, "Claw Thing", redirect="OpenClaw")
    _add_session(wiki, "s3", ["claw thing"])

    topics, raw_to_canonical = derive_vocabulary(wiki)
    assert raw_to_canonical["claw thing"] == "OpenClaw"
    [topic] = topics
    assert topic.canonical == "OpenClaw"
    assert "claw thing" in topic.aliases
    assert topic.sessions == {"s1", "s2", "s3"}


def test_prepare_known_names_skips_when_fingerprint_matches_despite_dropped(
    tmp_path: Path,
) -> None:
    """Dropped candidates must not force a perpetual delta; fingerprint match skips.

    # @spec: 325-known-names-prep
    """
    wiki = _make_wiki(
        tmp_path,
        {
            "s1": ["OpenClaw", "NoiseTool"],
            "s2": ["OpenClaw", "NoiseTool"],
        },
    )

    class _Spy:
        is_llm = True
        timeout = 120
        calls = 0

        def synthesize_source_page(self, raw_body, meta, prompt_template, **_kwargs):
            self.calls += 1
            # Keep OpenClaw; drop NoiseTool (no topic source_sig for it).
            return (
                '{"topics": [{"canonical": "OpenClaw", "kind": "entity",'
                ' "description": "Agent platform.", "aliases": []}],'
                ' "dropped": ["NoiseTool"]}'
            )

    spy = _Spy()
    cfg = {"synthesis": {"known_names": {"candidate_cap": 150}}}
    prepare_known_names(wiki, spy, cfg=cfg)
    assert spy.calls == 1
    prepare_known_names(wiki, spy, cfg=cfg)
    assert spy.calls == 1  # skip — not another delta for the dropped name
