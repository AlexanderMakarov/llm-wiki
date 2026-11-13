"""`llmwiki remove` cascade — a matched raw doc drags every derived
artifact out with it (raw file, synth-state key, wiki source page), so a
naive `rm raw/docs/...` can never leave the wiki holding orphan pages or
dangling state keys (B2). Pages that cited a removed source page are cleaned
too: ``sources:`` trimmed, wikilinks dropped or unlinked, unsourced curated
pages archived (#277)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import llmwiki.remove_doc as rd
from llmwiki._frontmatter import parse_frontmatter
from llmwiki.add_doc import add_sources, expected_source_page
from llmwiki.candidates import rewrite_sources_line
from llmwiki.candidates_harvest import harvest_targets
from llmwiki.cli import main
from llmwiki.dismissal_ledger import iter_dismissals, rebuild_ledger_from_archive
from llmwiki.lint import load_pages, run_all
from llmwiki.remove_doc import RemoveIncompleteError, build_remove_plan, execute_remove_plan, format_plan
from llmwiki.synth.pipeline import synthesize_new_sessions


def _read_synth_keys(state_file: Path) -> set[str]:
    return set(json.loads(state_file.read_text())["synth"]["files"])


def _build_vault(tmp_path: Path) -> tuple[Path, list[Path], Path]:
    """A real vault: one added raw doc, its synth-state key, its wiki page.

    Built through the real add + synthesize path so the layout matches
    exactly what production writes (empty ``source_file`` on doc pages
    included), not a hand-faked stand-in.
    """
    vault = tmp_path / "vault"
    docs = vault / "raw" / "docs"
    docs.mkdir(parents=True)
    sessions = vault / "raw" / "sessions"
    sessions.mkdir(parents=True)
    wiki_sources = vault / "wiki" / "sources"
    wiki_sources.mkdir(parents=True)
    (vault / "wiki" / "log.md").write_text("# Log\n", encoding="utf-8")
    (vault / "wiki" / "index.md").write_text(
        "# Wiki Index\n\n## Sources\n*(none yet)*\n\n## Entities\n- keep me\n",
        encoding="utf-8",
    )

    src = tmp_path / "note.md"
    src.write_text("# Old Project\n\nReference notes for the old project. " * 30, encoding="utf-8")
    res = add_sources([str(src)], docs, project="old-project")

    state_file = vault / "llmwiki-state.json"
    synthesize_new_sessions(
        raw_dir=sessions, wiki_sources_dir=wiki_sources, docs_dir=docs,
        state_file=state_file, log_path=vault / "wiki" / "log.md",
    )
    return vault, res["written"], state_file


def test_plan_lists_the_full_cascade(tmp_path: Path) -> None:
    vault, written, state_file = _build_vault(tmp_path)
    raw_doc = written[0]
    page = expected_source_page(raw_doc, vault / "wiki" / "sources")
    assert raw_doc.exists() and page.exists()

    plan = build_remove_plan(vault, "old-project*", state_file=state_file)

    assert raw_doc in plan.raw_docs
    assert page in plan.source_pages
    assert "docs::old-project/old-project.md" in plan.state_keys
    assert not plan.is_empty


def test_dry_run_mutates_nothing(tmp_path: Path) -> None:
    vault, written, state_file = _build_vault(tmp_path)
    raw_doc = written[0]
    page = expected_source_page(raw_doc, vault / "wiki" / "sources")
    log_before = (vault / "wiki" / "log.md").read_text()
    keys_before = _read_synth_keys(state_file)

    # Planning is read-only; a dry-run is exactly "plan, then don't execute".
    plan = build_remove_plan(vault, "old-project*", state_file=state_file)
    assert not plan.is_empty

    assert raw_doc.exists()
    assert page.exists()
    assert _read_synth_keys(state_file) == keys_before
    assert (vault / "wiki" / "log.md").read_text() == log_before
    assert "remove" not in log_before


def test_execute_removes_the_whole_cascade_orphan_free(tmp_path: Path) -> None:
    vault, written, state_file = _build_vault(tmp_path)
    raw_doc = written[0]
    wiki_sources = vault / "wiki" / "sources"
    page = expected_source_page(raw_doc, wiki_sources)

    plan = build_remove_plan(vault, "old-project*", state_file=state_file)
    result = execute_remove_plan(plan, state_file=state_file)

    # Raw doc + its wiki page + its state key are all gone.
    assert not raw_doc.exists()
    assert not page.exists()
    assert "docs::old-project/old-project.md" not in _read_synth_keys(state_file)
    assert result["raw_docs"] == 1
    assert result["source_pages"] == 1

    # No orphan page anywhere still pointing at a deleted raw doc.
    for p in wiki_sources.rglob("*.md"):
        meta, _ = parse_frontmatter(p.read_text())
        assert "old-project" not in str(meta.get("source_file", ""))

    # A remove entry landed in the log, unrelated index sections survived.
    log = (vault / "wiki" / "log.md").read_text()
    assert "remove | 1 docs (old-project*)" in log
    assert "keep me" in (vault / "wiki" / "index.md").read_text()


def test_source_file_frontmatter_page_is_caught(tmp_path: Path) -> None:
    """A manually-placed page (arbitrary folder/name) is still cascaded
    when its ``source_file`` points at a removed raw doc."""
    vault, written, state_file = _build_vault(tmp_path)
    manual = vault / "wiki" / "sources" / "hand-written.md"
    manual.write_text(
        "---\ntitle: manual\ntype: source\n"
        "source_file: raw/docs/old-project/old-project.md\n---\n\nbody\n",
        encoding="utf-8",
    )

    plan = build_remove_plan(vault, "old-project*", state_file=state_file)
    assert manual in plan.source_pages
    execute_remove_plan(plan, state_file=state_file)
    assert not manual.exists()


def test_glob_scopes_to_matching_docs(tmp_path: Path) -> None:
    vault, _written, state_file = _build_vault(tmp_path)
    docs = vault / "raw" / "docs"
    other = tmp_path / "other.md"
    other.write_text("# Taxes\n\nUnrelated content. " * 30, encoding="utf-8")
    add_sources([str(other)], docs, project="taxes")
    synthesize_new_sessions(
        raw_dir=vault / "raw" / "sessions",
        wiki_sources_dir=vault / "wiki" / "sources",
        docs_dir=docs, state_file=state_file,
        log_path=vault / "wiki" / "log.md",
    )

    plan = build_remove_plan(vault, "old-project*", state_file=state_file)
    execute_remove_plan(plan, state_file=state_file)

    assert not (docs / "old-project").exists()
    assert (docs / "taxes" / "taxes.md").exists()
    assert "docs::taxes/taxes.md" in _read_synth_keys(state_file)


def test_empty_match_is_a_clean_noop(tmp_path: Path) -> None:
    vault, written, state_file = _build_vault(tmp_path)
    keys_before = _read_synth_keys(state_file)

    plan = build_remove_plan(vault, "does-not-exist*", state_file=state_file)
    assert plan.is_empty
    assert plan.raw_docs == []

    result = execute_remove_plan(plan, state_file=state_file)
    assert result["raw_docs"] == 0
    assert written[0].exists()
    assert _read_synth_keys(state_file) == keys_before


def test_cli_remove_requires_confirmation(tmp_path: Path, monkeypatch) -> None:
    vault, written, _state_file = _build_vault(tmp_path)

    # No --yes and no TTY → refuse to cascade, exit non-zero, touch nothing.
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    rc = main(["remove", "old-project*", "--vault", str(vault)])
    assert rc != 0
    assert written[0].exists()


def test_cli_remove_yes_executes(tmp_path: Path) -> None:
    vault, written, state_file = _build_vault(tmp_path)
    page = expected_source_page(written[0], vault / "wiki" / "sources")

    rc = main(["remove", "old-project*", "--yes", "--vault", str(vault)])
    assert rc == 0
    assert not written[0].exists()
    assert not page.exists()
    assert "docs::old-project/old-project.md" not in _read_synth_keys(state_file)


def test_cli_remove_dry_run_reports_without_deleting(tmp_path: Path, capsys) -> None:
    vault, written, state_file = _build_vault(tmp_path)

    rc = main(["remove", "old-project*", "--dry-run", "--vault", str(vault)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "old-project" in out
    assert "docs::old-project/old-project.md" in out
    assert written[0].exists()


def test_pending_backlog_entry_is_dropped(tmp_path: Path) -> None:
    """A doc removed before it was ever synthesized has no ``synth.files``
    key — only a ``synth.pending`` entry. Dropping just the files dict would
    strand the backlog pointing at a file that no longer exists."""
    vault, written, state_file = _build_vault(tmp_path)
    raw_doc = written[0]
    rel = raw_doc.relative_to(vault / "raw" / "docs").as_posix()
    source = f"raw/docs/{rel}"

    state = json.loads(state_file.read_text())
    synth = state["synth"]
    synth["pending"] = [
        {"is_doc": True, "project": "old-project", "rel": rel,
         "source": source, "mtime": "2026-07-07T00:00:00Z"},
        {"is_doc": False, "project": "other", "rel": "s.md",
         "source": "raw/sessions/s.md", "mtime": "2026-07-07T00:00:00Z"},
    ]
    synth["pending_total"] = 2
    state_file.write_text(json.dumps(state), encoding="utf-8")

    plan = build_remove_plan(vault, "old-project*", state_file=state_file)
    assert source in plan.pending_sources

    result = execute_remove_plan(plan, state_file=state_file)
    assert result["pending_entries"] == 1

    after = json.loads(state_file.read_text())["synth"]
    remaining = [e["source"] for e in after["pending"]]
    assert source not in remaining
    assert "raw/sessions/s.md" in remaining  # unrelated backlog survives
    assert after["pending_total"] == 1


def test_backlink_blocks_survive_removal(tmp_path: Path) -> None:
    """`backlinks.prune_all` strips the block from EVERY page and nothing
    regenerates it (`inject_all` has no caller), so removal must not call it —
    otherwise removing one project silently wipes backlinks wiki-wide."""
    vault, written, state_file = _build_vault(tmp_path)
    entities = vault / "wiki" / "entities"
    entities.mkdir(parents=True, exist_ok=True)
    keeper = entities / "Foo.md"
    keeper.write_text(
        "# Foo\n\n<!-- BACKLINKS:START -->\n## Referenced by\n\n- [[Bar]]\n"
        "<!-- BACKLINKS:END -->\n",
        encoding="utf-8",
    )

    plan = build_remove_plan(vault, "old-project*", state_file=state_file)
    execute_remove_plan(plan, state_file=state_file)

    assert "BACKLINKS:START" in keeper.read_text(encoding="utf-8")


def test_partial_raw_failure_aborts_before_touching_derivatives(tmp_path: Path) -> None:
    """If a raw doc cannot be unlinked, the page and state key must survive —
    reporting success while the vault is half-removed is worse than failing."""

    vault, written, state_file = _build_vault(tmp_path)
    raw_doc = written[0]
    page = expected_source_page(raw_doc, vault / "wiki" / "sources")
    assert page.exists()

    plan = build_remove_plan(vault, "old-project*", state_file=state_file)
    raw_doc.parent.chmod(0o500)  # read+execute: unlink denied
    try:
        with pytest.raises(RemoveIncompleteError):
            execute_remove_plan(plan, state_file=state_file)
    finally:
        raw_doc.parent.chmod(0o700)

    assert raw_doc.exists()
    assert page.exists(), "derived page deleted despite the raw doc surviving"
    assert "docs::old-project/old-project.md" in _read_synth_keys(state_file)


def test_selector_does_not_cross_project_boundaries(tmp_path: Path) -> None:
    """A bare stem must not glob across projects — `notes` selecting both
    `taxes/notes.md` and `legal/notes.md` is the wrong default for a delete."""
    vault, _written, state_file = _build_vault(tmp_path)
    docs = vault / "raw" / "docs"
    for proj in ("taxes", "legal"):
        (docs / proj).mkdir(parents=True, exist_ok=True)
        (docs / proj / "notes.md").write_text(
            f"---\nproject: {proj}\nslug: notes\n---\n\n# Notes\n", encoding="utf-8"
        )

    plan = build_remove_plan(vault, "notes", state_file=state_file)
    assert plan.raw_docs == [], "bare stem must not select across projects"

    # The project-qualified form still targets exactly one doc.
    plan = build_remove_plan(vault, "taxes/notes", state_file=state_file)
    assert [p.name for p in plan.raw_docs] == ["notes.md"]
    assert plan.raw_docs[0].parent.name == "taxes"


def test_page_owned_by_another_source_is_not_deleted(tmp_path: Path) -> None:
    """A page whose `source_file` names a DIFFERENT raw file must survive even
    if it collides on the derived path (sessions share that namespace)."""
    vault, written, state_file = _build_vault(tmp_path)
    raw_doc = written[0]
    page = expected_source_page(raw_doc, vault / "wiki" / "sources")
    page.write_text(
        "---\ntitle: \"Someone else\"\nsource_file: raw/sessions/other.md\n---\n\nBody\n",
        encoding="utf-8",
    )

    plan = build_remove_plan(vault, "old-project*", state_file=state_file)
    assert page not in plan.source_pages
    execute_remove_plan(plan, state_file=state_file)
    assert page.exists()


# ─── citing-page cleanup (#277) ───────────────────────────────────────────────


def _write(vault: Path, rel: str, text: str) -> Path:
    path = vault / "wiki" / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _page(sources: str | None, body: str, title: str = "T") -> str:
    sources_line = f"sources: {sources}\n" if sources is not None else ""
    return f'---\ntitle: "{title}"\ntype: entity\n{sources_line}last_updated: 2026-01-01\n---\n\n{body}'


def _vault_with_slug(tmp_path: Path) -> tuple[Path, str, Path]:
    """The base vault plus a surviving source page ``keep-src``; returns the
    removed doc page's slug."""
    vault, written, state_file = _build_vault(tmp_path)
    slug = expected_source_page(written[0], vault / "wiki" / "sources").stem
    _write(vault, "sources/other/keep-src.md", '---\ntitle: "keep"\ntype: source\n---\n\nbody\n')
    return vault, slug, state_file


