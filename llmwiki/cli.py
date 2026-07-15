"""llmwiki CLI.

Usage:
    python3 -m llmwiki <subcommand> [options]

Subcommands:
    init              Scaffold raw/, wiki/, site/ directories
    sync              Convert new .jsonl sessions to markdown
    add               Add documents: URL, file, or folder → raw/docs/ + synthesize + build
    build             Compile static HTML site from raw/ + wiki/
    serve             Start local HTTP server
    adapters          List available session-store adapters
    graph             Build the knowledge graph (graph/graph.json + graph.html)
    export            Export AI-consumable formats: llms-txt, llms-full-txt, jsonld, sitemap, rss, robots, ai-readme, marp
    lint              Run lint rules against the wiki
    candidates        List / promote / merge / discard candidate pages
    synthesize        Synthesize wiki source pages from raw sessions via LLM
    all               Run the full pipeline: build → graph → export all → lint
                      (optional: synthesize first with --with-synth)
    version           Print version and exit
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Optional

from llmwiki import __version__, REPO_ROOT
from llmwiki.adapters import REGISTRY, discover_adapters
# #v1378-review (#691 follow-up): hoist these re-exports from mid-module
# to here so the file passes E402 cleanly. They re-export business
# logic that lives in the proper domain modules now (#611) — kept here
# for any caller still importing from llmwiki.cli.
from llmwiki.adapters.status import adapter_status as _adapter_status  # noqa: F401
from llmwiki.synth.estimate import synthesize_estimate_report  # noqa: F401
# #691 / #arch-h8: extracted business logic moves out of cli.py.
# cli.py keeps thin re-export wrappers for back-compat with anyone
# doing `from llmwiki.cli import cmd_all, cmd_sync_status, ...`.
from llmwiki.config_schedule import (  # noqa: F401
    apply_default_vault as _apply_default_vault,
    load_default_vault_path as _load_default_vault_path,
    load_schedule_config as _load_schedule_config,
    should_run_after_sync as _should_run_after_sync,
)
from llmwiki.pipeline import run_pipeline as _run_pipeline
from llmwiki.sync.status import (  # noqa: F401
    cmd_sync_status,
    resolve_key_exists as _resolve_key_exists,
)


def cmd_version(args: argparse.Namespace) -> int:
    print(f"llmwiki {__version__}")
    return 0


def cmd_all(args: argparse.Namespace) -> int:
    """Run the full wiki pipeline end-to-end: build → graph → export all → lint.

    Thin shim — the implementation lives in ``llmwiki.pipeline`` (#691).
    """
    _apply_default_vault(args)
    from llmwiki.pipeline_lock import pipeline_lock
    lock_root = REPO_ROOT
    if getattr(args, "vault", None):
        from llmwiki.vault import resolve_vault
        try:
            lock_root = resolve_vault(args.vault).root
        except (FileNotFoundError, NotADirectoryError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
    with pipeline_lock(lock_root):
        return _run_pipeline(args)


def cmd_init(args: argparse.Namespace) -> int:
    """Create raw/, wiki/, site/ directory structure.

    #29: scaffold into the configured vault (``--vault`` / ``config.json``
    ``vault.default_path``) so personal data lands outside the git clone.
    Falls back to REPO_ROOT only when no vault is configured (demo/dev use).
    """
    _apply_default_vault(args)
    base = REPO_ROOT
    if getattr(args, "vault", None):
        from llmwiki.vault import resolve_vault
        try:
            base = resolve_vault(args.vault).root
        except (FileNotFoundError, NotADirectoryError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        print(f"==> scaffolding into vault: {base}")

    for name in ("raw/sessions", "wiki/sources", "wiki/entities", "wiki/concepts", "wiki/syntheses", "site"):
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
        "wiki/index.md": (
            "# Wiki Index\n\n"
            "<!-- #387 U6: each section heading carries a (count) so the index\n"
            "stays scannable as the wiki grows past ~50 pages. Update the count\n"
            "in the heading when adding/removing pages. The index is otherwise\n"
            "kept flat (no nested folders) so a single grep/scan can find any\n"
            "page without descending into a tree. -->\n\n"
            "## Overview (1)\n- [Overview](overview.md)\n\n"
            "## Sources (0)\n\n"
            "## Entities (0)\n\n"
            "## Projects (0)\n\n"
            "## Concepts (0)\n\n"
            "## Syntheses (0)\n"
        ),
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
        print(f"  seeded wiki/dashboard.md")
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

    from llmwiki.convert import convert_all, DEFAULT_OUT_DIR
    from llmwiki.state_store import (
        resolve_state_file,
        check_sync_state_compatible,
        IncompatibleStateError,
    )

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
        from llmwiki.vault import describe_vault, resolve_vault
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
    from llmwiki.pipeline_lock import pipeline_lock
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
        from llmwiki.synth.pipeline import refresh_synth_pending
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
            if args.auto_build and _should_run_after_sync(schedule.get("build", "on-sync")):
                print("  auto-build: regenerating site/...")
                from llmwiki.build import build_site, RAW_SESSIONS, RAW_DIR
                # #54 vault-overlay: read the freshly-synced sessions from the
                # vault, not the repo's empty raw/ (which makes auto-build fail
                # with "RAW_SESSIONS does not exist" right after a vault sync).
                raw_sessions = (vault.root / "raw" / "sessions") if vault_path else RAW_SESSIONS
                raw_dir = (vault.root / "raw") if vault_path else RAW_DIR
                # #54: graph the vault's wiki/ (not the repo's demo wiki).
                wiki_dir = (vault.root / "wiki") if vault_path else (REPO_ROOT / "wiki")
                # #414: sync has explicit user opt-in to mutate wiki/, so it's
                # the right place to seed project stubs.
                build_site(out_dir=site_root, seed_project_stubs=True,
                           raw_sessions=raw_sessions, raw_dir=raw_dir,
                           wiki_dir=wiki_dir)
            if args.auto_lint and _should_run_after_sync(schedule.get("lint", "manual")):
                print("  auto-lint: running wiki lint...")
                from llmwiki.lint import load_pages, run_all, summarize
                # #470: lint the vault's wiki/, not the repo's, when in
                # vault-overlay mode.
                wiki_dir = (vault.root / "wiki") if vault_path else None
                pages = load_pages(wiki_dir) if wiki_dir else load_pages()
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
    from llmwiki.build import build_site

    # v1.2 (#54): vault-overlay mode. Validate the path up front so a
    # typo fails fast before the build walks raw/.
    from llmwiki.build import RAW_SESSIONS, RAW_DIR
    raw_sessions, raw_dir, out_dir = RAW_SESSIONS, RAW_DIR, args.out
    wiki_dir = REPO_ROOT / "wiki"
    lock_root = REPO_ROOT
    if getattr(args, "vault", None):
        from llmwiki.vault import describe_vault, resolve_vault
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

    from llmwiki.pipeline_lock import pipeline_lock
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
        )


def cmd_serve(args: argparse.Namespace) -> int:
    """Serve the built site via a local HTTP server."""
    from llmwiki.serve import serve_site
    return serve_site(directory=args.dir, port=args.port, host=args.host, open_browser=args.open)


def cmd_adapters(args: argparse.Namespace) -> int:
    """List available adapters and their config state.

    G-01 (#287): ``configured`` column now shows ``auto``/``explicit``/
    ``off`` (not ``-``/``enabled``/``disabled``) and a new
    ``will_fire`` column says whether the next ``sync`` will pick the
    adapter up.

    G-02 (#288): ``--wide`` disables the description cap.
    """
    import json as _json
    import shutil as _shutil

    discover_adapters()
    if not REGISTRY:
        print("No adapters registered.")
        return 0

    # Load user config to show enable/disable state
    config_path = REPO_ROOT / "examples" / "sessions_config.json"
    config: dict = {}
    if config_path.is_file():
        try:
            config = _json.loads(config_path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            pass

    # Description column width: 40 by default, full line with --wide,
    # or auto-fit to terminal (minus the four fixed columns + gutters).
    # #387 U2: column names renamed from default/configured/will_fire to
    # present/enabled/active — they read at a glance without needing the
    # legend below.
    wide = bool(getattr(args, "wide", False))
    if wide:
        desc_width: Optional[int] = None  # no cap
    else:
        term_cols = _shutil.get_terminal_size(fallback=(80, 24)).columns
        # Layout: "  name(16)  present(8)  enabled(10)  active(7)  desc"
        desc_width = max(30, term_cols - 55)

    print("Registered adapters:")
    dash = "-"
    header = (
        f"  {'name':<16}  {'present':<8}  {'enabled':<10}  "
        f"{'active':<7}  description"
    )
    print(header)
    sep_desc = "-" * (desc_width if desc_width is not None else len("description"))
    print(
        f"  {dash * 16}  {dash * 8}  {dash * 10}  {dash * 7}  {sep_desc}"
    )
    for name, adapter_cls in sorted(REGISTRY.items()):
        present = "yes" if adapter_cls.is_available() else "no"
        enabled, active = _adapter_status(name, adapter_cls, config)
        desc = adapter_cls.description()
        if desc_width is not None and len(desc) > desc_width:
            desc = desc[: max(desc_width - 3, 1)] + "..."
        print(
            f"  {name:<16}  {present:<8}  {enabled:<10}  "
            f"{active:<7}  {desc}"
        )

    print()
    print("Columns:")
    print("  present  — is the adapter's session store visible on disk?")
    print("  enabled  — auto (default), explicit (enabled:true in config), off (enabled:false)")
    print("  active   — yes/no — will `sync` pick this adapter up on its next run?")
    if not wide:
        print()
        print("Pass --wide to see untruncated descriptions.")
    return 0


def cmd_query(args: argparse.Namespace) -> int:
    """Query the knowledge graph with a natural language question."""
    from llmwiki.graphify_bridge import is_available, query_graph
    if not is_available():
        print("error: graphify not installed. Run: pip install llmwiki[graph]", file=sys.stderr)
        return 2
    question = " ".join(args.question)
    result = query_graph(question, depth=args.depth, token_budget=args.budget)
    print(result)
    return 0


def cmd_graph(args: argparse.Namespace) -> int:
    """Build the knowledge graph from wiki/ wikilinks.

    #488: graphify-engine failures (uninstalled, crashes, empty
    result) ALL fall back to the builtin engine so the user always
    gets *some* graph. Only the builtin engine's exit code is
    authoritative for the CLI return value.
    """
    engine = getattr(args, "engine", "graphify")
    if engine == "graphify":
        from llmwiki.graphify_bridge import is_available, build_graphify_graph
        if not is_available():
            print("  graphify not installed — falling back to builtin engine", file=sys.stderr)
            print("  install with: pip install llmwiki[graph]", file=sys.stderr)
            engine = "builtin"
        else:
            try:
                result = build_graphify_graph()
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

    from llmwiki.graph import build_and_report
    write_json = args.format in ("json", "both")
    write_html = args.format in ("html", "both")
    return build_and_report(write_json_flag=write_json, write_html_flag=write_html)


# cmd_sync_status + _resolve_key_exists moved to llmwiki/sync/status.py
# and re-exported at top of file (#691).


def cmd_export(args: argparse.Namespace) -> int:
    """Export AI-consumable formats from the compiled wiki."""
    import sys as _sys
    from llmwiki.exporters import (
        write_llms_txt,
        write_llms_full_txt,
        write_graph_jsonld,
        write_sitemap,
        write_rss,
        write_robots_txt,
        write_ai_readme,
        write_marp,
        export_all,
    )
    from llmwiki.build import discover_sources, group_by_project, RAW_SESSIONS

    out_dir = args.out if args.out else REPO_ROOT / "site"
    out_dir.mkdir(parents=True, exist_ok=True)

    sources = discover_sources(RAW_SESSIONS)
    if not sources:
        print("error: no sources found. Run 'llmwiki sync' first.", file=_sys.stderr)
        return 2
    groups = group_by_project(sources)

    format_ = args.format
    if format_ == "all":
        paths = export_all(out_dir, groups, sources)
        for name, p in sorted(paths.items()):
            print(f"  wrote {p.relative_to(REPO_ROOT) if p.is_relative_to(REPO_ROOT) else p}")
        return 0

    topic = getattr(args, "topic", "") or ""
    mapping = {
        "llms-txt": lambda: write_llms_txt(out_dir, groups, len(sources)),
        "llms-full-txt": lambda: write_llms_full_txt(out_dir, sources),
        "jsonld": lambda: write_graph_jsonld(out_dir, groups, sources),
        "sitemap": lambda: write_sitemap(out_dir, groups, sources),
        "rss": lambda: write_rss(out_dir, sources),
        "robots": lambda: write_robots_txt(out_dir),
        "ai-readme": lambda: write_ai_readme(out_dir, groups, len(sources)),
        "marp": lambda: write_marp(out_dir, sources, topic=topic),
    }
    fn = mapping.get(format_)
    if not fn:
        print(f"error: unknown format {format_!r}. Valid: {sorted(mapping.keys())} or 'all'", file=_sys.stderr)
        return 2
    p = fn()
    print(f"  wrote {p.relative_to(REPO_ROOT) if p.is_relative_to(REPO_ROOT) else p}")
    return 0


def cmd_lint(args: argparse.Namespace) -> int:
    """Run every registered lint rule against the wiki and print a report."""
    from llmwiki.lint import REGISTRY, load_pages, run_all, summarize  # noqa: F401

    wiki_dir = args.wiki_dir or (REPO_ROOT / "wiki")
    if not wiki_dir.is_dir():
        print(f"error: wiki directory not found: {wiki_dir}", file=sys.stderr)
        return 2

    pages = load_pages(wiki_dir)
    if not pages:
        print(f"  no pages found in {wiki_dir}")
        return 0

    selected = args.rules.split(",") if args.rules else None
    issues = run_all(
        pages,
        include_llm=args.include_llm,
        selected=selected,
    )

    summary = summarize(issues)

    if args.json:
        import json as _json
        print(_json.dumps({
            "summary": summary,
            "issues": issues,
            "total_pages": len(pages),
        }, indent=2))
    else:
        print(f"  scanned {len(pages)} pages")
        print(f"  {sum(summary.values())} issues: "
              f"{summary.get('error', 0)} errors, "
              f"{summary.get('warning', 0)} warnings, "
              f"{summary.get('info', 0)} info")
        print()
        if issues:
            by_rule: dict[str, list[dict[str, str]]] = {}
            for i in issues:
                by_rule.setdefault(i["rule"], []).append(i)
            for rule, rule_issues in sorted(by_rule.items()):
                print(f"## {rule} ({len(rule_issues)})")
                for i in rule_issues[:20]:
                    print(f"  [{i['severity']}] {i['page']}: {i['message']}")
                if len(rule_issues) > 20:
                    print(f"  ... and {len(rule_issues) - 20} more")
                print()

    if args.fail_on_errors and summary.get("error", 0) > 0:
        return 1
    _apply_default_vault(args)
    from llmwiki.state_store import resolve_state_file, update_state
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    update_state(
        lambda s: (s.setdefault("ops", {}).__setitem__("last_lint_run_at", now) or s),
        resolve_state_file(),
    )
    return 0


def cmd_queue(args: argparse.Namespace) -> int:
    from llmwiki.queue_ops import enqueue_task, queue_status, run_queue
    from llmwiki.state_store import resolve_state_file, read_state

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


def cmd_migrate_state(args: argparse.Namespace) -> int:
    # One-shot v1.4.0 migrator lives under scripts/ (not the package).
    import importlib.util
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


def cmd_synthesize(args: argparse.Namespace) -> int:
    """Synthesize wiki source pages from raw sessions (v1.1.0 · #35).

    Uses the backend selected via ``synthesis.backend`` in
    ``sessions_config.json`` (dummy | ollama). ``--check`` prints backend
    availability without running synthesis — useful for diagnosing Ollama
    connectivity before a long sync. ``--estimate`` prints a cached-vs-fresh
    token + dollar breakdown before spending money (#50).
    """
    _apply_default_vault(args)
    from llmwiki.config_schedule import _load_sessions_config
    from llmwiki.synth.pipeline import resolve_backend, synthesize_new_sessions

    config: dict = _load_sessions_config()

    if args.estimate:
        return _synthesize_estimate(args)

    backend = resolve_backend(config)
    print(f"Backend: {backend.name}")

    if args.check:
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
    if vault_path:
        from llmwiki.vault import resolve_vault
        try:
            vault = resolve_vault(vault_path)
        except (FileNotFoundError, NotADirectoryError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        # Post-final-review: Vault is a frozen dataclass with no
        # __truediv__ — `vault / "raw"` raises TypeError. cmd_sync at
        # line 205 correctly uses `vault.root / "raw"`; this site was
        # the missed copy. Caught by the multi-agent code review.
        raw_dir = vault.root / "raw" / "sessions"
        wiki_sources_dir = vault.root / "wiki" / "sources"

    summary = synthesize_new_sessions(
        backend=backend,
        force=args.force,
        raw_dir=raw_dir,
        wiki_sources_dir=wiki_sources_dir,
    )
    print(
        f"Scanned {summary['total_scanned']}, new {summary['new_files']}, "
        f"synthesized {summary['synthesized']}, skipped {summary['skipped']}"
    )
    if summary["errors"]:
        for err in summary["errors"]:
            print(f"  ! {err}", file=sys.stderr)
        return 1
    return 0


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
        from llmwiki.vault import resolve_vault
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
    from contextlib import ExitStack

    from llmwiki.pipeline_lock import pipeline_lock

    with ExitStack() as stack:
        if not args.dry_run:
            stack.enter_context(pipeline_lock(vault_root or REPO_ROOT))
        return _cmd_add_locked(args, docs_dir, vault_root, render)


def _cmd_add_locked(args: argparse.Namespace, docs_dir: Path,
                    vault_root: Path | None, render: str) -> int:
    """Body of cmd_add that runs under the pipeline lock (except dry-run)."""
    from llmwiki.add_doc import add_sources
    from llmwiki.state_store import resolve_state_file, update_state
    from datetime import datetime, timezone

    state_target = resolve_state_file()
    now_ts = datetime.now(timezone.utc)
    task_id = f"add-sync-{int(now_ts.timestamp() * 1000)}"

    def _track(status: str, *, result_msg: str = "", error_msg: str = "") -> None:
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
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
        from llmwiki.add_doc import expected_source_page, remove_raw_docs
        from llmwiki.config_schedule import _load_sessions_config
        from llmwiki.synth.pipeline import resolve_backend, synthesize_new_sessions
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
        from llmwiki.build import RAW_DIR, RAW_SESSIONS, build_site
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
    from datetime import date as _date
    log_path = (vault_root or REPO_ROOT) / "wiki" / "log.md"
    if log_path.parent.is_dir():
        day = _date.today().isoformat()
        with log_path.open("a", encoding="utf-8") as fh:
            for rec in result["docs"]:
                if any(p.exists() for p in rec["paths"]):
                    fh.write(f"\n## [{day}] add | {rec['title']}\n")

    from llmwiki.synth.pipeline import refresh_synth_pending
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
    prefix_tokens = None
    synthesized_source_keys = None
    wiki_sources_dir = None
    docs_root = None
    execution_model = ""
    pricing_model = None
    pricing_fallback_msg = ""
    from llmwiki.cache import MODEL_PRICING, resolve_pricing_model
    from llmwiki.config_schedule import _load_sessions_config
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
    from llmwiki.cache import estimate_tokens
    from llmwiki.state_store import resolve_state_file, update_state
    from llmwiki.synth.pipeline import _discover_raw_sessions, _load_state, discover_synth_source_keys

    state_target = resolve_state_file()
    vault_root = state_target.parent
    raw_root = vault_root / "raw" / "sessions"
    docs_root = vault_root / "raw" / "docs"
    wiki_sources_dir = vault_root / "wiki" / "sources"
    raw_sessions = _discover_raw_sessions(raw_root)
    state_keys = set(_load_state(state_target).keys())
    synthesized_source_keys = discover_synth_source_keys(wiki_sources_dir)
    prefix_parts: list[str] = []
    for rel in ("CLAUDE.md", "wiki/index.md", "wiki/overview.md"):
        p = vault_root / rel
        if p.is_file():
            prefix_parts.append(p.read_text(encoding="utf-8"))
    prefix_tokens = estimate_tokens("\n".join(prefix_parts))
    report = synthesize_estimate_report(
        raw_sessions=raw_sessions,
        state_keys=state_keys,
        prefix_tokens=prefix_tokens,
        model=pricing_model,
        pricing_table=pricing_table,
        synthesized_source_keys=synthesized_source_keys,
        wiki_sources_dir=wiki_sources_dir,
        raw_root=raw_root,
        docs_root=docs_root,
    )
    from datetime import datetime, timezone
    pending_rows = [
        {
            "rel": str(it.get("rel", "")),
            "source": str(it.get("source_file", "")),
            "project": str(it.get("project", "unknown")),
            "is_doc": bool(it.get("is_doc", False)),
            "mtime": str(it.get("mtime", "")),
        }
        for it in report.get("unsynth_items", [])
        if str(it.get("rel", "")).strip()
    ]
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _mut(s: dict[str, Any]) -> dict[str, Any]:
        synth = s.setdefault("synth", {})
        synth["pending"] = pending_rows
        synth["pending_total"] = len(pending_rows)
        synth["pending_updated_at"] = stamp
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
            "warnings": [str(w) for w in report.get("warnings", []) if str(w).strip()],
        }
        return s

    update_state(_mut, state_target)

    for w in report["warnings"]:
        print(f"warning: {w}")
    print("warning: cost estimate uses a local static rate card and token heuristic; real provider billing may deviate.")
    if pricing_fallback_msg:
        print(f"warning: {pricing_fallback_msg}")

    print(f"Corpus:                {report['corpus']:>6} sources (sessions + docs)")
    print(f"Already synthesized:   {report['synthesized']:>6} pages in wiki/sources/")
    print(f"New since last run:    {report['new']:>6}")
    print(
        f"Breakdown: sessions {report.get('new_sessions', 0)} new / "
        f"{report.get('corpus_sessions', 0)} total, docs {report.get('new_docs', 0)} new / "
        f"{report.get('corpus_docs', 0)} total"
    )
    print()
    if execution_model:
        print(
            f"Prefix: {report['prefix_tokens']:,} tok  "
            f"Execution model: {execution_model}  Pricing model: {report['model']}"
        )
    else:
        print(f"Prefix: {report['prefix_tokens']:,} tok  Pricing model: {report['model']}")
    print()
    if report["new"] == 0:
        print(f"Incremental sync:  $0.0000  (nothing new — this is a no-op)")
    else:
        print(
            f"Incremental sync:  ${report['incremental_usd']:.4f}  "
            f"(synthesize the {report['new']} new source(s): "
            f"{report.get('new_sessions', 0)} session(s), "
            f"{report.get('new_docs', 0)} doc source(s))"
        )
    print(
        f"Full re-synth:     ${report['full_force_usd']:.4f}  "
        f"(--force — {report['corpus']} source(s), 1 cache write + {max(report['corpus'] - 1, 0)} hits)"
    )
    return 0


def cmd_candidates(args: argparse.Namespace) -> int:
    """List / promote / merge / discard candidate pages (v1.1.0 · #51)."""
    import json as _json
    from llmwiki.candidates import (
        list_candidates,
        promote,
        merge as merge_candidate,
        discard,
        stale_candidates,
    )

    wiki_dir = args.wiki_dir or (REPO_ROOT / "wiki")
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

    if action == "promote":
        if not args.slug:
            print("error: --slug is required for promote", file=sys.stderr)
            return 2
        path = promote(args.slug, wiki_dir, kind=args.kind)
        print(f"  promoted → {path.relative_to(wiki_dir)}")
        return 0

    if action == "merge":
        if not args.slug or not args.into:
            print("error: both --slug and --into are required for merge", file=sys.stderr)
            return 2
        path = merge_candidate(args.slug, wiki_dir, into_slug=args.into, kind=args.kind)
        print(f"  merged into → {path.relative_to(wiki_dir)}")
        return 0

    if action == "discard":
        if not args.slug:
            print("error: --slug is required for discard", file=sys.stderr)
            return 2
        path = discard(args.slug, wiki_dir, reason=args.reason, kind=args.kind)
        print(f"  discarded → {path.relative_to(wiki_dir)}")
        return 0

    print(f"error: unknown action {action!r}", file=sys.stderr)
    return 2


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
            "sync": "Vault-overlay mode (#54): write new pages inside an "
                    "existing Obsidian / Logseq vault instead of the "
                    "repo's wiki/ directory.",
            "build": "Vault-overlay mode (#54): build from an existing "
                     "Obsidian / Logseq vault. Still writes site output to "
                     "--out.",
            "synthesize": "(#420) Vault-overlay mode: read raw/ + write "
                          "wiki/sources/ under the vault root, and isolate "
                          "the synth state file to the vault. Without this "
                          "flag the state file lives at the repo root, so "
                          "two vaults synthesised against the same repo "
                          "silently share idempotency state.",
            "all": "(#383) With --with-synth: run synthesize against the "
                   "vault's raw/ + wiki/sources/ (same semantics as "
                   "`llmwiki synthesize --vault`).",
            "add": "(#16) Vault-overlay mode: write the converted document "
                   "under the vault's raw/docs/ and run synthesize/build "
                   "against the vault.",
            "init": "(#29) Scaffold raw/, wiki/, site/ into this vault "
                    "instead of the repo, so personal data lands outside "
                    "the git clone.",
        }[role],
    )


def cmd_consolidate_topics(args: argparse.Namespace) -> int:
    """One-time topic consolidation pass (#54).

    Default: render the consolidation prompt (over the auto-derived topic list)
    to a file for the LLM/agent to run. ``--complete PATH`` ingests the model's
    JSON reply and writes the topic cache (merge-map + descriptions) the graph
    and regular-synth prompt then consume.
    """
    _apply_default_vault(args)
    from llmwiki.topics_consolidate import (
        render_consolidation_prompt, parse_and_cache, cache_path,
    )
    wiki_dir = REPO_ROOT / "wiki"
    vault = getattr(args, "vault", None)
    if vault:
        from llmwiki.vault import resolve_vault
        try:
            wiki_dir = resolve_vault(vault).root / "wiki"
        except (FileNotFoundError, NotADirectoryError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

    if args.complete:
        text = sys.stdin.read() if args.complete == "-" else Path(args.complete).read_text(encoding="utf-8")
        try:
            cache = parse_and_cache(text, wiki_dir)
        except (ValueError, OSError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        print(f"  wrote {cache_path(wiki_dir)} — {len(cache['topics'])} canonical "
              f"topics, {len(cache['dropped'])} dropped")
        return 0

    prompt = render_consolidation_prompt(wiki_dir)
    out = cache_path(wiki_dir).with_name(".llmwiki-topic-consolidation.md")
    out.write_text(prompt, encoding="utf-8")
    vault_flag = f" --vault {vault}" if vault else ""
    print(f"  wrote consolidation prompt → {out}")
    print("  Run it through your LLM/agent, save the JSON reply, then:")
    print(f"    llmwiki consolidate-topics --complete <reply.json>{vault_flag}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="llmwiki",
        description="LLM-powered knowledge base from Claude Code and Codex CLI sessions.",
    )
    p.add_argument("--version", action="version", version=f"llmwiki {__version__}")

    sub = p.add_subparsers(dest="cmd", metavar="COMMAND")

    # init
    init = sub.add_parser("init", help="Scaffold raw/, wiki/, site/ directories")
    _add_vault_arg(init, role="init")
    init.set_defaults(func=cmd_init)

    # sync
    sync = sub.add_parser("sync", help="Convert new .jsonl sessions to markdown")
    sync.add_argument("--adapter", nargs="*", default=None, help="Adapter(s) to run; default: all available")
    sync.add_argument("--since", type=str, help="Only sessions on or after YYYY-MM-DD")
    sync.add_argument("--project", type=str, help="Substring filter on project slug")
    sync.add_argument("--include-current", action="store_true", help="Don't skip live sessions (<60 min)")
    sync.add_argument("--force", action="store_true", help="Ignore state file, reconvert everything")
    sync.add_argument(
        "--force-resync", action="store_true",
        help="Override the newer-schema/corrupt-state guard and reconvert "
             "from scratch (#29). Implies --force; may duplicate an "
             "already-populated raw/.",
    )
    sync.add_argument(
        "--fail-on-errors", action="store_true",
        help="Exit 1 if any file fails to convert (default: per-file "
             "errors are quarantined and the run exits 0)",
    )
    sync.add_argument(
        "--auto-build", action=argparse.BooleanOptionalAction, default=True,
        help="After sync, rebuild the site when sessions_config.json's "
             "schedule.build is 'on-sync' (default: on; pass --no-auto-build to skip)",
    )
    sync.add_argument(
        "--auto-lint", action=argparse.BooleanOptionalAction, default=True,
        help="After sync, run lint when sessions_config.json's "
             "schedule.lint is 'on-sync' (default: on; pass --no-auto-lint to skip)",
    )
    _add_vault_arg(sync, role="sync")
    sync.add_argument(
        "--allow-overwrite", action="store_true",
        help="With --vault: allow clobbering existing vault pages "
             "(default: refuse, append under ## Connections instead)",
    )
    sync.add_argument(
        "--status", action="store_true",
        help="Show last-sync time + per-adapter counters + quarantine "
             "(G-03 · #289). Does not run a sync.",
    )
    sync.add_argument(
        "--recent", type=int, default=0,
        help="With --status: also show last N recent log entries.",
    )
    sync.set_defaults(func=cmd_sync)

    # build
    build = sub.add_parser("build", help="Compile static HTML site from raw/ + wiki/")
    build.add_argument("--out", type=Path, default=REPO_ROOT / "site", help="Output dir (default: site/)")
    build.add_argument("--synthesize", action="store_true", help="Call claude CLI for overview synthesis")
    build.add_argument(
        "--claude", type=str, default="",
        help="Path to claude CLI (#421: defaults to `shutil.which('claude')` "
             "so PATH-based / brew / nvm / Windows installs all work)",
    )
    build.add_argument(
        "--search-mode", choices=["auto", "tree", "flat"], default="auto",
        help="Search index mode (#53): auto picks tree vs flat from heading depth",
    )
    _add_vault_arg(build, role="build")
    build.add_argument(
        "--seed-project-stubs", action="store_true", dest="seed_project_stubs",
        help="(#414) Auto-create wiki/projects/<slug>.md stubs for any "
             "newly-discovered project that doesn't have a metadata file. "
             "Off by default — `build` is read-only on wiki/. Use `sync` "
             "(which already mutates wiki/) for routine seeding, or pass "
             "this flag to opt in from CI/scripts.",
    )
    build.set_defaults(func=cmd_build)

    # serve
    serve = sub.add_parser("serve", help="Start local HTTP server")
    serve.add_argument("--dir", type=Path, default=REPO_ROOT / "site", help="Directory to serve (default: site/)")
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--host", type=str, default="127.0.0.1")
    serve.add_argument("--open", action="store_true", help="Open browser after starting")
    serve.set_defaults(func=cmd_serve)

    # adapters
    ads = sub.add_parser("adapters", help="List available adapters")
    ads.add_argument(
        "--wide",
        action="store_true",
        help="Show untruncated adapter descriptions (G-02 · #288).",
    )
    ads.set_defaults(func=cmd_adapters)

    # graph
    graph = sub.add_parser("graph", help="Build the knowledge graph (graph/graph.json + graph.html)")
    graph.add_argument("--format", choices=["json", "html", "both"], default="both")
    graph.add_argument(
        "--engine", choices=["builtin", "graphify"], default="graphify",
        help="Graph engine: 'graphify' (AI-powered, default) or 'builtin' (stdlib wikilinks fallback)",
    )
    graph.set_defaults(func=cmd_graph)

    # export (v0.4)
    exp2 = sub.add_parser(
        "export",
        help="Export AI-consumable formats: llms-txt, llms-full-txt, jsonld, sitemap, rss, robots, ai-readme, marp (or 'all')",
    )
    exp2.add_argument(
        "format",
        choices=["llms-txt", "llms-full-txt", "jsonld", "sitemap", "rss", "robots", "ai-readme", "marp", "all"],
        help="Export format",
    )
    exp2.add_argument("--out", type=Path, default=None, help="Output directory (default: site/)")
    exp2.add_argument("--topic", type=str, default="", help="Topic filter for marp slide generation")
    exp2.set_defaults(func=cmd_export)

    # lint (v1.0, #155) — live count via the rule registry (currently 15)
    from llmwiki.lint import REGISTRY as _LINT_REG
    from llmwiki.lint import rules as _lint_rules  # noqa: F401 — force registration
    lint = sub.add_parser(
        "lint",
        help=f"Run all {len(_LINT_REG)} lint rules against the wiki",
    )
    lint.add_argument("--wiki-dir", type=Path, default=None,
                      help="Wiki directory (default: ./wiki)")
    lint.add_argument("--rules", type=str, default=None,
                      help="Comma-separated rule names (default: all applicable)")
    lint.add_argument("--include-llm", action="store_true",
                      help="Also run LLM-powered rules (requires --llm-callback)")
    lint.add_argument("--json", action="store_true", help="JSON output")
    lint.add_argument("--fail-on-errors", action="store_true",
                      help="Exit non-zero if any error-severity issues found")
    _add_vault_arg(lint, role="synthesize")
    lint.set_defaults(func=cmd_lint)

    queue_p = sub.add_parser("queue", help="Manage unified llmwiki queue")
    queue_p.add_argument("queue_action", nargs="?", default="status", choices=["status", "run", "enqueue"])
    queue_p.add_argument("--limit", type=int, default=20, help="Max tasks to process in one run")
    queue_p.add_argument("--task-type", default="add_doc", choices=["add_doc", "session_sync", "synthesize", "build"])
    queue_p.add_argument("--source", default="", help="Source value for add_doc enqueue")
    queue_p.add_argument("--state-file", type=Path, default=None, help="Override state file path")
    _add_vault_arg(queue_p, role="synthesize")
    queue_p.set_defaults(func=cmd_queue)

    migrate = sub.add_parser("migrate-state", help="One-time migration into unified state")
    migrate.add_argument("--state-file", type=Path, default=None, help="Target unified state file")
    migrate.set_defaults(func=cmd_migrate_state)

    # candidates (v1.1, #51) — approval workflow
    cand = sub.add_parser(
        "candidates",
        help="List / promote / merge / discard candidate wiki pages (approval workflow)",
    )
    cand.add_argument(
        "action", choices=["list", "promote", "merge", "discard"],
        help="What to do with candidates",
    )
    cand.add_argument("--slug", type=str, default=None,
                      help="Candidate slug (required for promote/merge/discard)")
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
    cand.set_defaults(func=cmd_candidates)

    # synthesize (v1.1, #35) — LLM-backed wiki page synthesis
    syn = sub.add_parser(
        "synthesize",
        help="Synthesize wiki source pages from raw sessions via LLM backend",
    )
    # #arch-h7 (#610): mutually-exclusive synth mode flags
    # used to be independently set-able. argparse silently honoured the
    # first one in `cmd_synthesize`'s if/elif chain, so e.g.
    # `synthesize --check --estimate` ran --check and silently dropped
    # --estimate. Use a mutually-exclusive group so the parser rejects
    # the combination loudly with a useful error.
    syn_mode = syn.add_mutually_exclusive_group()
    syn_mode.add_argument(
        "--check", action="store_true",
        help="Probe backend availability and exit (exit 0 if reachable)",
    )
    syn_mode.add_argument(
        "--estimate", action="store_true",
        help="Print cached-vs-fresh token + dollar estimate without calling a backend (#50)",
    )
    # --force is orthogonal (modifies the default re-synthesize-all flow)
    # and stays outside the exclusion group so callers can pass
    # `synthesize --force` for a forced full re-run.
    syn.add_argument(
        "--force", action="store_true",
        help="Ignore state file, re-synthesize all sessions",
    )
    _add_vault_arg(syn, role="synthesize")
    syn.set_defaults(func=cmd_synthesize)

    # add — ingest a document into the wiki (#16)
    add_p = sub.add_parser(
        "add",
        help="Add documents to the wiki: URL, file, or folder → raw/docs/ + synthesize + build (#16)",
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
                       help="Always land a new snapshot even when body matches an existing doc (#22)")
    _add_vault_arg(add_p, role="add")
    add_p.set_defaults(func=cmd_add)

    # consolidate-topics — one-time LLM dedup + description pass (#54)
    cons = sub.add_parser(
        "consolidate-topics",
        help="One-time LLM pass to merge duplicate topics + write descriptions "
             "(cheap: one call over the topic list, not the sessions)",
    )
    cons.add_argument(
        "--complete", metavar="PATH", default=None,
        help="Ingest the LLM's JSON reply (file path, or '-' for stdin) and "
             "write the topic cache; without this, the prompt is emitted.",
    )
    _add_vault_arg(cons, role="synthesize")
    cons.set_defaults(func=cmd_consolidate_topics)

    # query — natural-language graph query
    qry = sub.add_parser("query", help="Query the knowledge graph with a question")
    qry.add_argument("question", nargs="+", help="The question to ask")
    qry.add_argument("--depth", type=int, default=3, help="BFS traversal depth (default: 3)")
    qry.add_argument("--budget", type=int, default=2000, help="Max output tokens (default: 2000)")
    qry.set_defaults(func=cmd_query)

    # version
    ver = sub.add_parser("version", help="Print version")
    ver.set_defaults(func=cmd_version)

    # all — run build + graph + export all + lint in sequence
    all_p = sub.add_parser(
        "all",
        help="Run the full pipeline: build → graph → export all → lint "
             "(add --with-synth to run synthesize first)",
    )
    all_p.add_argument(
        "--out", type=Path, default=REPO_ROOT / "site",
        help="Output dir for build + export (default: site/)",
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
        "--strict", action="store_true",
        help="Exit 2 if lint reports any errors/warnings",
    )
    all_p.add_argument(
        "--with-synth", action="store_true",
        help="Run `synthesize` before build (fills wiki/sources/ from raw/; "
             "may invoke LLM — default off for cost discipline, #383)",
    )
    all_p.add_argument(
        "--synth-force", action="store_true",
        help="With --with-synth: pass --force to synthesize (re-synthesize all sessions)",
    )
    _add_vault_arg(all_p, role="all")
    all_p.set_defaults(func=cmd_all)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 0
    return args.func(args)


def main_add(argv: list[str] | None = None) -> int:
    """Console entry for `llm-wiki-add` — `llmwiki add` with less typing."""
    import sys as _sys
    return main(["add", *(_sys.argv[1:] if argv is None else argv)])


if __name__ == "__main__":
    sys.exit(main())
