"""Adapter status computation — pulled out of cli.py (#arch-h8 / #611).

Pre-#611 the ``configured``/``will_fire`` label computation lived as a
private ``_adapter_status`` helper inside ``cli.py``. The CLI's job is
to parse argv and print things — deciding whether an adapter is on /
off / auto belongs in the adapters package next to the adapters
themselves.

The function is re-exported from ``llmwiki.cli`` so the existing
``from llmwiki.cli import _adapter_status`` import path keeps working
for any downstream caller that reached for it.

#192 R9: the roster shows a single **enabled** yes/no column (whether
bare ``sync`` will select the adapter). No separate ``active`` column
and no ``auto`` / ``explicit`` / ``off`` labels in the table.
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
) -> str:
    """Return ``yes`` if bare ``sync`` will select this adapter, else ``no``.

    ``selected_names`` (when passed) is the set already computed by
    ``select_sync_adapters`` so the table stays consistent with the next
    bare sync without re-running selection per row.
    """
    if selected_names is not None:
        return "yes" if name in selected_names else "no"
    if name in REGISTRY:
        selected = {c.name for c in select_sync_adapters(config, None)}
        return "yes" if name in selected else "no"

    # Unit-test shims not registered in REGISTRY.
    available = bool(adapter_cls.is_available())
    if not available:
        return "no"
    adapter_cfg = adapter_block(config, name)
    enabled_in_cfg = None
    if isinstance(adapter_cfg, dict):
        enabled_in_cfg = adapter_cfg.get("enabled", None)
    if enabled_in_cfg is False:
        return "no"
    is_ai = getattr(adapter_cls, "is_ai_session", True)
    if enabled_in_cfg is True or is_ai:
        return "yes"
    return "no"


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
        desc_width = max(30, term_cols - 48)

    print("Registered adapters:")
    dash = "-"
    header = f"  {'name':<16}  {'present':<8}  {'enabled':<8}  description"
    print(header)
    sep_desc = "-" * (desc_width if desc_width is not None else len("description"))
    print(f"  {dash * 16}  {dash * 8}  {dash * 8}  {sep_desc}")
    for name, adapter_cls in sorted(REGISTRY.items()):
        present = "yes" if adapter_store_present(adapter_cls, config) else "no"
        enabled = adapter_status(
            name, adapter_cls, config, selected_names=selected_names
        )
        desc = adapter_cls.description()
        if desc_width is not None and len(desc) > desc_width:
            desc = desc[: max(desc_width - 3, 1)] + "..."
        print(f"  {name:<16}  {present:<8}  {enabled:<8}  {desc}")

    print()
    print("Columns:")
    print("  present  — is the adapter's session store visible on disk?")
    print(
        "  enabled  — yes/no — will the next bare `sync` include this source?"
        " (`configure-sources` sets this; use `sync --adapter <name>` for a one-off)"
    )
    if not wide:
        print()
        print("Pass --wide to see untruncated descriptions.")
