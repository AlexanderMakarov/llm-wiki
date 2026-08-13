"""Static candidates review page + JSON payload helpers (#97).

Build emits ``site/candidates.html``: two tables (entities, concepts) with a
**Decision** control on every row — promote, flip-promote, merge into a named
page, or discard with a reason. Decisions are DOM state, so the page needs
nothing running. **Apply** assembles the chosen rows into a ready-to-paste
``llmwiki candidates apply --vault … --actions -`` command plus the JSON batch
to pipe into it. Rows left at "No decision" stay out of the batch and stay
pending.
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


def merge_targets(wiki_dir: Path, kind: str, rows: list[dict[str, Any]]) -> list[str]:
    """Slugs ``merge --into`` accepts for ``kind``: trusted pages, then peers.

    ``merge()`` resolves a target under ``wiki/<kind>/`` first and falls back to
    another pending stub in the same table, so the suggestion list offers both.
    """
    trusted = []
    folder = wiki_dir / kind
    if folder.is_dir():
        trusted = sorted(
            p.stem for p in folder.glob("*.md") if not p.name.startswith("_")
        )
    peers = sorted(r["slug"] for r in rows if r["kind"] == kind)
    seen: set[str] = set()
    out: list[str] = []
    for slug in trusted + peers:
        if slug not in seen:
            seen.add(slug)
            out.append(slug)
    return out


#: Decision vocabulary, mirroring the ``action`` values ``llmwiki candidates
#: apply`` parses (see ``_VALID_ACTIONS``). The empty value is the default and
#: keeps the row out of the batch.
_DECISION_CHOICES: tuple[tuple[str, str], ...] = (
    ("", "No decision"),
    ("promote", "Promote"),
    ("flip-promote", "Flip and promote"),
    ("merge", "Merge into…"),
    ("discard", "Discard"),
)


def _decision_controls_html(row: dict[str, Any], kind: str, index: int) -> str:
    """The Decision cell: an action select plus the field that action needs.

    *Merge into…* reveals a combobox over the merge targets for ``kind``, and
    *Discard* reveals the reason the archived stub keeps beside itself.
    """
    slug = html.escape(row["slug"])
    kind_esc = html.escape(kind)
    list_id = f"cand-target-list-{kind_esc}-{index}"
    options = "".join(
        f'<option value="{html.escape(value)}">{html.escape(label)}</option>'
        for value, label in _DECISION_CHOICES
    )
    return (
        f'<div class="cand-intent" data-slug="{slug}" data-kind="{kind_esc}">'
        f'<label class="muted">Decision '
        f'<select class="cand-decision" aria-label="Decision for {slug}">'
        f"{options}</select></label>"
        f'<span class="cand-merge-wrap muted" hidden>Into '
        f'<span class="cand-combo" data-kind="{kind_esc}">'
        f'<input class="cand-merge-into" type="text" role="combobox"'
        f' autocomplete="off" aria-autocomplete="list" aria-expanded="false"'
        f' aria-controls="{list_id}" aria-label="Merge {slug} into"'
        f' placeholder="Choose a page">'
        f'<button type="button" class="cand-combo-open" tabindex="-1"'
        f' aria-label="Show pages {slug} can merge into">\u25be</button>'
        f'<ul class="cand-combo-list" id="{list_id}" role="listbox"'
        f' aria-label="Pages {slug} can merge into" hidden></ul>'
        f'<span class="cand-combo-empty" hidden></span>'
        "</span></span>"
        f'<label class="cand-reason-wrap muted" hidden>Reason '
        f'<input class="cand-discard-reason" type="text" aria-required="true"'
        f' placeholder="why it is rejected"'
        f' aria-label="Reason for discarding {slug}"></label>'
        "</div>"
    )


def _targets_data_html(wiki_dir: Path | None, kind: str,
                       rows: list[dict[str, Any]]) -> str:
    """The merge targets for ``kind`` as inline JSON, once for the whole page.

    Every row's combobox is filled and filtered from this one list, so a vault
    with many pending stubs still carries a single copy of the target names.
    """
    slugs = merge_targets(wiki_dir, kind, rows) if wiki_dir else []
    payload = json.dumps(slugs, ensure_ascii=False).replace("<", "\\u003c")
    return (
        f'<script type="application/json" class="cand-targets"'
        f' id="cand-targets-{html.escape(kind)}"'
        f' data-kind="{html.escape(kind)}">{payload}</script>'
    )


def _table_rows_html(rows: list[dict[str, Any]], kind: str) -> str:
    kind_rows = [r for r in rows if r["kind"] == kind]
    if not kind_rows:
        return (
            f'<tr><td colspan="3" class="muted">No pending {html.escape(kind)} '
            "candidates.</td></tr>"
        )
    out: list[str] = []
    for index, r in enumerate(kind_rows):
        age = f'{r["age_days"]}d' if r.get("created") else "\u2014"
        out.append(
            "<tr>"
            f'<td><strong>{html.escape(r["title"])}</strong>'
            f'<div class="muted"><code>{html.escape(r["slug"])}</code> \u00b7 '
            f'{html.escape(age)}</div></td>'
            f'<td>{html.escape(r["description"])}</td>'
            f'<td class="cand-actions">{_decision_controls_html(r, kind, index)}</td>'
            "</tr>"
        )
    return "\n".join(out)


def apply_command_prefix(vault: str) -> str:
    """Everything before ``--actions`` in the line the page emits for ``vault``.

    The page appends the shell-quoted batch, so what a reviewer copies is one
    line they can paste. Reading a decision back out of a separate JSON block
    is not something a terminal can do for them.
    """
    return f"llmwiki candidates apply --vault {_shell_single_quote(vault)}"


_REVIEW_SCRIPT = """<script>
  var APPLY_PREFIX = __APPLY_PREFIX__;
