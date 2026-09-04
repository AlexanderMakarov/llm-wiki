"""llmwiki CLI.

Usage:
    python3 -m llmwiki <command> [options]
    python3 -m llmwiki --help

Canonical loop: ingest (sync / add) → summarise (synth) → review candidates → publish (build).
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import json as _json
import sys
import sys as _sys
import textwrap
import time
from collections.abc import Callable, Sequence
from contextlib import ExitStack
from datetime import UTC, datetime
from datetime import date as _date
from pathlib import Path
from typing import Any

from llmwiki import (
    REPO_ROOT,
    __version__,
    install_agent_kit,
    migrate_broken_provenance,
    migrate_page_kinds,
    migrate_topic_kinds,
    usage,
)
from llmwiki.adapters import REGISTRY, discover_all

# #v1378-review (#691 follow-up): hoist these re-exports from mid-module
# to here so the file passes E402 cleanly. They re-export business
# logic that lives in the proper domain modules now (#611) — kept here
# for any caller still importing from llmwiki.cli.
from llmwiki.adapters.status import adapter_status as _adapter_status  # noqa: F401
from llmwiki.adapters.status import print_adapters_table
from llmwiki.add_doc import add_sources, expected_source_page, remove_raw_docs
from llmwiki.automation_install import (
    AutomationActivationError,
    default_staging_units_dir,
    detect_platform,
    run_install,
)
from llmwiki.automation_plan import (
    DEFAULT_SCHEDULE,
    LEGACY_PROFILE_MAP,
    AutomationPlan,
    GraphChoice,
    LintFail,
    plan_command,
    plan_label,
)
from llmwiki.automation_status import vault_automation_log_path
from llmwiki.build import RAW_DIR, RAW_SESSIONS, build_site
from llmwiki.cache import MODEL_PRICING, resolve_pricing_model
from llmwiki.candidates import (
    KeyFactsBackendError,
    apply_review_summary_to_pipeline,
    discard,
    flip_and_promote,
    list_candidates,
    promote,
    rewrite_key_facts,
    stale_candidates,
)
from llmwiki.candidates import (
    merge as merge_candidate,
)
from llmwiki.candidates_harvest import (
    DEFAULT_MIN_REFS,
    run_harvest,
    summarize_backlog,
)
from llmwiki.candidates_site import apply_candidate_actions

# #691 / #arch-h8: extracted business logic moves out of cli.py.
# cli.py keeps thin re-export wrappers for back-compat with anyone
# doing `from llmwiki.cli import cmd_all, cmd_sync_status, ...`.
from llmwiki.config_schedule import (
    _load_sessions_config,
    apply_default_vault,
    load_default_vault_path,
    load_synthesis_backend,
)
from llmwiki.config_schedule import (
    load_schedule_config as _load_schedule_config,
)
from llmwiki.config_schedule import (
    should_run_after_sync as _should_run_after_sync,
)
from llmwiki.convert import DEFAULT_OUT_DIR, convert_all
from llmwiki.cron_spec import CronError, describe, parse_cron
from llmwiki.graph import build_and_report
from llmwiki.graphify_bridge import build_graphify_graph, is_available, query_graph
from llmwiki.lint import REGISTRY as _LINT_REG
from llmwiki.lint import LintOptions, UnknownRuleError, load_pages, run_all, run_lint, summarize
from llmwiki.lint import rules as _lint_rules  # noqa: F401 — force registration
from llmwiki.lint.report import render_json as _render_lint_json
from llmwiki.lint.report import render_text as _render_lint_text
from llmwiki.pipeline import run_pipeline as _run_pipeline
from llmwiki.pipeline_lock import pipeline_lock
from llmwiki.queue_ops import enqueue_task, queue_status, run_queue
from llmwiki.reindex import (
    apply_reindex,
    plan_reindex,
    seed_index_text,
)
from llmwiki.remove_doc import RemoveIncompleteError, build_remove_plan, execute_remove_plan, format_plan
from llmwiki.source_checkout import SourceCheckoutError, ensure_not_source_checkout
from llmwiki.state_store import (
    IncompatibleStateError,
    check_sync_state_compatible,
    read_state,
    resolve_state_file,
    update_state,
)
from llmwiki.sync.status import (  # noqa: F401
    cmd_sync_status,
)
from llmwiki.synth.estimate import synthesize_estimate_report  # noqa: F401
from llmwiki.synth.pipeline import (
    DEFAULT_SYNTH_CONCURRENCY,
    MAX_SYNTH_CONCURRENCY,
    _discover_raw_sessions,
    _load_state,
    refresh_synth_pending,
    resolve_backend,
    resolve_exclude_headless,
    resolve_include_subagents,
    synthesize_new_sessions,
)
from llmwiki.synth.reporting import (
    print_candidates_pre_run,
    print_source_pages_current_state,
    print_synth_run_summary,
)
from llmwiki.trace import TraceError, TraceResult, trace_page
from llmwiki.usage import UNATTRIBUTED
from llmwiki.vault import describe_vault, resolve_vault
from llmwiki.vault_settings import (
    VAULT_SETTINGS_FILENAME,
    VaultSettingsError,
    disabled_lint_rules,
    load_vault_settings,
    vault_settings_path,
)
from llmwiki.watch import watch as watch_loop

#: Subcommands that write a vault's own content — ``raw/``, ``wiki/`` or
#: ``site/`` — into whatever content root they resolve. With no vault named
#: that root is ``REPO_ROOT``, so these are the commands the source-checkout
#: guard covers: they are what turns a clone into a half-vault. ``add``,
#: ``all`` and ``watch`` are compositions of ``sync`` / ``synth`` / ``build``
#: and are guarded for the same reason. Reporting commands (``lint``,
#: ``query``, ``trace``, ``usage``, ``adapters``) only read, and
#: commands that edit an existing vault in place (``candidates``, ``remove``,
#: ``graph``) have nothing to edit in a checkout whose root can no longer
#: become a vault.
_SOURCE_CHECKOUT_GUARDED_COMMANDS = frozenset(
    {"init", "sync", "synth", "add", "build", "all", "watch"}
)


def _apply_default_vault(args: argparse.Namespace) -> None:
    """Resolve ``args.vault`` from config, then guard the source checkout.

    Every vault-resolving command calls this before it picks a content root,
    which makes it the one place where "no vault named" becomes "write into
    ``REPO_ROOT``" — and therefore the place the guard belongs. The guard is
    keyed on the parsed subcommand name, so it applies at the CLI border and
    leaves direct library calls to the ``cmd_*`` functions alone.
    """
    apply_default_vault(args)
    if getattr(args, "vault", None) is not None:
        return
    command = getattr(args, "cmd", None)
    if command not in _SOURCE_CHECKOUT_GUARDED_COMMANDS:
        return
    try:
        ensure_not_source_checkout(REPO_ROOT, command)
    except SourceCheckoutError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc


def _content_root(args: argparse.Namespace) -> Path:
    """Resolve the content root a command should read and write.

    The vault (``--vault``, else ``config.json`` ``vault.default_path``)
    owns the user's ``raw/`` + ``wiki/``; ``REPO_ROOT`` is the content root
    only in demo/dev mode, when no vault is configured at all. Commands
    take their directory defaults from here — a module-level
    ``REPO_ROOT / "wiki"`` default silently targets the git clone's seed
    content instead of the user's vault.

    A configured-but-unusable vault is a hard error (exit 2), matching
    ``build`` / ``all``. Falling back to the repo would write the user's
    content into the git clone on a typo — exactly what routing through
    here prevents.
    """
    _apply_default_vault(args)
    configured = getattr(args, "vault", None)
    if configured is None:
        return REPO_ROOT
    try:
        return resolve_vault(Path(configured).expanduser()).root
    except (FileNotFoundError, NotADirectoryError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


def cmd_version(args: argparse.Namespace) -> int:
    print(f"llmwiki {__version__}")
    return 0


def cmd_all(args: argparse.Namespace) -> int:
    """Run the full wiki pipeline: sync → synth → build → graph → lint.

    Thin shim — the implementation lives in ``llmwiki.pipeline`` (#691).
    ``run_pipeline`` acquires the vault's ``pipeline_lock`` exactly once and
    calls library functions (``convert_all``, ``synthesize_new_sessions``,
    ``build_site``, ...) directly — never ``cmd_sync`` / ``cmd_synthesize`` /
    ``cmd_build``, which would each try to acquire the same non-reentrant
    lock again and deadlock. AI exports are part of ``build``; there is no
    separate export step.
    """
    if getattr(args, "legacy_with_sync", False) or getattr(args, "legacy_with_synth", False):
        print(
            "note: --with-sync / --with-synth are no longer needed — every stage "
            "runs by default. Use --no-sync / --no-synth to skip one.",
            file=sys.stderr,
        )
    _apply_default_vault(args)
    return _run_pipeline(args)


def cmd_init(args: argparse.Namespace) -> int:
    """Create raw/, wiki/, site/ directory structure.

    #29: scaffold into the configured vault (``--vault`` / ``config.json``
    ``vault.default_path``) so personal data lands outside the git clone.
    With no vault configured the scaffold lands in REPO_ROOT, which
    ``_apply_default_vault`` refuses when REPO_ROOT is an llmwiki source
    checkout (#109).
    """
    _apply_default_vault(args)
    base = REPO_ROOT
    if getattr(args, "vault", None):
        vault_arg = Path(args.vault).expanduser()
        # `init` is the bootstrap command: create the vault root if it does
        # not exist yet instead of erroring out (#29 review). Print the
        # creation so a wrong/unmounted path is visible, not silently masked.
        # An existing path that is not a directory still errors via resolve_vault.
        if not vault_arg.exists():
            try:
                vault_arg.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                print(f"error: cannot create vault directory {vault_arg}: {exc}",
                      file=sys.stderr)
                return 2
            print(f"==> created vault directory: {vault_arg}")
        try:
            base = resolve_vault(vault_arg).root
        except (FileNotFoundError, NotADirectoryError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        print(f"==> scaffolding into vault: {base}")

    # The wiki/ folders here are the page-kind homes reindex.CANONICAL_FOLDERS
    # catalogs — a fresh vault has somewhere to file every kind it can write.
    for name in ("raw/sessions", "wiki/sources", "wiki/entities", "wiki/concepts",
                 "wiki/projects", "wiki/syntheses", "site"):
        p = base / name
        p.mkdir(parents=True, exist_ok=True)
        keep = p / ".gitkeep"
        if not keep.exists() and not any(p.iterdir()):
            keep.touch()
        print(f"  {p.relative_to(base)}/")

    # Also create hot/ for per-project caches
    hot_dir = base / "wiki" / "hot"
    hot_dir.mkdir(parents=True, exist_ok=True)
    keep = hot_dir / ".gitkeep"
    if not keep.exists():
        keep.touch()

    # Seed index/log/overview + navigation files if not present
    seeds = {
        # #71: the empty catalog lives in llmwiki/reindex.py so `init` and
        # `reindex` cannot disagree about the header or the (count) headings.
        "wiki/index.md": seed_index_text(),
        "wiki/overview.md": '---\ntitle: "Overview"\ntype: synthesis\nsources: []\nlast_updated: ""\n---\n\n# Overview\n\n*This page is maintained by your coding agent.*\n',
        "wiki/log.md": "# Wiki Log\n\nAppend-only chronological record of all operations.\n\nFormat: `## [YYYY-MM-DD] <operation> | <title>`\n\n---\n",
        "wiki/hints.md": '---\ntitle: "Navigation Hints"\ntype: navigation\nlast_updated: ""\n---\n\n# Hints\n\nWriting conventions, entity naming rules, and navigation guidance.\nCustomize this file for your project.\n',
        "wiki/hot.md": '---\ntitle: "Hot Cache"\ntype: navigation\nlast_updated: ""\nauto_maintained: true\n---\n\n# Hot Cache\n\n*Auto-maintained. Last 10 session summaries.*\n',
        "wiki/MEMORY.md": '---\ntitle: "Cross-Session Memory"\ntype: navigation\nlast_updated: ""\nmax_lines: 200\n---\n\n# MEMORY\n\n*200-line cap. Auto-consolidated by Auto Dream.*\n\n## User\n\n## Feedback\n\n## Project\n\n## Reference\n',
        "wiki/SOUL.md": '---\ntitle: "Wiki Identity"\ntype: navigation\nlast_updated: ""\n---\n\n# SOUL\n\nThis wiki compiles raw session transcripts into structured, interlinked pages.\nCustomize this file to set your wiki\'s voice and purpose.\n',
        "wiki/CRITICAL_FACTS.md": '---\ntitle: "Critical Facts"\ntype: navigation\nlast_updated: ""\n---\n\n# Critical Facts\n\n- raw/ is immutable — never modify files under raw/\n- Wiki uses Obsidian-style double-bracket syntax for cross-references\n- Confidence: 0.0-1.0, 4-factor formula\n- Lifecycle: draft > reviewed > verified > stale > archived\n',
    }

    # v1.0 (#153): seed dashboard.md from examples/wiki_dashboard.md template.
    # The template ships with the code, so it always reads from REPO_ROOT;
    # the copy lands in the (possibly vault) base.
    dashboard_template = REPO_ROOT / "examples" / "wiki_dashboard.md"
    dashboard_target = base / "wiki" / "dashboard.md"
    if dashboard_template.is_file() and not dashboard_target.is_file():
        dashboard_target.write_text(
            dashboard_template.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        print("  seeded wiki/dashboard.md")
    for rel, content in seeds.items():
        p = base / rel
        if not p.exists():
            p.write_text(content, encoding="utf-8")
            print(f"  seeded {p.relative_to(base)}")
    return 0


def cmd_sync(args: argparse.Namespace) -> int:
    """Convert .jsonl sessions to markdown using the enabled adapters."""
    # G-03 (#289): `sync --status` short-circuits into the status reporter.
    if getattr(args, "status", False):
        return cmd_sync_status(args)

    _apply_default_vault(args)


    # v1.2 (#54): vault-overlay mode — resolve the vault early so bad
    # paths fail before we spend time converting sessions.
    # #470: actually wire the resolved vault root through to convert_all.
    # Previously this block printed a banner and then called convert_all
    # with no vault/out_dir argument, so all 500+ sessions wrote to the
    # repo's raw/sessions/ instead of the vault. The summary line said
    # "507 converted" but the vault directory was empty.
    vault_path = getattr(args, "vault", None)
    out_dir = DEFAULT_OUT_DIR
    state_file = resolve_state_file()
    if vault_path:
        try:
            vault = resolve_vault(vault_path)
        except (FileNotFoundError, NotADirectoryError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        print(f"==> {describe_vault(vault)}")
        if args.allow_overwrite:
            print("  --allow-overwrite: existing vault pages may be clobbered")
        # Route writes into the vault so a vault-mode sync actually
        # populates the vault. State file is configured at the CLI border
        # via ``apply_default_vault`` → ``configure_state_file``.
        out_dir = vault.root / "raw" / "sessions"

    # #29: downgrade / corrupt-state guard. An older engine (or a truncated
    # write) that reads the vault's unified state as "empty" would silently
    # reconvert the whole corpus and duplicate raw/. Hard-stop before we
    # spend time converting; --force-resync is the explicit escape hatch and
    # implies a full reconvert.
    force_resync = getattr(args, "force_resync", False)
    try:
        check_sync_state_compatible(state_file, force_resync=force_resync)
    except IncompatibleStateError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    force = args.force or force_resync

    # PR #19 field report: two llmwiki processes on one vault corrupt each
    # other's site resets — serialize the mutating pipeline on a vault lock.
    lock_root = vault.root if vault_path else REPO_ROOT
    with pipeline_lock(lock_root):
        rc = convert_all(
            adapters=args.adapter,
            out_dir=out_dir,
            state_file=state_file,
            since=args.since,
            project=args.project,
            include_current=args.include_current,
            force=force,
            fail_on_errors=getattr(args, "fail_on_errors", False),
        )
        refresh_synth_pending(
            raw_dir=(vault.root / "raw" / "sessions") if vault_path else None,
            docs_dir=(vault.root / "raw" / "docs") if vault_path else None,
            wiki_sources_dir=(vault.root / "wiki" / "sources") if vault_path else None,
            state_file=state_file,
        )

        # v1.0 (#157): auto-build and auto-lint after sync.
        # --no-build and --no-lint let users opt out.
        # #470: when --vault was given, point the auto-build at the vault's
        # site/ tree too — otherwise the build silently writes to the
        # repo's site/ and the user's vault stays empty.
        if rc == 0:
            schedule = _load_schedule_config()
            site_root = (vault.root / "site") if vault_path else (REPO_ROOT / "site")
            # #54: read/graph the vault's wiki/ (not the repo's demo wiki).
            wiki_dir = (vault.root / "wiki") if vault_path else (REPO_ROOT / "wiki")
            if args.auto_build and _should_run_after_sync(schedule.get("build", "on-sync")):
                print("  auto-build: regenerating site/...")
                # #54 vault-overlay: read the freshly-synced sessions from the
                # vault, not the repo's empty raw/ (which makes auto-build fail
                # with "RAW_SESSIONS does not exist" right after a vault sync).
                raw_sessions = (vault.root / "raw" / "sessions") if vault_path else RAW_SESSIONS
                raw_dir = (vault.root / "raw") if vault_path else RAW_DIR
                # #414: sync has explicit user opt-in to mutate wiki/, so it's
                # the right place to seed project stubs.
                build_site(out_dir=site_root, seed_project_stubs=True,
                           raw_sessions=raw_sessions, raw_dir=raw_dir,
                           wiki_dir=wiki_dir)
            # Always reconcile wiki/index.md after a successful sync (stubs,
            # new sources, removals) — not just when auto-build (the only
            # step that seeds project stubs) ran.
            plan = plan_reindex(wiki_dir)
            if plan is not None and plan.changed:
                apply_reindex(plan)
                print(f"  reindex: index.md +{len(plan.added)} listed, "
                      f"-{len(plan.removed)} dead link(s)")
            if args.auto_lint and _should_run_after_sync(schedule.get("lint", "manual")):
                print("  auto-lint: running wiki lint...")
                # #470: lint the vault's wiki/, not the repo's, when in
                # vault-overlay mode.
                pages = load_pages(wiki_dir) if vault_path else load_pages()
                issues = run_all(pages)
                summary = summarize(issues)
                print(f"  lint: {sum(summary.values())} issues "
                      f"({summary.get('error', 0)} errors, "
                      f"{summary.get('warning', 0)} warnings)")
    return rc


# _load_schedule_config + _should_run_after_sync moved to
# llmwiki/config_schedule.py and re-exported at top of file (#691).


def cmd_build(args: argparse.Namespace) -> int:
    """Build the static HTML site."""
    _apply_default_vault(args)
    # v1.2 (#54): vault-overlay mode. Validate the path up front so a
    # typo fails fast before the build walks raw/.
    raw_sessions, raw_dir, out_dir = RAW_SESSIONS, RAW_DIR, args.out
    wiki_dir = REPO_ROOT / "wiki"
    lock_root = REPO_ROOT
    if getattr(args, "vault", None):
        try:
            vault = resolve_vault(args.vault)
        except (FileNotFoundError, NotADirectoryError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        print(f"==> {describe_vault(vault)}")
        # Read sessions from the vault, and (unless --out was overridden)
        # write the site under the vault so a vault build doesn't silently
        # populate the repo's site/.
        raw_dir = vault.root / "raw"
        raw_sessions = raw_dir / "sessions"
        wiki_dir = vault.root / "wiki"
        lock_root = vault.root
        if args.out == REPO_ROOT / "site":
            out_dir = vault.root / "site"

    with pipeline_lock(lock_root):
        return build_site(
            out_dir=out_dir,
            synthesize=args.synthesize,
            claude_path=args.claude,
            search_mode=args.search_mode,
            seed_project_stubs=getattr(args, "seed_project_stubs", False),
            raw_sessions=raw_sessions,
            raw_dir=raw_dir,
            wiki_dir=wiki_dir,
            local_root=getattr(args, "local_root", "") or None,
        )


def cmd_usage(args: argparse.Namespace) -> int:
    """Report local MCP tool-usage telemetry (#26).

    Folds the per-process ``usage/`` logs into totals and prints them
    next to the synthesis *cost* already persisted in state, so the
    "is this wiki earning its synthesis spend?" question is answerable
    at a glance. Local-only — reads files, never the network.
    """

    _apply_default_vault(args)
    root = Path(args.vault).expanduser().resolve() if getattr(args, "vault", None) else REPO_ROOT

    if getattr(args, "compact", False):
        usage.compact(root)

    consumption = usage.combined_totals(root)

    estimate = read_state(getattr(args, "state_file", None)).get("synth", {}).get("estimate", {})
    cost = {
        "full_force_usd": float(estimate.get("full_force_usd", 0.0) or 0.0),
        "incremental_usd": float(estimate.get("incremental_usd", 0.0) or 0.0),
        "updated_at": str(estimate.get("updated_at", "")),
    }

    if getattr(args, "json", False):
        print(json.dumps({"consumption": consumption, "cost": cost}, indent=2))
        return 0

    _print_usage_report(consumption, cost)
    return 0


def _print_usage_report(consumption: dict[str, Any], cost: dict[str, Any]) -> None:

    total_calls = consumption["total_calls"]
    print(f"MCP tool usage — {total_calls} calls, "
          f"{consumption['total_resp_bytes'] / 1024:.1f} KiB served")
    if not total_calls:
        print("  (no tool calls logged yet)")
    else:
        print(f"  {'tool':<22}{'calls':>7}{'zero-hit':>10}{'bytes':>12}")
        for tool, s in sorted(consumption["per_tool"].items(),
                              key=lambda kv: kv[1]["calls"], reverse=True):
            print(f"  {tool:<22}{s['calls']:>7}"
                  f"{s['zero_hit_rate'] * 100:>9.0f}%{s['resp_bytes']:>12}")
        if consumption["per_project"]:
            print("  by caller project:")
            for proj, s in sorted(consumption["per_project"].items(),
                                  key=lambda kv: kv[1]["calls"], reverse=True):
                # The bucket for calls whose caller couldn't be identified is
                # spelled out rather than printed as a project name (#51).
                label = "(unattributed)" if proj == UNATTRIBUTED else proj
                print(f"    {label:<20}{s['calls']:>7} calls")

    # Cost side: what it took to synthesize the data being consumed.
    ff = cost["full_force_usd"]
    if ff:
        line = f"synthesis cost (full corpus): ${ff:,.2f}"
        if cost["incremental_usd"]:
            line += f"   incremental: ${cost['incremental_usd']:,.2f}"
        print(line)
    else:
        print("synthesis cost: unknown (run `llmwiki synth --estimate`)")


def cmd_configure_sources(args: argparse.Namespace) -> int:
    """Interactive probe + enablement for shipped session sources (#182)."""
    from llmwiki.configure_sources import run_configure_sources  # noqa: PLC0415

    return run_configure_sources(yes=bool(getattr(args, "yes", False)))


def cmd_adapters(args: argparse.Namespace) -> int:
    """List available adapters and their config state.

    G-01 (#287): ``configured`` column now shows ``auto``/``explicit``/
    ``off`` (not ``-``/``enabled``/``disabled``) and a new
    ``will_fire`` column says whether the next ``sync`` will pick the
    adapter up.

    G-02 (#288): ``--wide`` disables the description cap.
    """

    discover_all()
    if not REGISTRY:
        print("No adapters registered.")
        return 0

    config = _load_sessions_config()
    wide = bool(getattr(args, "wide", False))
    print_adapters_table(config, wide=wide)
    return 0


def cmd_query(args: argparse.Namespace) -> int:
    """Query the knowledge graph with a natural language question."""
    if not is_available():
        print("error: graphify not installed. Run: pip install llmwiki[graph]", file=sys.stderr)
        return 2
    question = " ".join(args.question)
    result = query_graph(question, depth=args.depth, token_budget=args.budget)
    print(result)
    return 0


def _format_trace_result(result: TraceResult) -> str:
    """Human-readable provenance chain for stdout (no body excerpts)."""
    lines: list[str] = []
    for hop in result.hops:
        title = hop.title or "(untitled)"
        miss = "  (missing)" if hop.status == "missing" else ""
        lines.append(f"{hop.role:<8}{title}  {hop.location}{miss}")
    if len(result.hops) == 1:
        lines.append("(no further provenance)")
    return "\n".join(lines)


def cmd_trace(args: argparse.Namespace) -> int:
    """Print downward provenance: wiki page → source summaries → raw (#122).

    Exit non-zero only when the starting page cannot be resolved
    (:class:`TraceError`). Partial missing hops still exit 0.
    """
    root = _content_root(args)
    try:
        result = trace_page(root, args.page)
    except TraceError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(_format_trace_result(result))
    return 0


def cmd_graph(args: argparse.Namespace) -> int:
    """Build the knowledge graph from wiki/ wikilinks.

    #488: graphify-engine failures (uninstalled, crashes, empty
    result) ALL fall back to the builtin engine so the user always
    gets *some* graph. Only the builtin engine's exit code is
    authoritative for the CLI return value.
    """
    root = _content_root(args)
    engine = getattr(args, "engine", "graphify")
    if engine == "graphify":
        if not is_available():
            print("  graphify not installed — falling back to builtin engine", file=sys.stderr)
            print("  install with: pip install llmwiki[graph]", file=sys.stderr)
            engine = "builtin"
        else:
            try:
                result = build_graphify_graph(
                    wiki_dir=root / "wiki", graph_dir=root / "graph",
                    graphify_out=root / "graphify-out",
                )
            except Exception as e:
                # #488: uncaught graphify exception used to surface as a
                # bare stack trace + non-zero exit. Now we log a warning
                # and fall through to the builtin engine.
                print(f"  graphify engine crashed ({type(e).__name__}: {e}) — "
                      f"falling back to builtin", file=sys.stderr)
                engine = "builtin"
            else:
                if result.get("graph") is not None:
                    return 0
                # #488: empty-result early-return used to fail with rc=1
                # without trying builtin. graphify can legitimately
                # return None for tiny corpora (no edges); the builtin
                # engine handles the same input gracefully.
                print("  graphify returned no graph — falling back to builtin",
                      file=sys.stderr)
                engine = "builtin"

    write_json = args.format in ("json", "both")
    write_html = args.format in ("html", "both")
    return build_and_report(
        write_json_flag=write_json, write_html_flag=write_html,
        wiki_dir=root / "wiki", graph_dir=root / "graph",
    )


# cmd_sync_status + _resolve_key_exists moved to llmwiki/sync/status.py
# and re-exported at top of file (#691).
# `export` and `reindex` CLIs removed: AI exports are part of `build`;
# index reconciliation runs inside `sync` and `synthesize`.


def cmd_lint(args: argparse.Namespace) -> int:
    """Run every registered lint rule against the wiki and print a report."""

    # --wiki-dir is the narrower flag and wins; otherwise lint the vault's
    # wiki, not the clone's seed demo content. The vault's settings file
    # sits beside wiki/, so it follows whichever root won.
    settings_root = args.wiki_dir.parent if args.wiki_dir else _content_root(args)
    wiki_dir = args.wiki_dir or (settings_root / "wiki")
    if not wiki_dir.is_dir():
        print(f"error: wiki directory not found: {wiki_dir}", file=sys.stderr)
        return 2

    # Read the opt-out declaration before anything can print a result: a
    # settings file that cannot be parsed must never yield a clean report.
    try:
        disabled = disabled_lint_rules(load_vault_settings(settings_root))
    except VaultSettingsError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    pages = load_pages(wiki_dir)
    if not pages:
        print(f"  no pages found in {wiki_dir}")
        return 0

    selected = [r.strip() for r in args.rules.split(",") if r.strip()] if args.rules else None
    options = LintOptions(min_refs=getattr(args, "min_refs", DEFAULT_MIN_REFS))
    try:
        outcome = run_lint(pages, selected=selected, disabled=disabled, options=options)
    except UnknownRuleError as exc:
        # Name the file when the bad name came from it — the reader is
        # editing a declaration, not typing --rules.
        origin = (f"{vault_settings_path(settings_root)}: "
                  if any(name in disabled for name in exc.unknown) else "")
        print(f"error: {origin}{exc}", file=sys.stderr)
        return 2

    if args.json:
        print(_json.dumps(_render_lint_json(outcome, len(pages)), indent=2))
    else:
        print(_render_lint_text(
            outcome, len(pages), settings_filename=VAULT_SETTINGS_FILENAME
        ))

    _apply_default_vault(args)

    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    update_state(
        lambda s: (s.setdefault("ops", {}).__setitem__("last_lint_run_at", now) or s),
        resolve_state_file(),
    )

    # Exit code last: returning early on a failing gate is what stopped a
    # failing lint from ever recording that it ran (#150).
    summary = summarize(outcome.issues)
    if args.fail_on_errors and summary.get("error", 0) > 0:
        return 1
    if getattr(args, "fail_on_warnings", False) and summary.get("warning", 0) > 0:
        return 1
    return 0


def cmd_watch(args: argparse.Namespace) -> int:
    """Near-real-time maintain when sessions finish."""
    _apply_default_vault(args)
    vault = getattr(args, "vault", None)
    vault_path = Path(vault) if vault else None
    return watch_loop(
        adapters=getattr(args, "adapter", None),
        interval=getattr(args, "interval", 5.0),
        settle=getattr(args, "settle", 2.0),
        dry_run=getattr(args, "dry_run", False),
        vault=vault_path,
        with_synthesize=not getattr(args, "no_synthesize", False),
        with_build=not getattr(args, "no_build", False),
    )


_JOB_QUESTION = """
What should the daily job do?

  1) Ingest only     Collect new agent sessions into your vault and refresh
                     the site. Never contacts an AI provider — no cost.
                     Writes: raw/, site/

  2) Maintain        Collect new sessions, summarise each one into a wiki page,
                     gather candidate topics for you to review, refresh the
                     site, and report wiki quality findings into the run log.
                     Sends session text to your AI provider — this costs money
                     once a real provider is configured.
                     Writes: raw/, wiki/sources/, wiki/candidates/, site/
"""

_EXTRAS_QUESTION = """
Optional extras (comma-separated numbers, Enter = none):

  1) Build the knowledge graph        Adds a graph of how your pages link
                                      together. Writes: graph/
  2) Fail the job on quality errors   Report the scheduled job as failed when
                                      the quality check finds errors.
  3) Fail the job on quality warnings Report the scheduled job as failed when
                                      the quality check finds warnings or
                                      errors. Stricter than 2.
"""

_BUILDER_QUESTION = """
Which builder should build the graph?

  1) Built-in    Ships with llmwiki. Needs no extra install.
  2) graphify    Richer graph, built by the graphify package. Needs an extra
                 install: pip install llm-wiki[graph]
"""

_SCHEDULE_QUESTION = """
When should the job run?

  1) Every day
  2) Weekdays only (skip weekends)
  3) Once a week
  4) Custom cron expression
"""

_SCHEDULE_CATCHUP_NOTE = """
  If the machine was off at the scheduled time: Linux systemd timers run once after
  wake (Persistent=true). macOS launchd and Windows Task Scheduler wait for the next
  slot — they do not backfill every missed day.
"""

_DAY_QUESTION = """
Which day?

  1) Monday   2) Tuesday   3) Wednesday   4) Thursday
  5) Friday   6) Saturday  7) Sunday
"""

_HOOKS_QUESTION = """
Install agent sync hooks? A SessionStart hook runs `llmwiki sync` whenever you open
a Claude Code or Cursor session — keeping raw/ fresher between daily runs, but firing
on every session start (not only when new transcripts exist). Prefer the OS scheduler
or `llmwiki watch` unless you specifically want sync-on-open.
Type 'install' to opt in (Enter = skip):
"""

_WATCH_QUESTION = """
Will you run `llmwiki watch` yourself for near-real-time updates? If yes, the built
site's Automation panel can show Watch: on as a reminder. This does not install or
start watch — it only records your choice in automation-status.json for the panel.
[y/N]:
"""


def _ask_until[T](prompt: str, default: T, resolve: Callable[[str], T]) -> T:
    """Ask a question until ``resolve`` accepts the answer, then return what it resolved to.

    An empty answer returns ``default``, and so does ``EOFError`` — a piped or
    otherwise non-interactive stdin ends the question instead of spinning. To
    re-ask, ``resolve`` raises :class:`ValueError` carrying the message the user
    should see.
    """
    while True:
        try:
            raw = input(prompt).strip()
        except EOFError:
            return default
        if not raw:
            return default
        try:
            return resolve(raw)
        except ValueError as exc:
            print(f"  {exc}")


def _ask_choice(prompt: str, valid: Sequence[str], default: str, *, multi: bool = False) -> str:
    """Ask a question whose answers are a fixed set, re-asking until one of them is given.

    Answers match case-insensitively and come back spelled the way ``valid``
    spells them. With ``multi`` the answer is a comma-separated list and the
    result is the accepted items joined by commas; an empty answer returns
    ``default`` either way.
    """
    options = {choice.lower(): choice for choice in valid}

    def resolve(raw: str) -> str:
        items = [part.strip() for part in raw.split(",")] if multi else [raw]
        picked: list[str] = []
        for item in items:
            match = options.get(item.lower())
            if match is None:
                raise ValueError(f"'{item}' is not one of: {', '.join(valid)}")
            picked.append(match)
        return ",".join(picked)

    return _ask_until(prompt, default, resolve)


def _parse_hh_mm(raw: str) -> tuple[int, int]:
    """Parse a 24-hour ``HH:MM`` answer into hour and minute."""
    try:
        hh, mm = raw.split(":", 1)
        hour, minute = int(hh), int(mm)
    except ValueError:
        raise ValueError(f"'{raw}' is not a time — write it as HH:MM, for example 08:00") from None
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError(f"'{raw}' is out of range — hours are 0-23 and minutes are 0-59")
    return hour, minute


def _validated_cron(raw: str) -> str:
    """Return a cron expression unchanged once :func:`parse_cron` accepts it."""
    try:
        parse_cron(raw)
    except CronError as exc:
        raise ValueError(str(exc)) from exc
    return raw


def _ask_graph_builder() -> GraphChoice:
    """Ask which builder draws the knowledge graph, warning when the richer one is missing."""
    print(_BUILDER_QUESTION)
    if _ask_choice("Builder [1]: ", ("1", "2"), "1") != "2":
        return "builtin"
    if not is_available():
        print("  graphify is not installed — the daily job falls back to the built-in builder")
        print("  until you run: pip install llm-wiki[graph]")
    return "graphify"


def _ask_plan() -> AutomationPlan:
    """Ask what the daily job does — the job itself, its extras, and the graph builder."""
    print(_JOB_QUESTION)
    answer = _ask_choice("Choice [2]: ", ("1", "2", "A", "B", "C"), "2")
    legacy = LEGACY_PROFILE_MAP.get(answer)
    job = legacy.job if legacy else ("maintain" if answer == "2" else "ingest")
    if job != "maintain":
        return AutomationPlan(job="ingest")
    print("  Maintain sends session text to your AI provider. Run `llmwiki synth --estimate`")
    print("  to see what that costs before the job first fires.")
    print(_EXTRAS_QUESTION)
    answered = _ask_choice("Extras []: ", ("1", "2", "3"), "", multi=True)
    extras = {item for item in answered.split(",") if item}
    lint_fail: LintFail = "never"
    if "2" in extras and "3" in extras:
        print("  Both failure policies chosen — applying the stricter one: fail on warnings.")
        lint_fail = "warnings"
    elif "3" in extras:
        lint_fail = "warnings"
    elif "2" in extras:
        lint_fail = "errors"
    graph: GraphChoice = _ask_graph_builder() if "1" in extras else "none"
    return AutomationPlan(job="maintain", graph=graph, lint_fail=lint_fail)


def _ask_schedule() -> str:
    """Ask when the job runs, returning a cron expression whichever route the answer took."""
    print(_SCHEDULE_QUESTION)
    choice = _ask_choice("Schedule [1]: ", ("1", "2", "3", "4"), "1")
    if choice == "4":
        return _ask_until(f"Cron expression [{DEFAULT_SCHEDULE}]: ", DEFAULT_SCHEDULE, _validated_cron)
    day_of_week = "*"
    if choice == "2":
        day_of_week = "1-5"
    elif choice == "3":
        print(_DAY_QUESTION)
        # Cron numbers days 1=Monday … 6=Saturday and accepts 7 for Sunday, so
        # the answer is already the day-of-week field.
        day_of_week = _ask_choice("Day [1]: ", ("1", "2", "3", "4", "5", "6", "7"), "1")
    hour, minute = _ask_until("Time HH:MM [08:00]: ", (8, 0), _parse_hh_mm)
    print(_SCHEDULE_CATCHUP_NOTE)
    return f"{minute} {hour} * * {day_of_week}"


def _confirm_plan(plan: AutomationPlan, schedule: str, vault: Path | None = None) -> bool:
    """Print the job, the schedule, and the exact command line, then ask whether to write it.

    ``vault`` is the one the scheduled command will name, so the line shown here
    is the line that gets installed. An empty answer is a yes, and an answer the
    question does not recognise is re-asked. Consent has to be typed: stdin ending
    without one is a no.
    """
    vault_root = vault if vault is not None else (load_default_vault_path() or REPO_ROOT)
    log_path = vault_automation_log_path(vault_root)
    print()
    print("About to schedule:")
    print(f"  Job:      {plan_label(plan)}")
    print(f"  When:     {describe(parse_cron(schedule))}  (cron: {schedule})")
    print(f"  Command:  {plan_command(plan, python_bin=sys.executable, working_dir=REPO_ROOT, vault=vault)}")
    print(f"  Run log:  {log_path}  (truncated each run)")
    print()
    while True:
        try:
            answer = input(
                "Write scheduler files and automation status now? [Y/n] "
                "(n = skip this step only): "
            ).strip().lower()
        except EOFError:
            print("  stdin ended before an answer — reading that as 'no'.")
            return False
        if answer in ("", "y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        print(f"  '{answer}' is not one of: y, yes, n, no")


def _write_synth_backend(backend: str) -> None:
    """Record the chosen synthesis backend under ``synthesis.backend`` in ``config.json``."""
    cfg_path = REPO_ROOT / "config.json"
    cfg: dict[str, Any] = {}
    if cfg_path.is_file():
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            cfg = {}
    synth = cfg.setdefault("synthesis", {})
    if isinstance(synth, dict):
        synth["backend"] = backend
    cfg_path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    print(f"  wrote synthesis.backend={backend!r} → config.json")


def _plan_from_flags(args: argparse.Namespace) -> tuple[AutomationPlan, str]:
    """Resolve the plan and the cron schedule from the non-interactive flags.

    ``--job`` wins over the deprecated ``--profile``, and ``--schedule`` wins
    over the deprecated ``--hour`` / ``--minute`` pair; every deprecated flag
    that was used prints a notice naming what replaces it. ``--graph`` and
    ``--lint-fail`` describe the maintain job only, so any other job prints a
    notice naming the flag it is dropping and why.

    Raises:
        CronError: when the resulting schedule is not an expression
            :func:`parse_cron` can translate.
    """
    job = getattr(args, "job", None)
    profile = getattr(args, "profile", None)
    if profile:
        print("note: --profile is deprecated; use --job {ingest,maintain}", file=sys.stderr)
    if job and profile:
        print("note: --job given, so --profile is ignored", file=sys.stderr)
    if job:
        plan = AutomationPlan(job=job)
    elif profile:
        plan = LEGACY_PROFILE_MAP.get(profile.strip().upper(), AutomationPlan())
    else:
        plan = AutomationPlan()
    graph = getattr(args, "graph", None) or "none"
    lint_fail = getattr(args, "lint_fail", None) or "never"
    if plan.job != "maintain":
        if graph != "none":
            print(
                f"note: --graph {graph} is ignored for --job {plan.job}; "
                f"the {plan.job} job runs a plain sync and builds no graph",
                file=sys.stderr,
            )
        if lint_fail != "never":
            print(
                f"note: --lint-fail {lint_fail} is ignored for --job {plan.job}; "
                f"the {plan.job} job runs no lint step",
                file=sys.stderr,
            )
    plan = AutomationPlan(job=plan.job, graph=graph, lint_fail=lint_fail)

    schedule = getattr(args, "schedule", None)
    hour = getattr(args, "hour", None)
    minute = getattr(args, "minute", None)
    if hour is not None or minute is not None:
        print('note: --hour/--minute are deprecated; use --schedule "<cron>"', file=sys.stderr)
    if schedule:
        if hour is not None or minute is not None:
            print("note: --schedule given, so --hour/--minute are ignored", file=sys.stderr)
    elif hour is not None or minute is not None:
        schedule = f"{minute or 0} {hour if hour is not None else 8} * * *"
    else:
        schedule = DEFAULT_SCHEDULE
    parse_cron(schedule)
    return plan, schedule


def _scheduled_command_vault(explicit_vault: str | None) -> Path | None:
    """The ``--vault`` the scheduled command needs, or ``None`` when config resolves it.

    ``explicit_vault`` is the ``--vault`` the user typed, read before the config
    default is filled in. A job installed against any other vault than the one
    ``vault.default_path`` resolves to has to name it, or the scheduled run would
    work on the default vault while its status file sits in the installed one.
    """
    if not explicit_vault:
        return None
    target = Path(explicit_vault).expanduser()
    default = load_default_vault_path()
    if default is not None and default.expanduser().resolve() == target.resolve():
        return None
    return target


def _print_manual_scheduler_activation(write_dir: Path, plat: str) -> None:
    """Copy-paste commands when ``--no-activate`` leaves units on disk only."""
    print("  Scheduler was NOT activated — enable it yourself:")
    if plat == "linux":
        dest = Path.home() / ".config" / "systemd" / "user"
        print(f"    mkdir -p {dest}")
        print(f"    cp {write_dir}/llmwiki-maintain.{{sh,service,timer}} {dest}/")
        print("    systemctl --user daemon-reload")
        print("    systemctl --user enable --now llmwiki-maintain.timer")
    elif plat == "macos":
        dest = Path.home() / "Library" / "LaunchAgents"
        plist = f"{dest}/com.llmwiki.maintain.plist"
        print(f"    cp {write_dir}/com.llmwiki.maintain.plist {dest}/")
        print(f"    launchctl bootstrap gui/$UID {plist}")
    elif plat == "windows":
        xml = write_dir / "llmwiki-maintain-task.xml"
        print(f"    schtasks /Create /TN llmwiki-maintain /XML {xml} /F")
    else:
        print(f"    See unit files under {write_dir}")


def cmd_install_automation(args: argparse.Namespace) -> int:
    """Set up the daily job: what it does, when it runs, then write the scheduler files."""
    command_vault = _scheduled_command_vault(getattr(args, "vault", None))
    _apply_default_vault(args)

    vault = getattr(args, "vault", None)
    vault_root = Path(vault) if vault else (load_default_vault_path() or REPO_ROOT)
    if vault_root is None:
        vault_root = REPO_ROOT

    yes = bool(getattr(args, "yes", False))
    install_hooks = False
    if yes:
        try:
            plan, schedule = _plan_from_flags(args)
        except CronError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        backend = getattr(args, "synth_backend", None) or load_synthesis_backend()
        watch_enabled = bool(getattr(args, "watch_enabled", False))
        write_dir = Path(getattr(args, "units_dir", None) or default_staging_units_dir())
    else:
        if not sys.stdin.isatty():
            print(
                "error: install-automation needs a terminal; "
                "pass --yes with the flags for an unattended install",
                file=sys.stderr,
            )
            return 2
        print("llmwiki install-automation")
        print("  Daily runs with no new sessions are a no-op.")
        plan = _ask_plan()
        schedule = _ask_schedule()
        print()
        backend = _ask_until(
            f"Synth backend [dummy/ollama/claude] (default {load_synthesis_backend()}): ",
            load_synthesis_backend(),
            str,
        )
        print(_HOOKS_QUESTION)
        hooks_answer = _ask_until("Hooks [Enter = skip]: ", "", str)
        install_hooks = hooks_answer.lower() == "install"
        print(_WATCH_QUESTION)
        watch_enabled = _ask_choice("Watch panel [y/N]: ", ("y", "yes", "n", "no"), "n") in (
            "y",
            "yes",
        )
        default_units = Path(getattr(args, "units_dir", None) or default_staging_units_dir())
        print("  Writes unit files to ~/.automation and activates the OS scheduler by default.")
        units = _ask_until(
            f"Staging directory for unit files (Enter = {default_units}): ",
            "",
            str,
        )
        write_dir = Path(units) if units else default_units
        if not _confirm_plan(plan, schedule, command_vault):
            print("  Skipped install-automation — no scheduler files or automation status written.")
            print("  Your vault, adapters, and config.json are unchanged.")
            print("  Run `python3 -m llmwiki install-automation` later to set up the daily job.")
            return 0
        _write_synth_backend(backend)

    activate = bool(getattr(args, "activate", True))
    plat = str(getattr(args, "force_platform", None) or detect_platform())

    try:
        status = run_install({
            "plan": plan,
            "schedule": schedule,
            "working_dir": REPO_ROOT,
            "python_bin": sys.executable,
            "vault_root": vault_root,
            "command_vault": command_vault,
            "write_units_dir": write_dir,
            "watch_enabled": watch_enabled,
            "hooks": ["claude", "cursor"] if install_hooks else [],
            "synth_backend": backend,
            "force_platform": getattr(args, "force_platform", None),
            "activate": activate,
        })
    except AutomationActivationError as exc:
        print(f"error: scheduler activation failed: {exc}", file=sys.stderr)
        return 1

    print(f"  automation status → {vault_root / '.llmwiki' / 'automation-status.json'}")
    print(f"  log path: {status.get('log_path')}")
    for u in status.get("units_written") or []:
        print(f"  wrote {u}")
    if activate and status.get("scheduler_activated"):
        backend_name = status.get("scheduler_backend") or "scheduler"
        active = status.get("scheduler_active")
        if active is True:
            print(f"  Scheduler activated ({backend_name}): timer is enabled.")
        elif active is False:
            print(f"  Scheduler activated ({backend_name}): installed but not yet enabled.")
        else:
            print(f"  Scheduler activated ({backend_name}).")
        print("  Idle days are a no-op.")
    elif not activate:
        _print_manual_scheduler_activation(write_dir, plat)
        print("  Idle days are a no-op.")
    else:
        print("  Enable the timer/plist using your OS instructions; "
              "idle days are a no-op.")
    return 0


def cmd_queue(args: argparse.Namespace) -> int:

    _apply_default_vault(args)
    vault = getattr(args, "vault", None)
    target = resolve_state_file()
    if args.queue_action == "status":
        stat = queue_status(target)
        state = read_state(target)
        items = state.get("queue", {}).get("items", [])
        by_type: dict[str, int] = {}
        for row in items:
            if not isinstance(row, dict):
                continue
            t = str(row.get("task_type") or "unknown")
            by_type[t] = by_type.get(t, 0) + 1
        sync_meta = state.get("sync", {}).get("meta", {})
        print(
            f"queue: total={stat['total']} pending={stat['counts'].get('pending',0)} "
            f"running={stat['counts'].get('running',0)} done={stat['counts'].get('done',0)} "
            f"error={stat['counts'].get('error',0)}"
        )
        print(f"state_file: {target}")
        if vault:
            print(f"vault: {vault}")
        if stat["oldest_pending"]:
            print(f"oldest_pending: {stat['oldest_pending']}")
        if isinstance(sync_meta, dict) and sync_meta.get("last_sync"):
            print(f"last_sync: {sync_meta.get('last_sync')}")
        synth = state.get("synth", {})
        if isinstance(synth, dict):
            print(f"unsynth_total: {int(synth.get('pending_total', 0))}")
        if by_type:
            print("by_type:")
            for name, count in sorted(by_type.items()):
                print(f"  {name}: {count}")
        return 0
    if args.queue_action == "enqueue":
        payload: dict[str, Any] = {}
        if args.source:
            payload["source"] = args.source
        task = enqueue_task(args.task_type, payload, target)
        print(f"enqueued {task['id']} ({args.task_type})")
        return 0
    if not vault:
        print("error: queue run requires --vault <path>", file=sys.stderr)
        return 2
    summary = run_queue(limit=args.limit, vault=vault, state_file=target)
    print(f"processed={summary['processed']} errors={len(summary['errors'])}")
    for err in summary["errors"]:
        print(f"  ! {err}", file=sys.stderr)
    return 1 if summary["errors"] else 0


# Add new migrations here, never as a new top-level command.
# Each record is (name, purpose, when you would run it).
_MIGRATIONS: tuple[tuple[str, str, str], ...] = (
    (
        "state",
        "Merge older per-feature state files into the single llmwiki-state.json the current CLI expects (queue, sync stamps, synth backlog, and related counters).",
        "Run once after an upgrade that introduced unified state, if leftover .llmwiki-* state files still sit beside the vault or you still see split/legacy state behaviour. Safe to re-run; it does not re-ingest sessions or rewrite wiki pages.",
    ),
    (
        "raw-redaction",
        "Rewrite already-synced raw/sessions/*.md so home-path and dash-encoded username segments use the USER placeholder, without re-reading agent session stores.",
        "Run when you publish or share raw/ and still see real usernames encoded in session paths (for example -Users-<you>-…). Prefer this over sync --force: agent stores are often short-lived, and a force re-sync can miss older files or trigger unnecessary synth. Does not touch wiki/ or call a synthesis backend.",
    ),
    (
        "tools-used",
        "Expand opaque CallMcpTool / GetMcpTools entries in raw/sessions frontmatter into concrete mcp__server__tool names by re-reading the originating agent session file when it still exists.",
        "Run after upgrading Analytics / tool-usage views if older synced sessions still show CallMcpTool stubs and the origin transcript is still on disk. Skips files whose origin store is gone (TTL or deleted). Does not synthesise wiki pages or invent tool names.",
    ),
    (
        "page-kinds",
        "Retype wiki pages that still use the removed question or comparison kinds to concept, and move their files into wiki/concepts/.",
        "Run after upgrading past the release that dropped those kinds, if lint or the site still shows question/comparison pages or paths outside concepts/. Does not invent new pages from raw/; it only relocates and retypes existing wiki markdown.",
    ),
    (
        "topic-kinds",
        "Stamp missing (entity) or (concept) labels onto older ## Connections bullets in wiki/sources/ by matching names already present as entity, concept, or candidate pages.",
        "Run when source pages still list bare [[wikilinks]] in Connections without a kind label, after an upgrade that expects those stamps for harvest and display. Reads only existing wiki pages — no LLM call and no new candidate creation.",
    ),
    (
        "broken-provenance",
        "Fix or clear wiki source_file pointers that still name raw/sessions files which are no longer on disk (remap to a same-date candidate when one exists, otherwise clear the hop).",
        "Run after a re-sync or adapter rename left wiki pages pointing at missing raw transcripts (broken Trace / provenance). Does not delete wiki pages and does not convert new sessions.",
    ),
)


def _print_migrate_catalog() -> None:
    for name, purpose, when in _MIGRATIONS:
        print(f"{name}")
        print(f"  What: {purpose}")
        print(f"  When: {when}")


def cmd_migrate(args: argparse.Namespace) -> int:
    """List migrations when unnamed or ``--list``; error if both ``--list`` and a name."""
    named = getattr(args, "migration", None)
    listing = bool(getattr(args, "list_migrations", False))
    if listing and named:
        print(
            "error: --list cannot be combined with a migration name.",
            file=sys.stderr,
        )
        print("To list migrations: llmwiki migrate --list", file=sys.stderr)
        print("To apply one: llmwiki migrate <name> [flags]", file=sys.stderr)
        return 2
    _print_migrate_catalog()
    return 0


def cmd_migrate_state(args: argparse.Namespace) -> int:
    # One-shot v1.4.0 migrator lives under scripts/ (not the package).
    script = REPO_ROOT / "scripts" / "migrate_state_v1_4_0.py"
    spec = importlib.util.spec_from_file_location("migrate_state_v1_4_0", script)
    if spec is None or spec.loader is None:
        print(f"error: migration script missing: {script}", file=sys.stderr)
        return 2
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    report = mod.run_migration(args.state_file)
    mod.print_report(report)
    return 0


def cmd_migrate_raw_redaction(args: argparse.Namespace) -> int:
    """#56: deterministic username redaction rewrite of raw/sessions (no synth)."""

    script = REPO_ROOT / "scripts" / "migrate_raw_encoded_username.py"
    spec = importlib.util.spec_from_file_location(
        "migrate_raw_encoded_username", script
    )
    if spec is None or spec.loader is None:
        print(f"error: migration script missing: {script}", file=sys.stderr)
        return 2
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    vault = getattr(args, "vault", None)
    if not vault:
        print(
            "error: --vault PATH is required (migrate the user's vault, "
            "not the llm-wiki clone)",
            file=sys.stderr,
        )
        return 2
    try:
        report = mod.run_migration(
            vault=Path(vault),
            real_username=getattr(args, "real_username", None),
            replacement_username=getattr(args, "replacement_username", None),
            dry_run=bool(getattr(args, "dry_run", False)),
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    mod.print_report(report)
    return 1 if report["errors"] else 0


def cmd_migrate_tools_used(args: argparse.Namespace) -> int:
    """Expand CallMcpTool frontmatter in raw/sessions from origin stores."""

    script = REPO_ROOT / "scripts" / "migrate_tools_used_mcp.py"
    spec = importlib.util.spec_from_file_location(
        "migrate_tools_used_mcp", script
    )
    if spec is None or spec.loader is None:
        print(f"error: migration script missing: {script}", file=sys.stderr)
        return 2
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    vault = getattr(args, "vault", None)
    if not vault:
        print(
            "error: --vault PATH is required (migrate the user's vault, "
            "not the llm-wiki clone)",
            file=sys.stderr,
        )
        return 2
    report = mod.run_migration(
        vault=Path(vault),
        dry_run=bool(getattr(args, "dry_run", False)),
        config_file=getattr(args, "config", None),
    )
    mod.print_report(report)
    return 1 if report["errors"] else 0


def cmd_install_agent_kit(args: argparse.Namespace) -> int:
    """Copy packaged slash commands and skills into ``--dest`` (#109).

    ``--dest`` is required: the command never guesses at agent directory
    conventions. The kit ships inside the package, so this works from a
    pip or Homebrew install with no checkout on disk.
    """
    report = install_agent_kit.run_install(
        dest=Path(args.dest),
        dry_run=bool(getattr(args, "dry_run", False)),
    )
    install_agent_kit.print_report(report)
    return 1 if report["errors"] else 0


def cmd_migrate_page_kinds(args: argparse.Namespace) -> int:
    """Retype and relocate pages carrying a removed page kind (#109).

    Unlike the other ``migrate-*`` commands this one lives in the package
    rather than under ``scripts/``: only ``llmwiki*`` is packaged, and a user
    upgrading from pip or Homebrew has no checkout to load a script from.
    """
    report = migrate_page_kinds.run_migration(
        vault=Path(args.vault),
        dry_run=bool(getattr(args, "dry_run", False)),
    )
    migrate_page_kinds.print_report(report)
    return 1 if report["errors"] else 0


def cmd_migrate_topic_kinds(args: argparse.Namespace) -> int:
    """Stamp ``(entity|concept)`` onto older source Connections bullets (#174).

    Package-local like ``migrate-page-kinds``: pip/Homebrew installs have no
    ``scripts/`` checkout. Kinds come from existing wiki pages only — no
    synthesis backend or network call.
    """
    report = migrate_topic_kinds.run_migration(
        vault=Path(args.vault),
        dry_run=bool(getattr(args, "dry_run", False)),
    )
    migrate_topic_kinds.print_report(report)
    return 1 if report["errors"] else 0


def cmd_migrate_broken_provenance(args: argparse.Namespace) -> int:
    """Remap or clear wiki hops to missing ``raw/sessions/`` files (#180).

    Package-local like ``migrate-topic-kinds``: pip/Homebrew installs have no
    ``scripts/`` checkout. Prefers same-date / non-headless raw candidates;
    clears unbroken-unmatchable ``source_file`` values without deleting pages.
    """
    report = migrate_broken_provenance.run_migration(
        vault=Path(args.vault),
        dry_run=bool(getattr(args, "dry_run", False)),
    )
    migrate_broken_provenance.print_report(report)
    return 1 if report["errors"] else 0


def _resolve_synthesize_only_paths(paths: list[str], vault_root: Path) -> set[Path]:
    """Resolve repeatable ``synthesize --path`` args under ``vault_root`` (#62).

    Paths may be vault-relative (``raw/sessions/….md``) or absolute under the
    vault. Raises ``ValueError`` with a user-facing message when a path is
    missing, not a file, outside the vault, or not under ``raw/sessions`` /
    ``raw/docs``.
    """
    root = vault_root.expanduser().resolve()
    resolved: set[Path] = set()
    for raw in paths:
        candidate = Path(raw).expanduser()
        if not candidate.is_absolute():
            candidate = root / candidate
        try:
            candidate = candidate.resolve(strict=True)
        except FileNotFoundError as exc:
            raise ValueError(f"path not found: {raw}") from exc
        except OSError as exc:
            raise ValueError(f"path not found: {raw}") from exc
        try:
            rel = candidate.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"path outside vault: {raw}") from exc
        if not candidate.is_file():
            raise ValueError(f"path not found: {raw}")
        parts = rel.parts
        if len(parts) < 3 or parts[0] != "raw" or parts[1] not in ("sessions", "docs"):
            raise ValueError(
                f"path must be under raw/sessions/ or raw/docs/: {raw}"
            )
        resolved.add(candidate)
    return resolved


def _validate_synthesize_path_kinds(
    paths: set[Path],
    vault_root: Path,
    *,
    include_sessions: bool,
    include_docs: bool,
) -> None:
    """Reject ``--path`` targets that conflict with ``--sessions-only`` / ``--docs-only``."""
    root = vault_root.expanduser().resolve()
    for path in paths:
        rel = path.resolve().relative_to(root)
        kind = rel.parts[1]
        if kind == "sessions" and not include_sessions:
            raise ValueError(f"--docs-only cannot target a session: {rel.as_posix()}")
        if kind == "docs" and not include_docs:
            raise ValueError(f"--sessions-only cannot target a doc: {rel.as_posix()}")


def _run_candidate_harvest(args: argparse.Namespace) -> int:
    """Harvest entity/concept candidates from synthesized sources (#90).

    Reads ``wiki/sources/``, never ``raw/``: the extraction already happened
    during synthesis, so there is no per-source synthesis here. The only
    backend work is classifying the harvested names, batched. A vault with
    nothing left to synthesize is exactly the vault with the largest candidate
    backlog, so this must still work when the backend is unreachable — and
    must say so rather than quietly filing everything as unknown.
    """
    wiki_dir = REPO_ROOT / "wiki"
    vault_path = getattr(args, "vault", None)
    if vault_path:
        try:
            wiki_dir = resolve_vault(vault_path).root / "wiki"
        except (FileNotFoundError, NotADirectoryError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

    try:
        backend = resolve_backend(_load_sessions_config())
    except Exception as exc:  # noqa: BLE001 - harvest still proceeds
        print(f"  ! backend unavailable ({exc})", file=sys.stderr)
        backend = None

    rc = run_harvest(
        wiki_dir,
        min_refs=getattr(args, "min_refs", DEFAULT_MIN_REFS),
        backend=backend,
        require_sources=True,
    )
    if rc == 0:
        _refresh_review_counts(wiki_dir)
    return rc


def cmd_synthesize(args: argparse.Namespace) -> int:
    """Synthesize wiki source pages and/or harvest candidates (#90 · #35).

    Wired to ``llmwiki synth``. ``--sources-only`` skips candidate harvest.
    """
    _apply_default_vault(args)

    candidates_only = bool(getattr(args, "candidates_only", False))
    sources_only = bool(getattr(args, "sources_only", False))
    if candidates_only and sources_only:
        print(
            "error: --sources-only and --candidates-only are mutually exclusive",
            file=sys.stderr,
        )
        return 2

    # #118: a hand-typed --concurrency is refused rather than normalized, so a
    # value the run cannot honour never passes silently. The config key stays
    # tolerant, since a typo there must not break automated runs.
    concurrency = getattr(args, "concurrency", None)
    if concurrency is not None and not 1 <= concurrency <= MAX_SYNTH_CONCURRENCY:
        print(
            f"error: --concurrency must be between 1 and {MAX_SYNTH_CONCURRENCY} "
            f"(got {concurrency})",
            file=sys.stderr,
        )
        return 2

    if candidates_only:
        return _run_candidate_harvest(args)

    config: dict = _load_sessions_config()
    path_args = getattr(args, "paths", None) or None
    sessions_only = bool(getattr(args, "sessions_only", False))
    docs_only = bool(getattr(args, "docs_only", False))
    include_sessions = not docs_only
    include_docs = not sessions_only

    if args.estimate:
        if path_args:
            print(
                "error: --path cannot be combined with --estimate",
                file=sys.stderr,
            )
            return 2
        if sessions_only or docs_only:
            print(
                "error: --sessions-only/--docs-only cannot be combined with --estimate",
                file=sys.stderr,
            )
            return 2
        return _synthesize_estimate(args)

    backend = resolve_backend(config)
    print(f"Backend: {backend.name}")

    if args.check:
        if path_args:
            print(
                "error: --path cannot be combined with --check",
                file=sys.stderr,
            )
            return 2
        if sessions_only or docs_only:
            print(
                "error: --sessions-only/--docs-only cannot be combined with --check",
                file=sys.stderr,
            )
            return 2
        available = backend.is_available()
        print(f"Available: {available}")
        return 0 if available else 1

    if not backend.is_available():
        print(
            f"error: backend {backend.name} is not available. "
            "Start the server or change synthesis.backend in config.",
            file=sys.stderr,
        )
        return 1

    # #420: vault-overlay mode isolates raw/wiki to the vault root.
    vault_path = getattr(args, "vault", None)
    raw_dir = wiki_sources_dir = None
    vault_root = REPO_ROOT
    if vault_path:
        try:
            vault = resolve_vault(vault_path)
        except (FileNotFoundError, NotADirectoryError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        # Post-final-review: Vault is a frozen dataclass with no
        # __truediv__ — `vault / "raw"` raises TypeError. cmd_sync at
        # line 205 correctly uses `vault.root / "raw"`; this site was
        # the missed copy. Caught by the multi-agent code review.
        vault_root = vault.root
        raw_dir = vault.root / "raw" / "sessions"
        wiki_sources_dir = vault.root / "wiki" / "sources"

    only_paths = None
    if path_args:
        try:
            only_paths = _resolve_synthesize_only_paths(path_args, vault_root)
            _validate_synthesize_path_kinds(
                only_paths,
                vault_root,
                include_sessions=include_sessions,
                include_docs=include_docs,
            )
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

    # Wall clock for the real run only (#113) — estimate/check return above.
    t0 = time.monotonic()
    summary = synthesize_new_sessions(
        backend=backend,
        force=args.force,
        raw_dir=raw_dir,
        wiki_sources_dir=wiki_sources_dir,
        only_paths=only_paths,
        include_sessions=include_sessions,
        include_docs=include_docs,
        concurrency=concurrency,
    )
    print(
        f"Scanned {summary['total_scanned']}, new {summary['new_files']}, "
        f"synthesized {summary['synthesized']}, skipped {summary['skipped']}"
    )
    if summary["errors"]:
        for err in summary["errors"]:
            print(f"  ! {err}", file=sys.stderr)

    # Ctrl-C: in-flight pages were drained and recorded; collect pending names
    # from what landed (or tell the operator how), then exit 130 — not 1.
    if summary.get("interrupted"):
        if sources_only:
            print("llmwiki synth --candidates-only")
        else:
            harvest_wiki = (
                wiki_sources_dir.parent
                if wiki_sources_dir is not None
                else (REPO_ROOT / "wiki")
            )
            min_refs = getattr(args, "min_refs", DEFAULT_MIN_REFS)
            rc = run_harvest(
                harvest_wiki,
                min_refs=min_refs,
                backend=backend,
                require_sources=False,
            )
            if rc == 0:
                _refresh_review_counts(harvest_wiki)
                print("Pending names collected from written sources.")
            else:
                print(
                    "Harvest after interrupt failed; retry with:",
                    file=sys.stderr,
                )
                print("llmwiki synth --candidates-only")
        return 130

    if summary["errors"]:
        return 1

    # Default `synth`: harvest candidates after sources. `--sources-only` skips this.
    if sources_only:
        print_synth_run_summary(
            synthesized=summary["synthesized"],
            duration_s=time.monotonic() - t0,
            tokens=summary.get("tokens"),
            cost_usd=summary.get("cost_usd"),
        )
        return 0
    harvest_wiki = (
        wiki_sources_dir.parent if wiki_sources_dir is not None else (REPO_ROOT / "wiki")
    )
    min_refs = getattr(args, "min_refs", DEFAULT_MIN_REFS)
    rc = run_harvest(
        harvest_wiki,
        min_refs=min_refs,
        backend=backend,
        require_sources=False,
    )
    if rc == 0:
        _refresh_review_counts(harvest_wiki)
        print_synth_run_summary(
            synthesized=summary["synthesized"],
            duration_s=time.monotonic() - t0,
            tokens=summary.get("tokens"),
            cost_usd=summary.get("cost_usd"),
        )
    return rc


# Alias used by docs / tests that prefer the new name.
cmd_synth = cmd_synthesize


def cmd_add(args: argparse.Namespace) -> int:
    """Add documents to the wiki: convert to Markdown, land under
    raw/docs/ (kbbuilder-compatible layout), then batch synthesize +
    rebuild the site (issue #16).

    Sources may be URLs, files, or folders, freely mixed. Conversion
    and writing happen per source; synthesis and build run ONCE for
    the whole batch. --no-synthesize / --no-build opt out.
    """
    _apply_default_vault(args)

    if args.title and len(args.sources) > 1:
        print("error: --title needs a single source (got "
              f"{len(args.sources)})", file=sys.stderr)
        return 2

    docs_dir = REPO_ROOT / "raw" / "docs"
    vault_root = None
    if getattr(args, "vault", None):
        try:
            vault = resolve_vault(args.vault)
        except (FileNotFoundError, NotADirectoryError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        vault_root = vault.root
        docs_dir = vault_root / "raw" / "docs"

    render = "auto"
    if args.render:
        render = "force"
    elif args.no_render:
        render = "never"

    # PR #19 field report: a concurrent sync/build on the same vault raced
    # this command's post-add build and died mid-site-reset. Serialize all
    # mutating pipeline entry points on the vault lock; dry-run writes
    # nothing, so it stays lock-free.


    with ExitStack() as stack:
        if not args.dry_run:
            stack.enter_context(pipeline_lock(vault_root or REPO_ROOT))
        return _cmd_add_locked(args, docs_dir, vault_root, render)


def _cmd_add_locked(args: argparse.Namespace, docs_dir: Path,
                    vault_root: Path | None, render: str) -> int:
    """Body of cmd_add that runs under the pipeline lock (except dry-run)."""


    state_target = resolve_state_file()
    now_ts = datetime.now(UTC)
    task_id = f"add-sync-{int(now_ts.timestamp() * 1000)}"

    def _track(status: str, *, result_msg: str = "", error_msg: str = "") -> None:
        stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        def _mut(s: dict[str, Any]) -> dict[str, Any]:
            items = s.setdefault("queue", {}).setdefault("items", [])
            row = None
            for it in items:
                if isinstance(it, dict) and it.get("id") == task_id:
                    row = it
                    break
            if row is None:
                row = {
                    "id": task_id,
                    "task_type": "add_doc_sync",
                    "payload": {"sources": list(args.sources)},
                    "created_at": stamp,
                    "attempts": 1,
                }
                items.append(row)
            row["status"] = status
            row["updated_at"] = stamp
            if result_msg:
                row["result"] = result_msg
            if error_msg:
                row["last_error"] = error_msg
            s.setdefault("ops", {})["last_queue_run_at"] = stamp
            return s
        update_state(_mut, state_target)

    result = add_sources(
        list(args.sources), docs_dir,
        title=args.title, project=args.project, tags=tuple(args.tag or ()),
        note=args.note, render=render, dry_run=args.dry_run,
        force_new=args.force_new,
    )

    for title in result["titles"]:
        print(f"  + {title}")
    for w in result["warnings"]:
        print(f"  ~ {w}")
    for e in result["errors"]:
        print(f"  ! {e}", file=sys.stderr)
    if args.dry_run:
        return 2 if result["errors"] else 0
    print(f"  wrote {len(result['written'])} file(s) under {docs_dir}")
    _track("running", result_msg=f"wrote {len(result['written'])} file(s)")

    failed = bool(result["errors"])
    if not result["written"]:
        return 2 if failed else 0

    # Post-steps run once for the whole batch. `add` is synchronous by
    # contract: the docs must come out the other end as real wiki pages
    # in THIS invocation, using the one backend configured for the whole
    # repository (config.json `synthesis.backend`). When synthesis can't
    # deliver, the just-added raw docs are ROLLED BACK — a raw doc with
    # no wiki page is a half-added state nothing else on the machine may
    # ever repair. --no-synthesize is the only way to opt out.
    if not args.no_synthesize:
        backend = resolve_backend(_load_sessions_config())
        raw_dir = wiki_sources_dir = None
        sources_dir = REPO_ROOT / "wiki" / "sources"
        if vault_root:
            raw_dir = vault_root / "raw" / "sessions"
            wiki_sources_dir = vault_root / "wiki" / "sources"
            sources_dir = wiki_sources_dir
        if not backend.is_available():
            removed = remove_raw_docs(result["written"])
            print(f"  ! backend {backend.name} is not available — cannot "
                  f"synthesize. Rolled back {len(removed)} just-added raw "
                  "doc file(s). Set synthesis.backend in config.json "
                  "(claude / ollama / dummy), or re-run with --no-synthesize.",
                  file=sys.stderr)
            return 2
        print(f"Synthesizing with backend: {backend.name}")
        # Only synthesize the docs this `add` just wrote — never drain
        # the whole unsynthesized backlog from an add invocation.
        summary = synthesize_new_sessions(
            backend=backend, raw_dir=raw_dir,
            wiki_sources_dir=wiki_sources_dir,
            only_paths=set(result["written"]),
        )
        print(f"  synthesized {summary['synthesized']}, skipped {summary['skipped']}")
        for err in summary["errors"]:
            print(f"  ! {err}", file=sys.stderr)
        # No half-added docs: every raw doc this run wrote must now have
        # its wiki page. (Pipeline errors about OTHER pending sources are
        # reported above but don't fail the add or touch its docs.)
        missing = [p for p in result["written"]
                   if not expected_source_page(p, sources_dir).exists()]
        if missing:
            removed = remove_raw_docs(missing)
            print(f"  ! rolled back {len(removed)} raw doc file(s) whose "
                  "synthesis produced no wiki page", file=sys.stderr)
            failed = True
            _track("error", error_msg=f"rolled back {len(removed)} unsynthesized raw doc file(s)")

    if not args.no_build:
        raw_sessions, raw_dir_b = RAW_SESSIONS, RAW_DIR
        wiki_dir = REPO_ROOT / "wiki"
        out_dir = REPO_ROOT / "site"
        if vault_root:
            raw_dir_b = vault_root / "raw"
            raw_sessions = raw_dir_b / "sessions"
            wiki_dir = vault_root / "wiki"
            out_dir = vault_root / "site"
        code = build_site(out_dir=out_dir, raw_sessions=raw_sessions,
                          raw_dir=raw_dir_b, wiki_dir=wiki_dir)
        if code:
            failed = True

    # Observability: same grep-parseable format as sync/synthesize.
    # Rolled-back docs are not logged — they are no longer in the wiki.
    log_path = (vault_root or REPO_ROOT) / "wiki" / "log.md"
    if log_path.parent.is_dir():
        day = _date.today().isoformat()
        with log_path.open("a", encoding="utf-8") as fh:
            for rec in result["docs"]:
                if any(p.exists() for p in rec["paths"]):
                    fh.write(f"\n## [{day}] add | {rec['title']}\n")

    refresh_synth_pending(
        raw_dir=(vault_root / "raw" / "sessions") if vault_root else None,
        docs_dir=(vault_root / "raw" / "docs") if vault_root else None,
        wiki_sources_dir=(vault_root / "wiki" / "sources") if vault_root else None,
        state_file=state_target,
    )

    if failed:
        _track("error", error_msg="add command finished with errors")
    else:
        _track("done", result_msg=f"added {len(result['written'])} file(s)")
    return 2 if failed else 0


def cmd_remove(args: argparse.Namespace) -> int:
    """Cascade-remove raw docs and everything derived from them (B2).

    A selector (project name or slug glob, e.g. ``old-project*``) selects
    raw docs under the resolved vault's ``raw/docs/``; the removal drags
    their synth-state keys and ``wiki/sources/`` pages out too, then
    refreshes backlinks / index / log. ``--dry-run`` prints the full
    cascade and touches nothing; a real run needs ``--yes`` (or an
    interactive confirm) — cascade deletion is never silent.
    """
    _apply_default_vault(args)


    vault_root = REPO_ROOT
    if getattr(args, "vault", None):
        try:
            vault_root = resolve_vault(args.vault).root
        except (FileNotFoundError, NotADirectoryError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

    state_file = vault_root / "llmwiki-state.json"
    plan = build_remove_plan(vault_root, args.selector, state_file=state_file)

    if args.dry_run:
        print(format_plan(plan))
        return 0

    if plan.is_empty:
        print(f"remove: selector {args.selector!r} matched nothing — nothing to do.")
        return 0

    print(format_plan(plan))
    if not args.yes:
        if not sys.stdin.isatty():
            print("error: refusing to cascade-remove without confirmation — "
                  "re-run with --yes (or --dry-run to preview).", file=sys.stderr)
            return 2
        reply = input(f"Remove {len(plan.raw_docs)} raw doc(s) and "
                      f"{len(plan.source_pages)} derived page(s)? [y/N] ").strip().lower()
        if reply not in ("y", "yes"):
            print("aborted.")
            return 1

    with pipeline_lock(vault_root):
        # Re-plan under the lock. The preview above was built outside it, and
        # an interactive confirm can sit here for minutes — long enough for a
        # concurrent synthesize to land a page this plan doesn't know about.
        plan = build_remove_plan(vault_root, args.selector, state_file=state_file)
        if plan.is_empty:
            print(f"remove: selector {args.selector!r} matched nothing — nothing to do.")
            return 0
        try:
            result = execute_remove_plan(plan, state_file=state_file)
        except RemoveIncompleteError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
    print(f"  removed {result['raw_docs']} raw doc(s), "
          f"{result['source_pages']} wiki page(s), "
          f"{result['state_keys']} synth-state key(s), "
          f"{result['pending_entries']} pending entry(ies)")
    return 0


def _synthesize_estimate(args: argparse.Namespace | None = None) -> int:
    """Print the G-07 incremental-vs-full-force cost report (v1.1.0 · #50 · #293).

    Transparency over one-liner: reads the state file so the user sees
    exactly which bucket gets billed next. The old ``--estimate`` printed
    a single number without saying whether it covered the whole corpus
    or just the delta.
    """
    args = args or argparse.Namespace(vault=None)
    _apply_default_vault(args)
    raw_sessions = None
    state_keys = None
    wiki_sources_dir = None
    docs_root = None
    execution_model = ""
    pricing_model = None
    pricing_fallback_msg = ""
    loaded_cfg = _load_sessions_config()
    synth_cfg = (loaded_cfg.get("synthesis", {}) if isinstance(loaded_cfg, dict) else {})
    pricing_table = {k: dict(v) for k, v in MODEL_PRICING.items()}
    if isinstance(synth_cfg, dict):
        execution_model = str(synth_cfg.get("claude_model", "")).strip()
        # Optional user override for rate-card drift:
        # synthesis.pricing = {"input": ..., "cached_input": ..., "cache_write": ..., "output": ...}
        pr = synth_cfg.get("pricing")
        if execution_model and isinstance(pr, dict):
            need = {"input", "cached_input", "cache_write", "output"}
            if need.issubset(set(pr.keys())):
                try:
                    pricing_table[execution_model] = {
                        "input": float(pr["input"]),
                        "cached_input": float(pr["cached_input"]),
                        "cache_write": float(pr["cache_write"]),
                        "output": float(pr["output"]),
                    }
                except (TypeError, ValueError):
                    pass
        if execution_model:
            try:
                pricing_model = resolve_pricing_model(execution_model, pricing_table)
            except ValueError:
                pricing_fallback_msg = (
                    f"pricing model fallback: execution model '{execution_model}' has no rate card entry; "
                    "using default pricing model."
                )

    state_target = resolve_state_file()
    vault_root = state_target.parent
    raw_root = vault_root / "raw" / "sessions"
    docs_root = vault_root / "raw" / "docs"
    wiki_sources_dir = vault_root / "wiki" / "sources"
    raw_sessions = _discover_raw_sessions(raw_root)
    state_keys = _load_state(state_target)
    # prefix_tokens is left for the report to derive: what every page pays
    # up front is the CLI's own per-call overhead plus the rendered prompt
    # template, not CLAUDE.md / index.md / overview.md — the `claude`
    # backend never sends the latter two.
    report = synthesize_estimate_report(
        raw_sessions=raw_sessions,
        state_keys=state_keys,
        lean=synth_cfg.get("claude_lean", True) is not False
        if isinstance(synth_cfg, dict)
        else True,
        model=pricing_model,
        pricing_table=pricing_table,
        wiki_sources_dir=wiki_sources_dir,
        raw_root=raw_root,
        docs_root=docs_root,
        include_subagents=resolve_include_subagents(loaded_cfg),
        exclude_headless=resolve_exclude_headless(loaded_cfg),
    )
    pending_rows = [
        {
            "rel": str(it.get("rel", "")),
            "source": str(it.get("source_file", "")),
            "project": str(it.get("project", "unknown")),
            "is_doc": bool(it.get("is_doc", False)),
            "mtime": str(it.get("mtime", "")),
            "agent": str(it.get("agent", "")),
            "usd": float(it.get("usd", 0.0) or 0.0),
        }
        for it in report.get("unsynth_items", [])
        if str(it.get("rel", "")).strip()
    ]
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    pipeline = apply_review_summary_to_pipeline(
        {
            "stages": list(report.get("pipeline_stages") or ["raw", "synthesized"]),
            "rows": list(report.get("pipeline_rows") or []),
            "updated_at": stamp,
        },
        vault_root / "wiki",
    )

    def _mut(s: dict[str, Any]) -> dict[str, Any]:
        synth = s.setdefault("synth", {})
        synth["pending"] = pending_rows
        synth["pending_total"] = len(pending_rows)
        synth["pending_updated_at"] = stamp
        synth["pipeline"] = pipeline
        synth["estimate"] = {
            "updated_at": stamp,
            "execution_model": execution_model or "",
            "pricing_model": str(report.get("model", "")),
            "prefix_tokens": int(report.get("prefix_tokens", 0) or 0),
            "corpus_total": int(report.get("corpus", 0) or 0),
            "corpus_sessions": int(report.get("corpus_sessions", 0) or 0),
            "corpus_docs": int(report.get("corpus_docs", 0) or 0),
            "new_total": int(report.get("new", 0) or 0),
            "new_sessions": int(report.get("new_sessions", 0) or 0),
            "new_docs": int(report.get("new_docs", 0) or 0),
            "incremental_usd": float(report.get("incremental_usd", 0.0) or 0.0),
            "full_force_usd": float(report.get("full_force_usd", 0.0) or 0.0),
            "source_pages_on_disk": int(report.get("source_pages_on_disk", 0) or 0),
            "source_page_stubs": int(report.get("source_page_stubs", 0) or 0),
            "source_pages_sessions": int(report.get("source_pages_sessions", 0) or 0),
            "source_pages_docs": int(report.get("source_pages_docs", 0) or 0),
            "source_pages_other": int(report.get("source_pages_other", 0) or 0),
            "warnings": [str(w) for w in report.get("warnings", []) if str(w).strip()],
        }
        return s

    update_state(_mut, state_target)

    for w in report["warnings"]:
        print(f"warning: {w}")
    print("warning: cost estimate uses a local static rate card and token heuristic; real provider billing may deviate.")
    if pricing_fallback_msg:
        print(f"warning: {pricing_fallback_msg}")

    print(
        f"Corpus:                {report['corpus']:>6} eligible sources "
        f"({report.get('corpus_sessions', 0)} sessions + "
        f"{report.get('corpus_docs', 0)} docs)"
    )
    print(
        f"Already synthesized:   {report['synthesized']:>6} of "
        f"{report['corpus']} eligible sources"
    )
    print_source_pages_current_state(
        pages_on_disk=int(report.get("source_pages_on_disk", 0) or 0),
        sessions=int(report.get("source_pages_sessions", 0) or 0),
        docs=int(report.get("source_pages_docs", 0) or 0),
        stubs=int(report.get("source_page_stubs", 0) or 0),
        other=int(report.get("source_pages_other", 0) or 0),
    )
    print(f"New since last run:    {report['new']:>6}")
    print(
        f"Breakdown: sessions {report.get('new_sessions', 0)} new / "
        f"{report.get('corpus_sessions', 0)} total, docs {report.get('new_docs', 0)} new / "
        f"{report.get('corpus_docs', 0)} total"
    )
    # The eligibility policy is applied identically here and in `synthesize`,
    # so state it — an estimate that silently skipped sessions a real run
    # would also skip is indistinguishable from one that forgot them.
    ex_sub = int(report.get("excluded_subagents", 0) or 0)
    ex_head = int(report.get("excluded_headless", 0) or 0)
    if ex_sub or ex_head:
        parts = []
        if ex_sub:
            parts.append(f"{ex_sub} subagent (include_subagents={report.get('include_subagents')})")
        if ex_head:
            parts.append(f"{ex_head} headless (exclude_headless=true)")
        print(f"Not eligible (synthesize skips these too): {', '.join(parts)}")
    print()
    # Per-page fixed cost, split so an unexpectedly large figure is
    # traceable to either the agent scaffolding or a bloated vocabulary.
    per_page = (
        f"Per page: {report['prefix_tokens']:,} tok fixed "
        f"({report.get('overhead_tokens', 0):,} agent overhead + "
        f"{report.get('template_tokens', 0):,} prompt) "
        f"+ body, ~{report.get('output_tokens_per_call', 0):,} out"
    )
    if not report.get("lean", True):
        per_page += "  [claude_lean=off]"
    print(per_page)
    if execution_model:
        print(f"Execution model: {execution_model}  Pricing model: {report['model']}")
    else:
        print(f"Pricing model: {report['model']}")
    print()
    if report["new"] == 0:
        print("Incremental sync:  $0.0000  (nothing new — this is a no-op)")
    else:
        print(
            f"Incremental sync:  ${report['incremental_usd']:.4f}  "
            f"(synthesize the {report['new']} new source(s): "
            f"{report.get('new_sessions', 0)} session(s), "
            f"{report.get('new_docs', 0)} doc source(s))"
        )
    print(
        f"Full re-synth:     ${report['full_force_usd']:.4f}  "
        f"(--force — {report['corpus']} source(s), one call each)"
    )

    # #90 / #113: surface the current candidate backlog as pre-run state.
    # Sources are only half the work; a vault can be fully synthesized and
    # still have an empty trusted layer. Candidates here are not a forecast.
    backlog = summarize_backlog(
        vault_root / "wiki", min_refs=getattr(args, "min_refs", DEFAULT_MIN_REFS)
    )
    print_candidates_pre_run(backlog)
    return 0


def cmd_candidates(args: argparse.Namespace) -> int:
    """List / promote / merge / discard candidate pages (v1.1.0 · #51)."""


    wiki_dir = args.wiki_dir or (_content_root(args) / "wiki")
    if not wiki_dir.is_dir():
        print(f"error: wiki directory not found: {wiki_dir}", file=sys.stderr)
        return 2

    action = args.action

    if action == "list":
        items = (
            stale_candidates(wiki_dir, threshold_days=args.stale_days)
            if args.stale else list_candidates(wiki_dir)
        )
        if args.json:
            # Path isn't JSON-serializable — drop it for the output
            cleaned = [{k: v for k, v in c.items() if k != "abs_path"} for c in items]
            print(_json.dumps(cleaned, indent=2))
        else:
            label = "stale" if args.stale else "pending"
            print(f"  {len(items)} {label} candidate(s):")
            for c in items:
                age = f"{c['age_days']}d" if c["created"] else "unknown age"
                print(f"    [{c['kind']:9}] {c['slug']}  ({age})  — {c['title']}")
        return 0

    if action == "apply":
        raw = getattr(args, "actions", None)
        if not raw:
            print(
                "error: --actions JSON array is required for apply "
                '(e.g. \'[{"action":"promote","slug":"Foo","kind":"entities"}]\')',
                file=sys.stderr,
            )
            return 2
        if raw.strip() == "-":
            raw = sys.stdin.read()
        try:
            parsed = _json.loads(raw)
        except json.JSONDecodeError as exc:
            print(f"error: --actions is not valid JSON: {exc}", file=sys.stderr)
            return 2
        if not isinstance(parsed, list) or not parsed:
            print(
                "error: --actions must be a non-empty JSON array",
                file=sys.stderr,
            )
            return 2
        backend = resolve_backend(_load_sessions_config())
        try:
            results = apply_candidate_actions(
                wiki_dir, parsed, synthesizer=backend,
            )
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        any_ok = False
        for r in results:
            slug = r.get("slug") or "?"
            act = r.get("action") or "?"
            if r.get("ok"):
                any_ok = True
                rel = r.get("path") or ""
                print(f"  ok  {act} {slug}" + (f" → {rel}" if rel else ""))
            else:
                print(
                    f"  fail {act} {slug}: {r.get('error') or 'unknown error'}",
                    file=sys.stderr,
                )
        if any_ok:
            _refresh_review_counts(wiki_dir)
            if not getattr(args, "no_rebuild", False):
                build_rc = _rebuild_vault_site(wiki_dir)
                if build_rc:
                    return build_rc
        return 0 if all(r.get("ok") for r in results) else 2

    if action == "promote":
        if not args.slug:
            print("error: --slug is required for promote", file=sys.stderr)
            return 2
        try:
            path = promote(
                args.slug, wiki_dir, kind=args.kind,
                synthesizer=resolve_backend(_load_sessions_config()),
            )
        except KeyFactsBackendError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        print(f"  promoted → {path.relative_to(wiki_dir)}")
        _refresh_review_counts(wiki_dir)
        return 0

    if action == "flip-promote":
        if not args.slug:
            print("error: --slug is required for flip-promote", file=sys.stderr)
            return 2
        try:
            path = flip_and_promote(
                args.slug, wiki_dir, kind=args.kind,
                synthesizer=resolve_backend(_load_sessions_config()),
            )
        except (ValueError, KeyFactsBackendError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        print(f"  flip-promoted → {path.relative_to(wiki_dir)}")
        _refresh_review_counts(wiki_dir)
        return 0

    if action == "rewrite-key-facts":
        backend = resolve_backend(_load_sessions_config())
        slugs: list[str]
        if getattr(args, "all", False):
            kinds = [args.kind] if args.kind else ["entities", "concepts"]
            slugs = []
            for sub in kinds:
                root = wiki_dir / sub
                if not root.is_dir():
                    continue
                for path in sorted(root.glob("*.md")):
                    if path.name != "_context.md":
                        slugs.append(path.stem)
        elif args.slug:
            slugs = [args.slug]
        else:
            print(
                "error: --slug or --all is required for rewrite-key-facts",
                file=sys.stderr,
            )
            return 2
        ok = 0
        for slug in slugs:
            try:
                path = rewrite_key_facts(
                    slug, wiki_dir, kind=args.kind, synthesizer=backend,
                )
            except (FileNotFoundError, KeyFactsBackendError) as exc:
                print(f"error: {exc}", file=sys.stderr)
                continue
            print(f"  rewrote Key Facts → {path.relative_to(wiki_dir)}")
            ok += 1
        return 0 if ok == len(slugs) else 2

    if action == "merge":
        if not args.slug or not args.into:
            print("error: both --slug and --into are required for merge", file=sys.stderr)
            return 2
        try:
            path = merge_candidate(
                args.slug, wiki_dir, into_slug=args.into, kind=args.kind
            )
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        print(f"  merged into → {path.relative_to(wiki_dir)}")
        _refresh_review_counts(wiki_dir)
        return 0

    if action == "discard":
        if not args.slug:
            print("error: --slug is required for discard", file=sys.stderr)
            return 2
        path = discard(args.slug, wiki_dir, reason=args.reason, kind=args.kind)
        print(f"  discarded → {path.relative_to(wiki_dir)}")
        _refresh_review_counts(wiki_dir)
        return 0

    print(f"error: unknown action {action!r}", file=sys.stderr)
    return 2


def _rebuild_vault_site(wiki_dir: Path) -> int:
    """Regenerate ``site/`` beside the wiki so a static candidates page matches disk.

    ``candidates apply`` mutates ``wiki/`` only. After the server was removed
    (#109) the open ``candidates.html`` no longer reloads itself, so a rebuild
    is the step that drops promoted/merged/discarded rows from the page.
    """
    vault = wiki_dir.parent
    raw_dir = vault / "raw"
    print("  rebuilding site so candidates.html matches the wiki")
    with pipeline_lock(vault):
        return build_site(
            out_dir=vault / "site",
            raw_sessions=raw_dir / "sessions",
            raw_dir=raw_dir,
            wiki_dir=wiki_dir,
        )


def _refresh_review_counts(wiki_dir: Path) -> None:
    """Keep ``synth.pipeline`` To-review counts accurate after queue mutations (#84)."""
    state_file = wiki_dir.parent / "llmwiki-state.json"
    if not state_file.is_file():
        return

    def _mut(s: dict[str, Any]) -> dict[str, Any]:
        synth = s.setdefault("synth", {})
        pipeline = synth.get("pipeline")
        if not isinstance(pipeline, dict):
            pipeline = {"stages": ["raw", "synthesized"], "rows": []}
        synth["pipeline"] = apply_review_summary_to_pipeline(pipeline, wiki_dir)
        return s

    update_state(_mut, state_file)


def _min_refs(value: str) -> int:
    """Parse ``--min-refs``: a threshold below 1 is not a weaker threshold.

    The suppression gate is ``0 < n_refs < min_refs``, so ``0`` and negatives
    behave exactly like ``1`` while the help text ("use 1 to report every
    unresolved link") implies they would report less. The same value reaches
    the candidate harvest on the ``all`` path, where "named by fewer than one
    source page" is not a threshold at all. Shared by every parser that
    accepts the flag so the three cannot drift.
    """
    try:
        n = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"--min-refs must be an integer, got {value!r}"
        ) from None
    if n < 1:
        raise argparse.ArgumentTypeError("--min-refs must be at least 1")
    return n


def _add_vault_arg(parser: argparse.ArgumentParser, *, role: str) -> None:
    """#arch-m8 (#620): single source of truth for the ``--vault`` flag.

    All three subcommands that accept ``--vault`` (sync, build, synthesize)
    used to declare it independently with subtly different help text and
    behaviour. The semantics differ legitimately by subcommand (sync
    WRITES into the vault; build READS from it; synthesize isolates the
    state file under it), so we keep the role-specific help string per
    site, but the flag spelling, type, default, and metavar are unified
    here so a future refactor changes them in one place.
    """
    parser.add_argument(
        "--vault", type=Path, default=None, metavar="PATH",
        help={
            "sync": "Write new pages inside an existing Obsidian / Logseq "
                    "vault instead of the repo's wiki/ directory.",
            "build": "Build from an existing Obsidian / Logseq vault. Still "
                     "writes site output to --out.",
            "synthesize": "Read raw/ + write wiki/sources/ under the vault "
                          "root, and isolate the synth state file to the "
                          "vault. Without this flag the state file lives at "
                          "the repo root, so two vaults synthesised against "
                          "the same repo silently share idempotency state.",
            "all": "Operate on this vault: sync → synth → build → graph → "
                   "lint (AI exports are part of build).",
            "add": "Write the converted document under the vault's "
                   "raw/docs/ and run synth/build against the vault.",
            "remove": "Cascade-remove raw docs + their derived pages from "
                      "this vault's raw/docs/ + wiki/, instead of the "
                      "repo's own directories.",
            "init": "Scaffold raw/, wiki/, site/ into this vault instead of "
                    "the repo, so personal data lands outside the git clone.",
            "graph": "Graph this vault's wiki/ and write graph/ under it, "
                     "instead of the repo's. Vault mode uses the builtin "
                     "engine (graphify is repo-anchored).",
            "candidates": "Triage candidate pages under this vault's wiki/, "
                          "instead of the repo's.",
            "trace": "Trace provenance under this vault's wiki/ → sources → "
                     "raw/, instead of the repo's.",
            "watch": "Watch agent session stores and maintain this vault "
                     "(sync → synth → build) when sessions finish.",
            "install-automation": "Write automation status and schedulers "
                                  "for this vault.",
        }[role],
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="llmwiki",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent("""\
            LLM-powered knowledge base from agent sessions.

            Start here
              init                 Scaffold raw/, wiki/, and site/ directories
              configure-sources    Enable detected session sources in config
              install-agent-kit    Copy slash commands and skills into an agent directory

            Daily loop (this order)
              sync                 Convert new agent sessions to raw markdown
              add                  Ingest a URL, file, or folder as a document
              synth                Summarise raw sources and harvest candidate pages
              candidates           Review harvested stubs: promote, merge, or discard
              build                Compile the static HTML site

            Run the loop for me
              all                  Run the full pipeline in one invocation
              watch                Re-run the loop when agent sessions finish
              install-automation   Install OS schedulers and optional hooks

            Look around
              lint                 Check the wiki without changing pages
              query                Ask a natural-language question of the wiki
              trace                Show how a wiki page traces back to raw sources
              graph                Walk [[wikilinks]] into a browsable connection map
              adapters             List which agents can feed sessions into this vault
              usage                Report local MCP tool calls next to synthesis cost
              version              Print which llmwiki release is installed

            Take things out
              remove               Delete raw documents and everything derived from them

            Rare — one-time
              migrate              List or apply a named one-time vault repair
              queue                Inspect or run the deferred-work task list
        """),
        epilog=textwrap.dedent("""\
            Canonical loop: ingest (sync / add) → summarise (synth) → review candidates → publish (build).
            After synth, rebuild the site so candidates and analytics stay current.
        """),
    )
    p.add_argument("--version", action="version", version=f"llmwiki {__version__}")

    sub = p.add_subparsers(dest="cmd", metavar="COMMAND")

    def add_command(name: str, description: str) -> argparse.ArgumentParser:
        return sub.add_parser(
            name,
            formatter_class=argparse.RawDescriptionHelpFormatter,
            description=textwrap.dedent(description).strip(),
        )

    # init
    init = add_command(
        "init",
        """
        Scaffold an empty llmwiki vault: the three layers (raw/, wiki/, site/) plus the seed wiki pages every later command assumes exist.

        First command for a fresh setup. Run this once before configure-sources / install-agent-kit, then sync to pull sessions, then synth to write summaries.

        Creates raw/sessions/, wiki/sources/, wiki/entities/, wiki/concepts/, wiki/projects/, wiki/syntheses/, and site/. Seeds wiki/index.md, overview.md, log.md, hints.md, hot.md, MEMORY.md, SOUL.md, CRITICAL_FACTS.md, and dashboard.md when they are missing.
        """,
    )
    _add_vault_arg(init, role="init")
    init.set_defaults(func=cmd_init)

    # sync
    sync = add_command(
        "sync",
        """
        Ingest new agent sessions into the vault as immutable markdown under raw/sessions/. This is the start of the daily loop: convert first, then summarise with synth, optionally review candidates, and publish with build.

        Enabled session-store adapters read each agent's transcript store, convert settled sessions into flat raw/sessions/*.md files, update sync state, and refresh which paths are pending for synth. After a successful convert, sync may also rebuild the site and/or run lint if your sessions config asks for that after sync. Pass --status to report last-sync time, per-adapter counters, and quarantine without converting anything.

        Does not write wiki/sources/ summaries or propose candidate pages — that is synth. Live sessions are skipped unless you pass --include-current.
        """,
    )
    sync.add_argument(
        "--adapter",
        nargs="*",
        default=None,
        help="Session-store adapter name(s) to run (an adapter reads one agent's session files). "
             "List names with `llmwiki adapters`. Default: all available",
    )
    sync.add_argument("--since", type=str, help="Only sessions on or after YYYY-MM-DD")
    sync.add_argument("--project", type=str, help="Substring filter on project slug")
    sync.add_argument("--include-current", action="store_true", help="Don't skip live sessions (<60 min)")
    sync.add_argument("--force", action="store_true", help="Ignore state file, reconvert everything")
    sync.add_argument(
        "--force-resync", action="store_true",
        help="Override the newer-schema/corrupt-state guard and reconvert "
             "from scratch. Implies --force; may duplicate an "
             "already-populated raw/.",
    )
    sync.add_argument(
        "--fail-on-errors", action="store_true",
        help="Exit 1 if any file fails to convert (default: per-file "
             "errors are quarantined and the run exits 0)",
    )
    sync.add_argument(
        "--auto-build", action=argparse.BooleanOptionalAction, default=True,
        help="After sync, also rebuild the site if your sessions config asks for a rebuild after sync "
             "(default: on; pass --no-auto-build to skip)",
    )
    sync.add_argument(
        "--auto-lint", action=argparse.BooleanOptionalAction, default=True,
        help="After sync, also run lint if your sessions config asks for lint after sync "
             "(default: on; pass --no-auto-lint to skip)",
    )
    _add_vault_arg(sync, role="sync")
    sync.add_argument(
        "--allow-overwrite", action="store_true",
        help="With --vault: allow clobbering existing vault pages "
             "(default: refuse, append under ## Connections instead)",
    )
    sync.add_argument(
        "--status", action="store_true",
        help="Show last-sync time, counters per session-store adapter, and "
             "quarantine. Does not run a sync.",
    )
    sync.add_argument(
        "--recent", type=int, default=0,
        help="With --status: also show last N recent log entries.",
    )
    sync.set_defaults(func=cmd_sync)

    # build
    build = add_command(
        "build",
        """
        Publish the vault: compile raw/ and wiki/ into a static HTML site under site/ (or --out), including AI-facing exports such as llms.txt. This is the last step of the daily loop after ingest and synth (and after candidate review when you chose to do one).

        Walks markdown pages, resolves wikilinks and navigation, and writes browsable HTML plus export artifacts. By default it is read-only on wiki/ content; the only exception is --seed-project-stubs, which may create missing wiki/projects/<slug>.md stubs.

        Run sync (and synth) first when those layers should catch up; run candidates when you need the Candidates page to match reviewed stubs.
        """,
    )
    build.add_argument("--out", type=Path, default=REPO_ROOT / "site", help="Output dir (default: site/)")
    build.add_argument("--synthesize", action="store_true", help="Call claude CLI for overview synthesis")
    build.add_argument(
        "--claude", type=str, default="",
        help="Path to claude CLI (defaults to `shutil.which('claude')` "
             "so PATH-based / brew / nvm / Windows installs all work)",
    )
    build.add_argument(
        "--search-mode", choices=["auto", "tree", "flat"], default="auto",
        help="Search index mode: auto picks tree vs flat from heading depth",
    )
    build.add_argument(
        "--local-root", type=str, default="", dest="local_root", metavar="PATH",
        help="Value shown in place of a session's stored home "
             "directory, e.g. /home/user. Defaults to this machine's home "
             "directory so local paths stay usable; pass a fixed string when "
             "publishing so the same vault renders identically anywhere.",
    )
    _add_vault_arg(build, role="build")
    build.add_argument(
        "--seed-project-stubs", action="store_true", dest="seed_project_stubs",
        help="Auto-create wiki/projects/<slug>.md stubs for any "
             "newly-discovered project that doesn't have a metadata file. "
             "Off by default — `build` is read-only on wiki/. Use `sync` "
             "(which already mutates wiki/) for routine seeding, or pass "
             "this flag to opt in from CI/scripts.",
    )
    build.set_defaults(func=cmd_build)

    # usage (#26) — local MCP tool-usage telemetry
    usage_p = add_command(
        "usage",
        """
        Look around: report local MCP tool-usage telemetry (calls, zero-hit rate, bytes served) next to estimated synthesis cost for this vault.

        Reads stored usage logs and optional synthesis-cost state, then prints a human table or JSON. --compact can fold older raw log months into a kept-forever rollup before reporting.

        Not part of the daily loop. Does not sync sessions, run synth, rebuild the site, or change wiki pages (aside from optional log compaction under --compact).
        """,
    )
    usage_p.add_argument("--vault", type=Path, default=None,
                         help="Read telemetry from this vault instead of the repo root")
    usage_p.add_argument("--state-file", type=Path, default=None,
                         help="State file to read synthesis-cost estimate from")
    usage_p.add_argument("--json", action="store_true",
                         help="Emit the aggregated totals as JSON")
    usage_p.add_argument("--compact", action="store_true",
                         help="Fold past-month raw logs into the kept-forever "
                              "rollup and delete them before reporting")
    usage_p.set_defaults(func=cmd_usage)

    # adapters
    ads = add_command(
        "adapters",
        """
        Look around: list which session-store adapters this install knows about. An adapter is a connector that reads one agent's session files (for example Claude Code or Codex CLI) so sync can turn them into raw markdown.

        Prints each adapter's name, availability, and a short description (use --wide for the full text). Useful before configure-sources or when diagnosing why sync skipped a source.

        Not part of the daily loop. Does not enable adapters in config, convert sessions, or write wiki pages — use configure-sources then sync for that.
        """,
    )
    ads.add_argument(
        "--wide",
        action="store_true",
        help="Show untruncated adapter descriptions (an adapter is a connector to one agent's session store).",
    )
    ads.set_defaults(func=cmd_adapters)

    cfg_src = add_command(
        "configure-sources",
        """
        Start-here setup: interactively enable detected session sources and write adapters.* entries into config.json. An adapter is a connector that reads one agent's session files so later sync runs know what to convert.

        Do this once after init (or whenever you add a new agent). Probes the machine for known stores, asks which to enable, and persists the choice. --yes skips the interview and makes no config writes.

        Does not convert sessions into raw/, summarise into wiki/, or rebuild the site. Run sync afterwards to ingest, then continue the daily loop with synth and build.
        """,
    )
    cfg_src.add_argument(
        "--yes",
        action="store_true",
        help="Non-interactive: skip interview (no config writes)",
    )
    cfg_src.set_defaults(func=cmd_configure_sources)

    # graph
    graph = add_command(
        "graph",
        """
        Look around / optional publish step: turn [[wikilink]] connections among wiki pages into a browsable knowledge graph. Often run after build (and included in all) when you want a map of how pages relate.

        Walks wikilinks across the wiki and writes graph/graph.json plus graph.html (or only one format via --format). The default engine is graphify; --engine builtin falls back to a stdlib wikilink walk.

        Does not summarise raw sessions into wiki/sources/, harvest candidates, or rebuild the rest of the static site. It only refreshes the graph artifacts.
        """,
    )
    graph.add_argument("--format", choices=["json", "html", "both"], default="both")
    graph.add_argument(
        "--engine", choices=["builtin", "graphify"], default="graphify",
        help="Graph engine: 'graphify' (AI-powered, default) or 'builtin' (stdlib wikilinks fallback)",
    )
    _add_vault_arg(graph, role="graph")
    graph.set_defaults(func=cmd_graph)

    # lint (v1.0, #155) — live count via the rule registry (currently 15)
    lint = add_command(
        "lint",
        f"""
        Look around: run the lint rule registry against the wiki and print findings (orphans, broken links, index drift, and similar). There are currently {len(_LINT_REG)} registered rules; --rules can narrow the set.

        Evaluates each selected rule over wiki/ (and related vault paths as the rule requires), then reports issues at their severity. Use --fail-on-errors / --fail-on-warnings when a script or CI gate should exit non-zero. Often run after a review pass (for example after candidates) or as the last stage of all.

        Report only — does not edit wiki pages, convert sessions, summarise sources, or rebuild the site.
        """,
    )
    lint.add_argument("--wiki-dir", type=Path, default=None,
                      help="Wiki directory (default: ./wiki)")
    lint.add_argument("--rules", type=str, default=None,
                      help="Comma-separated rule names (default: all applicable)")
    lint.add_argument("--json", action="store_true", help="JSON output")
    lint.add_argument(
        "--min-refs", type=_min_refs, default=DEFAULT_MIN_REFS, metavar="N",
        help=(
            "How many distinct source pages must name a [[wikilink]] target "
            "before an unresolved link to it is reported as broken. Matches "
            "the candidate harvest's threshold, so a target the harvest "
            "deliberately declined is not a finding "
            f"(default: {DEFAULT_MIN_REFS}; use 1 to report every "
            "unresolved link)"
        ),
    )
    lint.add_argument("--fail-on-errors", action="store_true",
                      help="Exit non-zero if any error-severity issues found")
    lint.add_argument("--fail-on-warnings", action="store_true",
                      help="Exit non-zero if any warning-severity issues found. "
                           "Stricter than --fail-on-errors; combine the two to "
                           "gate on both. Rules a vault switched off in "
                           "llmwiki.json cannot stop the gate — they never ran")
    _add_vault_arg(lint, role="synthesize")
    lint.set_defaults(func=cmd_lint)

    queue_p = add_command(
        "queue",
        """
        Rare. Internal deferred-work task list used when something else postponed a step (add a document, sync sessions, summarise, rebuild) instead of running it immediately.

        Most people never need this command if they run sync, synth, build, or all themselves. Subcommands status / run / enqueue inspect or process queued tasks with optional --limit and --task-type filters.

        Not part of the daily loop. Prefer the ordinary commands for routine work; use queue only when diagnosing or draining deferred tasks left behind by another path.
        """,
    )
    queue_p.add_argument("queue_action", nargs="?", default="status", choices=["status", "run", "enqueue"])
    queue_p.add_argument("--limit", type=int, default=20, help="Max tasks to process in one run")
    queue_p.add_argument("--task-type", default="add_doc", choices=["add_doc", "session_sync", "synthesize", "build"])
    queue_p.add_argument("--source", default="", help="Source value for add_doc enqueue")
    queue_p.add_argument("--state-file", type=Path, default=None, help="Override state file path")
    _add_vault_arg(queue_p, role="synthesize")
    queue_p.set_defaults(func=cmd_queue)

    migrate = add_command(
        "migrate",
        """
        Rare. One-time vault repairs after an upgrade — fix or rewrite existing vault data that an older release left behind.

        List available migrations with `llmwiki migrate` or `llmwiki migrate --list`. Nothing is applied until you choose a name: `llmwiki migrate <name> [flags]`. There is no run-everything default. Use `--dry-run` on a named migration to preview writes before applying.

        Does not run sync, synth, build, or any other command that adds new sessions or documents. Listing alone never mutates the vault; only an explicit named migration (without --list) performs a repair.
        """,
    )
    migrate.add_argument(
        "--list",
        dest="list_migrations",
        action="store_true",
        help="Print the migration catalog and exit (do not apply)",
    )
    migrate.set_defaults(func=cmd_migrate)
    mig = migrate.add_subparsers(dest="migration", metavar="NAME", required=False)

    def add_migration(
        name: str, purpose: str, when: str, *, short: str,
    ) -> argparse.ArgumentParser:
        """Register a nested migrate name; catalog uses purpose/when, list uses short."""
        return mig.add_parser(
            name,
            formatter_class=argparse.RawDescriptionHelpFormatter,
            help=short,
            description=textwrap.dedent(f"""\
                {purpose}

                When to run: {when}

                Does not ingest new sessions or documents. Prefer --dry-run first when the migration can rewrite files.
            """).strip(),
        )

    _mig_by_name = {name: (purpose, when) for name, purpose, when in _MIGRATIONS}

    migrate_state = add_migration(
        "state", *_mig_by_name["state"],
        short="Merge legacy state files into unified llmwiki-state.json",
    )
    migrate_state.add_argument("--state-file", type=Path, default=None, help="Target unified state file")
    migrate_state.set_defaults(func=cmd_migrate_state)

    migrate_raw = add_migration(
        "raw-redaction", *_mig_by_name["raw-redaction"],
        short="Redact encoded usernames already present in raw/sessions",
    )
    migrate_raw.add_argument(
        "--vault",
        type=Path,
        required=True,
        help="Vault root containing raw/sessions/",
    )
    migrate_raw.add_argument(
        "--dry-run",
        action="store_true",
        help="Report would-change files; write nothing",
    )
    migrate_raw.add_argument(
        "--real-username",
        default=None,
        help="Override redaction.real_username",
    )
    migrate_raw.add_argument(
        "--replacement-username",
        default=None,
        help="Override replacement placeholder (default USER)",
    )
    migrate_raw.set_defaults(func=cmd_migrate_raw_redaction)

    migrate_tools = add_migration(
        "tools-used", *_mig_by_name["tools-used"],
        short="Expand CallMcpTool stubs in raw frontmatter from origin stores",
    )
    migrate_tools.add_argument(
        "--vault",
        type=Path,
        required=True,
        help="Vault root containing raw/sessions/",
    )
    migrate_tools.add_argument(
        "--dry-run",
        action="store_true",
        help="Report would-change files; write nothing",
    )
    migrate_tools.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Optional sessions_config.json override",
    )
    migrate_tools.set_defaults(func=cmd_migrate_tools_used)

    migrate_kinds = add_migration(
        "page-kinds", *_mig_by_name["page-kinds"],
        short="Retype removed question/comparison pages into concepts/",
    )
    migrate_kinds.add_argument(
        "--vault",
        type=Path,
        required=True,
        help="Vault root containing wiki/",
    )
    migrate_kinds.add_argument(
        "--dry-run",
        action="store_true",
        help="Report would-change files; write nothing",
    )
    migrate_kinds.set_defaults(func=cmd_migrate_page_kinds)

    migrate_topic = add_migration(
        "topic-kinds", *_mig_by_name["topic-kinds"],
        short="Stamp (entity|concept) onto older source Connections bullets",
    )
    migrate_topic.add_argument(
        "--vault",
        type=Path,
        required=True,
        help="Vault root containing wiki/",
    )
    migrate_topic.add_argument(
        "--dry-run",
        action="store_true",
        help="Report would-change files; write nothing",
    )
    migrate_topic.set_defaults(func=cmd_migrate_topic_kinds)

    migrate_prov = add_migration(
        "broken-provenance", *_mig_by_name["broken-provenance"],
        short="Fix wiki source_file links that point at missing raw sessions",
    )
    migrate_prov.add_argument(
        "--vault",
        type=Path,
        required=True,
        help="Vault root containing wiki/ and raw/",
    )
    migrate_prov.add_argument(
        "--dry-run",
        action="store_true",
        help="Report would-change files; write nothing",
    )
    migrate_prov.set_defaults(func=cmd_migrate_broken_provenance)

    kit = add_command(
        "install-agent-kit",
        """
        Start-here setup: copy packaged slash commands and skills into an agent directory (--dest, for example .claude or .codex) so the agent can run /wiki-sync and related workflows against this vault.

        Do this after init when you want agent-facing commands on disk. Writes command and skill files under the destination; --dry-run reports would-write paths without changing anything.

        Not part of the daily loop. Does not convert sessions, summarise into wiki/, harvest candidates, or rebuild the site.
        """,
    )
    kit.add_argument(
        "--dest",
        type=Path,
        required=True,
        help="Directory to receive commands/ and skills/ (e.g. .claude)",
    )
    kit.add_argument(
        "--dry-run",
        action="store_true",
        help="Report would-write files; write nothing",
    )
    kit.set_defaults(func=cmd_install_agent_kit)

    # candidates (v1.1, #51) — approval workflow
    cand = add_command(
        "candidates",
        """
        Daily-loop review gate: promote, flip-promote, merge, discard, list, or batch-apply stubs under wiki/candidates/ after harvest. Runs after synth; rebuilding the site after review keeps the Candidates page in sync, unless you pass --no-rebuild on batch apply.

        Actions operate on pending candidate markdown: promote moves a stub into entities/ or concepts/, merge folds one slug into another, discard archives noise, and apply runs a JSON action list (the shape site/candidates.html prints). Successful apply rebuilds site/ by default so candidates.html matches the wiki.

        Does not harvest new stubs from sources — that is synth. Does not convert sessions or summarise raw/ into wiki/sources/.
        """,
    )
    cand.add_argument(
        "action",
        choices=[
            "list", "promote", "flip-promote", "merge", "discard", "apply",
            "rewrite-key-facts",
        ],
        help="What to do with candidates / trusted Key Facts",
    )
    cand.add_argument("--slug", type=str, default=None,
                      help="Page slug (required for promote/flip-promote/merge/discard; "
                           "or with rewrite-key-facts)")
    cand.add_argument("--all", action="store_true",
                      help="For rewrite-key-facts: every entity/concept page")
    cand.add_argument("--into", type=str, default=None,
                      help="For merge: slug of the page to merge into")
    cand.add_argument("--reason", type=str, default="",
                      help="For discard: why the candidate is being rejected")
    cand.add_argument("--kind", type=str, default=None,
                      choices=["entities", "concepts", "sources", "syntheses"],
                      help="Subtree (auto-detected if omitted)")
    cand.add_argument("--wiki-dir", type=Path, default=None,
                      help="Wiki directory (default: ./wiki)")
    cand.add_argument("--stale", action="store_true",
                      help="For list: only show stale candidates")
    cand.add_argument("--stale-days", type=int, default=30,
                      help="Staleness threshold in days (default 30)")
    cand.add_argument("--json", action="store_true", help="JSON output for list")
    cand.add_argument(
        "--actions", type=str, default=None, metavar="JSON",
        help="For apply: JSON array of {action,slug,kind?,into?,reason?} "
             "(the shape site/candidates.html prints); pass - to read stdin",
    )
    cand.add_argument(
        "--no-rebuild",
        action="store_true",
        help="For apply: skip rebuilding site/ after a successful batch "
             "(default: rebuild so candidates.html matches the wiki)",
    )
    _add_vault_arg(cand, role="candidates")
    cand.set_defaults(func=cmd_candidates)

    # synth (#90)
    def _add_synth_arguments(parser: argparse.ArgumentParser) -> None:
        """Flags for ``llmwiki synth``."""
        syn_mode = parser.add_mutually_exclusive_group()
        syn_mode.add_argument(
            "--check", action="store_true",
            help="Probe backend availability and exit (exit 0 if reachable)",
        )
        syn_mode.add_argument(
            "--estimate", action="store_true",
            help=(
                "Print cached-vs-fresh token + dollar estimate without calling "
                "a backend; Candidates shown as pre-run state"
            ),
        )
        syn_mode.add_argument(
            "--candidates-only", action="store_true",
            help=(
                "Harvest entity/concept candidates from wiki/sources/ into "
                "wiki/candidates/ without synthesizing sources"
            ),
        )
        syn_mode.add_argument(
            "--sources-only", action="store_true",
            help=(
                "Synthesize wiki/sources/ only — skip candidate harvest "
                "(legacy synthesize behaviour)"
            ),
        )
        parser.add_argument(
            "--min-refs", type=_min_refs, default=DEFAULT_MIN_REFS, metavar="N",
            help=(
                "Candidate threshold: a wikilink target becomes a candidate when "
                f"N or more distinct source pages name it (default: {DEFAULT_MIN_REFS})"
            ),
        )
        parser.add_argument(
            "--force", action="store_true",
            help="Ignore state file, re-synthesize all sessions",
        )
        parser.add_argument(
            "--concurrency", type=int, default=None, metavar="N",
            help=(
                "Synthesize N source pages at once, overriding "
                "synthesis.concurrency in config (default: "
                f"{DEFAULT_SYNTH_CONCURRENCY}; range 1-{MAX_SYNTH_CONCURRENCY}; "
                "1 runs strictly sequentially)"
            ),
        )
        parser.add_argument(
            "--path",
            action="append",
            dest="paths",
            metavar="PATH",
            help=(
                "Synthesize only this raw session/doc under raw/sessions/ or "
                "raw/docs/ (repeatable; relative to vault root)"
            ),
        )
        syn_corpus = parser.add_mutually_exclusive_group()
        syn_corpus.add_argument(
            "--sessions-only",
            action="store_true",
            help="Synthesize only raw/sessions/ (skip raw/docs/)",
        )
        syn_corpus.add_argument(
            "--docs-only",
            action="store_true",
            help="Synthesize only raw/docs/ (skip raw/sessions/)",
        )
        _add_vault_arg(parser, role="synthesize")

    syn = add_command(
        "synth",
        """
        Summarise pending raw sessions and documents into wiki/sources/, then propose repeated topics as stubs under wiki/candidates/ for later review. In the daily loop this follows ingest (sync / add) and prepares the material you browse, query, and optionally promote before publishing with build.

        Calls the configured LLM (or other synthesis backend) to write or refresh source pages, updates synth state, then walks those sources for repeated [[wikilink]] targets and writes candidate stubs. Flags can limit the run (--sources-only, --candidates-only, --path, --sessions-only / --docs-only) or probe cost (--estimate) / backend reachability (--check).

        Rebuild the site afterwards so candidates and analytics stay current. Promoting stubs into entities/concepts is the candidates command — many runs skip that review and go straight to build.
        """,
    )
    _add_synth_arguments(syn)
    syn.set_defaults(func=cmd_synthesize)

    # add — ingest a document into the wiki (#16)
    add_p = add_command(
        "add",
        """
        Alternative ingest path for documents (not agent transcripts): fetch or copy a URL, file, or folder into raw/docs/, then by default synthesise those paths and rebuild the site so the new material shows up in the wiki and on Home.

        Converts each SOURCE into markdown under raw/docs/ (optionally grouped with --project) and records state, then runs the default follow-on steps unless flags say otherwise.
        """,
    )
    add_p.add_argument("sources", nargs="+", metavar="SOURCE",
                       help="URL (http/https), file, or folder. Repeatable.")
    add_p.add_argument("--title", default=None,
                       help="Override title derivation (single source only)")
    add_p.add_argument("--project", default=None,
                       help="Group under raw/docs/<PROJECT>/ instead of the doc's own slug")
    add_p.add_argument("--tag", action="append", default=None, metavar="TAG",
                       help="Extra frontmatter tag (repeatable)")
    add_p.add_argument("--note", default=None,
                       help="Blockquote note prepended to the document body")
    add_p.add_argument("--no-synthesize", action="store_true",
                       help="Skip the post-add synthesis pass")
    add_p.add_argument("--no-build", action="store_true",
                       help="Skip the post-add site rebuild")
    render_group = add_p.add_mutually_exclusive_group()
    render_group.add_argument("--render", action="store_true",
                              help="Force the headless-browser layer for URLs (needs playwright)")
    render_group.add_argument("--no-render", action="store_true",
                              help="Never use the headless-browser layer")
    add_p.add_argument("--dry-run", action="store_true",
                       help="Convert and report, write nothing, run nothing")
    add_p.add_argument("--force-new", action="store_true",
                       help="Always land a new snapshot even when body matches an existing doc")
    _add_vault_arg(add_p, role="add")
    add_p.set_defaults(func=cmd_add)

    # remove — cascade-delete raw docs + their derived artifacts (B2)
    rm_p = add_command(
        "remove",
        """
        Take things out: cascade-delete raw documents matching a project name or slug glob, and everything derived from them (synth state entries, wiki/sources pages, index/log/backlink housekeeping).

        Destructive and interactive unless --yes. Prefer --dry-run first to print the full cascade without writing. Use this when a document or project should leave the vault entirely, not when you only want to stop syncing new sessions.

        Not part of ingest. Does not convert sessions, summarise remaining sources, or rebuild the site afterward — run build yourself if published HTML should drop the removed material.
        """,
    )
    rm_p.add_argument("selector", metavar="SELECTOR",
                      help="Project name or slug glob, e.g. 'old-project*'")
    rm_p.add_argument("--dry-run", action="store_true",
                      help="Print the full cascade and change nothing")
    rm_p.add_argument("--yes", action="store_true",
                      help="Skip the confirmation prompt (required without a TTY)")
    _add_vault_arg(rm_p, role="remove")
    rm_p.set_defaults(func=cmd_remove)

    # query — natural-language graph query
    qry = add_command(
        "query",
        """
        Look around: ask a natural-language question of the knowledge graph and get an answer grounded in wiki pages.

        Traverses linked pages (BFS depth via --depth, token budget via --budget) and synthesises a read-only reply in the terminal. Substantial answers are not auto-saved; write a wiki/syntheses/ page yourself if you want to keep one.

        Does not convert sessions, run the synth harvest pipeline, edit existing pages, or rebuild the site.
        """,
    )
    qry.add_argument("question", nargs="+", help="The question to ask")
    qry.add_argument("--depth", type=int, default=3, help="BFS traversal depth (default: 3)")
    qry.add_argument("--budget", type=int, default=2000, help="Max output tokens (default: 2000)")
    qry.set_defaults(func=cmd_query)

    # trace — downward provenance (#122)
    trc = add_command(
        "trace",
        """
        Look around: print downward provenance from a wiki page through its source summaries to the underlying raw sessions or docs.

        Resolves PAGE (vault-relative path or page stem), follows source_file / sources metadata, and prints the chain so you can defend a claim against original material.

        Read-only. Does not edit pages, convert sessions, summarise, or rebuild the site.
        """,
    )
    trc.add_argument(
        "page",
        metavar="PAGE",
        help="Vault-relative wiki path (wiki/entities/Foo.md) or page name/stem",
    )
    _add_vault_arg(trc, role="trace")
    trc.set_defaults(func=cmd_trace)

    # version
    ver = add_command(
        "version",
        """
        Look around: print the installed llmwiki package version and exit.

        Useful when filing bugs or checking whether an upgrade landed. Same information as `llmwiki --version` on the root parser.

        Does not touch the vault, config, or any pipeline stage.
        """,
    )
    ver.set_defaults(func=cmd_version)

    # all — [sync?] → [synthesize?] → build → graph → lint
    all_p = add_command(
        "all",
        """
        Run the full pipeline in one locked invocation: sync → synth → build → graph → lint. Use this when you want the daily loop without typing each command yourself (CI, scheduled jobs, or a one-shot refresh).

        Each stage runs in order with the same semantics as the standalone command. AI-consumable exports (llms.txt and similar) are written by the build stage, not a separate step. Skip stages with --no-sync, --no-synth, --skip-graph, or --skip-lint; --fail-fast stops at the first non-zero exit.

        Does not review or promote candidates — that stays a human (or scripted) candidates step between synth and a final build when the Candidates page must match decisions. It is not a substitute for migrate or one-off vault repairs.
        """,
    )
    all_p.add_argument(
        "--out", type=Path, default=REPO_ROOT / "site",
        help="Output dir for build (default: site/, or <vault>/site with --vault)",
    )
    all_p.add_argument(
        "--search-mode", choices=["auto", "tree", "flat"], default="auto",
        help="Search index mode passed through to build (default: auto)",
    )
    all_p.add_argument(
        "--graph-engine", choices=["builtin", "graphify"], default="graphify",
        help="Graph engine passed through to graph (default: graphify)",
    )
    all_p.add_argument(
        "--skip-graph", action="store_true",
        help="Skip the graph step (useful when graphify is not installed)",
    )
    all_p.add_argument(
        "--fail-fast", action="store_true",
        help="Stop at the first non-zero step (default: continue, report worst exit code)",
    )
    all_p.add_argument(
        "--skip-lint", action="store_true",
        help="Skip the lint step",
    )
    all_p.add_argument(
        "--lint-fail", choices=["never", "errors", "warnings"], default="never",
        help="Exit 2 when lint reports issues at this level (default: never — "
             "findings are printed, the run still exits 0)",
    )
    all_p.add_argument(
        "--strict", action="store_true",
        help="Spelling for --lint-fail warnings (exit 2 on any lint error or warning)",
    )
    all_p.add_argument(
        "--no-sync", action="store_false", dest="with_sync", default=True,
        help="Skip the sync step (do not convert new agent sessions first)",
    )
    all_p.add_argument(
        "--no-synth", action="store_false", dest="with_synth", default=True,
        help="Skip the synth step, so the run makes no LLM calls",
    )
    all_p.add_argument(
        "--synth-force", action="store_true",
        help="Pass --force to synth (re-synthesize every session)",
    )
    all_p.add_argument(
        "--min-refs", type=_min_refs, default=DEFAULT_MIN_REFS, metavar="N",
        help=(
            "Candidate threshold passed through to the synth and lint stages: "
            "a wikilink target becomes a candidate — and an unresolved link to "
            "it becomes a finding — when N or more distinct source pages name "
            f"it (default: {DEFAULT_MIN_REFS})"
        ),
    )
    # Accepted so an already-installed scheduled command keeps parsing. They
    # land on their own dests, inert: both stages already run by default, and
    # a --no-* on the same line must stay honoured.
    all_p.add_argument(
        "--with-sync", action="store_true", dest="legacy_with_sync",
        help="Deprecated and inert: sync runs by default; skip it with --no-sync",
    )
    all_p.add_argument(
        "--with-synth", action="store_true", dest="legacy_with_synth",
        help="Deprecated and inert: synth runs by default; skip it with --no-synth",
    )
    _add_vault_arg(all_p, role="all")
    all_p.set_defaults(func=cmd_all)

    watch_p = add_command(
        "watch",
        """
        Hands-off daily loop: poll configured agent session stores and, when a session file has settled, run maintain (sync → synth → build) for the new material.

        Watches adapter roots at --interval, waits --settle after the last mtime change, then invokes the maintain path. --dry-run only detects ready sessions; --no-synthesize / --no-build skip those stages of maintain.

        Does not install a persistent OS scheduler or login hooks — that is install-automation. Stops when you interrupt the process; it is a foreground poller, not a background service unit.
        """,
    )
    watch_p.add_argument("--adapter", nargs="*", default=None,
                         help="Session-store adapter name(s) to watch "
                              "(an adapter reads one agent's session files)")
    watch_p.add_argument("--interval", type=float, default=5.0,
                         help="Poll interval seconds (default 5)")
    watch_p.add_argument("--settle", type=float, default=2.0,
                         help="Mtime settle seconds before ready check (default 2)")
    watch_p.add_argument("--dry-run", action="store_true",
                         help="Detect only; do not run maintain")
    watch_p.add_argument("--no-synthesize", action="store_true",
                         help="Skip synthesize")
    watch_p.add_argument("--no-build", action="store_true",
                         help="Skip build")
    _add_vault_arg(watch_p, role="watch")
    watch_p.set_defaults(func=cmd_watch)

    auto_p = add_command(
        "install-automation",
        """
        Setup for running the loop on a schedule: install OS scheduler units (and optional hooks) and write automation status for the site Home panel. Choose --job ingest (collect + rebuild) or maintain (also summarise — costs provider money).

        Writes unit files, optionally activates them into the platform scheduler (--activate is default; --no-activate only writes and prints enable commands), and records what was installed so Home can show status. Hooks default to skip unless you opt in during the interview.

        Not a one-off ingest. Does not convert sessions or rebuild the site by itself until the scheduled job (or a hook) actually runs. For an immediate full pass use all; for a live foreground poller use watch.
        """,
    )
    auto_p.add_argument("--yes", action="store_true",
                        help="Non-interactive: use flags / defaults (no hooks)")
    auto_p.add_argument("--job", choices=["ingest", "maintain"], default=None,
                        help="What the daily job does: 'ingest' collects sessions and rebuilds the "
                             "site; 'maintain' also summarises them, which costs AI-provider money "
                             "(default: ingest)")
    auto_p.add_argument("--graph", choices=["none", "builtin", "graphify"], default="none",
                        help="Build the knowledge graph, and with which builder (default: none)")
    auto_p.add_argument("--lint-fail", choices=["never", "errors", "warnings"], default="never",
                        help="Report the scheduled job as failed on quality findings at this level "
                             "(default: never)")
    auto_p.add_argument("--schedule", default=None,
                        help='Cron expression for when the job runs, e.g. "0 8 * * 1-5" '
                             '(default: "0 8 * * *")')
    auto_p.add_argument("--profile", choices=["A", "B", "C"], default=None,
                        help="Deprecated: use --job. A=ingest, B/C=maintain")
    auto_p.add_argument("--hour", type=int, default=None,
                        help="Deprecated: use --schedule")
    auto_p.add_argument("--minute", type=int, default=None,
                        help="Deprecated: use --schedule")
    auto_p.add_argument("--synth-backend", default=None)
    auto_p.add_argument("--units-dir", type=Path, default=None)
    auto_p.add_argument("--watch-enabled", action="store_true")
    auto_p.add_argument("--force-platform", choices=["linux", "macos", "windows"],
                        default=None)
    activate_group = auto_p.add_mutually_exclusive_group()
    activate_group.add_argument(
        "--activate",
        dest="activate",
        action="store_true",
        help="Copy units into the OS scheduler location and enable the job (default)",
    )
    activate_group.add_argument(
        "--no-activate",
        dest="activate",
        action="store_false",
        help="Write unit files only; print manual enable commands",
    )
    auto_p.set_defaults(activate=True)
    _add_vault_arg(auto_p, role="install-automation")
    auto_p.set_defaults(func=cmd_install_automation)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 0
    # Nested migrate parsers overwrite func; catch --list vs name before apply.
    if getattr(args, "cmd", None) == "migrate" and (
        bool(getattr(args, "list_migrations", False))
        or getattr(args, "migration", None) is None
    ):
        return cmd_migrate(args)
    return args.func(args)


def main_add(argv: list[str] | None = None) -> int:
    """Console entry for `llm-wiki-add` — `llmwiki add` with less typing."""
    return main(["add", *(_sys.argv[1:] if argv is None else argv)])


if __name__ == "__main__":
    sys.exit(main())
