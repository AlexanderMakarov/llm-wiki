"""Tests for ``llmwiki migrate broken-provenance`` (#180 smoke side-effects).

# @spec: 175-exclude-headless-adapters
"""

from __future__ import annotations

from pathlib import Path

from llmwiki.cli import build_parser
from llmwiki.migrate_broken_provenance import (
    _project_slug_from_missing,
    run_migration,
)


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _source_page(wiki: Path, name: str, source_file: str, *, sources: str | None = None) -> Path:
    sources_line = f"sources: {sources}\n" if sources else ""
    return _write(
        wiki / "sources" / "cursor-aabbccddeeff" / f"{name}.md",
        (
            "---\n"
            f'title: "{name}"\n'
            "type: source\n"
            f"source_file: {source_file}\n"
            f"{sources_line}"
            "---\n\n"
            "## Summary\nhello\n"
        ),
    )


def _raw(vault: Path, name: str, *, is_headless: bool | None = False) -> Path:
    headless_line = (
        ""
        if is_headless is None
        else f"is_headless: {str(is_headless).lower()}\n"
    )
    return _write(
        vault / "raw" / "sessions" / name,
        (
            "---\n"
            f'title: "{name}"\n'
            "type: source\n"
            f"{headless_line}"
            "project: cursor-aabbccddeeff\n"
            "---\n\nbody\n"
        ),
    )


def test_project_slug_from_cursor_missing_path() -> None:
    assert (
        _project_slug_from_missing(
            "raw/sessions/2026-08-07T20-27-cursor-aabbccddeeff-store.md"
        )
        == "cursor-aabbccddeeff"
    )