(function () {
  var panel = document.getElementById("cand-apply-panel");
  if (!panel) return;
  var errEl = document.getElementById("cand-error");
  var outEl = document.getElementById("cand-output");
  var commandEl = document.getElementById("cand-command");
  var countEl = document.getElementById("cand-decision-count");
  var applyBtn = document.getElementById("cand-apply");
  var copyCmdBtn = document.getElementById("cand-copy-command");
  var TARGETS = readTargets();

  // One inline JSON island per kind holds every page `merge --into` resolves.
  function readTargets() {
    var map = {};
    Array.prototype.forEach.call(
      document.querySelectorAll("script.cand-targets"),
      function (el) {
        var kind = el.getAttribute("data-kind");
        try {
          map[kind] = JSON.parse(el.textContent || "[]");
        } catch (e) {
          map[kind] = [];
          if (window.__llmwikiReportError) {
            window.__llmwikiReportError(
              "Merge targets for " + kind + " unreadable", e
            );
          }
        }
      }
    );
    return map;
  }
  function targetsFor(kind, ownSlug) {
    // A candidate cannot be merged into itself: `merge` resolves the target
    // and would archive the row into its own page.
    var all = TARGETS[kind] || [];
    if (!ownSlug) return all;
    return all.filter(function (slug) { return slug !== ownSlug; });
  }
  // Typing narrows the list: case-insensitive substring, order preserved.
  function filterTargets(list, query) {
    var q = String(query == null ? "" : query).trim().toLowerCase();
    if (!q) return list.slice();
    return list.filter(function (slug) {
      return slug.toLowerCase().indexOf(q) !== -1;
    });
  }
  function isKnownTarget(kind, value, ownSlug) {
    return targetsFor(kind, ownSlug).indexOf(String(value)) !== -1;
  }

  function showError(msg) {
    errEl.hidden = !msg;
    errEl.textContent = msg || "";
  }
  function rows() {
    return Array.prototype.slice.call(document.querySelectorAll(".cand-intent"));
  }
  function decisionOf(wrap) {
    var sel = wrap.querySelector(".cand-decision");
    return sel ? sel.value : "";
  }
  function fieldValue(wrap, sel) {
    var el = wrap.querySelector(sel);
    return el ? (el.value || "").trim() : "";
  }
  function markField(el, bad) {
    if (!el) return;
    el.setAttribute("data-invalid", bad ? "yes" : "no");
    el.setAttribute("aria-invalid", bad ? "true" : "false");
  }
  // What a decided row still needs before it can run. Merge needs a page from
  // the list; discard needs the reason archived beside the stub. "" means the
  // row is ready.
  function rowProblem(wrap) {
    var action = decisionOf(wrap);
    var slug = wrap.getAttribute("data-slug");
    if (action === "merge") {
      var into = fieldValue(wrap, ".cand-merge-into");
      if (!into) return slug + " (choose a page to merge into)";
      if (!isKnownTarget(wrap.getAttribute("data-kind"), into, slug)) {
        return slug + " (no page named " + into + " to merge into)";
      }
    } else if (action === "discard" && !fieldValue(wrap, ".cand-discard-reason")) {
      return slug + " (give a reason for discarding)";
    }
    return "";
  }
  // Text naming no page is wrong the moment it is typed; an empty field is
  // merely unfinished, so it is flagged when Apply asks for it.
  function markTyping(wrap) {
    var mergeEl = wrap.querySelector(".cand-merge-into");
    if (mergeEl) {
      var into = (mergeEl.value || "").trim();
      markField(
        mergeEl,
        into !== "" && !isKnownTarget(wrap.getAttribute("data-kind"), into, wrap.getAttribute("data-slug"))
      );
    }
    var reasonEl = wrap.querySelector(".cand-discard-reason");
    if (reasonEl && (reasonEl.value || "").trim()) markField(reasonEl, false);
  }
  function flagUnfinished() {
    var first = null;
    rows().forEach(function (wrap) {
      var action = decisionOf(wrap);
      var bad = action ? rowProblem(wrap) : "";
      var field = wrap.querySelector(
        action === "merge" ? ".cand-merge-into" : ".cand-discard-reason"
      );
      if (action === "merge" || action === "discard") markField(field, Boolean(bad));
      if (bad && !first) first = field;
    });
    if (first && first.focus) first.focus();
  }
  function syncRow(wrap) {
    var value = decisionOf(wrap);
    var mergeWrap = wrap.querySelector(".cand-merge-wrap");
    var reasonWrap = wrap.querySelector(".cand-reason-wrap");
    if (mergeWrap) {
      mergeWrap.hidden = value !== "merge";
      var combo = mergeWrap.querySelector(".cand-combo");
      if (combo && combo.llmwikiClose && value !== "merge") combo.llmwikiClose();
    }
    if (reasonWrap) reasonWrap.hidden = value !== "discard";
    if (value !== "merge") markField(wrap.querySelector(".cand-merge-into"), false);
    if (value !== "discard") {
      markField(wrap.querySelector(".cand-discard-reason"), false);
    }
    wrap.setAttribute("data-decided", value ? "yes" : "no");
  }
  function refreshCount() {
    var n = rows().filter(function (w) { return decisionOf(w); }).length;
    countEl.textContent = n === 0
      ? "No decisions set"
      : n + (n === 1 ? " decision set" : " decisions set");
  }
  // Rows left at "No decision" are absent from the batch, so Apply never
  // promotes anything the reviewer did not choose. A row that was decided but
  // is not executable holds the whole batch back rather than going out broken.
  function collectActions() {
    var actions = [];
    var unfinished = [];
    rows().forEach(function (wrap) {
      var action = decisionOf(wrap);
      if (!action) return;
      var problem = rowProblem(wrap);
      if (problem) { unfinished.push(problem); return; }
      var item = {
        action: action,
        slug: wrap.getAttribute("data-slug"),
        kind: wrap.getAttribute("data-kind")
      };
      if (action === "merge") {
        item.into = fieldValue(wrap, ".cand-merge-into");
      } else if (action === "discard") {
        item.reason = fieldValue(wrap, ".cand-discard-reason");
      }
      actions.push(item);
    });
    if (unfinished.length) {
      var err = new Error("Finish these rows before Apply: " + unfinished.join("; "));
      err.reviewerFixable = true;
      throw err;
    }
    if (!actions.length) {
      var none = new Error("Set at least one Decision before Apply.");
      none.reviewerFixable = true;
      throw none;
    }
    return actions;
  }
  function apply() {
    showError("");
    var actions;
    try {
      actions = collectActions();
    } catch (e) {
      showError(e.message || String(e));
      if (e.reviewerFixable) {
        flagUnfinished();
      } else if (window.__llmwikiReportError) {
        window.__llmwikiReportError("Candidates Apply failed", e);
      }
      return;
    }
    commandEl.textContent = applyCommand(actions);
    outEl.hidden = false;
    copyCmdBtn.hidden = false;
    outEl.scrollIntoView({ block: "nearest" });
  }
  function shellQuote(s) {
    // Single-quote for POSIX shells: close, escape, reopen. Mirrors
    // _shell_single_quote so the page and the CLI agree on one line.
    return "'" + String(s).split("'").join("'\\''") + "'";
  }
  function applyCommand(actions) {
    var payload = JSON.stringify(actions);
    return APPLY_PREFIX + " --actions " + shellQuote(payload);
  }
  function copyFrom(btn) {
    var src = document.getElementById(btn.getAttribute("data-copy-target"));
    var text = src ? (src.textContent || "") : "";
    if (!text) {
      showError("Nothing to copy yet — press Apply first.");
      return;
    }
    if (!navigator.clipboard || !navigator.clipboard.writeText) {
      showError("Clipboard unavailable — select the text and copy manually.");
      return;
    }
    var label = btn.textContent;
    navigator.clipboard.writeText(text).then(function () {
      showError("");
      btn.textContent = "Copied";
      setTimeout(function () { btn.textContent = label; }, 1500);
    }).catch(function (e) {
      showError("Could not copy — select the text and copy manually.");
      if (window.__llmwikiReportError) {
        window.__llmwikiReportError("Candidates copy failed", e);
      }
    });
  }

  // A filterable dropdown over the merge targets: the text box narrows the
  // list, the button opens it whole for a reviewer who knows no names yet.
  function setupCombo(combo) {
    var input = combo.querySelector(".cand-merge-into");
    var list = combo.querySelector(".cand-combo-list");
    var emptyEl = combo.querySelector(".cand-combo-empty");
    var toggle = combo.querySelector(".cand-combo-open");
    var wrap = combo.closest(".cand-intent");
    var kind = combo.getAttribute("data-kind");
    var ownSlug = wrap ? wrap.getAttribute("data-slug") : null;
    var options = [];
    var active = -1;

    function isOpen() { return !list.hidden; }
    function setActive(i) {
      active = i;
      options.forEach(function (li, n) {
        li.setAttribute("aria-selected", n === i ? "true" : "false");
        li.className = n === i
          ? "cand-combo-option is-active"
          : "cand-combo-option";
      });
      if (i >= 0 && options[i]) {
        input.setAttribute("aria-activedescendant", options[i].id);
        if (options[i].scrollIntoView) {
          options[i].scrollIntoView({ block: "nearest" });
        }
      } else {
        input.removeAttribute("aria-activedescendant");
      }
    }
    function render() {
      var typed = (input.value || "").trim();
      var all = targetsFor(kind, ownSlug);
      var matches = filterTargets(all, typed);
      while (list.firstChild) list.removeChild(list.firstChild);
      options = matches.map(function (slug, i) {
        var li = document.createElement("li");
        li.className = "cand-combo-option";
        li.id = list.id + "-o" + i;
        li.setAttribute("role", "option");
        li.setAttribute("aria-selected", "false");
        li.textContent = slug;
        list.appendChild(li);
        return li;
      });
      emptyEl.textContent = all.length
        ? "No page matches — clear the text to see all " + all.length + "."
        : "No pages to merge into yet.";
      emptyEl.hidden = matches.length > 0;
      list.hidden = matches.length === 0;
      var exact = matches.indexOf(typed);
      setActive(exact >= 0 ? exact : (typed && matches.length ? 0 : -1));
    }
    function open() {
      render();
      input.setAttribute("aria-expanded", isOpen() ? "true" : "false");
    }
    function close() {
      list.hidden = true;
      emptyEl.hidden = true;
      input.setAttribute("aria-expanded", "false");
      input.removeAttribute("aria-activedescendant");
      active = -1;
    }
    function choose(i) {
      if (i < 0 || i >= options.length) return;
      input.value = options[i].textContent;
      close();
      markField(input, false);
      if (input.focus) input.focus();
    }
    function step(delta) {
      if (!options.length) return;
      var next = active + delta;
      if (next < 0) next = options.length - 1;
      if (next >= options.length) next = 0;
      setActive(next);
    }

    input.addEventListener("input", function () {
      open();
      if (wrap) markTyping(wrap);
    });
    input.addEventListener("keydown", function (ev) {
      var key = ev.key;
      if (key === "ArrowDown" || key === "ArrowUp") {
        ev.preventDefault();
        if (!isOpen()) {
          open();
          if (key === "ArrowUp") setActive(options.length - 1);
          else if (active < 0) setActive(0);
          return;
        }
        step(key === "ArrowDown" ? 1 : -1);
        return;
      }
      if (!isOpen()) return;
      if (key === "Home") { ev.preventDefault(); setActive(0); return; }
      if (key === "End") { ev.preventDefault(); setActive(options.length - 1); return; }
      if (key === "Enter" && active >= 0) { ev.preventDefault(); choose(active); return; }
      if (key === "Escape") { ev.preventDefault(); close(); return; }
      if (key === "Tab") close();
    });
    toggle.addEventListener("click", function (ev) {
      ev.preventDefault();
      if (input.focus) input.focus();
      if (isOpen()) { close(); } else { open(); }
    });
    // mousedown default would blur the input before the click lands.
    list.addEventListener("mousedown", function (ev) { ev.preventDefault(); });
    list.addEventListener("click", function (ev) {
      var li = ev.target.closest ? ev.target.closest(".cand-combo-option") : null;
      if (li) choose(options.indexOf(li));
    });
    combo.addEventListener("focusout", function (ev) {
      if (ev.relatedTarget && combo.contains(ev.relatedTarget)) return;
      close();
      if (wrap) markTyping(wrap);
    });
    combo.llmwikiClose = close;
  }

  try {
    document.addEventListener("change", function (ev) {
      var wrap = ev.target.closest && ev.target.closest(".cand-intent");
      if (!wrap) return;
      syncRow(wrap);
      refreshCount();
    });
    document.addEventListener("input", function (ev) {
      var wrap = ev.target.closest && ev.target.closest(".cand-intent");
      if (wrap) markTyping(wrap);
    });
    document.querySelectorAll("[data-copy-target]").forEach(function (btn) {
      btn.addEventListener("click", function () { copyFrom(btn); });
    });
    document.querySelectorAll(".cand-combo").forEach(setupCombo);
    applyBtn.addEventListener("click", apply);
    rows().forEach(syncRow);
    refreshCount();
  } catch (e) {
    if (window.__llmwikiReportError) {
      window.__llmwikiReportError("Candidates review controls unavailable", e);
    }
  }
})();
</script>
"""


def _apply_bar_html(rows: list[dict[str, Any]]) -> str:
    """The Apply control. Sits above the tables so it is never buried."""
    if not rows:
        return (
            '<p class="muted">Nothing pending. New stubs appear here after '
            "<code>llmwiki synth</code> harvests them.</p>"
        )
    return """<div class="cand-apply-panel" id="cand-apply-panel">
      <div class="cand-apply-bar">
        <button type="button" id="cand-apply" class="cand-apply-btn cand-apply-primary">Apply</button>
        <span class="muted" id="cand-decision-count" aria-live="polite">No decisions set</span>
        <span class="cand-apply-spacer"></span>
        <button type="button" class="cand-apply-btn" id="cand-copy-command" data-copy-target="cand-command" hidden>Copy command</button>
      </div>
    </div>"""


def _apply_output_html(rows: list[dict[str, Any]], vault: str) -> str:
    """The command Apply writes, placed after the tables.

    One line, with the batch already inside it, so it pastes into a terminal
    as-is. The tables stay on screen above it: the decisions are the thing
    being reviewed, and reading them back out of JSON is not review.
    """
    if not rows:
        return ""
    return f"""<div class="cand-output" id="cand-output" hidden>
      <p class="muted">Run this:</p>
      <pre class="cand-cli" id="cand-command"></pre>
      <p class="muted">Then <code>llmwiki build --vault {html.escape(vault)}</code> to refresh these counts.</p>
    </div>"""


def render_candidates_body(wiki_dir: Path | None) -> str:
    """Inner HTML for ``candidates.html`` — review tables + the Apply panel."""
    if wiki_dir and wiki_dir.is_dir():
        payload = candidates_payload(wiki_dir)
    else:
        payload = {"candidates": [], "summary": {"to_review": 0}}
    rows = payload["candidates"]
    n = int(payload["summary"].get("to_review") or 0)
    vault = vault_display_path(wiki_dir)
    entities = _table_rows_html(rows, "entities")
    concepts = _table_rows_html(rows, "concepts")
    targets = _targets_data_html(wiki_dir, "entities", rows) + _targets_data_html(
        wiki_dir, "concepts", rows,
    )
    headers = "<tr><th>Name</th><th>Description</th><th>Decision</th></tr>"
    return f"""<section class="section">
  <div class="container">
    <p class="muted" id="cand-status">{n} pending candidate(s). Set a Decision on the rows you have judged, then <strong>Apply</strong> — it writes the command and JSON batch to run. Rows left at <em>No decision</em> stay pending.</p>
    <p id="cand-error" class="error-banner" hidden role="alert"></p>
    {_apply_bar_html(rows)}
    <h2>Entities (pending)</h2>
    <div class="state-table-wrap cand-table-wrap" tabindex="0" role="region" aria-label="Pending entity candidates">
      <table class="state-pipeline-table cand-review-table" id="cand-table-entities">
        <thead>{headers}</thead>
        <tbody>{entities}</tbody>
      </table>
    </div>
    <h2>Concepts (pending)</h2>
    <div class="state-table-wrap cand-table-wrap" tabindex="0" role="region" aria-label="Pending concept candidates">
      <table class="state-pipeline-table cand-review-table" id="cand-table-concepts">
        <thead>{headers}</thead>
        <tbody>{concepts}</tbody>
      </table>
    </div>
    {_apply_output_html(rows, vault)}
    {targets}
  </div>
</section>
{_REVIEW_SCRIPT.replace('__APPLY_PREFIX__', json.dumps(apply_command_prefix(vault)))}"""
