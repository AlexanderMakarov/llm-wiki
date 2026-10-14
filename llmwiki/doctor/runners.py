"""Dispatch heal-catalog ``runner`` ids to in-process APIs or ``-m llmwiki``.

Hard rule: never escalate privileges (no ``sudo``, no ``os.setuid``). Prefer
in-process APIs; fall back to ``[sys.executable, "-m", "llmwiki", …]``.
"""

from __future__ import annotations

import importlib
import os
import shlex
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from llmwiki.install_hint import install_hint
from llmwiki.reindex import apply_reindex, plan_reindex

#: Runners that may spend LLM tokens / rewrite many pages — never under ``--yes`` alone.
DANGEROUS_RUNNER_PREFIXES: tuple[str, ...] = (
    "synth",
    "install_extra:",
    "migrate:",
    "build",
    "candidates:",
    "install_automation",
    "install_agent_kit",
)

#: Valid ``candidates:<action>`` suffixes (must match ``llmwiki candidates`` choices).
CANDIDATES_ACTIONS: frozenset[str] = frozenset(
    {
        "list",
        "promote",
        "flip-promote",
        "merge",
        "discard",
        "apply",
        "rewrite-key-facts",
    }
)

#: Catalog runners with no ``:`` suffix that map to in-process or ``-m llmwiki`` ids.
KNOWN_BARE_RUNNERS: frozenset[str] = frozenset(
    {
        "reindex",
        "synth",
        "build",
        "install_automation",
        "install_agent_kit",
    }
)

_ELEVATION_TOKENS = frozenset({"sudo", "doas", "pkexec", "runas"})


@dataclass(frozen=True)
class RunnerResult:
    """Outcome of one :func:`dispatch_runner` call."""

    ok: bool
    runner: str
    message: str
    mutated: bool = False
    refused_elevation: bool = False


def runner_is_dangerous(runner: str | None) -> bool:
    """True when ``runner`` must never auto-apply under ``--yes`` alone."""
    if not runner:
        return True
    if runner in DANGEROUS_RUNNER_PREFIXES:
        return True
    return any(runner.startswith(prefix) for prefix in DANGEROUS_RUNNER_PREFIXES if prefix.endswith(":"))


def command_requires_elevation(argv: list[str] | tuple[str, ...] | str) -> bool:
    """True when ``argv`` would escalate privileges (sudo / admin)."""
    if isinstance(argv, str):
        parts = shlex.split(argv)
    else:
        parts = [str(a) for a in argv]
    if not parts:
        return False
    first = Path(parts[0]).name.casefold()
    if first in _ELEVATION_TOKENS:
        return True
    return any(p.casefold() in _ELEVATION_TOKENS for p in parts)


def _refuse_elevation(runner: str, argv: list[str]) -> RunnerResult:
    cmd = " ".join(shlex.quote(a) for a in argv)
    return RunnerResult(
        ok=False,
        runner=runner,
        message=(
            f"Refused elevation for runner {runner!r}. "
            f"Run this yourself in an elevated session if needed: {cmd}"
        ),
        mutated=False,
        refused_elevation=True,
    )


def _run_reindex(vault: Path) -> RunnerResult:
    wiki_dir = Path(vault) / "wiki"
    plan = plan_reindex(wiki_dir)
    if plan is None:
        return RunnerResult(
            ok=True,
            runner="reindex",
            message="Nothing to reindex (empty wiki).",
            mutated=False,
        )
    if not plan.changed:
        return RunnerResult(
            ok=True,
            runner="reindex",
            message="index.md already in sync.",
            mutated=False,
        )
    changed = apply_reindex(plan)
    return RunnerResult(
        ok=True,
        runner="reindex",
        message="Reindexed wiki/index.md." if changed else "index.md unchanged.",
        mutated=bool(changed),
    )


