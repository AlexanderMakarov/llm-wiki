"""Near-real-time maintain watcher — sync → synthesize → build when sessions finish.

Polls adapter session stores (stdlib mtime; no inotify dep). Uses per-adapter
``session_ready`` heuristics. Mid-turn (``unsafe``) waits. Unsupported finished
signals: after a 2s mtime settle, trigger (documented at startup and in --help).

Single-flight: only one maintain iteration at a time; further changes set a
dirty flag and retry after the current run finishes.

Sync may time out (~180s). Synthesize and build have no timeout.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from llmwiki import REPO_ROOT
from llmwiki.adapters import REGISTRY, discover_all
from llmwiki.config_schedule import load_default_vault_path
from llmwiki.session_ready import Ready, session_ready_for_adapter

SETTLE_SECONDS = 2.0
SYNC_TIMEOUT_SECONDS = 180.0

_STARTUP_BANNER = f"""\
==> llmwiki watch
    Near-real-time maintain: when a session finishes, run sync → synthesize → build.
    Turn-complete signals (Claude stop_reason, Cursor last-role, Codex events) gate ingest.
    Adapters without a finished-signal: after a 2s mtime settle, the pipeline still runs
    (not a multi-minute wait). Mid-tool / permission loops stay deferred until safe.
    Single-flight: one update at a time; overlapping changes retry after it finishes.
    Sync timeout {SYNC_TIMEOUT_SECONDS:.0f}s; synthesize and build have no timeout.
"""


def scan_mtimes(adapters: list[str] | None) -> dict[str, float]:
    """Return ``{path: mtime}`` for every session file visible to adapters.

    Uses ``discover_all`` — not ``discover_adapters`` — so contrib stores
    (Cursor, OpenClaw, …) are watched too. ``sync`` loads contrib the same
    way, and a store watch can't see is a store watch can never trigger on.
    Opt-in adapters stay excluded: ``is_available()`` already gates those.
    """
    discover_all()
    selected_cls = []
    if adapters:
        for name in adapters:
            if name in REGISTRY:
                selected_cls.append(REGISTRY[name])
    else:
        selected_cls = [c for c in REGISTRY.values() if c.is_available()]

    mtimes: dict[str, float] = {}
    for cls in selected_cls:
        adapter = cls()
        for p in adapter.discover_sessions():
            try:
                mtimes[str(p)] = p.stat().st_mtime
            except OSError:
                continue
    return mtimes


def _adapter_for_path(path: str) -> str:
    discover_all()
    p = Path(path)
    for name, cls in REGISTRY.items():
        try:
            adapter = cls()
            for sp in adapter.discover_sessions():
                if sp.resolve() == p.resolve():
                    return name
        except OSError:
            continue
    return ""


def _load_records_for_ready(adapter_name: str, path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (records, messages) for session_ready dispatch."""
    discover_all()
    cls = REGISTRY.get(adapter_name)
    if cls is None:
        return [], []
    adapter = cls()
    try:
        records = list(adapter.load_records(path))
    except Exception:
        return [], []
    # Cursor: prefer raw messages if adapter exposes them
    messages: list[dict[str, Any]] = []
    load_raw = getattr(adapter, "load_raw_messages", None)
    if callable(load_raw):
        try:
            messages = list(load_raw(path))
        except Exception:
            messages = []
    if not messages and adapter_name.startswith("cursor"):
        messages = [r for r in records if isinstance(r, dict)]
    return records, messages


def path_ready(path: str) -> Ready:
    adapter_name = _adapter_for_path(path)
    records, messages = _load_records_for_ready(adapter_name, Path(path))
    return session_ready_for_adapter(
        adapter_name, records=records, messages=messages or None,
    )


def run_maintain(
    *,
    vault: Path | None,
    with_synthesize: bool = True,
    with_build: bool = True,
    working_dir: Path | None = None,
) -> int:
    """Run sync (--include-current --no-auto-build) then optional synth/build."""
    cwd = str(working_dir or REPO_ROOT)
    py = sys.executable
    vault_args = ["--vault", str(vault)] if vault else []

    sync_cmd = [
        py, "-m", "llmwiki", "sync",
        "--include-current", "--no-auto-build", "--no-auto-lint",
        *vault_args,
    ]
    print(f"==> running: {' '.join(sync_cmd)}")
    try:
        sync_rc = subprocess.run(
            sync_cmd, cwd=cwd, timeout=SYNC_TIMEOUT_SECONDS,
        ).returncode
    except subprocess.TimeoutExpired:
        print(f"  warning: sync timed out after {SYNC_TIMEOUT_SECONDS:.0f}s",
              file=sys.stderr)
        return 1
    if sync_rc != 0:
        return sync_rc

    if with_synthesize:
        synth_cmd = [py, "-m", "llmwiki", "synth", *vault_args]
        print(f"==> running: {' '.join(synth_cmd)}")
        synth_rc = subprocess.run(synth_cmd, cwd=cwd).returncode  # no timeout
        if synth_rc != 0:
            return synth_rc

    if with_build:
        build_cmd = [py, "-m", "llmwiki", "build", *vault_args]
        print(f"==> running: {' '.join(build_cmd)}")
        build_rc = subprocess.run(build_cmd, cwd=cwd).returncode  # no timeout
        if build_rc != 0:
            return build_rc
    return 0


