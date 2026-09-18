"""#460: mobile-viewport top-nav items were unreachable.

Below 1024px the desktop `.nav-links` row is hidden by an existing
media query, so Recent / Graph / Analytics / Docs had no path on
phones. The mobile bottom nav only carries Home / Projects / Sessions /
Search / Theme. The fix adds a hamburger button (visible <1024px) that
toggles a drawer mirroring the same nav links vertically.

These tests pin the markup, CSS, and JS contracts.
"""
from __future__ import annotations

from llmwiki.build import nav_bar
from llmwiki.render.css import CSS
from llmwiki.render.js import JS
from llmwiki.topics_page import build_topic_pages

# ─── Markup contract ──────────────────────────────────────────────────


def test_nav_emits_hamburger_button() -> None:
    html_text = nav_bar(active="home")
    assert 'id="nav-hamburger"' in html_text
    assert 'aria-expanded="false"' in html_text
    assert 'aria-controls="nav-drawer"' in html_text
    assert 'aria-label="Open navigation menu"' in html_text


def test_nav_emits_drawer_with_all_links() -> None:
    html_text = nav_bar(active="home")
    assert 'id="nav-drawer"' in html_text
    # Drawer starts hidden so the user doesn't see it on desktop.
    assert "<div id=\"nav-drawer\" class=\"nav-drawer\" hidden" in html_text
    # All seven top-level nav targets reachable from the drawer.
    for target in (
        'href="index.html"',
        'href="raw.html"',
        'href="graph.html"',
        'href="projects/index.html"',
        'href="sessions/index.html"',
        'href="analytics.html"',
        'href="docs/index.html"',
    ):
        assert html_text.count(target) >= 2, (
            f"{target} should appear in both .nav-links AND .nav-drawer "
            "so it's reachable on every viewport"
        )


def test_nav_offers_topics_in_the_row_and_the_drawer() -> None:
    """#248 FR3: the topics listing is generated on every build but had
    nothing pointing at it — no reader arrived there by navigating."""
    html_text = nav_bar(active="home")
    assert html_text.count('href="topics/index.html"') >= 2, (
        "Topics must appear in both .nav-links AND .nav-drawer so it is "
        "reachable on every viewport"
    )
    assert ">Topics</a>" in html_text
    # It sits beside Graph — both are ways into the same knowledge set.
    assert html_text.index('href="graph.html"') < html_text.index(
        'href="topics/index.html"'
    ) < html_text.index('href="projects/index.html"')


def test_nav_marks_topics_active_in_both_surfaces() -> None:
    html_text = nav_bar(active="topics")
    assert '<a href="topics/index.html" class="active">Topics</a>' in html_text
    assert 'class="nav-drawer-link active">Topics</a>' in html_text


def test_topics_index_page_marks_topics_as_the_current_entry(tmp_path) -> None:
    """The listing must highlight itself, not Graph (tech-considerations §5.3).

    Individual topic pages deliberately keep highlighting Graph, which this
    test pins alongside so the two are not "fixed" into agreement.
    """
    graph = {
        "nodes": [{
            "id": "Hazel", "label": "Hazel", "type": "topic", "kind": "entities",
            "site_url": "topics/hazel.html", "session_count": 1, "degree": 0,
            "aliases": [], "description": "", "sessions": [],
        }],
        "edges": [],
        "sessions": {},
        "stats": {"total_sessions": 1, "kinds": {"entities": 1}},
    }
    out = tmp_path / "site"
    build_topic_pages(graph, out)
    index = (out / "topics" / "index.html").read_text(encoding="utf-8")
    assert '<a href="../topics/index.html" class="active">Topics</a>' in index
    assert 'class="nav-drawer-link active">Topics</a>' in index

    topic_page = (out / "topics" / "hazel.html").read_text(encoding="utf-8")
    assert '<a href="../graph.html" class="active">Graph</a>' in topic_page


def test_drawer_marks_active_link() -> None:
    """The drawer must visually highlight the current page so users
    can orient themselves on mobile, same as the desktop nav."""
    html_text = nav_bar(active="graph")
    # The drawer Graph link carries `class="nav-drawer-link active"`.
    assert 'class="nav-drawer-link active">Graph</a>' in html_text


# ─── CSS contract ─────────────────────────────────────────────────────


def test_css_hides_hamburger_above_1024() -> None:
    """Hamburger should be hidden by default (desktop) and only shown
    where the desktop nav-links row has been hidden (<1024)."""
    assert ".nav-hamburger {" in CSS
    # Default: display none.
    assert "display: none" in CSS
    # Show below 1024.
    assert "@media (max-width: 1023px) { .nav-hamburger" in CSS


def test_css_drawer_styles_present() -> None:
    assert ".nav-drawer {" in CSS
    assert ".nav-drawer-link {" in CSS
    # Drawer must carry an active state for the current page.
    assert ".nav-drawer-link.active" in CSS


# ─── JS contract ──────────────────────────────────────────────────────


def test_js_wires_hamburger_toggle() -> None:
    assert "nav-hamburger" in JS
    assert "nav-drawer" in JS
    # Toggle reads + writes aria-expanded.
    assert 'getAttribute("aria-expanded")' in JS
    assert 'setAttribute("aria-expanded"' in JS


def test_js_handles_escape_key() -> None:
    """ESC closes the drawer and returns focus to the hamburger so
    keyboard users don't get trapped."""
    assert 'key === "Escape"' in JS
    # Focus return — find the assignment near the Escape handler.
    esc_block = JS[JS.find('key === "Escape"'): JS.find('key === "Escape"') + 200]
    assert "btn.focus()" in esc_block


def test_js_closes_drawer_on_outside_click() -> None:
    """Click-outside-to-close is the standard menu pattern."""
    # The handler checks contains() on both drawer + button, then closes.
    assert "drawer.contains(e.target)" in JS
    assert "btn.contains(e.target)" in JS


def test_js_closes_drawer_after_navigation() -> None:
    """After tapping a drawer link, close before the next page loads
    so the next page doesn't briefly render with the drawer open."""
    drawer_block = JS[JS.find("nav-drawer"): JS.find("Reading progress")]
    assert 'querySelectorAll("a")' in drawer_block
    assert 'setOpen(false)' in drawer_block
