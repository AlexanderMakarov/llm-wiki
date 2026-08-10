"""Migration off the removed `question` / `comparison` page kinds (#109).

The migration's whole job is to make an existing vault lint clean after the
vocabulary cut without the user hand-editing anything, so the acceptance test
here is the round trip: seed a vault carrying both removed kinds, run the
migration, and assert `lint` reports no `frontmatter_validity` error.

Relocation correctness rests on wikilink resolution being name-based —
`tests/test_page_kinds.py::test_wikilink_resolution_survives_a_move_between_wiki_folders`
is the evidence for that, and is not duplicated here. What this module adds is
that the migration *preserves the filename*, which is the precondition that
evidence depends on.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from llmwiki.cli import build_parser
from llmwiki.lint import load_pages, run_all
from llmwiki.migrate_page_kinds import REMOVED_KINDS, print_report, run_migration


def _page(path: Path, body: str, **meta: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    front = "".join(f"{k}: {v}\n" for k, v in meta.items())
    path.write_text(f"---\n{front}---\n\n{body}\n", encoding="utf-8")


def _vault(tmp_path: Path) -> Path:
    """A vault carrying one page of each removed kind plus a referrer."""
    wiki = tmp_path / "wiki"
    _page(
        wiki / "questions" / "CacheBudget.md",
        "# Cache budget\n\n## Connections\n- [[demo-session]]",
        title='"Cache budget"',
        type="question",
        last_updated="2026-08-01",
    )
    _page(
        wiki / "comparisons" / "SyncVsSynth.md",
        "# Sync vs synth\n\n## Connections\n- [[demo-session]]",
        title='"Sync vs synth"',
        type="comparison",
        last_updated="2026-08-01",
    )
    _page(
        wiki / "questions" / "_context.md",
        "Open questions.",
        title='"Questions"',
        type="context",
    )
    _page(
        wiki / "comparisons" / "_context.md",
        "Side-by-side diffs.",
        title='"Comparisons"',
        type="context",
    )
    _page(
        wiki / "sources" / "demo-session.md",
        "# Demo session\n\n## Connections\n"
        "- [[CacheBudget]] — how it relates\n- [[SyncVsSynth]] — and this one",
        title='"Demo session"',
        type="source",
        date="2026-08-01",
    )
    (wiki / "log.md").write_text("# Wiki Log\n", encoding="utf-8")
    return tmp_path


def _snapshot(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): p.read_text(encoding="utf-8")
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


# ─── retype + relocate ─────────────────────────────────────────────────


def test_removed_kind_pages_are_retyped_and_relocated(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    wiki = vault / "wiki"

    report = run_migration(vault=vault)

    assert report["moved"] == 2
    assert report["collisions"] == 0
    for name in ("CacheBudget.md", "SyncVsSynth.md"):
        moved = wiki / "concepts" / name
        assert moved.is_file(), f"{name} did not land in concepts/"
        assert "type: concept" in moved.read_text(encoding="utf-8")
    assert {p["to"] for p in report["pages"]} == {
        "concepts/CacheBudget.md",
        "concepts/SyncVsSynth.md",
    }


def test_the_referring_page_is_never_edited(tmp_path: Path) -> None:
    """Resolution is name-based, so the migration has no reason to touch a
    referrer — and must not, or it would churn every vault it runs on."""
    vault = _vault(tmp_path)
    referrer = vault / "wiki" / "sources" / "demo-session.md"
    before = referrer.read_text(encoding="utf-8")

    run_migration(vault=vault)

    assert referrer.read_text(encoding="utf-8") == before
    assert "[[CacheBudget]]" in before and "[[SyncVsSynth]]" in before


def test_only_the_type_line_changes(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    source = vault / "wiki" / "questions" / "CacheBudget.md"
    before = source.read_text(encoding="utf-8")

    run_migration(vault=vault)

    after = (vault / "wiki" / "concepts" / "CacheBudget.md").read_text(
        encoding="utf-8"
    )
    assert after == before.replace("type: question", "type: concept")


def test_a_removed_kind_outside_the_legacy_folders_is_retyped_in_place(
    tmp_path: Path,
) -> None:
    """The vocabulary is what changed, not the folder layout — a page already
    sitting in concepts/ still needs its frontmatter fixed."""
    wiki = tmp_path / "wiki"
    page = wiki / "concepts" / "OpenThread.md"
    _page(page, "# Open thread", title='"Open thread"', type="question")

    report = run_migration(vault=tmp_path)

    assert report["retyped"] == 1 and report["moved"] == 0
    assert "type: concept" in page.read_text(encoding="utf-8")


# ─── folder cleanup ────────────────────────────────────────────────────


def test_context_files_and_emptied_folders_are_removed(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    wiki = vault / "wiki"

    report = run_migration(vault=vault)

    assert sorted(report["contexts_removed"]) == [
        "comparisons/_context.md",
        "questions/_context.md",
    ]
    assert sorted(report["folders_removed"]) == ["comparisons", "questions"]
    assert not (wiki / "questions").exists()
    assert not (wiki / "comparisons").exists()


def test_a_folder_holding_other_content_is_kept_and_reported(
    tmp_path: Path,
) -> None:
    vault = _vault(tmp_path)
    keeper = vault / "wiki" / "questions" / "NOTES.md"
    _page(keeper, "# Notes", title='"Notes"', type="concept")

    report = run_migration(vault=vault)

    assert "questions" not in report["folders_removed"]
    assert report["folders_kept"] == [
        {"folder": "questions", "entries": ["NOTES.md"]}
    ]
    assert keeper.is_file(), "unrecognised content must never be deleted"
    assert (vault / "wiki" / "questions").is_dir()
    # The other folder is unaffected by its neighbour's leftovers.
    assert report["folders_removed"] == ["comparisons"]


# ─── the catalog ───────────────────────────────────────────────────────


_INDEX = """# Wiki Index