def _provenance_issues(vault: Path) -> list[dict]:
    return run_all(load_pages(vault / "wiki"), selected=["provenance_integrity"])


def _snapshot(vault: Path) -> dict[str, str]:
    return {
        p.relative_to(vault).as_posix(): p.read_text(encoding="utf-8")
        for p in sorted((vault / "wiki").rglob("*.md"))
    }


def test_remove_trims_sources_and_leaves_provenance_clean(tmp_path: Path) -> None:
    vault, slug, state_file = _vault_with_slug(tmp_path)
    foo = _write(vault, "entities/Foo.md", _page(
        f"[{slug}, keep-src]", "Backed by [[keep-src]] and [[Unrelated]].\n"))
    bystander = _write(vault, "entities/Bystander.md", _page("[keep-src]", "See [[Foo]].\n"))
    bystander_before = bystander.read_text(encoding="utf-8")
    assert _provenance_issues(vault) == []

    plan = build_remove_plan(vault, "old-project*", state_file=state_file)
    result = execute_remove_plan(plan, state_file=state_file)

    meta, body = parse_frontmatter(foo.read_text(encoding="utf-8"))
    assert meta["sources"] == ["keep-src"]
    assert "[[keep-src]]" in body and "[[Unrelated]]" in body  # unrelated links untouched
    assert bystander.read_text(encoding="utf-8") == bystander_before
    assert result["citing_pages"] == 1 and result["sources_trimmed"] == 1
    assert _provenance_issues(vault) == []


