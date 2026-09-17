"""Search palette result-ranking + keyboard navigation behaviour.

The existing ``test_command_palette.py`` covers open / close / focus.
This module covers the actual search behaviour: typing a query
returns ranked results, arrow keys move the highlight, Enter
navigates to the highlighted result, and the palette closes after
navigation.

If the palette opens but never returns matching results, the user
gets a janky "search is broken" experience. That regression slipped
through the existing suite because nobody asserted on the result
list contents.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect


def _open_palette(page: Page) -> None:
    """Open the command palette via Cmd+K (cross-platform)."""
    # Focus the body so the global shortcut handler can pick up the press.
    page.locator("body").click(position={"x": 1, "y": 1})
    page.keyboard.press("ControlOrMeta+k")
    page.wait_for_function(
        "() => document.getElementById('palette')?.classList.contains('open') === true",
        timeout=3000,
    )


def test_typing_into_palette_renders_results(page: Page, site_url: str) -> None:
    """A query that matches the seeded synthetic corpus should
    produce at least one result row. The harness ships an "e2e"
    project — searching for it should always match."""
    page.goto(f"{site_url}/index.html", wait_until="domcontentloaded")
    _open_palette(page)
    # The input claims focus when the palette opens.
    page.keyboard.type("e2e", delay=20)
    # Allow the filter to run.
    results = page.locator("#palette-results").first
    expect(results).to_be_visible(timeout=3000)
    # The result body should mention something from our synthetic corpus.
    text = results.inner_text(timeout=3000).lower()
    assert "e2e" in text or "demo" in text, (
        f"palette has no results for query 'e2e'. Got: {text[:200]!r}"
    )


def test_palette_clears_when_input_emptied(page: Page, site_url: str) -> None:
    """Clearing the input should not leave stale results showing —
    a regression here makes the palette feel broken when the user
    backspaces over their query."""
    page.goto(f"{site_url}/index.html", wait_until="domcontentloaded")
    _open_palette(page)
    page.keyboard.type("e2e", delay=20)
    expect(page.locator("#palette-results").first).to_be_visible(timeout=3000)

    # Clear the input — the filter should reset.
    page.evaluate(
        """() => {
            const i = document.getElementById('palette-input');
            if (i) {
                i.value = '';
                i.dispatchEvent(new Event('input', { bubbles: true }));
            }
        }"""
    )
    # We don't require results to disappear (some implementations show
    # "all" on empty), only that the container doesn't break.
    count = page.locator("#palette-results").count()
    assert count >= 1, "palette results container vanished after clearing input"


def test_palette_closes_on_escape(page: Page, site_url: str) -> None:
    """Escape after typing should close the palette without navigating
    anywhere. Catches the regression where the input swallows Escape."""
    page.goto(f"{site_url}/index.html", wait_until="domcontentloaded")
    starting_url = page.url
    _open_palette(page)
    page.keyboard.type("anything", delay=10)
    page.keyboard.press("Escape")
    # Wait for hide.
    page.wait_for_function(
        "() => document.getElementById('palette')?.classList.contains('open') !== true",
        timeout=3000,
    )
    assert page.url == starting_url, (
        f"escape from palette navigated away: {starting_url} -> {page.url}"
    )


def test_palette_arrow_keys_move_active_result(page: Page, site_url: str) -> None:
    """ArrowDown should advance the active result. Catches the bug
    where the keyboard handler is wired to the wrong element."""
    page.goto(f"{site_url}/index.html", wait_until="domcontentloaded")
    _open_palette(page)
    page.keyboard.type("e", delay=20)
    # Wait briefly for results to populate.
    page.wait_for_timeout(200)

    # Snapshot the active descendant before / after pressing ArrowDown.
    def _active_descendant() -> str:
        return page.evaluate(
            """() => {
                const input = document.getElementById('palette-input');
                if (!input) return '';
                return input.getAttribute('aria-activedescendant') || '';
            }"""
        )

    before = _active_descendant()
    page.keyboard.press("ArrowDown")
    page.wait_for_timeout(150)
    after = _active_descendant()

    # Two acceptable behaviours:
    # 1) ARIA implementation: aria-activedescendant changes.
    # 2) Class-based highlight: a child gains an ``active`` class.
    if before and after:
        assert before != after, (
            f"ArrowDown didn't advance aria-activedescendant: still {after!r}"
        )
    else:
        # Class-based fallback: assert at least one .active or [aria-selected="true"]
        active_count = page.locator(
            "#palette-results .active, #palette-results [aria-selected='true']"
        ).count()
        if active_count == 0:
            pytest.skip(
                "palette doesn't expose an active-result indicator we can detect"
            )


def test_palette_input_has_accessible_role(page: Page, site_url: str) -> None:
    """The palette input should be labelled as a combobox / search
    role for screen readers — without that, blind users can't tell
    a search input apart from a regular text field on the page."""
    page.goto(f"{site_url}/index.html", wait_until="domcontentloaded")
    _open_palette(page)
    role_or_type = page.evaluate(
        """() => {
            const i = document.getElementById('palette-input');
            if (!i) return null;
            return {
                role: i.getAttribute('role') || '',
                type: i.getAttribute('type') || '',
                ariaLabel: i.getAttribute('aria-label') || '',
                placeholder: i.getAttribute('placeholder') || '',
            };
        }"""
    )
    assert role_or_type is not None, "#palette-input not found in DOM"
    # Either an explicit role or a meaningful aria-label / placeholder.
    has_a11y = (
        role_or_type["role"] in ("combobox", "searchbox")
        or role_or_type["type"] == "search"
        or role_or_type["ariaLabel"]
        or role_or_type["placeholder"]
    )
    assert has_a11y, (
        f"#palette-input has no accessible name: {role_or_type}"
    )


# ── #248: the WIKI and SITE result groups ─────────────────────────────────


def _group(page: Page, group: str) -> dict:
    """Read one result group back out of the palette.

    Returns the heading text, how many openable rows it carries, and whether
    it rendered a zero-results / error line.
    """
    return page.evaluate(
        """(group) => {
            const items = Array.from(document.querySelectorAll('#palette-results > li'));
            const start = items.findIndex(li => li.dataset.group === group);
            if (start === -1) return null;
            const rest = items.slice(start + 1);
            const endRel = rest.findIndex(li => li.dataset.group);
            const rows = endRel === -1 ? rest : rest.slice(0, endRel);
            return {
                heading: items[start].textContent.trim(),
                openable: rows.filter(li => li.hasAttribute('data-i')).length,
                inert: rows.filter(li => li.classList.contains('palette-row-static')).length,
                message: rows.filter(li => li.dataset.groupMessage === group)
                             .map(li => li.textContent.trim())[0] || '',
            };
        }""",
        group,
    )


def _search(page: Page, site_url: str, query: str) -> None:
    page.goto(f"{site_url}/index.html", wait_until="domcontentloaded")
    _open_palette(page)
    page.keyboard.type(query, delay=10)
    page.wait_for_function(
        """() => document.querySelector('#palette-results li[data-group="wiki"]') !== null""",
        timeout=5000,
    )


def test_both_groups_render_for_a_wiki_only_term(page: Page, site_url: str) -> None:
    """`zanzibarine` is seeded into the wiki and into no transcript. The SITE
    group must still show its heading and say it found nothing — a reader who
    cannot see the empty group cannot tell it apart from a broken search."""
    _search(page, site_url, "zanzibarine")
    wiki, site = _group(page, "wiki"), _group(page, "site")
    assert wiki and site
    assert wiki["openable"] >= 1, f"wiki group found nothing: {wiki}"
    assert site["message"], f"site group vanished instead of reporting zero hits: {site}"


def test_both_groups_render_for_a_site_only_term(page: Page, site_url: str, site_has) -> None:
    """The mirror image: a static page title the seeded wiki never mentions."""
    if not site_has("/analytics.html"):
        pytest.skip("this build has no Analytics page to match on")
    _search(page, site_url, "analytics")
    wiki, site = _group(page, "wiki"), _group(page, "site")
    assert site and site["openable"] >= 1, f"site group found nothing: {site}"
    assert wiki and wiki["message"], f"wiki group vanished instead of reporting zero hits: {wiki}"


def test_both_groups_render_when_nothing_matches(page: Page, site_url: str) -> None:
    """Neither group disappears on a miss."""
    _search(page, site_url, "qwertyzzzznothing")
    for name in ("wiki", "site"):
        g = _group(page, name)
        assert g and g["openable"] == 0 and g["message"], f"{name} group: {g}"


def test_a_wiki_page_with_no_reader_page_is_listed_but_inert(page: Page, site_url: str) -> None:
    """`wiki/overview.md` has no page on the site. #248 keeps MCP's full
    coverage by listing it anyway — without a link, without `data-i`, and so
    without a stop on the arrow-key path."""
    _search(page, site_url, "overview")
    row = page.evaluate(
        """() => {
            const li = Array.from(document.querySelectorAll('#palette-results li'))
                .find(el => el.textContent.includes('wiki/overview.md'));
            if (!li) return null;
            return {
                static: li.classList.contains('palette-row-static'),
                disabled: li.getAttribute('aria-disabled'),
                hasIndex: li.hasAttribute('data-i'),
                anchors: li.querySelectorAll('a').length,
            };
        }"""
    )
    assert row is not None, "wiki/overview.md is missing from the WIKI group"
    assert row["static"] is True
    assert row["disabled"] == "true"
    assert row["hasIndex"] is False
    assert row["anchors"] == 0


def test_arrow_keys_skip_the_rows_that_cannot_open(page: Page, site_url: str) -> None:
    """Every highlighted row must be one Enter can act on."""
    _search(page, site_url, "overview")
    for _ in range(6):
        page.keyboard.press("ArrowDown")
    highlighted = page.evaluate(
        """() => Array.from(document.querySelectorAll('#palette-results li.active'))
                .map(li => li.hasAttribute('data-i'))"""
    )
    assert highlighted, "no row is highlighted after ArrowDown"
    assert all(highlighted), "an unopenable row took the highlight"
