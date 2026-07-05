"""Tests for llmwiki.slugs — shared slug/title derivation (issue #16, kbbuilder#7)."""

from __future__ import annotations

from llmwiki.slugs import (
    derive_title,
    first_heading,
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
    # kbbuilder#7: "Получение или замена биометрического загранпаспорта"
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
    # kbbuilder#7: docs.openclaw.ai titles itself "OpenClaw - OpenClaw".
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
    # kbbuilder#7: 'Source: External' boilerplate must not win over URL segments.
    t = derive_title(explicit=None, markdown="# Source: External\n\nbody",
                     html_title=None, url="https://ex.com/real-doc-name", path_name=None)
    assert t == "real doc name"


def test_derive_title_path_name():
    assert derive_title(explicit=None, markdown="", html_title=None, url=None,
                        path_name="notes.txt") == "notes"
