"""Interactive adapter enablement for ``llmwiki configure-sources`` (#182, #192)."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from llmwiki import PACKAGE_ROOT, REPO_ROOT
from llmwiki.adapters import REGISTRY, discover_all
from llmwiki.adapters.base import SyncCandidateEstimate
from llmwiki.adapters.settings import adapter_store_present
from llmwiki.adapters.status import print_adapters_table
from llmwiki.config_schedule import _load_sessions_config
from llmwiki.sync.lookback import parse_since_date

# Adapters whose default store path may be shown / edited in the interview.
_PATH_KEYS: dict[str, str] = {
    "obsidian": "vault_paths",
    "openclaw": "roots",
    "codex_cli": "roots",
    "cursor_ide": "roots",
    "cursor_cli": "roots",
    "copilot_chat": "roots",
    "copilot_cli": "roots",
    "gemini_cli": "roots",
    "opencode": "roots",
    "chatgpt": "export_dirs",
}

_NOTES_INTAKE = frozenset({"obsidian", "chatgpt"})

# Sentinel: per-adapter Enter → inherit shared (drop any prior ``since`` key).
_INHERIT_SINCE = object()


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


def suggested_since_today_minus_30(*, today: datetime | None = None) -> str:
    """Absolute ``YYYY-MM-DD`` for today UTC − 30 days (configure quiz default)."""
    base = (today or datetime.now(UTC)).date()
    return (base - timedelta(days=30)).isoformat()


def _section_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Shallow section merge: nested dicts updated key-wise, other values replaced."""
    out = dict(base)
    for key, value in overlay.items():
        existing = out.get(key)
        if isinstance(value, dict) and isinstance(existing, dict):
            out[key] = {**existing, **value}
        else:
            out[key] = value
    return out


def _load_quiz_config() -> dict[str, Any]:
    """Shipped examples merged with ``REPO_ROOT/config.json`` (the write target)."""
    examples = PACKAGE_ROOT.parent / "examples" / "sessions_config.json"
    merged = _load_sessions_config(examples) if examples.is_file() else {}
    return _section_merge(merged, _load_sessions_config(REPO_ROOT / "config.json"))


def _estimate_for(
    _name: str, cls: type, config: dict[str, Any]
) -> tuple[SyncCandidateEstimate, str | None]:
    """Return a count estimate, plus an error class name when the store walk failed."""
    try:
        return cls(config).estimate_sync_candidates(), None
    except Exception as exc:
        return SyncCandidateEstimate(eligible=0, in_last_30_days=0), type(exc).__name__


def _format_earliest(est: SyncCandidateEstimate) -> str:
    """Calendar day in the system local timezone (no clock time)."""
    if est.earliest is None:
        return "—"
    return est.earliest.astimezone().date().isoformat()


def _resolve_since_date(raw: str) -> str:
    """Validated ``YYYY-MM-DD`` (empty answers never reach here)."""
    s = raw.strip()
    parse_since_date(s)
    return s


def _path_found(cls: type, config: dict[str, Any]) -> bool:
    return adapter_store_present(cls, config)


def _merge_write_config(
    adapter_updates: dict[str, dict[str, Any]],
    *,
    filters_since: str | None | object = _INHERIT_SINCE,
    clear_adapter_since: frozenset[str] | set[str] | None = None,
) -> None:
    """Merge-write ``adapters.*`` and optional ``filters.since`` into ``config.json``.

    ``filters_since``:
      - ``_INHERIT_SINCE`` — leave ``filters.since`` untouched (non-quiz writes)
      - ``None`` — leave shared unset (pop ``filters.since`` if present)
      - ``str`` — set ``filters.since`` to that absolute date

    ``clear_adapter_since`` — adapter names whose prior ``since`` override is
    removed (Enter = inherit shared). Other keys on those adapters are kept.
    """
    clear = frozenset(clear_adapter_since or ())
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
    for name, block in adapter_updates.items():
        existing = adapters.get(name, {})
        if not isinstance(existing, dict):
            existing = {}
        merged = {**existing, **block}
        if name in clear:
            merged.pop("since", None)
        adapters[name] = merged

    if filters_since is not _INHERIT_SINCE:
        filters = cfg.get("filters")
        if not isinstance(filters, dict):
            filters = {}
            cfg["filters"] = filters
        if filters_since is None:
            filters.pop("since", None)
        else:
            filters["since"] = filters_since

    cfg_path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    print(f"  wrote adapter settings → {cfg_path}")


def _merge_write_adapters(updates: dict[str, dict[str, Any]]) -> None:
    """Back-compat: adapters-only merge (no ``filters.since`` change)."""
    _merge_write_config(updates)


def _print_adapter_facts(
    name: str,
    cls: type,
    config: dict[str, Any],
    *,
    path_found: bool,
    extra_lines: tuple[str, ...] = (),
) -> None:
    label = cls.description() if hasattr(cls, "description") else name
    print()
    print(f"── {name} ──")
    print(f"  {label}")
    for line in extra_lines:
        print(line)
    suggested = _suggested_path(cls, config, name)
    if path_found and suggested:
        print(f"  Path: {suggested}  (found)")
    elif suggested:
        print(f"  Path: {suggested}  (not found)")
    else:
        print("  Path: (not found)")
    est, estimate_err = _estimate_for(name, cls, config)
    print(
        f"  Sessions: {est.eligible} · Earliest: {_format_earliest(est)} · "
        f"In last 30 days: {est.in_last_30_days}"
    )
    if estimate_err:
        print(f"  (count unavailable: {estimate_err})")


