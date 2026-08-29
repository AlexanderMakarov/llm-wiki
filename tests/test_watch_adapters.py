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
from llmwiki.adapters.settings import select_sync_adapters
from llmwiki.config_schedule import _load_sessions_config


def _sync_visible(config: dict | None = None) -> set[str]:
    discover_all()
    cfg = config if config is not None else _load_sessions_config()
    return {c.name for c in select_sync_adapters(cfg, None)}


def test_watch_registers_contrib_adapters():
    """scan_mtimes must leave every contrib adapter registered."""
    watch.scan_mtimes(None)

    assert "cursor_cli" in REGISTRY, (
        "watch did not load contrib adapters — Cursor sessions would be "
        "invisible to the watcher (regression: discover_adapters vs discover_all)"
    )



def test_watch_uses_same_adapter_selection_as_sync():
    """``scan_mtimes`` must not narrow to core-only adapters (#182)."""
    cfg = _load_sessions_config()
    sync_names = _sync_visible(cfg)
    watch.scan_mtimes(None, cfg)
    for name in sync_names:
        assert name in REGISTRY
        mtimes = watch.scan_mtimes([name], cfg)
        assert isinstance(mtimes, dict)


def test_scan_mtimes_honours_explicit_contrib_adapter_name():
    """``--adapter cursor_cli`` resolves now that contrib is registered."""
    mtimes = watch.scan_mtimes(["cursor_cli"])

    assert isinstance(mtimes, dict)
    assert "cursor_cli" in REGISTRY
