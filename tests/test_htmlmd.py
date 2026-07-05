"""Tests for llmwiki.htmlmd — stdlib HTML→Markdown converter (issue #16)."""

from __future__ import annotations

from llmwiki.htmlmd import html_to_markdown

PAGE = """<!doctype html>
<html><head><title>Sample Page - ExampleSite</title>
<style>body { color: red }</style>
<script>alert("nope")</script>
</head><body>
<nav><a href="/">Home</a><a href="/about">About</a></nav>
<header><h1>Site Banner</h1></header>
<article>
  <h1>Real Article Title</h1>
  <p>First paragraph with <strong>bold</strong> and <em>italic</em> and
     an <a href="https://ex.com/link">anchor</a>.</p>
  <h2>Section &amp; Details</h2>
  <ul><li>alpha</li><li>beta</li></ul>
  <ol><li>one</li><li>two</li></ol>
  <pre><code>x = 1
y = 2</code></pre>
  <p>Inline <code>code()</code> too.</p>
</article>
<footer>© 2026 Example</footer>
</body></html>"""


def test_title_extracted():
    title, _ = html_to_markdown(PAGE)
    assert title == "Sample Page - ExampleSite"


def test_article_preferred_over_chrome():
    _, md = html_to_markdown(PAGE)
    assert "Real Article Title" in md
    assert "Site Banner" not in md      # <header> outside article dropped
    assert "About" not in md            # nav dropped
    assert "© 2026" not in md           # footer dropped
    assert "alert(" not in md           # script dropped
    assert "color: red" not in md       # style dropped


def test_block_conversions():
    _, md = html_to_markdown(PAGE)
    assert "# Real Article Title" in md
    assert "## Section & Details" in md          # entity decoded
    assert "- alpha" in md and "- beta" in md
    assert "1. one" in md and "2. two" in md
    assert "[anchor](https://ex.com/link)" in md
    assert "**bold**" in md and "*italic*" in md
    assert "`code()`" in md
    assert "```\nx = 1\ny = 2\n```" in md


def test_no_article_falls_back_to_body():
    html = "<html><head><title>T</title></head><body><p>hello world</p></body></html>"
    _, md = html_to_markdown(html)
    assert "hello world" in md


def test_whitespace_collapsed():
    _, md = html_to_markdown(PAGE)
    assert "\n\n\n" not in md
    assert not md.startswith("\n")
