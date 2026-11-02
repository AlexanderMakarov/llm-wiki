"""Shared **i** hint registry for Home pipeline table + metrics cards (#321).

Hint bodies are rendered once in Python; the static viewer reads
``window.LLMWIKI_UI_HINTS`` and shows them in ``#llmwiki-floating-hint-panel``.
"""
from __future__ import annotations

import html
import json

# Keys match ``data-hint-key`` on ``llmwiki-hint-trigger`` buttons.
UI_HINTS: dict[str, str] = {
    "state-table-overview": (
        "Knowledge from agent sessions or raw docs moves left to right through the columns: "
        "<strong>sync</strong> copies new sessions or docs into <code>raw/</code> "
        "(<strong>Raw</strong>); eligible items wait to become "
        "<code>wiki/sources/</code> pages (<strong>To synthesize</strong>, USD when estimated); "
        "<strong>synth</strong> writes summaries (<strong>Synthesized</strong>). "
        "<strong>Queryable</strong> is how many source markdown files exist on disk "
        "(what <strong>search</strong> in CLI and MCP read). "
        "<strong>build</strong> compiles the static <code>site/</code> "
        "(<strong>In site</strong>). "
        "Note that extra rows such as <strong>Other</strong> or <strong>Stubs</strong> appear only when "
        "the estimate scan finds pages that do not fit the agent/doc pipeline columns."
    ),
    "state-col-raw": "Sessions/docs eligible in <code>raw/</code> after sync filters.",
    "state-col-pending": (
        "Backlog not yet written to <code>wiki/sources/</code>; "
        "USD in parentheses when estimated."
    ),
    "state-col-synth": (
        "Eligible sources already summarized into <code>wiki/sources/</code>."
    ),
    "state-col-queryable": (
        "Queryable markdown files. Agent rows and <strong>Documents</strong> follow the "
        "<strong>synth estimate</strong> scan."
    ),
    "state-col-insite": (
        "Static HTML from the last <code>llmwiki build</code> attributed to this row "
        "(source pages you can open under <code>site/</code>). "
        "<strong>Total</strong> footer <strong>In site</strong> counts every "
        "<code>*.html</code> file under <code>site/</code> (index, entities, sessions, etc.)."
    ),
    "state-row-stubs": (
        "Optional estimate row <strong>Stubs</strong> (shown only when count &gt; 0): "
        "<code>wiki/sources/</code> pages whose body is machine-generated filler (#24). "
        "Pipeline columns Raw / To synthesize / Synthesized stay blank."
    ),
    "state-row-other": (
        "Counts <code>wiki/sources/</code> pages the scan does not assign to any agent session row or "
        "<strong>Documents</strong>, e.g. missing or non-standard "
        "<code>source_file</code>, hand-edited pages, legacy imports. "
        "Those pages can still be searchable — they are omitted from the agent/doc pipeline counts."
    ),
    "state-insite-na": (
        "This row has no per-row static HTML attribution in the estimate "
        "(orphan bucket pages are not broken out in the site roll-up). "
        "<strong>Total</strong> footer <strong>In site</strong> still shows the full "
        "<code>site/</code> size after the last build."
    ),
    "metric-payoff": (
        "How often agents requested wiki pages via MCP "
        "(<code>wiki_search</code> / <code>wiki_read_page</code> retrievals) "
        "divided by the number of wiki pages on disk."
    ),
    "metric-knowledge": (
        "<strong>Candidates</strong> — pending stubs under "
        "<code>wiki/candidates/</code>. "
        "<strong>Entities</strong> / <strong>Concepts</strong> — pages after promote. "
        "Review/promote on <strong>Candidates</strong> tab, agent "
        "<code>/wiki-candidates</code>, or "
        "<code>llmwiki candidates apply|promote|merge|discard</code>."
    ),
    "metric-weekly-pace": (
        "Rolling average over the last 7 days: "
        "<strong>s/day</strong> is sessions per day from raw session dates; "
        "<strong>t/day</strong> is tokens per day from measured usage in "
        "<code>usage/session-tokens.json</code> (daily sums ÷ 7); "
        "<strong>t/s</strong> = total tokens in the window ÷ total sessions in the window."
    ),
}


def render_metric_knowledge_hint_body(*, stale: int = 0, stale_days: int = 30) -> str:
    """Knowledge card hint including stale candidate count."""
    base = UI_HINTS["metric-knowledge"]
    stale_n = int(stale)
    if stale_n <= 0:
        return base
    word = "candidate" if stale_n == 1 else "candidates"
    stale_line = (
        f"<br><br>Currently there are {stale_n} stale {word} "
        f"(age ≥ {int(stale_days)} days; "
        f"<code>llmwiki candidates list --stale</code>)."
    )
    return base + stale_line


def render_ui_hint_button(
    key: str,
    aria_label: str,
    *,
    body_html: str | None = None,
) -> str:
    """Return an **i** button wired to the global floating hint panel."""
    attrs = (
        f'data-hint-key="{html.escape(key)}" '
        f'aria-label="{html.escape(aria_label)}" '
        'aria-expanded="false" aria-describedby="llmwiki-floating-hint-panel"'
    )
    if body_html is not None:
        attrs += f' data-hint-html="{html.escape(body_html, quote=True)}"'
    return (
        f' <button type="button" class="token-coverage-btn llmwiki-hint-trigger" '
        f"{attrs}>i</button>"
    )


def render_ui_hints_script() -> str:
    """Inline script defining ``window.LLMWIKI_UI_HINTS`` for ``script.js``."""
    payload = json.dumps(UI_HINTS, ensure_ascii=False)
    payload = payload.replace("</", "<\\/")
    return f"<script>window.LLMWIKI_UI_HINTS={payload};</script>"


def render_floating_hint_portal() -> str:
    """Single floating tooltip host (included in every page foot)."""
    return (
        '<div id="llmwiki-floating-hint" class="llmwiki-floating-hint" hidden>'
        '<div id="llmwiki-floating-hint-panel" '
        'class="llmwiki-floating-hint-panel" role="tooltip"></div>'
        "</div>"
    )
