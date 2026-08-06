"""Whole-feature acceptance tests for #108: topic pages show kind, freshness
and Key Facts; project topics route to the project page.

# @layer: integration
# @spec: 004-topic-page-kind-and-key-facts
# @regression

Per-slice tests (``test_topic_identity_line.py``, ``test_topic_freshness.py``,
``test_topic_page_content.py``, ``test_topic_project_routing.py``,
``test_project_page_connections.py``, ``test_graph_kind_colors.py``,
``test_graph_topic_panel.py``, ``test_topics.py``) already cover FR1-FR8's
per-slice mechanics in detail. This file fills the whole-feature gaps called
out by ``technical-considerations.md`` §3 (backward compatibility with vaults
that predate this feature) plus a couple of "every surface agrees" and
"nothing breaks under combination" checks that no single slice test exercises
on its own.

AC / requirement coverage this file adds:

    tech-considerations §3.1  -> test_vault_with_no_optional_frontmatter_anywhere_builds_clean
    tech-considerations §3.2  -> test_pre_102_project_page_routes_across_every_surface
    tech-considerations §3.3  -> test_last_updated_quoted_and_bare_render_identically
    tech-considerations §3.4  -> test_search_index_topic_entries_carry_only_the_frozen_keys
    FR8 AC2 (kitchen sink)    -> test_mixed_vault_completes_and_every_topic_page_opens
    "every surface agrees"    -> folded into test_pre_102_project_page_routes_across_every_surface

Everything else in FR1-FR9 is exercised by the per-slice suites listed above
and is not duplicated here.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import llmwiki.build as build_mod
from llmwiki.build import build_search_index, build_site
from llmwiki.topics import build_topic_graph

_EMPTY_HEADING = re.compile(r"<h(\d)[^>]*>\s*</h\1>")
_HERO_SUB = re.compile(r'<p class="hero-sub">(.*?)</p>', re.S)
_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
_GRAPH_JSON = re.compile(r"^const GRAPH = (\{.*\});$", re.M)


def _scaffold_vault(tmp_path: Path, project: str = "proj") -> dict[str, Path]:
    vault = tmp_path / "vault"
    wiki = vault / "wiki"
    raw = vault / "raw" / "sessions" / project
    site = vault / "site"
    src = wiki / "sources" / project
    src.mkdir(parents=True)
    raw.mkdir(parents=True)
    (vault / "raw" / "docs").mkdir(parents=True)
    site.mkdir()
    return {"vault": vault, "wiki": wiki, "raw": raw, "site": site, "src": src}


def _write_session(
    paths: dict[str, Path],
    stem: str,
    topics: list[str],
    *,
    project: str = "proj",
    date: str | None = "2026-04-01",
) -> None:
    """One raw session + its wiki/sources/ summary, mentioning ``topics``."""
    links = "\n".join(f"- [[{t}]]" for t in topics)
    date_line = f"date: {date}\n" if date else ""
    (paths["src"] / f"{stem}.md").write_text(
        f'---\ntitle: "{stem}"\ntype: source\nproject: {project}\n{date_line}'
        f"source_file: raw/sessions/{project}/{stem}.md\n"
        f"---\n\n## Connections\n\n{links}\n",
        encoding="utf-8",
    )
    (paths["raw"] / f"{stem}.md").write_text(
        f'---\ntitle: "{stem}"\ntype: source\nproject: {project}\n'
        f"slug: {stem}\n{date_line}"
        f"source_file: raw/sessions/{project}/{stem}.md\n"
        'token_totals: {"input": 1, "output": 1, "cache_creation": 0, "cache_read": 0}\n'
        f"---\n\n# {stem}\n",
        encoding="utf-8",
    )


def _write_wiki_page(
    paths: dict[str, Path], folder: str, stem: str, frontmatter_extra: str, body: str
) -> None:
    page = paths["wiki"] / folder / f"{stem}.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(
        f'---\ntitle: "{stem}"\ntype: {"entity" if folder == "entities" else folder.rstrip("s")}\n'
        f"{frontmatter_extra}---\n\n# {stem}\n\n{body}",
        encoding="utf-8",
    )


def _run_build(paths: dict[str, Path], monkeypatch) -> int:
    vault, wiki, site = paths["vault"], paths["wiki"], paths["site"]
    monkeypatch.setattr(build_mod, "REPO_ROOT", vault)
    monkeypatch.setattr(build_mod, "SOURCE_ROOT", vault)
    monkeypatch.setattr(build_mod, "RAW_DIR", vault / "raw")
    monkeypatch.setattr(build_mod, "RAW_SESSIONS", vault / "raw" / "sessions")
    monkeypatch.setattr(build_mod, "DEFAULT_OUT_DIR", site)
    monkeypatch.setattr(build_mod, "PROJECTS_META_DIR", wiki / "projects")
    monkeypatch.setattr(build_mod, "compile_docs_site", lambda *a, **k: [])
    return build_site(
        out_dir=site,
        raw_sessions=vault / "raw" / "sessions",
        raw_dir=vault / "raw",
        wiki_dir=wiki,
    )


# ── tech-considerations §3.1 — a vault carrying no optional frontmatter ────


def test_vault_with_no_optional_frontmatter_anywhere_builds_clean(
    tmp_path: Path, monkeypatch
):
    """No session carries ``date:``, no wiki page carries ``last_updated:``.

    This is the legacy-vault floor: every date on a topic or a project page is
    *derived*, never invented, so a vault that never wrote the optional fields
    must still build and render every page with no date shown anywhere, no
    empty heading, and no dangling label (tech-considerations §3, item 1).
    """
    # @regression
    paths = _scaffold_vault(tmp_path, project="toolkit")
    topics = ["Hazel", "Batching", "toolkit", "Unfiled", "Gamma"]
    for j in range(3):
        _write_session(paths, f"s{j}", topics, project="toolkit", date=None)

    for folder, stem in (("entities", "Hazel"), ("concepts", "Batching"),
                          ("projects", "toolkit")):
        _write_wiki_page(paths, folder, stem, "", "A fixture page.\n")

    graph = build_topic_graph(paths["wiki"], min_sessions=2)
    assert len(graph["nodes"]) >= 5, "fixture must clear the sparse-graph floor"

    rc = _run_build(paths, monkeypatch)
    assert rc == 0

    topics_dir = paths["site"] / "topics"
    pages = sorted(topics_dir.glob("*.html"))
    assert len(pages) >= 6  # 5 topics + index
    for path in pages:
        html = path.read_text(encoding="utf-8")
        assert not _EMPTY_HEADING.search(html), f"empty heading in {path.name}"
        assert "topic-activity" not in html, f"invented activity date in {path.name}"
        assert "topic-reviewed" not in html, f"invented review date in {path.name}"
        sub = _HERO_SUB.search(html)
        if sub:
            line = sub.group(1)
            assert not _DATE_RE.search(line), f"a date leaked into {path.name}"
            assert "· ·" not in line
            assert not line.strip().startswith("·")
            assert not line.strip().endswith("·")

    project_page = (paths["site"] / "projects" / "toolkit.html").read_text(
        encoding="utf-8"
    )
    project_sub = _HERO_SUB.search(project_page)
    assert project_sub, "project page carries no hero subtitle"
    assert "created" not in project_sub.group(1)
    assert "updated" not in project_sub.group(1)
    assert not _EMPTY_HEADING.search(project_page)


# ── tech-considerations §3.2 — pre-#102 project page, full build ───────────


def test_pre_102_project_page_routes_across_every_surface(tmp_path: Path, monkeypatch):
    """A ``type: entity`` + ``entity_type: project`` page under ``wiki/projects/``
    must still resolve to kind ``projects`` and route to its project page, on
    every surface the build writes — not just in the lookup helper.

    Covers tech-considerations §3, item 2, plus the "project routing is
    consistent across every surface" requirement, including a
    ``[[wikilink]]`` citation inside another topic's Key Facts content —
    the one surface the per-slice project-routing tests exercise only as a
    unit test against a hand-built URL dict, never through a real build.
    """
    # @regression
    paths = _scaffold_vault(tmp_path, project="legacy-app")
    # "legacy-app" gets real sessions -> a built project page. The other
    # topics pad the graph past _TOPIC_GRAPH_MIN_NODES.
    topics = ["legacy-app", "Hazel", "Batching", "Sparse", "Unfiled"]
    for j in range(3):
        _write_session(paths, f"s{j}", topics, project="legacy-app")

    projects_dir = paths["wiki"] / "projects"
    projects_dir.mkdir(parents=True)
    (projects_dir / "legacy-app.md").write_text(
        '---\ntitle: "legacy-app"\ntype: entity\nentity_type: project\n---\n\n'
        "# legacy-app\n\nA pre-#102 project stub.\n",
        encoding="utf-8",
    )
    # Key Facts on an entity page cite the legacy project by name.
    (paths["wiki"] / "entities").mkdir(parents=True)
    (paths["wiki"] / "entities" / "Hazel.md").write_text(
        '---\ntitle: "Hazel"\ntype: entity\n---\n\n# Hazel\n\n'
        "## Key Facts\n- Shares infrastructure with [[legacy-app]].\n",
        encoding="utf-8",
    )

    graph = build_topic_graph(paths["wiki"], min_sessions=2)
    assert len(graph["nodes"]) >= 5, "fixture must clear the sparse-graph floor"
    pre_build = {n["id"]: n for n in graph["nodes"]}
    assert pre_build["legacy-app"]["kind"] == "projects", (
        "fixture is broken: the pre-#102 page must still be kinded as a project"
    )

    rc = _run_build(paths, monkeypatch)
    assert rc == 0

    # Surface 1: the map's double-click target (the embedded graph payload).
    graph_html = (paths["site"] / "graph.html").read_text(encoding="utf-8")
    m = _GRAPH_JSON.search(graph_html)
    assert m, "graph.html carries no embedded graph payload"
    nodes = {n["id"]: n for n in json.loads(m.group(1))["nodes"]}
    assert nodes["legacy-app"]["kind"] == "projects"
    assert nodes["legacy-app"]["site_url"] == "projects/legacy-app.html"
    assert (paths["site"] / "projects" / "legacy-app.html").is_file()

    # Surface 2: the search index.
    idx = json.loads((paths["site"] / "search-index.json").read_text(encoding="utf-8"))
    by_title = {e["title"]: e for e in idx["entries"] if e.get("type") == "topic"}
    assert by_title["legacy-app"]["url"] == "projects/legacy-app.html"

    # Surface 3: topics/index.html.
    topics_index = (paths["site"] / "topics" / "index.html").read_text(encoding="utf-8")
    assert 'href="../projects/legacy-app.html">legacy-app</a>' in topics_index

    # Surface 4: a [[wikilink]] citation inside another topic's Key Facts
    # content, resolved and rendered through the real build pipeline.
    hazel_page = (paths["site"] / "topics" / "hazel.html").read_text(encoding="utf-8")
    assert '<a href="../projects/legacy-app.html">legacy-app</a>' in hazel_page
    assert "[[" not in hazel_page


# ── tech-considerations §3.3 — last_updated quoted vs bare ─────────────────


def test_last_updated_quoted_and_bare_render_identically(tmp_path: Path, monkeypatch):
    """``last_updated: "2026-04-02"`` and ``last_updated: 2026-04-02`` must
    produce the same Reviewed date on the rendered topic page.

    Both spellings exist in real vaults (``synth/pipeline.py`` writes quoted
    in one place and bare in another); a reader must never see them treated
    differently just because of which code path wrote the frontmatter.
    """
    # @regression
    paths = _scaffold_vault(tmp_path)
    topics = ["Hazel", "Batching", "Sparse", "Unfiled", "Gamma"]
    for j in range(3):
        _write_session(paths, f"s{j}", topics)

    _write_wiki_page(
        paths, "entities", "Hazel", 'last_updated: "2026-04-02"\n', "Quoted date.\n"
    )
    _write_wiki_page(
        paths, "concepts", "Batching", "last_updated: 2026-04-02\n", "Bare date.\n"
    )

    graph = build_topic_graph(paths["wiki"], min_sessions=2)
    assert len(graph["nodes"]) >= 5, "fixture must clear the sparse-graph floor"

    rc = _run_build(paths, monkeypatch)
    assert rc == 0

    for slug in ("hazel", "batching"):
        page = (paths["site"] / "topics" / f"{slug}.html").read_text(encoding="utf-8")
        sub = _HERO_SUB.search(page)
        assert sub, f"no identity line on {slug}.html"
        assert '<span class="topic-reviewed">Reviewed 2026-04-02</span>' in sub.group(1), (
            f"{slug}.html: quoted and bare last_updated must render identically\n"
            f"{sub.group(1)}"
        )
        # The raw quote character must never leak into the rendered page.
        assert '"2026-04-02"' not in page


# ── tech-considerations §3.4 — search-index.json key guardrail ─────────────


def test_search_index_topic_entries_carry_only_the_frozen_keys(tmp_path: Path):
    """Topic entries in ``site/search-index.json`` must carry exactly the
    keys ``docs/reference/reader-api.md`` freezes for the reader contract.

    #108 adds several new fields to a graph *node* (``kind``, ``first_seen``,
    ``last_seen``, ``last_updated``, ``wiki_slug``, ``wiki_path``,
    ``wiki_site_url``). ``build_search_index`` hand-constructs each topic
    entry rather than copying the node, so none of those fields should ever
    reach the index — this guardrail fails first if a future edit switches
    to copying the node wholesale.
    """
    # @regression
    src = tmp_path / "sessions" / "demo" / "one.md"
    src.parent.mkdir(parents=True)
    body = "# one\nbody\n"
    src.write_text(body, encoding="utf-8")
    sources = [(src, {"project": "demo", "slug": "one", "date": "2026-04-19"}, body)]
    groups = {"demo": sources}
    out = tmp_path / "site"
    out.mkdir()

    # A node carrying every #108 field, to prove none of it leaks through.
    topics = [{
        "id": "Hazel",
        "site_url": "topics/hazel.html",
        "session_count": 3,
        "aliases": ["hazel"],
        "description": "a fixture topic",
        "kind": "entities",
        "first_seen": "2026-01-01",
        "last_seen": "2026-02-01",
        "last_updated": "2026-03-01",
        "wiki_slug": "Hazel",
        "wiki_path": "wiki/entities/Hazel.md",
        "wiki_site_url": None,
        "degree": 2,
    }]
    build_search_index(sources, groups, out, topics=topics)
    data = json.loads((out / "search-index.json").read_text(encoding="utf-8"))
    topic_entries = [e for e in data["entries"] if e.get("type") == "topic"]
    assert len(topic_entries) == 1
    frozen_keys = {"id", "url", "title", "type", "project", "date", "model", "body"}
    assert set(topic_entries[0].keys()) == frozen_keys, (
        f"topic entry keys drifted from the frozen reader contract: "
        f"{sorted(topic_entries[0].keys())}"
    )
    for leaked in ("kind", "first_seen", "last_seen", "last_updated",
                   "wiki_slug", "wiki_path", "wiki_site_url", "degree"):
        assert leaked not in topic_entries[0]


# ── FR8 AC2 — every combination together, at once ───────────────────────


def test_mixed_vault_completes_and_every_topic_page_opens(tmp_path: Path, monkeypatch):
    """A wiki mixing described and undescribed topics, pages with and without
    recorded content, and pages with and without dates, must build without
    error, and every topic page must open (FR8, second acceptance criterion).

    Per-slice tests each vary one or two of these dimensions; this fixture
    combines all of them in a single vault the way a real, partly-curated
    wiki actually looks, so a rewrite that handles each dimension correctly
    in isolation but breaks on their combination is caught here.
    """
    # @regression
    paths = _scaffold_vault(tmp_path, project="shipped")
    topics = ["shipped", "Hazel", "Batching", "Sparse", "Unfiled"]
    dates = ["2026-04-01", None, "2026-04-09"]
    for j, date in enumerate(dates):
        _write_session(paths, f"s{j}", topics, project="shipped", date=date)

    # shipped: a project page WITH a review date and real sessions.
    (paths["wiki"] / "projects").mkdir(parents=True)
    (paths["wiki"] / "projects" / "shipped.md").write_text(
        '---\ntitle: "shipped"\ntype: project\nlast_updated: 2026-04-10\n---\n\n'
        "# shipped\n\nA fixture project.\n",
        encoding="utf-8",
    )
    # Hazel: entity WITH last_updated AND Key Facts content.
    (paths["wiki"] / "entities").mkdir(parents=True)
    (paths["wiki"] / "entities" / "Hazel.md").write_text(
        '---\ntitle: "Hazel"\ntype: entity\nlast_updated: 2026-04-02\n---\n\n'
        "# Hazel\n\n## Key Facts\n- Ships weekly.\n",
        encoding="utf-8",
    )
    # Batching: concept with NO last_updated and NO content beyond the title.
    (paths["wiki"] / "concepts").mkdir(parents=True)
    (paths["wiki"] / "concepts" / "Batching.md").write_text(
        '---\ntitle: "Batching"\ntype: concept\n---\n\n# Batching\n',
        encoding="utf-8",
    )
    # Sparse: entity with an empty Key Facts section (content -> None).
    (paths["wiki"] / "entities" / "Sparse.md").write_text(
        '---\ntitle: "Sparse"\ntype: entity\n---\n\n# Sparse\n\n## Key Facts\n\n',
        encoding="utf-8",
    )
    # Unfiled: no backing page at all.

    graph = build_topic_graph(paths["wiki"], min_sessions=2)
    assert len(graph["nodes"]) >= 5, "fixture must clear the sparse-graph floor"

    rc = _run_build(paths, monkeypatch)
    assert rc == 0

    pages = sorted((paths["site"] / "topics").glob("*.html"))
    # 5 topics + index; "shipped" routes to projects/ instead but its topic
    # page is never written for a routed project, so allow for that.
    assert len(pages) >= 5
    for path in pages:
        html = path.read_text(encoding="utf-8")
        assert not _EMPTY_HEADING.search(html), f"empty heading in {path.name}"

    # Sparse's Key Facts section recorded nothing, so no content block at all —
    # not a heading with an empty body underneath it.
    sparse_page = (paths["site"] / "topics" / "sparse.html").read_text(encoding="utf-8")
    assert "topic-page-content" not in sparse_page
    assert "Key Facts" not in sparse_page

    project_page = (paths["site"] / "projects" / "shipped.html").read_text(
        encoding="utf-8"
    )
    assert not _EMPTY_HEADING.search(project_page)
    assert "Connected topics" in project_page
