"""A vault switches a check off, and the report always says which (#150).

Covers the three pieces that make an opt-out honest rather than merely
quiet: the declaration a vault carries (``llmwiki.json``), the runner that
reports *what it skipped* alongside *what it found*, and the reporter that
prints both — plus ``--fail-on-warnings``, which is only safe to enforce
once a vault can decline the checks that cannot apply to it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from llmwiki.cli import build_parser
from llmwiki.lint import (
    REGISTRY,
    LintOutcome,
    UnknownRuleError,
    load_pages,
    rules,  # noqa: F401 — force rule registration
    run_all,
    run_lint,
)
from llmwiki.lint.report import render_json, render_text
from llmwiki.state_store import read_state, resolve_state_file, update_state
from llmwiki.vault_settings import (
    VaultSettingsError,
    disabled_lint_rules,
    load_vault_settings,
)

# ─── Fixtures ──────────────────────────────────────────────────────────


def _page(wiki: Path, rel: str, body: str) -> None:
    """Write one entity page with complete frontmatter."""
    path = wiki / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'---\ntitle: "{path.stem}"\ntype: entity\ntags: []\nsources: []\n'
        f"last_updated: 2026-08-26\n---\n\n# {path.stem}\n\n{body}\n",
        encoding="utf-8",
    )


@pytest.fixture
def warning_vault(tmp_path: Path) -> Path:
    """A vault root whose only warning is one ``link_integrity`` finding.

    The dangling target is named by no source page at all, so it is a
    finding at every threshold — the opt-out, not the threshold, is what
    silences it here.
    """
    _page(tmp_path / "wiki", "entities/Foo.md", "## Connections\n- [[Bar]]")
    return tmp_path


@pytest.fixture
def clean_vault(tmp_path: Path) -> Path:
    """A vault root with no error- or warning-severity findings."""
    _page(tmp_path / "wiki", "entities/Foo.md", "Body.")
    return tmp_path


def _error_page(wiki: Path) -> None:
    """Add a page with no frontmatter — one ``frontmatter_completeness`` error."""
    (wiki / "entities" / "Bad.md").write_text("No frontmatter at all.\n", encoding="utf-8")


def _declare(root: Path, declaration: object) -> None:
    """Write ``<root>/llmwiki.json`` carrying ``lint.disabled_rules``."""
    (root / "llmwiki.json").write_text(
        json.dumps({"lint": {"disabled_rules": declaration}}), encoding="utf-8"
    )


def _lint(root: Path, *flags: str) -> int:
    """Run ``llmwiki lint`` over ``<root>/wiki`` through the real parser."""
    args = build_parser().parse_args(
        ["lint", "--wiki-dir", str(root / "wiki"), *flags]
    )
    return args.func(args)


# ─── The declaration a vault carries ───────────────────────────────────


def test_a_vault_that_declares_nothing_has_no_settings(tmp_path: Path):
    """The normal case: no file, no opt-outs, behaviour as before."""
    assert load_vault_settings(tmp_path) == {}
    assert disabled_lint_rules(load_vault_settings(tmp_path)) == {}


def test_list_shape_normalises_to_empty_reasons(tmp_path: Path):
    _declare(tmp_path, ["content_freshness"])
    assert disabled_lint_rules(load_vault_settings(tmp_path)) == {
        "content_freshness": ""
    }


def test_object_shape_keeps_its_reasons(tmp_path: Path):
    _declare(tmp_path, {"content_freshness": "a committed snapshot ages by the calendar"})
    assert disabled_lint_rules(load_vault_settings(tmp_path)) == {
        "content_freshness": "a committed snapshot ages by the calendar"
    }


def test_malformed_json_is_never_a_silent_empty_dict(tmp_path: Path):
    """An unparseable declaration might be switching everything off."""
    (tmp_path / "llmwiki.json").write_text('{"lint": {', encoding="utf-8")
    with pytest.raises(VaultSettingsError) as exc:
        load_vault_settings(tmp_path)
    assert "llmwiki.json" in str(exc.value)


def test_a_non_object_declaration_is_an_error(tmp_path: Path):
    (tmp_path / "llmwiki.json").write_text('["content_freshness"]', encoding="utf-8")
    with pytest.raises(VaultSettingsError):
        load_vault_settings(tmp_path)


@pytest.mark.parametrize("declaration", ["content_freshness", 3, [7]])
def test_a_malformed_disabled_rules_shape_is_an_error(tmp_path: Path, declaration: object):
    """A shape nobody can read must not leave a check quietly switched on."""
    _declare(tmp_path, declaration)
    with pytest.raises(VaultSettingsError):
        disabled_lint_rules(load_vault_settings(tmp_path))


# ─── The runner reports what it skipped ────────────────────────────────


def test_a_disabled_rule_does_not_run_and_finds_nothing(warning_vault: Path):
    pages = load_pages(warning_vault / "wiki")
    outcome = run_lint(pages, disabled={"link_integrity": "not applicable"})
    assert outcome.issues == [
        i for i in outcome.issues if i["rule"] != "link_integrity"
    ]
    assert "link_integrity" not in outcome.ran
    assert outcome.skipped == {"link_integrity": "not applicable"}
    assert len(outcome.ran) == len(REGISTRY) - 1


def test_the_runner_accepts_both_declared_shapes(warning_vault: Path):
    pages = load_pages(warning_vault / "wiki")
    assert run_lint(pages, disabled=["link_integrity"]).skipped == {
        "link_integrity": ""
    }


def test_an_unknown_disabled_name_fails_loudly(warning_vault: Path):
    """A typo must not leave a check switched on that the author believed
    they had switched off."""
    pages = load_pages(warning_vault / "wiki")
    with pytest.raises(UnknownRuleError) as exc:
        run_lint(pages, disabled={"conten_freshness": ""})
    assert "conten_freshness" in str(exc.value)
    assert "content_freshness" in str(exc.value)  # lists the valid names


def test_run_all_still_returns_a_plain_issue_list(warning_vault: Path):
    """~20 existing call sites want findings and nothing else."""
    pages = load_pages(warning_vault / "wiki")
    issues = run_all(pages)
    assert isinstance(issues, list)
    assert issues == run_lint(pages).issues


# ─── The reporter names the skipped, found or not ──────────────────────


def _outcome(**kw) -> LintOutcome:
    kw.setdefault("ran", [n for n in REGISTRY if n not in kw.get("skipped", {})])
    return LintOutcome(issues=kw.get("issues", []), skipped=kw.get("skipped", {}),
                       ran=kw["ran"])


def test_a_clean_report_still_names_what_was_skipped():
    """Otherwise a clean result quietly means "almost nothing was checked"."""
    text = render_text(
        _outcome(skipped={"content_freshness": "a frozen snapshot"}), total_pages=3
    )
    assert "content_freshness" in text
    assert "a frozen snapshot" in text
    assert "0 issues" in text  # the clean summary is still there


def test_a_skipped_rule_without_a_reason_is_still_named():
    text = render_text(_outcome(skipped={"content_freshness": ""}), total_pages=3)
    assert "content_freshness" in text


def test_all_rules_disabled_says_nothing_was_checked():
    """Not a clean wiki — an unexamined one."""
    text = render_text(
        _outcome(skipped=dict.fromkeys(REGISTRY, ""), ran=[]), total_pages=3
    )
    assert "nothing was checked" in text
    assert "0 issues" not in text


def test_json_carries_the_disabled_rules():
    payload = render_json(
        _outcome(skipped={"content_freshness": "a frozen snapshot"}), total_pages=3
    )
    assert payload["disabled_rules"] == {"content_freshness": "a frozen snapshot"}
    assert set(payload) == {
        "summary", "issues", "total_pages", "disabled_rules", "ran"
    }


def test_json_always_carries_the_key_even_when_empty():
    assert render_json(_outcome(), total_pages=3)["disabled_rules"] == {}


# ─── Both counts are out of what the run would have used ───────────────


def test_the_outcome_records_the_rules_the_run_would_have_used(warning_vault: Path):
    """``considered`` is the selection, before the vault's opt-outs apply."""
    pages = load_pages(warning_vault / "wiki")
    assert run_lint(pages).considered == list(REGISTRY)

    narrowed = run_lint(
        pages, selected=["link_integrity"], disabled={"link_integrity": ""}
    )
    assert narrowed.considered == ["link_integrity"]
    assert narrowed.ran == []


