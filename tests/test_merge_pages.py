"""Tests for live curated-page merge via :func:`llmwiki.page_merge.merge_pages`.

Distinct from harvest-stub ``candidates.merge``: both pages are already live
under entities/concepts/projects. Covers same-kind and cross-kind folds,
alias recording, inbound wikilink rewrite, archive layout, and the dismissal
ledger merge row.

# @spec: 418-duplicate-page-review
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from llmwiki.dismissal_ledger import archive_candidates_dir, iter_merges, ledger_path
from llmwiki.page_merge import merge_pages


def _mk_wiki(tmp_path: Path) -> Path:
    """Minimal wiki tree with mergeable kind folders plus sources/."""
    wiki = tmp_path / "wiki"
    for sub in ("entities", "concepts", "projects", "sources"):
        (wiki / sub).mkdir(parents=True, exist_ok=True)
    return wiki


def _write_page(
    wiki: Path,
    folder: str,
    stem: str,
    *,
    page_type: str,
    title: str | None = None,
    sources: list[str] | None = None,
    body: str = "",
) -> Path:
    """Write a live curated page under ``wiki/<folder>/<stem>.md``."""
    title = title if title is not None else stem
    src = sources if sources is not None else []
    src_line = f"sources: [{', '.join(src)}]\n" if src else ""
    path = wiki / folder / f"{stem}.md"
    path.write_text(
        f'---\ntitle: "{title}"\ntype: {page_type}\n{src_line}---\n\n{body}',
        encoding="utf-8",
    )
    return path


def test_merge_pages_same_kind_unions_sources_connections_and_prose(
    tmp_path: Path,
) -> None:
    """Same-folder entity merge keeps the survivor path and folds evidence + prose."""
    wiki = _mk_wiki(tmp_path)
    survivor = _write_page(
        wiki,
        "entities",
        "Alpha",
        page_type="entity",
        sources=["s1"],
        body=(
            "# Alpha\n\n## Key Facts\n\n- Alpha fact.\n\n"
            "## Connections\n\n- [[s1]]\n"
        ),
    )
    _write_page(
        wiki,
        "entities",
        "Beta",
        page_type="entity",
        sources=["s2"],
        body=(
            "# Beta\n\n## Key Facts\n\n- Beta fact.\n\n"
            "## Connections\n\n- [[s2]]\n- [[Other]]\n"
        ),
    )

    result = merge_pages("Beta", wiki, into="Alpha")

    assert result == survivor
    text = survivor.read_text(encoding="utf-8")
    assert "sources: [s1, s2]" in text
    connections = text.split("## Connections", 1)[1].split("## ", 1)[0]
    assert "- [[s2]]" in connections
    assert "- [[Other]]" in connections
    assert connections.count("- [[s1]]") == 1
    assert "## Page merge —" in text
    assert "Merged from `entities/Beta.md`:" in text
    assert "- Beta fact." in text
    assert not (wiki / "entities" / "Beta.md").exists()


def test_merge_pages_cross_kind_keeps_survivor_folder(
    tmp_path: Path,
) -> None:
    """Concept→entity merge leaves the survivor under entities/ and archives the concept."""
    wiki = _mk_wiki(tmp_path)
    survivor = _write_page(
        wiki,
        "entities",
        "Widget",
        page_type="entity",
        sources=["a"],
        body="# Widget\n\n## Connections\n\n- [[a]]\n",
    )
    loser = _write_page(
        wiki,
        "concepts",
        "WidgetPattern",
        page_type="concept",
        title="Widget Pattern",
        sources=["b"],
        body=(
            "# Widget Pattern\n\n## Key Facts\n\n- Pattern fact.\n\n"
            "## Connections\n\n- [[b]]\n"
        ),
    )

    result = merge_pages("Widget Pattern", wiki, into="Widget")

    assert result == survivor
    assert survivor.parent.name == "entities"
    assert 'type: entity' in survivor.read_text(encoding="utf-8")
    assert not loser.exists()
    archived = wiki / "archive" / "concepts" / "WidgetPattern.md"
    assert archived.is_file()
    assert "Pattern fact" in archived.read_text(encoding="utf-8")


def test_merge_pages_records_loser_title_and_prior_aliases(
    tmp_path: Path,
) -> None:
    """Survivor ## Aliases lists the loser's title and any aliases it already carried."""
    wiki = _mk_wiki(tmp_path)
    survivor = _write_page(
        wiki,
        "entities",
        "Canonical",
        page_type="entity",
        sources=["s1"],
        body="# Canonical\n\n## Connections\n\n- [[s1]]\n",
    )
    _write_page(
        wiki,
        "entities",
        "Dup",
        page_type="entity",
        title="Duplicate Name",
        sources=["s2", "s3"],
        body=(
            "# Duplicate Name\n\n## Connections\n\n- [[s2]]\n\n"
            "## Aliases\n\n- OldDup — merged 2026-01-01 (1 source pages)\n"
        ),
    )

    merge_pages("Dup", wiki, into="Canonical")
    text = survivor.read_text(encoding="utf-8")
    aliases = text.split("## Aliases", 1)[1]

    assert "- Duplicate Name — merged " in aliases
    assert "- Dup — merged " in aliases
    assert "- OldDup — merged " in aliases
    assert "(2 source pages)" in aliases