def test_remove_drops_link_only_items_and_unlinks_prose(tmp_path: Path) -> None:
    vault, slug, state_file = _vault_with_slug(tmp_path)
    foo = _write(vault, "entities/Foo.md", _page("[keep-src]", (
        f"Prose cites [[{slug}|the notes]] and [[{slug}]].\n\n## Connections\n"
        f"- [[{slug}]]\n- [[{slug}|Label]]\n* [[{slug}#Part]]\n1. [[{slug}]]\n"
        f"- [[{slug}]] — kept note\n- [[Other]]\n"
    )))

    plan = build_remove_plan(vault, "old-project*", state_file=state_file)
    result = execute_remove_plan(plan, state_file=state_file)

    text = foo.read_text(encoding="utf-8")
    assert f"[[{slug}" not in text
    assert "Prose cites the notes and " + slug + "." in text
    assert f"- {slug} — kept note" in text  # item with more than the link is delinked, not dropped
    assert "- [[Other]]" in text
    assert text.count("\n- ") + text.count("\n* ") + text.count("\n1. ") == 2
    assert result["list_items_dropped"] == 4
    assert result["links_unlinked"] == 3  # two in prose + the annotated bullet


def test_remove_archives_page_left_with_no_sources(tmp_path: Path) -> None:
    vault, slug, state_file = _vault_with_slug(tmp_path)
    bar = _write(vault, "concepts/Bar.md", _page(f"[{slug}]", "Only fact.\n", "Bar"))
    foo = _write(vault, "entities/Foo.md", _page("[keep-src]", "Related: [[Bar]] and [[Bar|the bar]].\n"))

    plan = build_remove_plan(vault, "old-project*", state_file=state_file)
    assert [e.rel.as_posix() for e in plan.pages_to_archive] == ["concepts/Bar.md"]
    result = execute_remove_plan(plan, state_file=state_file)

    archived = vault / "wiki" / "archive" / "concepts" / "Bar.md"
    assert not bar.exists() and archived.is_file()
    assert "sources:" not in archived.read_text(encoding="utf-8")
    assert result["pages_archived"] == 1
    # Inbound links to the archived page become plain text.
    assert "Related: Bar and the bar." in foo.read_text(encoding="utf-8")
    assert _provenance_issues(vault) == []


