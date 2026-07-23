"""Tests for llmwiki.slugs — shared slug/title derivation (issue #16)."""

from __future__ import annotations

from llmwiki.slugs import (
    derive_title,
    first_heading,
    project_slug_from_abs_path,
    project_slug_from_encoded_dir,
    slugify,
    strip_site_suffix,
    title_from_url,
)

# ── slugify ──────────────────────────────────────────────────────────

def test_slugify_basic():
    assert slugify("Hello, World!") == "hello-world"


def test_slugify_accents_folded():
    assert slugify("Café Über naïve") == "cafe-uber-naive"


def test_slugify_cyrillic_transliterated():
    # Regression: a Cyrillic title must not collapse to ''.
    # must NOT collapse to '' (the old literal-'document' failure).
    s = slugify("Получение загранпаспорта РФ в Армении")
    assert s == "poluchenie-zagranpasporta-rf-v-armenii"


def test_slugify_empty_returns_empty():
    # Caller falls to the next title candidate — slugify never invents 'document'.
    assert slugify("†‡•") == ""


def test_slugify_caps_at_80_chars_no_trailing_dash():
    s = slugify("word " * 40)
    assert len(s) <= 80
    assert not s.endswith("-")


def test_slugify_output_is_site_safe():
    # raw_docs_site._SAFE_SEG_RE requires ^[A-Za-z0-9._-]+$ — anything else
    # is silently invisible to the site build.
    import re
    s = slugify("Weird 「title」 withّ marks — and stuff")
    assert re.fullmatch(r"[a-z0-9-]+", s)


# ── strip_site_suffix ────────────────────────────────────────────────

def test_strip_site_suffix_dash():
    assert strip_site_suffix("Getting Started - MyLib Docs") == "Getting Started"


def test_strip_site_suffix_pipe():
    assert strip_site_suffix("Pricing | Acme") == "Pricing"


def test_strip_site_suffix_emdash():
    assert strip_site_suffix("Guide — ReadTheDocs") == "Guide"


def test_strip_site_suffix_repeated_word_collapses():
    # Regression: docs.openclaw.ai titles itself "OpenClaw - OpenClaw".
    assert strip_site_suffix("OpenClaw - OpenClaw") == "OpenClaw"


def test_strip_site_suffix_no_separator_untouched():
    assert strip_site_suffix("Plain Title") == "Plain Title"


def test_strip_site_suffix_keeps_head_when_tail_longer():
    # Don't strip when the "suffix" is the real content.
    assert strip_site_suffix("FAQ - Frequently Asked Questions about Billing") \
        == "FAQ - Frequently Asked Questions about Billing"


# ── first_heading ────────────────────────────────────────────────────

def test_first_heading_simple():
    assert first_heading("intro\n\n# Real Title\n\nbody") == "Real Title"


def test_first_heading_skips_fenced_hash():
    md = "```sh\n# not a heading\n```\n\n## Actual\n"
    assert first_heading(md) == "Actual"


def test_first_heading_none():
    assert first_heading("no headings here") == ""


def test_first_heading_drops_permalink_anchor():
    # CMSs (BetterDocs/Elementor and friends) render a self-link inside every
    # heading. It survives extraction as a markdown link whose whole label is
    # punctuation, and used to end up in the title, the slug AND the raw/docs
    # project directory name (`primer-zagolovka-0-toc-title`). Cyrillic here
    # on purpose: the title feeds slugify, so this also covers the case where
    # the markup survives transliteration.
    assert first_heading("# Пример заголовка [#](#0-toc-title)\n") == "Пример заголовка"
    assert first_heading("# Title [¶](#1-toc-title)\n") == "Title"


def test_first_heading_keeps_real_link_label():
    # A heading may legitimately contain a link; keep its text, drop the markup.
    assert first_heading("# Taxes for [sole traders](/docs/ip)\n") == "Taxes for sole traders"


def test_first_heading_strips_emphasis_markers():
    assert first_heading("# **Bold** and _thin_\n") == "Bold and thin"


