"""Whole-feature acceptance tests for #150: per-vault lint rule scoping.

# @layer: integration
# @spec: 150-vault-lint-rule-scoping
# @regression

Per-slice tests already cover the mechanics in detail:

    tests/test_lint_vault_settings.py -- llmwiki.json shapes, run_lint(disabled=...),
                                          the reporter naming skips, --fail-on-warnings
    tests/test_lint_min_refs.py       -- the three-way threshold gate on link_integrity,
                                          the zero case, the shared DEFAULT_MIN_REFS
    tests/test_all_min_refs.py        -- --min-refs on the `all` parser reaching the
                                          harvest and the lint stage, opt-out on that path
    tests/test_lint_determinism.py    -- byte-identical --json across processes/hash seeds
    tests/test_mcp_lint_parity.py     -- wiki_lint == lint --json, one axis at a time
    tests/test_demo_gate.py           -- the committed demo's enforced gate, its one
                                          opt-out, a real warning still failing it
    tests/test_contradiction_filler.py-- boilerplate vs. real conflicting-claims wording

This file checks things that only show up when several of those pieces are
wired together, or that no per-slice test touches at all: the two scoping
mechanisms (opt-out and threshold) composing correctly on *both* the CLI and
MCP routes in a single call; the documentation's own worked example actually
producing the behaviour it claims when executed against a real vault; the
three independent places the minimum Python version is stated agreeing with
each other; and the release notes actually announcing the MCP payload
break that R9 requires.

AC coverage matrix (R<n>, in functional-spec.md order):

    R4/R5/R9 -> test_mcp_and_cli_agree_with_an_opt_out_and_a_threshold_together
    R8       -> test_installation_guide_and_pyproject_agree_on_minimum_python
    R9       -> test_changelog_and_upgrading_document_the_wiki_lint_payload_change
    R10      -> test_documented_worked_example_switches_off_the_named_check
                test_documentation_states_the_hiding_caution
                test_documentation_explains_the_threshold_effect

Not duplicated here (already proven, per-slice or elsewhere in this file's
own composition test):

    - R4's "the published example at stock settings reports zero broken
      cross-references" is a strict subset of
      test_demo_gate.test_committed_demo_passes_the_enforced_gate, which
      passes --fail-on-warnings -- a link_integrity warning would already
      fail that gate, so a dedicated "zero cross-references" assertion on
      the demo would only re-derive what that test already guarantees.
    - R9's "byte-identical across processes/hash seeds" is
      test_lint_determinism.py's whole point; re-running it here would not
      add anything the in-process MCP-parity checks in this file could not
      already give a false pass on.
    - R1/R2/R3/R6/R7 are exercised exhaustively, including negative cases,
      by test_lint_vault_settings.py and test_contradiction_filler.py.
"""

from __future__ import annotations

import io
import json
import re
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import pytest

from llmwiki import REPO_ROOT
from llmwiki.cli import build_parser
from llmwiki.lint import load_pages, run_lint
from llmwiki.lint import rules as _rules  # noqa: F401 -- force rule registration
from llmwiki.mcp.server import tool_wiki_health
from tests.changelog_notes import shipping_section_text


def _run_lint_json(vault: Path, *flags: str) -> tuple[int, dict]:
    """Run the real ``lint --json`` CLI over ``vault`` and parse its stdout."""
    args = build_parser().parse_args(["lint", "--vault", str(vault), "--json", *flags])
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = args.func(args)
    return rc, json.loads(buf.getvalue())


CHANGELOG = REPO_ROOT / "CHANGELOG.md"
UPGRADING = REPO_ROOT / "docs" / "UPGRADING.md"
CONFIG_REFERENCE = REPO_ROOT / "docs" / "configuration-reference.md"
INSTALLATION_GUIDE = REPO_ROOT / "docs" / "tutorials" / "01-installation.md"
PYPROJECT = REPO_ROOT / "pyproject.toml"


# ─── R8 -- one minimum Python version, stated in three places ─────────────