def test_archive_name_collision_nests_under_timestamp(tmp_path: Path) -> None:
    vault, slug, state_file = _vault_with_slug(tmp_path)
    _write(vault, "archive/concepts/Bar.md", "older archived copy\n")
    _write(vault, "concepts/Bar.md", _page(f"[{slug}]", "Only fact.\n", "Bar"))

    plan = build_remove_plan(vault, "old-project*", state_file=state_file)
    execute_remove_plan(plan, state_file=state_file)

    archive = vault / "wiki" / "archive"
    assert (archive / "concepts" / "Bar.md").read_text(encoding="utf-8") == "older archived copy\n"
    nested = [p for p in archive.rglob("Bar.md") if p != archive / "concepts" / "Bar.md"]
    assert len(nested) == 1
    assert nested[0].relative_to(archive).parts[1:] == ("concepts", "Bar.md")


def test_system_and_nav_pages_are_trimmed_but_never_archived(tmp_path: Path) -> None:
    vault, slug, state_file = _vault_with_slug(tmp_path)
    hot = _write(vault, "hot.md", _page(f"[{slug}]", "- [[" + slug + "]]\n"))
    ctx = _write(vault, "entities/_context.md", _page(f"[{slug}]", "Folder notes.\n"))
    log = vault / "wiki" / "log.md"
    log.write_text(f"# Log\n\n- [[{slug}]]\n", encoding="utf-8")

    plan = build_remove_plan(vault, "old-project*", state_file=state_file)
    assert plan.pages_to_archive == []
    execute_remove_plan(plan, state_file=state_file)

    assert hot.is_file() and ctx.is_file()
    assert "sources:" not in hot.read_text(encoding="utf-8")
    assert f"- [[{slug}]]" in log.read_text(encoding="utf-8")  # append-only history untouched
    assert not (vault / "wiki" / "archive").exists()