def test_remap_unique_same_date(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    missing = "raw/sessions/2026-08-07T20-27-cursor-aabbccddeeff-store.md"
    page = _source_page(wiki, "2026-08-07-store", missing)
    target = _raw(
        tmp_path,
        "2026-08-07T21-00-cursor-aabbccddeeff-e2285ab8.md",
        is_headless=False,
    )

    report = run_migration(vault=tmp_path)
    assert report["remapped"] == 1
    assert report["cleared"] == 0
    assert report["unresolved"] == 0
    text = page.read_text(encoding="utf-8")
    assert f"source_file: {target.relative_to(tmp_path).as_posix()}" in text
    assert missing not in text


def test_remap_prefers_unique_non_headless_when_multiple(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    missing = "raw/sessions/2026-08-07T20-27-cursor-aabbccddeeff-store.md"
    page = _source_page(wiki, "2026-08-07-store", missing)
    _raw(
        tmp_path,
        "2026-08-07T21-00-cursor-aabbccddeeff-aaaa.md",
        is_headless=True,
    )
    keeper = _raw(
        tmp_path,
        "2026-08-07T22-00-cursor-aabbccddeeff-bbbb.md",
        is_headless=False,
    )

    report = run_migration(vault=tmp_path)
    assert report["remapped"] == 1
    assert report["unresolved"] == 0
    assert keeper.relative_to(tmp_path).as_posix() in page.read_text(encoding="utf-8")


def test_unresolved_when_multiple_non_headless(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    # Same HH-MM distance to both keepers → ambiguous → clear-ambiguous.
    missing = "raw/sessions/2026-08-07T21-30-cursor-aabbccddeeff-store.md"
    page = _source_page(wiki, "2026-08-07-store", missing)
    _raw(tmp_path, "2026-08-07T21-00-cursor-aabbccddeeff-aaaa.md", is_headless=False)
    _raw(tmp_path, "2026-08-07T22-00-cursor-aabbccddeeff-bbbb.md", is_headless=False)

    report = run_migration(vault=tmp_path)
    assert report["unresolved"] == 1
    assert report["remapped"] == 0
    assert report["cleared"] == 1
    text = page.read_text(encoding="utf-8")
    assert "source_file:" not in text


def test_no_cross_day_remap(tmp_path: Path) -> None:
    """Same project on another day must not steal a missing same-day hop."""
    wiki = tmp_path / "wiki"
    missing = "raw/sessions/2026-06-20T14-56-cursor-aabbccddeeff-store.md"
    page = _source_page(wiki, "2026-06-20-store", missing)
    _raw(tmp_path, "2026-01-20T12-11-cursor-aabbccddeeff-60867dee.md", is_headless=False)

    report = run_migration(vault=tmp_path)
    assert report["remapped"] == 0
    assert report["cleared"] == 1
    assert "source_file:" not in page.read_text(encoding="utf-8")


def test_clear_when_same_day_only_headless(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    missing = "raw/sessions/2026-08-07T20-27-cursor-aabbccddeeff-store.md"
    page = _source_page(wiki, "2026-08-07-store", missing)
    _raw(tmp_path, "2026-08-07T21-00-cursor-aabbccddeeff-aaaa.md", is_headless=True)

    report = run_migration(vault=tmp_path)
    assert report["remapped"] == 0
    assert report["cleared"] == 1
    assert "source_file:" not in page.read_text(encoding="utf-8")


def test_remap_unmarked_legacy_as_interactive(tmp_path: Path) -> None:
    """Missing ``is_headless`` stays remap-eligible (synth parity)."""
    wiki = tmp_path / "wiki"
    missing = "raw/sessions/2026-08-07T20-27-cursor-aabbccddeeff-store.md"
    page = _source_page(wiki, "2026-08-07-store", missing)
    keeper = _raw(
        tmp_path,
        "2026-08-07T21-00-cursor-aabbccddeeff-legacy.md",
        is_headless=None,
    )

    report = run_migration(vault=tmp_path)
    assert report["remapped"] == 1
    assert keeper.relative_to(tmp_path).as_posix() in page.read_text(encoding="utf-8")


def test_closest_clock_among_same_day(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    missing = "raw/sessions/2026-08-07T20-27-cursor-aabbccddeeff-store.md"
    page = _source_page(wiki, "2026-08-07-store", missing)
    _raw(tmp_path, "2026-08-07T10-00-cursor-aabbccddeeff-aaaa.md", is_headless=False)
    keeper = _raw(
        tmp_path,
        "2026-08-07T20-30-cursor-aabbccddeeff-bbbb.md",
        is_headless=False,
    )

    report = run_migration(vault=tmp_path)
    assert report["remapped"] == 1
    assert keeper.relative_to(tmp_path).as_posix() in page.read_text(encoding="utf-8")


def test_clear_when_zero_candidates_and_trim_sources(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    missing = "raw/sessions/2026-08-07T20-27-cursor-aabbccddeeff-store.md"
    page = _source_page(wiki, "2026-08-07-store", missing)
    entity = _write(
        wiki / "entities" / "Widget.md",
        (
            "---\n"
            'title: "Widget"\n'
            "type: entity\n"
            "sources: [2026-08-07T20-27-cursor-aabbccddeeff-store, other-slug]\n"
            "---\n\n"
            "# Widget\n"
        ),
    )
    # Unrelated project raw should not match.
    _raw(tmp_path, "2026-08-07T21-00-cursor-ffffffffffff-zzzz.md", is_headless=False)

    report = run_migration(vault=tmp_path)
    assert report["cleared"] == 1
    assert report["remapped"] == 0
    text = page.read_text(encoding="utf-8")
    assert "source_file:" not in text
    et = entity.read_text(encoding="utf-8")
    assert "other-slug" in et
    assert "2026-08-07T20-27-cursor-aabbccddeeff-store" not in et
    assert report["sources_entries_dropped"] >= 1


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    missing = "raw/sessions/2026-08-07T20-27-cursor-aabbccddeeff-store.md"
    page = _source_page(wiki, "2026-08-07-store", missing)
    _raw(tmp_path, "2026-08-07T21-00-cursor-aabbccddeeff-e2285ab8.md")
    before = page.read_text(encoding="utf-8")

    report = run_migration(vault=tmp_path, dry_run=True)
    assert report["remapped"] == 1
    assert page.read_text(encoding="utf-8") == before


def test_cli_parse_and_run(tmp_path: Path, capsys) -> None:
    wiki = tmp_path / "wiki"
    missing = "raw/sessions/2026-08-07T20-27-cursor-aabbccddeeff-store.md"
    _source_page(wiki, "2026-08-07-store", missing)
    _raw(tmp_path, "2026-08-07T21-00-cursor-aabbccddeeff-e2285ab8.md")
    args = build_parser().parse_args(
        ["migrate", "broken-provenance", "--vault", str(tmp_path)]
    )
    assert args.func(args) == 0
    out = capsys.readouterr().out
    assert "remapped:" in out
