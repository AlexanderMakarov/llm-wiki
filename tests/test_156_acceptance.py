"""Whole-feature acceptance tests for #156: plain-language automation setup.

# @layer: integration
# @spec: 010-automation-profiles
# @regression

Per-slice tests already cover the mechanics in detail:

    tests/test_cron_spec.py         -- cron grammar, guards, per-backend renderers
    tests/test_automation_plan.py   -- AutomationPlan, plan_command/label, status round-trip
    tests/test_all_optout.py        -- `all` opt-in -> opt-out flip, lint-fail policy matrix
    tests/test_automation_install.py-- the wizard's scripted-input transcripts, flags,
                                        unit renderers, the Home Automation panel

This file checks the feature as a *whole* against
``context/spec/010-automation-profiles/functional-spec.md`` -- i.e. things that
only show up when two or more modules are wired together (wizard answers ->
files actually written to disk -> what the site build reads back), plus the
places the tech-considerations doc calls out as the highest-regression-risk
seams: the ingest command staying byte-identical, the deprecated flags not
crashing an already-installed job, the default install spending nothing, a
legacy status file still rendering, and the docs/changelog telling users what
changed.

AC coverage matrix (R<n>, in functional-spec.md order):

    R1  -> test_job_question_names_outcome_folders_and_cost_for_both_choices
    R2  -> test_ingest_choice_writes_no_extras_or_graph_choice_end_to_end
    R3  -> test_lint_findings_never_fail_the_job_by_default_but_do_at_the_chosen_policy
           test_wrapper_script_truncates_the_log_instead_of_appending
    R5  -> test_declining_writes_nothing_and_a_later_real_install_still_succeeds
    R6  -> test_bare_all_resolves_the_real_dummy_backend_with_no_network_call
           test_legacy_with_sync_with_synth_flags_still_parse_through_main
           test_all_help_lists_every_stage_and_its_opt_out_flag
    R7  -> test_ingest_scheduled_command_is_byte_identical_to_pre_change_profile_a
           test_maintain_scheduled_command_is_one_invocation_not_a_chain
    R9  -> test_home_page_shows_a_readable_label_for_a_legacy_letter_only_status
           test_home_page_shows_a_readable_label_for_a_new_format_status
    R10 -> test_cheatsheet_presents_automation_before_the_manual_alternative
           test_getting_started_and_quickstart_offer_automation_right_after_first_build
    R11 -> test_upgrade_guide_and_changelog_flag_the_all_behaviour_change
           test_rerunning_install_replaces_the_existing_units_not_duplicates_them
"""

from __future__ import annotations

import io
import re
import shlex
import socket
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from llmwiki import REPO_ROOT, cli, pipeline
from llmwiki.automation_install import render_wrapper_script, run_install
from llmwiki.automation_plan import AutomationPlan, plan_command
from llmwiki.automation_status import load_status, status_path
from llmwiki.build import render_automation_panel
from llmwiki.cli import _JOB_QUESTION, build_parser
from tests.changelog_notes import shipping_section_text

CHEATSHEET = REPO_ROOT / "docs" / "cheatsheet.md"
GETTING_STARTED = REPO_ROOT / "docs" / "getting-started.md"
QUICKSTART = REPO_ROOT / "docs" / "tutorials" / "00-quickstart-walkthrough.md"
UPGRADING = REPO_ROOT / "docs" / "UPGRADING.md"
CHANGELOG = REPO_ROOT / "CHANGELOG.md"


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    """A throwaway vault root -- raw/ + wiki/ scaffolded, nothing under REPO_ROOT touched."""
    v = tmp_path / "vault"
    (v / "raw" / "sessions").mkdir(parents=True)
    (v / "raw" / "docs").mkdir(parents=True)
    (v / "wiki").mkdir()
    return v