def test_a_narrowed_run_counts_against_what_it_selected(
    warning_vault: Path, capsys
):
    """A false number in the line that exists to stop a false clean report.

    ``--rules`` can empty a run without the vault disabling anything like
    seventeen rules: here exactly one rule was asked for, and exactly one
    was switched off.
    """
    _declare(warning_vault, {"link_integrity": "targets are materialized elsewhere"})
    assert _lint(warning_vault, "--rules", "link_integrity") == 0

    out = capsys.readouterr().out
    assert "nothing was checked" in out
    assert "all 1 rule this run would have used was skipped" in out
    assert "skipped 1 of 1 rules" in out
    assert f"of {len(REGISTRY)} rules" not in out


def test_a_rule_the_selection_never_named_is_not_called_skipped(
    warning_vault: Path, capsys
):
    """It was not skipped by this run — it was never going to be used."""
    _declare(warning_vault, {"content_freshness": "a frozen snapshot"})
    assert _lint(warning_vault, "--rules", "link_integrity") == 0

    out = capsys.readouterr().out
    assert "broken wikilink" in out  # the selected rule did run
    assert "content_freshness" not in out
    assert "skipped" not in out


def test_a_full_run_still_counts_against_the_whole_registry(
    clean_vault: Path, capsys
):
    """The unnarrowed case the wording must not regress."""
    _declare(clean_vault, {"content_freshness": "a frozen snapshot"})
    assert _lint(clean_vault) == 0
    assert f"skipped 1 of {len(REGISTRY)} rules" in capsys.readouterr().out


