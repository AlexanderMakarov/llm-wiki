"""Reconcile wiki/index.md with the pages on disk (#71).

The catalog drifts both ways during ordinary use: `sync` seeds project stubs
nothing lists, and hand-deleted pages leave dead index links behind.
`reindex_wiki` / `plan_reindex` fix both directions; `sync` and `synthesize`
call them automatically. These tests pin the reconciliation semantics —
above all that it never rewrites a hand-written description.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import patch

from llmwiki.candidates import promote
from llmwiki.cli import cmd_sync
from llmwiki.lint import load_pages, run_all
from llmwiki.reindex import plan_reindex, reindex_wiki, seed_index_text

SEEDED_HEADINGS = ("## Sources (0)", "## Entities (0)", "## Projects (0)")


def _page(path: Path, title: str, **meta: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    front = "".join(f"{k}: {v}\n" for k, v in meta.items())
    path.write_text(
        f'---\ntitle: "{title}"\n{front}---\n\n# {title}\n\nbody\n',
        encoding="utf-8",
    )


def _seed_wiki(tmp_path: Path, *, index: str | None = None) -> Path:
    """A vault wiki shaped like `init` leaves it, plus drifted pages."""
    wiki = tmp_path / "wiki"
    (wiki / "sources").mkdir(parents=True)
    (wiki / "entities").mkdir()
    (wiki / "concepts").mkdir()
    (wiki / "syntheses").mkdir()
    (wiki / "overview.md").write_text("# Overview\n", encoding="utf-8")
    (wiki / "log.md").write_text("# Wiki Log\n", encoding="utf-8")
    (wiki / "index.md").write_text(
        seed_index_text() if index is None else index, encoding="utf-8"
    )
    return wiki


def _index(wiki: Path) -> str:
    return (wiki / "index.md").read_text(encoding="utf-8")


# ─── The drift the issue reports ───────────────────────────────────────


def test_seeded_index_matches_the_reindex_header(tmp_path: Path) -> None:
    """`init`'s seed and `reindex` share one header (no drift between them)."""
    assert all(h in seed_index_text() for h in SEEDED_HEADINGS)


def test_unlisted_pages_are_added_with_refreshed_counts(tmp_path: Path) -> None:
    wiki = _seed_wiki(tmp_path)
    _page(wiki / "projects" / "awos-audit.md", "awos-audit", type="project")
    _page(wiki / "projects" / "code-hops.md", "code-hops", type="project")
    _page(wiki / "entities" / "Anthropic.md", "Anthropic")
    _page(
        wiki / "sources" / "proj" / "2026-07-01-hello.md",
        "Session: hello",
        project="proj",
        date="2026-07-01",
    )

    plan = reindex_wiki(wiki)

    assert plan is not None and plan.changed
    assert plan.added == [
        "sources/proj/2026-07-01-hello.md",
        "entities/Anthropic.md",
        "projects/awos-audit.md",
        "projects/code-hops.md",
    ]
    text = _index(wiki)
    assert "## Projects (2)" in text
    assert "- [awos-audit](projects/awos-audit.md)" in text
    assert "## Entities (1)" in text
    # Session sources keep the `project · date` suffix the catalog has always
    # shown for them; a page with neither is listed bare.
    assert (
        "- [Session: hello](sources/proj/2026-07-01-hello.md) — proj · 2026-07-01"
        in text
    )


def test_reindex_brings_index_sync_to_zero(tmp_path: Path) -> None:
    """The acceptance criterion: a drifted vault lints clean afterwards."""
    wiki = _seed_wiki(tmp_path)
    for slug in ("awos-audit", "code-hops", "evrika-1"):
        _page(wiki / "projects" / f"{slug}.md", slug, type="project")
    _page(wiki / "concepts" / "RAG.md", "RAG")
    _page(wiki / "syntheses" / "why-caching.md", "Why caching")

    before = run_all(load_pages(wiki), selected=["index_sync"])
    assert len(before) == 5, before

    reindex_wiki(wiki)

    assert run_all(load_pages(wiki), selected=["index_sync"]) == []


def test_dead_index_links_are_dropped(tmp_path: Path) -> None:
    wiki = _seed_wiki(
        tmp_path,
        index=(
            "# Wiki Index\n\n## Entities (2)\n"
            "- [Anthropic](entities/Anthropic.md) — the lab behind Claude\n"
            "- [OpenAI](entities/OpenAI.md) — deleted by hand\n"
        ),
    )
    _page(wiki / "entities" / "Anthropic.md", "Anthropic")

    plan = reindex_wiki(wiki)

    assert plan is not None
    assert plan.removed == ["entities/OpenAI.md"]
    text = _index(wiki)
    assert "OpenAI" not in text
    assert "## Entities (1)" in text
    assert run_all(load_pages(wiki), selected=["index_sync"]) == []


