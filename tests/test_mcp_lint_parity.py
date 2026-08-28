"""An agent asking about wiki quality gets the same answer a person does (#150, R9).

``wiki_lint`` used to be a private reimplementation: 2 hand-rolled checks
against the registry's 17, with a stricter broken-link test (exact stem
match, no slug normalisation, no anchor stripping) and a narrower orphan
test — so it over-reported on both, and its advertised description promised
contradictions and stale summaries it had never implemented. Two accounts of
one wiki, and the assistant's was the wrong one.

The central assertion of this module is a single equality: for the same
vault, ``tool_wiki_lint`` returns exactly the payload ``lint --json`` prints.
Everything else here defends one way that equality could rot — an opt-out
honoured on one route only, a threshold honoured on one route only, or an
unrecognised rule name swallowed into a clean report.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from llmwiki.cli import build_parser
from llmwiki.lint import REGISTRY, rules  # noqa: F401 — force rule registration
from llmwiki.mcp.server import TOOLS, tool_wiki_lint

# ─── Fixtures ──────────────────────────────────────────────────────────


def _source(wiki: Path, slug: str, body: str) -> None:
    path = wiki / "sources" / f"{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'---\ntitle: "{slug}"\ntype: source\n---\n\n{body}\n', encoding="utf-8"
    )


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    """A vault root with findings from several rules, not just one.

    Parity is only worth asserting over a payload with something in it, and
    over more than the two checks the private implementation used to run:
    ``[[Twice]]`` is a deliberate harvest decline at the stock threshold and
    a genuine gap at ``min_refs=1``, ``[[Ghost]]`` is dangling at every
    threshold, and the frontmatter-free page is an error-severity finding.
    """
    wiki = tmp_path / "wiki"
    _source(wiki, "a", "See [[Twice]] and [[Thrice]].")
    _source(wiki, "b", "See [[Twice]] and [[Thrice]].")
    _source(wiki, "c", "See [[Thrice]] and [[Ghost]].")
    (wiki / "entities").mkdir(parents=True, exist_ok=True)
    (wiki / "entities" / "Bad.md").write_text(
        "No frontmatter at all.\n", encoding="utf-8"
    )
    (wiki / "overview.md").write_text("# Overview\n", encoding="utf-8")
    return tmp_path


def _declare(root: Path, declaration: object) -> None:
    """Write ``<root>/llmwiki.json`` carrying ``lint.disabled_rules``."""
    (root / "llmwiki.json").write_text(
        json.dumps({"lint": {"disabled_rules": declaration}}), encoding="utf-8"
    )


def _via_cli(root: Path, *flags: str, capsys) -> dict:
    """What a person sees: ``llmwiki lint --json`` over ``<root>/wiki``."""
    args = build_parser().parse_args(
        ["lint", "--wiki-dir", str(root / "wiki"), "--json", *flags]
    )
    assert args.func(args) == 0
    return json.loads(capsys.readouterr().out)


def _via_mcp(root: Path, args: dict | None = None) -> dict:
    """What an assistant sees, resolved against the same vault root."""
    with patch("llmwiki.mcp.server.REPO_ROOT", root):
        result = tool_wiki_lint(args or {})
    assert result["isError"] is False, result["content"][0]["text"]
    return json.loads(result["content"][0]["text"])


def _mcp_error(root: Path, args: dict) -> str:
    with patch("llmwiki.mcp.server.REPO_ROOT", root):
        result = tool_wiki_lint(args)
    assert result["isError"] is True
    return result["content"][0]["text"]


# ─── The central parity assertion ──────────────────────────────────────


def test_the_two_routes_return_the_same_payload(vault: Path, capsys):
    """R9's first criterion, stated as an equality rather than a resemblance."""
    assert _via_mcp(vault) == _via_cli(vault, capsys=capsys)


def test_the_payload_is_worth_comparing(vault: Path, capsys):
    """A guard on the test above: two empty reports are also equal.

    Pins that the tool now runs the whole registry rather than the two
    hand-rolled checks it used to — findings from more than one rule, and
    an error severity the private implementation could not produce.
    """
    payload = _via_mcp(vault)
    assert set(payload) == {
        "summary", "issues", "total_pages", "disabled_rules", "ran"
    }
    assert payload["total_pages"] > 0
    assert len({issue["rule"] for issue in payload["issues"]}) > 1
    assert payload["summary"].get("error", 0) > 0


# ─── The vault's opt-out, honoured on both routes ──────────────────────


def test_the_two_routes_agree_about_a_vault_opt_out(vault: Path, capsys):
    """R9's second criterion: a check a vault switches off is switched off
    for the assistant too, and named as skipped where it can see it."""
    _declare(vault, {"link_integrity": "targets are materialized elsewhere"})

    payload = _via_mcp(vault)

    assert payload == _via_cli(vault, capsys=capsys)
    assert payload["disabled_rules"] == {
        "link_integrity": "targets are materialized elsewhere"
    }
    assert [i for i in payload["issues"] if i["rule"] == "link_integrity"] == []


def test_the_opt_out_actually_removed_something(vault: Path, capsys):
    """Otherwise the agreement above could be two routes finding nothing."""
    before = _via_mcp(vault)
    _declare(vault, ["link_integrity"])
    after = _via_mcp(vault)

    assert [i for i in before["issues"] if i["rule"] == "link_integrity"]
    assert before["disabled_rules"] == {}
    assert after["disabled_rules"] == {"link_integrity": ""}
    assert len(after["issues"]) < len(before["issues"])


