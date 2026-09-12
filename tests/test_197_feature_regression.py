"""End-to-end / regression gaps for #197 (Slice 6).

# @layer: integration
# @spec: 197-search-quality-eval
# @regression

Fills whole-feature gaps not owned by Slice 1–4 suites:
CLI↔MCP result agreement, CLI lint on crafted defects, bulk phrase empty
entries, vault content immutability, and ``query`` still distinct/working.

Does **not** re-assert demo MRR / rank-1 baselines (see ``test_197_acceptance``).
Never targets a live Obsidian vault — only ``tmp_path`` fixtures.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from unittest.mock import patch

from llmwiki.cli import build_parser, cmd_query, cmd_search
from llmwiki.mcp.server import tool_wiki_search

# @spec: 197-search-quality-eval
# @regression


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _make_parity_vault(tmp_path: Path) -> Path:
    """Vault where phrase ranking and term match are both observable."""
    vault = tmp_path / "vault"
    wiki = vault / "wiki"
    entities = wiki / "entities"
    entities.mkdir(parents=True)
    _write(wiki / "index.md", "# Wiki Index\n")
    _write(wiki / "overview.md", "Overview of the vault.\n")
    _write(
        entities / "AlphaBeta.md",
        "---\ntitle: AlphaBeta\ntype: entity\n---\n\n"
        "AlphaBeta discusses reinforcement learning basics.\n"
        "Also mentions concatenate for substring checks.\n",
    )
    _write(
        entities / "Other.md",
        "---\ntitle: Other\ntype: entity\n---\n\n"
        "Only the words reinforcement and learning appear separately here.\n",
    )
    return vault


def _fingerprint_content(vault: Path) -> dict[str, str]:
    """wiki/ + raw/ file bodies only (ops sidecars may update on lint)."""
    out: dict[str, str] = {}
    for sub in ("wiki", "raw"):
        root = vault / sub
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if path.is_file():
                out[str(path.relative_to(vault))] = path.read_text(encoding="utf-8")
    return out


def _parse(*argv: str):
    return build_parser().parse_args(list(argv))


def _cli_match_paths(vault: Path, term: str, capsys) -> list[str]:
    args = _parse(
        "search", term, "--vault", str(vault), "--format", "json", "--mode", "term"
    )
    assert cmd_search(args) == 0
    payload = json.loads(capsys.readouterr().out)
    return [p["path"] for p in payload["pages"]]


def _mcp_match_paths(vault: Path, term: str) -> list[str]:
    with patch("llmwiki.mcp.server.REPO_ROOT", vault):
        result = tool_wiki_search({"term": term, "format": "json", "mode": "match"})
    assert result.get("isError") is not True
    payload = json.loads(result["content"][0]["text"])
    return [p["path"] for p in payload["pages"]]


def _cli_phrase_paths(vault: Path, phrase: str, capsys) -> list[str]:
    args = _parse(
        "search",
        phrase,
        "--vault",
        str(vault),
        "--format",
        "json",
        "--mode",
        "phrase",
    )
    assert cmd_search(args) == 0
    payload = json.loads(capsys.readouterr().out)
    return [p["path"] for p in payload["pages"]]


def _mcp_extract_paths(vault: Path, phrase: str) -> list[str]:
    with patch("llmwiki.mcp.server.REPO_ROOT", vault):
        result = tool_wiki_search({"question": phrase, "max_pages": 5})
    assert result.get("isError") is not True
    text = result["content"][0]["text"]
    return re.findall(r"^## `([^`]+)` \(score:", text, re.MULTILINE)


def test_cli_term_paths_match_mcp_for_same_vault(tmp_path: Path, capsys):
    """R1: CLI search results match the agent interface for the same input."""
    # @spec: 197-search-quality-eval
    # @regression
    vault = _make_parity_vault(tmp_path)
    term = "AlphaBeta"
    cli_paths = _cli_match_paths(vault, term, capsys)
    mcp_paths = _mcp_match_paths(vault, term)
    assert cli_paths
    assert cli_paths == mcp_paths


def test_cli_phrase_order_matches_mcp_and_ranks_whole_phrase(
    tmp_path: Path, capsys
):
    """R1: phrase/extract parity + whole phrase ranks above partial words."""
    # @spec: 197-search-quality-eval
    # @regression
    vault = _make_parity_vault(tmp_path)
    phrase = "reinforcement learning"
    cli_paths = _cli_phrase_paths(vault, phrase, capsys)
    mcp_paths = _mcp_extract_paths(vault, phrase)
    assert cli_paths == mcp_paths
    assert "wiki/entities/AlphaBeta.md" in cli_paths
    assert "wiki/entities/Other.md" in cli_paths
    assert cli_paths.index("wiki/entities/AlphaBeta.md") < cli_paths.index(
        "wiki/entities/Other.md"
    )


def test_bulk_phrase_file_states_empty_entries(tmp_path: Path, capsys):
    """R1: bulk phrase list reports per entry and names empties plainly."""
    # @spec: 197-search-quality-eval
    # @regression
    vault = _make_parity_vault(tmp_path)
    phrases = tmp_path / "phrases.txt"
    phrases.write_text(
        "reinforcement learning\nzzznophrasexyz\n",
        encoding="utf-8",
    )
    args = _parse(
        "search",
        "--mode",
        "phrase",
        "--terms-file",
        str(phrases),
        "--vault",
        str(vault),
    )
    assert cmd_search(args) == 0
    out = capsys.readouterr().out
    assert "=== reinforcement learning ===" in out
    assert "=== zzznophrasexyz ===" in out
    assert "(no matches): 'zzznophrasexyz'" in out


def test_cli_lint_title_ambiguity_fires_on_crafted_defect(
    tmp_path: Path, capsys
):
    """R3: CLI lint surfaces title_ambiguity on a purpose-built vault."""
    # @spec: 197-search-quality-eval
    # @regression
    vault = tmp_path / "ambig"
    long_body = ("lorem ipsum dolor sit amet " * 80) + "\n"
    _write(
        vault / "wiki" / "entities" / "Config.md",
        f"---\ntitle: Configuration\ntype: entity\n---\n\n{long_body}",
    )
    _write(
        vault / "wiki" / "entities" / "Aaa.md",
        "---\ntitle: Configuration Guide\ntype: entity\n---\n\nConfiguration\n",
    )
    args = _parse(
        "lint",
        "--vault",
        str(vault),
        "--rules",
        "title_ambiguity",
        "--json",
    )
    rc = args.func(args)
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    warnings = [
        i
        for i in payload["issues"]
        if i.get("rule") == "title_ambiguity" and i.get("severity") == "warning"
    ]
    assert warnings, payload["issues"]
    config = [w for w in warnings if "Config.md" in w.get("page", "")]
    assert config
    assert "outranked by" in config[0]["message"]
    assert "Aaa.md" in config[0]["message"]


def test_cli_lint_page_findability_and_consistency_run_clean(
    tmp_path: Path, capsys
):
    """R3: CLI lint runs the other two findability rules on a healthy vault."""
    # @spec: 197-search-quality-eval
    # @regression
    vault = tmp_path / "healthy"
    _write(
        vault / "wiki" / "entities" / "Keep.md",
        "---\ntitle: UniqueKeepTitle\ntype: entity\n---\n\nBody.\n",
    )
    _write(
        vault / "raw" / "sessions" / "2026-01-01T00-00-alpha-session.md",
        "---\ntitle: Alpha\ntype: source\n---\n\n"
        "Conversation mentions PlantedLexeme and WidgetFactory.\n",
    )
    args = _parse(
        "lint",
        "--vault",
        str(vault),
        "--rules",
        "page_findability,search_consistency",
        "--json",
    )
    assert args.func(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert "page_findability" in payload["ran"]
    assert "search_consistency" in payload["ran"]
    errors = [i for i in payload["issues"] if i.get("severity") == "error"]
    assert errors == []
    infos = [i["message"] for i in payload["issues"] if i.get("severity") == "info"]
    assert any(m.startswith("present terms:") for m in infos)
    assert any(m.startswith("absent terms:") for m in infos)
    assert any("survival share:" in m for m in infos)


def test_vault_content_unchanged_after_search_and_findability_lint(
    tmp_path: Path, capsys
):
    """R1/R3: search + findability lint never rewrite wiki/ or raw/."""
    # @spec: 197-search-quality-eval
    # @regression
    vault = _make_parity_vault(tmp_path)
    _write(
        vault / "raw" / "sessions" / "2026-01-01T00-00-s.md",
        "---\ntitle: S\ntype: source\n---\n\nSessionTokenABCDEF\n",
    )
    before = _fingerprint_content(vault)

    assert cmd_search(
        _parse("search", "AlphaBeta", "--vault", str(vault), "--format", "json")
    ) == 0
    capsys.readouterr()

    lint_args = _parse(
        "lint",
        "--vault",
        str(vault),
        "--rules",
        "page_findability,title_ambiguity,search_consistency",
        "--json",
    )
    assert lint_args.func(lint_args) == 0
    capsys.readouterr()

    assert _fingerprint_content(vault) == before


def test_query_command_still_registered_and_graceful(capsys):
    """R1: natural-language ``query`` remains distinct from ``search``."""
    # @spec: 197-search-quality-eval
    # @regression
    search_args = _parse("search", "x")
    query_args = _parse("query", "what", "is", "this")
    assert search_args.func is cmd_search
    assert query_args.func is cmd_query
    assert search_args.func is not query_args.func

    rc = cmd_query(query_args)
    err = capsys.readouterr().err
    # graphify optional: 0 when installed, 2 with install hint when not.
    assert rc in (0, 2)
    if rc == 2:
        assert "graphify" in err.lower()
    assert "Traceback" not in err