def test_duplicate_countless_heading_is_collapsed(tmp_path: Path) -> None:
    """The exact shape #71 found on a real vault.

    The previous writer matched `^## Sources$`, so against the seeded
    `## Sources (0)` it appended a *second*, count-less `## Sources` below it
    and left both on disk.
    """
    wiki = _seed_wiki(
        tmp_path,
        index=(
            "# Wiki Index\n\n## Sources (0)\n\n## Entities (0)\n\n"
            "## Sources\n- [Session: hello](sources/hello.md) — proj · 2026-07-01\n"
        ),
    )
    _page(wiki / "sources" / "hello.md", "Session: hello", project="proj")

    reindex_wiki(wiki)

    text = _index(wiki)
    assert text.count("## Sources") == 1
    assert "## Sources (1)" in text
    assert "sources/hello.md" in text


# ─── What reindex must not touch ───────────────────────────────────────


def test_hand_written_descriptions_survive_verbatim(tmp_path: Path) -> None:
    """Descriptions are human/agent prose — reindex preserves, never rewrites.

    The em-dash inside the *title* is deliberate: splitting a bullet on the
    first ` — ` instead of on the link would mangle every session entry, whose
    titles look like `Session: 5d9d20d6 — 2026-06-08`.
    """
    listed = (
        "- [Session: 5d9d20d6 — 2026-06-08](sources/2026-06-08-5d9d20d6.md)"
        " — hand-written note about the outage\n"
    )
    wiki = _seed_wiki(tmp_path, index=f"# Wiki Index\n\n## Sources (1)\n{listed}")
    # Frontmatter deliberately disagrees with the listed title + description.
    _page(
        wiki / "sources" / "2026-06-08-5d9d20d6.md",
        "Session: renamed by a later synth",
        project="other",
        date="2026-06-08",
    )
    _page(wiki / "entities" / "Anthropic.md", "Anthropic")

    reindex_wiki(wiki)

    text = _index(wiki)
    assert listed.strip() in text
    assert "renamed by a later synth" not in text
    assert "- [Anthropic](entities/Anthropic.md)" in text


def test_unmanaged_sections_and_preamble_pass_through(tmp_path: Path) -> None:
    wiki = _seed_wiki(
        tmp_path,
        index=(
            "# Wiki Index\n\nRead the overview first.\n\n"
            "## Overview (1)\n- [Overview](overview.md)\n\n"
            "## Reading order\n1. overview\n2. everything else\n\n"
            "## Sources (0)\n"
        ),
    )
    _page(wiki / "sources" / "hello.md", "Session: hello")

    reindex_wiki(wiki)

    text = _index(wiki)
    assert "Read the overview first." in text
    assert "## Reading order\n1. overview\n2. everything else" in text
    assert "## Overview (1)\n- [Overview](overview.md)" in text
    assert "## Sources (1)" in text


def test_page_bodies_are_never_touched(tmp_path: Path) -> None:
    wiki = _seed_wiki(tmp_path)
    page = wiki / "concepts" / "RAG.md"
    _page(page, "RAG")
    before = page.read_text(encoding="utf-8")

    reindex_wiki(wiki)

    assert page.read_text(encoding="utf-8") == before


def test_second_run_is_a_no_op(tmp_path: Path) -> None:
    wiki = _seed_wiki(tmp_path)
    _page(wiki / "projects" / "awos-audit.md", "awos-audit")
    reindex_wiki(wiki)
    first = _index(wiki)

    plan = plan_reindex(wiki)

    assert plan is not None and not plan.changed
    assert plan.text == first


# ─── Folders beyond the canonical five ─────────────────────────────────


def test_non_canonical_folder_gets_its_own_section(tmp_path: Path) -> None:
    """A vault may carry folders the schema does not name — a page type added
    later, or one a user keeps by hand.

    Naming the section after the folder lists those pages instead of leaving
    them as permanent `index_sync` noise.
    """
    wiki = _seed_wiki(tmp_path)
    _page(wiki / "decisions" / "adopt-cache-tiers.md", "Adopt cache tiers")
    _page(wiki / "playbooks" / "cache-budget-review.md", "Cache budget review")

    reindex_wiki(wiki)

    text = _index(wiki)
    assert "## Decisions (1)" in text
    assert "## Playbooks (1)" in text
    assert run_all(load_pages(wiki), selected=["index_sync"]) == []


def test_context_files_empty_folders_and_system_pages_are_skipped(
    tmp_path: Path,
) -> None:
    wiki = _seed_wiki(tmp_path)
    (wiki / "entities" / "_context.md").write_text(
        "People and orgs live here.\n", encoding="utf-8"
    )
    (wiki / "hot").mkdir()
    _page(wiki / "MEMORY.md", "MEMORY")

    reindex_wiki(wiki)

    text = _index(wiki)
    assert "_context.md" not in text
    assert "## Hot" not in text
    assert "MEMORY.md" not in text


