"""Vault-path audit: commands must act on the configured vault, not the repo.

`REPO_ROOT` is the code checkout; the user's content lives in a vault
resolved from `--vault` or `config.json` `vault.default_path`. `lint`,
`export`, and `graph` used their module-level `REPO_ROOT / "wiki"|"site"`
defaults, so with a vault configured they silently read/wrote the git
clone's seed demo content instead of the user's wiki.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from llmwiki import REPO_ROOT
from llmwiki import cli as cli_mod


def _page(text: str = "") -> str:
    return f"---\ntitle: \"Only\"\ntype: concept\n---\n\n# Only\n\n{text}\n"


def _vault_with_wiki(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "wiki").mkdir(parents=True)
    (vault / "wiki" / "Only.md").write_text(_page("[[Other]]"), encoding="utf-8")
    (vault / "wiki" / "Other.md").write_text(_page("[[Only]]"), encoding="utf-8")
    return vault


# ── lint ────────────────────────────────────────────────────────────────

def test_lint_scans_the_configured_vault(tmp_path, capsys):
    """`lint --vault` must lint the vault's wiki, not the repo's."""
    vault = _vault_with_wiki(tmp_path)
    args = cli_mod.build_parser().parse_args(["lint", "--vault", str(vault)])
    rc = args.func(args)
    out = capsys.readouterr().out
    assert rc in (0, 1)
    # The vault holds exactly two pages; the repo's seed wiki holds many.
    assert "scanned 2 pages" in out


def test_lint_explicit_wiki_dir_still_wins(tmp_path, capsys):
    """An explicit --wiki-dir overrides the vault (it is the narrower flag)."""
    vault = _vault_with_wiki(tmp_path)
    other = tmp_path / "elsewhere"
    other.mkdir()
    (other / "Solo.md").write_text(_page(), encoding="utf-8")
    args = cli_mod.build_parser().parse_args(
        ["lint", "--vault", str(vault), "--wiki-dir", str(other)]
    )
    args.func(args)
    assert "scanned 1 pages" in capsys.readouterr().out


# ── graph ───────────────────────────────────────────────────────────────

def test_graph_writes_under_the_configured_vault(tmp_path, capsys):
    """`graph --vault` must graph the vault's wiki and write into the vault."""
    vault = _vault_with_wiki(tmp_path)
    args = cli_mod.build_parser().parse_args(
        ["graph", "--vault", str(vault), "--format", "json", "--engine", "builtin"]
    )
    rc = args.func(args)
    capsys.readouterr()
    assert rc == 0
    assert (vault / "graph" / "graph.json").is_file()


# ── export ──────────────────────────────────────────────────────────────

def test_export_reads_and_writes_the_configured_vault(tmp_path, capsys):
    """`export --vault` must read the vault's raw/sessions and write its site."""
    vault = tmp_path / "vault"
    sessions = vault / "raw" / "sessions"
    sessions.mkdir(parents=True)
    (sessions / "2026-01-01T00-00-demo-x.md").write_text(
        '---\ntitle: "Demo"\nproject: demo\nslug: demo-x\ndate: 2026-01-01\n'
        '---\n\n## Summary\n\nA demo session.\n',
        encoding="utf-8",
    )
    args = cli_mod.build_parser().parse_args(
        ["export", "llms-txt", "--vault", str(vault)]
    )
    rc = args.func(args)
    capsys.readouterr()
    assert rc == 0
    assert (vault / "site" / "llms.txt").is_file()


# ── shared content-root resolver ────────────────────────────────────────

def test_content_root_prefers_explicit_vault(tmp_path):
    vault = tmp_path / "v"
    (vault / "wiki").mkdir(parents=True)
    args = cli_mod.build_parser().parse_args(["lint", "--vault", str(vault)])
    assert cli_mod._content_root(args) == vault.resolve()


def test_content_root_falls_back_to_configured_default(tmp_path, monkeypatch):
    """No --vault, but config.json names one: the config vault still wins."""
    vault = tmp_path / "configured"
    (vault / "wiki").mkdir(parents=True)
    monkeypatch.setattr(
        "llmwiki.config_schedule.load_default_vault_path", lambda: vault
    )
    args = cli_mod.build_parser().parse_args(["lint"])
    assert cli_mod._content_root(args) == vault.resolve()


def test_content_root_uses_repo_when_no_vault_configured(monkeypatch):
    """Demo/dev mode: no vault anywhere means the repo is the content root."""
    monkeypatch.setattr(
        "llmwiki.config_schedule.load_default_vault_path", lambda: None
    )
    args = cli_mod.build_parser().parse_args(["lint"])
    assert cli_mod._content_root(args) == REPO_ROOT


def test_content_root_warns_when_configured_vault_is_unusable(tmp_path, monkeypatch, capsys):
    """A configured-but-missing vault must not silently target the git clone."""
    missing = tmp_path / "gone"
    monkeypatch.setattr(
        "llmwiki.config_schedule.load_default_vault_path", lambda: missing
    )
    args = cli_mod.build_parser().parse_args(["lint"])
    root = cli_mod._content_root(args)
    err = capsys.readouterr().err
    assert root == REPO_ROOT
    assert "vault" in err.lower()
    assert str(missing) in err
