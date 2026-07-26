"""Shared collapsible section with a count badge in the summary.

Used on Home (pipeline backlog / timeline / commands) and Analytics
(Dead stock). The Home pipeline **table** stays separate
(``state_widget.py``); only this fold-out chrome is shared.
"""

from __future__ import annotations

import html


def collapse_section(
    title: str,
    count: int,
    body_html: str,
    *,
    open: bool = False,
    extra_class: str = "",
) -> str:
    """Return a ``<details>`` block with ``title`` + count badge + body.

    ``body_html`` is inserted as-is (caller is responsible for escaping
    any untrusted text inside it).
    """
    classes = "collapse-section"
    if extra_class:
        classes += f" {extra_class.strip()}"
    open_attr = " open" if open else ""
    return (
        f'<details class="{classes}"{open_attr}>'
        f"<summary>{html.escape(title)}"
        f'<span class="collapse-section-count">{int(count)}</span></summary>'
        f'<div class="collapse-section-body">{body_html}</div>'
        "</details>"
    )


def collapse_section_list(
    title: str,
    items_html: list[str],
    *,
    count: int | None = None,
    intro_html: str = "",
    empty_html: str = '<p class="muted">None.</p>',
    footer_html: str = "",
    list_class: str = "collapse-section-list",
    open: bool = False,
    extra_class: str = "",
) -> str:
    """Collapsible section whose body is an intro + ``<ul>`` of items.

    ``items_html`` entries are raw ``<li>…</li>`` fragments (already escaped).
    ``count`` defaults to ``len(items_html)`` — pass explicitly when the badge
    should reflect a larger total than the rendered sample.
    """
    n = int(count) if count is not None else len(items_html)
    if items_html:
        body = (
            (intro_html or "")
            + f'<ul class="{html.escape(list_class)}">'
            + "".join(items_html)
            + "</ul>"
            + (footer_html or "")
        )
    else:
        body = (intro_html or "") + empty_html + (footer_html or "")
    return collapse_section(
        title, n, body, open=open, extra_class=extra_class
    )


def collapse_sections_wrap(*sections: str) -> str:
    """Stack one or more ``collapse_section`` fragments vertically."""
    return '<div class="collapse-sections">' + "".join(sections) + "</div>"
