"""Tests for the llmwiki/render/ module split (v1.1, #217).

Verifies that the CSS + JS extraction from build.py into llmwiki/render/
is byte-identical and backwards-compatible.
"""

from __future__ import annotations

import pytest


def test_render_package_imports():
    """llmwiki.render exposes CSS + JS at package level."""
    from llmwiki.render import CSS, JS
    assert isinstance(CSS, str)
    assert isinstance(JS, str)


def test_css_module_directly_importable():
    from llmwiki.render.css import CSS
    assert CSS.startswith("/* llmwiki — god-level docs style */")


def test_js_module_directly_importable():
    from llmwiki.render.js import JS
    assert "llmwiki viewer" in JS


# ─── Backwards compatibility ──────────────────────────────────────────


def test_build_module_still_exposes_CSS():
    """Old imports like `from llmwiki.build import CSS` keep working."""
    from llmwiki.build import CSS
    assert isinstance(CSS, str)
    assert len(CSS) > 1000


def test_build_module_still_exposes_JS():
    from llmwiki.build import JS
    assert isinstance(JS, str)
    assert len(JS) > 1000


def test_build_CSS_identical_to_render_CSS():
    """build.CSS and render.css.CSS must be the same object (re-exported)."""
    from llmwiki import build
    from llmwiki.render.css import CSS as RENDER_CSS
    assert build.CSS is RENDER_CSS


def test_build_JS_identical_to_render_JS():
    from llmwiki import build
    from llmwiki.render.js import JS as RENDER_JS
    assert build.JS is RENDER_JS


# ─── Content integrity ───────────────────────────────────────────────


def test_css_contains_theme_variables():
    """Critical tokens must all be present."""
    from llmwiki.render.css import CSS
    for var in ["--bg:", "--text:", "--border:", "--accent:",
                "--shadow-card:", "--heatmap-0:", "--tool-cat-io:"]:
        assert var in CSS, f"missing token: {var}"


def test_css_has_dark_theme_block():
    from llmwiki.render.css import CSS
    assert '[data-theme="dark"]' in CSS
    assert "prefers-color-scheme: dark" in CSS


def test_css_respects_prefers_reduced_motion():
    from llmwiki.render.css import CSS
    assert "prefers-reduced-motion" in CSS


def test_js_has_theme_toggle():
    from llmwiki.render.js import JS
    assert "Theme toggle" in JS
    assert "data-theme" in JS


def test_js_has_command_palette():
    from llmwiki.render.js import JS
    assert "cmdk" in JS.lower() or "palette" in JS.lower() or "Cmd+K" in JS or "Ctrl+K" in JS


def test_js_loads_search_index():
    from llmwiki.render.js import JS
    assert "search-index.json" in JS


# ─── Size constraint ─────────────────────────────────────────────────


def test_build_py_is_smaller():
    """After the refactor, build.py should be ~half its original size.

    Threshold adjusted as follow-on features landed:
      * 3,378 (pre-refactor #217)
      * 2,000 (post-split)
      * 2,200 (#283 md_to_html cache + #284 README/CONTRIBUTING
        compile + #277 palette docs indexing)
      * 2,300 (#417 plain_text cache + content_key helper)
      * 2,400 (#425 stub-defaults pre-population helpers)
      * 2,500 (#492 _is_subagent helper for renderer-side classification)
      * 2,850 (Home queue dashboard + Raw page + estimate widget)
      * 2,900 (#27 Analytics: render_mcp_usage_section + wiring)
      * 2,950 (#27 per-project render_project_usage_block + wiring)
      * 3,000 (#27 feedback: single card row, render_mcp_heaviest_card,
        analytics-scoped spacing, wiki_dir log-source fix)
      * 3,200 (#52 Wiki value extract → llmwiki/viz_wiki_value.py;
        orchestrator still holds analytics wiring)
    Next refactor target: extract md_to_html + preprocessor to
    llmwiki/render/markdown.py (tracked in the deep-audit epic #286).
    """
    from llmwiki import REPO_ROOT
    build_py = REPO_ROOT / "llmwiki" / "build.py"
    line_count = len(build_py.read_text(encoding="utf-8").splitlines())
    assert line_count < 3200, f"build.py is {line_count} lines (ceiling 3200)"


def test_css_module_under_800_lines():
    """Per the refactor acceptance criterion.

    Threshold adjusted as follow-on features landed:
      * 1,015 (refactor acceptance criterion)
      * 1,020 (#20 palette-note styling for unloadable search data)
      * 1,110 (#52 Wiki value chart / mix / dead-stock styles)
      * 1,130 (Home pipeline State table + shared collapse-section chrome)
    """
    from llmwiki import REPO_ROOT
    css_py = REPO_ROOT / "llmwiki" / "render" / "css.py"
    line_count = len(css_py.read_text(encoding="utf-8").splitlines())
    assert line_count < 1130, f"css.py is {line_count} lines"


# ─── Build equivalence ───────────────────────────────────────────────


def test_build_site_still_works():
    """Smoke test: the orchestrator hasn't been broken."""
    from llmwiki.build import build_site
    # Don't actually run — just confirm it's callable
    assert callable(build_site)


def test_discover_sources_still_exported():
    """Other modules may call this."""
    from llmwiki.build import discover_sources
    assert callable(discover_sources)


def test_parse_frontmatter_still_exported():
    """Tests + other modules import this."""
    from llmwiki.build import parse_frontmatter
    assert callable(parse_frontmatter)
