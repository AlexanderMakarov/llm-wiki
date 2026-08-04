"""End-to-end build pipeline orchestrator (#691 / #arch-h8).

Pre-#691 ``cmd_all`` lived inside ``cli.py`` and was a 110-LOC pipeline
runner that constructed argparse Namespaces by hand and dispatched to
the cmd_* functions. The architect-agent flagged it as domain logic
that didn't belong in a CLI shim, so the function moved here.

#pipeline-lock-h1: the original post-#691 version kept dispatching to
``cmd_build`` / ``cmd_sync`` / ``cmd_synthesize`` from inside this
module — each of which acquires :func:`llmwiki.pipeline_lock.pipeline_lock`
itself. ``pipeline_lock`` is explicitly **not reentrant** (see its
docstring), so ``llmwiki all`` calling ``cmd_build`` from inside its
own lock deadlocked against itself the moment the lock became
non-trivial to acquire twice. This rewrite calls the **library**
functions those cmd_* wrappers are thin shims over
(:func:`llmwiki.convert.convert_all`, :func:`llmwiki.build.build_site`,
:func:`llmwiki.synth.pipeline.synthesize_new_sessions`, lint's
``load_pages`` / ``run_all``) directly, under **one** outer lock
acquired here. Never reintroduce a call to ``cmd_build`` / ``cmd_sync``
/ ``cmd_synthesize`` inside this module.
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from llmwiki import REPO_ROOT
from llmwiki.build import RAW_DIR, RAW_SESSIONS, build_site
from llmwiki.candidates_harvest import DEFAULT_MIN_REFS, run_harvest
from llmwiki.config_schedule import _load_sessions_config
from llmwiki.convert import convert_all
from llmwiki.graph import build_and_report
from llmwiki.graphify_bridge import build_graphify_graph, is_available
from llmwiki.lint import load_pages, run_all, summarize
from llmwiki.pipeline_lock import pipeline_lock
from llmwiki.reindex import reindex_wiki
from llmwiki.state_store import resolve_state_file, update_state
from llmwiki.synth.pipeline import refresh_synth_pending, resolve_backend, synthesize_new_sessions
from llmwiki.synth.reporting import print_synth_run_summary
from llmwiki.vault import describe_vault, resolve_vault


def _merge_rc(overall: int, rc: int) -> int:
    """Keep the first non-zero exit code seen (worst-first-wins isn't the
    rule here — the *first* failing step's code is what callers report)."""
    return rc if overall == 0 else overall


def _run_graph_step(*, wiki_dir: Path, graph_root: Path, engine: str) -> int:
    """Build the knowledge graph, mirroring ``cmd_graph``'s fallback chain.

    Any graphify failure (uninstalled, crashes, empty result) falls back
    to the builtin engine so the pipeline always produces *some* graph;
    only the builtin engine's exit code is authoritative.
    """
    if engine == "graphify":
        if not is_available():
            print("  graphify not installed — falling back to builtin engine", file=sys.stderr)
            print("  install with: pip install llmwiki[graph]", file=sys.stderr)
            engine = "builtin"
        else:
            try:
                result = build_graphify_graph(
                    wiki_dir=wiki_dir, graph_dir=graph_root / "graph",
                    graphify_out=graph_root / "graphify-out",
                )
            except Exception as e:
                print(f"  graphify engine crashed ({type(e).__name__}: {e}) — "
                      f"falling back to builtin", file=sys.stderr)
                engine = "builtin"
            else:
                if result.get("graph") is not None:
                    return 0
                print("  graphify returned no graph — falling back to builtin",
                      file=sys.stderr)
                engine = "builtin"

    return build_and_report(
        write_json_flag=True, write_html_flag=True,
        wiki_dir=wiki_dir, graph_dir=graph_root / "graph",
    )


def _run_lint_step(wiki_dir: Path) -> tuple[int, dict[str, int]]:
    """Run every lint rule and print the same report ``llmwiki lint`` prints.

    Returns ``(rc, summary)``. ``rc`` is 2 when ``wiki_dir`` doesn't exist,
    else 0 — lint issues alone never fail the pipeline; ``--strict``
    escalation is the caller's job (it needs the summary either way).
    """
    if not wiki_dir.is_dir():
        print(f"error: wiki directory not found: {wiki_dir}", file=sys.stderr)
        return 2, {}

    pages = load_pages(wiki_dir)
    if not pages:
        print(f"  no pages found in {wiki_dir}")
        return 0, {}

    issues = run_all(pages)
    summary = summarize(issues)
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

    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    update_state(
        lambda s: (s.setdefault("ops", {}).__setitem__("last_lint_run_at", now) or s),
        resolve_state_file(),
    )
    return 0, summary


def run_pipeline(args: argparse.Namespace) -> int:
    """Run the full wiki pipeline end-to-end: [sync] → [synthesize] → build → graph → lint.

    Callers must have already run ``_apply_default_vault(args)`` (``cmd_all``
    does this before calling in). Everything below runs under **one**
    :func:`~llmwiki.pipeline_lock.pipeline_lock`, acquired once here —
    library functions are called directly so no nested lock acquisition
    is possible (see module docstring).

    With ``--with-sync`` (before synth/build): converts new sessions with
    auto-build off (the pipeline's own build step runs later anyway),
    refreshes the synth-pending backlog, and reconciles ``wiki/index.md``
    unconditionally.

    With ``--with-synth``: synthesizes wiki source pages from raw sessions
    via the configured LLM backend — opt-in, may invoke an LLM (#383).

    ``build`` already writes every AI-consumable export
    (:func:`llmwiki.exporters.export_all`) as part of
    :func:`~llmwiki.build.build_site`, so this pipeline has no separate
    export step.

    Exit codes:
      0  every step succeeded (lint warnings are informational).
      1  at least one step returned a non-zero exit status.
      2  ``--strict`` was passed and lint reported any error or warning,
         or a required directory (wiki/vault) was missing.
    """
    vault_arg = getattr(args, "vault", None)
    vault_root: Path | None = None
    if vault_arg:
        try:
            vault = resolve_vault(Path(vault_arg))
        except (FileNotFoundError, NotADirectoryError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        vault_root = vault.root
        print(f"==> {describe_vault(vault)}")

    lock_root = vault_root or REPO_ROOT
    raw_sessions = (vault_root / "raw" / "sessions") if vault_root else RAW_SESSIONS
    raw_dir = (vault_root / "raw") if vault_root else RAW_DIR
    wiki_dir = (vault_root / "wiki") if vault_root else (REPO_ROOT / "wiki")
    # #arch: --vault remaps --out's repo-default the same way cmd_build
    # does, both for the printed banner and for the actual build — a
    # vault run whose --out was never overridden must not silently write
    # (or claim to write) into the git clone's site/.
    out_dir = args.out
    if vault_root and out_dir == REPO_ROOT / "site":
        out_dir = vault_root / "site"

    overall_rc = 0

    with pipeline_lock(lock_root):
        if getattr(args, "with_sync", False):
            print("\n==> llmwiki sync (convert; auto-build off)")
            state_file = resolve_state_file()
            rc = convert_all(out_dir=raw_sessions, state_file=state_file)
            if rc != 0:
                overall_rc = _merge_rc(overall_rc, rc)
                if args.fail_fast:
                    print(f"error: step 'sync' exited {rc}; stopping (--fail-fast).", file=sys.stderr)
                    return rc
            refresh_synth_pending(
                raw_dir=raw_sessions if vault_root else None,
                docs_dir=(vault_root / "raw" / "docs") if vault_root else None,
                wiki_sources_dir=(wiki_dir / "sources") if vault_root else None,
                state_file=state_file,
            )
            # Always reconcile — unlike `sync`'s own auto-build path (which
            # only reindexes because it's the step that seeds project
            # stubs), `all --with-sync` runs `build` right after this
            # regardless, so there's no reason to gate the catalog fix-up
            # on anything.
            plan = reindex_wiki(wiki_dir)
            if plan is not None and plan.changed:
                print(f"  reindex: index.md +{len(plan.added)} listed, "
                      f"-{len(plan.removed)} dead link(s)")

        if getattr(args, "with_synth", False):
            print("\n==> llmwiki synth")
            config: dict[str, Any] = _load_sessions_config()
            backend = resolve_backend(config)
            print(f"Backend: {backend.name}")
            if not backend.is_available():
                print(
                    f"error: backend {backend.name} is not available. "
                    "Start the server or change synthesis.backend in config.",
                    file=sys.stderr,
                )
                overall_rc = _merge_rc(overall_rc, 1)
                if args.fail_fast:
                    print("error: step 'synth' exited 1; stopping (--fail-fast).", file=sys.stderr)
                    return overall_rc
            else:
                # Wall clock for this synth+harvest segment (#113).
                t0 = time.monotonic()
                summary = synthesize_new_sessions(
                    backend=backend,
                    force=getattr(args, "synth_force", False),
                    raw_dir=raw_sessions if vault_root else None,
                    wiki_sources_dir=(wiki_dir / "sources") if vault_root else None,
                )
                print(
                    f"Scanned {summary['total_scanned']}, new {summary['new_files']}, "
                    f"synthesized {summary['synthesized']}, skipped {summary['skipped']}"
                )
                if summary["errors"]:
                    for err in summary["errors"]:
                        print(f"  ! {err}", file=sys.stderr)
                    overall_rc = _merge_rc(overall_rc, 1)
                    if args.fail_fast:
                        print("error: step 'synth' exited 1; stopping (--fail-fast).", file=sys.stderr)
                        return overall_rc
                # Default synth also harvests candidates (#90).
                harvest_rc = run_harvest(
                    wiki_dir,
                    min_refs=DEFAULT_MIN_REFS,
                    backend=backend,
                    require_sources=False,
                )
                if harvest_rc != 0:
                    overall_rc = _merge_rc(overall_rc, harvest_rc)
                    if args.fail_fast:
                        print(
                            "error: step 'synth' (candidates) exited "
                            f"{harvest_rc}; stopping (--fail-fast).",
                            file=sys.stderr,
                        )
                        return overall_rc
                elif not summary["errors"]:
                    print_synth_run_summary(
                        synthesized=summary["synthesized"],
                        duration_s=time.monotonic() - t0,
                        tokens=summary.get("tokens"),
                        cost_usd=summary.get("cost_usd"),
                    )

        search_mode = args.search_mode or "auto"
        print(f"\n==> llmwiki build --out {out_dir} --search-mode {search_mode}")
        rc = build_site(
            out_dir=out_dir,
            synthesize=False,
            claude_path="",
            search_mode=search_mode,
            seed_project_stubs=False,
            raw_sessions=raw_sessions,
            raw_dir=raw_dir,
            wiki_dir=wiki_dir,
        )
        if rc != 0:
            overall_rc = _merge_rc(overall_rc, rc)
            if args.fail_fast:
                print(f"error: step 'build' exited {rc}; stopping (--fail-fast).", file=sys.stderr)
                return rc

        if not args.skip_graph:
            print(f"\n==> llmwiki graph --format both --engine {args.graph_engine}")
            rc = _run_graph_step(
                wiki_dir=wiki_dir, graph_root=(vault_root or REPO_ROOT),
                engine=args.graph_engine,
            )
            if rc != 0:
                overall_rc = _merge_rc(overall_rc, rc)
                if args.fail_fast:
                    print(f"error: step 'graph' exited {rc}; stopping (--fail-fast).", file=sys.stderr)
                    return rc

        lint_label = "lint --fail-on-errors" if args.strict else "lint"
        print(f"\n==> llmwiki {lint_label}")
        lint_rc, lint_summary = _run_lint_step(wiki_dir)
        overall_rc = _merge_rc(overall_rc, lint_rc)

        if args.strict:
            # ``--strict`` escalates *any* lint signal — errors OR warnings
            # — into a pipeline failure, independent of lint's own exit
            # code (which by design only fires on error-severity issues).
            errors = lint_summary.get("error", 0)
            warnings = lint_summary.get("warning", 0)
            if errors or warnings:
                print(
                    f"error: --strict: lint reported "
                    f"{errors} error(s) + {warnings} warning(s).",
                    file=sys.stderr,
                )
                return 2

    return overall_rc
