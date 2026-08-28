"""Interactive adapter enablement for ``llmwiki configure-sources`` (#182)."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from llmwiki import REPO_ROOT
from llmwiki.adapters import REGISTRY, discover_all
from llmwiki.adapters.settings import adapter_store_present
from llmwiki.adapters.status import print_adapters_table
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


def _vault_openclaw_inbox(config: dict[str, Any]) -> str | None:
    vault = (config.get("vault") or {}).get("default_path")
    if not vault:
        return None
    return str(Path(vault).expanduser() / ".openclaw-sessions-inbox")


def _default_paths(adapter_cls: type, config: dict[str, Any], name: str) -> list[str]:
    try:
        inst = adapter_cls(config)
        stores = inst.session_store_path
    except Exception:
        return []
    if isinstance(stores, Path):
        stores = [stores]
    paths = [str(Path(p).expanduser()) for p in stores]
    if name == "openclaw":
        inbox = _vault_openclaw_inbox(config)
        if inbox and inbox not in paths:
            paths.insert(0, inbox)
    return paths


def _suggested_path(adapter_cls: type, config: dict[str, Any], name: str) -> str:
    """First existing candidate path, else first listed default."""
    candidates = _default_paths(adapter_cls, config, name)
    for path in candidates:
        if Path(path).expanduser().exists():
            return path
    return candidates[0] if candidates else ""


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


def _prompt_enable_block(
    name: str,
    cls: type,
    config: dict[str, Any],
    *,
    ask_choice: Callable[..., str],
    ask_until: Callable[..., Any],
    default_enable: str,
    extra_lines: tuple[str, ...] = (),
) -> dict[str, Any] | None:
    label = cls.description() if hasattr(cls, "description") else name
    print(f"  Found {name}: {label}")
    for line in extra_lines:
        print(line)
    enable = ask_choice(
        "    Enable for sync? [Y/n]: " if default_enable == "y" else "    Enable for sync? [y/N]: ",
        ("y", "yes", "n", "no"),
        default_enable,
    )
    if enable not in ("y", "yes"):
        return {"enabled": False}
    block: dict[str, Any] = {"enabled": True}
    path_key = _PATH_KEYS.get(name)
    if path_key:
        suggested = _suggested_path(cls, config, name)
        if suggested:

            def _path_default(default: str) -> Callable[[str], str]:
                return lambda s: s.strip() or default

            entered = ask_until(
                f"    Path [{suggested}]: ",
                suggested,
                _path_default(suggested),
            )
            block[path_key] = [str(Path(entered).expanduser())]
    return block


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
        present = adapter_store_present(cls, config)
        if not present:
            continue
        is_notes = name in _NOTES_INTAKE or not getattr(cls, "is_ai_session", True)
        ingest_ready = getattr(cls, "ingest_ready", True)
        extra: tuple[str, ...] = ()
        default_enable = "n" if is_notes else "y"
        if not ingest_ready:
            extra = ("    (IDE chat ingest incomplete — see #2; not active on bare sync)",)
            default_enable = "n"
        elif is_notes:
            extra = ("    (notes/export intake — not agent chat history)",)
        block = _prompt_enable_block(
            name,
            cls,
            config,
            ask_choice=ask_choice,
            ask_until=ask_until,
            default_enable=default_enable,
            extra_lines=extra,
        )
        if block is not None:
            updates[name] = block

    for name in sorted(REGISTRY):
        if name in updates or adapter_store_present(REGISTRY[name], config):
            continue
        cls = REGISTRY[name]
        label = cls.description() if hasattr(cls, "description") else name
        print(f"  Not detected: {name} ({label})")
        enable = ask_choice("    Enable with custom path? [y/N]: ", ("y", "yes", "n", "no"), "n")
        if enable not in ("y", "yes"):
            continue
        path_key = _PATH_KEYS.get(name)
        if not path_key:
            updates[name] = {"enabled": True}
            continue
        suggested = _suggested_path(cls, config, name)
        if not suggested and name == "openclaw":
            suggested = _vault_openclaw_inbox(config) or ""
        if not suggested:
            suggested = str(Path.home())

        def _path_default(default: str) -> Callable[[str], str]:
            return lambda s: s.strip() or default

        entered = ask_until(
            f"    Path [{suggested}]: ",
            suggested,
            _path_default(suggested),
        )
        updates[name] = {
            "enabled": True,
            path_key: [str(Path(entered).expanduser())],
        }

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
    config = _load_sessions_config()
    print()
    print("  Active sources after save:")
    print()
    print_adapters_table(config)
    return 0
