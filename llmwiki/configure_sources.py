"""Interactive adapter enablement for ``llmwiki configure-sources`` (#182)."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from llmwiki import REPO_ROOT
from llmwiki.adapters import REGISTRY, discover_all
from llmwiki.adapters.settings import adapter_is_available
from llmwiki.config_schedule import _load_sessions_config

# Adapters whose default store path may be shown / edited in the interview.
_PATH_KEYS: dict[str, str] = {
    "obsidian": "vault_paths",
    "openclaw": "roots",
    "codex_cli": "roots",
    "cursor": "roots",
    "cursor_cli": "roots",
    "copilot_chat": "roots",
    "copilot_cli": "roots",
    "gemini_cli": "roots",
    "opencode": "roots",
    "chatgpt": "export_dirs",
}

_NOTES_INTAKE = frozenset({"obsidian", "chatgpt"})


def _default_paths(adapter_cls: type, config: dict[str, Any]) -> list[str]:
    try:
        inst = adapter_cls(config)
        stores = inst.session_store_path
    except Exception:
        return []
    if isinstance(stores, Path):
        stores = [stores]
    return [str(Path(p).expanduser()) for p in stores]


def _merge_write_adapters(updates: dict[str, dict[str, Any]]) -> None:
    cfg_path = REPO_ROOT / "config.json"
    cfg: dict[str, Any] = {}
    if cfg_path.is_file():
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            cfg = {}
    adapters = cfg.setdefault("adapters", {})
    if not isinstance(adapters, dict):
        adapters = {}
        cfg["adapters"] = adapters
    for name, block in updates.items():
        existing = adapters.get(name, {})
        if not isinstance(existing, dict):
            existing = {}
        merged = {**existing, **block}
        adapters[name] = merged
    cfg_path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    print(f"  wrote adapter settings → {cfg_path}")


def run_configure_sources(
    *,
    yes: bool = False,
    ask_choice: Callable[..., str] | None = None,
    ask_until: Callable[..., Any] | None = None,
) -> int:
    """Probe stores and optionally write ``adapters.*`` to ``config.json``."""
    if yes or not sys.stdin.isatty():
        print("configure-sources: skipped (non-interactive). Run in a terminal to interview.")
        return 0

    if ask_choice is None or ask_until is None:
        from llmwiki.cli import _ask_choice, _ask_until  # noqa: PLC0415

        ask_choice = ask_choice or _ask_choice
        ask_until = ask_until or _ask_until

    discover_all()
    config = _load_sessions_config()
    updates: dict[str, dict[str, Any]] = {}

    print("llmwiki configure-sources")
    print("  Detecting session stores on disk…")
    print()

    for name in sorted(REGISTRY):
        cls = REGISTRY[name]
        present = adapter_is_available(cls, config)
        label = cls.description() if hasattr(cls, "description") else name
        if not present:
            continue
        is_notes = name in _NOTES_INTAKE or not getattr(cls, "is_ai_session", True)
        if is_notes:
            print(f"  Found {name}: {label}")
            print("    (notes/export intake — not agent chat history)")
            enable = ask_choice("    Enable for sync? [y/N]: ", ("y", "yes", "n", "no"), "n")
        else:
            print(f"  Found {name}: {label}")
            enable = ask_choice("    Enable for sync? [Y/n]: ", ("y", "yes", "n", "no"), "y")
        if enable not in ("y", "yes"):
            updates[name] = {"enabled": False}
            continue
        block: dict[str, Any] = {"enabled": True}
        path_key = _PATH_KEYS.get(name)
        if path_key:
            defaults = _default_paths(cls, config)
            if defaults:
                suggested = defaults[0]

                def _path_default(default: str) -> Callable[[str], str]:
                    return lambda s: s.strip() or default

                entered = ask_until(
                    f"    Path [{suggested}]: ",
                    suggested,
                    _path_default(suggested),
                )
                block[path_key] = [str(Path(entered).expanduser())]
        updates[name] = block

    if not updates:
        print("  No session stores detected — nothing to configure.")
        return 0

    print()
    print("  Will write:")
    for name, block in sorted(updates.items()):
        print(f"    adapters.{name}: {block}")
    answer = ask_choice("  Save to config.json? [Y/n]: ", ("y", "yes", "n", "no"), "y")
    if answer not in ("y", "yes"):
        print("  Aborted — no changes written.")
        return 0
    _merge_write_adapters(updates)
    print("  Run `llmwiki adapters` to confirm active sources.")
    return 0
