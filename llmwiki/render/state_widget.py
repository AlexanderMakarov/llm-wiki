"""Home pipeline State widget mount (table filled client-side).

Collapsible sections under the table share
``llmwiki.render.collapse_section`` chrome (CSS class ``collapse-section``);
this module only emits the Home-specific mount for the pipeline table +
JS-filled sections.
"""

from __future__ import annotations


def state_widget_mount(*, widget_id: str = "llmwiki-state-widget") -> str:
    """Return the empty mount HTML for the pipeline State widget."""
    return (
        f'<div id="{widget_id}" class="state-widget" data-llmwiki-state-widget>'
        '<p class="muted">Loading pipeline state…</p>'
        "</div>"
    )
