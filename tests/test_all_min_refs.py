"""The significance threshold reaches the full pipeline (#150, R5).

``--min-refs`` was only ever defined by ``_add_synth_arguments``, so the one
command a person is most likely to run — ``llmwiki all`` — could not state the
threshold at all, and harvested at the hardcoded stock value no matter what.
Running the steps together must not behave differently from running them
apart, so these tests pin both halves of the claim: the flag exists on the
``all`` parser, and the value it carries is the value the harvest and the
lint stage actually use.

The lint stage is checked here too, because ``all`` resolves the vault's
``llmwiki.json`` on its own path. A rule a vault switched off must be
switched off here as well — and named as skipped, or the pipeline would be
the one place a silenced check looks like a passing check.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from llmwiki import cli, pipeline
from llmwiki.candidates_harvest import DEFAULT_MIN_REFS
from llmwiki.cli import build_parser

# ─── Fixtures ──────────────────────────────────────────────────────────


def _source(wiki: Path, slug: str, body: str) -> None:
    """Write ``wiki/sources/<slug>.md`` with minimal frontmatter."""
    path = wiki / "sources" / f"{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'---\ntitle: "{slug}"\ntype: source\n---\n\n{body}\n', encoding="utf-8"
    )


def _seed_corpus(root: Path) -> Path:
    """A vault root whose sources name ``[[Twice]]`` twice, ``[[Thrice]]`` thrice.

    At the stock threshold only ``Thrice`` clears the bar; at ``--min-refs 2``
    both do. One corpus, two answers — which is what makes it able to tell
    whether a stated threshold was honoured or quietly dropped.
    """
    (root / "raw" / "sessions").mkdir(parents=True, exist_ok=True)
    wiki = root / "wiki"
    _source(wiki, "a", "See [[Twice]] and [[Thrice]].")
    _source(wiki, "b", "See [[Twice]] and [[Thrice]].")
    _source(wiki, "c", "See [[Thrice]].")
    return root


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    """A throwaway vault root, so no test can reach a real one."""
    return _seed_corpus(tmp_path)


def _parse(*argv: str) -> argparse.Namespace:
    return build_parser().parse_args(["all", *argv])


def _run(args: argparse.Namespace, **stubs) -> int:
    """Run ``cmd_all`` with every stage stubbed unless a test overrides it."""
    patches = {
        "build_site": patch.object(pipeline, "build_site", return_value=0),
        "_run_lint_step": patch.object(
            pipeline, "_run_lint_step", return_value=(0, {})
        ),
    }
    patches.update(stubs)
    with patch.object(pipeline, "_maybe_print_optout_notice"):
        for p in patches.values():
            p.start()
        try:
            return cli.cmd_all(args)
        finally:
            for p in patches.values():
                p.stop()


def _synth_stubs() -> dict[str, object]:
    """Patches that let the synth stage reach ``run_harvest`` without a backend."""
    backend = MagicMock()
    backend.name = "dummy"
    backend.is_available.return_value = True
    backend.is_llm = False
    return {
        "_load_sessions_config": patch.object(
            pipeline, "_load_sessions_config", return_value={}
        ),
        "resolve_backend": patch.object(
            pipeline, "resolve_backend", return_value=backend
        ),
        "synthesize_new_sessions": patch.object(
            pipeline,
            "synthesize_new_sessions",
            return_value={
                "total_scanned": 0, "new_files": 0,
                "synthesized": 0, "skipped": 0, "errors": [],
            },
        ),
    }


# ─── The flag exists on the path that was missing it ───────────────────


def test_the_all_parser_exposes_min_refs():
    """It was reachable from ``synth`` only, which is the whole defect."""
    assert _parse().min_refs == DEFAULT_MIN_REFS
    assert _parse("--min-refs", "2").min_refs == 2


def test_the_all_parser_default_is_the_shared_stock_value():
    """No second place to change the threshold (R4's last criterion)."""
    assert _parse().min_refs == build_parser().parse_args(["synth"]).min_refs


# ─── The stated threshold reaches the harvest ──────────────────────────


def test_a_stated_threshold_reaches_the_harvest(vault: Path):
    harvest = MagicMock(return_value=0)
    args = _parse("--no-sync", "--skip-graph", "--min-refs", "2",
                  "--vault", str(vault))

    assert _run(args, run_harvest=patch.object(pipeline, "run_harvest", harvest),
                **_synth_stubs()) == 0
    assert harvest.call_args.kwargs["min_refs"] == 2


def test_no_stated_threshold_harvests_at_the_stock_value(vault: Path):
    harvest = MagicMock(return_value=0)
    args = _parse("--no-sync", "--skip-graph", "--vault", str(vault))

    assert _run(args, run_harvest=patch.object(pipeline, "run_harvest", harvest),
                **_synth_stubs()) == 0
    assert harvest.call_args.kwargs["min_refs"] == DEFAULT_MIN_REFS


def test_a_stated_threshold_reaches_the_lint_stage(vault: Path):
    """One threshold for the whole run: the harvest that materializes a
    candidate and the rule that reports an unmaterialized link agree."""
    lint = MagicMock(return_value=(0, {}))
    args = _parse("--no-sync", "--no-synth", "--skip-graph", "--min-refs", "2",
                  "--vault", str(vault))

    assert _run(args, _run_lint_step=patch.object(pipeline, "_run_lint_step", lint)) == 0
    assert lint.call_args.kwargs["min_refs"] == 2


# ─── `all` and `synth` agree on the same corpus ────────────────────────


def _candidate_slugs(wiki: Path) -> set[str]:
    return {p.relative_to(wiki / "candidates").as_posix()
            for p in (wiki / "candidates").rglob("*.md")}


@pytest.mark.parametrize("min_refs", ["1", "2", "3"])
def test_all_and_synth_harvest_the_same_candidates(
    tmp_path_factory, min_refs: str, capsys
):
    """R5's last criterion, run for real: two vaults, one corpus, one answer.

    Nothing about the harvest is stubbed on either route — only the backend
    resolution, which classification does not need and which must never
    reach a network from a test.
    """
    via_all = _seed_corpus(tmp_path_factory.mktemp("via-all"))
    via_synth = _seed_corpus(tmp_path_factory.mktemp("via-synth"))

    args = _parse("--no-sync", "--skip-graph", "--min-refs", min_refs,
                  "--vault", str(via_all))
    assert _run(args, **_synth_stubs()) == 0

    with patch.object(cli, "resolve_backend", return_value=None):
        rc = cli.main([
            "synth", "--candidates-only",
            "--min-refs", min_refs, "--vault", str(via_synth),
        ])
    assert rc == 0
    capsys.readouterr()

    harvested = _candidate_slugs(via_all / "wiki")
    assert harvested == _candidate_slugs(via_synth / "wiki")
    # Sanity: the run really harvested something, and the threshold moved it.
    assert any("Thrice" in slug for slug in harvested)
    assert any("Twice" in slug for slug in harvested) == (int(min_refs) <= 2)


# ─── The vault's opt-out is honoured on this path too ──────────────────


def _entity(wiki: Path, name: str, body: str) -> None:
    path = wiki / "entities" / f"{name}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'---\ntitle: "{name}"\ntype: entity\ntags: []\nsources: []\n'
        f"last_updated: 2026-08-26\n---\n\n# {name}\n\n{body}\n",
        encoding="utf-8",
    )


