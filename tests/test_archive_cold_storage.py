"""`wiki/archive/` is cold storage — one rule, every component (#140).

`archive/` is the candidate-triage reject bin: `candidates.discard()` and
`candidates.merge()` are the only writers. Discarding a candidate means the
reviewer judged the term to be noise — a tool name, an example, something
repeated by accident — so nothing that reads content may surface it again.
Every reader derived its own page set instead, and `reindex` catalogued the
reject bin that `lint` refused to load, so discarding one candidate wrote
`## Archive (N)` bullets into `index.md` that lint then reported as dead index
links, failing `lint --fail-on-errors` on a correct vault.

These tests pin the single rule (`_system_pages.is_archived_path`) across the
catalog, lint, graph, tags, backlinks and the MCP read surfaces — and pin the
one deliberate exception, the candidate harvest, which must keep counting an
archived slug as resolved or every dismissal is re-proposed on every `synth`.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from llmwiki import backlinks, tags
from llmwiki._system_pages import ARCHIVE_FOLDER, is_archived_path
from llmwiki.candidates import MIRRORED_SUBDIRS, discard
from llmwiki.candidates_harvest import harvest_targets
from llmwiki.graph import scan_pages
from llmwiki.graphify_bridge import _extract_wiki_nodes
from llmwiki.lint import load_pages, run_all, run_lint
from llmwiki.lint.report import render_json
from llmwiki.mcp.server import tool_wiki_lint, tool_wiki_query, tool_wiki_search
from llmwiki.reindex import reindex_wiki, seed_index_text


def _seed_vault(tmp_path: Path) -> Path:
    """A wiki shaped like `init` leaves it, plus the candidates/ mirror."""
    wiki = tmp_path / "wiki"
    for sub in MIRRORED_SUBDIRS:
        (wiki / sub).mkdir(parents=True, exist_ok=True)
        (wiki / "candidates" / sub).mkdir(parents=True, exist_ok=True)
    (wiki / "sources").mkdir(parents=True, exist_ok=True)
    (wiki / "overview.md").write_text("# Overview\n", encoding="utf-8")
    (wiki / "index.md").write_text(seed_index_text(), encoding="utf-8")
    return wiki


def _write_candidate(wiki: Path, kind: str, slug: str) -> Path:
    path = wiki / "candidates" / kind / f"{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'---\ntitle: "{slug}"\ntype: {kind[:-1]}\nstatus: candidate\n'
        f"last_updated: 2026-08-15\n---\n\n# {slug}\n\nCandidate body.\n",
        encoding="utf-8",
    )
    return path


def _index(wiki: Path) -> str:
    return (wiki / "index.md").read_text(encoding="utf-8")


# ─── The predicate ─────────────────────────────────────────────────────


def test_is_archived_path_matches_only_the_top_level_folder() -> None:
    assert is_archived_path((ARCHIVE_FOLDER, "candidates", "t", "Bogus.md"))
    assert is_archived_path(("archive",))
    assert not is_archived_path(())
    assert not is_archived_path(("entities", "Hetzner.md"))
    # A folder named `archive` nested under a page folder is a live page —
    # source pages are grouped by project slug, and a project called
    # `archive` must not vanish from the index without an error.
    assert not is_archived_path(("sources", "archive", "x.md"))
    assert not is_archived_path(("projects", "archive.md"))


# ─── The reported failure, end to end ──────────────────────────────────


def test_discarding_a_candidate_leaves_no_archive_entries_in_the_index(
    tmp_path: Path,
) -> None:
    """Discard → reindex → lint is clean. This is the CI failure from #140."""
    wiki = _seed_vault(tmp_path)
    _write_candidate(wiki, "entities", "Bogus")

    archived = discard("Bogus", wiki, reason="hallucinated")
    reindex_wiki(wiki)

    assert archived.is_file()
    text = _index(wiki)
    assert "## Archive" not in text
    assert "archive/" not in text
    assert run_all(load_pages(wiki), selected=["index_sync"]) == []


