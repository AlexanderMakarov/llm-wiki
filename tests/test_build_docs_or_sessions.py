"""build_site accepts docs-only vaults; fails only when both corpora empty (#273 B1)."""

from __future__ import annotations

from pathlib import Path

from llmwiki.build import build_site
from llmwiki.state_store import configure_state_file


def _vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "raw" / "sessions").mkdir(parents=True)
    (vault / "raw" / "docs").mkdir(parents=True)
    (vault / "wiki").mkdir(parents=True)
    configure_state_file(vault / "llmwiki-state.json")
    return vault


def test_build_site_sessions_empty_docs_present_returns_0(tmp_path: Path):
    vault = _vault(tmp_path)
    doc = vault / "raw" / "docs" / "hello" / "hello.md"
    doc.parent.mkdir(parents=True)
    doc.write_text(
        "---\ntitle: Hello\ntype: source\ntags: [raw-doc]\n---\n\n# Hello\n\nbody\n",
        encoding="utf-8",
    )
    rc = build_site(
        out_dir=vault / "site",
        raw_sessions=vault / "raw" / "sessions",
        raw_dir=vault / "raw",
        wiki_dir=vault / "wiki",
    )
    assert rc == 0
    assert (vault / "site" / "index.html").is_file()


def test_build_site_sessions_and_docs_empty_returns_2(tmp_path: Path):
    vault = _vault(tmp_path)
    rc = build_site(
        out_dir=vault / "site",
        raw_sessions=vault / "raw" / "sessions",
        raw_dir=vault / "raw",
        wiki_dir=vault / "wiki",
    )
    assert rc == 2


def test_build_site_missing_sessions_dir_still_returns_2(tmp_path: Path):
    vault = tmp_path / "vault"
    (vault / "raw" / "docs").mkdir(parents=True)
    (vault / "wiki").mkdir(parents=True)
    # no sessions dir
    (vault / "raw" / "docs" / "x.md").write_text("# X\n", encoding="utf-8")
    rc = build_site(
        out_dir=vault / "site",
        raw_sessions=vault / "raw" / "sessions",
        raw_dir=vault / "raw",
        wiki_dir=vault / "wiki",
    )
    assert rc == 2
