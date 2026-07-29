"""Tests for ``strip_dead_session_refs`` (#336).

Covers:
* Known session-local filenames (tasks.md, CHANGELOG.md, etc.)
* Wiki-layer wikilinks (../../sources/, ../../wiki/)
* Absolute /Users/ / /home/ paths
* IDE config dirs (.kiro/, .cursor/, .vscode/)
* Bare build files (settings.gradle.kts, gradlew, CODEOWNERS)
* External URLs and mailto left intact
* Regular site-absolute and relative paths left intact
* HTML attribute preservation on the stripped span
* Multi-anchor body processing
* Title attribute surfaces the original href for debugging
"""

from __future__ import annotations

import pytest

from llmwiki.docs_pages import (
    _is_session_local_ref,
    strip_dead_session_refs,
)

# ─── _is_session_local_ref: classifier ────────────────────────────────


@pytest.mark.parametrize("href", [
    "tasks.md",
    "CHANGELOG.md",
    "_progress.md",
    "user_profile.md",
    "user_pratiyush.md",
    "notes.md",
    "TODO.md",
    "plan.md",
    "roadmap.md",
])
def test_known_session_local_basenames_stripped(href):
    assert _is_session_local_ref(href) is True


@pytest.mark.parametrize("href", [
    "../../sources/proj/foo.md",
    "../sources/bar.md",
    "sources/baz.md",
    "../../wiki/entities/X.md",
    "../../entities/Y.md",
    "../../concepts/Z.md",
    "../../syntheses/q.md",
])
def test_wiki_layer_wikilinks_stripped(href):
    assert _is_session_local_ref(href) is True


@pytest.mark.parametrize("href", [
    "/Users/USER/.claude/plans/foo.md",
    "/home/alice/.claude/projects/foo.md",
    "/root/.claude/sessions.jsonl",
    "/tmp/session-notes.md",
])
def test_absolute_home_paths_stripped(href):
    assert _is_session_local_ref(href) is True


@pytest.mark.parametrize("href", [
    ".kiro/steering/architecture.md",
    ".cursor/rules.md",
    ".vscode/settings.json",
    ".idea/workspace.xml",
    ".claude/hooks/a.sh",
    ".codex/sessions.log",
])
def test_ide_config_dirs_stripped(href):
    assert _is_session_local_ref(href) is True


@pytest.mark.parametrize("href", [
    "settings.gradle.kts",
    "build.gradle.kts",
    "gradle.properties",
    "gradlew",
    "gradlew.bat",
    "CODEOWNERS",
])
def test_bare_build_files_stripped(href):
    assert _is_session_local_ref(href) is True


@pytest.mark.parametrize("href", [
    "http://example.com/x.md",
    "https://github.com/Pratiyush/llm-wiki/blob/master/README.md",
    "mailto:user@example.com",
    "/absolute/site/path.html",
    "projects/index.html",
    "sessions/foo/bar.html",
    "../index.html",
])
def test_external_and_real_paths_not_stripped(href):
    assert _is_session_local_ref(href) is False


def test_empty_href_not_stripped():
    assert _is_session_local_ref("") is False


def test_anchor_only_not_stripped():
    # "#section" reduces to "" after split — not a session-local ref.
    assert _is_session_local_ref("#section") is False


def test_query_suffix_stripped_before_classification():
    # href = "tasks.md?foo=bar" should still match the tasks.md rule.
    assert _is_session_local_ref("tasks.md?foo=bar") is True


# ─── strip_dead_session_refs: HTML rewriter ───────────────────────────


def test_strip_replaces_anchor_with_span():
    html = 'Do <a href="tasks.md">your tasks</a> now.'
    out = strip_dead_session_refs(html)
    assert '<span class="session-ref dead-link"' in out
    assert ">your tasks</span>" in out
    assert 'href="tasks.md"' not in out


def test_strip_preserves_text_content():
    html = '<a href="user_profile.md">Meet John Doe</a>'
    out = strip_dead_session_refs(html)
    assert "Meet John Doe" in out
    assert 'href=' not in out


def test_strip_adds_title_with_original_href():
    html = '<a href="tasks.md">x</a>'
    out = strip_dead_session_refs(html)
    assert 'title="session-local ref: tasks.md"' in out


def test_strip_leaves_external_anchors_alone():
    html = '<a href="https://example.com">ext</a>'
    out = strip_dead_session_refs(html)
    assert '<a href="https://example.com">ext</a>' in out


def test_strip_leaves_absolute_site_paths():
    html = '<a href="/docs/ref.html">ref</a>'
    out = strip_dead_session_refs(html)
    # Absolute site paths are real; keep the anchor.
    assert '<a href="/docs/ref.html">ref</a>' in out


def test_strip_leaves_real_relative_paths():
    html = '<a href="../index.html">home</a>'
    out = strip_dead_session_refs(html)
    assert '<a href="../index.html">home</a>' in out


def test_strip_handles_multiple_anchors_in_one_body():
    html = (
        '<p>See <a href="tasks.md">tasks</a>, '
        '<a href="https://gh.com">github</a>, and '
        '<a href="user_profile.md">profile</a>.</p>'
    )
    out = strip_dead_session_refs(html)
    # Two stripped, one intact.
    assert out.count("session-ref dead-link") == 2
    assert "https://gh.com" in out


def test_strip_preserves_anchor_attributes_on_real_links():
    html = '<a href="docs/x.html" class="k" data-x="1">x</a>'
    out = strip_dead_session_refs(html)
    # docs/x.html doesn't match session-local — anchor intact with attrs.
    assert 'class="k"' in out
    assert 'data-x="1"' in out


def test_strip_is_noop_on_empty_body():
    assert strip_dead_session_refs("") == ""


def test_strip_handles_anchor_with_multiline_inner():
    html = '<a href="tasks.md">line 1\nline 2</a>'
    out = strip_dead_session_refs(html)
    assert "line 1\nline 2" in out
    assert "session-ref" in out


def test_strip_case_insensitive_anchor_tag():
    html = '<A HREF="tasks.md">x</A>'
    out = strip_dead_session_refs(html)
    assert "session-ref" in out


def test_strip_handles_href_with_spaces():
    html = '<a href="01 Summary.md">summary</a>'
    out = strip_dead_session_refs(html)
    # Bare filename with .md and no directory — classifier strips it.
    assert "session-ref" in out