def test_stale_archive_section_is_pruned_from_an_existing_index(
    tmp_path: Path,
) -> None:
    """A vault carrying `## Archive (N)` from an older run self-heals."""
    wiki = _seed_vault(tmp_path)
    dest = wiki / ARCHIVE_FOLDER / "candidates" / "2026-08-01T13-22-06"
    dest.mkdir(parents=True)
    (dest / "Hetzner.md").write_text(
        '---\ntitle: "Hetzner"\ntype: entity\n---\n\n# Hetzner\n', encoding="utf-8"
    )
    (wiki / "index.md").write_text(
        seed_index_text()
        + "\n## Archive (1)\n"
        + "- [Hetzner](archive/candidates/2026-08-01T13-22-06/Hetzner.md) — discarded\n",
        encoding="utf-8",
    )

    reindex_wiki(wiki)

    text = _index(wiki)
    assert "## Archive" not in text
    assert "Hetzner" not in text
    assert run_all(load_pages(wiki), selected=["index_sync"]) == []


def test_archived_pages_are_not_graph_nodes(tmp_path: Path) -> None:
    wiki = _seed_vault(tmp_path)
    (wiki / "entities" / "Alpha.md").write_text(
        '---\ntitle: "Alpha"\ntype: entity\n---\n\n# Alpha\n', encoding="utf-8"
    )
    dest = wiki / ARCHIVE_FOLDER / "candidates" / "2026-08-01T13-22-06"
    dest.mkdir(parents=True)
    (dest / "Bogus.md").write_text(
        '---\ntitle: "Bogus"\ntype: entity\n---\n\n# Bogus\n', encoding="utf-8"
    )

    pages = scan_pages(wiki)

    assert "Alpha" in pages
    assert "Bogus" not in pages


# ─── The narrowing to top level, for backlinks and tags ────────────────


def _tagged(path: Path, slug: str, tag: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'---\ntitle: "{slug}"\ntype: source\ntags: [{tag}]\n---\n\n# {slug}\n',
        encoding="utf-8",
    )


def test_backlinks_and_tags_read_only_the_top_level_archive(tmp_path: Path) -> None:
    """`wiki/sources/archive/` is a live page set; `wiki/archive/` is not.

    Source pages are grouped by project slug, so a project called `archive`
    would silently drop out of both indexes under an any-depth match.
    """
    wiki = _seed_vault(tmp_path)
    _tagged(wiki / "sources" / "archive" / "x.md", "x", "live-tag")
    _tagged(wiki / ARCHIVE_FOLDER / "candidates" / "t" / "Bogus.md", "Bogus", "cold-tag")

    slugs = set(backlinks._collect_pages(wiki))
    tagged = {entry.tag for entry in tags.collect_tags(wiki)}

    assert "x" in slugs
    assert "Bogus" not in slugs
    assert "live-tag" in tagged
    assert "cold-tag" not in tagged


# ─── The dismissal ledger: harvest must NOT skip archive/ ──────────────


def test_harvest_still_treats_a_discarded_slug_as_resolved(tmp_path: Path) -> None:
    """Discarding a term must make it stay gone.

    `archive/` is the only record that a candidate was ever judged. If the
    harvest scan skipped it, every dismissed term would be re-proposed on the
    next `synth` — and on every `synth` after, because discarding it again
    would change nothing. This is the one reader that reads cold storage.
    """
    wiki = _seed_vault(tmp_path)
    _write_candidate(wiki, "entities", "Bash")
    for slug in ("a", "b", "c"):
        page = wiki / "sources" / f"{slug}.md"
        page.write_text(
            f"---\ntitle: {slug}\ntype: source\n---\n\n## Connections\n"
            "- [[Bash]] — the tool was mentioned again\n",
            encoding="utf-8",
        )

    discard("Bash", wiki, reason="a tool name, not a concept")

    proposed = {t.name for t in harvest_targets(wiki, min_refs=3)}

    assert "Bash" not in proposed


