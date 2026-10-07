"""Tests for ``llmwiki migrate doc-source-provenance``.

Heals document source pages an older release synthesised with a blank
``source_file`` and a ``session-transcript`` tag
(https://github.com/AlexanderMakarov/llm-wiki/issues/307).

# @spec: 307-doc-source-provenance
"""

from __future__ import annotations

from pathlib import Path

from llmwiki._frontmatter import parse_frontmatter
from llmwiki.cli import _MIGRATIONS, build_parser
from llmwiki.migrate_doc_source_provenance import run_migration


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _raw_doc(vault: Path, rel: str, *, slug: str, project: str = "field-notes") -> Path:
    """A raw doc shaped like ``llmwiki add`` writes it (``source:``, no ``source_file:``)."""
    return _write(
        vault / "raw" / "docs" / rel,
        (
            "---\n"
            f'title: "{slug}"\n'
            f"slug: {slug}\n"
            f"project: {project}\n"
            "type: source\n"
            "tags: [wiki-add, raw-doc]\n"
            "date: 2026-05-01\n"
            'source: "/tmp/original.pdf"\n'
            "---\n\nbody\n"
        ),
    )


def _page(vault: Path, rel: str, *, tags: str, source_file: str = "") -> Path:
    return _write(
        vault / "wiki" / "sources" / rel,
        (
            "---\n"
            'title: "page"\n'
            "type: source\n"
            f"{tags}"
            "date: 2026-05-01\n"
            f"source_file: {source_file}\n"
            "---\n\n## Summary\nhello\n"
        ),
    )


def _meta(path: Path) -> dict:
    return parse_frontmatter(path.read_text(encoding="utf-8"))[0]


def test_fills_blank_claim_and_strips_session_tag(tmp_path: Path) -> None:
    _raw_doc(tmp_path, "field-notes/widget-guide.md", slug="widget-guide")
    page = _page(
        tmp_path,
        "field-notes/2026-05-01-widget-guide.md",
        tags="tags: [wiki-add, raw-doc, session-transcript, field-notes]\n",
    )

    report = run_migration(vault=tmp_path)

    meta = _meta(page)
    assert meta["source_file"] == "raw/docs/field-notes/widget-guide.md"
    assert meta["tags"] == ["wiki-add", "raw-doc", "field-notes"]
    assert report["filled"] == 1
    assert report["tags_stripped"] == 1
    assert report["pages_touched"] == 1
    assert "migrate | doc source provenance" in (tmp_path / "wiki" / "log.md").read_text(encoding="utf-8")


def test_block_tags_on_a_stub_get_raw_doc_when_no_doc_tag_is_left(tmp_path: Path) -> None:
    """A stub synthesised before #307 from a frontmatter-less doc carries only the session stamp."""
    _write(tmp_path / "raw" / "docs" / "bare.md", "# Bare\n\nno frontmatter\n")
    page = _page(
        tmp_path,
        "docs/bare.md",
        tags="tags:\n  - session-transcript\n  - docs\n",
    )
    page.write_text(
        page.read_text(encoding="utf-8") + "\n<!-- llmwiki-pending: stub -->\n",
        encoding="utf-8",
    )

    report = run_migration(vault=tmp_path)

    text = page.read_text(encoding="utf-8")
    assert "source_file: raw/docs/bare.md" in text
    assert "tags:\n  - docs\n  - raw-doc\n" in text
    assert "session-transcript" not in text
    assert report["raw_doc_added"] == 1


def test_already_claimed_doc_page_still_loses_session_tag(tmp_path: Path) -> None:
    page = _page(
        tmp_path,
        "manual/notes.md",
        tags="tags: [raw-doc, session-transcript]\n",
        source_file="raw/docs/manual/notes.md",
    )

    report = run_migration(vault=tmp_path)

    meta = _meta(page)
    assert meta["source_file"] == "raw/docs/manual/notes.md"
    assert meta["tags"] == ["raw-doc"]
    assert report["filled"] == 0
    assert report["tags_stripped"] == 1


