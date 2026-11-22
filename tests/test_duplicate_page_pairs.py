"""Tests for read-only duplicate curated/project page pair detection (#365).

Also covers lint rule registration / findings and reference-doc mentions
for doctor id ``candidates.duplicate_pairs`` (#418 Slice 6).

# @spec: 418-duplicate-page-review
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from llmwiki import REPO_ROOT
from llmwiki.dismissal_ledger import archive_candidates_dir, upsert_keep_distinct
from llmwiki.lint import REGISTRY, load_pages, run_all
from llmwiki.lint import rules as _lint_rules
from llmwiki.topics import detect_duplicate_pairs
from llmwiki.topics_consolidate import CACHE_VERSION, cache_path

assert _lint_rules is not None  # register lint REGISTRY


def _session(
    body_links: list[str], *, stem: str, project: str = "proj"
) -> str:
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
        (src / f"{stem}.md").write_text(
            _session(links, stem=stem),
            encoding="utf-8",
        )
    return wiki


def _page(wiki: Path, folder: str, name: str, *, page_type: str) -> Path:
    path = wiki / folder / f"{name}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'---\ntitle: "{name}"\ntype: {page_type}\n---\n\n# {name}\n',
        encoding="utf-8",
    )
    return path


def _write_dirty_topics_cache(
    wiki: Path, topics: list[dict[str, Any]], *, dropped: list[Any] | None = None
) -> None:
    """Persist a pre-repair topics cache (bypasses parse_and_cache detach).

    Duplicate detection reads unconstrained folds; :func:`parse_and_cache`
    would strip curated↔curated aliases before disk write (#365).
    """
    payload = {
        "version": CACHE_VERSION,
        "topics": topics,
        "dropped": list(dropped or []),
    }
    cache_path(wiki).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _pair_paths(pairs) -> set[frozenset[str]]:
    return {p.paths for p in pairs}


def test_folded_onto_other_curated_page_is_a_pair(tmp_path: Path) -> None:
    """Cache fold of one live entity spelling onto another surfaces one pair."""
    wiki = _make_wiki(
        tmp_path,
        {
            "s1": ["wgctl", "Widget"],
            "s2": ["WGCTL", "Widget"],
            "s3": ["Widget CLI", "Widget"],
        },
    )
    _page(wiki, "entities", "wgctl", page_type="entity")
    _page(wiki, "entities", "Widget CLI", page_type="entity")
    _write_dirty_topics_cache(
        wiki,
        [
            {
                "canonical": "Widget CLI",
                "description": "CLI tool.",
                "aliases": ["wgctl", "WGCTL"],
            },
            {"canonical": "Widget", "aliases": []},
        ],
    )

    pairs = detect_duplicate_pairs(wiki)

    assert len(pairs) == 1
    pair = pairs[0]
    assert pair.paths == frozenset(
        {"wiki/entities/wgctl.md", "wiki/entities/Widget CLI.md"}
    )
    assert pair.suspicion == "folded onto other curated page"
    assert pair.description == "CLI tool."
    titles = {pair.a.title, pair.b.title}
    assert titles == {"wgctl", "Widget CLI"}
    by_title = {pair.a.title: pair.a, pair.b.title: pair.b}
    assert by_title["wgctl"].session_count == 2
    assert by_title["Widget CLI"].session_count == 1
    assert by_title["wgctl"].kind == "entities"


def test_shared_pageless_canonical_lists_claimant_pair(tmp_path: Path) -> None:
    """Two curated pages folded onto one page-less topic form a shared-topic pair."""
    wiki = _make_wiki(
        tmp_path,
        {
            "s1": ["wgctl", "Widget"],
            "s2": ["Widget CLI", "Widget"],
            "s3": ["Widget Tool", "Widget"],
        },
    )
    _page(wiki, "entities", "wgctl", page_type="entity")
    _page(wiki, "entities", "Widget CLI", page_type="entity")
    _write_dirty_topics_cache(
        wiki,
        [
            {
                "canonical": "Widget Tool",
                "description": "Shared.",
                "aliases": ["wgctl", "Widget CLI"],
            },
            {"canonical": "Widget", "aliases": []},
        ],
    )

    pairs = detect_duplicate_pairs(wiki)

    assert len(pairs) == 1
    pair = pairs[0]
    assert pair.paths == frozenset(
        {"wiki/entities/wgctl.md", "wiki/entities/Widget CLI.md"}
    )
    assert pair.suspicion == "shared page-less topic"
    assert pair.description == "Shared."


def test_fold_direction_does_not_duplicate_the_undirected_pair(tmp_path: Path) -> None:
    """A→B and B→A folds share one ``frozenset`` path key (undirected)."""
    sessions = {
        "s1": ["AlphaTool", "Widget"],
        "s2": ["BetaTool", "Widget"],
    }
    wiki = _make_wiki(tmp_path, sessions)
    _page(wiki, "entities", "AlphaTool", page_type="entity")
    _page(wiki, "entities", "BetaTool", page_type="entity")

    _write_dirty_topics_cache(
        wiki,
        [
            {"canonical": "AlphaTool", "aliases": ["BetaTool"]},
            {"canonical": "Widget", "aliases": []},
        ],
    )
    forward = detect_duplicate_pairs(wiki)

    _write_dirty_topics_cache(
        wiki,
        [
            {"canonical": "BetaTool", "aliases": ["AlphaTool"]},
            {"canonical": "Widget", "aliases": []},
        ],
    )
    reverse = detect_duplicate_pairs(wiki)

    assert len(forward) == 1
    assert len(reverse) == 1
    expected = frozenset(
        {"wiki/entities/AlphaTool.md", "wiki/entities/BetaTool.md"}
    )
    assert forward[0].paths == expected
    assert reverse[0].paths == expected
    assert _pair_paths(forward) == _pair_paths(reverse)


def test_project_page_folded_with_concept_is_included(tmp_path: Path) -> None:
    """Duplicate review covers projects, not only entities/concepts."""
    wiki = _make_wiki(
        tmp_path,
        {
            "s1": ["Widget Notes Style", "Widget"],
            "s2": ["widget-notes", "Widget"],
        },
    )
    _page(wiki, "concepts", "Widget Notes Style", page_type="concept")
    _page(wiki, "projects", "widget-notes", page_type="project")
    _write_dirty_topics_cache(
        wiki,
        [
            {"canonical": "widget-notes", "aliases": ["Widget Notes Style"]},
            {"canonical": "Widget", "aliases": []},
        ],
    )

    pairs = detect_duplicate_pairs(wiki)

    assert len(pairs) == 1
    pair = pairs[0]
    assert pair.paths == frozenset(
        {
            "wiki/concepts/Widget Notes Style.md",
            "wiki/projects/widget-notes.md",
        }
    )
    kinds = {pair.a.kind, pair.b.kind}
    assert kinds == {"concepts", "projects"}
    assert pair.suspicion == "folded onto other curated page"


def test_keep_distinct_pair_is_omitted_from_detection(tmp_path: Path) -> None:
    """Ledger keep-distinct suppresses the same undirected pair on re-detect."""
    wiki = _make_wiki(
        tmp_path,
        {
            "s1": ["Widget Notes Style", "Widget"],
            "s2": ["widget-notes", "Widget"],
        },
    )
    _page(wiki, "concepts", "Widget Notes Style", page_type="concept")
    _page(wiki, "projects", "widget-notes", page_type="project")
    _write_dirty_topics_cache(
        wiki,
        [
            {"canonical": "widget-notes", "aliases": ["Widget Notes Style"]},
            {"canonical": "Widget", "aliases": []},
        ],
    )
    assert len(detect_duplicate_pairs(wiki)) == 1

    archive_candidates_dir(wiki).mkdir(parents=True, exist_ok=True)
    upsert_keep_distinct(
        wiki,
        a="widget-notes",
        b="Widget Notes Style",
        why="different subjects",
        decided_at="2026-03-01T12:00:00+00:00",
    )

    assert detect_duplicate_pairs(wiki) == []


def test_no_duplicate_pairs_when_pages_are_distinct_topics(tmp_path: Path) -> None:
    """Unrelated curated pages with separate cache topics yield an empty list."""
    wiki = _make_wiki(
        tmp_path,
        {
            "s1": ["OpenClaw", "Bun"],
            "s2": ["OpenClaw", "Bun"],
        },
    )
    _page(wiki, "entities", "OpenClaw", page_type="entity")
    _page(wiki, "entities", "Bun", page_type="entity")
    _write_dirty_topics_cache(
        wiki,
        [
            {"canonical": "OpenClaw", "aliases": []},
            {"canonical": "Bun", "aliases": []},
        ],
    )

    assert detect_duplicate_pairs(wiki) == []


# ─── lint rule + reference coverage (#418 Slice 6) ─────────────────────


def test_duplicate_page_pairs_lint_rule_registered() -> None:
    """``duplicate_page_pairs`` is a registered lint rule distinct from body-similarity."""
    assert "duplicate_page_pairs" in REGISTRY
    assert REGISTRY["duplicate_page_pairs"].severity == "info"
    assert "duplicate_detection" in REGISTRY
    assert REGISTRY["duplicate_page_pairs"].name != REGISTRY["duplicate_detection"].name


def test_lint_flags_pending_vocabulary_fold_pair(tmp_path: Path) -> None:
    """Lint emits one info finding per pending fold pair with how to open the list."""
    wiki = _make_wiki(
        tmp_path,
        {
            "s1": ["wgctl", "Widget"],
            "s2": ["WGCTL", "Widget"],
            "s3": ["Widget CLI", "Widget"],
        },
    )
    _page(wiki, "entities", "wgctl", page_type="entity")
    _page(wiki, "entities", "Widget CLI", page_type="entity")
    _write_dirty_topics_cache(
        wiki,
        [
            {
                "canonical": "Widget CLI",
                "description": "CLI tool.",
                "aliases": ["wgctl", "WGCTL"],
            },
            {"canonical": "Widget", "aliases": []},
        ],
    )

    pages = load_pages(tmp_path)
    issues = run_all(pages, selected=["duplicate_page_pairs"])
    assert len(issues) == 1
    issue = issues[0]
    assert issue["rule"] == "duplicate_page_pairs"
    assert issue["severity"] == "info"
    assert "wgctl" in issue["message"] and "Widget CLI" in issue["message"]
    assert "candidates list" in issue["message"] or "candidates.html" in issue["message"]


def test_lint_silent_when_no_duplicate_pairs(tmp_path: Path) -> None:
    """Distinct topics produce no duplicate_page_pairs lint issues."""
    wiki = _make_wiki(
        tmp_path,
        {
            "s1": ["OpenClaw", "Bun"],
            "s2": ["OpenClaw", "Bun"],
        },
    )
    _page(wiki, "entities", "OpenClaw", page_type="entity")
    _page(wiki, "entities", "Bun", page_type="entity")
    _write_dirty_topics_cache(
        wiki,
        [
            {"canonical": "OpenClaw", "aliases": []},
            {"canonical": "Bun", "aliases": []},
        ],
    )

    pages = load_pages(tmp_path)
    assert run_all(pages, selected=["duplicate_page_pairs"]) == []


def test_reference_docs_name_duplicate_page_pairs_and_doctor_id() -> None:
    """CLI + slash refs document the lint rule and doctor id (CONTRIBUTING coverage)."""
    cli = (REPO_ROOT / "docs" / "reference" / "cli.md").read_text(encoding="utf-8")
    slash = (REPO_ROOT / "docs" / "reference" / "slash-commands.md").read_text(
        encoding="utf-8"
    )
    assert "duplicate_page_pairs" in cli
    assert "candidates.duplicate_pairs" in cli
    assert "duplicate_detection" in cli  # distinct body-similarity rule still named
    assert "duplicate_page_pairs" in slash
    assert "candidates.duplicate_pairs" in slash
    agent = (
        REPO_ROOT / "llmwiki" / "agent_kit" / "commands" / "wiki-candidates.md"
    ).read_text(encoding="utf-8")
    assert "Possible duplicate pages" in agent
    assert "duplicate_page_pairs" in agent
    assert "candidates.duplicate_pairs" in agent