# ─── The read surfaces ─────────────────────────────────────────────────


def _cold_and_live(wiki: Path) -> None:
    """One live page and one discarded page, both naming `Tailnet`."""
    (wiki / "entities" / "Alpha.md").write_text(
        '---\ntitle: "Alpha"\ntype: entity\n---\n\n# Alpha\n\nAlpha links [[Tailnet]].\n',
        encoding="utf-8",
    )
    cold = wiki / ARCHIVE_FOLDER / "candidates" / "2026-08-01T13-22-06" / "Tailnet.md"
    cold.parent.mkdir(parents=True, exist_ok=True)
    cold.write_text(
        '---\ntitle: "Tailnet"\ntype: entity\n---\n\n# Tailnet\n\nDiscarded as noise.\n',
        encoding="utf-8",
    )


def test_graphify_bridge_skips_archived_pages(tmp_path: Path) -> None:
    """No archived file becomes a node, matching `graph.scan_pages`.

    The bare `Tailnet` node that Alpha's dangling `[[wikilink]]` materialises
    is a different thing and stays: every unresolved link gets one, and links
    to discarded slugs are deliberately left dangling.
    """
    wiki = _seed_vault(tmp_path)
    _cold_and_live(wiki)

    nodes = _extract_wiki_nodes(wiki)["nodes"]

    assert "entities_Alpha" in {node["id"] for node in nodes}
    assert not any(node["file"].startswith(f"{ARCHIVE_FOLDER}/") for node in nodes)


def test_mcp_search_does_not_return_archived_pages(tmp_path: Path) -> None:
    wiki = _seed_vault(tmp_path)
    _cold_and_live(wiki)

    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        text = tool_wiki_search({"term": "Tailnet"})["content"][0]["text"]

    assert "archive/" not in text
    assert "wiki/entities/Alpha.md" in text


def test_mcp_search_still_scans_a_raw_folder_named_archive(tmp_path: Path) -> None:
    """Only `wiki/archive/**` is cold storage — `raw/` is untouched by it."""
    wiki = _seed_vault(tmp_path)
    _cold_and_live(wiki)
    raw = tmp_path / "raw" / "sessions" / "archive" / "2026-08-01T09-00-proj.md"
    raw.parent.mkdir(parents=True, exist_ok=True)
    raw.write_text(
        "---\ntitle: old session\ntype: source\n---\n\nWe set up Tailnet here.\n",
        encoding="utf-8",
    )

    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        text = tool_wiki_search({"term": "Tailnet", "include_raw": True})[
            "content"
        ][0]["text"]

    assert "raw/sessions/archive/2026-08-01T09-00-proj.md" in text
    assert "wiki/archive/" not in text


def test_mcp_query_does_not_quote_archived_pages(tmp_path: Path) -> None:
    wiki = _seed_vault(tmp_path)
    _cold_and_live(wiki)

    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        text = tool_wiki_query({"question": "Tailnet"})["content"][0]["text"]

    assert "Discarded as noise." not in text
    assert "archive/" not in text


def test_mcp_lint_agrees_with_llmwiki_lint_about_discarded_slugs(
    tmp_path: Path,
) -> None:
    """A `[[wikilink]]` to a discarded page is broken in both, or neither.

    Since #150 the MCP tool *is* `run_lint`, so agreement is structural rather
    than two implementations happening to match — the assertion is that the
    tool returns the runner's own payload, plus the discard-specific finding
    that made this test worth writing.
    """
    wiki = _seed_vault(tmp_path)
    _cold_and_live(wiki)

    with patch("llmwiki.mcp.server.REPO_ROOT", tmp_path):
        report = json.loads(tool_wiki_lint({})["content"][0]["text"])

    pages = load_pages(wiki)
    assert report == render_json(run_lint(pages), len(pages))
    assert {
        "rule": "link_integrity",
        "severity": "warning",
        "page": "entities/Alpha.md",
        "message": "broken wikilink [[Tailnet]]",
    } in report["issues"]
