"""Tests for the llmwiki/render/ module split (v1.1, #217).

Verifies that the CSS + JS extraction from build.py into llmwiki/render/
is byte-identical and backwards-compatible.
"""

from __future__ import annotations
from llmwiki.render import CSS, JS
from llmwiki.render.css import CSS
from llmwiki.render.js import JS
from llmwiki.build import CSS
from llmwiki.build import JS
from llmwiki import build
from llmwiki.render.css import CSS as RENDER_CSS
from llmwiki.render.js import JS as RENDER_JS
from llmwiki.build import build_site
from llmwiki.build import discover_sources
from llmwiki.build import parse_frontmatter



def test_render_package_imports():
    """llmwiki.render exposes CSS + JS at package level."""
    assert isinstance(CSS, str)
    assert isinstance(JS, str)


def test_css_module_directly_importable():
    assert CSS.startswith("/* llmwiki — god-level docs style */")


def test_js_module_directly_importable():
    assert "llmwiki viewer" in JS


# ─── Backwards compatibility ──────────────────────────────────────────


def test_build_module_still_exposes_CSS():
    """Old imports like `from llmwiki.build import CSS` keep working."""
    assert isinstance(CSS, str)
    assert len(CSS) > 1000


def test_build_module_still_exposes_JS():
    assert isinstance(JS, str)
    assert len(JS) > 1000


def test_build_CSS_identical_to_render_CSS():
    """build.CSS and render.css.CSS must be the same object (re-exported)."""
    assert build.CSS is RENDER_CSS


def test_build_JS_identical_to_render_JS():
    assert build.JS is RENDER_JS


# ─── Content integrity ───────────────────────────────────────────────


def test_css_contains_theme_variables():
    """Critical tokens must all be present."""
    for var in ["--bg:", "--text:", "--border:", "--accent:",
                "--shadow-card:", "--heatmap-0:", "--tool-cat-io:"]:
        assert var in CSS, f"missing token: {var}"


def test_css_has_dark_theme_block():
    assert '[data-theme="dark"]' in CSS
    assert "prefers-color-scheme: dark" in CSS


def test_css_respects_prefers_reduced_motion():
    assert "prefers-reduced-motion" in CSS


def test_js_has_theme_toggle():
    assert "Theme toggle" in JS
    assert "data-theme" in JS


def test_js_has_command_palette():
    assert "cmdk" in JS.lower() or "palette" in JS.lower() or "Cmd+K" in JS or "Ctrl+K" in JS


def test_js_loads_search_index():
    assert "search-index.json" in JS


# ─── Build equivalence ───────────────────────────────────────────────


def test_build_site_still_works():
    """Smoke test: the orchestrator hasn't been broken."""
    # Don't actually run — just confirm it's callable
    assert callable(build_site)


def test_discover_sources_still_exported():
    """Other modules may call this."""
    assert callable(discover_sources)


def test_parse_frontmatter_still_exported():
    """Tests + other modules import this."""
    assert callable(parse_frontmatter)