@pytest.fixture
def warning_vault(tmp_path: Path) -> Path:
    """A vault whose only warning is one dangling ``link_integrity`` finding.

    No source page names ``[[Bar]]``, so it is a finding at every threshold —
    the opt-out, not the threshold, is what can silence it here.
    """
    (tmp_path / "raw" / "sessions").mkdir(parents=True)
    _entity(tmp_path / "wiki", "Foo", "## Connections\n- [[Bar]]")
    return tmp_path


def _declare(root: Path, declaration: object) -> None:
    (root / "llmwiki.json").write_text(
        json.dumps({"lint": {"disabled_rules": declaration}}), encoding="utf-8"
    )


def test_the_pipeline_lint_step_reports_a_finding(warning_vault: Path, capsys):
    """The baseline the opt-out tests below are measured against."""
    rc, summary = pipeline._run_lint_step(warning_vault / "wiki")
    out = capsys.readouterr().out

    assert rc == 0
    assert summary.get("warning", 0) == 1
    assert "broken wikilink [[Bar]]" in out


def test_the_pipeline_lint_step_honours_a_vault_opt_out(warning_vault: Path, capsys):
    """A rule disabled for a vault is disabled on the ``all`` path too — the
    stage reads the same ``llmwiki.json`` beside ``wiki/`` that ``lint`` does."""
    _declare(warning_vault, {"link_integrity": "targets are materialized elsewhere"})

    rc, summary = pipeline._run_lint_step(warning_vault / "wiki")
    out = capsys.readouterr().out

    assert rc == 0
    assert summary.get("warning", 0) == 0
    assert "broken wikilink" not in out