def _subprocess_llmwiki(args: list[str], *, vault: Path) -> tuple[int, str]:
    argv = [sys.executable, "-m", "llmwiki", *args, "--vault", str(vault)]
    if command_requires_elevation(argv):
        return 126, "elevation refused"
    proc = subprocess.run(
        argv,
        check=False,
        capture_output=True,
        text=True,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, out.strip()


def _run_migrate(name: str, vault: Path) -> RunnerResult:
    runner = f"migrate:{name}"
    # Prefer in-process migration modules when present.
    module_map: dict[str, str] = {
        "broken-provenance": "llmwiki.migrate_broken_provenance",
        "doc-source-provenance": "llmwiki.migrate_doc_source_provenance",
        "page-kinds": "llmwiki.migrate_page_kinds",
        "dismissal-ledger": "llmwiki.migrate_dismissal_ledger",
        "topic-kinds": "llmwiki.migrate_topic_kinds",
        "source-page-paths": "llmwiki.migrate_source_page_paths",
        "wikilink-titles": "llmwiki.migrate_wikilink_titles",
        "whole-document-storage": "llmwiki.migrate_whole_document_storage",
        "discarded-topic-links": "llmwiki.migrate_discarded_topic_links",
    }
    mod_name = module_map.get(name)
    if mod_name is not None:
        mod = importlib.import_module(mod_name)
        run_migration: Callable[..., dict[str, Any]] | None = getattr(
            mod, "run_migration", None
        )
        if callable(run_migration):
            report = run_migration(vault=Path(vault), dry_run=False)
            return RunnerResult(
                ok=True,
                runner=runner,
                message=f"migrate {name} complete: {report!r}"[:500],
                mutated=True,
            )
    code, out = _subprocess_llmwiki(["migrate", name], vault=vault)
    if code == 126:
        return _refuse_elevation(runner, [sys.executable, "-m", "llmwiki", "migrate", name])
    return RunnerResult(
        ok=code == 0,
        runner=runner,
        message=out or f"migrate {name} exit {code}",
        mutated=code == 0,
    )


def _run_install_extra(extra: str, vault: Path) -> RunnerResult:
    del vault  # install targets the running interpreter, not the vault
    runner = f"install_extra:{extra}"
    hint = install_hint(extra)
    argv = shlex.split(hint)
    if command_requires_elevation(argv):
        return _refuse_elevation(runner, argv)
    geteuid = getattr(os, "geteuid", None)
    if callable(geteuid) and geteuid() == 0:  # pragma: no cover — never elevate
        return RunnerResult(
            ok=False,
            runner=runner,
            message="Refusing to install packages while running as root.",
            mutated=False,
            refused_elevation=True,
        )
    proc = subprocess.run(argv, check=False, capture_output=True, text=True)
    out = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return RunnerResult(
        ok=proc.returncode == 0,
        runner=runner,
        message=out or f"install_extra:{extra} exit {proc.returncode}",
        mutated=proc.returncode == 0,
    )


def _run_module_cli(runner: str, cli_args: list[str], vault: Path) -> RunnerResult:
    argv = [sys.executable, "-m", "llmwiki", *cli_args, "--vault", str(vault)]
    if command_requires_elevation(argv):
        return _refuse_elevation(runner, argv)
    code, out = _subprocess_llmwiki(cli_args, vault=vault)
    if code == 126:
        return _refuse_elevation(runner, argv)
    return RunnerResult(
        ok=code == 0,
        runner=runner,
        message=out or f"{runner} exit {code}",
        mutated=code == 0,
    )


def dispatch_runner(
    runner: str,
    vault: Path,
    *,
    kit_dest: Path | None = None,
) -> RunnerResult:
    """Execute one catalog ``runner`` id against ``vault``.

    Raises nothing for expected failures — returns :class:`RunnerResult`.
    """
    rid = (runner or "").strip()
    if not rid:
        return RunnerResult(ok=False, runner="", message="No runner id.", mutated=False)

    if command_requires_elevation([rid]) or rid.casefold().startswith("sudo"):
        return _refuse_elevation(rid, [rid])

    if rid == "reindex":
        return _run_reindex(Path(vault))

    if rid.startswith("migrate:"):
        name = rid.split(":", 1)[1].strip()
        if not name:
            return RunnerResult(ok=False, runner=rid, message="Empty migrate name.")
        return _run_migrate(name, Path(vault))

    if rid.startswith("install_extra:"):
        extra = rid.split(":", 1)[1].strip()
        if not extra:
            return RunnerResult(ok=False, runner=rid, message="Empty extra name.")
        return _run_install_extra(extra, Path(vault))

    if rid == "synth":
        return _run_module_cli(rid, ["synth"], Path(vault))

    if rid == "build":
        return _run_module_cli(rid, ["build"], Path(vault))

    if rid.startswith("candidates:"):
        action = rid.split(":", 1)[1].strip()
        if action not in CANDIDATES_ACTIONS:
            return RunnerResult(
                ok=False,
                runner=rid,
                message=(
                    f"Unknown candidates action {action!r}; "
                    f"valid: {', '.join(sorted(CANDIDATES_ACTIONS))}"
                ),
                mutated=False,
            )
        # Candidate promote/merge/discard need human intent; list is the only
        # catalog-safe default if a future entry attaches a candidates: runner.
        return _run_module_cli(rid, ["candidates", action], Path(vault))

    if rid == "install_automation":
        return _run_module_cli(rid, ["install-automation"], Path(vault))

    if rid == "install_agent_kit":
        dest = kit_dest
        if dest is None:
            return RunnerResult(
                ok=False,
                runner=rid,
                message=(
                    "install_agent_kit needs an explicit --dest; "
                    "print: llmwiki install-agent-kit --dest <agent-dir>"
                ),
                mutated=False,
            )
        argv = [
            sys.executable,
            "-m",
            "llmwiki",
            "install-agent-kit",
            "--dest",
            str(dest),
        ]
        if command_requires_elevation(argv):
            return _refuse_elevation(rid, argv)
        proc = subprocess.run(argv, check=False, capture_output=True, text=True)
        out = ((proc.stdout or "") + (proc.stderr or "")).strip()
        return RunnerResult(
            ok=proc.returncode == 0,
            runner=rid,
            message=out or f"install_agent_kit exit {proc.returncode}",
            mutated=proc.returncode == 0,
        )

    return RunnerResult(
        ok=False,
        runner=rid,
        message=f"Unknown runner {rid!r} — guided only; not executed.",
        mutated=False,
    )