def test_first_heading_can_restrict_to_levels():
    md = "## Subsection\n\ntext\n\n# Real Title\n"
    assert first_heading(md) == "Subsection"
    assert first_heading(md, levels=(1,)) == "Real Title"
    assert first_heading("## Only a subsection\n", levels=(1,)) == ""


def test_derive_title_prefers_html_title_over_body_subsection():
    # A CMS article <h1> often sits outside the extracted content container,
    # so the first heading in the markdown is an ## body subsection. Using it
    # gave whole families of articles the same generic title ("Signing in" for
    # every bank's guide), colliding into "-2" directory suffixes, while the
    # real title sat unused in html_title.
    title = derive_title(
        explicit=None,
        markdown="## Вход в систему\n\ntext\n\n## Меню\n",
        html_title="Пример Банк: инструкция для юрлиц",
        url="https://ex.com/docs/banks/primer-bank",
        path_name=None,
    )
    assert title == "Пример Банк: инструкция для юрлиц"


def test_derive_title_still_prefers_h1_over_html_title():
    title = derive_title(
        explicit=None,
        markdown="# Document Heading\n\ntext\n",
        html_title="Document Heading - Some Site",
        url="https://ex.com/x",
        path_name=None,
    )
    assert title == "Document Heading"


# ── title_from_url ───────────────────────────────────────────────────

def test_title_from_url_path_segment():
    assert title_from_url("https://ex.com/docs/getting-started.html") == "getting started"


def test_title_from_url_skips_index():
    assert title_from_url("https://ex.com/guide/index.html") == "guide"


def test_title_from_url_host_fallback():
    assert title_from_url("https://docs.openclaw.ai/") == "docs.openclaw.ai"


# ── derive_title ─────────────────────────────────────────────────────

def test_derive_title_prefers_explicit():
    assert derive_title(explicit="My Title", markdown="# Other", html_title="X",
                        url="https://e.com/a", path_name=None) == "My Title"


def test_derive_title_markdown_heading_beats_html_title():
    assert derive_title(explicit=None, markdown="# From Heading",
                        html_title="From <title> - Site", url="https://e.com/a",
                        path_name=None) == "From Heading"


def test_derive_title_html_title_suffix_stripped():
    assert derive_title(explicit=None, markdown="no headings",
                        html_title="Page - SiteName", url="https://e.com/a",
                        path_name=None) == "Page"


def test_derive_title_boilerplate_heading_falls_to_url():
    # Regression: 'Source: External' boilerplate must not win over URL segments.
    t = derive_title(explicit=None, markdown="# Source: External\n\nbody",
                     html_title=None, url="https://ex.com/real-doc-name", path_name=None)
    assert t == "real doc name"


def test_derive_title_path_name():
    assert derive_title(explicit=None, markdown="", html_title=None, url=None,
                        path_name="notes.txt") == "notes"


# ── project_slug_from_abs_path (#51 / #36) ───────────────────────────

def test_abs_path_slug_matches_the_session_adapter():
    """An absolute path and the session store's dash-encoded form of the same
    path must resolve to one slug, so MCP telemetry keyed by a live path lines
    up with the project page the ingestion adapter built."""
    from llmwiki.adapters.claude_code import ClaudeCodeAdapter

    adapter = ClaudeCodeAdapter()
    encoded = adapter.session_store_path / "-Users-alice-code-webapp" / "s.jsonl"
    assert (project_slug_from_abs_path("/Users/alice/code/webapp")
            == adapter.derive_project_slug(encoded)
            == "code-webapp")


def test_abs_path_slug_reuses_the_encoded_decoder():
    assert (project_slug_from_abs_path("/home/dev/code/project-a")
            == project_slug_from_encoded_dir("-home-dev-code-project-a"))


def test_abs_path_slug_honors_workspace_markers():
    assert (project_slug_from_abs_path(
        "/Users/alice/Desktop/2026/production/draft/ai-newsletter")
        == "ai-newsletter")


def test_abs_path_slug_normalizes_spaces_and_trailing_slash():
    assert project_slug_from_abs_path("/home/dev/code/my project/") == "my-project"


def test_abs_path_slug_windows_separators():
    assert project_slug_from_abs_path(r"C:\\Users\\alice\\code\\webapp") == "code-webapp"