def test_stem_shared_with_a_surviving_source_page_is_left_alone(tmp_path: Path) -> None:
    vault, slug, state_file = _vault_with_slug(tmp_path)
    _write(vault, f"sources/legal/{slug}.md", '---\ntitle: "twin"\ntype: source\n---\n\nbody\n')
    foo = _write(vault, "entities/Foo.md", _page(f"[{slug}]", f"See [[{slug}]].\n"))
    before = foo.read_text(encoding="utf-8")

    plan = build_remove_plan(vault, "old-project*", state_file=state_file)
    assert plan.removed_slugs == [] and plan.citing_pages == []
    execute_remove_plan(plan, state_file=state_file)

    assert foo.read_text(encoding="utf-8") == before


def test_link_a_live_page_still_answers_to_is_kept(tmp_path: Path) -> None:
    """A project page named like the removed source slug keeps its inbound
    links; only the dangling ``sources:`` entry goes."""
    vault, slug, state_file = _vault_with_slug(tmp_path)
    _write(vault, f"projects/{slug}.md", _page("[keep-src]", "Project page.\n", slug))
    foo = _write(vault, "entities/Foo.md", _page(f"[{slug}, keep-src]", f"Part of [[{slug}]].\n"))

    plan = build_remove_plan(vault, "old-project*", state_file=state_file)
    assert plan.delink_keys == []
    execute_remove_plan(plan, state_file=state_file)

    meta, body = parse_frontmatter(foo.read_text(encoding="utf-8"))
    assert meta["sources"] == ["keep-src"]
    assert f"[[{slug}]]" in body


def test_dry_run_reports_citing_pages_and_writes_nothing(tmp_path: Path, capsys) -> None:
    vault, slug, state_file = _vault_with_slug(tmp_path)
    _write(vault, "concepts/Bar.md", _page(f"[{slug}]", "Only fact.\n", "Bar"))
    _write(vault, "entities/Foo.md", _page(f"[{slug}, keep-src]", f"- [[{slug}]]\nSee [[{slug}]].\n"))
    before = _snapshot(vault)
    keys_before = _read_synth_keys(state_file)

    plan = build_remove_plan(vault, "old-project*", state_file=state_file)
    preview = format_plan(plan)
    assert "wiki/entities/Foo.md" in preview and "1 list item(s) dropped" in preview
    assert "wiki/concepts/Bar.md" in preview and "will archive" in preview
    assert "prune backlinks" not in preview

    assert main(["remove", "old-project*", "--dry-run", "--vault", str(vault)]) == 0
    assert "wiki/concepts/Bar.md" in capsys.readouterr().out
    assert _snapshot(vault) == before
    assert not (vault / "wiki" / "archive").exists()
    assert _read_synth_keys(state_file) == keys_before


