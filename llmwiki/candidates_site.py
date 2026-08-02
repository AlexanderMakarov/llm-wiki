"""Static candidates review page + JSON payload helpers (#97).

Build emits ``site/candidates.html``. Under ``llmwiki serve``, action buttons POST to ``/api/candidates`` which calls the same library paths as ``llmwiki candidates …``.
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any

from llmwiki.candidates import Candidate, candidate_review_summary, list_candidates

_HEADING_RE = re.compile(r"^#+\s+.*$", re.MULTILINE)


def candidate_description(cand: Candidate) -> str:
    """Short prose for the Description column — enough to decide without opening the file."""
    preview = (cand.get("body_preview") or "").strip()
    preview = _HEADING_RE.sub("", preview).strip()
    preview = re.sub(r"\n{2,}", " ", preview)
    preview = re.sub(r"\s+", " ", preview).strip()
    if not preview:
        return "(no description yet — see evidence under ## Connections)"
    if len(preview) > 160:
        return preview[:157].rstrip() + "…"
    return preview


def candidates_payload(wiki_dir: Path) -> dict[str, Any]:
    """JSON-serialisable list + summary for the review page / API responses."""
    items = list_candidates(wiki_dir)
    rows = []
    for c in items:
        rows.append({
            "slug": c["slug"],
            "kind": c["kind"],
            "title": c["title"],
            "age_days": c["age_days"],
            "created": c["created"],
            "description": candidate_description(c),
        })
    return {
        "candidates": rows,
        "summary": candidate_review_summary(wiki_dir),
    }


def _table_rows_html(rows: list[dict[str, Any]], kind: str) -> str:
    peers = [r["slug"] for r in rows if r["kind"] == kind]
    kind_rows = [r for r in rows if r["kind"] == kind]
    if not kind_rows:
        return (
            f'<tr><td colspan="3" class="muted">No pending {html.escape(kind)} '
            "candidates.</td></tr>"
        )
    out: list[str] = []
    for r in kind_rows:
        merge_opts = ['<option value="">Merge with…</option>']
        for peer in peers:
            if peer == r["slug"]:
                continue
            merge_opts.append(
                f'<option value="{html.escape(peer)}">{html.escape(peer)}</option>'
            )
        merge_select = (
            f'<select class="cand-merge" data-slug="{html.escape(r["slug"])}" '
            f'data-kind="{html.escape(kind)}" aria-label="Merge {html.escape(r["slug"])} with">'
            + "".join(merge_opts)
            + "</select>"
        )
        actions = (
            f'<button type="button" class="cand-action" data-action="promote" '
            f'data-slug="{html.escape(r["slug"])}" data-kind="{html.escape(kind)}">Promote</button> '
            f'<button type="button" class="cand-action" data-action="flip-promote" '
            f'data-slug="{html.escape(r["slug"])}" data-kind="{html.escape(kind)}">Flip and promote</button> '
            f'<button type="button" class="cand-action" data-action="discard" '
            f'data-slug="{html.escape(r["slug"])}" data-kind="{html.escape(kind)}">Discard</button> '
            f"{merge_select}"
        )
        age = f'{r["age_days"]}d' if r.get("created") else "—"
        out.append(
            "<tr>"
            f'<td><strong>{html.escape(r["title"])}</strong>'
            f'<div class="muted"><code>{html.escape(r["slug"])}</code> · {html.escape(age)}</div></td>'
            f'<td>{html.escape(r["description"])}</td>'
            f'<td class="cand-actions">{actions}</td>'
            "</tr>"
        )
    return "\n".join(out)


def render_candidates_body(wiki_dir: Path | None) -> str:
    """Inner HTML for ``candidates.html`` (tables + status + inline script)."""
    if wiki_dir and wiki_dir.is_dir():
        payload = candidates_payload(wiki_dir)
    else:
        payload = {"candidates": [], "summary": {"to_review": 0}}
    rows = payload["candidates"]
    n = int(payload["summary"].get("to_review") or 0)
    entities = _table_rows_html(rows, "entities")
    concepts = _table_rows_html(rows, "concepts")
    payload_json = json.dumps(payload, ensure_ascii=False)
    return f"""<section class="section">
  <div class="container">
    <p class="muted" id="cand-status">{n} pending candidate(s). Actions require <code>llmwiki serve</code> (not <code>file://</code>). After a successful action the tables reload; run <code>llmwiki build</code> when you want a cold-open Home/Analytics recount.</p>
    <p id="cand-error" class="error-banner" hidden role="alert"></p>
    <h2>Entities (pending)</h2>
    <div class="state-table-wrap" tabindex="0" role="region" aria-label="Pending entity candidates">
      <table class="state-pipeline-table cand-review-table" id="cand-table-entities">
        <thead><tr><th>Name</th><th>Description</th><th>Actions</th></tr></thead>
        <tbody>{entities}</tbody>
      </table>
    </div>
    <h2>Concepts (pending)</h2>
    <div class="state-table-wrap" tabindex="0" role="region" aria-label="Pending concept candidates">
      <table class="state-pipeline-table cand-review-table" id="cand-table-concepts">
        <thead><tr><th>Name</th><th>Description</th><th>Actions</th></tr></thead>
        <tbody>{concepts}</tbody>
      </table>
    </div>
  </div>
</section>
<script>
window.LLMWIKI_CANDIDATES = {payload_json};
(function () {{
  var errEl = document.getElementById("cand-error");
  function showError(msg) {{
    if (!errEl) return;
    errEl.hidden = !msg;
    errEl.textContent = msg || "";
  }}
  function fileMode() {{
    return location.protocol === "file:";
  }}
  async function postAction(body) {{
    showError("");
    if (fileMode()) {{
      showError("Open this page via llmwiki serve to run review actions.");
      return null;
    }}
    var res = await fetch("/api/candidates", {{
      method: "POST",
      headers: {{ "Content-Type": "application/json" }},
      body: JSON.stringify(body),
    }});
    var data = null;
    try {{ data = await res.json(); }} catch (e) {{ data = null; }}
    if (!res.ok) {{
      showError((data && data.error) || ("Request failed (" + res.status + ")"));
      return null;
    }}
    return data;
  }}
  document.addEventListener("click", function (ev) {{
    var btn = ev.target.closest && ev.target.closest(".cand-action");
    if (!btn) return;
    var action = btn.getAttribute("data-action");
    var slug = btn.getAttribute("data-slug");
    var kind = btn.getAttribute("data-kind");
    if (!action || !slug) return;
    btn.disabled = true;
    postAction({{ action: action, slug: slug, kind: kind }}).then(function (data) {{
      btn.disabled = false;
      if (data) location.reload();
    }});
  }});
  document.addEventListener("change", function (ev) {{
    var sel = ev.target.closest && ev.target.closest("select.cand-merge");
    if (!sel || !sel.value) return;
    var slug = sel.getAttribute("data-slug");
    var kind = sel.getAttribute("data-kind");
    var into = sel.value;
    sel.disabled = true;
    postAction({{ action: "merge", slug: slug, kind: kind, into: into }}).then(function (data) {{
      sel.disabled = false;
      sel.value = "";
      if (data) location.reload();
    }});
  }});
}})();
</script>
"""