def test_installation_guide_and_pyproject_agree_on_minimum_python() -> None:
    """The functional spec's own headline defect: the guide named 3.9 in one
    place and 3.12 in another while the project actually required 3.12.

    Pins all three places the version is stated so a future edit to any one
    of them, without the others, fails this test rather than shipping a
    second disagreement.
    """
    pyproject_text = PYPROJECT.read_text(encoding="utf-8")
    guide_text = INSTALLATION_GUIDE.read_text(encoding="utf-8")

    pyproject_version = re.search(
        r'requires-python\s*=\s*">=(\d+\.\d+)"', pyproject_text
    )
    header_version = re.search(r"\*\*You'll need:\*\* Python (\d+\.\d+)\+", guide_text)
    verify_version = re.search(
        r"python3 --version\s+# expect (\d+\.\d+) or newer", guide_text
    )
    troubleshooting_version = re.search(
        r"llmwiki requires ≥ ?(\d+\.\d+)", guide_text
    )

    assert pyproject_version, "pyproject.toml requires-python not found"
    assert header_version, "installation guide header version not found"
    assert verify_version, "installation guide Step 1 verification version not found"
    assert troubleshooting_version, "installation guide troubleshooting version not found"

    versions = {
        pyproject_version.group(1),
        header_version.group(1),
        verify_version.group(1),
        troubleshooting_version.group(1),
    }
    assert versions == {"3.12"}, f"minimum Python version disagrees across sources: {versions}"


# ─── R9 -- the MCP payload break is announced where a reader would look ──


def test_changelog_and_upgrading_document_mcp_consolidation() -> None:
    """#196: readers of the release notes and upgrade guide are told the MCP
    surface shrank to six tools and which retired names map where."""
    changelog = CHANGELOG.read_text(encoding="utf-8")
    unreleased = shipping_section_text(changelog)
    assert "wiki_health" in unreleased
    assert "#196" in unreleased
    assert "BREAKING" in unreleased.upper() or "six" in unreleased.lower()
    for retired in ("wiki_query", "wiki_lint", "wiki_dashboard"):
        assert retired in unreleased

    upgrading = UPGRADING.read_text(encoding="utf-8")
    assert "wiki_health" in upgrading
    assert "#196" in upgrading
    assert "wiki_query" in upgrading
    assert "mcp.md" in upgrading


# ─── R10 -- the documentation's own worked example actually works ────────


def _extract_worked_example_json(text: str) -> dict:
    """Pull the JSON heredoc body out of configuration-reference.md's
    "Worked example" section -- the literal ``llmwiki.json`` a reader would
    end up with by following the doc, not a paraphrase of it."""
    section = text.split("### Worked example", 1)[1]
    match = re.search(r"<<'JSON'\n(.*?)\nJSON\n", section, re.DOTALL)
    assert match, "worked example heredoc body not found in configuration-reference.md"
    return json.loads(match.group(1))


def test_documented_worked_example_switches_off_the_named_check(tmp_path: Path) -> None:
    """R10's second AC, executed rather than read: follow the doc's own
    instructions against a fresh wiki and check the report says what the
    doc says it will.

    The fixture page is deliberately 400+ days stale, so ``content_freshness``
    would otherwise fire -- proving the declaration suppressed a real
    finding, not merely that nothing was ever going to be reported.
    """
    doc_text = CONFIG_REFERENCE.read_text(encoding="utf-8")
    declaration = _extract_worked_example_json(doc_text)
    reason = declaration["lint"]["disabled_rules"]["content_freshness"]

    vault = tmp_path / "vault"
    wiki = vault / "wiki"
    wiki.mkdir(parents=True)
    (wiki / "entities").mkdir()
    (wiki / "entities" / "Old.md").write_text(
        '---\ntitle: "Old"\ntype: entity\ntags: []\nsources: []\n'
        "last_updated: 2020-01-01\n---\n\n# Old\n\nBody.\n",
        encoding="utf-8",
    )
    (vault / "llmwiki.json").write_text(json.dumps(declaration), encoding="utf-8")

    rc, payload = _run_lint_json(vault)
    assert rc == 0

    assert payload["disabled_rules"] == {"content_freshness": reason}
    assert [i for i in payload["issues"] if i["rule"] == "content_freshness"] == []


def test_the_worked_example_fixture_would_otherwise_have_flagged_staleness(
    tmp_path: Path,
) -> None:
    """Guard on the test above: without the declaration, the same fixture
    page really is a content_freshness finding -- so the previous test's
    "0 content_freshness issues" is the opt-out working, not an accident of
    the fixture."""
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "entities").mkdir()
    (wiki / "entities" / "Old.md").write_text(
        '---\ntitle: "Old"\ntype: entity\ntags: []\nsources: []\n'
        "last_updated: 2020-01-01\n---\n\n# Old\n\nBody.\n",
        encoding="utf-8",
    )
    outcome = run_lint(load_pages(wiki), selected=["content_freshness"])
    assert outcome.issues, "fixture page must be stale enough to trigger the rule"