def _write_session(vault: Path, stem: str = "s1", project: str = "proj") -> None:
    """One minimal raw session + its wiki/sources/ summary, enough for build_site to run."""
    src_dir = vault / "wiki" / "sources" / project
    raw_dir = vault / "raw" / "sessions" / project
    src_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / f"{stem}.md").write_text(
        f'---\ntitle: "{stem}"\ntype: source\nproject: {project}\ndate: 2026-01-01\n'
        f"source_file: raw/sessions/{project}/{stem}.md\n---\n\n## Connections\n",
        encoding="utf-8",
    )
    (raw_dir / f"{stem}.md").write_text(
        f'---\ntitle: "{stem}"\ntype: source\nproject: {project}\nslug: {stem}\n'
        f"date: 2026-01-01\nsource_file: raw/sessions/{project}/{stem}.md\n"
        'token_totals: {"input": 1, "output": 1, "cache_creation": 0, "cache_read": 0}\n'
        f"---\n\n# {stem}\n",
        encoding="utf-8",
    )


def _all_args(*flags: str):
    return build_parser().parse_args(["all", *flags])


class _TerminalStdin(io.StringIO):
    """A stdin stand-in whose ``isatty`` is true, the way a real wizard run needs."""

    def isatty(self) -> bool:
        return True


def _pretend_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Satisfy the wizard's terminal guard; the answers themselves stay scripted."""
    monkeypatch.setattr(sys, "stdin", _TerminalStdin())


# ─── R1 -- one plain-language question, two real choices ──────────────────


def test_job_question_names_outcome_folders_and_cost_for_both_choices() -> None:
    """The daily-job question names each outcome, its folders, and its AI-provider cost."""
    q = _JOB_QUESTION
    assert "Ingest only" in q
    assert "Maintain" in q
    assert "Never contacts an AI provider" in q and "no cost" in q
    assert "Sends session text to your AI provider" in q and "costs money" in q
    assert "Writes: raw/, site/" in q
    assert "Writes: raw/, wiki/sources/, wiki/candidates/, site/" in q


# ─── R2/R4 -- extras and the graph-builder question are ingest-only ───────