def test_cli_remove_reports_cleanup_and_logs_it(tmp_path: Path, capsys) -> None:
    vault, slug, _state_file = _vault_with_slug(tmp_path)
    _write(vault, "concepts/Bar.md", _page(f"[{slug}]", "Only fact.\n", "Bar"))
    _write(vault, "entities/Foo.md", _page(f"[{slug}, keep-src]", f"See [[{slug}]].\n"))

    assert main(["remove", "old-project*", "--yes", "--vault", str(vault)]) == 0

    out = capsys.readouterr().out
    assert "cleaned 2 citing page(s): 2 source(s) trimmed, 1 link(s) unlinked" in out
    assert "1 page(s) archived" in out
    log = (vault / "wiki" / "log.md").read_text(encoding="utf-8")
    assert "remove | 1 docs (old-project*)" in log
    assert "2 citing page(s)" in log
    assert _provenance_issues(vault) == []


def test_inbound_delink_never_rewrites_log_pages(tmp_path: Path) -> None:
    """Archiving a page unlinks live links to it but leaves ``log.md`` and its
    yearly archives byte-identical (append-only), and does not count them."""
    vault, slug, state_file = _vault_with_slug(tmp_path)
    _write(vault, "concepts/Bar.md", _page(f"[{slug}]", "Only fact.\n", "Bar"))
    foo = _write(vault, "entities/Foo.md", _page("[keep-src]", "Related: [[Bar]].\n"))
    log = vault / "wiki" / "log.md"
    log_before = "# Log\n\n- Created [[Bar]]\n"
    log.write_text(log_before, encoding="utf-8")
    log_archive = _write(vault, "log-archive-2025.md", "# Old log\n\n- Created [[Bar]]\n")
    archive_before = log_archive.read_bytes()

    plan = build_remove_plan(vault, "old-project*", state_file=state_file)
    result = execute_remove_plan(plan, state_file=state_file)

    assert "Related: Bar." in foo.read_text(encoding="utf-8")
    assert result["links_unlinked"] == 1  # the live page only; log pages are not counted
    assert log_archive.read_bytes() == archive_before
    log_after = log.read_text(encoding="utf-8")
    assert log_after.startswith(log_before)  # only appended to
    assert "- Created [[Bar]]" in log_after


def test_archived_page_is_recorded_as_a_settled_name(tmp_path: Path) -> None:
    vault, slug, state_file = _vault_with_slug(tmp_path)
    _write(vault, "concepts/Bar.md", _page(f"[{slug}]", "Only fact.\n", "Bar"))
    _write(vault, "candidates/Baz.md", _page(f"[{slug}]", "Pending.\n", "Baz"))
    wiki = vault / "wiki"

    plan = build_remove_plan(vault, "old-project*", state_file=state_file)
    execute_remove_plan(plan, state_file=state_file)

    rows = {r["key"]: r for r in iter_dismissals(wiki)}
    assert set(rows) == {"bar", "baz"}
    assert rows["bar"]["reason"] == "archived by remove: last citing source removed"
    assert rows["bar"]["stub"] == "../concepts/Bar.md"
    assert rows["baz"]["stub"] == "Baz.md"
    assert (wiki / "archive" / "candidates" / "Baz.md").is_file()
    assert (wiki / "archive" / "candidates" / "dismissals.json").is_file()


def test_page_trimmed_but_not_archived_is_not_recorded(tmp_path: Path) -> None:
    vault, slug, state_file = _vault_with_slug(tmp_path)
    _write(vault, "entities/Foo.md", _page(f"[{slug}, keep-src]", "Fact.\n"))

    plan = build_remove_plan(vault, "old-project*", state_file=state_file)
    execute_remove_plan(plan, state_file=state_file)

    assert not (vault / "wiki" / "archive").exists()


def test_harvest_does_not_reopen_a_topic_remove_archived(tmp_path: Path) -> None:
    """After ``remove`` archives a topic page, re-adding evidence for it (three
    sources linking it) must not propose it as a candidate again."""
    vault, slug, state_file = _vault_with_slug(tmp_path)
    wiki = vault / "wiki"
    _write(vault, "concepts/Bar.md", _page(f"[{slug}]", "Only fact.\n", "Bar"))
    plan = build_remove_plan(vault, "old-project*", state_file=state_file)
    execute_remove_plan(plan, state_file=state_file)
    # Layout alone must not be what settles it: drop the archived file itself.
    (wiki / "archive" / "concepts" / "Bar.md").unlink()
    for n in range(3):
        _write(vault, f"sources/other/again-{n}.md",
               '---\ntitle: again\ntype: source\n---\n\n## Connections\n- [[Bar]] — why\n')

    assert [t.name for t in harvest_targets(wiki)] == []


# ─── local-review 2 (#277) ────────────────────────────────────────────────────

REMOVE_REASON = "archived by remove: last citing source removed"


