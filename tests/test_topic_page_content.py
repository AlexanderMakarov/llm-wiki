"""Topic pages render the backing page's curated content (#108, FR3).

Entity and concept pages get no page of their own anywhere on the site, so the
topic page is the only surface their recorded content can reach a reader. These
tests cover the extraction helper, the wikilink resolution applied to it, and a
built fixture vault proving the content lands above the connected-topics list.
"""

from __future__ import annotations

import re
from pathlib import Path

import llmwiki.build as build_mod
from llmwiki.build import build_site
from llmwiki.topics import build_topic_graph
from llmwiki.topics_page import _resolve_wikilinks, page_content

# Distinct enough that the vocabulary's near-duplicate clustering keeps them apart.
_TOPICS = ["Hazel", "Batching", "Sparse", "Unfiled", "Gamma"]
_EMPTY_HEADING = re.compile(r"<h(\d)[^>]*>\s*</h\1>")


# --- extraction ------------------------------------------------------------


def test_extraction_drops_frontmatter_h1_connections_and_sessions():
    text = (
        '---\ntitle: "Hazel"\ntype: entity\nlast_updated: 2026-04-02\n---\n\n'
        "# Hazel\n\nIntro prose about Hazel.\n\n"
        "## Key Facts\n- Ships weekly.\n\n"
        "## Curator Notes\n- Added by hand.\n\n"
        "## Sessions\n- [[s0]] (2026-04-01) — first look\n\n"
        "## Connections\n- [[Batching]]\n"
    )
    out = page_content(text)
    assert out is not None
    assert "title:" not in out and "type: entity" not in out
    assert "# Hazel" not in out
    assert "Intro prose about Hazel." in out
    assert "## Key Facts" in out and "Ships weekly." in out
    assert "## Curator Notes" in out and "Added by hand." in out
    assert "## Sessions" not in out and "first look" not in out
    assert "## Connections" not in out and "[[Batching]]" not in out


def test_extraction_returns_none_when_nothing_is_left():
    text = (
        '---\ntitle: "Hazel"\ntype: entity\n---\n\n# Hazel\n\n'
        "## Connections\n- [[Batching]]\n"
    )
    assert page_content(text) is None


def test_extraction_returns_none_for_an_empty_section():
    text = '---\ntitle: "Hazel"\ntype: entity\n---\n\n# Hazel\n\n## Key Facts\n\n'
    assert page_content(text) is None


def test_extraction_keeps_a_subsection_inside_its_parent_section():
    text = (
        "# Hazel\n\n## Key Facts\n- Ships weekly.\n\n"
        "### Release cadence\n- Thursdays.\n\n"
        "## Connections\n- [[Batching]]\n"
    )
    out = page_content(text)
    assert out is not None
    # The `###` did not terminate `## Key Facts`, and neither survived into
    # the dropped Connections section.
    assert "### Release cadence" in out and "Thursdays." in out
    assert "## Connections" not in out


def test_extraction_ignores_a_heading_inside_a_fenced_block():
    text = (
        "# Hazel\n\n## Key Facts\n\n```markdown\n## Sessions\nnot a heading\n```\n\n"
        "- Ships weekly.\n\n## Connections\n- [[Batching]]\n"
    )
    out = page_content(text)
    assert out is not None
    assert "## Sessions" in out and "not a heading" in out
    assert "- Ships weekly." in out
    assert "## Connections" not in out


def test_extraction_keeps_prose_only_pages():
    text = '---\ntitle: "Batching"\ntype: concept\n---\n\n# Batching\n\nJust prose.\n'
    assert page_content(text) == "Just prose."


def test_a_title_after_an_omitted_section_still_closes_that_section():
    """A curator who puts `## Connections` first must not lose the page.

    Dropping the title used to happen before the section state was updated, so
    the omitted section stayed open past the `# H1` and swallowed everything
    until the next `##`.
    """
    text = (
        "---\nt: 1\n---\n## Connections\n- [[X]]\n\n# Hazel\n\n"
        "Important prose.\n\n## Key Facts\n- a\n"
    )
    out = page_content(text)
    assert out == "Important prose.\n\n## Key Facts\n- a"
    assert "[[X]]" not in out


def test_a_second_h1_after_an_omitted_section_keeps_the_prose_under_it():
    text = (
        "---\nt: 1\n---\n# Hazel\n\n## Connections\n- [[X]]\n\n"
        "# Related Work\n\nImportant prose.\n"
    )
    out = page_content(text)
    assert "Important prose." in out
    assert "[[X]]" not in out


# --- wikilink resolution ---------------------------------------------------

_TOPIC_INDEX = {"hazel": "Hazel", "hazelnut": "Hazel"}
_SESSIONS = {"s0": {"title": "s0", "url": "sessions/proj/s0.html"},
             "s1": {"title": "s1", "url": ""}}


def test_wikilink_to_a_topic_links_to_its_sibling_page():
    out = _resolve_wikilinks("see [[Hazel]] here", _TOPIC_INDEX, _SESSIONS)
    assert out == 'see <a href="hazel.html">Hazel</a> here'