def test_documentation_states_the_hiding_caution() -> None:
    """R10's third AC: the caution that switching a check off hides real
    findings, and is for checks that cannot apply -- not ones that are
    merely inconvenient."""
    text = CONFIG_REFERENCE.read_text(encoding="utf-8")
    assert "hides real findings" in text.lower()
    assert "cannot apply" in text
    assert "merely inconvenient" in text


def test_documentation_explains_the_threshold_effect() -> None:
    """R10's fourth AC: why lowering --min-refs produces more findings, tied
    back to the one shared stock-value definition."""
    text = CONFIG_REFERENCE.read_text(encoding="utf-8")
    assert "DEFAULT_MIN_REFS" in text
    assert "lowering the threshold" in text.lower()
    # The three-way gate itself, not just the existence of the flag.
    assert "deliberately declined" in text or "deliberate" in text


# ─── R4 + R5 + R9 -- the two scoping mechanisms compose, on both routes ──


def _source(wiki: Path, slug: str, body: str) -> None:
    path = wiki / "sources" / f"{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f'---\ntitle: "{slug}"\ntype: source\n---\n\n{body}\n', encoding="utf-8")


@pytest.fixture
def composed_vault(tmp_path: Path) -> Path:
    """A vault whose report needs *both* scoping mechanisms to read clean:
    an orphan page nobody links to (silenced by the declared opt-out) and a
    threshold-sensitive [[wikilink]] (silenced or not depending on the
    stated --min-refs, independently of the opt-out).

    Two sources name [[Twice]]: a harvest decline at the stock threshold
    (3), a genuine gap at 2 -- so a run with --min-refs 2 must report it
    while the untouched stock run must not, on both routes.
    """
    wiki = tmp_path / "wiki"
    _source(wiki, "a", "See [[Twice]].")
    _source(wiki, "b", "See [[Twice]].")
    (wiki / "entities").mkdir(parents=True, exist_ok=True)
    (wiki / "entities" / "Lonely.md").write_text(
        '---\ntitle: "Lonely"\ntype: entity\ntags: []\nsources: []\n'
        "last_updated: 2026-08-01\n---\n\n# Lonely\n\nNothing links here.\n",
        encoding="utf-8",
    )
    (tmp_path / "llmwiki.json").write_text(
        json.dumps({
            "lint": {"disabled_rules": {"orphan_detection": "not applicable to this fixture"}}
        }),
        encoding="utf-8",
    )
    return tmp_path


def _via_cli(vault: Path, *flags: str) -> dict:
    rc, payload = _run_lint_json(vault, *flags)
    assert rc == 0
    return payload


def _via_mcp(vault: Path, args: dict | None = None) -> dict:
    with patch("llmwiki.mcp.server.REPO_ROOT", vault):
        result = tool_wiki_health(args or {})
    assert result["isError"] is False, result["content"][0]["text"]
    payload = json.loads(result["content"][0]["text"])
    payload.pop("totals", None)
    return payload


def test_mcp_and_cli_agree_with_an_opt_out_and_a_threshold_together(
    composed_vault: Path,
) -> None:
    """Every per-slice parity test in test_mcp_lint_parity.py varies the
    opt-out or the threshold alone. Real vaults set both; this proves
    neither route drops one when the other is also in play."""
    stock_cli = _via_cli(composed_vault)
    stock_mcp = _via_mcp(composed_vault)
    assert stock_cli == stock_mcp
    # The opt-out actually silenced the orphan finding on both routes.
    assert "orphan_detection" not in {i["rule"] for i in stock_cli["issues"]}
    assert stock_cli["disabled_rules"] == {
        "orphan_detection": "not applicable to this fixture"
    }
    # At the stock threshold [[Twice]] is a harvest decision, not a finding.
    assert "broken wikilink [[Twice]]" not in {i["message"] for i in stock_cli["issues"]}

    lowered_cli = _via_cli(composed_vault, "--min-refs", "2")
    lowered_mcp = _via_mcp(composed_vault, {"min_refs": 2})
    assert lowered_cli == lowered_mcp
    # The threshold, not the opt-out, controls this finding: still silenced
    # is orphan_detection, but [[Twice]] now surfaces on both routes.
    assert "orphan_detection" not in {i["rule"] for i in lowered_cli["issues"]}
    assert "broken wikilink [[Twice]]" in {i["message"] for i in lowered_cli["issues"]}
    assert lowered_cli["disabled_rules"] == stock_cli["disabled_rules"]
