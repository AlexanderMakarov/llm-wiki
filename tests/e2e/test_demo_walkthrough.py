"""A reader walks the built demo site with nothing running (R12a).

Every other module in this suite drives the small synthetic corpus that
`conftest.py` seeds. This one builds the committed `demo/` vault — the
same corpus published as the public demo — and opens it the way a
reader does: `file://` URLs against the output directory.

The walk covers the surfaces a reader actually uses — home, the
projects index and a project, the sessions index and a session, topics
when the committed demo emits them, search, the graph, and candidates —
and fails on a console error, an uncaught exception, or a file the page
asked for and did not get. A full wiki ``synth`` is deferred (Slice 9),
so the committed vault may have no per-topic HTML; that is not a
walkthrough failure.

Why a file URL is the whole point: same-origin `fetch` is refused, ES
modules are refused, and a directory URL resolves to nothing. A page
that leans on any of those passes when served and fails here, which is
the failure this module exists to surface.

Links to a font service are outside the assertion: they are the one
accepted outbound request, and a reader without a network gets the same
pages in the reader's own fonts. Only requests for the site's own files
count as resources that must load.
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from playwright.sync_api import Page

REPO_ROOT = Path(__file__).resolve().parents[2]
DEMO_VAULT = REPO_ROOT / "demo"

# Pinned so the walk renders the same paths wherever it runs — the same
# value `pages.yml` publishes with.
DEMO_LOCAL_ROOT = "/home/user"


@pytest.fixture(scope="session")
def demo_site(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build the committed demo vault once and return its output dir."""
    if not (DEMO_VAULT / "raw" / "sessions").is_dir():
        pytest.skip("demo vault is not present in this checkout")
    out = tmp_path_factory.mktemp("llmwiki_demo_site") / "site"
    proc = subprocess.run(
        [
            sys.executable, "-m", "llmwiki", "build",
            "--vault", str(DEMO_VAULT),
            "--out", str(out),
            "--local-root", DEMO_LOCAL_ROOT,
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, (
        f"demo build failed ({proc.returncode}):\n{proc.stdout}\n{proc.stderr}"
    )
    return out


def _first_page(directory: Path, *, recursive: bool = False) -> Path | None:
    """Lowest-named HTML page in `directory`, ignoring its own index."""
    if not directory.is_dir():
        return None
    pattern = "**/*.html" if recursive else "*.html"
    pages = sorted(p for p in directory.glob(pattern) if p.name != "index.html")
    return pages[0] if pages else None


class _Recorder:
    """Collects everything that counts as the page failing the reader."""

    def __init__(self) -> None:
        self.problems: list[str] = []
        self._where = ""

    def watch(self, page: Page) -> None:
        page.on(
            "console",
            lambda msg: self._note(f"console.error: {msg.text}")
            if msg.type == "error"
            else None,
        )
        page.on("pageerror", lambda exc: self._note(f"uncaught: {exc}"))
        page.on(
            "requestfailed",
            lambda req: self._note(f"resource did not load: {req.url} ({req.failure})")
            if req.url.startswith("file://")
            else None,
        )

    def at(self, surface: str) -> None:
        self._where = surface

    def _note(self, detail: str) -> None:
        self.problems.append(f"[{self._where}] {detail}")


@pytest.fixture()
def walk(page: Page) -> Iterator[_Recorder]:
    recorder = _Recorder()
    recorder.watch(page)
    yield recorder


def test_reader_walks_the_built_demo_site_as_files(
    page: Page, walk: _Recorder, demo_site: Path
) -> None:
    """Open every reader-facing surface from disk and end with a clean
    console and every site resource loaded."""
    base = demo_site.as_uri().rstrip("/")

    def visit(surface: str, rel: str) -> None:
        walk.at(surface)
        page.goto(f"{base}/{rel}", wait_until="load")
        page.wait_for_timeout(400)
        assert page.locator("header.nav").first.count() > 0, (
            f"{surface} ({rel}) rendered without the site nav"
        )

    visit("home", "index.html")
    visit("projects index", "projects/index.html")

    project = _first_page(demo_site / "projects")
    assert project is not None, "demo build emitted no project pages"
    visit("project page", project.relative_to(demo_site).as_posix())

    visit("sessions index", "sessions/index.html")

    session = _first_page(demo_site / "sessions", recursive=True)
    assert session is not None, "demo build emitted no session pages"
    visit("session page", session.relative_to(demo_site).as_posix())

    topics_index = demo_site / "topics" / "index.html"
    if topics_index.is_file():
        visit("topics index", "topics/index.html")
    topic = _first_page(demo_site / "topics")
    if topic is not None:
        visit("topic page", topic.relative_to(demo_site).as_posix())

    visit("graph", "graph.html")
    assert page.locator("canvas").first.count() > 0, (
        "graph.html rendered no canvas — the vendored viewer did not run"
    )

    visit("candidates", "candidates.html")

    # Search last: the index arrives over the same origin as the page,
    # which is the request a file URL refuses when it is a `fetch`.
    walk.at("search")
    page.goto(f"{base}/index.html", wait_until="load")
    page.locator("body").click(position={"x": 1, "y": 1})
    page.keyboard.press("ControlOrMeta+k")
    page.wait_for_function(
        "() => document.getElementById('palette')?.classList.contains('open') === true",
        timeout=3000,
    )
    page.keyboard.type("wiki", delay=20)
    page.wait_for_function(
        "() => document.querySelectorAll('#palette-results li').length > 0",
        timeout=5000,
    )

    assert not walk.problems, (
        "the demo site does not hold up when opened as files:\n  "
        + "\n  ".join(walk.problems[:20])
    )