def test_the_pipeline_lint_step_names_what_it_skipped(warning_vault: Path, capsys):
    """R2 on this path: a silenced check must never look like a passing one."""
    _declare(warning_vault, {"content_freshness": "a committed snapshot"})

    pipeline._run_lint_step(warning_vault / "wiki")
    out = capsys.readouterr().out

    assert "content_freshness" in out
    assert "a committed snapshot" in out


def test_the_pipeline_lint_step_refuses_an_unreadable_declaration(
    warning_vault: Path, capsys
):
    """A settings file nobody can parse might be switching every check off."""
    (warning_vault / "llmwiki.json").write_text('{"lint": {', encoding="utf-8")

    rc, summary = pipeline._run_lint_step(warning_vault / "wiki")
    captured = capsys.readouterr()

    assert (rc, summary) == (2, {})
    assert "llmwiki.json" in captured.err
    assert "issues" not in captured.out


def test_the_pipeline_lint_step_refuses_an_unknown_rule_name(
    warning_vault: Path, capsys
):
    """A typo must not leave a check switched on that the author believed
    they had switched off."""
    _declare(warning_vault, ["conten_freshness"])

    rc, summary = pipeline._run_lint_step(warning_vault / "wiki")
    captured = capsys.readouterr()

    assert (rc, summary) == (2, {})
    assert "conten_freshness" in captured.err
    assert "content_freshness" in captured.err  # lists the valid names
    assert "issues" not in captured.out


def test_the_pipeline_lint_step_honours_the_threshold(vault: Path, capsys):
    """``[[Twice]]`` is a decision at the stock value and a gap at 2."""
    stock_rc, stock = pipeline._run_lint_step(vault / "wiki")
    stock_out = capsys.readouterr().out
    lowered_rc, lowered = pipeline._run_lint_step(vault / "wiki", min_refs=2)
    lowered_out = capsys.readouterr().out

    assert (stock_rc, lowered_rc) == (0, 0)
    assert "broken wikilink [[Twice]]" not in stock_out
    assert "broken wikilink [[Twice]]" in lowered_out
    assert lowered.get("warning", 0) > stock.get("warning", 0)


# ─── The escalation policy is unchanged by any of the above ────────────


def _lint_run(vault_root: Path, *flags: str) -> int:
    """``cmd_all`` over a real vault with only ``build`` stubbed out."""
    args = _parse("--no-sync", "--no-synth", "--skip-graph",
                  *flags, "--vault", str(vault_root))
    with (
        patch.object(pipeline, "_maybe_print_optout_notice"),
        patch.object(pipeline, "build_site", return_value=0),
    ):
        return cli.cmd_all(args)


def test_real_lint_findings_alone_never_fail_the_pipeline(warning_vault: Path, capsys):
    """Unstubbed: a real warning reaches the real stage and is still not a gate."""
    assert _lint_run(warning_vault) == 0
    assert "broken wikilink [[Bar]]" in capsys.readouterr().out


def test_lint_fail_errors_still_ignores_a_warning_only_vault(warning_vault: Path):
    assert _lint_run(warning_vault, "--lint-fail", "errors") == 0


@pytest.mark.parametrize("flags", [("--strict",), ("--lint-fail", "warnings")])
def test_the_stricter_policies_still_escalate_a_real_warning(
    warning_vault: Path, flags: tuple[str, ...]
):
    assert _lint_run(warning_vault, *flags) == 2


def test_disabling_the_offending_rule_passes_the_strict_gate(warning_vault: Path):
    """The escalation reads the stage's summary, so an opt-out reaches it."""
    _declare(warning_vault, {"link_integrity": "targets are materialized elsewhere"})
    assert _lint_run(warning_vault, "--strict") == 0
