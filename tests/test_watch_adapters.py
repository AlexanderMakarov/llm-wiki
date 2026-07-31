"""`watch` must see the same session stores `sync` does.

Field report: `llmwiki watch` printed `adapters: claude_code` and never
reacted to a finished Cursor session. `watch` called `discover_adapters()`
(core only — Claude, Codex) while `sync` calls `discover_adapters()` +
`discover_contrib()`. Contrib stores were therefore never registered, so
`scan_mtimes` never enumerated them: a store watch cannot see is a store
watch can never trigger on.
"""

from __future__ import annotations

from llmwiki import watch
from llmwiki.adapters import REGISTRY, discover_all


def _available_after(discover) -> set[str]:
    discover()
    return {name for name, cls in REGISTRY.items() if cls.is_available()}


def test_watch_registers_contrib_adapters():
    """scan_mtimes must leave every contrib adapter registered."""
    watch.scan_mtimes(None)

    assert "cursor_cli" in REGISTRY, (
        "watch did not load contrib adapters — Cursor sessions would be "
        "invisible to the watcher (regression: discover_adapters vs discover_all)"
    )


def test_watch_sees_every_adapter_sync_sees():
    """No store is watchable by `sync` but invisible to `watch`."""
    watch.scan_mtimes(None)
    watch_visible = {name for name, cls in REGISTRY.items() if cls.is_available()}

    sync_visible = _available_after(discover_all)

    assert sync_visible <= watch_visible, (
        f"stores visible to sync but not watch: {sorted(sync_visible - watch_visible)}"
    )


def test_scan_mtimes_honours_explicit_contrib_adapter_name():
    """`--adapter cursor_cli` resolves now that contrib is registered."""
    mtimes = watch.scan_mtimes(["cursor_cli"])

    assert isinstance(mtimes, dict)
    assert "cursor_cli" in REGISTRY