def _prompt_path(
    name: str,
    cls: type,
    config: dict[str, Any],
    *,
    path_found: bool,
    ask_until: Callable[..., Any],
) -> str | None:
    path_key = _PATH_KEYS.get(name)
    if not path_key:
        return None
    suggested = _suggested_path(cls, config, name)
    if name == "openclaw" and not suggested:
        suggested = _vault_openclaw_inbox(config) or ""

    def _path_or_keep(default: str) -> Callable[[str], str]:
        return lambda s: s.strip() or default

    if path_found and suggested:
        entered = ask_until(
            f"    Path [{suggested}]: ",
            suggested,
            _path_or_keep(suggested),
        )
        return str(Path(entered).expanduser())

    empty = 0
    while True:
        entered = ask_until(
            "    Path: ",
            "",
            lambda s: s.strip(),
        )
        if entered:
            return str(Path(entered).expanduser())
        empty += 1
        if empty >= 3:
            print("    skipping — path is required when the default store was not found")
            return None
        print("    error: path is required when the default store was not found")


def _prompt_adapter(
    name: str,
    cls: type,
    config: dict[str, Any],
    *,
    shared_since: str,
    ask_choice: Callable[..., str],
    ask_until: Callable[..., Any],
) -> dict[str, Any] | None:
    """One adapter: facts → enable → path + start date if enabled.

    Returns ``None`` when the store is missing and the user declines enable
    (do not write a stub). Returns ``{enabled: False}`` when the store exists
    and they turn it off.
    """
    path_found = _path_found(cls, config)
    is_notes = name in _NOTES_INTAKE or not getattr(cls, "is_ai_session", True)
    ingest_ready = getattr(cls, "ingest_ready", True)
    extra: tuple[str, ...] = ()
    if not ingest_ready:
        extra = ("    (present on disk, not included in a default sync)",)
    elif is_notes:
        extra = ("    (notes/export intake — not agent chat history)",)
    _print_adapter_facts(
        name, cls, config, path_found=path_found, extra_lines=extra
    )
    default_yes = bool(path_found and ingest_ready)
    enable = ask_choice(
        "    Enable for sync? [Y/n]: " if default_yes else "    Enable for sync? [y/N]: ",
        ("y", "yes", "n", "no"),
        "y" if default_yes else "n",
    )
    if enable not in ("y", "yes"):
        if path_found:
            return {"enabled": False}
        return None

    block: dict[str, Any] = {"enabled": True}
    path_key = _PATH_KEYS.get(name)
    entered_path = _prompt_path(
        name, cls, config, path_found=path_found, ask_until=ask_until
    )
    if path_key and not path_found and not entered_path:
        return None
    if path_key and entered_path:
        block[path_key] = [entered_path]

    override = ask_until(
        f"    Start date [Enter = use shared {shared_since} · or YYYY-MM-DD]: ",
        _INHERIT_SINCE,
        _resolve_since_date,
    )
    if override is not _INHERIT_SINCE:
        block["since"] = override
    return block


def _prompt_shared_since(
    config: dict[str, Any],
    *,
    ask_until: Callable[..., Any],
) -> str:
    """Shared lookback: Enter = today−30 (or keep stored); else typed date."""
    suggested = suggested_since_today_minus_30()
    filters = config.get("filters") if isinstance(config.get("filters"), dict) else {}
    current = str((filters or {}).get("since") or "").strip()
    print()
    print("── Shared sync lookback ──")
    if current:
        print(f"  Stored: {current}")
        print(f"  Suggested default (today−30): {suggested}")
        default = current
        prompt = "  Enter = keep stored · or type YYYY-MM-DD: "
    else:
        print(f"  Default: {suggested} (today−30)")
        default = suggested
        prompt = "  Enter = use this default · or type YYYY-MM-DD: "
    return ask_until(prompt, default, _resolve_since_date)


def run_configure_sources(
    *,
    yes: bool = False,
    ask_choice: Callable[..., str] | None = None,
    ask_until: Callable[..., Any] | None = None,
) -> int:
    """Probe stores and optionally write ``adapters.*`` / ``filters.since`` to ``config.json``."""
    if yes or not sys.stdin.isatty():
        print("configure-sources: skipped (non-interactive). Run in a terminal to interview.")
        return 0

    if ask_choice is None or ask_until is None:
        from llmwiki.cli import _ask_choice, _ask_until  # noqa: PLC0415

        ask_choice = ask_choice or _ask_choice
        ask_until = ask_until or _ask_until

    discover_all()
    config = _load_quiz_config()
    updates: dict[str, dict[str, Any]] = {}

    print("llmwiki configure-sources")
    print("  Detecting session stores on disk…")

    filters_since = _prompt_shared_since(config, ask_until=ask_until)

    for name in sorted(REGISTRY):
        cls = REGISTRY[name]
        block = _prompt_adapter(
            name,
            cls,
            config,
            shared_since=filters_since,
            ask_choice=ask_choice,
            ask_until=ask_until,
        )
        if block is not None:
            updates[name] = block

    clear_adapter_since = frozenset(
        n for n, b in updates.items() if b.get("enabled") and "since" not in b
    )

    print()
    print("  Will write:")
    print(f"    filters.since: {filters_since}")
    for name, block in sorted(updates.items()):
        shown = dict(block)
        shown_note = ""
        if name in clear_adapter_since:
            shown.pop("since", None)
            shown_note = " (inherit shared lookback)"
        print(f"    adapters.{name}: {shown}{shown_note}")
    answer = ask_choice("  Save to config.json? [Y/n]: ", ("y", "yes", "n", "no"), "y")
    if answer not in ("y", "yes"):
        print("  Aborted — no changes written.")
        return 0
    _merge_write_config(
        updates,
        filters_since=filters_since,
        clear_adapter_since=clear_adapter_since,
    )
    config = _load_quiz_config()
    print()
    print("  Active sources after save:")
    print()
    print_adapters_table(config)
    return 0