def test_wikilink_to_an_alias_resolves_to_the_canonical_topic():
    out = _resolve_wikilinks("[[Hazelnut]]", _TOPIC_INDEX, _SESSIONS)
    assert out == '<a href="hazel.html">Hazelnut</a>'


def test_wikilink_to_a_session_links_to_its_compiled_page():
    out = _resolve_wikilinks("cited [[s0]]", _TOPIC_INDEX, _SESSIONS)
    assert out == 'cited <a href="../sessions/proj/s0.html">s0</a>'


def test_unresolvable_wikilink_becomes_plain_text():
    out = _resolve_wikilinks("about [[Nowhere]] and [[s1]]", _TOPIC_INDEX, _SESSIONS)
    assert out == "about Nowhere and s1"
    assert "[[" not in out


def test_wikilink_display_text_is_what_the_reader_sees():
    out = _resolve_wikilinks(
        "[[Hazel|the shrub]] and [[Nowhere|nothing]]", _TOPIC_INDEX, _SESSIONS
    )
    assert out == '<a href="hazel.html">the shrub</a> and nothing'


def test_a_wikilink_inside_a_fenced_block_survives_verbatim():
    """A page documenting the syntax means its example literally."""
    rendered = (
        "<p>Cite a fact like this:</p>\n"
        "<pre><code>- Fact ([[Hazel]])\n</code></pre>\n"
        "<p>as in [[Hazel]].</p>"
    )
    out = _resolve_wikilinks(rendered, _TOPIC_INDEX, _SESSIONS)
    assert "<pre><code>- Fact ([[Hazel]])\n</code></pre>" in out
    assert '<p>as in <a href="hazel.html">Hazel</a>.</p>' in out


def test_a_wikilink_inside_a_code_span_survives_verbatim():
    out = _resolve_wikilinks(
        "write <code>[[Nowhere]]</code> to cite it", _TOPIC_INDEX, _SESSIONS
    )
    assert out == "write <code>[[Nowhere]]</code> to cite it"


# --- built fixture vault ---------------------------------------------------


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

    pages = {
        # Key Facts with a session citation, a topic citation and a dead one.
        "entities/Hazel.md": (
            '---\ntitle: "Hazel"\ntype: entity\nlast_updated: 2026-04-02\n---\n\n'
            "# Hazel\n\nIntro prose about Hazel.\n\n"
            "## Key Facts\n"
            "- Batched nightly, per [[s0]].\n"
            "- Shares a queue with [[Batching]].\n"
            "- Was once called [[NoSuchPage]].\n\n"
            "## Connections\n- [[Batching]]\n"
        ),
        # Prose only — no Key Facts heading anywhere.
        "concepts/Batching.md": (
            '---\ntitle: "Batching"\ntype: concept\n---\n\n'
            "# Batching\n\nGrouping work so it runs once instead of many times.\n\n"
            "## Connections\n- [[Hazel]]\n"
        ),
        # Key Facts recorded but empty.
        "entities/Sparse.md": (
            '---\ntitle: "Sparse"\ntype: entity\n---\n\n'
            "# Sparse\n\n## Key Facts\n\n## Connections\n- [[Hazel]]\n"
        ),
    }
    for rel, body in pages.items():
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


def test_entity_content_renders_above_connected_topics(tmp_path: Path, monkeypatch):
    site = _build_fixture_vault(tmp_path, monkeypatch)
    page = (site / "topics" / "hazel.html").read_text(encoding="utf-8")
    assert "Intro prose about Hazel." in page
    assert "Key Facts" in page
    assert page.index("Key Facts") < page.index("Connected topics")


def test_citations_become_working_links_and_dead_ones_plain_text(
    tmp_path: Path, monkeypatch
):
    site = _build_fixture_vault(tmp_path, monkeypatch)
    page = (site / "topics" / "hazel.html").read_text(encoding="utf-8")
    assert '<a href="../sessions/proj/s0.html">s0</a>' in page
    assert '<a href="batching.html">Batching</a>' in page
    assert "NoSuchPage" in page and "[[" not in page


def test_prose_only_concept_page_reaches_the_reader(tmp_path: Path, monkeypatch):
    site = _build_fixture_vault(tmp_path, monkeypatch)
    page = (site / "topics" / "batching.html").read_text(encoding="utf-8")
    assert "Grouping work so it runs once instead of many times." in page
    assert page.index("Grouping work") < page.index("Connected topics")


def test_empty_content_emits_no_heading_and_no_wrapper(tmp_path: Path, monkeypatch):
    site = _build_fixture_vault(tmp_path, monkeypatch)
    page = (site / "topics" / "sparse.html").read_text(encoding="utf-8")
    assert "Key Facts" not in page
    assert "topic-page-content" not in page
    assert not _EMPTY_HEADING.search(page)


def test_undescribed_topic_renders_no_content_block(tmp_path: Path, monkeypatch):
    site = _build_fixture_vault(tmp_path, monkeypatch)
    page = (site / "topics" / "unfiled.html").read_text(encoding="utf-8")
    assert "topic-page-content" not in page
    assert "Connected topics" in page
