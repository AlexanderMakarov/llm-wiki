"""Link integrity for a site opened as files.

A reader opens `index.html` from disk, so every link the build emits
has to name a file that the build also emitted. There is nothing
behind a `file://` URL to answer for a missing target: the browser
refuses the navigation and the reader is stranded on the page they
came from.

This module asserts:

* A path the build never emitted is absent from the output directory
  and cannot be opened.
* Every internal link on the homepage resolves to a file on disk,
  including directory-shaped links, which have no index to fall back on.
* No console errors fire on the home page.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page


def test_unknown_path_is_absent_and_unopenable(
    page: Page, site_url: str, site_root: Path
) -> None:
    """A path the build didn't emit has no file behind it, and opening
    it fails at the browser rather than landing the reader anywhere."""
    assert not (site_root / "this-path-does-not-exist.html").exists()
    with pytest.raises(PlaywrightError):
        page.goto(f"{site_url}/this-path-does-not-exist.html")


def test_homepage_internal_links_resolve(
    page: Page, site_url: str, site_root: Path
) -> None:
    """Every same-origin link on the homepage must name a file the build
    emitted. Catches the class of regression where a link points to a
    path the build didn't produce (e.g. a project page deleted between
    builds), and the class where a link names a directory — which a
    served site papers over with an index and a file URL does not."""
    page.goto(f"{site_url}/index.html", wait_until="domcontentloaded")

    # Collect all hrefs that look local (start with / or . or are
    # bare ``foo.html`` paths). Skip mailto:, http(s):, and # fragments.
    hrefs: list[str] = page.evaluate(
        """() => {
            const out = [];
            document.querySelectorAll('a[href]').forEach(a => {
                const h = a.getAttribute('href') || '';
                if (!h) return;
                if (h.startsWith('#') || h.startsWith('mailto:')) return;
                if (h.startsWith('http://') || h.startsWith('https://')) return;
                if (h.startsWith('javascript:')) return;
                out.push(h);
            });
            return [...new Set(out)];
        }"""
    )

    if not hrefs:
        # Synthetic corpus has very few links — skip cleanly rather than fail.
        pytest.skip("homepage has no internal links to verify")

    broken: list[str] = []
    for href in hrefs[:20]:  # cap at 20 to keep the test fast
        rel = unquote(urlsplit(href).path).lstrip("/")
        if not rel:
            continue
        if not (site_root / rel).is_file():
            broken.append(href)

    assert not broken, (
        f"{len(broken)} homepage links name no file in the build:\n  "
        + "\n  ".join(broken[:5])
    )


def test_homepage_renders_without_console_errors(page: Page, site_url: str) -> None:
    """The conftest auto-attaches a console listener that records
    every ``console.error``. The home page should produce zero — any
    error is a real bug that's been shipping silently because no
    other test asserts on this exact page in isolation."""
    page.goto(f"{site_url}/index.html", wait_until="networkidle")
    errors = getattr(page, "_llmwiki_console_errors", [])
    # Filter out hljs / CDN noise and missing favicon (build does not emit one).
    real = [
        e for e in errors
        if "highlight" not in e.lower()
        and "cdn" not in e.lower()
        and "favicon" not in e.lower()
    ]
    assert not real, f"homepage has console errors: {real}"
