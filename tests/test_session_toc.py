"""#229: session page TOC mounts in doctree-layout below the hero.

# @layer: unit
# @spec: 229-session-tags-and-toc
# @regression
"""
from __future__ import annotations

import re
from pathlib import Path

from llmwiki.build import render_session
from llmwiki.render.css import CSS
from llmwiki.render.js import JS


def _session_src(body: str = "## One\n\nx\n\n## Two\n\ny\n\n## Three\n\nz\n"):
    meta = {
        "title": "Session: abc12345 — 2026-07-20",
        "slug": "abc12345",
        "project": "demo-proj",
        "date": "2026-07-20",
        "started": "2026-07-20T12:00:00+00:00",
        "model": "claude-sonnet-4-6",
        "agent": "claude-code",
        "sessionId": "8057bbe6-73e8-418f-b439-b4d11bad1ad7",
        "cwd": "/Users/USER/code/demo-proj",
        "gitBranch": "main",
        "is_subagent": False,
        "user_messages": 3,
        "tool_calls": 5,
        "tags": ["claude-code", "session-transcript"],
    }
    path = Path("raw/sessions/2026-07-20T12-00-demo-proj-abc12345.md")
    return path, meta, body


def test_session_html_toc_mount_inside_doctree_section(tmp_path: Path) -> None:
    """TOC aside lives under section.doctree-section, after hero, not on body."""
    path, meta, body = _session_src()
    out = render_session(path, meta, body, tmp_path, "demo-proj")
    html = out.read_text(encoding="utf-8")

    assert 'class="doctree-layout session-toc-layout"' in html
    assert 'data-toc-mount' in html
    assert 'class="toc-sidebar"' in html

    hero_idx = html.find("hero-sm")
    section_idx = html.find('class="section doctree-section"')
    mount_idx = html.find("data-toc-mount")
    assert hero_idx != -1 and section_idx != -1 and mount_idx != -1
    assert hero_idx < section_idx < mount_idx

    # Mount precedes article content inside the grid.
    main_idx = html.find('class="doctree-main"')
    assert mount_idx < main_idx


def test_session_description_lives_inside_hero(tmp_path: Path) -> None:
    """#229/#471: description is inside ``.hero .container``, not a sibling after it.

    Selection quality of the text is #246; this test only locks layout placement.
    """
    path, meta, body = _session_src()
    meta = {**meta, "description": "few more items here:"}
    out = render_session(path, meta, body, tmp_path, "demo-proj")
    html = out.read_text(encoding="utf-8")

    m = re.search(
        r'<section class="hero[^"]*">\s*<div class="container">(.*?)</div>\s*</section>',
        html,
        re.S,
    )
    assert m, "hero section missing"
    hero_inner = m.group(1)
    assert 'class="session-description"' in hero_inner
    assert "few more items here:" in hero_inner
    after_hero = html[m.end() : html.find('class="section doctree-section"')]
    assert "session-description" not in after_hero
    assert ".hero .session-description" in CSS


def test_session_toc_js_mounts_into_data_toc_mount_not_body() -> None:
    """Regression: old code appended a fixed .toc-sidebar to document.body."""
    toc_block = re.search(
        r"// ─── TOC sidebar.*?^\}\)\(\);",
        JS,
        re.DOTALL | re.MULTILINE,
    )
    assert toc_block, "TOC sidebar block missing from render/js.py"
    block = toc_block.group(0)
    assert "data-toc-mount" in block
    assert "document.body.appendChild" not in block
    assert "#229" in block
    # Short sessions (Conversation + one Turn) only have 2 headings.
    assert "headings.length < 2" in block
    assert "headings.length < 3" not in block


def test_session_toc_css_sticky_in_doctree_grid() -> None:
    """TOC uses sticky positioning inside session-toc-layout, not body-fixed."""
    assert ".session-toc-layout" in CSS
    assert ".session-toc-layout:has(> .toc-sidebar.toc-ready)" in CSS
    sticky_rule = re.search(
        r"\.toc-sidebar\s*\{[^}]*position:\s*sticky",
        CSS,
        re.DOTALL,
    )
    assert sticky_rule, ".toc-sidebar must use position: sticky"
    assert "not body-fixed over the hero" in CSS
    assert "#229" in CSS
    # Same collapse breakpoint as .doctree-layout (not a separate 1340 gate).
    toc_css = CSS.split("/* TOC sidebar")[1].split("/* #460:")[0]
    assert "1340" not in toc_css
    assert "@media (max-width: 860px)" in toc_css
    assert "toc-sidebar.toc-ready" in toc_css
    assert re.search(r"\.toc-sidebar\.toc-ready\s*\{\s*display:\s*block", toc_css)
