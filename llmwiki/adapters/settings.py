"""Adapter config resolution and sync selection (#182).

Single place for ``adapters.<name>`` vs legacy top-level blocks, enable
flags, and which adapter classes bare ``sync`` / ``watch`` should load.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from llmwiki.adapters import REGISTRY, discover_all, resolve_adapter_name

# Legacy kebab-case keys still seen in user configs.
_ADAPTER_KEY_ALIASES: dict[str, tuple[str, ...]] = {
    "copilot_chat": ("copilot-chat",),
}


def adapter_block(config: dict[str, Any] | None, name: str) -> dict[str, Any]:
    """Merged settings for one adapter.

    Precedence (later wins): legacy top-level ``<name>`` → ``adapters.<name>``
    → kebab alias under ``adapters`` when applicable.
    """
    if not isinstance(config, dict):
        return {}
    merged: dict[str, Any] = {}
    top = config.get(name)
    if isinstance(top, dict):
        merged.update(top)
    adapters = config.get("adapters")
    if isinstance(adapters, dict):
        section = adapters.get(name)
        if isinstance(section, dict):
            merged.update(section)
        for alias in _ADAPTER_KEY_ALIASES.get(name, ()):
            alt = adapters.get(alias)
            if isinstance(alt, dict):
                for key, value in alt.items():
                    merged.setdefault(key, value)
    return merged


def adapter_enabled_flag(config: dict[str, Any] | None, name: str) -> bool | None:
    """Return explicit enablement: ``True``, ``False``, or ``None`` (auto)."""
    block = adapter_block(config, name)
    enabled = block.get("enabled", None)
    if enabled is True:
        return True
    if enabled is False:
        return False
    return None


def _adapter_instance(adapter_cls: type, config: dict[str, Any] | None):
    try:
        return adapter_cls(config or {})
    except Exception:
        return None


def _normalized_store_paths(inst: Any) -> list[Path]:
    paths = inst.session_store_path
    if isinstance(paths, Path):
        paths = [paths]
    return [Path(p).expanduser() for p in paths]


def adapter_store_present(adapter_cls: type, config: dict[str, Any] | None) -> bool:
    """Whether the adapter's store path exists on disk (``present`` column).

  Independent of enablement — R3 treats ``present`` as disk visibility only.
    """
    inst = _adapter_instance(adapter_cls, config)
    if inst is None:
        return False
    if adapter_cls.name == "chatgpt":
        return any(
            (p / "conversations.json").is_file() for p in _normalized_store_paths(inst)
        )
    return any(p.exists() for p in _normalized_store_paths(inst))


def adapter_is_available(adapter_cls: type, config: dict[str, Any] | None) -> bool:
    """Whether sync/watch can use this adapter (store ready to read)."""
    inst = _adapter_instance(adapter_cls, config)
    if inst is None:
        return False
    checker = getattr(inst, "is_available_with_config", None)
    if callable(checker):
        return bool(checker())
    return adapter_store_present(adapter_cls, config)


def select_sync_adapters(
    config: dict[str, Any] | None,
    explicit: list[str] | None = None,
) -> list[type]:
    """Return adapter classes to run for sync or watch.

    Parameters
    ----------
    config
        Merged sessions config (``examples/sessions_config.json`` + ``config.json``).
    explicit
        When set (``--adapter``), load only these names; skip enablement filter.
    """
    discover_all()
    if explicit:
        selected: list[type] = []
        for name in explicit:
            canonical = resolve_adapter_name(name)
            if canonical is None:
                raise ValueError(f"unknown adapter {name!r}")
            selected.append(REGISTRY[canonical])
        return selected

    selected = []
    for name, cls in sorted(REGISTRY.items()):
        if not getattr(cls, "ingest_ready", True):
            continue
        if not adapter_is_available(cls, config):
            continue
        enabled = adapter_enabled_flag(config, name)
        if enabled is False:
            continue
        is_ai = getattr(cls, "is_ai_session", True)
        if is_ai or enabled is True:
            selected.append(cls)
    return selected
