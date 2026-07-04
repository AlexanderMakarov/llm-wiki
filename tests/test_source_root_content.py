"""Repo-authored site content must resolve from the source checkout.

With ``LLMWIKI_ROOT`` set, ``REPO_ROOT`` points at the user's vault —
which has no ``docs/``, ``README.md``, or ``.claude/commands``. Pages
compiled from repo-authored files must therefore resolve from
``SOURCE_ROOT`` (the package's checkout), or vault builds ship a nav
that links a nonexistent ``docs/index.html``.
"""
from __future__ import annotations

from pathlib import Path

import llmwiki.build as build


def test_source_root_is_the_package_checkout():
    assert (build.SOURCE_ROOT / "llmwiki" / "build.py").is_file()
    assert (build.SOURCE_ROOT / "docs").is_dir()


def test_readme_page_renders_with_vault_repo_root(monkeypatch, tmp_path: Path):
    # Simulate a vault REPO_ROOT: empty directory, no repo files.
    monkeypatch.setattr(build, "REPO_ROOT", tmp_path)
    out = tmp_path / "site"
    out.mkdir()
    assert build.render_readme_page(out) is not None
    assert (out / "README.html").is_file()