def test_every_rule_disabled_is_not_reported_as_clean(vault: Path, capsys):
    """The dishonest case the whole feature exists to avoid, over MCP."""
    _declare(vault, sorted(REGISTRY))

    payload = _via_mcp(vault)

    assert payload == _via_cli(vault, capsys=capsys)
    assert payload["issues"] == []
    assert set(payload["disabled_rules"]) == set(REGISTRY)


# ─── The threshold, honoured on both routes ────────────────────────────


@pytest.mark.parametrize("min_refs", [1, 2, 5])
def test_the_two_routes_agree_at_a_non_default_threshold(
    vault: Path, min_refs: int, capsys
):
    assert _via_mcp(vault, {"min_refs": min_refs}) == _via_cli(
        vault, "--min-refs", str(min_refs), capsys=capsys
    )


def test_the_threshold_argument_actually_changes_the_answer(vault: Path):
    """A guard on the parametrized agreement above: at the stock threshold
    ``[[Twice]]`` is a harvest decision, at 1 it is a finding."""
    stock = {i["message"] for i in _via_mcp(vault)["issues"]}
    lowered = {i["message"] for i in _via_mcp(vault, {"min_refs": 1})["issues"]}

    assert "broken wikilink [[Twice]]" not in stock
    assert "broken wikilink [[Twice]]" in lowered


def test_the_stock_threshold_needs_no_argument(vault: Path, capsys):
    """No second place to change it: an absent ``min_refs`` is the CLI default."""
    assert _via_mcp(vault) == _via_mcp(vault, {"min_refs": 3})
    assert _via_mcp(vault) == _via_cli(vault, capsys=capsys)


def test_a_non_integer_threshold_is_an_error(vault: Path):
    assert "min_refs" in _mcp_error(vault, {"min_refs": "three"})


@pytest.mark.parametrize("bad", [0, -5])
def test_a_non_positive_threshold_is_an_error(vault: Path, bad: int):
    """The CLI rejects the same range: below 1 the suppression gate
    silently behaves like 1, so the answer would not be the one asked for."""
    assert "at least 1" in _mcp_error(vault, {"min_refs": bad})


# ─── The rules argument mirrors the CLI flag ───────────────────────────


@pytest.mark.parametrize("selection", [["link_integrity"], "link_integrity"])
def test_the_rules_argument_mirrors_the_cli_flag(
    vault: Path, selection: object, capsys
):
    """A list and the CLI's comma-separated string mean the same thing."""
    assert _via_mcp(vault, {"rules": selection}) == _via_cli(
        vault, "--rules", "link_integrity", capsys=capsys
    )


def test_selecting_one_rule_narrows_the_findings(vault: Path):
    payload = _via_mcp(vault, {"rules": ["link_integrity"]})
    assert {i["rule"] for i in payload["issues"]} == {"link_integrity"}


def test_the_payload_says_which_checks_produced_it(vault: Path):
    """Without ``ran``, a run narrowed by ``rules`` is indistinguishable
    from a full one that happened to find a single class of issue —
    ``disabled_rules`` only covers the narrowing the vault declared."""
    full = _via_mcp(vault)
    narrowed = _via_mcp(vault, {"rules": ["link_integrity"]})

    assert full["ran"] == list(REGISTRY)
    assert narrowed["ran"] == ["link_integrity"]
    assert narrowed["disabled_rules"] == full["disabled_rules"] == {}


# ─── An unknown name errors rather than reporting a clean wiki ─────────


def test_an_unknown_rules_argument_errors(vault: Path):
    """Not a silent skip: an agent must not read a narrower run as a clean one."""
    message = _mcp_error(vault, {"rules": ["conten_freshness"]})
    assert "conten_freshness" in message
    assert "content_freshness" in message  # lists the valid names


def test_an_unknown_name_in_the_declaration_errors_and_names_the_file(vault: Path):
    _declare(vault, ["conten_freshness"])
    message = _mcp_error(vault, {})
    assert "conten_freshness" in message
    assert "llmwiki.json" in message


def test_an_unreadable_declaration_errors(vault: Path):
    """A settings file nobody can parse might be switching every check off."""
    (vault / "llmwiki.json").write_text('{"lint": {', encoding="utf-8")
    message = _mcp_error(vault, {})
    assert "llmwiki.json" in message
    assert "JSON" in message


def test_a_vault_without_a_wiki_errors(tmp_path: Path):
    assert "wiki/" in _mcp_error(tmp_path, {})


# ─── The advertised description matches what it runs ───────────────────


def _schema() -> dict:
    return next(tool for tool in TOOLS if tool["name"] == "wiki_lint")


def test_the_description_no_longer_promises_a_private_shape():
    """R9's third criterion. The old text named the two keys it returned and
    two checks it never implemented; the new text names the CLI payload."""
    description = _schema()["description"]
    for key in ("summary", "issues", "total_pages", "disabled_rules", "ran"):
        assert key in description
    assert "llmwiki lint --json" in description
    for stale in ("orphan_count", "broken_link_count", "broken_links"):
        assert stale not in description


def test_the_schema_advertises_exactly_the_arguments_the_tool_accepts():
    schema = _schema()["inputSchema"]
    assert set(schema["properties"]) == {"rules", "min_refs"}
    assert "required" not in schema  # both optional, like the CLI flags
    # No `fail_on_*`: there is no exit code over MCP to gate.
    assert "fail_on" not in json.dumps(schema)
