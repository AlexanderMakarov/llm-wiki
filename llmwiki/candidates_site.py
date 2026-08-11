"""Static candidates review page + JSON payload helpers (#97).

Build emits ``site/candidates.html`` — a read-only listing of everything
pending under ``wiki/candidates/``. Reviewing happens on the command line:
the page prints the exact ``llmwiki candidates apply --vault … --actions -``
line to run and a ready-made JSON batch covering the listed candidates, so a
reviewer edits the actions and pipes the batch straight in.
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


def cli_command_for_actions(
    actions: list[dict[str, Any]], *, vault: str | None = None,
) -> str:
    """One pasteable ``candidates apply --actions`` line for a batch.

    ``vault`` names the knowledge base the batch applies to; omit it only
    when the caller has already selected one another way. Empty list raises.
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
    vault_flag = f" --vault {_shell_single_quote(vault)}" if vault else ""
    return f"llmwiki candidates apply{vault_flag} --actions {_shell_single_quote(payload)}"


def vault_display_path(wiki_dir: Path | None) -> str:
    """The ``--vault`` value to print for the knowledge base holding ``wiki_dir``.

    Relative to the current directory when the vault sits under it — that is
    the form the operator typed (``--vault demo``) and it is identical on
    every machine — and absolute otherwise.
    """
    if wiki_dir is None:
        return "."
    root = wiki_dir.parent
    try:
        rel = root.resolve().relative_to(Path.cwd().resolve())
    except (ValueError, OSError):
        return str(root)
    return str(rel) if str(rel) != "." else "."


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


def _table_rows_html(rows: list[dict[str, Any]], kind: str) -> str:
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
            f'<td><strong>{html.escape(r["title"])}</strong></td>'
            f'<td><code>{html.escape(r["slug"])}</code></td>'
            f'<td>{html.escape(r["description"])}</td>'
            f'<td>{html.escape(age)}</td>'
            "</tr>"
        )
    return "\n".join(out)


def actions_template(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """A ``--actions`` batch covering every listed candidate, all set to promote.

    The reviewer changes each ``action`` (or deletes the entry to skip that
    candidate) before piping the batch into ``candidates apply``.
    """
    return [
        {"action": "promote", "slug": r["slug"], "kind": r["kind"]}
        for r in rows
    ]


_COPY_SCRIPT = """<script>
(function () {
  var errEl = document.getElementById("cand-error");
  function showError(msg) {
    if (!errEl) return;
    errEl.hidden = !msg;
    errEl.textContent = msg || "";
  }
  function copyFrom(btn) {
    var src = document.getElementById(btn.getAttribute("data-copy-target"));
    var text = src ? (src.textContent || "") : "";
    if (!text) {
      showError("Nothing to copy on this page.");
      return;
    }
    if (!navigator.clipboard || !navigator.clipboard.writeText) {
      showError("Clipboard unavailable — select the text below and copy manually.");
      return;
    }
    var label = btn.textContent;
    navigator.clipboard.writeText(text).then(function () {
      showError("");
      btn.textContent = "Copied";
      setTimeout(function () { btn.textContent = label; }, 1500);
    }).catch(function (e) {
      showError("Could not copy — select the text below and copy manually.");
      if (window.__llmwikiReportError) window.__llmwikiReportError("Candidates copy failed", e);
    });
  }
  document.querySelectorAll("[data-copy-target]").forEach(function (btn) {
    btn.addEventListener("click", function () { copyFrom(btn); });
  });
})();
</script>
"""


def _apply_block_html(rows: list[dict[str, Any]], vault: str) -> str:
    """The command + ready-made JSON batch a reviewer copies into a terminal."""
    if not rows:
        return (
            '<p class="muted">Nothing pending. New stubs appear here after '
            "<code>llmwiki synth</code> harvests them.</p>"
        )
    command = (
        f"llmwiki candidates apply --vault {_shell_single_quote(vault)} --actions -"
    )
    batch = json.dumps(actions_template(rows), ensure_ascii=False, indent=2)
    return f"""<h2>Apply your decisions</h2>
    <p>Run this in a terminal and paste the batch below into it:</p>
    <div class="cand-apply-bar">
      <button type="button" class="cand-apply-btn" data-copy-target="cand-command">Copy command</button>
      <button type="button" class="cand-apply-btn" data-copy-target="cand-actions">Copy JSON</button>
    </div>
    <pre class="cand-cli" id="cand-command">{html.escape(command)}</pre>
    <pre class="cand-cli" id="cand-actions">{html.escape(batch)}</pre>
    <p class="muted">Every entry starts as <code>promote</code>. Change <code>action</code> to
      <code>flip-promote</code>, <code>discard</code> (optional <code>"reason"</code>) or
      <code>merge</code> (add <code>"into": "&lt;slug&gt;"</code>), or delete an entry to leave that
      candidate pending. Then run <code>llmwiki build --vault {html.escape(vault)}</code> to refresh
      these counts.</p>"""


def render_candidates_body(wiki_dir: Path | None) -> str:
    """Inner HTML for ``candidates.html`` — pending tables + the CLI batch."""
    if wiki_dir and wiki_dir.is_dir():
        payload = candidates_payload(wiki_dir)
    else:
        payload = {"candidates": [], "summary": {"to_review": 0}}
    rows = payload["candidates"]
    n = int(payload["summary"].get("to_review") or 0)
    vault = vault_display_path(wiki_dir)
    entities = _table_rows_html(rows, "entities")
    concepts = _table_rows_html(rows, "concepts")
    headers = "<tr><th>Name</th><th>Slug</th><th>Description</th><th>Age</th></tr>"
    return f"""<section class="section">
  <div class="container">
    <p class="muted" id="cand-status">{n} pending candidate(s). This page lists what is waiting; review runs on the command line with <code>llmwiki candidates</code>.</p>
    <p id="cand-error" class="error-banner" hidden role="alert"></p>
    <h2>Entities (pending)</h2>
    <div class="state-table-wrap" tabindex="0" role="region" aria-label="Pending entity candidates">
      <table class="state-pipeline-table cand-review-table" id="cand-table-entities">
        <thead>{headers}</thead>
        <tbody>{entities}</tbody>
      </table>
    </div>
    <h2>Concepts (pending)</h2>
    <div class="state-table-wrap" tabindex="0" role="region" aria-label="Pending concept candidates">
      <table class="state-pipeline-table cand-review-table" id="cand-table-concepts">
        <thead>{headers}</thead>
        <tbody>{concepts}</tbody>
      </table>
    </div>
    {_apply_block_html(rows, vault)}
  </div>
</section>
{_COPY_SCRIPT}"""
