"""Tests for ``llmwiki/tags.py`` + ``llmwiki tag`` CLI + G-16 lint rule.

Covers:
* Frontmatter parsing: inline list, block list, mixed, absent, malformed.
* collect_tags: walks wiki/, skips archive + underscore files.
* count_tags aggregate.
* add_tag_to_page: new page (seeds frontmatter), existing field (append),
  different field (creates field), idempotent re-add, missing page,
  invalid field.
* rename_tag: inline + block, dry-run, no-op, boundary (substring safety).
* near_duplicate_tags: threshold, case-insensitive, no pair → empty,
  sort order deterministic.
* convention_violations: project with `tags:` → flag,
  source with `topics:` → flag, both fields OK.
* format_tag_table rendering.
* CLI subprocess: list / add / rename --dry-run / check / convention.
* Lint rule wiring: registry count bumped to 14, rule name present.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from textwrap import dedent

import pytest

from llmwiki import tags as t

REPO_ROOT = Path(__file__).resolve().parents[1]


def _run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "llmwiki", *args],
        capture_output=True,
        text=True,
        check=False,
    )


# ─── fixture helpers ─────────────────────────────────────────────────────


def _mk_wiki(tmp_path: Path, **pages: str) -> Path:
    """Seed a mini-wiki with the given pages (rel → body with FM)."""
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    for rel, content in pages.items():
        p = wiki / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    return wiki


def _source_page(tags_str: str = "[a, b]", topics_str: str = "") -> str:
    fm_lines = ['title: "Example"', "type: source"]
    if tags_str:
        fm_lines.append(f"tags: {tags_str}")
    if topics_str:
        fm_lines.append(f"topics: {topics_str}")
    return "---\n" + "\n".join(fm_lines) + "\n---\n\n# Body\n"


# ─── frontmatter parsing ─────────────────────────────────────────────────


def test_iter_tags_inline_list():
    fm = 'title: "X"\ntags: [alpha, beta, gamma]'
    out = t._iter_tags_in_frontmatter(fm)
    assert out == [("tags", ["alpha", "beta", "gamma"])]


def test_iter_tags_block_list():
    fm = dedent(
        """\
        title: "X"
        tags:
          - alpha
          - beta
        """
    )
    out = t._iter_tags_in_frontmatter(fm)
    assert out == [("tags", ["alpha", "beta"])]


def test_iter_tags_strips_quotes():
    fm = 'tags: ["alpha", "beta"]'
    out = t._iter_tags_in_frontmatter(fm)
    assert out == [("tags", ["alpha", "beta"])]


def test_iter_tags_handles_both_fields():
    fm = 'tags: [a, b]\ntopics: [x, y]'
    out = t._iter_tags_in_frontmatter(fm)
    assert len(out) == 2
    keys = {k for k, _ in out}
    assert keys == {"tags", "topics"}


def test_iter_tags_empty_string_skipped():
    out = t._iter_tags_in_frontmatter("title: X")
    assert out == []


def test_iter_tags_malformed_line_ignored():
    fm = 'tags: not-a-list'
    out = t._iter_tags_in_frontmatter(fm)
    assert out == []


# ─── collect_tags + count_tags ───────────────────────────────────────────


def test_collect_tags_walks_wiki(tmp_path):
    wiki = _mk_wiki(
        tmp_path,
        **{
            "sources/a.md": _source_page("[one, two]"),
            "sources/b.md": _source_page("[two, three]"),
        },
    )
    entries = t.collect_tags(wiki)
    tag_set = {e.tag for e in entries}
    assert tag_set == {"one", "two", "three"}
    assert all(e.field == "tags" for e in entries)


def test_collect_tags_skips_underscore_and_archive(tmp_path):
    wiki = _mk_wiki(
        tmp_path,
        **{
            "sources/a.md": _source_page("[keeper]"),
            "_context.md": _source_page("[skip-me]"),
            "archive/old.md": _source_page("[skip-me-too]"),
        },
    )
    entries = t.collect_tags(wiki)
    tag_names = {e.tag for e in entries}
    assert "keeper" in tag_names
    assert "skip-me" not in tag_names
    assert "skip-me-too" not in tag_names


def test_collect_tags_empty_wiki(tmp_path):
    wiki = tmp_path / "empty-wiki"
    wiki.mkdir()
    assert t.collect_tags(wiki) == []


def test_collect_tags_missing_wiki(tmp_path):
    assert t.collect_tags(tmp_path / "nope") == []


def test_collect_tags_page_without_frontmatter_is_skipped(tmp_path):
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "a.md").write_text("# just a heading\n", encoding="utf-8")
    assert t.collect_tags(wiki) == []


def test_count_tags_basic():
    entries = [
        t.TagEntry(page=Path("a.md"), field="tags", tag="foo"),
        t.TagEntry(page=Path("b.md"), field="tags", tag="foo"),
        t.TagEntry(page=Path("b.md"), field="tags", tag="bar"),
    ]
    counts = t.count_tags(entries)
    assert counts == {"foo": 2, "bar": 1}


# ─── add_tag_to_page ────────────────────────────────────────────────────


def test_add_tag_to_page_appends_to_inline_list(tmp_path):
    p = tmp_path / "a.md"
    p.write_text(_source_page("[alpha]"), encoding="utf-8")
    changed = t.add_tag_to_page("beta", p)
    assert changed == 1
    text = p.read_text(encoding="utf-8")
    assert "alpha" in text and "beta" in text


def test_add_tag_to_page_idempotent(tmp_path):
    p = tmp_path / "a.md"
    p.write_text(_source_page("[alpha]"), encoding="utf-8")
    changed = t.add_tag_to_page("alpha", p)
    assert changed == 0


def test_add_tag_to_page_creates_new_field(tmp_path):
    p = tmp_path / "a.md"
    # Has topics but no tags; adding a tag creates the tags field.
    p.write_text(_source_page(tags_str="", topics_str="[react]"), encoding="utf-8")
    changed = t.add_tag_to_page("alpha", p, field="tags")
    assert changed == 1
    text = p.read_text(encoding="utf-8")
    assert "tags: [alpha]" in text
    # topics field preserved
    assert "topics: [react]" in text


def test_add_tag_to_page_invalid_field(tmp_path):
    p = tmp_path / "a.md"
    p.write_text(_source_page("[x]"), encoding="utf-8")
    with pytest.raises(ValueError):
        t.add_tag_to_page("y", p, field="bogus")


def test_add_tag_to_page_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        t.add_tag_to_page("x", tmp_path / "nope.md")


def test_add_tag_to_page_empty_tag(tmp_path):
    p = tmp_path / "a.md"
    p.write_text(_source_page("[x]"), encoding="utf-8")
    with pytest.raises(ValueError):
        t.add_tag_to_page("", p)


def test_add_tag_to_page_seeds_frontmatter_on_page_without_it(tmp_path):
    p = tmp_path / "a.md"
    p.write_text("# body only\n", encoding="utf-8")
    changed = t.add_tag_to_page("first", p)
    assert changed == 1
    assert p.read_text().startswith("---\n")


# ─── rename_tag ──────────────────────────────────────────────────────────


def test_rename_tag_inline_list(tmp_path):
    wiki = _mk_wiki(
        tmp_path,
        **{"sources/a.md": _source_page("[old, keep]")},
    )
    touched = t.rename_tag("old", "new", wiki_dir=wiki)
    assert touched == {wiki / "sources" / "a.md": 1}
    text = (wiki / "sources" / "a.md").read_text(encoding="utf-8")
    assert "new" in text and "old" not in text.split("tags:")[1].split("]")[0]


def test_rename_tag_block_list(tmp_path):
    page = dedent(
        """\
        ---
        title: "X"
        type: source
        tags:
          - old
          - keep
        ---

        body
        """
    )
    wiki = _mk_wiki(tmp_path, **{"sources/a.md": page})
    touched = t.rename_tag("old", "new", wiki_dir=wiki)
    assert list(touched.values()) == [1]
    text = (wiki / "sources" / "a.md").read_text(encoding="utf-8")
    assert "- new" in text
    assert "- old" not in text


def test_rename_tag_dry_run_does_not_write(tmp_path):
    wiki = _mk_wiki(
        tmp_path,
        **{"sources/a.md": _source_page("[old]")},
    )
    before = (wiki / "sources" / "a.md").read_text(encoding="utf-8")
    touched = t.rename_tag("old", "new", wiki_dir=wiki, dry_run=True)
    assert touched == {wiki / "sources" / "a.md": 1}
    after = (wiki / "sources" / "a.md").read_text(encoding="utf-8")
    assert before == after  # on-disk unchanged


def test_rename_tag_substring_safety(tmp_path):
    """Renaming `obs` must NOT clobber `obsidian`."""
    wiki = _mk_wiki(
        tmp_path,
        **{"sources/a.md": _source_page("[obsidian, obs]")},
    )
    t.rename_tag("obs", "observability", wiki_dir=wiki)
    text = (wiki / "sources" / "a.md").read_text(encoding="utf-8")
    assert "obsidian" in text
    assert "observability" in text


def test_rename_tag_no_occurrences_empty_result(tmp_path):
    wiki = _mk_wiki(
        tmp_path,
        **{"sources/a.md": _source_page("[x]")},
    )
    assert t.rename_tag("missing", "ghost", wiki_dir=wiki) == {}


def test_rename_tag_same_old_and_new_is_noop(tmp_path):
    wiki = _mk_wiki(
        tmp_path,
        **{"sources/a.md": _source_page("[x]")},
    )
    assert t.rename_tag("x", "x", wiki_dir=wiki) == {}


def test_rename_tag_empty_args_raises(tmp_path):
    with pytest.raises(ValueError):
        t.rename_tag("", "new", wiki_dir=tmp_path)
    with pytest.raises(ValueError):
        t.rename_tag("old", "", wiki_dir=tmp_path)


# ─── near_duplicate_tags ─────────────────────────────────────────────────


def test_near_duplicate_tags_case_insensitive():
    entries = [
        t.TagEntry(page=Path("a"), field="tags", tag="Obsidian"),
        t.TagEntry(page=Path("b"), field="tags", tag="obsidian"),
    ]
    pairs = t.near_duplicate_tags(entries, threshold=0.9)
    assert len(pairs) == 1
    a, b, ratio = pairs[0]
    assert {a.lower(), b.lower()} == {"obsidian"}
    assert ratio == 1.0


def test_near_duplicate_tags_threshold_controls_results():
    entries = [
        t.TagEntry(page=Path("a"), field="tags", tag="plugin"),
        t.TagEntry(page=Path("b"), field="tags", tag="plugins"),
    ]
    # At 0.9 this pair qualifies; at 1.0 it does not.
    assert t.near_duplicate_tags(entries, threshold=0.9)
    assert t.near_duplicate_tags(entries, threshold=1.0) == []


def test_near_duplicate_tags_empty():
    assert t.near_duplicate_tags([]) == []


def test_near_duplicate_tags_unique_pairs_only():
    entries = [
        t.TagEntry(page=Path("a"), field="tags", tag="alpha"),
        t.TagEntry(page=Path("b"), field="tags", tag="beta"),
        t.TagEntry(page=Path("c"), field="tags", tag="gamma"),
    ]
    # alpha vs alpha shouldn't appear — self-comparison excluded by design.
    pairs = t.near_duplicate_tags(entries, threshold=0.1)
    for a, b, _ in pairs:
        assert a != b


# ─── convention_violations ──────────────────────────────────────────────


def test_convention_project_with_tags_flagged():
    entries = [
        t.TagEntry(page=Path("wiki/projects/foo.md"), field="tags", tag="x"),
    ]
    out = t.convention_violations(entries)
    assert len(out) == 1
    page, expected, actual = out[0]
    assert expected == "topics"
    assert actual == "tags"


def test_convention_source_with_topics_flagged():
    entries = [
        t.TagEntry(page=Path("wiki/sources/a.md"), field="topics", tag="x"),
    ]
    out = t.convention_violations(entries)
    assert len(out) == 1
    _, expected, actual = out[0]
    assert expected == "tags"
    assert actual == "topics"


def test_convention_correct_usage_no_violation():
    entries = [
        t.TagEntry(page=Path("wiki/projects/foo.md"), field="topics", tag="React"),
        t.TagEntry(page=Path("wiki/sources/a.md"), field="tags", tag="claude-code"),
    ]
    assert t.convention_violations(entries) == []


def test_convention_unknown_folder_ignored():
    entries = [
        t.TagEntry(page=Path("wiki/misc/note.md"), field="tags", tag="x"),
    ]
    assert t.convention_violations(entries) == []


# ─── format_tag_table ────────────────────────────────────────────────────


def test_format_tag_table_empty():
    assert t.format_tag_table({}) == "No tags found."


def test_format_tag_table_sorts_by_count_desc_then_alpha():
    out = t.format_tag_table({"a": 1, "b": 3, "c": 3})
    lines = out.splitlines()
    # 3-count entries come first; alphabetical within same count.
    b_idx = next(i for i, ln in enumerate(lines) if "b " in ln or ln.strip().startswith("b"))
    c_idx = next(i for i, ln in enumerate(lines) if "c " in ln or ln.strip().startswith("c"))
    a_idx = next(i for i, ln in enumerate(lines) if "a " in ln or ln.strip().startswith("a"))
    assert b_idx < c_idx
    assert b_idx < a_idx
    assert c_idx < a_idx


# ─── CLI subprocess tests ───────────────────────────────────────────────


@pytest.mark.skip(reason="tag CLI subcommand removed")
def test_cli_tag_list_empty_wiki(tmp_path):
    pass


@pytest.mark.skip(reason="tag CLI subcommand removed")
def test_cli_tag_help_shows_subcommands():
    pass


@pytest.mark.skip(reason="tag CLI subcommand removed")
def test_cli_tag_rename_dry_run_does_not_touch_files(tmp_path):
    pass


@pytest.mark.skip(reason="tag CLI subcommand removed")
def test_cli_tag_check_threshold_custom(tmp_path):
    pass


@pytest.mark.skip(reason="tag CLI subcommand removed")
def test_cli_tag_convention_on_good_wiki(tmp_path):
    pass


# ─── G-16 lint rule registration ────────────────────────────────────────


def test_lint_rule_registered():
    from llmwiki.lint import REGISTRY, rules  # noqa: F401
    assert "tags_topics_convention" in REGISTRY


def test_lint_rule_flags_project_with_tags():
    from llmwiki.lint import REGISTRY, rules  # noqa: F401

    rule_cls = REGISTRY["tags_topics_convention"]
    rule = rule_cls()
    pages = {
        "projects/foo.md": {
            "meta": {"title": "Foo", "type": "source", "tags": ["x"]},
            "body": "",
        },
    }
    issues = rule.run(pages)
    assert len(issues) == 1
    assert "topics" in issues[0]["message"]


def test_lint_rule_flags_source_with_topics():
    from llmwiki.lint import REGISTRY, rules  # noqa: F401

    rule_cls = REGISTRY["tags_topics_convention"]
    rule = rule_cls()
    pages = {
        "sources/a.md": {
            "meta": {"title": "A", "type": "source", "topics": ["x"]},
            "body": "",
        },
    }
    issues = rule.run(pages)
    assert len(issues) == 1


def test_lint_rule_silent_on_correct_usage():
    from llmwiki.lint import REGISTRY, rules  # noqa: F401

    rule_cls = REGISTRY["tags_topics_convention"]
    rule = rule_cls()
    pages = {
        "projects/foo.md": {
            "meta": {"title": "Foo", "type": "source", "topics": ["React"]},
            "body": "",
        },
        "sources/a.md": {
            "meta": {"title": "A", "type": "source", "tags": ["claude-code"]},
            "body": "",
        },
    }
    issues = rule.run(pages)
    assert issues == []