def test_ledger_rebuild_keeps_names_remove_archived(tmp_path: Path) -> None:
    """``migrate dismissal-ledger`` / a missing ledger must not forget a page
    ``remove`` archived outside ``archive/candidates/`` — nor a reviewer's own
    dismissal sitting next to it."""
    vault, slug, state_file = _vault_with_slug(tmp_path)
    wiki = vault / "wiki"
    _write(vault, "concepts/Bar.md", _page(f"[{slug}]", "Only fact.\n", "Bar Concept"))
    _write(vault, "archive/candidates/2026-01-01T00-00-00/Noise.md", '---\ntitle: "Noise"\n---\n')
    execute_remove_plan(build_remove_plan(vault, "old-project*", state_file=state_file), state_file=state_file)
    assert {"bar", "barconcept"} <= {r["key"] for r in iter_dismissals(wiki)}

    rebuilt = rebuild_ledger_from_archive(wiki)

    rows = {r["key"]: r for r in rebuilt["dismissals"]}
    assert rows["bar"]["reason"] == REMOVE_REASON and rows["bar"]["stub"] == "../concepts/Bar.md"
    assert rows["barconcept"]["reason"] == REMOVE_REASON
    assert rows["noise"]["reason"] == "" and rows["noise"]["stub"] == "2026-01-01T00-00-00/Noise.md"
    # The ledger survives being deleted: a plain read rebuilds the same rows.
    (wiki / "archive" / "candidates" / "dismissals.json").unlink()
    assert {r["key"] for r in iter_dismissals(wiki)} == set(rows)


def test_ledger_rebuild_without_candidates_dir(tmp_path: Path) -> None:
    vault, _slug, _state = _vault_with_slug(tmp_path)
    wiki = vault / "wiki"
    _write(vault, "archive/entities/Foo.md", _page(None, "gone\n", "Foo"))
    assert {r["key"] for r in iter_dismissals(wiki)} == {"foo"}


def test_corrupt_ledger_aborts_before_any_delete(tmp_path: Path, capsys) -> None:
    vault, slug, state_file = _vault_with_slug(tmp_path)
    raw_doc = next((vault / "raw" / "docs").rglob("*.md"))
    page = expected_source_page(raw_doc, vault / "wiki" / "sources")
    bar = _write(vault, "concepts/Bar.md", _page(f"[{slug}]", "Only fact.\n", "Bar"))
    ledger = _write_ledger(vault, "{not json")
    bar_before = bar.read_text(encoding="utf-8")
    keys_before = _read_synth_keys(state_file)

    plan = build_remove_plan(vault, "old-project*", state_file=state_file)
    with pytest.raises(RemoveIncompleteError, match="migrate dismissal-ledger"):
        execute_remove_plan(plan, state_file=state_file)

    assert raw_doc.exists() and page.exists()
    assert bar.read_text(encoding="utf-8") == bar_before and not (vault / "wiki" / "archive" / "concepts").exists()
    assert _read_synth_keys(state_file) == keys_before
    assert ledger.read_text(encoding="utf-8") == "{not json"

    assert main(["remove", "old-project*", "--yes", "--vault", str(vault)]) == 2
    assert "migrate dismissal-ledger" in capsys.readouterr().err
    assert raw_doc.exists()


def _write_ledger(vault: Path, text: str) -> Path:
    path = vault / "wiki" / "archive" / "candidates" / "dismissals.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_corrupt_ledger_is_ignored_when_nothing_is_archived(tmp_path: Path) -> None:
    vault, slug, state_file = _vault_with_slug(tmp_path)
    _write(vault, "entities/Foo.md", _page(f"[{slug}, keep-src]", "Fact.\n"))
    _write_ledger(vault, "{not json")
    result = execute_remove_plan(build_remove_plan(vault, "old-project*", state_file=state_file), state_file=state_file)
    assert result["raw_docs"] == 1 and result["sources_trimmed"] == 1


def test_unwritable_citing_page_is_reported_not_raised(tmp_path: Path, capsys, monkeypatch) -> None:
    vault, slug, state_file = _vault_with_slug(tmp_path)
    foo = _write(vault, "entities/Foo.md", _page(f"[{slug}, keep-src]", "Fact.\n"))
    other = _write(vault, "entities/Other.md", _page(f"[{slug}, keep-src]", "Fact.\n"))
    real = rd.write_page_text

    def _flaky(path: Path, text: str) -> None:
        if path == foo:
            raise PermissionError("denied")
        real(path, text)

    monkeypatch.setattr(rd, "write_page_text", _flaky)
    assert main(["remove", "old-project*", "--yes", "--vault", str(vault)]) == 1

    assert "wiki/entities/Foo.md: denied" in capsys.readouterr().err
    assert slug in foo.read_text(encoding="utf-8")  # untouched, reported
    assert slug not in other.read_text(encoding="utf-8")  # the rest still cleaned
    assert "1 page error(s)" in (vault / "wiki" / "log.md").read_text(encoding="utf-8")


