"""Project pages carry connected topics and session-derived dates (#108).

FR5 makes routing a project topic to its project page lossless: the
co-occurrence list the reader would have seen on the topic page shows up on the
project page instead, immediately above the sessions. FR2's project half
derives created / updated from the project's oldest and newest session, because
project stubs record no date of their own.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import llmwiki.build as build_mod
from llmwiki.build import (
    build_site,
    project_connected_topics,
    project_session_dates,
    render_connected_topics,
    render_project_page,
)
from llmwiki.topics import build_topic_graph
from llmwiki.topics_page import kind_chip, kind_label

_HEADING = "<h2>Connected topics</h2>"
_HERO_SUB = re.compile(r'<p class="hero-sub">(.*?)</p>', re.S)


def _hero_sub(page: str) -> str:
    """The hero's subtitle line — where the project's dates belong."""
    m = _HERO_SUB.search(page)
    assert m, "project page carries no hero subtitle"
    return m.group(1)


def _session(stem: str, date: str | None = "2026-04-01") -> tuple[Path, dict[str, Any], str]:
    meta: dict[str, Any] = {"title": stem, "slug": stem, "project": "demo"}
    if date is not None:
        meta["date"] = date
    return Path(f"raw/sessions/demo/{stem}.md"), meta, ""


# ── unit: finding a project's node in the topic graph ───────────────────────


def _graph() -> dict[str, Any]:
    return {
        "nodes": [
            {"id": "shipped", "kind": "projects", "wiki_slug": "shipped"},
            {"id": "Hazel", "kind": "entities", "wiki_slug": "Hazel"},
        ],
        "edges": [
            {"source": "shipped", "target": "Hazel", "weight": 3},
            {"source": "Batching", "target": "shipped", "weight": 5},
            {"source": "Hazel", "target": "Batching", "weight": 9},
        ],
    }


def test_project_topics_come_from_its_own_node_strongest_first():
    assert project_connected_topics(_graph(), "shipped") == [
        ("Batching", 5, "../topics/batching.html"),
        ("Hazel", 3, "../topics/hazel.html"),
    ]


def test_a_neighbour_that_is_itself_a_project_routes_to_its_project_page():
    """FR4: every surface honours the project rewrite, this list included.

    Two projects sharing a session co-occur in the graph, so project A's page
    lists project B — and must send the reader to B's project page, not to the
    thin topic page the rewrite exists to route away from.
    """
    graph = {
        "nodes": [
            {"id": "shipped", "kind": "projects", "wiki_slug": "shipped",
             "site_url": "projects/shipped.html"},
            {"id": "legacy-app", "kind": "projects", "wiki_slug": "legacy-app",
             "site_url": "projects/legacy-app.html"},
        ],
        "edges": [{"source": "shipped", "target": "legacy-app", "weight": 2}],
    }
    topics = project_connected_topics(graph, "shipped")
    assert topics == [("legacy-app", 2, "../projects/legacy-app.html")]
    assert 'href="../projects/legacy-app.html"' in render_connected_topics(topics)


def test_a_project_topic_with_no_built_page_keeps_its_topic_page():
    """FR4's fallback: an unresolved project node still links somewhere real."""
    graph = {
        "nodes": [
            {"id": "shipped", "kind": "projects", "wiki_slug": "shipped"},
            {"id": "legacy-app", "kind": "projects", "wiki_slug": "legacy-app"},
        ],
        "edges": [{"source": "shipped", "target": "legacy-app", "weight": 2}],
    }
    assert project_connected_topics(graph, "shipped") == [
        ("legacy-app", 2, "../topics/legacy-app.html")
    ]


def test_a_project_with_no_node_in_the_graph_has_no_topics():
    assert project_connected_topics(_graph(), "unknown") == []


def test_an_entity_node_is_never_mistaken_for_the_project():
    # Same wiki_slug, wrong kind — a project's node is the `projects` one.
    graph = {
        "nodes": [{"id": "Hazel", "kind": "entities", "wiki_slug": "demo"}],
        "edges": [{"source": "Hazel", "target": "Batching", "weight": 2}],
    }
    assert project_connected_topics(graph, "demo") == []


def test_no_graph_at_all_yields_no_topics():
    assert project_connected_topics(None, "shipped") == []
    assert project_connected_topics({}, "shipped") == []


# ── unit: rendering ─────────────────────────────────────────────────────────


def test_topic_links_climb_out_of_the_projects_directory():
    out = render_connected_topics([("Some Topic", 4, "../topics/some-topic.html")])
    assert _HEADING in out
    assert 'href="../topics/some-topic.html"' in out
    assert ">Some Topic</a>" in out
    assert "· 4 shared" in out