def test_merge_pages_rewrites_inbound_wikilinks(
    tmp_path: Path,
) -> None:
    """Inbound [[loser]] links (and prior aliases) retarget to the survivor stem."""
    wiki = _mk_wiki(tmp_path)
    _write_page(
        wiki,
        "entities",
        "Main",
        page_type="entity",
        body="# Main\n\nbody\n",
    )
    _write_page(
        wiki,
        "entities",
        "Alias",
        page_type="entity",
        body=(
            "# Alias\n\n## Aliases\n\n"
            "- Former — merged 2026-01-01 (0 source pages)\n"
        ),
    )
    linker = wiki / "sources" / "note.md"
    linker.write_text(
        "See [[Alias]] and [[Former|old label]].\n",
        encoding="utf-8",
    )

    merge_pages("Alias", wiki, into="Main")

    rewritten = linker.read_text(encoding="utf-8")
    assert "[[Main|Alias]]" in rewritten
    assert "[[Main|old label]]" in rewritten
    assert "[[Alias]]" not in rewritten
    assert "[[Former" not in rewritten


def test_merge_pages_archives_loser_and_upserts_ledger_merge_row(
    tmp_path: Path,
) -> None:
    """Loser lands under archive/<kind>/ and dismissals.json gets one merge intent."""
    wiki = _mk_wiki(tmp_path)
    _write_page(
        wiki,
        "projects",
        "keep-me",
        page_type="project",
        body="# keep-me\n\nkeeper\n",
    )
    loser = _write_page(
        wiki,
        "projects",
        "fold-me",
        page_type="project",
        title="Fold Me",
        body="# Fold Me\n\nloser body\n",
    )

    merge_pages("fold-me", wiki, into="keep-me")

    assert not loser.exists()
    archived = wiki / "archive" / "projects" / "fold-me.md"
    assert archived.is_file()
    assert ledger_path(wiki).is_file()
    rows = list(iter_merges(wiki))
    assert len(rows) == 1
    row = rows[0]
    assert row["name"] == "Fold Me"
    assert row["into"] == "keep-me"
    assert row["key"] == "foldme"
    expected_stub = Path(
        os.path.relpath(archived, archive_candidates_dir(wiki))
    ).as_posix()
    assert row["stub"] == expected_stub
    assert row["stub"] == "../projects/fold-me.md"
    assert row["merged_at"]


def test_merge_pages_refuses_self_merge(tmp_path: Path) -> None:
    """Merging a page into itself raises ValueError without moving the file."""
    wiki = _mk_wiki(tmp_path)
    page = _write_page(
        wiki, "entities", "Solo", page_type="entity", body="# Solo\n"
    )
    with pytest.raises(ValueError, match="into itself"):
        merge_pages("Solo", wiki, into="Solo")
    assert page.is_file()


def test_merge_pages_refuses_non_mergeable_kind(tmp_path: Path) -> None:
    """A source page is not a mergeable loser even when find_live_page resolves it."""
    wiki = _mk_wiki(tmp_path)
    _write_page(
        wiki, "entities", "Keep", page_type="entity", body="# Keep\n"
    )
    _write_page(
        wiki, "sources", "RawNote", page_type="source", body="# RawNote\n"
    )
    with pytest.raises(ValueError, match="not mergeable"):
        merge_pages("RawNote", wiki, into="Keep")
    assert (wiki / "sources" / "RawNote.md").is_file()