# ─── The payload says which checks produced it ─────────────────────────


def test_json_names_the_rules_that_ran(clean_vault: Path, capsys):
    """Otherwise a run narrowed by ``rules`` reads as a full one."""
    assert _lint(clean_vault, "--json") == 0
    assert json.loads(capsys.readouterr().out)["ran"] == list(REGISTRY)


def test_json_ran_shrinks_with_the_selection(clean_vault: Path, capsys):
    _declare(clean_vault, {"content_freshness": "a frozen snapshot"})
    assert _lint(
        clean_vault, "--json", "--rules", "link_integrity,orphan_detection"
    ) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["ran"] == ["link_integrity", "orphan_detection"]
    assert payload["disabled_rules"] == {"content_freshness": "a frozen snapshot"}


# ─── The CLI, end to end ───────────────────────────────────────────────


def test_cli_drops_the_finding_and_names_the_skip(warning_vault: Path, capsys):
    _declare(warning_vault, {"link_integrity": "targets are materialized elsewhere"})
    assert _lint(warning_vault) == 0
    out = capsys.readouterr().out
    assert "broken wikilink" not in out
    assert "link_integrity" in out
    assert "targets are materialized elsewhere" in out


def test_cli_json_names_the_skip_alongside_the_findings(warning_vault: Path, capsys):
    _declare(warning_vault, {"link_integrity": "targets are materialized elsewhere"})
    assert _lint(warning_vault, "--json") == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["disabled_rules"] == {
        "link_integrity": "targets are materialized elsewhere"
    }
    assert [i for i in payload["issues"] if i["rule"] == "link_integrity"] == []


