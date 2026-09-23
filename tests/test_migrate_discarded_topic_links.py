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