def test_ingest_choice_writes_no_extras_or_graph_choice_end_to_end(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Pressing Enter for Ingest only never asks Extras/Builder, and the *written* status
    file (not just the in-memory plan) carries graph=none / lint_fail=never -- proving the
    whole chain from scripted input through the real, unmocked run_install."""
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        "llmwiki.automation_install.activate_scheduler",
        lambda **kwargs: {
            "scheduler_activated": True,
            "scheduler_backend": "systemd",
            "scheduler_units_dir": "/home/USER/.config/systemd/user",
            "scheduler_active": True,
            "scheduler_error": None,
        },
    )
    _pretend_tty(monkeypatch)
    vault = tmp_path / "vault"
    prompts: list[str] = []
    answers = iter(["1"] + [""] * 8)

    def fake_input(prompt: str) -> str:
        prompts.append(prompt)
        return next(answers)

    monkeypatch.setattr("builtins.input", fake_input)
    args = cli.build_parser().parse_args(["install-automation", "--vault", str(vault)])
    code = cli.cmd_install_automation(args)

    assert code == 0
    asked = " ".join(prompts)
    assert "Extras" not in asked
    assert "Builder" not in asked

    status = load_status(vault)
    assert status is not None
    assert status["job"] == "ingest"
    assert status["graph"] == "none"
    assert status["lint_fail"] == "never"


# ─── R3 -- quality checks always run for Maintain, never fail by default ──


def test_lint_findings_never_fail_the_job_by_default_but_do_at_the_chosen_policy(
    vault: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Real, unmocked build + lint over a deliberately invalid page: default policy still
    exits 0 with the findings printed; --lint-fail errors exits 2 for the same vault.

    Only ``resolve_state_file`` is stubbed (so the lint step's bookkeeping write lands in
    tmp_path instead of the real llmwiki-state.json) -- sync and synth are switched off via
    --no-sync/--no-synth so no other real infrastructure is touched.
    """
    _write_session(vault)
    (vault / "wiki" / "entities").mkdir(parents=True, exist_ok=True)
    # frontmatter_validity (severity=error) fires on an out-of-range confidence value.
    (vault / "wiki" / "entities" / "Bogus.md").write_text(
        '---\ntitle: "Bogus"\ntype: entity\nconfidence: 2.5\n---\n\n# Bogus\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(pipeline, "resolve_state_file", lambda: vault / "state.json")

    default_args = _all_args("--no-sync", "--no-synth", "--skip-graph", "--vault", str(vault))
    rc = cli.cmd_all(default_args)
    assert rc == 0, "quality findings must not fail the job when --lint-fail is unset"

    strict_args = _all_args(
        "--no-sync", "--no-synth", "--skip-graph", "--lint-fail", "errors", "--vault", str(vault)
    )
    rc = cli.cmd_all(strict_args)
    assert rc == 2, "the chosen failure policy must still be honoured"


def test_wrapper_script_truncates_the_log_instead_of_appending(tmp_path: Path) -> None:
    """R3 AC: 'the log contains only the latest run's output' -- the wrapper must
    truncate (``>``) the log file each run, never append (``>>``)."""
    text = render_wrapper_script(
        plan=AutomationPlan(job="maintain"),
        python_bin="python3",
        working_dir=tmp_path,
        log_path=tmp_path / "last-automation.log",
    )
    log = shlex.quote(str(tmp_path / "last-automation.log"))
    assert f">{log} 2>&1" in text
    assert f">>{log}" not in text


# ─── R5 -- declining the confirmation writes nothing ───────────────────────


def test_declining_writes_nothing_and_a_later_real_install_still_succeeds(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Decline once through the real CLI entrypoint (``cli.main``, not the bare
    ``cmd_install_automation`` helper): nothing lands on disk. A second, --yes install
    right after must still succeed cleanly -- declining must not leave partial state
    that blocks a later real install."""
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    _pretend_tty(monkeypatch)
    vault = tmp_path / "vault"
    vault.mkdir()
    answers = iter(["2", "", "", "", "ollama", "", "", "", "n"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))

    code = cli.main(["install-automation", "--vault", str(vault)])
    assert code == 0
    assert load_status(vault) is None
    assert not (tmp_path / ".llmwiki").exists()
    assert not (tmp_path / "config.json").exists()

    units = tmp_path / "units"
    code = cli.main([
        "install-automation", "--yes", "--job", "maintain",
        "--units-dir", str(units), "--vault", str(vault), "--force-platform", "linux",
        "--no-activate",
    ])
    assert code == 0
    status = load_status(vault)
    assert status is not None and status["job"] == "maintain"
    assert (units / "llmwiki-maintain.sh").is_file()


# ─── R6 -- `all` means all of it, and the default install spends nothing ──


def test_bare_all_resolves_the_real_dummy_backend_with_no_network_call(
    vault: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The headline risk (tech-considerations §Impact): a default `llmwiki all` must
    never contact a provider. ``resolve_backend`` runs FOR REAL here (never mocked) --
    only the config lookup is forced empty (independent of whatever the operator's own
    clone config.json happens to contain) and the heavier stages are stubbed the same
    way tests/test_all_optout.py already does. A raw ``socket.connect`` is blocked so a
    wrong backend selection fails loudly instead of silently phoning home.
    """
    def _blocked_connect(*_a, **_k):
        raise AssertionError("network call attempted during a supposedly offline run")

    monkeypatch.setattr(socket.socket, "connect", _blocked_connect)
    monkeypatch.setattr(pipeline, "_load_sessions_config", lambda: {})

    captured: dict = {}

    def fake_synth(*, backend, **_kwargs):
        captured["backend"] = backend
        return {"total_scanned": 0, "new_files": 0, "synthesized": 0, "skipped": 0, "errors": []}

    args = _all_args("--no-sync", "--skip-graph", "--skip-lint", "--vault", str(vault))
    with (
        patch.object(pipeline, "synthesize_new_sessions", side_effect=fake_synth),
        patch.object(pipeline, "run_harvest", return_value=0),
        patch.object(pipeline, "build_site", return_value=0),
    ):
        rc = cli.cmd_all(args)

    assert rc == 0
    assert "backend" in captured, "resolve_backend's result must reach synthesize_new_sessions"
    assert captured["backend"].name == "DummySynthesizer"
    assert captured["backend"].is_llm is False


def test_legacy_with_sync_with_synth_flags_still_parse_through_main(
    vault: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An already-installed scheduled command (the old profile-C shape) must not die on
    argparse's 'unrecognized arguments' -- routed through ``cli.main`` end to end, not
    just ``cmd_all`` directly, so the subparser wiring itself is exercised too."""
    monkeypatch.setattr(pipeline, "_load_sessions_config", lambda: {})
    with (
        patch.object(pipeline, "_maybe_print_optout_notice"),
        patch.object(pipeline, "convert_all", return_value=0),
        patch.object(pipeline, "refresh_synth_pending"),
        patch.object(pipeline, "reindex_wiki", return_value=None),
        patch.object(pipeline, "synthesize_new_sessions", return_value={
            "total_scanned": 0, "new_files": 0, "synthesized": 0, "skipped": 0, "errors": [],
        }),
        patch.object(pipeline, "run_harvest", return_value=0),
        patch.object(pipeline, "build_site", return_value=0),
        patch.object(pipeline, "_run_lint_step", return_value=(0, {})),
    ):
        rc = cli.main([
            "all", "--with-sync", "--with-synth", "--skip-graph", "--vault", str(vault),
        ])
    assert rc == 0


def test_all_help_lists_every_stage_and_its_opt_out_flag() -> None:
    """R6 AC: the built-in help lists the stages in order and names each stage's opt-out."""
    all_parser = build_parser()._subparsers._group_actions[0].choices["all"]  # noqa: SLF001
    help_text = all_parser.format_help()
    assert "sync" in help_text and "synth" in help_text and "graph" in help_text and "lint" in help_text
    for flag in ("--no-sync", "--no-synth", "--skip-graph", "--skip-lint"):
        assert flag in help_text


# ─── R7 -- the scheduled command is a single run ───────────────────────────


def test_ingest_scheduled_command_is_byte_identical_to_pre_change_profile_a(
    tmp_path: Path,
) -> None:
    """Pre-#156, ``profile_command("A", py, root)`` returned exactly
    ``f"cd {quoted(root)} && {quoted(py)} -m llmwiki sync"`` (confirmed against
    ``git show main:llmwiki/automation_install.py``). Runs the real, on-disk
    ``run_install`` -- not ``plan_command`` in isolation -- and reads the actual
    wrapper file it wrote, so this is the whole install path, not just the composer.
    """
    units = tmp_path / "units"
    working_dir = tmp_path / "clone"
    python_bin = "/usr/bin/python3"
    run_install({
        "plan": AutomationPlan(job="ingest"),
        "schedule": "0 8 * * *",
        "working_dir": working_dir,
        "python_bin": python_bin,
        "vault_root": tmp_path / "vault",
        "write_units_dir": units,
        "force_platform": "linux",
        "activate": False,
    })
    wrapper = (units / "llmwiki-maintain.sh").read_text(encoding="utf-8")
    expected_command = f"cd {shlex.quote(str(working_dir))} && {shlex.quote(python_bin)} -m llmwiki sync"
    assert expected_command in wrapper
    # Nothing from the maintain vocabulary should have leaked into the ingest command.
    assert "synth" not in wrapper.split("&&", 1)[1]
    assert "build" not in wrapper.split("&&", 1)[1]


def test_maintain_scheduled_command_is_one_invocation_not_a_chain(tmp_path: Path) -> None:
    """Old profile B chained three commands with ' && '; the new maintain command must
    be a single ``llmwiki all`` invocation -- exactly one '&&' in the whole line (the
    directory change), never a second one joining a follow-up command."""
    units = tmp_path / "units"
    plan = AutomationPlan(job="maintain", graph="builtin", lint_fail="errors")
    run_install({
        "plan": plan,
        "schedule": "0 8 * * 1-5",
        "working_dir": tmp_path / "clone",
        "python_bin": sys.executable,
        "vault_root": tmp_path / "vault",
        "write_units_dir": units,
        "force_platform": "linux",
        "activate": False,
    })
    wrapper = (units / "llmwiki-maintain.sh").read_text(encoding="utf-8")
    command_line = next(line for line in wrapper.splitlines() if "-m llmwiki" in line)
    assert command_line.count("&&") == 1
    assert plan_command(plan, python_bin=sys.executable, working_dir=tmp_path / "clone") in command_line


# ─── R9 -- the Automation panel says what the job does ────────────────────


def test_home_page_shows_a_readable_label_for_a_legacy_letter_only_status(tmp_path: Path) -> None:
    """A status file an older llmwiki wrote -- only ``profile``/``hour``/``minute``, none
    of the new keys -- must still render a readable panel, never a bare letter, blank,
    or exception."""
    path = status_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"profile": "C", "hour": 8, "minute": 0}', encoding="utf-8")
    panel = render_automation_panel(tmp_path)
    assert "Maintain" in panel
    assert "<strong>C</strong>" not in panel
    assert "Scheduler profile" not in panel
    assert panel.strip() != ""


def test_home_page_shows_a_readable_label_for_a_new_format_status(tmp_path: Path) -> None:
    """The new-format status renders the job in words and the schedule in words, plus
    whether it can spend money -- reached through the real ``run_install`` write path."""
    plan = AutomationPlan(job="maintain", graph="builtin")
    run_install({
        "plan": plan,
        "schedule": "0 8 * * 1-5",
        "working_dir": tmp_path,
        "python_bin": sys.executable,
        "vault_root": tmp_path,
        "activate": False,
    })
    panel = render_automation_panel(tmp_path)
    assert "Maintain + graph (built-in)" in panel
    assert "Weekdays at 08:00" in panel
    assert "can spend money at your AI provider" in panel


# ─── R10 -- newcomer docs point at automation instead of chores ───────────


def test_cheatsheet_presents_automation_before_the_manual_alternative() -> None:
    text = CHEATSHEET.read_text(encoding="utf-8")
    setup_idx = text.index("llmwiki install-automation")
    manual_idx = text.index("For a one-off run of the same pipeline by hand")
    assert setup_idx < manual_idx
    # Stale facts the tech spec flagged must be fixed, consistently.
    assert "llm-notebook[graph]" not in text
    assert "pip install llm-wiki[graph]" in text
    assert "11 CLI commands" not in text
    counts = {int(n) for n in re.findall(r"(\d+) wiki-quality rules", text)}
    assert len(counts) <= 1, f"cheatsheet quality-rule count must not contradict itself: {counts}"


def test_getting_started_and_quickstart_offer_automation_right_after_first_build() -> None:
    for path, build_marker, automation_heading in (
        (GETTING_STARTED, "Open `<vault>/site/index.html`", "## Next: let it run itself"),
        (QUICKSTART, "## 6. Browse the site", "## 7. Hand the loop to a daily job"),
    ):
        text = path.read_text(encoding="utf-8")
        assert text.index(build_marker) < text.index(automation_heading)
        after = text[text.index(automation_heading):]
        assert "llmwiki install-automation" in after
        assert "never contacts an ai provider" in after.lower()


# ─── R11 -- existing installations are told to refresh ────────────────────


def test_upgrade_guide_and_changelog_flag_the_all_behaviour_change() -> None:
    upgrading = UPGRADING.read_text(encoding="utf-8")
    assert "--with-sync" in upgrading and "--with-synth" in upgrading
    assert "--schedule" in upgrading

    changelog = CHANGELOG.read_text(encoding="utf-8")
    unreleased = shipping_section_text(changelog)
    assert "#156" in unreleased
    assert (
        "BREAKING" in unreleased
        or "### Breaking" in unreleased
        or "runs `sync` and `synth`" in unreleased
    )
    assert "runs every stage" in unreleased or "opt-out" in unreleased


def test_rerunning_install_replaces_the_existing_units_not_duplicates_them(tmp_path: Path) -> None:
    """R11 AC: re-running the setup on a machine that already has a scheduled job
    replaces it rather than adding a second one -- unit filenames are fixed, so a
    second real install must leave exactly the same files, now carrying the new plan."""
    units = tmp_path / "units"
    vault_root = tmp_path / "vault"
    common = {
        "working_dir": tmp_path / "clone",
        "python_bin": sys.executable,
        "vault_root": vault_root,
        "write_units_dir": units,
        "force_platform": "linux",
        "activate": False,
    }
    first = run_install({"plan": AutomationPlan(job="ingest"), "schedule": "0 8 * * *", **common})
    files_after_first = sorted(p.name for p in units.iterdir())

    second = run_install({
        "plan": AutomationPlan(job="maintain", lint_fail="warnings"),
        "schedule": "0 9 * * 1-5",
        **common,
    })
    files_after_second = sorted(p.name for p in units.iterdir())

    assert files_after_first == files_after_second, "re-install must not add new unit files"
    assert first["job"] == "ingest"
    assert second["job"] == "maintain"
    wrapper = (units / "llmwiki-maintain.sh").read_text(encoding="utf-8")
    assert "llmwiki all" in wrapper and "--lint-fail warnings" in wrapper
    status = load_status(vault_root)
    assert status is not None and status["job"] == "maintain"
