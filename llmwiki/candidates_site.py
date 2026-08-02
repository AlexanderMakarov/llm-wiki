"""Static candidates review page + JSON payload helpers (#97).

Build emits ``site/candidates.html``. Each row picks an intent (skip / promote /
flip-promote / discard / merge); **Apply** either POSTs a batch to
``/api/candidates`` under ``llmwiki serve``, or shows one pasteable
``llmwiki candidates apply --actions '…'`` command when the page is static /
``file://``.
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any

from llmwiki.candidates import (
    Candidate,
    KeyFactsBackendError,
    candidate_review_summary,
    discard,
    flip_and_promote,
    list_candidates,
    merge,
    promote,
)
from llmwiki.synth.base import BaseSynthesizer

_HEADING_RE = re.compile(r"^#+\s+.*$", re.MULTILINE)

_VALID_ACTIONS = frozenset({"promote", "flip-promote", "discard", "merge"})


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


def _shell_single_quote(s: str) -> str:
    """Quote ``s`` for POSIX shells (safe inside single quotes)."""
    return "'" + s.replace("'", "'\\''") + "'"


def cli_command_for_action(item: dict[str, Any]) -> str:
    """One shell line for a single review intent (legacy one-off CLI)."""
    action = str(item.get("action") or "").strip()
    slug = str(item.get("slug") or "").strip()
    kind = str(item.get("kind") or "").strip()
    into = str(item.get("into") or "").strip()
    reason = str(item.get("reason") or "").strip()
    if not action or not slug:
        raise ValueError("action and slug are required")
    if action not in _VALID_ACTIONS:
        raise ValueError(f"unknown action {action!r}")
    kind_flag = f" --kind {kind}" if kind else ""
    if action == "promote":
        return f"llmwiki candidates promote --slug {_shell_single_quote(slug)}{kind_flag}"
    if action == "flip-promote":
        return (
            f"llmwiki candidates flip-promote --slug {_shell_single_quote(slug)}"
            f"{kind_flag}"
        )
    if action == "discard":
        reason_flag = (
            f" --reason {_shell_single_quote(reason)}" if reason else ""
        )
        return (
            f"llmwiki candidates discard --slug {_shell_single_quote(slug)}"
            f"{kind_flag}{reason_flag}"
        )
    if not into:
        raise ValueError("merge requires into")
    return (
        f"llmwiki candidates merge --slug {_shell_single_quote(slug)}"
        f" --into {_shell_single_quote(into)}{kind_flag}"
    )


def cli_command_for_actions(actions: list[dict[str, Any]]) -> str:
    """One pasteable ``candidates apply --actions`` line for a batch.

    Matches ``POST /api/candidates`` JSON shape so static Apply and the served
    API stay aligned. Empty list raises.
    """
    if not actions:
        raise ValueError("actions must be non-empty")
    # Validate each item the same way one-offs are validated.
    for item in actions:
        if not isinstance(item, dict):
            raise ValueError("each action must be an object")
        action = str(item.get("action") or "").strip()
        slug = str(item.get("slug") or "").strip()
        if action not in _VALID_ACTIONS:
            raise ValueError(f"unknown action {action!r}")
        if not slug:
            raise ValueError("slug is required")
        if action == "merge" and not str(item.get("into") or "").strip():
            raise ValueError("merge requires into")
    payload = json.dumps(actions, ensure_ascii=False, separators=(",", ":"))
    return f"llmwiki candidates apply --actions {_shell_single_quote(payload)}"


def apply_candidate_actions(
    wiki_dir: Path,
    actions: list[dict[str, Any]],
    *,
    synthesizer: BaseSynthesizer | None = None,
) -> list[dict[str, Any]]:
    """Run a batch of review actions in order. Returns one result dict per item.

    Each result is ``{"ok": True, "slug": …, "action": …, "path": …}`` or
    ``{"ok": False, "slug": …, "action": …, "error": …}``. Processing continues
    after failures so one bad row does not hide the rest.
    """
    results: list[dict[str, Any]] = []
    for raw in actions:
        if not isinstance(raw, dict):
            results.append({
                "ok": False, "slug": "", "action": "",
                "error": "each action must be an object",
            })
            continue
        action = str(raw.get("action") or "").strip()
        slug = str(raw.get("slug") or "").strip()
        kind = raw.get("kind")
        kind_s = str(kind).strip() if kind else None
        into = str(raw.get("into") or "").strip()
        reason = str(raw.get("reason") or "").strip()
        entry: dict[str, Any] = {"ok": False, "slug": slug, "action": action}
        try:
            if action not in _VALID_ACTIONS:
                raise ValueError(f"unknown action {action!r}")
            if not slug:
                raise ValueError("slug is required")
            if action == "promote":
                path = promote(slug, wiki_dir, kind=kind_s, synthesizer=synthesizer)
            elif action == "flip-promote":
                path = flip_and_promote(
                    slug, wiki_dir, kind=kind_s, synthesizer=synthesizer,
                )
            elif action == "discard":
                path = discard(slug, wiki_dir, reason=reason, kind=kind_s)
            else:
                if not into:
                    raise ValueError("merge requires into")
                path = merge(slug, wiki_dir, into_slug=into, kind=kind_s)
            entry["ok"] = True
            entry["path"] = str(path)
        except (
            FileNotFoundError,
            FileExistsError,
            ValueError,
            KeyFactsBackendError,
            OSError,
        ) as exc:
            entry["error"] = str(exc)
        results.append(entry)
    return results


def _intent_controls_html(row: dict[str, Any], peers: list[str]) -> str:
    slug = html.escape(row["slug"])
    kind = html.escape(row["kind"])
    merge_opts = ['<option value="">Choose peer…</option>']
    for peer in peers:
        if peer == row["slug"]:
            continue
        merge_opts.append(
            f'<option value="{html.escape(peer)}">{html.escape(peer)}</option>'
        )
    return (
        f'<div class="cand-intent" data-slug="{slug}" data-kind="{kind}">'
        f'<label class="muted">Decision '
        f'<select class="cand-decision" aria-label="Decision for {slug}">'
        '<option value="">Skip</option>'
        '<option value="promote">Promote</option>'
        '<option value="flip-promote">Flip and promote</option>'
        '<option value="discard">Discard</option>'
        '<option value="merge">Merge with…</option>'
        "</select></label> "
        f'<label class="cand-merge-wrap muted" hidden>Into '
        f'<select class="cand-merge-into" aria-label="Merge {slug} into">'
        + "".join(merge_opts)
        + "</select></label>"
        "</div>"
    )


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
        age = f'{r["age_days"]}d' if r.get("created") else "—"
        out.append(
            "<tr>"
            f'<td><strong>{html.escape(r["title"])}</strong>'
            f'<div class="muted"><code>{html.escape(r["slug"])}</code> · {html.escape(age)}</div></td>'
            f'<td>{html.escape(r["description"])}</td>'
            f'<td class="cand-actions">{_intent_controls_html(r, peers)}</td>'
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
    <p class="muted" id="cand-status">{n} pending candidate(s). Set a decision per row, then <strong>Apply</strong>. Under <code>llmwiki serve</code> Apply runs a batch API; on a static / <code>file://</code> open it shows one pasteable <code>llmwiki candidates apply --actions</code> command. Run <code>llmwiki build</code> after Apply when you want a cold-open Home/Analytics recount.</p>
    <p id="cand-mode" class="muted" hidden></p>
    <p id="cand-error" class="error-banner" hidden role="alert"></p>
    <h2>Entities (pending)</h2>
    <div class="state-table-wrap" tabindex="0" role="region" aria-label="Pending entity candidates">
      <table class="state-pipeline-table cand-review-table" id="cand-table-entities">
        <thead><tr><th>Name</th><th>Description</th><th>Decision</th></tr></thead>
        <tbody>{entities}</tbody>
      </table>
    </div>
    <h2>Concepts (pending)</h2>
    <div class="state-table-wrap" tabindex="0" role="region" aria-label="Pending concept candidates">
      <table class="state-pipeline-table cand-review-table" id="cand-table-concepts">
        <thead><tr><th>Name</th><th>Description</th><th>Decision</th></tr></thead>
        <tbody>{concepts}</tbody>
      </table>
    </div>
    <div class="cand-apply-bar">
      <button type="button" id="cand-apply" class="cand-apply-btn">Apply</button>
      <button type="button" id="cand-copy-cli" class="cand-apply-btn" hidden>Copy CLI</button>
    </div>
    <pre id="cand-cli" class="cand-cli" hidden></pre>
  </div>
</section>
<script>
window.LLMWIKI_CANDIDATES = {payload_json};
(function () {{
  var errEl = document.getElementById("cand-error");
  var modeEl = document.getElementById("cand-mode");
  var cliEl = document.getElementById("cand-cli");
  var applyBtn = document.getElementById("cand-apply");
  var copyBtn = document.getElementById("cand-copy-cli");
  var apiAvailable = false;

  function showError(msg) {{
    if (!errEl) return;
    errEl.hidden = !msg;
    errEl.textContent = msg || "";
  }}
  function setMode(text) {{
    if (!modeEl) return;
    modeEl.hidden = !text;
    modeEl.textContent = text || "";
  }}
  function fileMode() {{
    return location.protocol === "file:";
  }}
  function shellSingleQuote(s) {{
    return "'" + String(s).replace(/'/g, "'\\\\''") + "'";
  }}
  function collectActions() {{
    var actions = [];
    document.querySelectorAll(".cand-intent").forEach(function (wrap) {{
      var decision = wrap.querySelector(".cand-decision");
      var action = decision && decision.value;
      if (!action) return;
      var item = {{
        action: action,
        slug: wrap.getAttribute("data-slug"),
        kind: wrap.getAttribute("data-kind"),
      }};
      if (action === "merge") {{
        var intoSel = wrap.querySelector(".cand-merge-into");
        var into = intoSel && intoSel.value;
        if (!into) {{
          throw new Error("Choose a merge peer for " + item.slug);
        }}
        item.into = into;
      }}
      actions.push(item);
    }});
    return actions;
  }}
  function cliForBatch(actions) {{
    var payload = JSON.stringify(actions);
    return "llmwiki candidates apply --actions " + shellSingleQuote(payload);
  }}
  function showCli(actions) {{
    cliEl.hidden = false;
    cliEl.textContent = cliForBatch(actions);
    copyBtn.hidden = false;
    setMode("Static mode — paste this one command in a terminal (or Copy CLI), then llmwiki build.");
  }}
  async function probeApi() {{
    if (fileMode()) {{
      apiAvailable = false;
      setMode("Static / file open — Apply will show CLI commands to run locally.");
      return;
    }}
    try {{
      var res = await fetch("/api/candidates", {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify({{ actions: [] }}),
      }});
      apiAvailable = res.status !== 404 && res.status !== 405;
    }} catch (e) {{
      apiAvailable = false;
    }}
    if (apiAvailable) {{
      setMode("Served mode — Apply runs a batch on this vault via POST /api/candidates.");
    }} else {{
      setMode("No candidates API on this host — Apply will show CLI commands instead.");
    }}
  }}
  document.addEventListener("change", function (ev) {{
    var decision = ev.target.closest && ev.target.closest(".cand-decision");
    if (!decision) return;
    var wrap = decision.closest(".cand-intent");
    var mergeWrap = wrap && wrap.querySelector(".cand-merge-wrap");
    if (mergeWrap) mergeWrap.hidden = decision.value !== "merge";
  }});
  copyBtn.addEventListener("click", function () {{
    var text = cliEl.textContent || "";
    if (!text) return;
    if (navigator.clipboard && navigator.clipboard.writeText) {{
      navigator.clipboard.writeText(text).then(function () {{
        copyBtn.textContent = "Copied";
        setTimeout(function () {{ copyBtn.textContent = "Copy CLI"; }}, 1500);
      }}).catch(function () {{
        showError("Could not copy — select the commands below and copy manually.");
      }});
    }} else {{
      showError("Clipboard unavailable — select the commands below and copy manually.");
    }}
  }});
  applyBtn.addEventListener("click", async function () {{
    showError("");
    var actions;
    try {{
      actions = collectActions();
    }} catch (e) {{
      showError(e.message || String(e));
      return;
    }}
    if (!actions.length) {{
      showError("Set at least one decision before Apply.");
      return;
    }}
    if (!apiAvailable) {{
      showCli(actions);
      return;
    }}
    applyBtn.disabled = true;
    try {{
      var res = await fetch("/api/candidates", {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify({{ actions: actions }}),
      }});
      var data = null;
      try {{ data = await res.json(); }} catch (e) {{ data = null; }}
      if (res.status === 404 || res.status === 405) {{
        apiAvailable = false;
        showCli(actions);
        return;
      }}
      if (!res.ok) {{
        showError((data && data.error) || ("Request failed (" + res.status + ")"));
        return;
      }}
      var failed = (data && data.results || []).filter(function (r) {{ return !r.ok; }});
      if (failed.length) {{
        showError(failed.map(function (r) {{
          return (r.slug || "?") + ": " + (r.error || "failed");
        }}).join(" · "));
        return;
      }}
      location.reload();
    }} catch (e) {{
      apiAvailable = false;
      showCli(actions);
    }} finally {{
      applyBtn.disabled = false;
    }}
  }});
  probeApi();
}})();
</script>
"""