def test_session_pages_are_never_touched(tmp_path: Path) -> None:
    session = _page(
        tmp_path,
        "proj/2026-05-01-sess.md",
        tags="tags: [raw-doc, session-transcript]\n",
        source_file="raw/sessions/proj/2026-05-01-sess.md",
    )
    unclaimed_session = _page(
        tmp_path,
        "proj/2026-05-02-other.md",
        tags="tags: [claude-code, session-transcript]\n",
    )
    before = {p: p.read_text(encoding="utf-8") for p in (session, unclaimed_session)}

    report = run_migration(vault=tmp_path)

    assert {p: p.read_text(encoding="utf-8") for p in before} == before
    assert report["changed"] is False
    assert report["unmatched"] == []


def test_page_two_raw_docs_derive_to_is_reported_and_left_alone(tmp_path: Path) -> None:
    _write(tmp_path / "raw" / "docs" / "a" / "notes.md", "# A\n")
    _write(tmp_path / "raw" / "docs" / "b" / "notes.md", "# B\n")
    page = _page(tmp_path, "docs/notes.md", tags="tags: [session-transcript]\n")
    before = page.read_text(encoding="utf-8")

    report = run_migration(vault=tmp_path)

    assert page.read_text(encoding="utf-8") == before
    assert report["ambiguous"] == [
        {"wiki_path": "wiki/sources/docs/notes.md", "candidates": ["raw/docs/a/notes.md", "raw/docs/b/notes.md"]}
    ]
    assert report["changed"] is False


def test_unmatched_doc_tagged_page_keeps_blank_claim_but_loses_session_tag(tmp_path: Path) -> None:
    page = _page(tmp_path, "docs/orphan.md", tags="tags: [wiki-add, session-transcript]\n")

    report = run_migration(vault=tmp_path)

    meta = _meta(page)
    assert meta["source_file"] == ""
    assert meta["tags"] == ["wiki-add"]
    assert report["unmatched"] == ["wiki/sources/docs/orphan.md"]


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    raw = _raw_doc(tmp_path, "field-notes/widget-guide.md", slug="widget-guide")
    raw_before = raw.read_text(encoding="utf-8")
    page = _page(
        tmp_path,
        "field-notes/2026-05-01-widget-guide.md",
        tags="tags: [raw-doc, session-transcript]\n",
    )
    (tmp_path / "wiki" / "log.md").write_text("# Log\n", encoding="utf-8")
    before = page.read_text(encoding="utf-8")

    report = run_migration(vault=tmp_path, dry_run=True)

    assert report["filled"] == 1 and report["tags_stripped"] == 1
    assert page.read_text(encoding="utf-8") == before
    assert (tmp_path / "wiki" / "log.md").read_text(encoding="utf-8") == "# Log\n"
    assert raw.read_text(encoding="utf-8") == raw_before


def test_second_run_changes_nothing(tmp_path: Path) -> None:
    raw = _raw_doc(tmp_path, "field-notes/widget-guide.md", slug="widget-guide")
    raw_before = raw.read_text(encoding="utf-8")
    page = _page(
        tmp_path,
        "field-notes/2026-05-01-widget-guide.md",
        tags="tags: [session-transcript]\n",
    )

    first = run_migration(vault=tmp_path)
    healed = page.read_text(encoding="utf-8")
    second = run_migration(vault=tmp_path)

    assert first["changed"] is True
    assert second["changed"] is False
    assert page.read_text(encoding="utf-8") == healed
    assert raw.read_text(encoding="utf-8") == raw_before


def test_catalog_and_cli_list_the_migration(tmp_path: Path, capsys) -> None:
    assert "doc-source-provenance" in {name for name, _purpose, _when in _MIGRATIONS}
    _raw_doc(tmp_path, "field-notes/widget-guide.md", slug="widget-guide")
    _page(tmp_path, "field-notes/2026-05-01-widget-guide.md", tags="tags: [raw-doc]\n")

    args = build_parser().parse_args(
        ["migrate", "doc-source-provenance", "--vault", str(tmp_path), "--dry-run"]
    )
    assert args.func(args) == 0
    assert "claims filled:  1" in capsys.readouterr().out
