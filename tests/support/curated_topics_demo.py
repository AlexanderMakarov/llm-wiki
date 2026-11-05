"""Shared harness for #248 curated-topics acceptance tests."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

import llmwiki.build as build_mod
from llmwiki.build import build_site

REPO_ROOT = Path(__file__).resolve().parents[2]
DEMO = REPO_ROOT / "demo"

# Committed demo curated pages (7 entities + 4 concepts after hollow cleanup).
DEMO_CURATED: dict[str, list[str]] = {
    "entities": [
        "Claude Code",
        "Codex CLI",
        "Frontmatter",
        "GitHub Actions",
        "GitHub Pages",
        "Obsidian",
        "Ollama",
    ],
    "concepts": [
        "Adapters",
        "Knowledge Graph",
        "Observability",
        "Static Site",
    ],
}


def copy_demo_vault(tmp_path: Path) -> Path:
    """Private copy of committed ``demo/`` wiki + raw (never writes into ``demo/``)."""
    vault = tmp_path / "vault"
    shutil.copytree(DEMO / "wiki", vault / "wiki")
    shutil.copytree(DEMO / "raw", vault / "raw")
    return vault


def run_build(vault: Path, out: Path, monkeypatch: pytest.MonkeyPatch) -> int:
    out.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(build_mod, "REPO_ROOT", vault)
    monkeypatch.setattr(build_mod, "SOURCE_ROOT", vault)
    monkeypatch.setattr(build_mod, "RAW_DIR", vault / "raw")
    monkeypatch.setattr(build_mod, "RAW_SESSIONS", vault / "raw" / "sessions")
    monkeypatch.setattr(build_mod, "DEFAULT_OUT_DIR", out)
    monkeypatch.setattr(build_mod, "PROJECTS_META_DIR", vault / "wiki" / "projects")
    monkeypatch.setattr(build_mod, "compile_docs_site", lambda *a, **k: [])
    return build_site(
        out_dir=out,
        raw_sessions=vault / "raw" / "sessions",
        raw_dir=vault / "raw",
        wiki_dir=vault / "wiki",
    )


@pytest.fixture(scope="module")
def curated_demo_build(tmp_path_factory: pytest.TempPathFactory, request: pytest.FixtureRequest) -> Path:
    """One ``build_site()`` over a private demo vault copy (module-scoped)."""
    tmp_path = tmp_path_factory.mktemp("curated_topics_demo")
    vault = copy_demo_vault(tmp_path)
    out = tmp_path / "site"
    mp = pytest.MonkeyPatch()
    request.addfinalizer(mp.undo)
    rc = run_build(vault, out, mp)
    assert rc == 0, "demo vault build failed"
    return out
