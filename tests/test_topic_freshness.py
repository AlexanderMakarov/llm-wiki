"""Topic pages show activity and review as two different facts (#108, FR2).

Builds a fixture vault mixing topics that have both dates, topics that have
only one, and a topic that has neither, then asserts every topic page renders
exactly the dates it actually has — no placeholder, no borrowed value, no
label left dangling.
"""

from __future__ import annotations

import re
from pathlib import Path

import llmwiki.build as build_mod
from llmwiki.build import build_site
from llmwiki.topics import build_topic_graph

_HERO_SUB = re.compile(r'<p class="hero-sub">(.*?)</p>', re.S)
_EMPTY_HEADING = re.compile(r"<h(\d)[^>]*>\s*</h\1>")

# Two dated sessions and two undated ones, so a topic's activity dates depend
# only on the sessions that actually mention it.
_SESSIONS = {
    "s0": ("2026-04-01", ["Hazel", "Batching", "Gamma"]),
    "s1": ("2026-04-05", ["Hazel", "Batching", "Gamma"]),
    "s2": ("", ["toolkit", "Unfiled"]),
    "s3": ("", ["toolkit", "Unfiled"]),
}
# Only Hazel and toolkit record a review date of their own.
_PAGES = {
    "Hazel": ("entities", "entity", "2026-04-02"),
    "Batching": ("concepts", "concept", ""),
    "toolkit": ("projects", "project", "2026-04-09"),
}


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

    for stem, (date, topics) in _SESSIONS.items():
        links = "\n".join(f"- [[{t}]]" for t in topics)
        date_line = f"date: {date}\n" if date else ""
        (src / f"{stem}.md").write_text(
            f'---\ntitle: "{stem}"\ntype: source\nproject: proj\n{date_line}'
            f"source_file: raw/sessions/proj/{stem}.md\n"
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

    for stem, (folder, type_, last_updated) in _PAGES.items():
        review_line = f"last_updated: {last_updated}\n" if last_updated else ""
        page = wiki / folder / f"{stem}.md"
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text(
            f'---\ntitle: "{stem}"\ntype: {type_}\ntags: []\n{review_line}'
            f"---\n\n# {stem}\n\nA fixture page.\n",
            encoding="utf-8",
        )

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


def _identity_line(site: Path, slug: str) -> str:
    """The hero subtitle of one topic page — the only place dates may appear."""
    page = (site / "topics" / f"{slug}.html").read_text(encoding="utf-8")
    match = _HERO_SUB.search(page)
    assert match, f"no identity line on {slug}.html"
    return match.group(1).strip()


def test_topic_with_both_dates_shows_both_labelled_apart(tmp_path: Path, monkeypatch):
    site = _build_fixture_vault(tmp_path, monkeypatch)
    line = _identity_line(site, "hazel")
    assert '<span class="topic-activity">Active 2026-04-01 – 2026-04-05</span>' in line
    assert '<span class="topic-reviewed">Reviewed 2026-04-02</span>' in line


def test_topic_with_sessions_only_shows_activity_and_no_review(
    tmp_path: Path, monkeypatch
):
    site = _build_fixture_vault(tmp_path, monkeypatch)
    line = _identity_line(site, "batching")
    assert '<span class="topic-activity">Active 2026-04-01 – 2026-04-05</span>' in line
    assert "Reviewed" not in line
    assert "topic-reviewed" not in line


def test_topic_with_a_review_date_only_shows_no_activity(tmp_path: Path, monkeypatch):
    site = _build_fixture_vault(tmp_path, monkeypatch)
    line = _identity_line(site, "toolkit")
    assert '<span class="topic-reviewed">Reviewed 2026-04-09</span>' in line
    assert "Active" not in line
    assert "topic-activity" not in line


def test_topic_with_neither_date_shows_none_and_no_empty_label(
    tmp_path: Path, monkeypatch
):
    site = _build_fixture_vault(tmp_path, monkeypatch)
    line = _identity_line(site, "unfiled")
    assert "topic-activity" not in line
    assert "topic-reviewed" not in line
    assert "Active" not in line and "Reviewed" not in line
    # No date is borrowed from anywhere else, and nothing dangles.
    assert not re.search(r"\d{4}-\d{2}-\d{2}", line)
    assert "· ·" not in line
    assert not line.startswith("·") and not line.endswith("·")


def test_every_topic_page_builds_without_an_empty_section(tmp_path: Path, monkeypatch):
    site = _build_fixture_vault(tmp_path, monkeypatch)
    pages = sorted((site / "topics").glob("*.html"))
    assert len(pages) >= 6  # five topics plus the index
    for path in pages:
        assert not _EMPTY_HEADING.search(path.read_text(encoding="utf-8")), path.name
