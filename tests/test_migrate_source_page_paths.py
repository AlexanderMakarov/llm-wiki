"""``llmwiki migrate source-page-paths`` — re-file stale source pages (#265).

A real source page tied to its raw file by ``source_file:`` but filed under a
name the writer no longer derives is skipped by synth's dedup guard forever
and counted as pending by ``--estimate`` / Home. The migration moves such a
page to its derived path, rewrites the links that point at it, and records
synth state for the source — offline, with no backend call.

Every fixture here is invented; every run points ``log_path`` / state at the
tmp vault so nothing leaks into the repository's own ``wiki/``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from llmwiki.cli import build_parser
from llmwiki.migrate_source_page_paths import print_report, run_migration
from llmwiki.synth import base as synth_base
from llmwiki.synth.base import DummySynthesizer
from llmwiki.synth.pipeline import (
    _load_state,
    discover_unsynth_session_rels,
    synthesize_new_sessions,
)

PROJECT = "demo-proj"
DATE = "2026-07-01"
SLUG = "a1b2c3d4"
RAW_STEM = f"{DATE}T10-00-{PROJECT}-{SLUG}"
RAW_REL = f"{RAW_STEM}.md"
SOURCE_FILE = f"raw/sessions/{RAW_REL}"
OLD_STEM = f"{DATE}-generic-task"
NEW_STEM = f"{DATE}-{SLUG}"
OLD_TITLE = f"Session: generic-task — {DATE}"
RAW_TITLE = f"Session: {SLUG} — {DATE}"

RAW_SESSION = """---
title: "{title}"
type: source
date: {date}
source_file: raw/sessions/{stem}.md
slug: {slug}
project: {project}
---

# Session

Synthetic transcript body.
"""

REAL_PAGE = """---
title: "{title}"
type: source
tags: [claude-code, session-transcript]
date: {date}
source_file: {source_file}
project: {project}
---

## Summary

A real synthesized summary.

## Connections

- [[Pytest]] (entity) — the test runner
"""

STUB_PAGE = """---
title: "Pending"
type: source
source_file: {source_file}
project: {project}
---

<!-- llmwiki-pending: 1 -->
"""


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _raw_session(
    vault: Path, *, slug: str = SLUG, project: str = PROJECT, date: str = DATE,
    time: str = "10-00",
) -> Path:
    stem = f"{date}T{time}-{project}-{slug}"
    return _write(
        vault / "raw" / "sessions" / f"{stem}.md",
        RAW_SESSION.format(
            title=f"Session: {slug} — {date}", date=date, stem=stem,
            slug=slug, project=project,
        ),
    )


def _real_page(
    vault: Path, rel: str, *, source_file: str = SOURCE_FILE,
    title: str = OLD_TITLE, project: str = PROJECT, date: str = DATE,
) -> Path:
    return _write(
        vault / "wiki" / "sources" / rel,
        REAL_PAGE.format(
            title=title, date=date, source_file=source_file, project=project
        ),
    )


def _vault(tmp_path: Path) -> Path:
    """One raw session whose real page sits under a stale slug, plus referrers."""
    vault = tmp_path / "vault"
    _raw_session(vault)
    _real_page(vault, f"{PROJECT}/{OLD_STEM}.md")
    _write(
        vault / "wiki" / "projects" / f"{PROJECT}.md",
        f"""---
title: "{PROJECT}"
type: project
tags: []
sources: [{OLD_STEM}, 2026-06-30-other]
last_updated: {DATE}
---

# {PROJECT}

