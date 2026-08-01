"""Inline JavaScript for the static site viewer (v1.1 · #217).

Extracted from ``llmwiki/build.py`` in the #217 refactor. Byte-identical
to the pre-refactor constant — verified by ``llmwiki build`` hash.

Vanilla JS, no framework. Handles:
  - Theme toggle (light/dark/system) with localStorage persistence
  - Cmd+K command palette + fuzzy search against search-index.json
  - Keyboard shortcuts (/, g h/p/s, j/k, ?)
  - Copy-as-markdown + copy-code buttons
  - Reading progress bar on long pages
  - Sticky table headers on the sessions index
  - Filter bar on sessions table (project/model/date/text)
  - Mobile bottom nav
  - Hover-to-preview wikilinks
  - Deep-link anchors on headings
  - Related pages panel
"""

from __future__ import annotations

JS = r"""// llmwiki viewer — theme + copy + search palette + keyboard shortcuts + progress bar + filter bar
// Vanilla JS, no framework.

// ─── Theme toggle ─────────────────────────────────────────────────────────
(function () {
  function formatTs(ts) {
    if (!ts) return "never";
    return ts;
  }
  function escapeHtml(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }
  function formatUsd(n) {
    var v = Number(n || 0);
    if (!isFinite(v) || v <= 0) return "";
    return "$" + v.toFixed(4);
  }
  /** One-line cell: ``42`` or ``42 ($1.2345)``. */
  function stageCell(count, nextCost) {
    var cost = formatUsd(nextCost);
    var html = '<span class="state-cell-count">' + Number(count || 0) + "</span>";
    if (cost) {
      html += ' <span class="state-cell-cost">(' + cost + ")</span>";
    }
    return html;
  }
  function pendingListHtml(items) {
    if (!items.length) return '<p class="muted">None.</p>';
    return "<ul class=\"queue-type-list\">" + items.map(function (it) {
      var rel = it && it.rel ? String(it.rel) : "";
      var project = it && it.project ? String(it.project) : "unknown";
      var agent = it && it.agent ? String(it.agent) : "";
      var usd = formatUsd(it && it.usd);
      var meta = project + (agent ? " · " + agent : "") + (usd ? " · " + usd : "");
      return "<li><code>" + escapeHtml(rel) + "</code> <span class=\"muted\">(" + escapeHtml(meta) + ")</span></li>";
    }).join("") + "</ul>";
  }
  function detailsSection(title, count, bodyHtml) {
    return (
      '<details class="collapse-section">' +
      "<summary>" + escapeHtml(title) +
      '<span class="collapse-section-count">' + Number(count || 0) + "</span></summary>" +
      '<div class="collapse-section-body">' + bodyHtml + "</div></details>"
    );
  }
  function commandsBody(repoRoot) {
    function copyBtn(cmd) {
      // Escape so quoted agent launchers (… claude "/wiki-candidates") do not
      // break the attribute. Click handler prefers the Command cell text.
      var safe = escapeHtml(cmd);
      return (
        '<button type="button" class="btn queue-copy-btn" data-copy="' + safe +
        '" aria-label="Copy command: ' + safe + '" title="Copy command">Copy</button>'
      );
    }
    var repo = repoRoot ? String(repoRoot) : "<llm-wiki-checkout>";
    var reviewPurpose = "Review/edit pending candidates (promote, merge, or discard).";
    function commandRow(cmd, purposeHtml) {
      return (
        "<tr><td><code>" + escapeHtml(cmd) + "</code></td><td>" + purposeHtml +
        "</td><td>" + copyBtn(cmd) + "</td></tr>"
      );
    }
    function agentReview(bin) {
      // Prompt arg starts the review slash in one shot — cwd is the checkout
      // (where .claude/commands/ lives), not the vault.
      return commandRow(
        "cd " + repo + " && " + bin + ' "/wiki-candidates"',
        escapeHtml(reviewPurpose)
      );
    }
    return (
      '<p class="muted">CLI rows are copy-paste runnable. Agent rows start <code>/wiki-candidates</code> from the <strong>llmwiki checkout</strong> (slash commands load from <code>.claude/commands/</code>; vault path comes from <code>config.json</code>). Harvest stubs with <code>llmwiki synth</code> (or <code>synth --candidates-only</code>) before review — estimate&apos;s &quot;Candidates: N stub(s)&quot; is a preview, not the Home <strong>Candidates</strong> count.</p>' +
      '<table class="queue-commands-table">' +
      "<thead><tr><th>Command</th><th>Purpose</th><th></th></tr></thead><tbody>" +
      commandRow("llmwiki sync", "Convert new agent sessions into <code>raw/sessions/</code>.") +
      commandRow("llmwiki sync --project <slug>", "Sync only one project&apos;s sessions.") +
      commandRow("llmwiki synth", "Synthesize pending sources, then harvest entity/concept candidates.") +
      commandRow("llmwiki synth --sources-only", "Drain unsynthesized backlog into <code>wiki/sources/</code> only.") +
      commandRow("llmwiki synth --candidates-only", "Harvest entity/concept candidates into <code>wiki/candidates/</code>.") +
      commandRow("llmwiki synth --estimate", "Refresh cost estimate + pipeline table (sources + harvestable-stub preview).") +
      commandRow("llmwiki candidates list", "Show pending review stubs (runnable output).") +
      commandRow("llmwiki candidates list --stale", "Show candidates older than the stale threshold (default 30d).") +
      commandRow("llmwiki candidates promote --slug <Name>", "Promote one stub into trusted <code>wiki/entities/</code> or <code>concepts/</code>.") +
      agentReview("claude") +
      agentReview("agent") +
      agentReview("codex") +
      commandRow("llmwiki build", "Rebuild the static site (refreshes Candidates / Entities / Concepts counts).") +
      "</tbody></table>"
    );
  }
  function reviewBreakdownHtml(pipeline) {
    var byKind = (pipeline && pipeline.to_review_by_kind) ? pipeline.to_review_by_kind : {};
    var keys = Object.keys(byKind).sort();
    if (!keys.length) {
      return '<p class="muted">No pending candidates under <code>wiki/candidates/</code>. Harvest with <code>llmwiki synth</code> (or <code>synth --candidates-only</code>).</p>';
    }
    var stale = Number(pipeline && pipeline.to_review_stale || 0);
    var staleDays = Number(pipeline && pipeline.stale_days || 30);
    var items = keys.map(function (k) {
      return "<li><strong>" + escapeHtml(k) + ":</strong> " + Number(byKind[k] || 0) + "</li>";
    });
    items.push("<li><strong>Stale (≥" + staleDays + "d):</strong> " + stale + "</li>");
    return "<ul class=\"queue-type-list\">" + items.join("") + "</ul>" +
      '<p class="muted">Review focus: identity / naming / kind / duplicates — not primarily <code>## Contradictions</code>. Approve via agent <code>/wiki-candidates</code> or <code>llmwiki candidates promote|merge|discard</code>.</p>';
  }
  function renderStateWidget(root, snapshot) {
    if (!root) return;
    if (!snapshot) {
      root.innerHTML = '<p class="muted">No state snapshot available.</p>';
      return;
    }
    var synthState = snapshot.synth || {};
    var pipeline = synthState.pipeline || {};
    var rows = Array.isArray(pipeline.rows) ? pipeline.rows : [];
    var pendingList = Array.isArray(synthState.pending) ? synthState.pending : [];
    var estimate = (synthState && synthState.estimate) ? synthState.estimate : {};
    var ops = snapshot.ops || {};
    var lastSync = ((snapshot.sync || {}).meta || {}).last_sync || "";
    var items = Array.isArray((snapshot.queue || {}).items) ? snapshot.queue.items : [];
    var oldest = "";
    var queuePending = 0;
    var queueRunning = 0;
    items.forEach(function (it) {
      var st = (it && it.status) ? String(it.status) : "pending";
      if (st === "pending") queuePending += 1;
      if (st === "running") queueRunning += 1;
      if (st === "pending" && it.created_at && (!oldest || it.created_at < oldest)) oldest = it.created_at;
    });
    pendingList.forEach(function (it) {
      if (it && it.mtime && (!oldest || it.mtime < oldest)) oldest = it.mtime;
    });

    var pendingSessions = pendingList.filter(function (it) { return !(it && it.is_doc); });
    var pendingDocs = pendingList.filter(function (it) { return !!(it && it.is_doc); });
    var warnings = Array.isArray(estimate.warnings) ? estimate.warnings : [];
    var toReview = Number(pipeline.to_review || 0);
    var trustedEntities = Number(pipeline.trusted_entities || 0);
    var trustedConcepts = Number(pipeline.trusted_concepts || 0);
    var repoRoot = root.getAttribute("data-repo-root") || "";

    var totalRaw = 0;
    var totalSynth = 0;
    var totalPending = 0;
    var totalNext = 0;
    var bodyRows = rows.map(function (row) {
      var label = row && row.label ? String(row.label) : "Unknown";
      var css = row && row.css ? String(row.css) : "agent-unknown";
      var raw = Number(row && row.raw || 0);
      var synthesized = Number(row && row.synthesized || 0);
      var pending = Number(row && row.pending || 0);
      var nextUsd = Number(row && row.next_usd || 0);
      totalRaw += raw;
      totalSynth += synthesized;
      totalPending += pending;
      totalNext += nextUsd;
      var isDocs = (row && row.kind === "docs") || label === "Documents";
      var sourceLabel = isDocs
        ? '<span class="state-source-docs">' + escapeHtml(label) + "</span>"
        : ('<span class="agent-badge ' + escapeHtml(css) + '">' + escapeHtml(label) +
           "</span> sessions");
      // Files layer: Raw → To synthesize → Synthesized (shell-handled)
      return (
        "<tr>" +
        '<td class="state-row-label">' + sourceLabel + "</td>" +
        "<td>" + stageCell(raw, 0) + "</td>" +
        "<td>" + stageCell(pending, nextUsd) + "</td>" +
        "<td>" + stageCell(synthesized, 0) + "</td>" +
        "</tr>"
      );
    }).join("");

    var footHtml = "";
    if (!bodyRows) {
      bodyRows = '<tr><td colspan="4" class="muted">No pipeline rows yet — run <code>llmwiki sync</code> then <code>llmwiki synth --estimate</code>. Rows appear per agent that has contributed at least one session.</td></tr>';
    } else {
      footHtml =
        "<tfoot><tr>" +
        "<td>Total" +
        ' <span class="muted state-queue-meta">(queued ' + queuePending +
        " · in progress " + queueRunning + ")</span></td>" +
        "<td>" + stageCell(totalRaw, 0) + "</td>" +
        "<td>" + stageCell(totalPending, totalNext) + "</td>" +
        "<td>" + stageCell(totalSynth, 0) + "</td>" +
        "</tr></tfoot>";
    }

    var tableHtml =
      '<div class="state-table-wrap" tabindex="0" role="region" aria-label="Files layer">' +
      '<p class="muted">Files layer: Raw → To synthesize → Synthesized (by agent). Handled by shell commands.</p>' +
      '<table class="state-pipeline-table">' +
      "<thead><tr><th>Source</th><th>Raw</th><th>To synthesize</th><th>Synthesized</th></tr></thead>" +
      "<tbody>" + bodyRows + "</tbody>" + footHtml + "</table></div>";

    var knowledgeHtml =
      '<div class="state-table-wrap" tabindex="0" role="region" aria-label="Knowledge layer">' +
      '<p class="muted">Knowledge layer: Candidates → Entities / Concepts. Review runs in the agent Commands below.</p>' +
      '<table class="state-pipeline-table state-knowledge-table">' +
      "<thead><tr><th>Candidates</th><th>Entities</th><th>Concepts</th></tr></thead>" +
      "<tbody><tr>" +
      "<td>" + stageCell(toReview, 0) + "</td>" +
      "<td>" + stageCell(trustedEntities, 0) + "</td>" +
      "<td>" + stageCell(trustedConcepts, 0) + "</td>" +
      "</tr></tbody></table></div>";

    var timelineBody =
      "<ul class=\"queue-type-list\">" +
      "<li><strong>Oldest pending:</strong> " + escapeHtml(oldest || "none") + "</li>" +
      "<li><strong>Last sync:</strong> " + escapeHtml(formatTs(lastSync)) + "</li>" +
      "<li><strong>Last queue run:</strong> " + escapeHtml(formatTs(ops.last_queue_run_at)) + "</li>" +
      "<li><strong>Last lint run:</strong> " + escapeHtml(formatTs(ops.last_lint_run_at)) + "</li>" +
      "<li><strong>Last reflect run:</strong> " + escapeHtml(formatTs(ops.last_reflect_run_at)) + "</li>" +
      "</ul>";

    var warningsBody = warnings.length
      ? ("<ul class=\"queue-type-list\">" + warnings.map(function (w) {
          return "<li>" + escapeHtml(w) + "</li>";
        }).join("") + "</ul>")
      : '<p class="muted">No estimate warnings.</p>';

    var estNote = "";
    if (estimate && (estimate.updated_at || estimate.incremental_usd != null)) {
      estNote =
        '<p class="muted">Estimate updated ' + escapeHtml(formatTs(estimate.updated_at || "")) +
        " · incremental $" + Number(estimate.incremental_usd || 0).toFixed(4) +
        " · pricing <code>" + escapeHtml(estimate.pricing_model || "default") + "</code></p>";
    }

    root.innerHTML =
      tableHtml +
      knowledgeHtml +
      estNote +
      '<div class="collapse-sections">' +
      detailsSection("Timeline", 5, timelineBody) +
      detailsSection("Not synthesized sessions", pendingSessions.length, pendingListHtml(pendingSessions)) +
      detailsSection("Not synthesized docs", pendingDocs.length, pendingListHtml(pendingDocs)) +
      detailsSection("Candidates to review", toReview, reviewBreakdownHtml(pipeline)) +
      detailsSection("Commands", 13, commandsBody(repoRoot)) +
      detailsSection("Estimate warnings", warnings.length, warningsBody) +
      "</div>";
  }

  function renderQueueTrace() {
    var snapshot = window.LLMWIKI_STATE_SNAPSHOT;
    var mounts = document.querySelectorAll("[data-llmwiki-state-widget], #llmwiki-state-widget, #queue-home-content, #queue-raw-content");
    if (!mounts.length) return;
    mounts.forEach(function (el) {
      renderStateWidget(el, snapshot);
      wireQueueCopyButtons(el);
    });
  }

  function wireQueueCopyButtons(root) {
    var scope = root || document;
    scope.querySelectorAll(".queue-copy-btn").forEach(function (btn) {
      if (btn.getAttribute("data-wired") === "1") return;
      btn.setAttribute("data-wired", "1");
      btn.addEventListener("click", function () {
        // Prefer the Command cell text so Copy matches what the user sees
        // (avoids broken data-copy when the command contains quotes).
        var row = btn.closest("tr");
        var code = row && row.querySelector("td code");
        var txt = (code && code.textContent ? code.textContent.trim() : "") ||
          btn.getAttribute("data-copy") || "";
        if (!txt) return;
        navigator.clipboard.writeText(txt).then(function () {
          btn.textContent = "Copied";
          setTimeout(function () { btn.textContent = "Copy"; }, 1200);
        }).catch(function () {});
      });
    });
  }
  document.addEventListener("DOMContentLoaded", function () {
    renderQueueTrace();
    wireQueueCopyButtons();
  });
})();

(function () {
  const root = document.documentElement;
  // v0.5: Keep the highlight.js theme in sync with the page theme by
  // swapping which stylesheet is "disabled". Runs on page load and on every
  // toggle. Falls back silently if the tags are absent.
  function syncHljsTheme() {
    const light = document.getElementById("hljs-light");
    const dark = document.getElementById("hljs-dark");
    if (!light || !dark) return;
    let active = root.getAttribute("data-theme");
    if (!active) {
      active = (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) ? "dark" : "light";
    }
    const isDark = active === "dark";
    light.disabled = isDark;
    dark.disabled = !isDark;
  }
  // #ui-h4 (#566): localStorage access can throw in Safari Private Mode,
  // sandboxed iframes, and some embedded browsers. Wrap reads + writes
  // in try/catch so a thrown SecurityError doesn't kill the whole
  // theme + hljs-sync wiring.
  let saved = null;
  try { saved = localStorage.getItem("llmwiki-theme"); } catch (e) { /* private mode */ }
  if (saved === "dark" || saved === "light") root.setAttribute("data-theme", saved);
  // `system` and the missing-key case both mean "follow OS preference"
  // — leave data-theme unset so the @media (prefers-color-scheme)
  // rules in css.py drive the palette.
  syncHljsTheme();
  // #ui-h6 (#567): keep the page palette in sync if the OS theme
  // changes WHILE we're on `system` mode. Without this listener, a
  // user who toggles their OS dark mode mid-session sees the page
  // stay on whatever it was rendered with.
  if (window.matchMedia) {
    try {
      window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", function () {
        let s = null;
        try { s = localStorage.getItem("llmwiki-theme"); } catch (e) {}
        if (s !== "dark" && s !== "light") syncHljsTheme();
      });
    } catch (e) { /* old Safari uses addListener */ }
  }
  document.addEventListener("DOMContentLoaded", function () {
    syncHljsTheme();
    const btn = document.getElementById("theme-toggle");
    if (!btn) return;
    // #ui-h8 (#568): aria state mirrors the current cycle position so
    // assistive tech announces what's pinned, not just "pressed".
    // #v1378-review: aria-pressed collapses 3 states (system / dark /
    // light) to 2 (true|false) — both "system" and "light" mapped to
    // "false", so a screen-reader user couldn't tell which state they
    // were in. Switched to a dynamic aria-label describing the
    // current theme + the next-tap action. aria-pressed is also kept
    // for back-compat with anything reading the binary signal.
    function syncAriaState() {
      let stored = null;
      try { stored = localStorage.getItem("llmwiki-theme"); } catch (e) {}
      const isDark = (root.getAttribute("data-theme") || (
        (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) ? "dark" : "light"
      )) === "dark";
      btn.setAttribute("aria-pressed", isDark ? "true" : "false");
      const labels = {
        dark: "Theme: dark — click for light",
        light: "Theme: light — click for system default",
      };
      const systemLabel = "Theme: follows system — click for dark";
      btn.setAttribute(
        "aria-label",
        labels[stored] || systemLabel,
      );
    }
    const syncAriaPressed = syncAriaState; // alias kept for older call sites
    syncAriaPressed();
    btn.addEventListener("click", function () {
      // #ui-h6 (#567): tri-state toggle. The cycle is:
      //   system → dark → light → system → ...
      // `system` means: data-theme attribute removed, palette follows
      // @media (prefers-color-scheme). Pinning a value moves out of
      // system mode; clicking back to system clears the localStorage
      // entry so a fresh tab also follows the OS.
      let stored = null;
      try { stored = localStorage.getItem("llmwiki-theme"); } catch (e) {}
      let next;
      if (stored !== "dark" && stored !== "light") {
        // Currently following system → pin to dark.
        next = "dark";
      } else if (stored === "dark") {
        next = "light";
      } else {
        // stored === "light" → return to system.
        next = null;
      }
      if (next === null) {
        root.removeAttribute("data-theme");
        try { localStorage.removeItem("llmwiki-theme"); } catch (e) {}
      } else {
        root.setAttribute("data-theme", next);
        try { localStorage.setItem("llmwiki-theme", next); } catch (e) {}
      }
      syncHljsTheme();
      syncAriaPressed();
    });
  });
  // Also respond to the mobile bottom nav theme button (bound later in script.js).
  window.__llmwikiSyncHljsTheme = syncHljsTheme;
})();

// ─── #460: Mobile/tablet hamburger nav drawer ─────────────────────────────
// Wires the hamburger button to toggle the drawer with proper aria state.
// ESC closes and returns focus to the hamburger. Click-outside closes.
// Drawer items are real <a>; tabbing flows naturally. No focus trap needed
// because the drawer is non-modal — the rest of the page is still
// interactive when it's open.
(function () {
  document.addEventListener("DOMContentLoaded", function () {
    const btn = document.getElementById("nav-hamburger");
    const drawer = document.getElementById("nav-drawer");
    if (!btn || !drawer) return;
    function setOpen(open) {
      btn.setAttribute("aria-expanded", open ? "true" : "false");
      // #v1378-review: aria-label was static "Open navigation menu"
      // even when the drawer was already open; screen readers
      // announced the wrong action. Toggle it alongside aria-expanded.
      btn.setAttribute(
        "aria-label",
        open ? "Close navigation menu" : "Open navigation menu",
      );
      if (open) drawer.removeAttribute("hidden");
      else drawer.setAttribute("hidden", "");
    }
    btn.addEventListener("click", function () {
      setOpen(btn.getAttribute("aria-expanded") !== "true");
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && btn.getAttribute("aria-expanded") === "true") {
        setOpen(false);
        btn.focus();
      }
    });
    // Click outside the drawer closes it.
    document.addEventListener("click", function (e) {
      if (btn.getAttribute("aria-expanded") !== "true") return;
      if (drawer.contains(e.target) || btn.contains(e.target)) return;
      setOpen(false);
    });
    // Close after navigating to one of the drawer items so the next page
    // doesn't briefly render with the drawer still open above the fold.
    drawer.querySelectorAll("a").forEach(function (a) {
      a.addEventListener("click", function () { setOpen(false); });
    });
  });
})();

// ─── Reading progress bar ────────────────────────────────────────────────
(function () {
  const bar = document.getElementById("progress-bar");
  if (!bar) return;
  function update() {
    const h = document.documentElement;
    const scrolled = h.scrollTop || document.body.scrollTop;
    const height = (h.scrollHeight || document.body.scrollHeight) - h.clientHeight;
    const pct = height > 0 ? (scrolled / height) * 100 : 0;
    bar.style.width = Math.min(100, Math.max(0, pct)) + "%";
  }
  window.addEventListener("scroll", update, { passive: true });
  update();
})();

// ─── Reading position persistence (session pages only, localStorage) ─────
(function () {
  const CAP_KEY = "llmwiki-scroll-log";
  const MAX_ENTRIES = 30;
  const article = document.querySelector(".content[itemscope]");
  if (!article) return;
  const key = location.pathname;
  let log = {};
  try { log = JSON.parse(localStorage.getItem(CAP_KEY) || "{}") || {}; } catch (e) { log = {}; }

  function restore() {
    // Restore only if deep into page (5%-95%) and no URL hash override
    if (location.hash || !log[key] || typeof log[key].pct !== "number") return;
    const pct = log[key].pct;
    if (pct <= 0.05 || pct >= 0.95) return;
    const h = document.documentElement;
    const height = h.scrollHeight - h.clientHeight;
    window.scrollTo(0, Math.max(0, height * pct));
  }
  // Restore after `load` so images/fonts are in and scrollHeight is accurate.
  // If the document is already loaded (e.g. script injected late), run now.
  if (document.readyState === "complete") restore();
  else window.addEventListener("load", restore);

  let timer = null;
  function save() {
    const h = document.documentElement;
    const height = h.scrollHeight - h.clientHeight;
    const pct = height > 0 ? h.scrollTop / height : 0;
    log[key] = { pct: Math.round(pct * 10000) / 10000, t: Date.now() };
    const entries = Object.entries(log);
    if (entries.length > MAX_ENTRIES) {
      entries.sort(function (a, b) { return (b[1].t || 0) - (a[1].t || 0); });
      log = {};
      entries.slice(0, MAX_ENTRIES).forEach(function (e) { log[e[0]] = e[1]; });
    }
    try { localStorage.setItem(CAP_KEY, JSON.stringify(log)); } catch (e) { /* quota exceeded */ }
  }
  window.addEventListener("scroll", function () {
    if (timer) return;
    timer = setTimeout(function () { timer = null; save(); }, 400);
  }, { passive: true });
})();

// ─── TOC sidebar + scroll-spy (session pages only, desktop only) ─────────
(function () {
  document.addEventListener("DOMContentLoaded", function () {
    const article = document.querySelector(".content[itemscope]");
    if (!article) return;
    const headings = article.querySelectorAll("h2[id], h3[id], h4[id]");
    if (headings.length < 3) return;
    const aside = document.createElement("aside");
    aside.className = "toc-sidebar";
    aside.setAttribute("aria-label", "Page contents");
    const title = document.createElement("div");
    title.className = "toc-title";
    title.textContent = "On this page";
    aside.appendChild(title);
    const ul = document.createElement("ul");
    const linkMap = new Map();
    headings.forEach(function (h) {
      const li = document.createElement("li");
      li.className = "toc-" + h.tagName.toLowerCase();
      const a = document.createElement("a");
      a.href = "#" + h.id;
      a.className = "toc-link";
      // The `toc` markdown extension appends a permalink anchor; strip its text.
      const clean = (h.textContent || "").replace(/\u00b6\s*$/, "").trim();
      a.textContent = clean;
      a.title = clean;
      li.appendChild(a);
      ul.appendChild(li);
      linkMap.set(h.id, a);
    });
    aside.appendChild(ul);
    document.body.appendChild(aside);
    // Scroll-spy via IntersectionObserver
    if (!("IntersectionObserver" in window)) return;
    const visible = new Set();
    function clearActive() { linkMap.forEach(function (a) { a.classList.remove("active"); }); }
    function setActive(id) {
      const link = linkMap.get(id);
      if (link) link.classList.add("active");
    }
    function applySpy() {
      clearActive();
      // Near-bottom fallback: the rootMargin creates a dead zone at the bottom
      // of the page, so the last heading would otherwise never activate.
      const doc = document.documentElement;
      const atBottom = (window.innerHeight + window.scrollY) >= (doc.scrollHeight - 24);
      if (atBottom) {
        setActive(headings[headings.length - 1].id);
        return;
      }
      if (visible.size > 0) {
        for (const h of headings) {
          if (visible.has(h.id)) { setActive(h.id); return; }
        }
      }
    }
    const obs = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) visible.add(e.target.id);
        else visible.delete(e.target.id);
      });
      applySpy();
    }, { rootMargin: "-80px 0px -70% 0px", threshold: 0 });
    headings.forEach(function (h) { obs.observe(h); });
    // Scroll listener handles the bottom-of-page edge case.
    window.addEventListener("scroll", applySpy, { passive: true });
  });
})();

// ─── Mobile bottom nav active-state + button wiring ──────────────────────
(function () {
  document.addEventListener("DOMContentLoaded", function () {
    // Mark the active link based on current path
    const path = location.pathname;
    document.querySelectorAll(".mobile-bottom-nav .mbn-link[data-page]").forEach(function (a) {
      const page = a.getAttribute("data-page");
      if (page === "home" && (path.endsWith("/") || path.endsWith("/index.html"))) a.classList.add("active");
      else if (page === "projects" && path.indexOf("/projects/") !== -1) a.classList.add("active");
      else if (page === "sessions" && path.indexOf("/sessions/") !== -1) a.classList.add("active");
    });
    // Wire the search button — delegate to the header palette trigger so that
    // the existing openPalette() runs (clears input, loads index, renders).
    const searchBtn = document.getElementById("mbn-search");
    if (searchBtn) {
      searchBtn.addEventListener("click", function () {
        const trigger = document.getElementById("open-palette");
        if (trigger) trigger.click();
      });
    }
    // Wire the theme button to toggle
    const themeBtn = document.getElementById("mbn-theme");
    if (themeBtn) {
      // #v1378-review: same dynamic aria-label treatment as the
      // desktop button — aria-pressed alone collapses the tri-state
      // (system / dark / light) into a binary signal. The label
      // describes the current state plus the next-tap action.
      function _mbnSyncPressed() {
        let stored = null;
        try { stored = localStorage.getItem("llmwiki-theme"); } catch (e) { /* private mode */ }
        const isDark = (document.documentElement.getAttribute("data-theme") || (
          (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) ? "dark" : "light"
        )) === "dark";
        themeBtn.setAttribute("aria-pressed", isDark ? "true" : "false");
        const labels = {
          dark: "Theme: dark — tap for light",
          light: "Theme: light — tap for system default",
        };
        const systemLabel = "Theme: follows system — tap for dark";
        themeBtn.setAttribute("aria-label", labels[stored] || systemLabel);
      }
      _mbnSyncPressed();
      themeBtn.addEventListener("click", function () {
        // Post-final-review: mirror the desktop tri-state cycle
        // (system → dark → light → system) instead of a binary
        // dark/light flip. The old binary path would silently move
        // the user out of "system" mode on the first tap and there
        // was no way back from the mobile menu — desktop and mobile
        // diverged behaviorally. Cycle source-of-truth is desktop.
        const root = document.documentElement;
        let stored = null;
        try { stored = localStorage.getItem("llmwiki-theme"); } catch (e) { /* private mode */ }
        let next;
        if (stored !== "dark" && stored !== "light") {
          next = "dark";
        } else if (stored === "dark") {
          next = "light";
        } else {
          next = null; // back to system
        }
        if (next === null) {
          root.removeAttribute("data-theme");
          try { localStorage.removeItem("llmwiki-theme"); } catch (e) { /* private mode */ }
        } else {
          root.setAttribute("data-theme", next);
          try { localStorage.setItem("llmwiki-theme", next); } catch (e) { /* private mode */ }
        }
        if (window.__llmwikiSyncHljsTheme) window.__llmwikiSyncHljsTheme();
        _mbnSyncPressed();
      });
    }
  });
})();

// ─── Copy-as-markdown (inline handler) ───────────────────────────────────
function copyMarkdown(btn) {
  const ta = btn.parentElement.querySelector(".md-source");
  if (!ta) return;
  const text = ta.value.replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&amp;/g, "&").replace(/&quot;/g, '"').replace(/&#39;/g, "'");
  const finish = function (ok) {
    btn.textContent = ok ? "Copied!" : "Failed";
    btn.classList.add("copied");
    setTimeout(function () { btn.textContent = "Copy as markdown"; btn.classList.remove("copied"); }, 1800);
  };
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(function () { finish(true); }, function () { finish(false); });
  } else {
    const tmp = document.createElement("textarea");
    tmp.value = text; tmp.style.position = "fixed"; tmp.style.left = "-9999px";
    document.body.appendChild(tmp); tmp.select();
    try { document.execCommand("copy"); finish(true); } catch (e) { finish(false); }
    document.body.removeChild(tmp);
  }
}

// #36: copy the `cd … && claude --resume …` one-liner from a session page.
function copyResume(btn) {
  const wrap = btn.closest(".resume-command");
  if (!wrap) return;
  const code = wrap.querySelector(".resume-cmd-text");
  if (!code) return;
  const text = code.textContent || "";
  const finish = function (ok) {
    btn.textContent = ok ? "Copied!" : "Failed";
    btn.classList.add("copied");
    setTimeout(function () { btn.textContent = "Copy"; btn.classList.remove("copied"); }, 1800);
  };
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(function () { finish(true); }, function () { finish(false); });
  } else {
    const tmp = document.createElement("textarea");
    tmp.value = text; tmp.style.position = "fixed"; tmp.style.left = "-9999px";
    document.body.appendChild(tmp); tmp.select();
    try { document.execCommand("copy"); finish(true); } catch (e) { finish(false); }
    document.body.removeChild(tmp);
  }
}

// ─── Copy-code buttons on every <pre> ────────────────────────────────────
document.addEventListener("DOMContentLoaded", function () {
  document.querySelectorAll(".content pre").forEach(function (pre) {
    if (pre.parentElement && pre.parentElement.classList.contains("code-wrap")) return;
    const wrap = document.createElement("div"); wrap.className = "code-wrap";
    pre.parentNode.insertBefore(wrap, pre);
    wrap.appendChild(pre);
    const btn = document.createElement("button");
    btn.className = "copy-code-btn"; btn.type = "button"; btn.textContent = "Copy";
    btn.addEventListener("click", function () {
      const code = pre.querySelector("code");
      const text = code ? code.innerText : pre.innerText;
      const finish = function (ok) {
        btn.textContent = ok ? "Copied!" : "Failed"; btn.classList.add("copied");
        setTimeout(function () { btn.textContent = "Copy"; btn.classList.remove("copied"); }, 1500);
      };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(function () { finish(true); }, function () { finish(false); });
      } else {
        const tmp = document.createElement("textarea");
        tmp.value = text; tmp.style.position = "fixed"; tmp.style.left = "-9999px";
        document.body.appendChild(tmp); tmp.select();
        try { document.execCommand("copy"); finish(true); } catch (e) { finish(false); }
        document.body.removeChild(tmp);
      }
    });
    wrap.appendChild(btn);
  });
});

// ─── Auto-collapse long tool results into <details> ──────────────────────
// #476: the summary used to read "Tool results (544 chars) — click to
// expand" — pure char-count, no signal. Now extracts the first non-
// blank line as a preview, detects ok/error from a leading `(ok)` or
// `(ERROR)` marker the markdown emit puts in, and counts result lines.
// Renders as a richer card: `[ok] preview text · 412 lines · click to
// expand`. Keeps the same <details>/<summary> structure so existing CSS
// + a11y plumbing continues to work.
document.addEventListener("DOMContentLoaded", function () {
  const markers = document.querySelectorAll(".content p strong");
  markers.forEach(function (s) {
    const text = (s.textContent || "").trim();
    if (text !== "Tool results:") return;
    const p = s.closest("p");
    if (!p) return;
    let next = p.nextElementSibling;
    if (!next) return;
    const combinedText = (next.innerText || "").trim();
    if (combinedText.length < 500) return;

    // Outcome detection: the markdown emit prepends "→ result (ok):" or
    // "→ result (ERROR):" to each block. First match wins.
    const outcome = /\(ERROR\)/.test(combinedText) ? "error" : "ok";
    // Preview: first non-blank line, stripped of "→ result (ok):" prefix
    // and arrow indent. Truncate at 80 chars on a word boundary.
    const lines = combinedText.split(/\r?\n/);
    let preview = "";
    for (const raw of lines) {
      const line = raw.replace(/^\s*→\s*result\s*\((?:ok|ERROR)\):\s*/, "").trim();
      if (line) { preview = line; break; }
    }
    if (preview.length > 80) {
      const cut = preview.lastIndexOf(" ", 77);
      preview = (cut > 40 ? preview.slice(0, cut) : preview.slice(0, 77)) + "...";
    }
    const lineCount = lines.length;

    // Wrap next element in a <details>.
    const det = document.createElement("details");
    det.className = "collapsible-result outcome-" + outcome;
    const sum = document.createElement("summary");
    // Build the summary as DOM nodes (not innerHTML) so a malicious
    // preview can't inject markup.
    const badge = document.createElement("span");
    badge.className = "tool-result-badge tool-result-" + outcome;
    badge.textContent = outcome === "error" ? "ERROR" : "ok";
    sum.appendChild(badge);
    if (preview) {
      const previewEl = document.createElement("span");
      previewEl.className = "tool-result-preview";
      previewEl.textContent = " " + preview;
      sum.appendChild(previewEl);
    }
    const meta = document.createElement("span");
    meta.className = "tool-result-meta muted";
    meta.textContent = " · " + lineCount + (lineCount === 1 ? " line" : " lines") +
                       " · " + combinedText.length + " chars";
    sum.appendChild(meta);
    det.appendChild(sum);
    next.parentNode.insertBefore(det, next);
    det.appendChild(next);
  });
});

// ─── Visible error reporting (#20) ─────────────────────────────────────
// Runtime failures used to be swallowed by bare `.catch()` handlers, so a
// broken search index looked exactly like a corpus with no matches. Anything
// that fails at runtime now says so on the page, not just in the console.
(function () {
  var seen = {};
  var listEl = null;

  function bar() {
    if (listEl) return listEl;
    var wrap = document.createElement("div");
    wrap.id = "llmwiki-errors";
    wrap.setAttribute("role", "alert");
    // Styled inline on purpose: an error surface must not depend on the
    // stylesheet it might itself be reporting the failure of.
    wrap.style.cssText = "position:fixed;left:0;right:0;bottom:0;z-index:9999;" +
      "background:#7f1d1d;color:#fff;font:13px/1.5 ui-monospace,monospace;" +
      "padding:10px 40px 10px 14px;max-height:40vh;overflow:auto;" +
      "box-shadow:0 -2px 12px rgba(0,0,0,.4)";
    listEl = document.createElement("div");
    wrap.appendChild(listEl);
    var close = document.createElement("button");
    close.textContent = "×";
    close.setAttribute("aria-label", "Dismiss errors");
    close.style.cssText = "position:absolute;top:6px;right:10px;background:none;" +
      "border:0;color:#fff;font-size:20px;cursor:pointer;line-height:1";
    close.addEventListener("click", function () { wrap.remove(); listEl = null; seen = {}; });
    wrap.appendChild(close);
    (document.body || document.documentElement).appendChild(wrap);
    return listEl;
  }

  window.__llmwikiReportError = function (context, err) {
    var detail = err && err.message ? err.message : String(err || "unknown error");
    var msg = context + " — " + detail;
    if (seen[msg]) return;          // don't stack duplicates from retries
    seen[msg] = true;
    if (window.console && console.error) console.error("[llmwiki] " + msg);
    try {
      var row = document.createElement("div");
      row.textContent = "⚠ " + msg;
      bar().appendChild(row);
    } catch (e) {
      // DOM not ready (or unavailable) — the console line above still stands.
    }
  };
})();

// ─── Runtime data loader (#20) ─────────────────────────────────────────
// Data is loaded by injecting <script src>, never by fetch(). Browsers block
// fetch/XHR against file:// URLs, so a site opened straight from disk would
// otherwise get an empty search index with no visible symptom. Script
// execution *is* allowed on file://, so one code path covers served + local.
(function () {
  var pending = {};
  window.llmwikiData = window.llmwikiData || {};

  window.__llmwikiLoadData = function (url, key) {
    if (window.llmwikiData[key] !== undefined) {
      return Promise.resolve(window.llmwikiData[key]);
    }
    if (pending[key]) return pending[key];
    pending[key] = new Promise(function (resolve, reject) {
      var s = document.createElement("script");
      s.src = url;
      s.async = true;
      s.onload = function () {
        if (window.llmwikiData[key] === undefined) {
          reject(new Error(url + " loaded but did not define " + key));
        } else {
          resolve(window.llmwikiData[key]);
        }
      };
      s.onerror = function () { reject(new Error("could not load " + url)); };
      (document.head || document.documentElement).appendChild(s);
    });
    return pending[key];
  };

  // Where the search payloads live. Prefer the explicit global the build
  // emits; fall back to rewriting the .json URL so a page built before #20
  // still resolves a sensible path.
  window.__llmwikiIndexJsUrl = function () {
    if (window.LLMWIKI_INDEX_JS_URL) return window.LLMWIKI_INDEX_JS_URL;
    var json = window.LLMWIKI_INDEX_URL || "search-index.json";
    return json.replace(/\.json$/, ".js");
  };
})();

// ─── Command palette (Cmd+K) + search index loader ─────────────────────
(function () {
  let idx = null;
  let idxPromise = null;
  let metaEntries = null;  // project + page entries (loaded first, fast)
  let activeIdx = 0;
  let currentResults = [];
  let idxFailed = false;   // index unreachable — every search is meaningless
  let idxPartial = false;  // some chunks missing — results are incomplete

  // Lazy-chunked loader (#47): loads the small meta index first (projects +
  // static pages), then pulls per-project session chunks in parallel on first
  // demand. Backwards-compatible with the old flat-array format. Data arrives
  // via script injection rather than fetch so file:// works too (#20).
  function loadIndex() {
    if (idx) return Promise.resolve(idx);
    if (idxPromise) return idxPromise;
    const jsUrl = window.__llmwikiIndexJsUrl();
    const base = jsUrl.substring(0, jsUrl.lastIndexOf("/") + 1);
    idxPromise = window.__llmwikiLoadData(jsUrl, "search-index")
      .then(function (data) {
        // Old format: flat array → return as-is
        if (Array.isArray(data)) { idx = data; return idx; }
        // New format: {entries: [...], _chunks: ["search-chunks/foo.json", ...]}
        metaEntries = data.entries || [];
        var chunkUrls = data._chunks || [];
        if (!chunkUrls.length) { idx = metaEntries; return idx; }
        return Promise.all(chunkUrls.map(function (cu) {
          // The manifest lists .json paths; the executable twin sits beside
          // it and is keyed by that same manifest path.
          return window.__llmwikiLoadData(base + cu.replace(/\.json$/, ".js"), cu)
            .catch(function (e) {
              // One bad chunk degrades search rather than killing it — but
              // the user is told the results are incomplete.
              idxPartial = true;
              window.__llmwikiReportError("Search chunk " + cu + " failed to load", e);
              return [];
            });
        })).then(function (chunks) {
          idx = metaEntries.slice();
          chunks.forEach(function (c) {
            if (Array.isArray(c)) { for (var i = 0; i < c.length; i++) idx.push(c[i]); }
          });
          return idx;
        });
      })
      .catch(function (e) {
        idxFailed = true;
        window.__llmwikiReportError("Search index failed to load", e);
        idx = [];
        return idx;
      });
    return idxPromise;
  }
  // Expose the shared loader so wikilink-preview + related-pages can reuse it
  window.__llmwikiLoadIndex = loadIndex;

  // Return the meta entries (projects + pages) synchronously if available,
  // otherwise trigger a full load. Used for instant palette rendering before
  // session chunks arrive.
  function getMetaSync() { return metaEntries || idx || []; }

  function score(entry, query) {
    if (!query) return 0;
    const q = query.toLowerCase();
    const title = (entry.title || "").toLowerCase();
    const project = (entry.project || "").toLowerCase();
    const body = (entry.body || "").toLowerCase();
    let s = 0;
    if (title === q) s += 100;
    else if (title.indexOf(q) === 0) s += 60;
    else if (title.indexOf(q) !== -1) s += 40;
    if (project.indexOf(q) !== -1) s += 20;
    if (body.indexOf(q) !== -1) s += 10;
    // Token match
    const tokens = q.split(/\s+/).filter(Boolean);
    let allMatch = true;
    tokens.forEach(function (t) {
      if (title.indexOf(t) === -1 && project.indexOf(t) === -1 && body.indexOf(t) === -1) allMatch = false;
    });
    if (allMatch && tokens.length > 1) s += 30;
    return s;
  }

  // v0.8 (#97): Dataview-style structured queries. Users can type
  // key:value pairs alongside free text to filter by metadata:
  //   type:session project:llm-wiki model:claude date:>2026-03-01 sort:date rust
  // Supported keys: type, project, model, date (range with > / <), tags, sort
  // Anything that doesn't match key:value is treated as free-text fuzzy search.
  function parseStructuredQuery(raw) {
    var filters = {};
    var freeText = [];
    var tokens = raw.split(/\s+/).filter(Boolean);
    tokens.forEach(function (t) {
      var m = t.match(/^(type|project|model|date|tags|sort):(.+)$/i);
      if (m) { filters[m[1].toLowerCase()] = m[2]; }
      else { freeText.push(t); }
    });
    return { filters: filters, freeText: freeText.join(" ") };
  }

  function matchesFilters(entry, filters) {
    if (filters.type && (entry.type || "").toLowerCase() !== filters.type.toLowerCase()) return false;
    if (filters.project && (entry.project || "").toLowerCase().indexOf(filters.project.toLowerCase()) === -1) return false;
    if (filters.model && (entry.model || "").toLowerCase().indexOf(filters.model.toLowerCase()) === -1) return false;
    if (filters.tags) {
      var want = filters.tags.toLowerCase();
      var entryBody = ((entry.body || "") + " " + (entry.title || "")).toLowerCase();
      if (entryBody.indexOf(want) === -1) return false;
    }
    if (filters.date) {
      var d = entry.date || "";
      var op = filters.date.charAt(0);
      if (op === ">" && d <= filters.date.substring(1)) return false;
      if (op === "<" && d >= filters.date.substring(1)) return false;
      if (op !== ">" && op !== "<" && d.indexOf(filters.date) === -1) return false;
    }
    return true;
  }

  function search(query) {
    if (!idx) return [];
    if (!query) return idx.slice(0, 10);
    var parsed = parseStructuredQuery(query);
    var filtered = idx;
    if (Object.keys(parsed.filters).length > 0) {
      filtered = idx.filter(function (e) { return matchesFilters(e, parsed.filters); });
    }
    var sortKey = parsed.filters.sort;
    if (sortKey === "date") {
      return filtered
        .slice()
        .sort(function (a, b) { return (b.date || "").localeCompare(a.date || ""); })
        .slice(0, 20);
    }
    if (!parsed.freeText) return filtered.slice(0, 20);
    return filtered
      .map(function (e) { return { entry: e, score: score(e, parsed.freeText) }; })
      .filter(function (r) { return r.score > 0; })
      .sort(function (a, b) { return b.score - a.score; })
      .slice(0, 15)
      .map(function (r) { return r.entry; });
  }

  function renderResults(results) {
    const ul = document.getElementById("palette-results");
    if (!ul) return;
    currentResults = results;
    activeIdx = 0;
    // #20: an unreachable index produces zero matches for every query, which
    // is indistinguishable from an empty corpus. Say which one it is.
    if (!results.length && (idxFailed || idxPartial)) {
      ul.innerHTML = '<li class="palette-note">' + escapeHtml(idxFailed
        ? "Search data could not be loaded — this page is broken, not empty."
        : "No matches, but part of the search data failed to load.") + '</li>';
      currentResults = [];
      return;
    }
    ul.innerHTML = results.map(function (r, i) {
      const meta = [r.project, r.date, r.model].filter(Boolean).join(" · ");
      return '<li data-i="' + i + '" class="' + (i === 0 ? 'active' : '') + '">' +
        '<span class="result-type">' + (r.type || 'page') + '</span>' +
        '<span class="result-title">' + escapeHtml(r.title) + '</span>' +
        (meta ? '<div class="result-meta">' + escapeHtml(meta) + '</div>' : '') +
        '</li>';
    }).join("");
    ul.querySelectorAll("li").forEach(function (li) {
      li.addEventListener("click", function () {
        const i = parseInt(li.getAttribute("data-i"));
        openResult(i);
      });
    });
  }

  function escapeHtml(s) {
    return String(s || "").replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function openResult(i) {
    if (!currentResults[i]) return;
    const r = currentResults[i];
    // #277: slash commands don't have URLs — copy the command text
    // to the clipboard + flash a hint instead of navigating.
    if (r.type === "slash" || !r.url) {
      try { navigator.clipboard && navigator.clipboard.writeText(r.title); } catch (e) {}
      const input = document.getElementById("palette-input");
      if (input) { input.value = r.title; input.placeholder = "copied — paste inside Claude Code"; }
      return;
    }
    const pageUrl = window.LLMWIKI_INDEX_URL || "";
    // Compute base dir from current page URL
    const pathPrefix = pageUrl.substring(0, pageUrl.lastIndexOf("/") + 1) || "";
    window.location.href = pathPrefix + r.url;
  }

  // #478, #479: dialog focus + inert helpers shared by palette + help.
  // Stash who opened the dialog so we can restore focus on close.
  // Apply `inert` to every direct child of <body> EXCEPT the dialog
  // itself so AT users can't tab into the page chrome behind the
  // backdrop (the previous aria-hidden gate left siblings reachable).
  //
  // Post-review: stash is a Map keyed by dialog.id so opening a second
  // dialog while the first is still open doesn't clobber the first
  // dialog's restoration target. Equally, inert is only removed from
  // siblings that are NOT themselves currently-open dialogs, so closing
  // help while palette is still open doesn't strip the palette's inert
  // wrapping of the rest of the chrome.
  var __dialogLastFocus = new Map();
  function __getInertSiblings(dialog) {
    return Array.prototype.filter.call(
      document.body.children,
      function (el) { return el !== dialog; }
    );
  }
  function __isOpenDialog(el) {
    return el && el.classList && el.classList.contains("open") &&
           (el.id === "palette" || el.id === "help-dialog");
  }
  function __isDialogOpen(dialog) {
    return dialog && dialog.classList.contains("open");
  }
  function __getFocusable(container) {
    return Array.prototype.filter.call(
      container.querySelectorAll(
        'a[href], button:not([disabled]), input:not([disabled]), ' +
        'select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
      ),
      function (el) { return !el.hasAttribute("disabled") && el.offsetParent !== null; }
    );
  }
  function __syncTriggerAriaExpanded(dialog, value) {
    // #ui-h8 (#568): trigger button's aria-expanded must mirror the
    // dialog's open/closed state so AT users hear the right thing
    // when they re-focus the trigger.
    if (!dialog || !dialog.id) return;
    const trigger = document.querySelector('[aria-controls="' + dialog.id + '"]');
    if (trigger) trigger.setAttribute("aria-expanded", value ? "true" : "false");
  }
  function __openDialog(dialog, firstFocus) {
    if (!dialog || dialog.classList.contains("open")) return;
    if (dialog.id) __dialogLastFocus.set(dialog.id, document.activeElement);
    dialog.classList.add("open");
    __syncTriggerAriaExpanded(dialog, true);
    __getInertSiblings(dialog).forEach(function (s) { s.setAttribute("inert", ""); });
    if (firstFocus && firstFocus.focus) firstFocus.focus();
  }
  function __closeDialog(dialog) {
    if (!dialog || !dialog.classList.contains("open")) return;
    dialog.classList.remove("open");
    __syncTriggerAriaExpanded(dialog, false);
    // Only strip inert from siblings that are NOT themselves an open
    // dialog — otherwise closing the help-dialog while palette is open
    // re-exposes the palette's inert chrome guard.
    __getInertSiblings(dialog).forEach(function (s) {
      if (!__isOpenDialog(s)) s.removeAttribute("inert");
    });
    var lf = dialog.id ? __dialogLastFocus.get(dialog.id) : null;
    if (lf && lf.focus) {
      try { lf.focus(); } catch (e) { /* trigger gone */ }
    }
    if (dialog.id) __dialogLastFocus.delete(dialog.id);
  }
  // Trap Tab + Shift+Tab inside `dialog` so focus can't escape into
  // the inert page chrome and become visually invisible.
  function __trapTab(dialog) {
    return function (e) {
      if (e.key !== "Tab" || !__isDialogOpen(dialog)) return;
      const focusable = __getFocusable(dialog);
      if (focusable.length === 0) { e.preventDefault(); return; }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault(); last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault(); first.focus();
      }
    };
  }

  function openPalette() {
    const p = document.getElementById("palette");
    if (!p) return;
    const input = document.getElementById("palette-input");
    if (input) { input.value = ""; }
    __openDialog(p, input);
    // Show meta entries immediately while chunks load
    var meta = getMetaSync();
    if (meta.length && !idx) renderResults(meta.slice(0, 10));
    loadIndex().then(function () { renderResults(search(input ? input.value : "")); });
  }

  function closePalette() {
    const p = document.getElementById("palette");
    __closeDialog(p);
  }

  function openHelp() {
    const d = document.getElementById("help-dialog");
    if (!d) return;
    const closeBtn = document.getElementById("help-close");
    __openDialog(d, closeBtn);
  }
  function closeHelp() {
    const d = document.getElementById("help-dialog");
    __closeDialog(d);
  }

  document.addEventListener("DOMContentLoaded", function () {
    // Wire up buttons
    const openBtn = document.getElementById("open-palette");
    if (openBtn) openBtn.addEventListener("click", openPalette);

    const backdrop = document.getElementById("palette-backdrop");
    if (backdrop) backdrop.addEventListener("click", closePalette);

    const input = document.getElementById("palette-input");
    if (input) {
      input.addEventListener("input", function () { renderResults(search(input.value)); });
      input.addEventListener("keydown", function (e) {
        const items = document.querySelectorAll("#palette-results li");
        if (e.key === "ArrowDown") { e.preventDefault(); activeIdx = Math.min(items.length - 1, activeIdx + 1); updateActive(); }
        else if (e.key === "ArrowUp") { e.preventDefault(); activeIdx = Math.max(0, activeIdx - 1); updateActive(); }
        else if (e.key === "Enter") { e.preventDefault(); openResult(activeIdx); }
      });
    }

    const helpBackdrop = document.getElementById("help-backdrop");
    if (helpBackdrop) helpBackdrop.addEventListener("click", closeHelp);
    const helpClose = document.getElementById("help-close");
    if (helpClose) helpClose.addEventListener("click", closeHelp);

    // #479: Tab focus traps. Listening on document so the handler fires
    // even when the focused element is a backdrop / non-focusable.
    const paletteEl = document.getElementById("palette");
    if (paletteEl) document.addEventListener("keydown", __trapTab(paletteEl));
    const helpEl = document.getElementById("help-dialog");
    if (helpEl) document.addEventListener("keydown", __trapTab(helpEl));
  });

  function updateActive() {
    const items = document.querySelectorAll("#palette-results li");
    items.forEach(function (li, i) { li.classList.toggle("active", i === activeIdx); });
    const active = items[activeIdx];
    if (active) active.scrollIntoView({ block: "nearest" });
  }

  // ─── Keyboard shortcuts ─────────────────────────────────────────────────
  let gPressed = false;
  let gPressedTimer = null;
  document.addEventListener("keydown", function (e) {
    const inInput = e.target && (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA" || e.target.tagName === "SELECT");

    // Cmd/Ctrl+K opens palette everywhere
    if ((e.metaKey || e.ctrlKey) && e.key === "k") {
      e.preventDefault();
      openPalette();
      return;
    }
    // Esc closes palette / help / clears focus
    if (e.key === "Escape") {
      const p = document.getElementById("palette");
      const h = document.getElementById("help-dialog");
      // #478: state check now reads the .open class (was aria-hidden).
      if (p && p.classList.contains("open")) { closePalette(); return; }
      if (h && h.classList.contains("open")) { closeHelp(); return; }
      if (inInput) { e.target.blur(); return; }
    }

    // Shortcuts only work when not typing in an input
    if (inInput) return;

    if (e.key === "/") { e.preventDefault(); openPalette(); return; }
    if (e.key === "?") { e.preventDefault(); openHelp(); return; }

    // g-prefix shortcuts
    if (e.key === "g" && !gPressed) {
      gPressed = true;
      gPressedTimer = setTimeout(function () { gPressed = false; }, 1000);
      return;
    }
    if (gPressed) {
      gPressed = false;
      if (gPressedTimer) clearTimeout(gPressedTimer);
      const rel = window.LLMWIKI_INDEX_URL || "";
      const base = rel.substring(0, rel.lastIndexOf("/") + 1);
      if (e.key === "h") { window.location.href = base + "index.html"; return; }
      if (e.key === "p") { window.location.href = base + "projects/index.html"; return; }
      if (e.key === "s") { window.location.href = base + "sessions/index.html"; return; }
    }

    // j/k on sessions table
    const tbody = document.getElementById("sessions-tbody");
    if (tbody && (e.key === "j" || e.key === "k")) {
      e.preventDefault();
      const visibleRows = Array.from(tbody.querySelectorAll("tr")).filter(function (r) { return !r.hidden; });
      if (!visibleRows.length) return;
      let cur = visibleRows.findIndex(function (r) { return r.classList.contains("selected"); });
      if (cur === -1) cur = 0;
      else cur = e.key === "j" ? Math.min(visibleRows.length - 1, cur + 1) : Math.max(0, cur - 1);
      visibleRows.forEach(function (r) { r.classList.remove("selected"); });
      visibleRows[cur].classList.add("selected");
      visibleRows[cur].scrollIntoView({ block: "nearest" });
      // Enter on selected row navigates
    }
    if (e.key === "Enter" && tbody) {
      const sel = tbody.querySelector("tr.selected a");
      if (sel) { window.location.href = sel.href; }
    }
  });
})();

// ─── Sessions table filter bar ────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", function () {
  const tbody = document.getElementById("sessions-tbody");
  if (!tbody) return;
  const fProject = document.getElementById("filter-project");
  const fAgent = document.getElementById("filter-agent");
  const fModel = document.getElementById("filter-model");
  const fFrom = document.getElementById("filter-date-from");
  const fTo = document.getElementById("filter-date-to");
  const fText = document.getElementById("filter-text");
  const fClear = document.getElementById("filter-clear");
  const fCount = document.getElementById("filter-count");

  // #ui-m1 (#572): persist filter selections to sessionStorage so a
  // navigation away + back doesn't lose the user's filter state.
  // sessionStorage (not localStorage) is the right scope: it survives
  // back/forward but clears on tab close, matching user expectations
  // for a transient filter view.
  const STORAGE_KEY = "llmwiki-sessions-filters";
  function _readSaved() {
    try {
      const raw = sessionStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch (e) { return null; }
  }
  function _writeSaved() {
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify({
        p: fProject ? fProject.value : "",
        a: fAgent ? fAgent.value : "",
        m: fModel ? fModel.value : "",
        from: fFrom ? fFrom.value : "",
        to: fTo ? fTo.value : "",
        txt: fText ? fText.value : "",
      }));
    } catch (e) { /* private mode */ }
  }
  // Restore on page load.
  const saved = _readSaved();
  if (saved) {
    if (fProject && saved.p) fProject.value = saved.p;
    if (fAgent && saved.a) fAgent.value = saved.a;
    if (fModel && saved.m) fModel.value = saved.m;
    if (fFrom && saved.from) fFrom.value = saved.from;
    if (fTo && saved.to) fTo.value = saved.to;
    if (fText && saved.txt) fText.value = saved.txt;
  }

  function apply() {
    const p = fProject ? fProject.value : "";
    const a = fAgent ? fAgent.value : "";
    const m = fModel ? fModel.value : "";
    const from = fFrom ? fFrom.value : "";
    const to = fTo ? fTo.value : "";
    const txt = fText ? fText.value.toLowerCase() : "";
    let shown = 0;
    Array.from(tbody.querySelectorAll("tr")).forEach(function (r) {
      const rp = r.getAttribute("data-project") || "";
      const ra = r.getAttribute("data-agent") || "";
      const rm = r.getAttribute("data-model") || "";
      const rd = r.getAttribute("data-date") || "";
      const rs = (r.getAttribute("data-slug") || "").toLowerCase();
      let show = true;
      if (p && rp !== p) show = false;
      if (a && ra !== a) show = false;
      if (m && rm !== m) show = false;
      if (from && rd < from) show = false;
      if (to && rd > to) show = false;
      if (txt && rs.indexOf(txt) === -1) show = false;
      r.hidden = !show;
      if (show) shown++;
    });
    if (fCount) fCount.textContent = shown + " shown";
    _writeSaved();
  }

  [fProject, fAgent, fModel, fFrom, fTo, fText].forEach(function (el) {
    if (el) el.addEventListener("input", apply);
  });
  if (fClear) fClear.addEventListener("click", function () {
    if (fProject) fProject.value = "";
    if (fAgent) fAgent.value = "";
    if (fModel) fModel.value = "";
    if (fFrom) fFrom.value = "";
    if (fTo) fTo.value = "";
    if (fText) fText.value = "";
    try { sessionStorage.removeItem(STORAGE_KEY); } catch (e) {}
    apply();
  });
  apply();
});

// ─── Hover-to-preview wikilinks ───────────────────────────────────────────
// When the user hovers over a wikilink (an <a> whose text starts with "[["
// or whose href is a wiki page), fetch the target's first ~300 chars and
// show a floating preview card. Uses the client-side search index.
(function () {
  let idx = null;
  let previewEl = null;
  let hideTimer = null;

  function getPreviewEl() {
    if (previewEl) return previewEl;
    previewEl = document.createElement("div");
    previewEl.className = "wikilink-preview";
    previewEl.setAttribute("hidden", "");
    previewEl.innerHTML = '<div class="wl-title"></div><div class="wl-body"></div>';
    document.body.appendChild(previewEl);
    previewEl.addEventListener("mouseenter", function () {
      if (hideTimer) { clearTimeout(hideTimer); hideTimer = null; }
    });
    previewEl.addEventListener("mouseleave", function () {
      hidePreview();
    });
    return previewEl;
  }

  function loadIndex() {
    if (idx) return Promise.resolve(idx);
    // Reuse the shared chunked loader from the palette IIFE (#47)
    if (window.__llmwikiLoadIndex) {
      return window.__llmwikiLoadIndex().then(function (data) { idx = data; return idx; });
    }
    return window.__llmwikiLoadData(window.__llmwikiIndexJsUrl(), "search-index")
      .then(function (data) {
        idx = Array.isArray(data) ? data : (data.entries || []);
        return idx;
      })
      .catch(function (e) {
        window.__llmwikiReportError("Wikilink previews unavailable", e);
        idx = [];
        return idx;
      });
  }

  function findEntry(keyOrText) {
    if (!idx) return null;
    const needle = (keyOrText || "").toLowerCase().trim();
    if (!needle) return null;
    // Try exact title match first
    for (const e of idx) {
      if ((e.title || "").toLowerCase() === needle) return e;
    }
    // Fall back to prefix
    for (const e of idx) {
      if ((e.title || "").toLowerCase().startsWith(needle)) return e;
    }
    // Fall back to substring
    for (const e of idx) {
      if ((e.title || "").toLowerCase().indexOf(needle) !== -1) return e;
    }
    return null;
  }

  function showPreview(target, entry) {
    const el = getPreviewEl();
    el.querySelector(".wl-title").textContent = entry.title || entry.id || "";
    el.querySelector(".wl-body").textContent = (entry.body || "").slice(0, 300);
    // Position below the target
    const rect = target.getBoundingClientRect();
    el.style.position = "fixed";
    el.style.top = (rect.bottom + 8) + "px";
    el.style.left = Math.min(window.innerWidth - 380, Math.max(16, rect.left)) + "px";
    el.removeAttribute("hidden");
  }

  function hidePreview() {
    if (previewEl) previewEl.setAttribute("hidden", "");
  }

  function attach(a) {
    const text = (a.textContent || "").trim();
    // Only target links that look like wikilinks (starting with [[) or that
    // point to another page in site/sessions, site/projects, or site/.
    const isWiki = text.startsWith("[[") || /sessions\/|projects\//.test(a.getAttribute("href") || "");
    if (!isWiki) return;
    let key = text.replace(/^\[\[|\]\]$/g, "").trim();
    if (!key) {
      // Derive from href
      const href = a.getAttribute("href") || "";
      const m = href.match(/([^/]+)\.html$/);
      if (m) key = m[1];
    }
    if (!key) return;

    function _show() {
      if (hideTimer) { clearTimeout(hideTimer); hideTimer = null; }
      loadIndex().then(function () {
        const entry = findEntry(key);
        if (entry) showPreview(a, entry);
      });
    }
    function _hide() {
      hideTimer = setTimeout(hidePreview, 200);
    }
    // #ui-h13 (#570): keyboard parity for the hover preview. Show on
    // focus + hide on blur so a Tab-only user gets the same affordance
    // a mouse user gets. ESC dismisses immediately and returns nothing
    // to do (focus is already on the link).
    a.addEventListener("mouseenter", _show);
    a.addEventListener("mouseleave", _hide);
    a.addEventListener("focus", _show);
    a.addEventListener("blur", _hide);
    a.addEventListener("keydown", function (e) {
      if (e.key === "Escape") {
        if (hideTimer) { clearTimeout(hideTimer); hideTimer = null; }
        hidePreview();
      }
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll(".content a").forEach(attach);
  });
})();

// ─── Timeline view on sessions index ──────────────────────────────────────
// Render a compact sparkline above the sessions table showing session count
// per day over the last 60 days.
(function () {
  // Post-final-review: local attribute escaper. The timeline SVG below
  // string-concatenates `data-date` and `data-count` into HTML; while
  // the values come from controlled `data-date` row attributes (built
  // in build.py from frontmatter dates), defense-in-depth escapes them
  // anyway. The palette IIFE has its own `escapeHtml` but it's out of
  // scope here, hence the local copy.
  function escAttr(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  document.addEventListener("DOMContentLoaded", function () {
    const tbody = document.getElementById("sessions-tbody");
    if (!tbody) return;
    // Only run on the sessions index page
    const container = document.querySelector(".section .container");
    if (!container || !container.querySelector(".filter-bar")) return;

    // Collect dates
    const rows = Array.from(tbody.querySelectorAll("tr"));
    const counts = new Map();
    rows.forEach(function (r) {
      const d = r.getAttribute("data-date");
      if (!d) return;
      counts.set(d, (counts.get(d) || 0) + 1);
    });
    if (!counts.size) return;

    // Sort dates ascending
    const dates = Array.from(counts.keys()).sort();
    const maxCount = Math.max(...counts.values());

    // #453: position bars by calendar date so gaps between active days are
    // visible. The previous behaviour stretched dates.length bars across
    // the full width with equal spacing, which hid 6-month gaps. We now
    // compute calendar span (minDate→maxDate) in days and lay bars out
    // proportional to their date offset. Single-day collections fall back
    // to a single centred bar.
    const minDate = new Date(dates[0] + "T00:00:00Z");
    const maxDate = new Date(dates[dates.length - 1] + "T00:00:00Z");
    const dayMs = 86400000;
    const spanDays = Math.round((maxDate - minDate) / dayMs) + 1;

    // Build an SVG sparkline
    const w = 800;
    const h = 60;
    const padX = 4;
    const innerW = w - 2 * padX;
    const slotW = spanDays > 1 ? innerW / spanDays : innerW;
    const bars = dates.map(function (d) {
      const count = counts.get(d);
      const offset = spanDays > 1
        ? Math.round((new Date(d + "T00:00:00Z") - minDate) / dayMs)
        : 0;
      const x = spanDays > 1 ? padX + offset * slotW : padX + innerW / 2 - 2;
      const barW = Math.max(2, slotW - 1);
      const barH = (count / maxCount) * (h - 16);
      const y = h - barH - 4;
      return '<rect x="' + x + '" y="' + y + '" width="' + barW + '" height="' + barH +
             '" fill="var(--accent)" opacity="0.7" data-date="' + escAttr(d) +
             '" data-count="' + escAttr(count) + '">' +
             '<title>' + escAttr(d) + ' — ' + escAttr(count) +
             (count === 1 ? ' session' : ' sessions') + '</title></rect>';
    }).join("");

    const svg =
      '<svg viewBox="0 0 ' + w + ' ' + h + '" preserveAspectRatio="none" ' +
      'style="width:100%;height:' + h + 'px;display:block" aria-label="Session activity timeline">' +
      bars + '</svg>';

    // #453: label now shows calendar span (matches the geometry above) plus
    // active-day count and peak so users can read both stories from one line.
    const labelText = spanDays === 1
      ? 'Activity timeline · 1 day · peak ' + maxCount + (maxCount === 1 ? ' session' : ' sessions')
      : 'Activity timeline · ' + spanDays + ' days · ' + dates.length +
        ' active · peak ' + maxCount + (maxCount === 1 ? ' session/day' : ' sessions/day');

    // Create the timeline block. #v1378-review: previously assigned
    // the label + svg via innerHTML, which interpolated `labelText`
    // (currently number-only — safe today) into HTML without escaping.
    // Defense-in-depth: build the label as a real element with
    // textContent so a future change feeding a user-derived string
    // into the label can't introduce XSS. The svg string itself is
    // already escaped via escAttr() at every data-* interpolation
    // and uses only static structural markup elsewhere.
    const tl = document.createElement("div");
    tl.className = "timeline-block";
    const labelEl = document.createElement("div");
    labelEl.className = "timeline-label muted";
    labelEl.textContent = labelText;
    tl.appendChild(labelEl);
    tl.insertAdjacentHTML("beforeend", svg);

    // Show the day count in the label on hover/focus/click (native
    // <title> covers the browser tooltip; the label is the persistent cue).
    const svgEl = tl.querySelector("svg");
    function showBarValue(rect) {
      const d = rect.getAttribute("data-date") || "";
      const c = rect.getAttribute("data-count") || "0";
      labelEl.textContent = d + " · " + c + (c === "1" ? " session" : " sessions");
    }
    function resetLabel() {
      labelEl.textContent = labelText;
    }
    if (svgEl) {
      svgEl.addEventListener("mouseover", function (ev) {
        const r = ev.target.closest("rect");
        if (r) showBarValue(r);
      });
      svgEl.addEventListener("mouseout", function (ev) {
        const to = ev.relatedTarget && ev.relatedTarget.closest
          ? ev.relatedTarget.closest("rect") : null;
        if (!to) resetLabel();
      });
      svgEl.addEventListener("focusin", function (ev) {
        const r = ev.target.closest("rect");
        if (r) showBarValue(r);
      });
      svgEl.addEventListener("focusout", resetLabel);
      svgEl.addEventListener("click", function (ev) {
        const r = ev.target.closest("rect");
        if (r) showBarValue(r);
      });
      // Keyboard: make bars focusable so focusin works.
      svgEl.querySelectorAll("rect").forEach(function (r) {
        r.setAttribute("tabindex", "0");
        r.setAttribute("role", "img");
        const d = r.getAttribute("data-date") || "";
        const c = r.getAttribute("data-count") || "0";
        r.setAttribute("aria-label", d + ": " + c + (c === "1" ? " session" : " sessions"));
      });
    }

    // Insert above the filter bar
    const filter = container.querySelector(".filter-bar");
    if (filter) container.insertBefore(tl, filter);
  });
})();

// ─── v0.4: Related pages panel ────────────────────────────────────────────
// On a session page, find 3-5 other sessions that share wikilink targets
// or project, and display them at the bottom under a "Related pages" heading.
(function () {
  document.addEventListener("DOMContentLoaded", function () {
    const article = document.querySelector("article.content");
    if (!article) return;
    // Only on session pages (have a breadcrumb + back-to-project link)
    const backBtn = document.querySelector(".session-actions a.btn");
    if (!backBtn) return;

    // Extract current page metadata from the llmwiki:metadata comment
    const html = document.documentElement.outerHTML;
    const m = html.match(/llmwiki:metadata\n([\s\S]*?)-->/);
    if (!m) return;
    const meta = {};
    m[1].split("\n").forEach(function (line) {
      const idx = line.indexOf(":");
      if (idx > 0) {
        const k = line.slice(0, idx).trim();
        const v = line.slice(idx + 1).trim();
        if (k && v) meta[k] = v;
      }
    });
    const currentProject = meta.project || "";
    const currentSlug = meta.slug || "";
    if (!currentProject) return;

    // Reuse the shared chunked loader (#47) — includes session entries
    var loader = window.__llmwikiLoadIndex
      ? window.__llmwikiLoadIndex()
      : window.__llmwikiLoadData(window.__llmwikiIndexJsUrl(), "search-index")
          .then(function (d) { return Array.isArray(d) ? d : (d.entries || []); });
    loader
      .catch(function (e) {
        window.__llmwikiReportError("Related pages unavailable", e);
        return [];
      })
      .then(function (entries) {
        if (!entries || !entries.length) return;
        // Score each other session: same project = 2 pts, shared wikilink targets = +1 per token
        const scored = entries
          .filter(function (e) {
            return e.type === "session" && e.url && !e.url.endsWith(currentSlug + ".html");
          })
          .map(function (e) {
            let score = 0;
            if (e.project === currentProject) score += 2;
            return { entry: e, score: score };
          })
          .filter(function (s) { return s.score > 0; })
          .sort(function (a, b) { return b.score - a.score; })
          .slice(0, 5);
        if (!scored.length) return;

        // Post-review remediation: title + url + date used to be
        // interpolated into innerHTML without escaping. Build the DOM
        // tree explicitly with createElement / textContent so a malicious
        // session frontmatter title (e.g. "<img src=x onerror=...>") or
        // a `javascript:` URL can't execute in the visitor's browser.
        function _safeHref(raw) {
          // Reject anything that isn't a relative path or http(s).
          // Same-origin checks happen at the browser; we just gate the
          // protocol prefix here to stop `javascript:` / `data:` etc.
          var s = String(raw || "");
          if (/^(javascript|data|vbscript):/i.test(s)) return "#";
          return s;
        }
        const section = document.createElement("div");
        section.className = "related-pages";
        const heading = document.createElement("h3");
        heading.textContent = "Related pages";
        section.appendChild(heading);
        const ul = document.createElement("ul");
        scored.forEach(function (s) {
          const li = document.createElement("li");
          const a = document.createElement("a");
          a.href = _safeHref("../../" + (s.entry.url || ""));
          a.textContent = String(s.entry.title || "");
          li.appendChild(a);
          if (s.entry.date) {
            const span = document.createElement("span");
            span.className = "muted";
            span.textContent = " \u00b7 " + String(s.entry.date);
            li.appendChild(span);
          }
          ul.appendChild(li);
        });
        section.appendChild(ul);
        article.appendChild(section);
      })
      .catch(function () {});
  });
})();

// v0.8 (#64, #72): the v0.4 JS-based tiny-strip heatmap is gone. The 365-day
// GitLab/GitHub-style grid is now rendered at build time as pure SVG by
// llmwiki/viz_heatmap.py and inlined into index.html + each project page.
// The page CSS (--heatmap-0..4) picks up the current theme automatically —
// no JS wiring needed.

// ─── v0.4: Search result highlights ──────────────────────────────────────
// When showing search palette results, highlight the matched query in the
// title and body snippet.
(function () {
  function highlight(text, query) {
    if (!query || !text) return escapeLocalHtml(text);
    const q = query.toLowerCase();
    const lower = text.toLowerCase();
    const i = lower.indexOf(q);
    if (i === -1) return escapeLocalHtml(text);
    return escapeLocalHtml(text.slice(0, i)) +
      '<mark>' + escapeLocalHtml(text.slice(i, i + q.length)) + '</mark>' +
      escapeLocalHtml(text.slice(i + q.length));
  }
  function escapeLocalHtml(s) {
    return String(s || "").replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  // Expose so the palette renderer can call it if it chooses
  window.llmwikiHighlight = highlight;
})();

// ─── Documents tree (lazy load — one payload for all document pages) ───────
(function () {
  function escapeHtml(s) {
    return String(s || "").replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function renderNode(node, prefix, activeRel, pathParts) {
    var html = "<ul>";
    var folders = node.folders || [];
    for (var i = 0; i < folders.length; i++) {
      var folder = folders[i];
      var nextParts = pathParts.concat([folder.name]);
      var isOpen = false;
      if (activeRel) {
        var activeParts = activeRel.split("/");
        isOpen = activeParts.slice(0, nextParts.length).join("/") === nextParts.join("/");
      }
      html += "<li><details" + (isOpen ? " open" : "") + ">"
        + "<summary>" + escapeHtml(folder.name) + "</summary>"
        + renderNode(folder, prefix, activeRel, nextParts)
        + "</details></li>";
    }
    var files = node.files || [];
    for (var j = 0; j < files.length; j++) {
      var f = files[j];
      var cls = (activeRel && f.rel === activeRel)
        ? ' class="active" aria-current="page"' : "";
      html += '<li><a href="' + escapeHtml(prefix + f.href) + '"' + cls + ">"
        + escapeHtml(f.label) + "</a></li>";
    }
    html += "</ul>";
    return html;
  }

  function mountAside(aside) {
    var prefix = aside.getAttribute("data-link-prefix") || "";
    var activeRel = aside.getAttribute("data-active-rel") || "";
    var jsUrl = aside.getAttribute("data-doctree-js") || (prefix + "documents-tree.js");
    var loading = aside.querySelector(".doctree-loading");
    var title = aside.querySelector(".doctree-title");

    function showError(err) {
      window.__llmwikiReportError("Documents tree unavailable", err);
      if (loading) {
        loading.textContent = "Documents tree could not be loaded — this page is broken, not empty.";
        loading.classList.add("doctree-error");
      }
    }

    if (typeof window.__llmwikiLoadData !== "function") {
      showError(new Error("__llmwikiLoadData missing"));
      return;
    }

    window.__llmwikiLoadData(jsUrl, "documents-tree")
      .then(function (tree) {
        if (!tree || (typeof tree !== "object")) {
          throw new Error("documents-tree payload missing or invalid");
        }
        var body = renderNode(tree, prefix, activeRel, []);
        // Replace loading / noscript; keep the title.
        var keep = title ? [title] : [];
        aside.innerHTML = "";
        keep.forEach(function (el) { aside.appendChild(el); });
        if (!tree.folders || !tree.folders.length) {
          if (!tree.files || !tree.files.length) {
            var empty = document.createElement("p");
            empty.className = "muted";
            empty.textContent = "No documents yet.";
            aside.appendChild(empty);
            return;
          }
        }
        var wrap = document.createElement("div");
        wrap.innerHTML = body;
        while (wrap.firstChild) aside.appendChild(wrap.firstChild);
      })
      .catch(showError);
  }

  function init() {
    document.querySelectorAll("[data-doctree-mount]").forEach(mountAside);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();

// ─── v0.4: Deep-link icon next to headings ────────────────────────────────
(function () {
  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll(".content h2[id], .content h3[id], .content h4[id]").forEach(function (h) {
      if (h.querySelector(".deep-link")) return;
      const icon = document.createElement("a");
      icon.className = "deep-link";
      icon.href = "#" + h.id;
      icon.innerHTML = "🔗";
      icon.title = "Copy link to this section";
      icon.addEventListener("click", function (ev) {
        ev.preventDefault();
        const url = window.location.origin + window.location.pathname + "#" + h.id;
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(url).then(function () {
            icon.textContent = "✓";
            setTimeout(function () { icon.textContent = "🔗"; }, 1200);
          });
        }
      });
      h.appendChild(icon);
    });
  });
})();
"""