def test_topic_names_are_escaped():
    out = render_connected_topics([("A & B <x>", 1, "../topics/a-b-x.html")])
    assert "A &amp; B &lt;x&gt;" in out
    assert "<x>" not in out


def test_an_empty_list_renders_nothing_at_all():
    assert render_connected_topics([]) == ""


# ── unit: the page parameter ────────────────────────────────────────────────


def test_project_page_omits_the_section_by_default(tmp_path: Path):
    page = render_project_page("demo", [_session("s0")], tmp_path).read_text(
        encoding="utf-8"
    )
    assert _HEADING not in page
    assert "topic-neighbor-list" not in page


def test_project_page_omits_the_section_for_an_empty_list(tmp_path: Path):
    page = render_project_page(
        "demo", [_session("s0")], tmp_path, connected_topics=[]
    ).read_text(encoding="utf-8")
    assert _HEADING not in page


def test_project_page_puts_connected_topics_above_the_sessions(tmp_path: Path):
    page = render_project_page(
        "demo", [_session("s0")], tmp_path,
        connected_topics=[("Hazel", 2, "../topics/hazel.html")],
    ).read_text(encoding="utf-8")
    assert page.index(_HEADING) < page.index("<h2>Main sessions (1)</h2>")
    assert 'href="../topics/hazel.html"' in page


# ── unit: created / updated dates ───────────────────────────────────────────


def test_dates_come_from_the_oldest_and_newest_session():
    sessions = [_session("s0", "2026-01-05"), _session("s1", "2026-02-09"),
                _session("s2", "2026-03-14")]
    assert project_session_dates(sessions) == ("2026-01-05", "2026-03-14")


def test_dates_do_not_depend_on_the_input_order():
    sessions = [_session("s2", "2026-03-14"), _session("s0", "2026-01-05"),
                _session("s1", "2026-02-09")]
    assert project_session_dates(sessions) == ("2026-01-05", "2026-03-14")


def test_undated_sessions_are_skipped_rather_than_blanking_the_range():
    sessions = [_session("s0", None), _session("s1", "2026-02-09"),
                _session("s2", "")]
    assert project_session_dates(sessions) == ("2026-02-09", "2026-02-09")


def test_a_project_with_no_dated_session_has_no_dates():
    assert project_session_dates([_session("s0", None)]) == ("", "")
    assert project_session_dates([]) == ("", "")


def test_project_hero_opens_with_a_project_kind_chip(tmp_path: Path):
    """FR5: a project topic routes here, so this page carries the kind chip.

    The reader never sees the topic page's chip, and the label comes from the
    topic page's own helper rather than a literal, so the two cannot drift.
    """
    page = render_project_page("demo", [_session("s0")], tmp_path).read_text(
        encoding="utf-8"
    )
    sub = _hero_sub(page)
    assert sub.startswith(kind_chip("projects"))
    assert f'<span class="topic-kind-chip">{kind_label("projects")}</span>' in sub


def test_project_hero_shows_the_derived_dates(tmp_path: Path):
    sessions = [_session("s0", "2026-01-05"), _session("s1", "2026-03-14")]
    page = render_project_page("demo", sessions, tmp_path).read_text(encoding="utf-8")
    sub = _hero_sub(page)
    assert "created 2026-01-05" in sub
    assert "updated 2026-03-14" in sub


def test_project_hero_shows_no_dates_when_the_sessions_carry_none(tmp_path: Path):
    page = render_project_page(
        "demo", [_session("s0", None)], tmp_path
    ).read_text(encoding="utf-8")
    sub = _hero_sub(page)
    assert "created" not in sub
    assert "updated" not in sub
    # The rest of the identity line still renders — no placeholder, no gap.
    assert "slug <code>demo</code>" in sub
    assert "1 main sessions" in sub


# ── integration: a built vault ──────────────────────────────────────────────

# Spellings far enough apart that near-duplicate clustering keeps them separate.
_TOPICS = ["demo", "Hazel", "Batching", "Sparse", "Unfiled"]
_PROJECT = "demo"
_DATES = ["2026-04-01", "2026-04-09", "2026-04-17"]