def test_cli_names_the_skip_on_an_otherwise_clean_vault(clean_vault: Path, capsys):
    """R2's sharpest case: nothing found, so only the skip block can tell
    the reader how much of the wiki was actually examined."""
    _declare(clean_vault, {"content_freshness": "a frozen snapshot"})
    assert _lint(clean_vault) == 0
    out = capsys.readouterr().out
    assert "content_freshness" in out
    assert "a frozen snapshot" in out


def test_cli_all_rules_disabled_is_not_reported_as_clean(clean_vault: Path, capsys):
    _declare(clean_vault, sorted(REGISTRY))
    assert _lint(clean_vault) == 0
    out = capsys.readouterr().out
    assert "nothing was checked" in out
    assert "0 issues" not in out


def test_cli_malformed_json_exits_two_and_names_the_file(warning_vault: Path, capsys):
    (warning_vault / "llmwiki.json").write_text('{"lint": {', encoding="utf-8")
    assert _lint(warning_vault) == 2
    captured = capsys.readouterr()
    assert "llmwiki.json" in captured.err
    assert "JSON" in captured.err
    assert "issues" not in captured.out  # nothing reported as clean


def test_cli_unknown_rule_in_the_declaration_exits_two(warning_vault: Path, capsys):
    _declare(warning_vault, ["conten_freshness"])
    assert _lint(warning_vault) == 2
    captured = capsys.readouterr()
    assert "conten_freshness" in captured.err
    assert "content_freshness" in captured.err  # the valid names
    assert "llmwiki.json" in captured.err
    assert "issues" not in captured.out


def test_a_declaration_affects_only_the_vault_that_carries_it(
    warning_vault: Path, tmp_path_factory, capsys
):
    other = tmp_path_factory.mktemp("other-vault")
    _page(other / "wiki", "entities/Foo.md", "## Connections\n- [[Bar]]")
    _declare(warning_vault, ["link_integrity"])

    assert _lint(warning_vault, "--json") == 0
    assert json.loads(capsys.readouterr().out)["disabled_rules"] == {
        "link_integrity": ""
    }
    assert _lint(other, "--json") == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["disabled_rules"] == {}
    assert [i["rule"] for i in payload["issues"] if i["rule"] == "link_integrity"]


# ─── --fail-on-warnings ────────────────────────────────────────────────


def test_warnings_do_not_stop_the_gate_by_default(warning_vault: Path):
    assert _lint(warning_vault) == 0


def test_warnings_stop_the_gate_when_asked(warning_vault: Path):
    assert _lint(warning_vault, "--fail-on-warnings") == 1


def test_a_clean_vault_passes_the_stricter_gate(clean_vault: Path):
    assert _lint(clean_vault, "--fail-on-warnings") == 0


def test_disabling_the_offending_rule_passes_the_stricter_gate(warning_vault: Path):
    _declare(warning_vault, {"link_integrity": "targets are materialized elsewhere"})
    assert _lint(warning_vault, "--fail-on-warnings") == 0


def test_fail_on_errors_still_ignores_a_warning_only_vault(warning_vault: Path):
    assert _lint(warning_vault, "--fail-on-errors") == 0


def test_the_lint_parser_exposes_the_flag():
    parser = build_parser()
    assert parser.parse_args(["lint"]).fail_on_warnings is False
    assert parser.parse_args(["lint", "--fail-on-warnings"]).fail_on_warnings is True


def test_a_failing_lint_still_records_that_it_ran(warning_vault: Path):
    """The exit code is computed last, so no gate can skip the state update.

    Before #150 ``cmd_lint`` returned on ``--fail-on-errors`` *above* the
    state update, so the runs most worth recording were the ones never
    recorded.
    """
    state_file = resolve_state_file()
    update_state(
        lambda s: (s.setdefault("ops", {}).__setitem__("last_lint_run_at", "") or s),
        state_file,
    )
    _error_page(warning_vault / "wiki")
    assert _lint(warning_vault, "--fail-on-errors", "--fail-on-warnings") == 1
    assert read_state(state_file)["ops"]["last_lint_run_at"]
