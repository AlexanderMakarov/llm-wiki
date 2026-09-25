"""Offline cleanup of links to discarded candidates (#282).

# @spec: 282-discarded-topic-links
"""

from __future__ import annotations

from pathlib import Path

import pytest

from llmwiki import candidates as candidates_mod
from llmwiki.candidates import _find_candidate, list_candidates  # noqa: PLC2701
from llmwiki.candidates_harvest import harvest_targets, write_stubs
from llmwiki.cli import build_parser
from llmwiki.lint import LintOptions, load_pages
from llmwiki.lint.rules import LinkIntegrity
from llmwiki.migrate_discarded_topic_links import (
    parse_redirects,
    print_report,
    run_migration,
)
from llmwiki.synth.base import BaseSynthesizer
from llmwiki.wikilinks import build_page_alias_map, resolve_wikilink_target


def _source(wiki: Path, slug: str, body: str) -> None:
    path = wiki / "sources" / f"{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f'---\ntitle: "{slug}"\ntype: source\n---\n\n{body}\n', encoding="utf-8")


def _archive_without_rewrite(wiki: Path, name: str) -> None:
    """Archive a stub the way discard did before #282: move it, leave links."""
    candidates_mod._archive_candidate(  # noqa: SLF001
        _find_candidate(name, wiki, None), wiki, reason="noise",
    )


def _broken(wiki: Path) -> set[str]:
    rule = LinkIntegrity()
    rule.options = LintOptions(min_refs=1)
    return {
        i["message"].removeprefix("broken wikilink [[").removesuffix("]]")
        for i in rule.run(load_pages(wiki))
    }


def _snapshot(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): p.read_text(encoding="utf-8")
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


