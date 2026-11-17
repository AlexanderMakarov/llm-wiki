"""Tests for the llmwiki/render/ module split (v1.1, #217).

Verifies that the CSS + JS extraction from build.py into llmwiki/render/
is identity-preserving and backwards-compatible.
"""

from __future__ import annotations

import pytest

from llmwiki import build
from llmwiki.render import CSS, JS
from llmwiki.render.css import CSS as RENDER_CSS
from llmwiki.render.js import JS as RENDER_JS

# ─── Backwards compatibility ──────────────────────────────────────────

def test_render_package_reexports_the_module_constants():
    """`llmwiki.render.CSS` / `.JS` are the same objects as the `render.css` / `render.js` constants."""
    assert CSS is RENDER_CSS
    assert JS is RENDER_JS

def test_build_CSS_identical_to_render_CSS():
    """Old imports like `from llmwiki.build import CSS` get the same object as `render.css.CSS`."""
    assert build.CSS is RENDER_CSS

def test_build_JS_identical_to_render_JS():
    """Old imports like `from llmwiki.build import JS` get the same object as `render.js.JS`."""
    assert build.JS is RENDER_JS

# ─── Content integrity ───────────────────────────────────────────────

def test_css_contains_theme_variables():
    """Critical design tokens are all present in the emitted stylesheet."""
    for var in ["--bg:", "--text:", "--border:", "--accent:",
                "--shadow-card:", "--heatmap-0:", "--tool-cat-io:"]:
        assert var in CSS, f"missing token: {var}"

def test_css_has_dark_theme_block():
    """The stylesheet ships both the explicit dark theme and the OS-preference dark theme."""
    assert '[data-theme="dark"]' in CSS
    assert "prefers-color-scheme: dark" in CSS

def test_css_respects_prefers_reduced_motion():
    """The stylesheet carries a `prefers-reduced-motion` override for animations."""
    assert "prefers-reduced-motion" in CSS

# ─── Emitted JS still ships core chrome contracts ─────────────────────

@pytest.mark.parametrize(
    "needle,label",
    [
        ("Theme toggle", "theme toggle control"),
        ("data-theme", "theme attribute writes"),
        ("search-index.json", "search index fetch"),
    ],
)
def test_js_bundle_ships_core_features(needle: str, label: str):
    """The shared viewer JS still embeds the theme toggle, theme attribute writes, and search-index loader."""
    assert needle in JS, f"missing {label}: {needle!r}"

def test_js_bundle_ships_command_palette():
    """The shared viewer JS still embeds the command-palette / Cmd+K surface."""
    lowered = JS.lower()
    assert (
        "cmdk" in lowered
        or "palette" in lowered
        or "Cmd+K" in JS
        or "Ctrl+K" in JS
    ), "missing command palette markers"