def watch(
    adapters: list[str] | None = None,
    interval: float = 5.0,
    settle: float = SETTLE_SECONDS,
    dry_run: bool = False,
    vault: Path | None = None,
    with_synthesize: bool = True,
    with_build: bool = True,
) -> int:
    """Main watch loop (single-flight)."""
    print(_STARTUP_BANNER)
    print(f"    interval: {interval}s  settle: {settle}s")
    print(f"    synth: {'on' if with_synthesize else 'off'}  "
          f"build: {'on' if with_build else 'off'}")
    if adapters:
        print(f"    adapters: {', '.join(adapters)}")
    else:
        discover_all()
        avail = [n for n, c in REGISTRY.items() if c.is_available()]
        print(f"    adapters: {', '.join(avail) or '(none available)'}")
    print("    Ctrl+C to stop.\n")

    baseline = scan_mtimes(adapters)
    print(f"==> baseline: {len(baseline)} files")

    busy = False
    dirty = False
    pending_paths: set[str] = set()
    last_change: dict[str, float] = {}

    try:
        while True:
            time.sleep(interval)
            current = scan_mtimes(adapters)
            now = time.time()

            for path, mtime in current.items():
                if path not in baseline or baseline[path] != mtime:
                    pending_paths.add(path)
                    last_change[path] = now
                    if busy:
                        dirty = True

            baseline = current

            if busy:
                continue

            # Paths that have been settled
            ready_paths: list[str] = []
            for path in list(pending_paths):
                if now - last_change.get(path, 0) < settle:
                    continue
                status = path_ready(path)
                if status == Ready.UNSAFE:
                    # Still mid-turn — keep pending, wait for more writes
                    continue
                # SAFE or UNSUPPORTED → trigger after settle
                ready_paths.append(path)
                pending_paths.discard(path)

            if not ready_paths and not dirty:
                continue

            if dry_run:
                print(f"==> [dry-run] would maintain {len(ready_paths)} path(s)")
                dirty = False
                continue

            busy = True
            dirty = False
            try:
                print(f"==> maintain ({len(ready_paths)} settled path(s))")
                # Do not hold pipeline_lock here: sync/synthesize/build each
                # acquire it in their own process. Parent + child would deadlock.
                rc = run_maintain(
                    vault=vault,
                    with_synthesize=with_synthesize,
                    with_build=with_build,
                )
                if rc != 0:
                    print(f"  warning: maintain exited {rc}", file=sys.stderr)
            finally:
                busy = False
            if dirty:
                # Force re-settle of any still-pending + re-scan next loop
                print("==> changes arrived during maintain; will retry")
                for path in pending_paths:
                    last_change[path] = time.time()
    except KeyboardInterrupt:
        print("\n==> watch stopped")
        return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="llmwiki watch",
        description=(
            "Near-real-time vault maintain when agent sessions finish. "
            "Uses per-adapter turn-complete signals. Adapters without a "
            "finished-signal trigger after a 2s mtime settle (not a long "
            "quiesce). Mid-tool/permission turns wait. Single-flight updates."
        ),
    )
    parser.add_argument("--adapter", nargs="*", help="Adapter name(s) to watch")
    parser.add_argument("--interval", type=float, default=5.0,
                        help="Poll interval seconds (default 5)")
    parser.add_argument("--settle", type=float, default=SETTLE_SECONDS,
                        help="Mtime settle seconds before ready check (default 2)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Detect only; do not sync/synthesize/build")
    parser.add_argument("--no-synthesize", action="store_true",
                        help="Skip synthesize step")
    parser.add_argument("--no-build", action="store_true",
                        help="Skip build step")
    parser.add_argument("--vault", type=Path, default=None,
                        help="Vault root (default: config.json vault.default_path)")
    args = parser.parse_args(argv)

    vault = args.vault
    if vault is None:
        vault = load_default_vault_path()

    return watch(
        adapters=args.adapter,
        interval=args.interval,
        settle=args.settle,
        dry_run=args.dry_run,
        vault=vault,
        with_synthesize=not args.no_synthesize,
        with_build=not args.no_build,
    )


if __name__ == "__main__":
    raise SystemExit(main())