def _build_fixture_vault(tmp_path: Path, monkeypatch, *, topics: list[str]) -> Path:
    vault = tmp_path / "vault"
    wiki = vault / "wiki"
    raw = vault / "raw" / "sessions" / _PROJECT
    site = vault / "site"
    src = wiki / "sources" / _PROJECT
    src.mkdir(parents=True)
    raw.mkdir(parents=True)
    (vault / "raw" / "docs").mkdir(parents=True)
    site.mkdir()

    links = "\n".join(f"- [[{t}]]" for t in topics)
    for j, date in enumerate(_DATES):
        stem = f"s{j}"
        (src / f"{stem}.md").write_text(
            f'---\ntitle: "{stem}"\ntype: source\nproject: {_PROJECT}\n'
            f"date: {date}\nsource_file: raw/sessions/{_PROJECT}/{stem}.md\n"
            f"---\n\n## Connections\n\n{links}\n",
            encoding="utf-8",
        )
        (raw / f"{stem}.md").write_text(
            f'---\ntitle: "{stem}"\ntype: source\nproject: {_PROJECT}\n'
            f"slug: {stem}\ndate: {date}\nstarted: {date}T09-00\n"
            f"source_file: raw/sessions/{_PROJECT}/{stem}.md\n"
            'token_totals: {"input": 1, "output": 1, "cache_creation": 0, "cache_read": 0}\n'
            f"---\n\n# {stem}\n",
            encoding="utf-8",
        )

    projects = wiki / "projects"
    projects.mkdir(parents=True)
    (projects / f"{_PROJECT}.md").write_text(
        f'---\ntitle: "{_PROJECT}"\ntype: project\ntags: []\n---\n\n'
        f"# {_PROJECT}\n\nA fixture project.\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(build_mod, "REPO_ROOT", vault)
    monkeypatch.setattr(build_mod, "SOURCE_ROOT", vault)
    monkeypatch.setattr(build_mod, "RAW_DIR", vault / "raw")
    monkeypatch.setattr(build_mod, "RAW_SESSIONS", vault / "raw" / "sessions")
    monkeypatch.setattr(build_mod, "DEFAULT_OUT_DIR", site)
    monkeypatch.setattr(build_mod, "PROJECTS_META_DIR", projects)
    monkeypatch.setattr(build_mod, "compile_docs_site", lambda *a, **k: [])

    rc = build_site(
        out_dir=site,
        raw_sessions=vault / "raw" / "sessions",
        raw_dir=vault / "raw",
        wiki_dir=wiki,
    )
    assert rc == 0
    return site


def _rich_vault(tmp_path: Path, monkeypatch) -> Path:
    wiki = tmp_path / "vault" / "wiki"
    site = _build_fixture_vault(tmp_path, monkeypatch, topics=_TOPICS)
    nodes = build_topic_graph(wiki, min_sessions=2)["nodes"]
    assert len(nodes) >= 5, "fixture must clear the sparse-graph floor"
    return site


def test_built_project_page_shows_connected_topics_above_its_sessions(
    tmp_path: Path, monkeypatch
):
    site = _rich_vault(tmp_path, monkeypatch)
    page = (site / "projects" / f"{_PROJECT}.html").read_text(encoding="utf-8")
    assert page.index(_HEADING) < page.index("<h2>Main sessions (3)</h2>")
    for topic in ("Hazel", "Batching", "Sparse", "Unfiled"):
        assert f">{topic}</a>" in page
    # The project never lists itself among the topics it connects to.
    assert f'href="../topics/{_PROJECT}.html"' not in page


def test_every_connected_topic_link_resolves_to_a_real_file(
    tmp_path: Path, monkeypatch
):
    site = _rich_vault(tmp_path, monkeypatch)
    path = site / "projects" / f"{_PROJECT}.html"
    section = path.read_text(encoding="utf-8").split(_HEADING, 1)[1].split("</ul>", 1)[0]
    hrefs = re.findall(r'href="([^"]+)"', section)
    assert hrefs
    for href in hrefs:
        assert (path.parent / href).resolve().is_file(), href


def test_built_project_hero_carries_the_session_derived_dates(
    tmp_path: Path, monkeypatch
):
    site = _rich_vault(tmp_path, monkeypatch)
    sub = _hero_sub((site / "projects" / f"{_PROJECT}.html").read_text(encoding="utf-8"))
    assert f"created {_DATES[0]}" in sub
    assert f"updated {_DATES[-1]}" in sub


def test_a_sparse_vault_writes_no_connected_topics_section(
    tmp_path: Path, monkeypatch, capsys
):
    # Two topics across the sources — below _TOPIC_GRAPH_MIN_NODES, so the
    # build degrades to the page graph and the project page shows no section
    # at all rather than an empty one (FR8).
    site = _build_fixture_vault(tmp_path, monkeypatch, topics=["Hazel", "Batching"])
    out = capsys.readouterr().out
    assert "topic graph too sparse" in out
    assert not (site / "topics").exists()
    page = (site / "projects" / f"{_PROJECT}.html").read_text(encoding="utf-8")
    assert _HEADING not in page
    assert "topic-neighbor-list" not in page
    # The dates are session-derived and survive the degraded graph.
    assert f"created {_DATES[0]}" in _hero_sub(page)
