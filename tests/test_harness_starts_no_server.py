"""The project serves the site for nobody, including itself (R12, R12a).

# @layer: integration
# @spec: 008-make-product-explain-itself
# @regression

The browser suite reached the site over HTTP while the product was being
changed to need no server, so every check passed and none exercised the
claim. These tests pin the harness itself: the e2e suite, the Playwright
config, the editor launch task and the workflows address built files, and
nothing among them starts something that answers requests.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from llmwiki import REPO_ROOT

E2E_DIR = REPO_ROOT / "tests" / "e2e"

# Named ways this repository has started something in front of the output.
# A list of literals only catches what someone thought to write down, so the
# loopback-address check below carries the general case.
_SERVER_TOKENS = (
    "http.server",
    "HTTPServer",
    "serve_forever",
    "webServer",
    "--base-url",
    "LLMWIKI_BASE_URL",
    "socketserver",
    "uvicorn",
)

# Any harness file addressing a local port is reaching the site over HTTP,
# whatever started it. This is the check that does not depend on predicting
# the mechanism.
_LOOPBACK_URL = re.compile(r"https?://(?:127\.0\.0\.1|localhost|0\.0\.0\.0|\[::1\])(?::\d+)?")


def _harness_files() -> list[Path]:
    """Every file that decides how the browser checks reach the site."""
    files = [
        p for p in E2E_DIR.rglob("*.py") if "__pycache__" not in p.parts
    ]
    files += sorted((REPO_ROOT / ".github" / "workflows").glob("*.yml"))
    files += [
        REPO_ROOT / "playwright.config.ts",
        REPO_ROOT / ".claude" / "launch.json",
    ]
    files += sorted((REPO_ROOT / "tests" / "agents").glob("*.ts"))
    return [p for p in files if p.is_file()]


@pytest.mark.parametrize("token", _SERVER_TOKENS)
def test_no_harness_file_puts_a_server_in_front_of_the_site(token: str):
    # @regression
    guilty = [
        str(p.relative_to(REPO_ROOT))
        for p in _harness_files()
        if token in p.read_text(encoding="utf-8", errors="replace")
    ]
    assert not guilty, (
        f"{token!r} is back in the browser harness: {guilty}. "
        f"The built site is opened as files; nothing serves it."
    )


def test_the_e2e_suite_navigates_by_file_url():
    """`site_url` is the suite's one address for a page, and it is a
    `file://` prefix — so a page that only works when served fails."""
    conftest = (E2E_DIR / "conftest.py").read_text(encoding="utf-8")
    assert "def site_url(" in conftest, "the e2e suite lost its site_url fixture"
    assert "as_uri()" in conftest, "site_url no longer derives a file:// address"

    stragglers = [
        str(p.relative_to(REPO_ROOT))
        for p in E2E_DIR.rglob("*.py")
        if "__pycache__" not in p.parts
        and "base_url" in p.read_text(encoding="utf-8", errors="replace")
    ]
    assert not stragglers, (
        f"these modules still address pages through pytest-playwright's "
        f"`base_url`, which resolves to a served origin: {stragglers}"
    )


def test_no_harness_file_addresses_a_local_port():
    """A loopback URL means the site is being reached over HTTP.

    The token list above names mechanisms someone already used. This catches
    the general case — any server, any library, however it was started —
    because the address is the part that cannot be hidden.
    """
    # This file lists the same addresses as strings it forbids from appearing
    # in built HTML. It is a guard, not a harness reaching a server.
    exempt = {REPO_ROOT / "tests" / "e2e" / "test_build_artifacts.py"}

    offenders = []
    for path in _harness_files():
        if path in exempt:
            continue
        for match in _LOOPBACK_URL.finditer(path.read_text(encoding="utf-8")):
            offenders.append(f"{path.relative_to(REPO_ROOT)}: {match.group(0)}")
    assert not offenders, "harness reaches the site over HTTP:\n  " + "\n  ".join(offenders)