def test_loose_root_page_is_listed_once(tmp_path: Path) -> None:
    """A saved `lint-report.md` is a real page lint expects to find listed."""
    wiki = _seed_wiki(tmp_path)
    _page(wiki / "lint-report.md", "Lint report")

    reindex_wiki(wiki)

    text = _index(wiki)
    assert "## Pages (1)" in text
    assert text.count("lint-report.md") == 1
    assert run_all(load_pages(wiki), selected=["index_sync"]) == []


def test_entry_filed_under_the_wrong_section_moves(tmp_path: Path) -> None:
    wiki = _seed_wiki(
        tmp_path,
        index=(
            "# Wiki Index\n\n## Sources (0)\n\n"
            "## Entities (1)\n- [awos-audit](projects/awos-audit.md) — audit tooling\n"
        ),
    )
    _page(wiki / "projects" / "awos-audit.md", "awos-audit")

    plan = reindex_wiki(wiki)

    assert plan is not None
    assert plan.added == [] and plan.removed == []
    text = _index(wiki)
    assert "## Entities (0)" in text
    assert (
        "## Projects (1)\n- [awos-audit](projects/awos-audit.md) — audit tooling"
        in text
    )


def test_empty_wiki_gets_no_index(tmp_path: Path) -> None:
    """Nothing to catalog: don't seed an index as a side effect."""
    wiki = tmp_path / "wiki"
    wiki.mkdir()

    assert plan_reindex(wiki) is None
    assert not (wiki / "index.md").exists()


def test_missing_index_is_seeded_from_disk(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    _page(wiki / "entities" / "Anthropic.md", "Anthropic")

    reindex_wiki(wiki)

    text = _index(wiki)
    assert "# Wiki Index" in text
    assert "## Entities (1)" in text


def test_empty_candidates_section_pruned_when_folder_empty(tmp_path: Path) -> None:
    """#101: leftover ## Candidates with dead bullets is dropped when empty."""
    wiki = _seed_wiki(
        tmp_path,
        index=(
            "# Wiki Index\n\n"
            "## Sources (0)\n\n"
            "## Entities (0)\n\n"
            "## Candidates (2)\n"
            "- [Gone](candidates/entities/Gone.md)\n"
            "- [AlsoGone](candidates/concepts/AlsoGone.md)\n\n"
            "## Concepts (0)\n"
        ),
    )

    plan = plan_reindex(wiki)
    assert plan is not None
    assert plan.changed
    assert any("Gone" in href or "AlsoGone" in href for href in plan.removed)
    reindex_wiki(wiki)
    text = _index(wiki)
    assert "## Candidates" not in text
    assert "candidates/entities/Gone.md" not in text
    assert run_all(load_pages(wiki), selected=["index_sync"]) == []


def test_promote_reconciles_stale_candidates_section(tmp_path: Path) -> None:
    """#101: promote of the last stub clears dead Candidates catalog bullets."""
    wiki = _seed_wiki(
        tmp_path,
        index=(
            "# Wiki Index\n\n"
            "## Sources (0)\n\n"
            "## Entities (0)\n\n"
            "## Candidates (1)\n"
            "- [KeepMe](candidates/entities/KeepMe.md)\n\n"
            "## Concepts (0)\n"
        ),
    )
    _page(
        wiki / "candidates" / "entities" / "KeepMe.md",
        "KeepMe",
        type="entity",
        status="candidate",
    )

    promote("KeepMe", wiki)

    text = _index(wiki)
    assert "## Candidates" not in text
    assert "candidates/entities/KeepMe.md" not in text
    assert "entities/KeepMe.md" in text
    assert run_all(load_pages(wiki), selected=["index_sync"]) == []


def test_sync_leaves_no_index_error_for_a_new_project(tmp_path: Path) -> None:
    """The other half of #71: sync seeds the stub, so sync must list it.

    `build --seed-project-stubs` (which sync always passes) is stubbed out
    here — this asserts the wiring, not the seeder — but it writes the same
    `wiki/projects/<slug>.md` the real one does.
    """
    vault = tmp_path / "vault"
    wiki = _seed_wiki(vault)

    def fake_build_site(**kwargs: object) -> int:
        assert kwargs["seed_project_stubs"] is True
        _page(Path(str(kwargs["wiki_dir"])) / "projects" / "awos-audit.md", "awos-audit")
        return 0

    args = argparse.Namespace(
        vault=vault, allow_overwrite=False, adapter=None, since=None, project=None,
        include_current=False, force=False, auto_build=True, auto_lint=False,
        status=False, recent=0,
    )
    with patch("llmwiki.cli.convert_all", return_value=0), \
         patch("llmwiki.cli.refresh_synth_pending", return_value=None), \
         patch("llmwiki.cli.build_site", side_effect=fake_build_site), \
         patch("llmwiki.cli._should_run_after_sync", return_value=True), \
         patch("llmwiki.cli._load_schedule_config", return_value={"build": "on-sync"}):
        assert cmd_sync(args) == 0

    assert "projects/awos-audit.md" in _index(wiki)
    assert run_all(load_pages(wiki), selected=["index_sync"]) == []