@pytest.fixture
def vault(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A vault whose discarded candidates still have links pointing at them.

    Also fails loudly on any synthesis call: the migration is offline.
    """
    def _no_llm(*_a, **_k):
        raise AssertionError("migration must not call a synthesis backend")

    for method in ("synthesize_source_page", "synthesize_key_facts", "is_available"):
        monkeypatch.setattr(BaseSynthesizer, method, _no_llm)

    wiki = tmp_path / "wiki"
    _source(wiki, "a", "Uses [[Junk]], [[Old Name]] and [[Ghost]].")
    _source(wiki, "b", "Mentions [[junk|the junk]] and [[old name]].")
    (wiki / "concepts").mkdir(parents=True)
    (wiki / "concepts" / "Proper.md").write_text(
        '---\ntitle: "Proper"\ntype: concept\n---\n\n# Proper\n', encoding="utf-8",
    )
    write_stubs(wiki, harvest_targets(wiki, min_refs=2))
    _archive_without_rewrite(wiki, "Junk")
    _archive_without_rewrite(wiki, "Old Name")
    return tmp_path


def test_migration_leaves_only_truly_broken_links(vault: Path) -> None:
    """# @layer: integration"""
    wiki = vault / "wiki"
    assert _broken(wiki) == {"Junk", "junk", "Old Name", "old name", "Ghost"}

    report = run_migration(vault=vault)

    assert report["errors"] == []
    assert report["unlinked"] == {"Junk": 2, "Old Name": 2}
    assert sorted(report["changed_pages"]) == ["sources/a.md", "sources/b.md"]
    assert _broken(wiki) == {"Ghost"}
    text = (wiki / "sources" / "b.md").read_text(encoding="utf-8")
    assert "Mentions the junk and old name." in text


def test_dry_run_writes_nothing(vault: Path) -> None:
    """# @layer: integration"""
    before = _snapshot(vault)
    report = run_migration(vault=vault, dry_run=True)
    assert report["changed"] is True
    assert report["unlinked"] == {"Junk": 2, "Old Name": 2}
    assert _snapshot(vault) == before


def test_second_run_changes_nothing(vault: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """# @layer: integration"""
    run_migration(vault=vault, redirects={"Old Name": "Proper"})
    after_first = _snapshot(vault)

    report = run_migration(vault=vault, redirects={"Old Name": "Proper"})

    assert report["changed"] is False
    assert report["errors"] == []
    assert _snapshot(vault) == after_first
    # The redirect is a no-op now, and says so rather than vanishing.
    assert len(report["skipped"]) == 1
    print_report(report)
    assert "no redirect was needed" in capsys.readouterr().out


def test_a_redirect_a_live_page_already_answers_is_reported(vault: Path) -> None:
    """A dropped ``--redirect`` would look like it applied. # @layer: unit  # @spec: 282-discarded-topic-links"""
    wiki = vault / "wiki"
    (wiki / "concepts" / "Junk.md").write_text(
        '---\ntitle: "Junk"\ntype: concept\n---\n\n# Junk\n', encoding="utf-8",
    )

    report = run_migration(vault=vault, redirects={"Junk": "Proper"})

    assert report["errors"] == []
    assert report["redirected"] == {}
    assert report["skipped"] == [
        "--redirect 'Junk': a live page already answers to that name, so its "
        "links resolve and no redirect was needed"
    ]
    assert "[[Junk]]" in (wiki / "sources" / "a.md").read_text(encoding="utf-8")


def test_a_bad_redirect_writes_nothing_at_all(vault: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Validation comes before the first write. # @layer: integration  # @spec: 282-discarded-topic-links"""
    before = _snapshot(vault)

    report = run_migration(
        vault=vault, redirects={"Old Name": "Proper", "Junk": "Missing"},
    )

    assert report["aborted"] is True
    assert report["errors"] == ["--redirect 'Junk': redirect target not found: "
                               "'Missing' is not an existing page under "
                               f"{vault / 'wiki'} (candidates and archive do not count)"]
    assert report["changed"] is False
    assert _snapshot(vault) == before
    print_report(report)
    assert "nothing was written" in capsys.readouterr().out


def test_cli_bad_redirect_exits_non_zero_without_migrating(vault: Path) -> None:
    before = _snapshot(vault)
    args = build_parser().parse_args([
        "migrate", "discarded-topic-links", "--vault", str(vault),
        "--redirect", "Junk=Missing",
    ])
    assert args.func(args) == 1
    assert _snapshot(vault) == before


def test_unreadable_pages_are_reported_not_skipped_in_silence(vault: Path) -> None:
    """# @layer: integration  # @spec: 282-discarded-topic-links"""
    wiki = vault / "wiki"
    (wiki / "sources" / "broken.md").write_bytes(
        b'---\ntitle: "bad"\n---\n\n\xff\xfe Uses [[Junk]].\n'
    )

    report = run_migration(vault=vault)

    assert report["errors"]
    assert all(err.startswith("sources/broken.md:") for err in report["errors"])
    assert report["unlinked"] == {"Junk": 2, "Old Name": 2}
    args = build_parser().parse_args([
        "migrate", "discarded-topic-links", "--vault", str(vault),
    ])
    assert args.func(args) == 1


def test_redirect_target_keeps_its_own_mention_as_text(vault: Path) -> None:
    """The target must not end up linking to itself. # @layer: integration  # @spec: 282-discarded-topic-links"""
    wiki = vault / "wiki"
    target = wiki / "concepts" / "Proper.md"
    target.write_text(
        '---\ntitle: "Proper"\ntype: concept\n---\n\n# Proper\n\n'
        "## Connections\n- [[Old Name]] — the old spelling\n",
        encoding="utf-8",
    )

    run_migration(vault=vault, redirects={"Old Name": "Proper"})

    body = target.read_text(encoding="utf-8")
    assert "- Old Name — the old spelling" in body
    assert "[[Proper|Old Name]]" not in body
    assert build_page_alias_map({"Proper": body}) == {"Old Name": "Proper"}


def test_redirect_points_links_at_page_and_records_alias(vault: Path) -> None:
    """# @layer: integration"""
    wiki = vault / "wiki"

    report = run_migration(vault=vault, redirects={"old-name": "proper"})

    assert report["redirected"] == {"Old Name -> Proper": 2}
    assert report["unlinked"] == {"Junk": 2}
    assert report["aliases_recorded"] == ["Old Name -> concepts/Proper.md"]
    text = (wiki / "sources" / "a.md").read_text(encoding="utf-8")
    assert "[[Proper|Old Name]]" in text
    body = (wiki / "concepts" / "Proper.md").read_text(encoding="utf-8")
    alias_map = build_page_alias_map({"Proper": body})
    assert resolve_wikilink_target("old name", {"Proper"}, alias_map) == "Proper"
    assert "- Old Name — redirected " in body
    assert "(2 source pages)" in body
    assert _broken(wiki) == {"Ghost"}


def test_redirect_errors_are_reported(vault: Path) -> None:
    report = run_migration(
        vault=vault, redirects={"Nope": "Proper", "Junk": "Missing"},
    )
    assert len(report["errors"]) == 2
    # A name whose redirect failed is left linked, not silently unlinked.
    assert "Junk" not in report["unlinked"]


def test_nested_slash_stub_is_flattened(tmp_path: Path) -> None:
    """A stub the old ``write_stubs`` filed under ``A/`` moves to its flat path."""
    wiki = tmp_path / "wiki"
    nested = wiki / "candidates" / "entities" / "A" / "B thing.md"
    nested.parent.mkdir(parents=True)
    nested.write_text('---\ntitle: "A/B thing"\ntype: entity\n---\n\n# A/B thing\n',
                      encoding="utf-8")
    clash = wiki / "candidates" / "concepts" / "C" / "D.md"
    clash.parent.mkdir(parents=True)
    clash.write_text('---\ntitle: "C/D"\n---\n', encoding="utf-8")
    (wiki / "candidates" / "concepts" / "C-D.md").write_text("# kept\n", encoding="utf-8")

    dry = run_migration(vault=tmp_path, dry_run=True)
    assert dry["flattened"] == [
        "candidates/entities/A/B thing.md -> candidates/entities/A-B thing.md"
    ]
    assert nested.is_file()

    report = run_migration(vault=tmp_path)

    assert not (wiki / "candidates" / "entities" / "A").exists()
    assert (wiki / "candidates" / "entities" / "A-B thing.md").is_file()
    assert report["conflicts"] == [
        "candidates/concepts/C/D.md -> candidates/concepts/C-D.md (already exists)"
    ]
    assert clash.is_file()
    assert "A/B thing" in [c["title"] for c in list_candidates(wiki)]


def test_parse_redirects() -> None:
    assert parse_redirects(["Old Name=Proper", "a=b=c"]) == {"Old Name": "Proper", "a=b": "c"}
    with pytest.raises(ValueError):
        parse_redirects(["no-equals"])


def test_cli_registration(vault: Path) -> None:
    args = build_parser().parse_args([
        "migrate", "discarded-topic-links", "--vault", str(vault), "--dry-run",
        "--redirect", "Old Name=Proper",
    ])
    assert args.func(args) == 0
    assert "[[Old Name]]" in (vault / "wiki" / "sources" / "a.md").read_text(encoding="utf-8")
    with pytest.raises(SystemExit):
        build_parser().parse_args(["migrate", "discarded-topic-links"])


# ─── merged names whose survivor stopped answering to them (#282) ──────

_MERGED = "Tailnet"
_SURVIVOR = "Tailscale"
_RENAMED = "Tailscale-Overlay"


def _cli(vault: Path, *flags: str) -> int:
    args = build_parser().parse_args([
        "migrate", "discarded-topic-links", "--vault", str(vault), *flags,
    ])
    return args.func(args)


def _nested_stub(wiki: Path) -> Path:
    """A stub an older ``write_stubs`` filed under a subfolder of its kind."""
    nested = wiki / "candidates" / "entities" / "A" / "B thing.md"
    nested.parent.mkdir(parents=True, exist_ok=True)
    nested.write_text('---\ntitle: "A/B thing"\ntype: entity\n---\n\n# A/B thing\n',
                      encoding="utf-8")
    return nested


@pytest.fixture
def merged_vault(vault: Path) -> Path:
    """``vault`` plus a candidate a reviewer really merged into a live page."""
    wiki = vault / "wiki"
    _source(wiki, "notes-one", f"Runs on [[{_MERGED}]] here.")
    _source(wiki, "notes-two", "Runs on [[tailnet|the overlay]] there.")
    (wiki / "entities").mkdir(parents=True, exist_ok=True)
    (wiki / "entities" / f"{_SURVIVOR}.md").write_text(
        f'---\ntitle: "{_SURVIVOR}"\ntype: entity\n---\n\n# {_SURVIVOR}\n',
        encoding="utf-8",
    )
    write_stubs(wiki, harvest_targets(wiki, min_refs=2))
    candidates_mod.merge(_MERGED, wiki, into_slug=_SURVIVOR)
    return vault


def _refile_survivor_losing_its_alias(wiki: Path) -> Path:
    """Put the survivor where a pre-#139 merge plus a rename leaves it.

    Merges older than the alias mechanism recorded no ``## Aliases`` entry, so
    once the page is renamed nothing on disk but the reason file still ties the
    merged-away name to it.
    """
    page = wiki / "entities" / f"{_SURVIVOR}.md"
    kept, _, _ = page.read_text(encoding="utf-8").partition("## Aliases")
    dest = page.with_name(f"{_RENAMED}.md")
    dest.write_text(kept.rstrip() + "\n", encoding="utf-8")
    page.unlink()
    return dest


def test_a_merge_whose_survivor_still_answers_is_left_alone(merged_vault: Path) -> None:
    """The alias resolves the links, so there is nothing to report.

    # @layer: integration  # @spec: 282-discarded-topic-links
    """
    wiki = merged_vault / "wiki"

    report = run_migration(vault=merged_vault)

    assert report["recorded_merges"] == []
    assert report["merges_skipped"] is False
    assert report["unlinked"] == {"Junk": 2, "Old Name": 2}
    assert f"[[{_MERGED}]]" in (wiki / "sources" / "notes-one.md").read_text(
        encoding="utf-8")
    assert _cli(merged_vault) == 0


def test_a_merged_name_whose_survivor_was_refiled_is_reported_not_unlinked(
    merged_vault: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """The reason file is the only record of where those links belong.

    # @layer: integration  # @spec: 282-discarded-topic-links
    """
    wiki = merged_vault / "wiki"
    _refile_survivor_losing_its_alias(wiki)
    nested = _nested_stub(wiki)

    report = run_migration(vault=merged_vault)

    assert report["merges_skipped"] is True
    assert report["recorded_merges"] == [{
        "key": "tailnet",
        "name": _MERGED,
        "merged_into": _SURVIVOR,
        "suggestion": _RENAMED,
        "links": 2,
    }]
    # Left linked, while the run's other work went through.
    assert f"[[{_MERGED}]]" in (wiki / "sources" / "notes-one.md").read_text(
        encoding="utf-8")
    assert report["unlinked"] == {"Junk": 2, "Old Name": 2}
    assert "[[Junk]]" not in (wiki / "sources" / "a.md").read_text(encoding="utf-8")
    assert not nested.exists()
    assert (wiki / "candidates" / "entities" / "A-B thing.md").is_file()

    print_report(report)
    out = capsys.readouterr().out
    assert f'--redirect "{_MERGED}={_RENAMED}"' in out
    assert "--force" in out
    assert _cli(merged_vault) == 1


def test_the_suggested_redirect_lands_the_links_on_the_survivor(
    merged_vault: Path,
) -> None:
    """# @layer: integration  # @spec: 282-discarded-topic-links"""
    wiki = merged_vault / "wiki"
    survivor = _refile_survivor_losing_its_alias(wiki)

    assert _cli(merged_vault, "--redirect", f"{_MERGED}={_RENAMED}") == 0

    text = (wiki / "sources" / "notes-one.md").read_text(encoding="utf-8")
    assert f"[[{_RENAMED}|{_MERGED}]]" in text
    body = survivor.read_text(encoding="utf-8")
    alias_map = build_page_alias_map({_RENAMED: body})
    assert resolve_wikilink_target("tailnet", {_RENAMED}, alias_map) == _RENAMED
    report = run_migration(vault=merged_vault)
    assert report["recorded_merges"] == []


def test_force_unlinks_a_recorded_merge_like_a_dismissal(
    merged_vault: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """# @layer: integration  # @spec: 282-discarded-topic-links"""
    wiki = merged_vault / "wiki"
    _refile_survivor_losing_its_alias(wiki)

    assert _cli(merged_vault, "--force") == 0

    text = (wiki / "sources" / "notes-one.md").read_text(encoding="utf-8")
    assert f"[[{_MERGED}]]" not in text
    assert f"Runs on {_MERGED} here." in text
    out = capsys.readouterr().out
    assert "merged, unlinked anyway" in out
    assert "--redirect" not in out


def test_dry_run_shows_the_recorded_merge_partition_and_writes_nothing(
    merged_vault: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """# @layer: integration  # @spec: 282-discarded-topic-links"""
    _refile_survivor_losing_its_alias(merged_vault / "wiki")
    before = _snapshot(merged_vault)

    report = run_migration(vault=merged_vault, dry_run=True)

    assert report["merges_skipped"] is True
    assert [e["name"] for e in report["recorded_merges"]] == [_MERGED]
    assert report["unlinked"] == {"Junk": 2, "Old Name": 2}
    assert _snapshot(merged_vault) == before
    print_report(report)
    out = capsys.readouterr().out
    assert f'--redirect "{_MERGED}={_RENAMED}"' in out
    assert "dry run: nothing was written" in out
    assert _cli(merged_vault, "--dry-run") == 1


def test_a_recorded_merge_with_no_matching_page_asks_for_one(
    merged_vault: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """# @layer: integration  # @spec: 282-discarded-topic-links"""
    (merged_vault / "wiki" / "entities" / f"{_SURVIVOR}.md").unlink()

    report = run_migration(vault=merged_vault)

    assert [e["suggestion"] for e in report["recorded_merges"]] == [None]
    print_report(report)
    out = capsys.readouterr().out
    assert f'--redirect "{_MERGED}=<page>"' in out


def test_a_recorded_merge_with_zero_links_is_not_actionable(
    merged_vault: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """A merge with nothing to rewrite needs no operator decision (#282).

    Regression: the merge guard used to count every recorded merge toward
    ``merges_skipped`` regardless of link count, so a name with zero links
    still tripped the non-zero exit forever.

    # @layer: integration  # @spec: 282-discarded-topic-links
    """
    wiki = merged_vault / "wiki"
    _refile_survivor_losing_its_alias(wiki)
    for slug, needle, replacement in (
        ("notes-one", f"[[{_MERGED}]]", _MERGED),
        ("notes-two", "[[tailnet|the overlay]]", "the overlay"),
    ):
        path = wiki / "sources" / f"{slug}.md"
        path.write_text(
            path.read_text(encoding="utf-8").replace(needle, replacement),
            encoding="utf-8",
        )

    report = run_migration(vault=merged_vault)

    assert report["recorded_merges"] == []
    assert report["merges_skipped"] is False
    # The base vault's own dismissals still went through.
    assert report["unlinked"] == {"Junk": 2, "Old Name": 2}
    assert f"Runs on {_MERGED} here." in (
        wiki / "sources" / "notes-one.md"
    ).read_text(encoding="utf-8")
    print_report(report)
    assert "merged" not in capsys.readouterr().out
    assert _cli(merged_vault) == 0


def test_zero_link_merge_does_not_hide_a_linked_one(
    vault: Path,
) -> None:
    """Mixing a quiet and a reportable merge only surfaces the reportable one.

    # @layer: integration  # @spec: 282-discarded-topic-links
    """
    wiki = vault / "wiki"
    wiki.joinpath("entities").mkdir(parents=True, exist_ok=True)

    # A merge whose links disappear afterward: no decision to make.
    _source(wiki, "quiet-one", f"Runs on [[{_MERGED}]] here.")
    (wiki / "entities" / f"{_SURVIVOR}.md").write_text(
        f'---\ntitle: "{_SURVIVOR}"\ntype: entity\n---\n\n# {_SURVIVOR}\n',
        encoding="utf-8",
    )
    write_stubs(wiki, harvest_targets(wiki, min_refs=1))
    candidates_mod.merge(_MERGED, wiki, into_slug=_SURVIVOR)
    _refile_survivor_losing_its_alias(wiki)
    quiet_path = wiki / "sources" / "quiet-one.md"
    quiet_path.write_text(
        quiet_path.read_text(encoding="utf-8").replace(f"[[{_MERGED}]]", _MERGED),
        encoding="utf-8",
    )

    # A second merge whose links are still there: needs an operator decision.
    loud_merged, loud_survivor = "Skylink", "Meshnet"
    _source(wiki, "loud-one", f"Runs on [[{loud_merged}]] here.")
    (wiki / "entities" / f"{loud_survivor}.md").write_text(
        f'---\ntitle: "{loud_survivor}"\ntype: entity\n---\n\n# {loud_survivor}\n',
        encoding="utf-8",
    )
    write_stubs(wiki, harvest_targets(wiki, min_refs=1))
    candidates_mod.merge(loud_merged, wiki, into_slug=loud_survivor)
    loud_page = wiki / "entities" / f"{loud_survivor}.md"
    kept, _, _ = loud_page.read_text(encoding="utf-8").partition("## Aliases")
    loud_page.with_name(f"{loud_survivor}-Core.md").write_text(
        kept.rstrip() + "\n", encoding="utf-8",
    )
    loud_page.unlink()

    report = run_migration(vault=vault)

    assert [entry["name"] for entry in report["recorded_merges"]] == [loud_merged]
    assert report["merges_skipped"] is True
    assert _cli(vault) == 1


def test_redirect_then_rerun_converges_to_a_clean_report(
    merged_vault: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """Applying the suggested ``--redirect`` leaves nothing pending on a re-run.

    Regression for the merge guard trapping every future run at exit 1 even
    after the operator did everything the report asked for (#282).

    # @layer: integration  # @spec: 282-discarded-topic-links
    """
    wiki = merged_vault / "wiki"
    _refile_survivor_losing_its_alias(wiki)

    assert _cli(merged_vault, "--redirect", f"{_MERGED}={_RENAMED}") == 0
    capsys.readouterr()

    assert _cli(merged_vault) == 0
    out = capsys.readouterr().out
    assert "merged" not in out
    report = run_migration(vault=merged_vault)
    assert report["recorded_merges"] == []
    assert report["merges_skipped"] is False


@pytest.mark.parametrize("target", ["Nord — Star", "A/B Thing"])
def test_the_reader_round_trips_a_punctuated_merge_target(
    vault: Path, target: str,
) -> None:
    """A merge target with an em dash or a slash comes back verbatim.

    # @layer: unit  # @spec: 282-discarded-topic-links
    """
    wiki = vault / "wiki"
    _source(wiki, "notes-one", f"Uses [[{_MERGED}]].")
    _source(wiki, "notes-two", f"Uses [[{_MERGED}]] too.")
    page = wiki / "entities" / candidates_mod.candidate_filename(target)
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(f'---\ntitle: "{target}"\ntype: entity\n---\n\n# {target}\n',
                    encoding="utf-8")
    write_stubs(wiki, harvest_targets(wiki, min_refs=2))

    candidates_mod.merge(_MERGED, wiki, into_slug=target)

    assert candidates_mod.merged_intents(wiki) == {"tailnet": target}
