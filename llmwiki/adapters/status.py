"""Adapter status computation — pulled out of cli.py (#arch-h8 / #611).

Pre-#611 the ``configured``/``will_fire`` label computation lived as a
private ``_adapter_status`` helper inside ``cli.py``. The CLI's job is
to parse argv and print things — deciding whether an adapter is on /
off / auto belongs in the adapters package next to the adapters
themselves.

The function is re-exported from ``llmwiki.cli`` so the existing
``from llmwiki.cli import _adapter_status`` import path keeps working
for any downstream caller that reached for it.
"""

from __future__ import annotations

import shutil as _shutil
from typing import Any

from llmwiki.adapters import REGISTRY
from llmwiki.adapters.settings import adapter_block, adapter_store_present, select_sync_adapters


def adapter_status(
    name: str,
    adapter_cls: Any,
    config: dict,
    *,
    selected_names: set[str] | None = None,
) -> tuple[str, str]:
    """Return ``(configured, will_fire)`` labels for one adapter (G-01 · #287).

    * ``configured``: ``explicit`` (user set ``enabled: true`` in the
      config), ``off`` (user set ``enabled: false``), or ``auto``
      (default — no explicit toggle).
    * ``will_fire``: ``yes`` when the next ``sync`` will pick this
      adapter up (available **and** not explicitly off), ``no``
      otherwise.

    The old labels — ``-`` / ``enabled`` / ``disabled`` — read as
    "adapter can't see anything" even when the adapter was discovering
    471 files on the next line. The new labels say exactly what they
    mean without the user cross-referencing ``sessions_config.json``.
    """
    adapter_cfg = adapter_block(config, name)
    enabled_in_cfg = None
    if isinstance(adapter_cfg, dict):
        enabled_in_cfg = adapter_cfg.get("enabled", None)
    if enabled_in_cfg is True:
        configured = "explicit"
    elif enabled_in_cfg is False:
        configured = "off"
    else:
        configured = "auto"
    if selected_names is not None:
        will_fire = "yes" if name in selected_names else "no"
    elif name in REGISTRY:
        selected = {c.name for c in select_sync_adapters(config, None)}
        will_fire = "yes" if name in selected else "no"
    else:
        available = adapter_cls.is_available()
        is_ai = getattr(adapter_cls, "is_ai_session", True)
        if configured == "off":
            will_fire = "no"
        elif configured == "explicit":
            will_fire = "yes" if available else "no"
        else:
            will_fire = "yes" if (available and is_ai) else "no"
    return configured, will_fire


def print_adapters_table(
    config: dict,
    *,
    wide: bool = False,
    selected_names: set[str] | None = None,
) -> None:
    """Print the ``llmwiki adapters`` roster (shared with configure-sources)."""
    if selected_names is None:
        selected_names = {c.name for c in select_sync_adapters(config, None)}

    if wide:
        desc_width: int | None = None
    else:
        term_cols = _shutil.get_terminal_size(fallback=(80, 24)).columns
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
        present = "yes" if adapter_store_present(adapter_cls, config) else "no"
        enabled, active = adapter_status(
            name, adapter_cls, config, selected_names=selected_names
        )
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
