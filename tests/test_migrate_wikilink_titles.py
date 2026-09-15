"""Offline wikilink title migration (#259): library + tests (Slice 1).

# @spec: 251-findability-by-title
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from llmwiki.cli import build_parser
from llmwiki.migrate_wikilink_titles import (
    build_title_map,
    print_report,
    rewrite_wikilink_titles,
    run_migration,
)


def _page(path: Path, body: str, **meta: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{k}: {v}" for k, v in meta.items()]
    front = "\n".join(lines)
    path.write_text(f"---\n{front}\n---\n\n{body}\n", encoding="utf-8")


def _entity(wiki: Path, name: str, *, title: str | None = None) -> None:
    display = title if title is not None else name
    _page(
        wiki / "entities" / f"{name}.md",
        f"# {name}\n\n## Connections\n- [[nonexistent-fixture-target]]",
        title=f'"{display}"',
        type="entity",
        last_updated="2026-08-01",
    )


def _source(wiki: Path, slug: str, body: str) -> Path:
    path = wiki / "sources" / f"{slug}.md"
    _page(
        path,
        body,
        title=f'"{slug}"',
        type="source",
        date="2026-08-01",
    )
    return path


def _snapshot(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): p.read_text(encoding="utf-8")
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


# ─── title map ─────────────────────────────────────────────────────────


def test_build_title_map_from_wiki_scan(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    _entity(wiki, "OpenAI", title="OpenAI Inc.")
    _page(
        wiki / "concepts" / "RAG.md",
        "# RAG",
        title='"Retrieval Augmented Generation"',
        type="concept",
    )

    slug_to_title, _alias_map, slugs = build_title_map(wiki)

    assert "OpenAI" in slugs
    assert "RAG" in slugs
    assert slug_to_title["OpenAI"] == "OpenAI Inc."
    assert slug_to_title["RAG"] == "Retrieval Augmented Generation"


# ─── rewrite ───────────────────────────────────────────────────────────


def test_rewrite_bare_link_adds_title_display() -> None:
    text = "See [[OpenAI]] for details."
    slug_to_title = {"OpenAI": "OpenAI Inc."}
    new_text, counters = rewrite_wikilink_titles(
        text,
        slug_to_title=slug_to_title,
        alias_map={},
        slugs={"OpenAI"},
    )

    assert counters["links_rewritten"] == 1
    assert new_text == "See [[OpenAI|OpenAI Inc.]] for details."


def test_rewrite_preserves_section_anchor() -> None:
    text = "Jump to [[OpenAI#History]] here."
    slug_to_title = {"OpenAI": "OpenAI Inc."}
    new_text, counters = rewrite_wikilink_titles(
        text,
        slug_to_title=slug_to_title,
        alias_map={},
        slugs={"OpenAI"},
    )

    assert counters["links_rewritten"] == 1
    assert new_text == "Jump to [[OpenAI#History|OpenAI Inc.]] here."


def test_second_run_skips_display_pipe_links() -> None:
    text = "Already [[OpenAI|OpenAI Inc.]] titled."
    slug_to_title = {"OpenAI": "OpenAI Inc."}
    new_text, counters = rewrite_wikilink_titles(
        text,
        slug_to_title=slug_to_title,
        alias_map={},
        slugs={"OpenAI"},
    )

    assert new_text == text
    assert counters["links_skipped_display"] == 1
    assert counters["links_rewritten"] == 0


def test_skip_unresolved_link() -> None:
    text = "Missing [[NoSuchPage]] stays."
    new_text, counters = rewrite_wikilink_titles(
        text,
        slug_to_title={},
        alias_map={},
        slugs=set(),
    )

    assert new_text == text
    assert counters["links_skipped_unresolved"] == 1


def test_skip_alias_only_non_bare_anchor(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    _page(
        wiki / "entities" / "Survivor.md",
        "## Aliases\n- [[MergedAway]]\n",
        title='"Survivor Entity"',
        type="entity",
    )
    slug_to_title, alias_map, slugs = build_title_map(wiki)
    text = "Old name [[MergedAway]] still works."

    new_text, counters = rewrite_wikilink_titles(
        text,
        slug_to_title=slug_to_title,
        alias_map=alias_map,
        slugs=slugs,
    )

    assert new_text == text
    assert counters["links_skipped_non_bare"] == 1


def test_rewrite_case_variant_normalizes_to_canonical_slug(tmp_path: Path) -> None:
    """[[LLM-Wiki]] matches page llm-wiki via shared norm_page_key (#262)."""
    wiki = tmp_path / "wiki"
    _page(
        wiki / "projects" / "llm-wiki.md",
        "# llm-wiki\n",
        title='"llm-wiki"',
        type="project",
    )
    slug_to_title, alias_map, slugs = build_title_map(wiki)
    text = "- [[LLM-Wiki]] — document tagged for wiki addition\n"

    new_text, counters = rewrite_wikilink_titles(
        text,
        slug_to_title=slug_to_title,
        alias_map=alias_map,
        slugs=slugs,
    )

    assert counters["links_rewritten"] == 1
    assert new_text == "- [[llm-wiki|llm-wiki]] — document tagged for wiki addition\n"


def test_rewrite_case_variant_preserves_section_anchor(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    _page(
        wiki / "projects" / "llm-wiki.md",
        "# llm-wiki\n",
        title='"LLM Wiki Project"',
        type="project",
    )
    slug_to_title, alias_map, slugs = build_title_map(wiki)

    new_text, counters = rewrite_wikilink_titles(
        "See [[LLM-Wiki#Setup]]",
        slug_to_title=slug_to_title,
        alias_map=alias_map,
        slugs=slugs,
    )

    assert counters["links_rewritten"] == 1
    assert new_text == "See [[llm-wiki#Setup|LLM Wiki Project]]"


def test_rewrite_punct_variant_space_to_hyphen_slug(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    _entity(wiki, "OpenAI", title="OpenAI Inc.")
    slug_to_title, alias_map, slugs = build_title_map(wiki)

    new_text, counters = rewrite_wikilink_titles(
        "[[Open AI]]",
        slug_to_title=slug_to_title,
        alias_map=alias_map,
        slugs=slugs,
    )

    assert counters["links_rewritten"] == 1
    assert new_text == "[[OpenAI|OpenAI Inc.]]"


def test_ambiguous_norm_page_key_stays_unresolved(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    _entity(wiki, "OpenAI", title="OpenAI Inc.")
    _page(
        wiki / "concepts" / "Open-AI.md",
        "# Open-AI\n",
        title='"Open AI concept"',
        type="concept",
    )
    slug_to_title, alias_map, slugs = build_title_map(wiki)

    new_text, counters = rewrite_wikilink_titles(
        "[[openai]]",
        slug_to_title=slug_to_title,
        alias_map=alias_map,
        slugs=slugs,
    )

    assert new_text == "[[openai]]"
    assert counters["links_skipped_unresolved"] == 1


def test_skip_unsafe_title_with_pipe(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    _entity(wiki, "BadTitle", title="Foo | Bar")
    slug_to_title, alias_map, slugs = build_title_map(wiki)
    text = "Link [[BadTitle]] here."

    new_text, counters = rewrite_wikilink_titles(
        text,
        slug_to_title=slug_to_title,
        alias_map=alias_map,
        slugs=slugs,
    )

    assert new_text == text
    assert counters["links_skipped_unsafe_title"] == 1


def test_skip_unsafe_title_with_closing_brackets(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    _entity(wiki, "Broken", title='Say "hello]]world"')
    slug_to_title, alias_map, slugs = build_title_map(wiki)

    new_text, counters = rewrite_wikilink_titles(
        "[[Broken]]",
        slug_to_title=slug_to_title,
        alias_map=alias_map,
        slugs=slugs,
    )

    assert new_text == "[[Broken]]"
    assert counters["links_skipped_unsafe_title"] == 1


def test_skip_empty_title(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    _page(
        wiki / "entities" / "EmptyTitle.md",
        "# Empty",
        title='""',
        type="entity",
    )
    slug_to_title, alias_map, slugs = build_title_map(wiki)
    # scan_pages falls back to stem when title empty — force empty in rewrite map
    slug_to_title["EmptyTitle"] = "   "

    new_text, counters = rewrite_wikilink_titles(
        "[[EmptyTitle]]",
        slug_to_title=slug_to_title,
        alias_map=alias_map,
        slugs=slugs,
    )

    assert new_text == "[[EmptyTitle]]"
    assert counters["links_skipped_unsafe_title"] == 1


# ─── run_migration ─────────────────────────────────────────────────────


def test_run_migration_rewrites_wiki_pages(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    _entity(wiki, "OpenAI", title="OpenAI Inc.")
    page = _source(wiki, "demo", "Mention [[OpenAI]] in prose.\n")

    report = run_migration(vault=tmp_path)

    after = page.read_text(encoding="utf-8")
    assert "[[OpenAI|OpenAI Inc.]]" in after
    assert report["links_rewritten"] == 1
    assert report["pages_changed"] == 1
    assert report["changed"] is True


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    _entity(wiki, "OpenAI", title="OpenAI Inc.")
    _source(wiki, "demo", "Mention [[OpenAI]] in prose.\n")
    before = _snapshot(tmp_path)

    report = run_migration(vault=tmp_path, dry_run=True)

    assert report["changed"] is True
    assert report["pages_changed"] == 1
    assert report["links_rewritten"] == 1
    assert _snapshot(tmp_path) == before


def test_run_migration_never_touches_raw(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    raw = tmp_path / "raw" / "sessions"
    raw.mkdir(parents=True)
    raw_file = raw / "2026-08-01-demo.md"
    raw_before = "---\ntitle: demo\n---\n\n[[OpenAI]]\n"
    raw_file.write_text(raw_before, encoding="utf-8")
    _entity(wiki, "OpenAI", title="OpenAI Inc.")
    _source(wiki, "demo", "Mention [[OpenAI]] in prose.\n")

    run_migration(vault=tmp_path)

    assert raw_file.read_text(encoding="utf-8") == raw_before


def test_nothing_to_migrate_message(tmp_path: Path, capsys) -> None:
    wiki = tmp_path / "wiki"
    _entity(wiki, "OpenAI", title="OpenAI Inc.")
    _source(wiki, "demo", "Already [[OpenAI|OpenAI Inc.]] titled.\n")

    report = run_migration(vault=tmp_path)
    print_report(report)

    out = capsys.readouterr().out
    assert "nothing to migrate" in out
    assert report["changed"] is False


def test_write_failure_rolls_back_report_counters(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wiki = tmp_path / "wiki"
    _entity(wiki, "OpenAI", title="OpenAI Inc.")
    page = _source(wiki, "demo", "Mention [[OpenAI]] in prose.\n")
    before = page.read_text(encoding="utf-8")
    real_write = Path.write_text

    def _failing_write(self: Path, data: object, *args: object, **kwargs: object) -> None:
        if self == page:
            raise OSError("simulated write failure")
        return real_write(self, data, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "write_text", _failing_write)

    report = run_migration(vault=tmp_path)

    assert page.read_text(encoding="utf-8") == before
    assert report["errors"]
    assert report["pages_changed"] == 0
    assert report["links_rewritten"] == 0


def test_migration_module_has_no_synth_backend_imports() -> None:
    """Migration must not pull HTTP or LLM synthesis backends."""
    source = Path("llmwiki/migrate_wikilink_titles.py").read_text(encoding="utf-8")
    forbidden = (
        r"llmwiki\.synth\.ollama",
        r"llmwiki\.synth\.claude",
        r"llmwiki\.synth\.pipeline",
        r"llmwiki\.backends",
        r"\bhttpx\b",
        r"\burllib\b",
        r"\brequests\b",
        r"\bopenai\b",
        r"\banthropic\b",
    )
    for pattern in forbidden:
        assert not re.search(pattern, source), f"forbidden import pattern: {pattern}"


# ─── CLI wiring ────────────────────────────────────────────────────────


def test_cli_runs_the_migration(tmp_path: Path, capsys) -> None:
    wiki = tmp_path / "wiki"
    _entity(wiki, "OpenAI", title="OpenAI Inc.")
    page = _source(wiki, "demo", "Mention [[OpenAI]] in prose.\n")
    args = build_parser().parse_args(
        ["migrate", "wikilink-titles", "--vault", str(tmp_path)]
    )

    assert args.func(args) == 0
    capsys.readouterr()
    assert "[[OpenAI|OpenAI Inc.]]" in page.read_text(encoding="utf-8")


def test_cli_dry_run_writes_nothing(tmp_path: Path, capsys) -> None:
    wiki = tmp_path / "wiki"
    _entity(wiki, "OpenAI", title="OpenAI Inc.")
    _source(wiki, "demo", "Mention [[OpenAI]] in prose.\n")
    before = _snapshot(tmp_path)
    args = build_parser().parse_args(
        ["migrate", "wikilink-titles", "--vault", str(tmp_path), "--dry-run"]
    )

    assert args.func(args) == 0
    capsys.readouterr()
    assert _snapshot(tmp_path) == before


def test_cli_requires_a_vault() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(["migrate", "wikilink-titles"])
