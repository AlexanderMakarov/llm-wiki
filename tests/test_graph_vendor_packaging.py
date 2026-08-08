"""Packaging regression for vendored graph assets (#127).

# @layer: integration
# @spec: 007-graph-viewer-external-assets
# @regression

Repo checkouts always have ``llmwiki/vendor/vis-network.min.js`` on disk, so
``VIS_NETWORK_VENDOR.is_file()`` alone cannot catch a wheel that drops the
asset.  This module asserts setuptools ``package-data`` declares the vendor
tree and, when ``build`` is available, builds a wheel and lists its contents.
"""

from __future__ import annotations

import importlib.util
import re
import shutil
import subprocess
import sys
import zipfile
from importlib.resources import files
from pathlib import Path

import pytest

from llmwiki import REPO_ROOT
from llmwiki.graph import VIS_NETWORK_VENDOR

PYPROJECT = REPO_ROOT / "pyproject.toml"
VENDOR_WHEEL_PATH = "llmwiki/vendor/vis-network.min.js"
_BUILD_AVAILABLE = importlib.util.find_spec("build") is not None


@pytest.fixture(scope="module")
def pyproject() -> str:
    return PYPROJECT.read_text(encoding="utf-8")


def test_pyproject_package_data_includes_vendor_assets(pyproject: str):
    # @regression
    """setuptools must ship vendored JS beside the installed llmwiki package."""
    block = re.search(
        r"\[tool\.setuptools\.package-data\]\s*\nllmwiki\s*=\s*\[(.*?)\]",
        pyproject,
        re.DOTALL,
    )
    assert block is not None, "pyproject.toml missing [tool.setuptools.package-data] llmwiki list"
    entries = block.group(1)
    assert "vendor/*.js" in entries or "vendor/vis-network.min.js" in entries, (
        "package-data must include vendor JS globs — pip installs otherwise "
        "crash in write_html() when copying vis-network.min.js"
    )
    assert "vendor/NOTICE" in entries or "vendor/*" in entries, (
        "package-data must include vendor/NOTICE (or vendor/*) for attribution"
    )


def test_vendored_vis_network_exists_in_repo():
    # @regression
    assert VIS_NETWORK_VENDOR.is_file(), (
        "llmwiki/vendor/vis-network.min.js missing from repo checkout"
    )


def test_vendored_vis_network_available_via_importlib_resources():
    # @regression
    vendor_path = files("llmwiki") / "vendor" / "vis-network.min.js"
    assert vendor_path.is_file(), (
        "importlib.resources cannot see llmwiki/vendor/vis-network.min.js — "
        "check package-data and editable-install layout"
    )
    assert vendor_path.stat().st_size >= 100_000


@pytest.mark.skipif(not _BUILD_AVAILABLE, reason="build package not installed")
def test_wheel_includes_vendored_vis_network(tmp_path: Path):
    # @regression
    """A built wheel must contain llmwiki/vendor/vis-network.min.js."""
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    proc = subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--outdir", str(dist_dir)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, (
        "python -m build --wheel failed:\n"
        f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )
    wheels = sorted(dist_dir.glob("*.whl"))
    assert wheels, f"no wheel produced under {dist_dir}"
    with zipfile.ZipFile(wheels[-1]) as zf:
        names = zf.namelist()
    assert VENDOR_WHEEL_PATH in names, (
        f"{VENDOR_WHEEL_PATH!r} missing from wheel — pip installs will crash "
        f"on llmwiki graph/build. Wheel entries sample: {names[:12]!r}…"
    )


def test_wheel_build_skips_cleanly_when_build_unavailable():
    # Documents the weaker fallback when CI/dev env lacks `build`.
    if _BUILD_AVAILABLE:
        pytest.skip("build is installed — test_wheel_includes_vendored_vis_network covers this")
    assert shutil.which(sys.executable), "interpreter missing"
    assert PYPROJECT.is_file()