## Sessions
- [[{OLD_STEM}]] ({DATE}) — bare
- [[{OLD_STEM}|{OLD_TITLE}]] — titled
- [[{OLD_STEM}|custom label]] — custom
- [[{OLD_STEM}#Summary]] — anchored
- [[sources/{PROJECT}/{OLD_STEM}]] — path-qualified
- [[{PROJECT}/{OLD_STEM}|custom label]] — short path

## Connections
- [[Pytest]]
""",
    )
    _write(
        vault / "wiki" / "entities" / "Pytest.md",
        f"""---
title: "Pytest"
type: entity
tags: []
sources: [{OLD_STEM}]
last_updated: {DATE}
---

# Pytest

## Connections
- [[{OLD_STEM}]]
""",
    )
    _write(
        vault / "wiki" / "archive" / "candidates" / "Old.md",
        f"---\ntitle: Old\n---\n\n- [[{OLD_STEM}]]\n",
    )
    _write(vault / "wiki" / "index.md", "# Wiki Index\n\n## Sources (0)\n")
    _write(vault / "wiki" / "log.md", "# Wiki Log\n")
    return vault


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        str(p.relative_to(root)): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def _synth(vault: Path) -> dict:
    return synthesize_new_sessions(
        backend=DummySynthesizer(),
        raw_dir=vault / "raw" / "sessions",
        docs_dir=vault / "raw" / "docs",
        wiki_sources_dir=vault / "wiki" / "sources",
        log_path=vault / "wiki" / "log.md",
        state_file=vault / "llmwiki-state.json",
        include_subagents="all",
        exclude_headless=False,
    )


def _pending(vault: Path) -> set[str]:
    return discover_unsynth_session_rels(
        raw_dir=vault / "raw" / "sessions",
        wiki_sources_dir=vault / "wiki" / "sources",
        state_file=vault / "llmwiki-state.json",
        include_subagents="all",
        exclude_headless=False,
    )


@pytest.fixture(autouse=True)
def _no_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    """The migration never reaches a synthesis backend."""

    def _boom(*_a, **_k):
        raise AssertionError("migration must not call a synthesis backend")

    monkeypatch.setattr(synth_base.BaseSynthesizer, "synthesize_source_page", _boom)
    monkeypatch.setattr(DummySynthesizer, "synthesize_source_page", _boom)


# ─── acceptance ─────────────────────────────────────────────────────────


def test_before_the_migration_synth_skips_and_estimate_counts_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    vault = _vault(tmp_path)

    assert _pending(vault) == {RAW_REL}
    summary = _synth(vault)

    assert summary["skipped"] == 1
    assert "already claimed by a real page" in capsys.readouterr().out


def test_migrated_source_is_done_for_synth_and_estimate(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    vault = _vault(tmp_path)

    report = run_migration(vault=vault)

    assert report["errors"] == []
    sources = vault / "wiki" / "sources" / PROJECT
    assert not (sources / f"{OLD_STEM}.md").exists()
    assert (sources / f"{NEW_STEM}.md").is_file()
    assert _pending(vault) == set()
    capsys.readouterr()
    summary = _synth(vault)
    out = capsys.readouterr().out
    assert summary["synthesized"] == 0
    assert summary["skipped"] == 0
    assert "already claimed" not in out


def test_move_keeps_body_and_frontmatter_and_updates_converter_title(
    tmp_path: Path,
) -> None:
    vault = _vault(tmp_path)
    old = (vault / "wiki" / "sources" / PROJECT / f"{OLD_STEM}.md").read_text(
        encoding="utf-8"
    )

    run_migration(vault=vault)

    new = (vault / "wiki" / "sources" / PROJECT / f"{NEW_STEM}.md").read_text(
        encoding="utf-8"
    )
    assert new == old.replace(f'title: "{OLD_TITLE}"', f'title: "{RAW_TITLE}"')


def test_hand_written_title_is_kept(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    page = vault / "wiki" / "sources" / PROJECT / f"{OLD_STEM}.md"
    page.write_text(
        page.read_text(encoding="utf-8").replace(OLD_TITLE, "My notes"),
        encoding="utf-8",
    )
    old = page.read_text(encoding="utf-8")

    run_migration(vault=vault)

    new = vault / "wiki" / "sources" / PROJECT / f"{NEW_STEM}.md"
    assert new.read_text(encoding="utf-8") == old


def test_links_and_sources_lists_are_rewritten(tmp_path: Path) -> None:
    vault = _vault(tmp_path)

    report = run_migration(vault=vault)

    project = (vault / "wiki" / "projects" / f"{PROJECT}.md").read_text(
        encoding="utf-8"
    )
    assert f"sources: [{NEW_STEM}, 2026-06-30-other]" in project
    assert f"- [[{NEW_STEM}]] ({DATE}) — bare" in project
    assert f"- [[{NEW_STEM}|{RAW_TITLE}]] — titled" in project
    assert f"- [[{NEW_STEM}|custom label]] — custom" in project
    assert f"- [[{NEW_STEM}#Summary]] — anchored" in project
    assert f"- [[sources/{PROJECT}/{NEW_STEM}]] — path-qualified" in project
    assert f"- [[{PROJECT}/{NEW_STEM}|custom label]] — short path" in project
    assert OLD_STEM not in project
    entity = (vault / "wiki" / "entities" / "Pytest.md").read_text(encoding="utf-8")
    assert f"sources: [{NEW_STEM}]" in entity
    assert f"- [[{NEW_STEM}]]" in entity
    assert report["links_rewritten"] == 7
    assert report["sources_rewritten"] == 2


def test_archive_is_left_alone(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    archived = vault / "wiki" / "archive" / "candidates" / "Old.md"
    before = archived.read_text(encoding="utf-8")

    run_migration(vault=vault)

    assert archived.read_text(encoding="utf-8") == before


def test_state_is_recorded_under_the_synth_key(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    raw = vault / "raw" / "sessions" / RAW_REL

    report = run_migration(vault=vault)

    state = _load_state(vault / "llmwiki-state.json")
    assert state[RAW_REL] == pytest.approx(raw.stat().st_mtime, abs=1e-3)
    assert report["state_upserts"] == [RAW_REL]


def test_newer_state_value_is_not_regressed(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    raw = vault / "raw" / "sessions" / RAW_REL
    future = raw.stat().st_mtime + 1000
    _write(
        vault / "llmwiki-state.json",
        json.dumps({"synth": {"files": {RAW_REL: future}}}),
    )

    report = run_migration(vault=vault)

    assert report["state_upserts"] == []
    assert _load_state(vault / "llmwiki-state.json")[RAW_REL] == pytest.approx(
        future, abs=1e-3
    )


def test_older_state_value_is_kept_so_the_page_stays_stale(tmp_path: Path) -> None:
    """The raw was re-converted after synthesis: synth must still see that."""
    vault = _vault(tmp_path)
    raw = vault / "raw" / "sessions" / RAW_REL
    past = raw.stat().st_mtime - 1000
    _write(
        vault / "llmwiki-state.json",
        json.dumps({"synth": {"files": {RAW_REL: past}}}),
    )

    report = run_migration(vault=vault)

    assert len(report["moves"]) == 1
    assert report["state_upserts"] == []
    assert _load_state(vault / "llmwiki-state.json")[RAW_REL] == pytest.approx(
        past, abs=1e-3
    )
    assert _pending(vault) == {RAW_REL}


def test_page_already_at_target_without_state_is_healed(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _raw_session(vault)
    page = _real_page(vault, f"{PROJECT}/{NEW_STEM}.md", title=RAW_TITLE)
    before = page.read_text(encoding="utf-8")
    _write(vault / "wiki" / "log.md", "# Wiki Log\n")

    report = run_migration(vault=vault)

    assert report["moves"] == []
    assert report["state_upserts"] == [RAW_REL]
    assert page.read_text(encoding="utf-8") == before
    assert _pending(vault) == set()


def test_index_is_rebuilt_and_log_appended(tmp_path: Path) -> None:
    vault = _vault(tmp_path)

    run_migration(vault=vault)

    index = (vault / "wiki" / "index.md").read_text(encoding="utf-8")
    assert f"sources/{PROJECT}/{NEW_STEM}.md" in index
    assert OLD_STEM not in index
    log = (vault / "wiki" / "log.md").read_text(encoding="utf-8")
    entries = [ln for ln in log.splitlines() if ln.startswith("## [")]
    assert len(entries) == 1
    assert entries[0].endswith("] migrate | source page paths")


# ─── safety ─────────────────────────────────────────────────────────────


def test_dry_run_writes_nothing(tmp_path: Path, capsys) -> None:
    vault = _vault(tmp_path)
    before = _snapshot(vault)

    report = run_migration(vault=vault, dry_run=True)
    print_report(report)

    assert _snapshot(vault) == before
    assert len(report["moves"]) == 1
    assert report["links_rewritten"] == 7
    assert report["state_upserts"] == [RAW_REL]
    out = capsys.readouterr().out
    assert f"{PROJECT}/{OLD_STEM}.md" in out
    assert f"{PROJECT}/{NEW_STEM}.md" in out


def test_second_run_is_a_no_op(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    run_migration(vault=vault)
    before = _snapshot(vault)

    report = run_migration(vault=vault)

    assert report["changed"] is False
    assert _snapshot(vault) == before


def test_collision_is_reported_and_both_pages_kept(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    stale = vault / "wiki" / "sources" / PROJECT / f"{OLD_STEM}.md"
    target = _real_page(vault, f"{PROJECT}/{NEW_STEM}.md", title="Already here")
    stale_before = stale.read_text(encoding="utf-8")
    target_before = target.read_text(encoding="utf-8")

    report = run_migration(vault=vault)

    assert report["moves"] == []
    assert [c["from"] for c in report["collisions"]] == [
        f"sources/{PROJECT}/{OLD_STEM}.md"
    ]
    assert stale.read_text(encoding="utf-8") == stale_before
    assert target.read_text(encoding="utf-8") == target_before
    assert report["state_upserts"] == []
    assert RAW_REL not in _load_state(vault / "llmwiki-state.json")


def test_stub_at_target_for_the_same_source_is_replaced(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    stub = _write(
        vault / "wiki" / "sources" / PROJECT / f"{NEW_STEM}.md",
        STUB_PAGE.format(source_file=SOURCE_FILE, project=PROJECT),
    )

    report = run_migration(vault=vault)

    assert report["collisions"] == []
    assert len(report["moves"]) == 1
    assert "A real synthesized summary." in stub.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "stub_extra",
    [
        f"\nSee [[{OLD_STEM}]] for the old notes.\n",
        None,
    ],
    ids=["body-link", "sources-entry"],
)
def test_stub_at_target_that_links_the_old_stem_does_not_win(
    tmp_path: Path, stub_extra: str | None
) -> None:
    vault = _vault(tmp_path)
    stub_text = STUB_PAGE.format(source_file=SOURCE_FILE, project=PROJECT)
    if stub_extra is None:
        stub_text = stub_text.replace(
            f"project: {PROJECT}\n", f"project: {PROJECT}\nsources: [{OLD_STEM}]\n"
        )
    else:
        stub_text += stub_extra
    target = _write(vault / "wiki" / "sources" / PROJECT / f"{NEW_STEM}.md", stub_text)

    report = run_migration(vault=vault)

    assert report["errors"] == []
    text = target.read_text(encoding="utf-8")
    assert "A real synthesized summary." in text
    assert "llmwiki-pending" not in text


def test_failed_move_is_undone_and_its_rewrites_dropped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault = _vault(tmp_path)
    stale = vault / "wiki" / "sources" / PROJECT / f"{OLD_STEM}.md"
    before = _snapshot(vault)
    real_unlink = Path.unlink

    def _unlink(self: Path, *args, **kwargs):
        if self == stale:
            raise PermissionError("read-only")
        return real_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", _unlink)

    report = run_migration(vault=vault)

    assert report["moves"] == []
    assert report["links_rewritten"] == 0
    assert report["state_upserts"] == []
    assert any("move undone" in e for e in report["errors"])
    assert not (vault / "wiki" / "sources" / PROJECT / f"{NEW_STEM}.md").exists()
    assert _snapshot(vault) == before


def test_failed_write_leaves_the_vault_as_it_was(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault = _vault(tmp_path)
    dest = vault / "wiki" / "sources" / PROJECT / f"{NEW_STEM}.md"
    before = _snapshot(vault)
    real_write = Path.write_text

    def _write_text(self: Path, *args, **kwargs):
        if self == dest:
            raise OSError("disk full")
        return real_write(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", _write_text)

    report = run_migration(vault=vault)

    assert report["moves"] == []
    assert any("not moved" in e for e in report["errors"])
    assert _snapshot(vault) == before


def test_ambiguous_bare_stem_is_reported_not_rewritten(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    # An unrelated page elsewhere shares the stale stem.
    _write(
        vault / "wiki" / "sources" / "other-proj" / f"{OLD_STEM}.md",
        "---\ntitle: Other\ntype: source\n---\n\n## Summary\nOther.\n",
    )

    report = run_migration(vault=vault)

    project = (vault / "wiki" / "projects" / f"{PROJECT}.md").read_text(
        encoding="utf-8"
    )
    assert f"- [[{OLD_STEM}]] ({DATE}) — bare" in project
    assert f"sources: [{OLD_STEM}, 2026-06-30-other]" in project
    # Path-qualified links still resolve to exactly one page.
    assert f"- [[sources/{PROJECT}/{NEW_STEM}]] — path-qualified" in project
    assert f"- [[{PROJECT}/{NEW_STEM}|custom label]] — short path" in project
    assert [(a["stem"], a["dangling"]) for a in report["ambiguous"]] == [
        (OLD_STEM, False)
    ]
    assert (vault / "wiki" / "sources" / PROJECT / f"{NEW_STEM}.md").is_file()


def _share_stale_stem(vault: Path, *, links_back: bool) -> Path:
    """Add an unrelated source page carrying the stale stem in another project."""
    body = "## Summary\nOther.\n"
    if links_back:
        body += "\n## Connections\n- [[Pytest]] (entity) — also uses it\n"
    return _write(
        vault / "wiki" / "sources" / "other-proj" / f"{OLD_STEM}.md",
        f"---\ntitle: Other\ntype: source\n---\n\n{body}",
    )


def test_unique_backlinker_disambiguates_a_shared_stem(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _share_stale_stem(vault, links_back=False)

    report = run_migration(vault=vault)

    # Only the moving page links back to Pytest, so Pytest's links follow it.
    entity = (vault / "wiki" / "entities" / "Pytest.md").read_text(encoding="utf-8")
    assert f"sources: [{NEW_STEM}]" in entity
    assert f"- [[{NEW_STEM}]]" in entity
    assert report["disambiguated"] == 2
    # Nothing on the project page links back from either candidate.
    assert report["still_ambiguous"] == 5
    assert report["would_break"] == 0


def test_two_backlinkers_leave_the_stem_ambiguous(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _share_stale_stem(vault, links_back=True)
    entity_path = vault / "wiki" / "entities" / "Pytest.md"
    before = entity_path.read_text(encoding="utf-8")

    report = run_migration(vault=vault)

    assert entity_path.read_text(encoding="utf-8") == before
    assert report["disambiguated"] == 0
    assert "entities/Pytest.md" in report["ambiguous"][0]["referrers"]


def test_backlinker_that_stays_put_keeps_the_link(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _share_stale_stem(vault, links_back=True)
    stale = vault / "wiki" / "sources" / PROJECT / f"{OLD_STEM}.md"
    stale.write_text(
        stale.read_text(encoding="utf-8").replace("[[Pytest]]", "[[Runner]]"),
        encoding="utf-8",
    )
    entity_path = vault / "wiki" / "entities" / "Pytest.md"
    before = entity_path.read_text(encoding="utf-8")

    report = run_migration(vault=vault)

    assert entity_path.read_text(encoding="utf-8") == before
    assert report["disambiguated"] == 0
    assert report["disambiguated_kept"] == 2
    assert all("entities/Pytest.md" not in a["referrers"] for a in report["ambiguous"])


def test_backlinker_with_an_ambiguous_new_stem_stays_ambiguous(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _share_stale_stem(vault, links_back=False)
    _write(
        vault / "wiki" / "sources" / "third-proj" / f"{NEW_STEM}.md",
        "---\ntitle: Third\ntype: source\n---\n\n## Summary\nThird.\n",
    )
    entity_path = vault / "wiki" / "entities" / "Pytest.md"
    before = entity_path.read_text(encoding="utf-8")

    report = run_migration(vault=vault)

    assert entity_path.read_text(encoding="utf-8") == before
    assert report["disambiguated"] == 0


def test_no_state_file_when_nothing_to_do(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _write(vault / "wiki" / "log.md", "# Wiki Log\n")
    before = _snapshot(vault)

    report = run_migration(vault=vault)

    assert report["changed"] is False
    assert _snapshot(vault) == before


def test_a_vault_without_a_wiki_is_an_error(tmp_path: Path) -> None:
    report = run_migration(vault=tmp_path)

    assert report["errors"] and "missing wiki dir" in report["errors"][0]
    assert report["changed"] is False


# ─── number-shaped slugs and doc part groups ────────────────────────────


def test_doubled_date_page_of_a_numeric_slug_moves(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    raw = _raw_session(vault, slug="0123")
    source_file = f"raw/sessions/{raw.name}"
    doubled = f"{DATE}-{raw.stem}"
    _real_page(vault, f"{PROJECT}/{doubled}.md", source_file=source_file)
    _write(vault / "wiki" / "log.md", "# Wiki Log\n")

    report = run_migration(vault=vault)

    assert [m["to"] for m in report["moves"]] == [f"sources/{PROJECT}/{DATE}-0123.md"]


DOC_RAW = """---
title: "Field guide"
slug: field-guide
date: 2026-07-02
---

# Field guide
"""


def test_doc_part_pages_move_as_a_group(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _write(vault / "raw" / "docs" / "field-guide.md", DOC_RAW)
    for n in (1, 2):
        _real_page(
            vault, f"docs/old-guide--part-{n:02d}.md",
            source_file="raw/docs/field-guide.md", project="docs",
            title="Field guide", date="2026-07-02",
        )
    _write(
        vault / "wiki" / "concepts" / "Guides.md",
        "---\ntitle: Guides\ntype: concept\n---\n\n- [[old-guide--part-02]]\n",
    )
    _write(vault / "wiki" / "log.md", "# Wiki Log\n")

    report = run_migration(vault=vault)

    docs = vault / "wiki" / "sources" / "docs"
    assert sorted(p.name for p in docs.iterdir()) == [
        "2026-07-02-field-guide--part-01.md",
        "2026-07-02-field-guide--part-02.md",
    ]
    assert report["state_upserts"] == ["docs::field-guide.md"]
    concept = (vault / "wiki" / "concepts" / "Guides.md").read_text(encoding="utf-8")
    assert "[[2026-07-02-field-guide--part-02]]" in concept


# ─── CLI wiring ─────────────────────────────────────────────────────────


def test_migrate_list_includes_it(capsys) -> None:
    args = build_parser().parse_args(["migrate", "--list"])

    assert args.func(args) == 0
    assert "source-page-paths" in capsys.readouterr().out


def test_cli_dry_run_exits_zero_and_writes_nothing(tmp_path: Path, capsys) -> None:
    vault = _vault(tmp_path)
    before = _snapshot(vault)
    args = build_parser().parse_args(
        ["migrate", "source-page-paths", "--vault", str(vault), "--dry-run"]
    )

    assert args.func(args) == 0
    capsys.readouterr()
    assert _snapshot(vault) == before


def test_cli_requires_a_vault() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(["migrate", "source-page-paths"])
