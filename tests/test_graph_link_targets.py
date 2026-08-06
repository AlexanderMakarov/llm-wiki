"""The map opens pages in the current tab, except on double-click (#108 FR10).

Everywhere else in the generated site a link opens in the current tab. The map
used to be the exception three times over — the side panel's ``Open page →``
link, the session links beside it, and the right-click menu's open action all
opened a new tab. Only the double-click, a deliberate "take this elsewhere"
gesture, still does.

These assert on the emitted ``graph.html`` rather than the template so a
placeholder substitution can never quietly reintroduce a new-tab target.
"""

from __future__ import annotations

import pytest

from llmwiki.graph import write_html


@pytest.fixture(scope="module")
def rendered(tmp_path_factory: pytest.TempPathFactory) -> str:
    """The generated `graph.html` for an empty graph."""
    out = tmp_path_factory.mktemp("graph") / "graph.html"
    write_html({"nodes": [], "edges": [], "stats": {}}, out)
    return out.read_text(encoding="utf-8")


def _js_block(html: str, marker: str) -> str:
    """The declaration starting at `marker`, up to its balanced closing brace."""
    start = html.index(marker)
    depth = 0
    for i in range(start, len(html)):
        if html[i] == "{":
            depth += 1
        elif html[i] == "}":
            depth -= 1
            if depth == 0:
                return html[start : i + 1]
    raise AssertionError(f"unbalanced braces after {marker!r}")


def test_panel_open_page_link_stays_in_the_current_tab(rendered: str):
    panel = _js_block(rendered, "function showTopicPanel(node) {")
    assert "panel-open" in panel, "fixture drift: the panel no longer emits the link"
    assert "_blank" not in panel
    assert 'rel="noopener"' not in panel


def test_panel_session_links_stay_in_the_current_tab(rendered: str):
    sessions = _js_block(rendered, "function topicSessionLinks(slugs, limit) {")
    assert "panel-link" in sessions
    assert "_blank" not in sessions


def test_context_menu_open_navigates_in_the_current_tab(rendered: str):
    menu = _js_block(rendered, "if (ctxMenu) ctxMenu.addEventListener('click'")
    open_case = menu[menu.index("case 'open': {") : menu.index("case 'neighbours':")]
    assert "window.location.href = node.site_url;" in open_case
    assert "window.open" not in open_case
    # The graceful no-page path is untouched.
    assert "no compiled page exists" in open_case


def test_double_click_still_opens_a_new_tab(rendered: str):
    """The one deliberate exception — double-click means "take this elsewhere"."""
    handler = _js_block(rendered, "network.on('doubleClick', params => {")
    assert "window.open(node.site_url, '_blank', 'noopener')" in handler