def test_frontmatter_list_items_are_not_dropped(tmp_path: Path) -> None:
    """A ``- [[slug]]`` line inside YAML frontmatter must not lose its item
    (that would leave a bare ``related:`` key); the body bullet still goes."""
    vault, slug, state_file = _vault_with_slug(tmp_path)
    foo = _write(vault, "entities/Foo.md", (
        f'---\ntitle: "Foo"\ntype: entity\nsources: [keep-src]\nrelated:\n  - [[{slug}]]\n  - [[Other]]\n---\n\n'
        f"## Connections\n- [[{slug}]]\n"
    ))
    execute_remove_plan(build_remove_plan(vault, "old-project*", state_file=state_file), state_file=state_file)

    text = foo.read_text(encoding="utf-8")
    head, _, body = text.partition("\n---\n\n")
    assert f"  - {slug}\n  - [[Other]]" in head  # item kept, link made plain text
    assert f"- [[{slug}]]" not in body and "## Connections" in body  # emptied section left for lint/agent


def test_crlf_page_keeps_its_line_endings(tmp_path: Path) -> None:
    vault, slug, state_file = _vault_with_slug(tmp_path)
    crlf = _write(vault, "entities/Foo.md", "")
    crlf.write_bytes((
        f'---\r\ntitle: "Foo"\r\nsources: [{slug}, keep-src]\r\n---\r\n\r\n'
        f"See [[{slug}]].\r\n- [[{slug}]]\r\n- [[Other]]\r\n"
    ).encode())
    bar = _write(vault, "concepts/Bar.md", "")
    bar.write_bytes(f'---\r\ntitle: "Bar"\r\nsources: [{slug}]\r\n---\r\n\r\nFact.\r\n'.encode())
    inbound = _write(vault, "entities/Inbound.md", "")
    inbound.write_bytes(b'---\r\ntitle: "I"\r\nsources: [keep-src]\r\n---\r\n\r\nSee [[Bar]].\r\n')

    execute_remove_plan(build_remove_plan(vault, "old-project*", state_file=state_file), state_file=state_file)

    data = crlf.read_bytes()
    assert b"\n" not in data.replace(b"\r\n", b"") and b"sources: [keep-src]\r\n" in data
    assert b"- [[Other]]\r\n" in data and slug.encode() + b"." in data
    assert inbound.read_bytes().endswith(b"See Bar.\r\n")  # inbound delink keeps CRLF too
    assert (vault / "wiki" / "archive" / "concepts" / "Bar.md").read_bytes().count(b"\r\n") == 5


def test_block_style_sources_are_trimmed_and_archived(tmp_path: Path) -> None:
    vault, slug, state_file = _vault_with_slug(tmp_path)
    blk = _write(vault, "entities/Blk.md", (
        f'---\ntitle: "Blk"\nsources:\n  - {slug}\n  - "keep-src"\nlast_updated: 2026-01-01\n---\n\n- [[{slug}]]\nBody.\n'
    ))
    solo = _write(vault, "concepts/Solo.md", f'---\ntitle: "Solo"\nsources:\n  - {slug}\n---\n\nFact.\n')

    plan = build_remove_plan(vault, "old-project*", state_file=state_file)
    assert [e.rel.as_posix() for e in plan.pages_to_archive] == ["concepts/Solo.md"]
    execute_remove_plan(plan, state_file=state_file)

    assert blk.read_text(encoding="utf-8") == (
        '---\ntitle: "Blk"\nsources:\n  - "keep-src"\nlast_updated: 2026-01-01\n---\n\nBody.\n'
    )
    assert not solo.exists() and (vault / "wiki" / "archive" / "concepts" / "Solo.md").is_file()


def test_rewrite_sources_line_block_and_inline_forms() -> None:
    block = '---\r\nsources:\r\n  - a\r\n  - B\r\ntitle: t\r\n---\r\nbody\r\n'
    assert rewrite_sources_line(block, {"b"}) == '---\r\nsources:\r\n  - a\r\ntitle: t\r\n---\r\nbody\r\n'
    assert rewrite_sources_line(block, {"a", "b"}) == '---\r\ntitle: t\r\n---\r\nbody\r\n'
    assert rewrite_sources_line(block, {"zzz"}) == block
    assert rewrite_sources_line("---\nsources: [a, b]\n---\n", {"a"}) == "---\nsources: [b]\n---\n"
    # ``sources:`` outside a closed frontmatter block is body text.
    assert rewrite_sources_line("---\nsources: [a]\n", {"a"}) == "---\nsources: [a]\n"
