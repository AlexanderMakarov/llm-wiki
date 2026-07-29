"""Tests for the `.llmwikiignore` matcher."""

from __future__ import annotations

from llmwiki.convert import IgnoreMatcher


def test_empty_matcher():
    m = IgnoreMatcher([])
    assert not m
    assert len(m) == 0
    assert m.is_ignored(project="anything", filename="foo.md") is False


def test_empty_lines_and_comments_are_ignored():
    m = IgnoreMatcher([
        "# this is a comment",
        "",
        "  # indented comment",
        "",
        "*.tmp",
    ])
    assert len(m) == 1
    assert m.is_ignored(project="p", filename="foo.tmp") is True
    assert m.is_ignored(project="p", filename="foo.md") is False


def test_basename_glob():
    m = IgnoreMatcher(["*.secret"])
    assert m.is_ignored(project="p", filename="creds.secret") is True
    assert m.is_ignored(project="p", filename="notes.md") is False


def test_whole_project_match_with_trailing_slash():
    m = IgnoreMatcher(["confidential-client/"])
    assert m.is_ignored(project="confidential-client", filename="2026-04-04-x.md") is True
    # Other projects untouched
    assert m.is_ignored(project="ai-newsletter", filename="2026-04-04-x.md") is False


def test_composite_path_match():
    m = IgnoreMatcher(["ai-newsletter/2026-04-04-*"])
    assert m.is_ignored(project="ai-newsletter", filename="2026-04-04-secret.md") is True
    assert m.is_ignored(project="ai-newsletter", filename="2026-04-05-other.md") is False
    assert m.is_ignored(project="other", filename="2026-04-04-x.md") is False


def test_date_pattern_across_projects():
    m = IgnoreMatcher(["*2025-*"])
    # 2025 matches
    assert m.is_ignored(project="p", filename="2025-12-31-x.md") is True
    # 2026 doesn't
    assert m.is_ignored(project="p", filename="2026-01-01-x.md") is False


def test_negation_reincludes():
    m = IgnoreMatcher([
        "confidential-client/",       # exclude the whole project
        "!confidential-client/public-*",  # …except public-* sessions
    ])
    assert m.is_ignored(project="confidential-client", filename="2026-04-04-private.md") is True
    assert m.is_ignored(project="confidential-client", filename="public-launch.md") is False


def test_last_rule_wins():
    """Order matters — later rules override earlier ones."""
    m = IgnoreMatcher([
        "*.md",         # ignore all markdown
        "!keep-*.md",   # but keep keep-*.md
        "keep-bad.md",  # except this one
    ])
    assert m.is_ignored(project="p", filename="other.md") is True
    assert m.is_ignored(project="p", filename="keep-me.md") is False
    assert m.is_ignored(project="p", filename="keep-bad.md") is True


def test_from_file_missing(tmp_path):
    m = IgnoreMatcher.from_file(tmp_path / "does-not-exist.llmwikiignore")
    assert not m


def test_from_file_present(tmp_path):
    f = tmp_path / ".llmwikiignore"
    f.write_text("# comment\n*.tmp\nconfidential/\n", encoding="utf-8")
    m = IgnoreMatcher.from_file(f)
    assert len(m) == 2
    assert m.is_ignored(project="p", filename="x.tmp") is True
    assert m.is_ignored(project="confidential", filename="y.md") is True
    assert m.is_ignored(project="ok", filename="y.md") is False
