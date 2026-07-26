"""Reusable Home/Raw pipeline State widget mount.

The interactive table + collapsible sections are filled client-side from
``window.LLMWIKI_STATE_SNAPSHOT`` (see ``render/js.py``). This module only
emits the mount point so other pages can embed the same widget later.
"""

from __future__ import annotations


def state_widget_mount(*, widget_id: str = "llmwiki-state-widget") -> str:
    """Return the empty mount HTML for the pipeline State widget."""
    return (
        f'<div id="{widget_id}" class="state-widget" data-llmwiki-state-widget>'
        '<p class="muted">Loading pipeline state…</p>'
        "</div>"
    )
