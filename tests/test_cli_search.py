"""Integration tests for ``llmwiki search`` (#197 Slice 2)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from llmwiki.cli import build_parser, cmd_search

REPO_ROOT = Path(__file__).resolve().parents[1]


def _make_vault(tmp_path: Path) -> Path:
    """Minimal searchable vault under tmp (never the live Obsidian vault)."""
    vault = tmp_path / "vault"
    wiki = vault / "wiki"
    entities = wiki / "entities"
    entities.mkdir(parents=True)
    (wiki / "index.md").write_text("# Wiki Index\n", encoding="utf-8")
    (wiki / "overview.md").write_text("Overview of the vault.\n", encoding="utf-8")
    (entities / "AlphaBeta.md").write_text(
        "---\ntitle: AlphaBeta\ntype: entity\n---\n\n"
        "AlphaBeta discusses reinforcement learning basics.\n"
        "Also mentions concatenate for substring checks.\n",
        encoding="utf-8",
    )
    (entities / "Other.md").write_text(
        "---\ntitle: Other\ntype: entity\n---\n\n"
        "Only the words reinforcement and learning appear separately here.\n",
        encoding="utf-8",
    )
    return vault


def _parse(*argv: str):
    return build_parser().parse_args(list(argv))


def _fingerprint(root: Path) -> dict[str, str]:
    """Relative path → content hash of every file under root."""
    out: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            rel = str(path.relative_to(root))
            out[rel] = path.read_text(encoding="utf-8")
    return out


def test_parser_registers_search_defaults():
    args = _parse("search", "RAG")
    assert args.func is cmd_search
    assert args.mode == "term"
    assert args.format == "text"
    assert args.query == "RAG"


def test_term_mode_finds_page(tmp_path: Path, capsys):
    vault = _make_vault(tmp_path)
    args = _parse("search", "AlphaBeta", "--vault", str(vault))
    assert cmd_search(args) == 0
    out = capsys.readouterr().out
    assert "AlphaBeta" in out
    assert "page(s) matching" in out


def test_term_mode_absent_exits_zero(tmp_path: Path, capsys):
    vault = _make_vault(tmp_path)
    args = _parse("search", "zzznomatchxyz", "--vault", str(vault))
    assert cmd_search(args) == 0
    out = capsys.readouterr().out
    assert "0 page(s) matching" in out


def test_phrase_mode_ranks_whole_phrase_above_partial(tmp_path: Path, capsys):
    vault = _make_vault(tmp_path)
    args = _parse(
        "search",
        "reinforcement learning",
        "--mode",
        "phrase",
        "--vault",
        str(vault),
    )
    assert cmd_search(args) == 0
    out = capsys.readouterr().out
    # Whole phrase lives only on AlphaBeta; Other has the words separately.
    alpha_i = out.index("entities/AlphaBeta.md")
    other_i = out.index("entities/Other.md")
    assert alpha_i < other_i


def test_bulk_terms_file(tmp_path: Path, capsys):
    vault = _make_vault(tmp_path)
    terms = tmp_path / "terms.txt"
    terms.write_text(
        "# comment\n\nAlphaBeta\nzzznomatchxyz\n",
        encoding="utf-8",
    )
    args = _parse("search", "--terms-file", str(terms), "--vault", str(vault))
    assert cmd_search(args) == 0
    out = capsys.readouterr().out
    assert "=== AlphaBeta ===" in out
    assert "=== zzznomatchxyz ===" in out
    assert "(no matches): 'zzznomatchxyz'" in out


def test_bulk_stdin(tmp_path: Path, monkeypatch, capsys):
    vault = _make_vault(tmp_path)
    monkeypatch.setattr(sys, "stdin", __import__("io").StringIO("AlphaBeta\nmissingterm\n"))
    args = _parse("search", "--terms-file", "-", "--vault", str(vault))
    # argparse Path("-") — cmd_search must treat "-" as stdin.
    assert cmd_search(args) == 0
    out = capsys.readouterr().out
    assert "=== AlphaBeta ===" in out
    assert "(no matches): 'missingterm'" in out


def test_format_json(tmp_path: Path, capsys):
    vault = _make_vault(tmp_path)
    args = _parse(
        "search", "AlphaBeta", "--vault", str(vault), "--format", "json"
    )
    assert cmd_search(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["term"] == "AlphaBeta"
    assert isinstance(payload["pages"], list)
    assert any("AlphaBeta" in p["path"] for p in payload["pages"])


def test_format_json_phrase(tmp_path: Path, capsys):
    vault = _make_vault(tmp_path)
    args = _parse(
        "search",
        "reinforcement learning",
        "--mode",
        "phrase",
        "--vault",
        str(vault),
        "--format",
        "json",
    )
    assert cmd_search(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["mode"] == "phrase"
    assert payload["pages"]
    assert "score" in payload["pages"][0]


def test_non_vault_clear_error(tmp_path: Path, capsys):
    missing = tmp_path / "does-not-exist"
    args = _parse("search", "x", "--vault", str(missing))
    with pytest.raises(SystemExit) as exc:
        cmd_search(args)
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "error:" in err
    assert "does not exist" in err or "not a directory" in err


def test_vault_unchanged_after_search(tmp_path: Path, capsys):
    vault = _make_vault(tmp_path)
    before = _fingerprint(vault)
    args = _parse(
        "search",
        "AlphaBeta",
        "--mode",
        "term",
        "--vault",
        str(vault),
        "--format",
        "json",
    )
    assert cmd_search(args) == 0
    capsys.readouterr()  # discard stdout
    assert _fingerprint(vault) == before


def test_subprocess_help_exits_zero():
    r = subprocess.run(
        [sys.executable, "-m", "llmwiki", "search", "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0
    assert "usage:" in r.stdout.lower()
    assert "--mode" in r.stdout
    assert "--terms-file" in r.stdout