## Sources (1)
- [Demo session](sources/demo-session.md) — 2026-08-01

## Concepts (0)

## Questions (1)
- [Cache budget](questions/CacheBudget.md)

## Comparisons (1)
- [Sync vs synth](comparisons/SyncVsSynth.md)
"""


def test_index_entries_for_a_pruned_folder_are_unlisted(tmp_path: Path) -> None:
    """`reindex` reconciles a section against its folder, so it cannot clear
    one whose folder is gone — those bullets would stay as `index_sync` dead
    links."""
    vault = _vault(tmp_path)
    index = vault / "wiki" / "index.md"
    index.write_text(_INDEX, encoding="utf-8")

    report = run_migration(vault=vault)

    text = index.read_text(encoding="utf-8")
    assert sorted(report["index_links_pruned"]) == [
        "comparisons/SyncVsSynth.md",
        "questions/CacheBudget.md",
    ]
    assert "questions/" not in text and "comparisons/" not in text
    assert "## Questions" not in text and "## Comparisons" not in text
    # The surviving pages are re-catalogued under their new folder.
    assert "concepts/CacheBudget.md" in text
    assert "sources/demo-session.md" in text


def test_a_kept_folder_is_left_to_reindex(tmp_path: Path) -> None:
    """A folder that survives still backs its section, so `reindex` owns it —
    the migration prunes nothing there."""
    vault = _vault(tmp_path)
    _page(
        vault / "wiki" / "questions" / "NOTES.md",
        "# Notes",
        title='"Notes"',
        type="concept",
    )
    index = vault / "wiki" / "index.md"
    index.write_text(
        _INDEX.replace(
            "- [Cache budget](questions/CacheBudget.md)\n",
            "- [Cache budget](questions/CacheBudget.md)\n- [Notes](questions/NOTES.md)\n",
        ),
        encoding="utf-8",
    )

    report = run_migration(vault=vault)

    text = index.read_text(encoding="utf-8")
    assert report["index_links_pruned"] == ["comparisons/SyncVsSynth.md"]
    assert "questions/NOTES.md" in text
    assert "concepts/CacheBudget.md" in text


def test_a_section_with_prose_survives_losing_its_bullets(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    index = vault / "wiki" / "index.md"
    index.write_text(
        "# Wiki Index\n\n## Questions (1)\n\nThings I still wonder about.\n\n"
        "- [Cache budget](questions/CacheBudget.md)\n",
        encoding="utf-8",
    )

    run_migration(vault=vault)

    text = index.read_text(encoding="utf-8")
    assert "Things I still wonder about." in text
    assert "questions/CacheBudget.md" not in text


def test_a_vault_without_an_index_does_not_get_one(tmp_path: Path) -> None:
    """A vault that keeps no catalog is not handed a seeded one pointing at
    an overview page the user never wrote."""
    vault = _vault(tmp_path)

    run_migration(vault=vault)

    assert not (vault / "wiki" / "index.md").exists()


# ─── collisions ────────────────────────────────────────────────────────


def test_a_filename_collision_retypes_in_place_instead_of_overwriting(
    tmp_path: Path,
) -> None:
    """concepts/ already holding the filename means moving would destroy a
    page. The migration retypes where the page stands so the vault lints
    clean, keeps both files, and reports the clash for the user to settle."""
    vault = _vault(tmp_path)
    wiki = vault / "wiki"
    incumbent = wiki / "concepts" / "CacheBudget.md"
    _page(incumbent, "# Incumbent", title='"Incumbent"', type="concept")
    incumbent_text = incumbent.read_text(encoding="utf-8")

    report = run_migration(vault=vault)

    assert incumbent.read_text(encoding="utf-8") == incumbent_text
    legacy = wiki / "questions" / "CacheBudget.md"
    assert legacy.is_file()
    assert "type: concept" in legacy.read_text(encoding="utf-8")
    assert report["collisions"] == 1
    assert {"action": "collision", "kind": "question",
            "from": "questions/CacheBudget.md",
            "to": "questions/CacheBudget.md"} in report["pages"]
    assert "questions" not in report["folders_removed"]


def test_two_removed_folders_claiming_one_filename_collide(
    tmp_path: Path,
) -> None:
    """The first page wins the name; the second is reported, not clobbered."""
    wiki = tmp_path / "wiki"
    _page(wiki / "comparisons" / "Same.md", "# A", title='"A"', type="comparison")
    _page(wiki / "questions" / "Same.md", "# B", title='"B"', type="question")

    report = run_migration(vault=tmp_path)

    assert report["moved"] == 1 and report["collisions"] == 1
    assert (wiki / "concepts" / "Same.md").read_text(encoding="utf-8").endswith("# A\n")
    assert (wiki / "questions" / "Same.md").is_file()


# ─── dry run + no-op ───────────────────────────────────────────────────


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    before = _snapshot(vault)

    report = run_migration(vault=vault, dry_run=True)

    assert _snapshot(vault) == before
    assert report["dry_run"] is True
    assert report["moved"] == 2
    assert sorted(report["folders_removed"]) == ["comparisons", "questions"]


def test_dry_run_predicts_a_kept_folder(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _page(
        vault / "wiki" / "questions" / "NOTES.md",
        "# Notes",
        title='"Notes"',
        type="concept",
    )

    report = run_migration(vault=vault, dry_run=True)

    assert report["folders_removed"] == ["comparisons"]
    assert report["folders_kept"] == [
        {"folder": "questions", "entries": ["NOTES.md"]}
    ]


def test_a_clean_vault_is_a_silent_no_op(tmp_path: Path, capsys) -> None:
    wiki = tmp_path / "wiki"
    _page(wiki / "concepts" / "Thing.md", "# Thing", title='"Thing"', type="concept")
    (wiki / "log.md").write_text("# Wiki Log\n", encoding="utf-8")
    before = _snapshot(tmp_path)

    report = run_migration(vault=tmp_path)
    print_report(report)

    assert report["changed"] is False
    assert report["errors"] == []
    assert _snapshot(tmp_path) == before
    out = capsys.readouterr().out
    assert out.strip() == "nothing to migrate: no page carries a removed kind"


def test_running_twice_is_idempotent(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    run_migration(vault=vault)
    after_first = _snapshot(vault)

    second = run_migration(vault=vault)

    assert second["changed"] is False
    assert _snapshot(vault) == after_first


# ─── log + report ──────────────────────────────────────────────────────


def test_a_changed_run_appends_one_log_entry(tmp_path: Path) -> None:
    vault = _vault(tmp_path)

    run_migration(vault=vault)

    log = (vault / "wiki" / "log.md").read_text(encoding="utf-8")
    entries = [ln for ln in log.splitlines() if ln.startswith("## [")]
    assert len(entries) == 1
    assert entries[0].endswith("] migrate | page kinds")


def test_report_names_every_touched_file(tmp_path: Path, capsys) -> None:
    vault = _vault(tmp_path)

    print_report(run_migration(vault=vault))

    out = capsys.readouterr().out
    for fragment in (
        "questions/CacheBudget.md",
        "comparisons/SyncVsSynth.md",
        "questions/_context.md",
        "comparisons/_context.md",
    ):
        assert fragment in out


def test_a_vault_without_a_wiki_is_an_error(tmp_path: Path) -> None:
    report = run_migration(vault=tmp_path)

    assert report["errors"] and "missing wiki dir" in report["errors"][0]
    assert report["changed"] is False


# ─── acceptance: the vault lints clean afterwards (R7) ─────────────────


@pytest.mark.parametrize("kind", REMOVED_KINDS)
def test_a_removed_kind_page_is_a_lint_error_before_the_migration(
    tmp_path: Path, kind: str
) -> None:
    wiki = tmp_path / "wiki"
    _page(wiki / f"{kind}s" / "Thing.md", "# Thing", title='"Thing"', type=kind)

    issues = run_all(load_pages(wiki), selected=["frontmatter_validity"])

    assert [i["severity"] for i in issues] == ["error"]


def test_the_migrated_vault_reports_no_invalid_type(tmp_path: Path) -> None:
    """R7: an existing wiki lints clean after upgrading, with the user
    deleting nothing by hand."""
    vault = _vault(tmp_path)
    wiki = vault / "wiki"
    before = run_all(load_pages(wiki), selected=["frontmatter_validity"])
    assert len(before) == 2

    run_migration(vault=vault)

    assert run_all(load_pages(wiki), selected=["frontmatter_validity"]) == []


# ─── CLI wiring ────────────────────────────────────────────────────────


def test_cli_runs_the_migration(tmp_path: Path, capsys) -> None:
    vault = _vault(tmp_path)
    args = build_parser().parse_args(
        ["migrate-page-kinds", "--vault", str(vault)]
    )

    assert args.func(args) == 0
    capsys.readouterr()
    assert (vault / "wiki" / "concepts" / "CacheBudget.md").is_file()


def test_cli_dry_run_writes_nothing(tmp_path: Path, capsys) -> None:
    vault = _vault(tmp_path)
    before = _snapshot(vault)
    args = build_parser().parse_args(
        ["migrate-page-kinds", "--vault", str(vault), "--dry-run"]
    )

    assert args.func(args) == 0
    capsys.readouterr()
    assert _snapshot(vault) == before


def test_cli_requires_a_vault(capsys) -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(["migrate-page-kinds"])
