"""Graph viewer JavaScript for graph.html (#127).

Extracted from ``llmwiki/graph.py`` ``HTML_TEMPLATE``. Expects the inline
stub in graph.html to define global ``GRAPH`` before this script runs.

Vanilla JS, no framework. vis-network UMD must load first.
"""

from __future__ import annotations

GRAPH_VIEWER_JS = r"""'use strict';
window.__llmwikiGraphViewerLoaded = true;
// Expects global GRAPH from the graph.html inline stub (const GRAPH = …).
// #456: graph used to wire its own #theme-toggle button + #theme-label.
// Both responsibilities now live in the site nav (script.js handles the
// click; CSS variables react to data-theme automatically). Local handler
// removed so two listeners don't fight over the same event.
const root = document.documentElement;

// ─── Check vis-network loaded (local fallback hook) ────────────────────
if (typeof vis === 'undefined') {
  document.getElementById('offline-notice').classList.add('show');
} else {
  main();
}

function main() {
  const cssVar = name =>
    getComputedStyle(document.documentElement).getPropertyValue(name).trim() || '#7c3aed';
  const colors = {
    sources: () => cssVar('--g-node-source'),
    entities: () => cssVar('--g-node-entities'),
    concepts: () => cssVar('--g-node-concepts'),
    syntheses: () => cssVar('--g-node-syntheses'),
    projects: () => cssVar('--g-node-projects'),
    questions: () => cssVar('--g-node-questions'),
    comparisons: () => cssVar('--g-node-comparisons'),
    other: () => cssVar('--g-node-other'),
    root: () => cssVar('--g-node-root'),
    topic: () => cssVar('--g-node-topic'),
  };
  const orphanColor = () => cssVar('--g-orphan');
  const KIND_LABELS = {
    entities: 'Entities', concepts: 'Concepts', projects: 'Projects',
    questions: 'Questions', comparisons: 'Comparisons',
    syntheses: 'Syntheses', sources: 'Sources', other: 'Other',
  };
  const kindLabel = k => KIND_LABELS[k] || k;
  // Singular form of the same label, naming one topic in the side panel as
  // the static page's chip does (topics_page.py `_KIND_LABELS`). Derived from
  // KIND_LABELS so the forms can't drift. 'other' takes the label injected
  // from topics_page.KIND_OTHER_LABEL: no page describes the topic, and that
  // absence is itself worth naming rather than leaving the row out (#108 FR8).
  const kindLabelOne = k => {
    if (!k || k === 'other') return __KIND_OTHER_LABEL__;
    const s = kindLabel(k);
    if (s.endsWith('ies')) return s.slice(0, -3) + 'y';
    if (s.endsWith('ses')) return s.slice(0, -3) + 'sis';
    return s.replace(/s$/, '');
  };
  const kindColor = k => (colors[k] || colors.topic)();
  // Surface viewer failures on the page, not just in the console —
  // script.js owns the banner, so fall back if it hasn't loaded yet.
  const reportGraphError = (context, err) => {
    if (window.__llmwikiReportError) window.__llmwikiReportError(context, err);
    else if (window.console) console.error('[llmwiki] ' + context, err);
  };

  // #54: topic-first mode. Nodes are topics (never sessions); edges are
  // topic↔topic co-occurrences bridged by sessions. Drives sizing, the
  // contextual side panel, and double-click-to-open below.
  const TOPIC = GRAPH.mode === 'topic';
  const SESS = GRAPH.sessions || {};

  // ─── Stats overlay ───────────────────────────────────────────────────
  const stats = GRAPH.stats || {};
  const statsEl = document.getElementById('stats-overlay');
  if (TOPIC) {
    document.getElementById('top-crumbs').textContent =
      (stats.total_topics ?? GRAPH.nodes.length) + ' topics · ' +
      (stats.total_edges ?? GRAPH.edges.length) + ' connections · ' +
      (stats.total_sessions ?? 0) + ' sessions';
    const lg = document.getElementById('legend');
    // One row per kind actually present — a wiki with no concept pages
    // shouldn't advertise a concept swatch.
    const presentKinds = [...new Set(GRAPH.nodes.map(n => n.kind || 'other'))].sort();
    if (lg) lg.innerHTML =
      presentKinds.map(k =>
        '<div class="row"><span class="dot" style="background: ' + kindColor(k) +
        // 'other' reads as the panel and page chip do, not as 'Other'.
        '"></span>' + escapeHtml(k === 'other' ? kindLabelOne(k) : kindLabel(k)) + '</div>').join('') +
      '<div class="row"><span class="dot" style="background: var(--g-edge)"></span>shared sessions</div>' +
      '<div class="row" style="color:var(--g-muted)">size = #sessions</div>';
  } else {
    const pages = stats.total_pages ?? GRAPH.nodes.length;
    const edgeCount = stats.total_edges ?? GRAPH.edges.length;
    const orphans = stats.orphans ?? [];
    document.getElementById('s-pages').textContent = pages;
    document.getElementById('s-edges').textContent = edgeCount;
    document.getElementById('s-orphans').textContent = orphans.length;
    document.getElementById('s-avg').textContent =
      pages > 0 ? (edgeCount / pages).toFixed(2) : '0';
    document.getElementById('top-crumbs').textContent =
      pages + ' pages · ' + edgeCount + ' edges · ' + orphans.length + ' orphans';

    const hubsEl = document.getElementById('s-hubs');
    (stats.top_linked || []).slice(0, 5).forEach(n => {
      if (!n || n.in_degree === 0) return;
      const row = document.createElement('div');
      row.className = 'hub-item';
      row.innerHTML = '<b>' + String(n.in_degree).padStart(3) + '</b> ' +
        escapeHtml(n.id);
      hubsEl.appendChild(row);
    });
  }

  // ─── Build vis DataSets ──────────────────────────────────────────────
  const nodes = new vis.DataSet(GRAPH.nodes.map(n => {
    if (TOPIC) {
      return {
        id: n.id,
        label: n.label,
        color: {
          // Topics inherit the colour of the wiki folder they resolve to,
          // so entities and concepts stay distinguishable both loose and
          // collapsed into clusters.
          background: kindColor(n.kind),
          border: kindColor(n.kind),
          highlight: { background: cssVar('--g-highlight'), border: cssVar('--g-highlight') },
        },
        borderWidth: 1,
        value: Math.max(n.session_count || 1, 1),
        // Deliberately no `group`: vis owns that key and re-applies its own
        // automatic group palette when a cluster reopens, overwriting the
        // per-kind colours above. `kind` is ours, so it survives.
        kind: n.kind || 'other',
        title: n.label + ' · ' + (n.session_count || 0) + ' sessions · ' +
          (n.degree || 0) + ' connected\nClick to focus · double-click to open',
        site_url: n.site_url,
        session_count: n.session_count,
        degree: n.degree,
        sessions: n.sessions || [],
        // A node keeps only the keys named here, and the panel reads freshness
        // off the vis node — so these must be forwarded (#108 FR7).
        first_seen: n.first_seen,
        last_seen: n.last_seen,
        last_updated: n.last_updated,
        type: 'topic',
      };
    }
    const isOrphan = n.in_degree === 0;
    return {
      id: n.id,
      label: n.label,
      color: {
        background: (colors[n.type] || colors.root)(),
        border: isOrphan ? orphanColor() : (colors[n.type] || colors.root)(),
        highlight: { background: cssVar('--g-highlight'), border: cssVar('--g-highlight') },
      },
      borderWidth: isOrphan ? 3 : 1,
      value: Math.max(n.in_degree, 1),
      kind: n.type,
      title:
        n.type + ' · ' + n.in_degree + ' inbound, ' + n.out_degree + ' outbound' +
        (n.path ? '\nClick to open ' + n.path : ''),
      path: n.path,
      site_url: n.site_url,
      type: n.type,
    };
  }));
  // Topic edges carry their bridging-session list; index them by a stable id
  // so an edge click can show "how these two topics connect".
  const edgeData = {};
  const edges = new vis.DataSet(GRAPH.edges.map((e, i) => {
    if (TOPIC) {
      const id = 'e' + i;
      edgeData[id] = e;
      return {
        id: id,
        from: e.source,
        to: e.target,
        width: Math.min(1 + (e.weight || 1) * 0.6, 8),
        color: { color: cssVar('--g-edge'), highlight: cssVar('--g-highlight') },
        title: e.source + ' ↔ ' + e.target + ' · ' + (e.weight || 0) + ' shared sessions',
      };
    }
    return {
      from: e.source,
      to: e.target,
      arrows: 'to',
      color: { color: cssVar('--g-edge') },
      title: e.source + ' → ' + e.target,
    };
  }));

  // ─── Render network ──────────────────────────────────────────────────
  const container = document.getElementById('network');

  // #21: layout-density presets. forceAtlas2Based spreads hub-heavy graphs
  // far more evenly than barnesHut, which let the dominant hub collapse
  // everything inward into an unreadable clump. `tight` adds central
  // gravity + shorter/stiffer springs to reel single-edge leaves back in.
  const LAYOUTS = {
    sparse: {
      solver: 'forceAtlas2Based',
      forceAtlas2Based: { gravitationalConstant: -120, springLength: 180,
        springConstant: 0.08, avoidOverlap: 0.6, damping: 0.4 },
      stabilization: { iterations: 2000 },
    },
    tight: {
      solver: 'forceAtlas2Based',
      forceAtlas2Based: { gravitationalConstant: -120, centralGravity: 0.06,
        springLength: 120, springConstant: 0.14, avoidOverlap: 0.7, damping: 0.4 },
      stabilization: { iterations: 2000 },
    },
  };
  // Persisted choice (defaults to sparse). Guarded so a locked-down
  // localStorage can't break the render.
  let layoutMode = 'sparse';
  try {
    const s = localStorage.getItem('llmwiki-graph-layout');
    if (s === 'sparse' || s === 'tight') layoutMode = s;
  } catch (e) { /* private mode / disabled storage */ }

  const network = new vis.Network(container, { nodes, edges }, {
    nodes: {
      shape: 'dot',
      font: { color: cssVar('--g-text'), size: 12, face: 'system-ui' },
      scaling: { min: 8, max: 32, label: { enabled: true, min: 10, max: 18 } },
    },
    // #21: cubicBezier is a STATIC curve type, so edges keep their
    // curvature after the physics freeze. The old "continuous" type
    // rendered as near-straight lines; the "dynamic" type would curve
    // more but needs live physics, conflicting with the #9 freeze.
    edges: { smooth: { enabled: true, type: 'cubicBezier', roundness: 0.4 } },
    physics: LAYOUTS[layoutMode],
    interaction: { hover: true, tooltipDelay: 120 },
  });

  // #9: freeze the layout once the simulation settles. Physics left running
  // keeps perturbing node positions live ("shaking" on every open).
  // `once`, not `on`, and re-registered explicitly on each layout switch,
  // so a stray restabilize (e.g. clustering) never yanks the camera.
  function freezeWhenStable(fit) {
    network.once('stabilizationIterationsDone', () => {
      network.setOptions({ physics: false });
      if (fit) network.fit();
    });
  }
  freezeWhenStable(true);

  // #21: switch layout density live, then re-freeze + fit. Fitting here is
  // intentional — the #9 no-yank rule guards incidental clicks; a deliberate
  // layout change repositions every node, so framing it is expected.
  // Re-run the layout after a change that moves every node, then re-freeze
  // and frame the result. Physics is frozen the rest of the time, so
  // without this a structural change (a layout switch, or collapsing the
  // graph into clusters) leaves every node stacked at whatever position it
  // was created at, reading as one merged dot in the middle of the canvas.
  function restabilize() {
    freezeWhenStable(true);
    network.setOptions({ physics: Object.assign({ enabled: true }, LAYOUTS[layoutMode]) });
    // setOptions re-enables *live* physics but does NOT emit
    // stabilizationIterationsDone, so the freeze handler above would never
    // fire and the new layout would shake forever (#9). Kick an explicit
    // stabilization run to drive it to a settled, frozen state.
    network.stabilize();
  }

  function applyLayout(mode) {
    if (!LAYOUTS[mode]) return;
    layoutMode = mode;
    try { localStorage.setItem('llmwiki-graph-layout', mode); } catch (e) {}
    restabilize();
  }
  const layoutSelect = document.getElementById('layout-select');
  if (layoutSelect) {
    layoutSelect.value = layoutMode;
    layoutSelect.addEventListener('change', e => applyLayout(e.target.value));
  }

  // ─── Click: focus neighbourhood + navigate (#328) ─────────────────────
  // A left-click ALWAYS highlights the node's 1-hop neighbourhood — the
  // Obsidian-style "show me what links here" view — so clicking is never a
  // silent no-op. This matters because only sources, projects and sessions
  // are compiled to standalone pages (build.py); entity / concept /
  // synthesis nodes have site_url === null, and the connected core of the
  // graph is made entirely of those. Nodes that DO have a compiled page
  // additionally open it. Clicking empty canvas clears the focus.
  network.on('click', params => {
    if (params.nodes && params.nodes.length) {
      const node = nodes.get(params.nodes[0]);
      if (!node) return;
      highlightNeighbours(node.id);
      if (TOPIC) {
        showTopicPanel(node);              // single click = focus + per-topic panel
      } else if (node.site_url) {
        window.open(node.site_url, '_blank', 'noopener');
      } else {
        _flashNoSiteTooltip(node, params.event);
      }
      return;
    }
    // Empty space — or, in topic mode, an edge (its bridging sessions).
    if (TOPIC && params.edges && params.edges.length) {
      const e = edgeData[params.edges[0]];
      if (e) { try { network.selectEdges([params.edges[0]]); } catch (_) {} showEdgePanel(e); return; }
    }
    resetHighlight();
    if (TOPIC) renderGlobalStats();
  });

  // Double-click opens the node's page (the topic page in topic mode), so a
  // single click stays reserved for focus + the side panel.
  network.on('doubleClick', params => {
    if (!params.nodes || !params.nodes.length) return;
    const node = nodes.get(params.nodes[0]);
    if (node && node.site_url) window.open(node.site_url, '_blank', 'noopener');
  });

  // ─── Topic-mode side panel (#54) ──────────────────────────────────────
  // Replaces the whole-wiki Stats widget with per-topic / per-edge info.
  function topicNeighbors(id) {
    const out = [];
    (GRAPH.edges || []).forEach(e => {
      if (e.source === id) out.push([e.target, e.weight]);
      else if (e.target === id) out.push([e.source, e.weight]);
    });
    out.sort((a, b) => b[1] - a[1]);
    return out;
  }
  function topicSessionLinks(slugs, limit) {
    const rows = (slugs || []).slice(0, limit).map(s => {
      const m = SESS[s] || {};
      const t = escapeHtml(m.title || s);
      return m.url
        ? '<a class="panel-link" href="' + escapeHtml(m.url) + '">' + t + '</a>'
        : '<span class="panel-muted">' + t + '</span>';
    });
    const extra = (slugs || []).length - rows.length;
    return rows.join('') + (extra > 0 ? '<span class="panel-muted">+' + extra + ' more…</span>' : '');
  }
  function statRow(label, value) {
    return '<div class="stat"><span>' + escapeHtml(label) + '</span><b>' +
      escapeHtml(value) + '</b></div>';
  }
  // Session-derived dates, one date or a range. Empty when no session carries
  // one — never a placeholder (#108 FR2).
  function topicActivity(node) {
    const seen = [node.first_seen, node.last_seen].filter(Boolean).map(String);
    if (!seen.length) return '';
    const first = seen[0], last = seen[seen.length - 1];
    return first === last ? first : first + ' – ' + last;
  }
  // Kind and freshness — the facts the topic page names, so the map can be
  // triaged without opening pages (#108 FR7). Kind always renders, naming the
  // unclassified state when no page describes the topic. Active comes from
  // sessions, Reviewed from the page's own curation date: two facts, two rows,
  // each dropped when the node lacks its field.
  function topicIdentityRows(node) {
    let h = statRow('Kind', kindLabelOne(node.kind));
    const active = topicActivity(node);
    if (active) h += statRow('Active', active);
    if (node.last_updated) h += statRow('Reviewed', String(node.last_updated));
    return h;
  }
  function showTopicPanel(node) {
    const neigh = topicNeighbors(node.id);
    let h = '<h3>' + escapeHtml(node.label) + '</h3>';
    h += '<div class="stat"><span>Sessions</span><b>' + (node.session_count || 0) + '</b></div>';
    h += '<div class="stat"><span>Connected topics</span><b>' + (node.degree || 0) + '</b></div>';
    try {
      h += topicIdentityRows(node);
    } catch (err) {
      reportGraphError('Could not read details for "' + node.label + '"', err);
    }
    // Current tab, like every other link in the site: only double-clicking a
    // node is the deliberate "take this elsewhere" gesture (#108 FR10).
    if (node.site_url) h += '<a class="panel-open" href="' + escapeHtml(node.site_url) + '">Open page →</a>';
    if (neigh.length) {
      h += '<h3 style="margin-top:10px">Top connections</h3>';
      h += neigh.slice(0, 6).map(p =>
        '<div class="hub-item"><b>' + String(p[1]).padStart(2) + '</b> ' + escapeHtml(p[0]) + '</div>').join('');
    }
    h += '<h3 style="margin-top:10px">Sessions</h3>';
    h += '<div class="panel-sessions">' + topicSessionLinks(node.sessions, 25) + '</div>';
    statsEl.innerHTML = h;
  }
  function showEdgePanel(e) {
    let h = '<h3>' + escapeHtml(e.source) + ' ↔ ' + escapeHtml(e.target) + '</h3>';
    h += '<div class="stat"><span>Shared sessions</span><b>' + (e.weight || 0) + '</b></div>';
    h += '<p class="panel-muted" style="margin:6px 0">Sessions mentioning both:</p>';
    h += '<div class="panel-sessions">' + topicSessionLinks(e.sessions, 30) + '</div>';
    statsEl.innerHTML = h;
  }
  function renderGlobalStats() {
    const s = GRAPH.stats || {};
    let h = '<h3>Stats</h3>';
    h += '<div class="stat"><span>Topics</span><b>' + (s.total_topics ?? GRAPH.nodes.length) + '</b></div>';
    h += '<div class="stat"><span>Connections</span><b>' + (s.total_edges ?? GRAPH.edges.length) + '</b></div>';
    h += '<div class="stat"><span>Sessions</span><b>' + (s.total_sessions ?? 0) + '</b></div>';
    h += '<h3 style="margin-top:10px">Top hubs</h3>';
    (s.top_topics || []).forEach(t => {
      h += '<div class="hub-item"><b>' + String(t.count).padStart(3) + '</b> ' + escapeHtml(t.id) + '</div>';
    });
    h += '<p class="panel-muted" style="margin-top:8px">Click a topic to focus · double-click to open · click an edge for shared sessions</p>';
    statsEl.innerHTML = h;
  }
  if (TOPIC) renderGlobalStats();

  // Restore every node to its base colour — clears a neighbourhood focus
  // (or a search dim). Defined here, called only at interaction time, so
  // `baseColors` is already populated by then.
  function resetHighlight() {
    const update = [];
    nodes.forEach(n => { update.push({ id: n.id, color: baseColors[n.id] }); });
    nodes.update(update);
  }

  // Transient "no page" hint for entity / concept / nav nodes.
  function _flashNoSiteTooltip(node, ev) {
    const tip = document.createElement('div');
    tip.textContent = node.label + ' — no compiled page (see ## Connections)';
    tip.style.cssText =
      'position:fixed;z-index:50;padding:6px 10px;border-radius:6px;' +
      'background:var(--g-panel);border:1px solid var(--g-border);' +
      'color:var(--g-muted);font-size:0.78rem;' +
      'pointer-events:none;transition:opacity 0.3s;';
    tip.style.left = (ev.clientX + 12) + 'px';
    tip.style.top = (ev.clientY + 12) + 'px';
    document.body.appendChild(tip);
    setTimeout(() => { tip.style.opacity = '0'; }, 1400);
    setTimeout(() => { tip.remove(); }, 1800);
  }

  // ─── G-19 (#305): node context menu ──────────────────────────────────
  // The context menu is wired up only when its DOM nodes are present.
  // Closes #386 — a minimal graph render without these elements would
  // throw on the addEventListener calls below.
  const ctxMenu = document.getElementById('ctx-menu');
  const ctxTarget = document.getElementById('ctx-target');
  let ctxNode = null;

  function showContextMenu(nodeId, clientX, clientY) {
    const node = nodes.get(nodeId);
    if (!node) return;
    ctxNode = node;
    ctxTarget.textContent = node.label || node.id;
    // Position the menu, clamped inside the viewport.
    ctxMenu.style.left = '0px';
    ctxMenu.style.top = '0px';
    ctxMenu.classList.add('show');
    const rect = ctxMenu.getBoundingClientRect();
    const maxX = window.innerWidth - rect.width - 8;
    const maxY = window.innerHeight - rect.height - 8;
    ctxMenu.style.left = Math.min(clientX, maxX) + 'px';
    ctxMenu.style.top = Math.min(clientY, maxY) + 'px';
    const first = ctxMenu.querySelector('button:not([disabled])');
    if (first) first.focus();
  }

  function hideContextMenu() {
    ctxMenu.classList.remove('show');
    ctxNode = null;
  }

  network.on('oncontext', params => {
    const nodeId = network.getNodeAt(params.pointer.DOM);
    if (nodeId) {
      // Only swallow the native menu where we actually replace it.
      params.event.preventDefault();
      showContextMenu(nodeId, params.event.clientX, params.event.clientY);
    } else {
      // Right-click on empty canvas belongs to the browser: the native
      // context menu, and mouse-gesture extensions that drive navigation
      // from a held right button. Preventing it unconditionally made the
      // graph page the one place on the site where those stop working.
      hideContextMenu();
    }
  });

  document.addEventListener('click', e => {
    if (!ctxMenu.contains(e.target)) hideContextMenu();
  });
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && ctxMenu.classList.contains('show')) {
      e.preventDefault();
      hideContextMenu();
    }
  });

  // Highlight the 1-hop neighbourhood of `nodeId`; dim everything else.
  function highlightNeighbours(nodeId) {
    const neighbourIds = new Set([nodeId]);
    GRAPH.edges.forEach(e => {
      if (e.source === nodeId) neighbourIds.add(e.target);
      if (e.target === nodeId) neighbourIds.add(e.source);
    });
    const update = [];
    nodes.forEach(n => {
      const inSet = neighbourIds.has(n.id);
      update.push({
        id: n.id,
        color: inSet
          ? baseColors[n.id]
          : { background: 'rgba(100,100,100,0.12)', border: 'rgba(100,100,100,0.25)' },
      });
    });
    nodes.update(update);
  }

  async function copyToClipboard(text) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (_) {
      // Fallback: textarea trick for older browsers / privacy mode.
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.style.position = 'fixed'; ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.focus(); ta.select();
      let ok = false;
      try { ok = document.execCommand('copy'); } catch (_) {}
      document.body.removeChild(ta);
      return ok;
    }
  }

  if (ctxMenu) ctxMenu.addEventListener('click', async e => {
    const btn = e.target.closest('button[data-action]');
    if (!btn || btn.disabled || !ctxNode) return;
    const action = btn.dataset.action;
    const node = ctxNode;
    hideContextMenu();
    switch (action) {
      case 'open': {
        // #328: use precomputed site_url so nodes without a compiled
        // page degrade gracefully instead of 404. Navigates in the current
        // tab — only double-click opens a new one (#108 FR10).
        if (node.site_url) {
          window.location.href = node.site_url;
        } else {
          alert(node.label + ' — no compiled page exists for this node. '
            + 'Entities, concepts, and nav files live in wiki/ but aren\u2019t rendered as standalone site pages.');
        }
        break;
      }
      case 'neighbours':
        highlightNeighbours(node.id);
        break;
      case 'copy-slug':
        await copyToClipboard(String(node.id));
        break;
      case 'copy-path':
        await copyToClipboard(String(node.path || node.id));
        break;
      case 'view-references': {
        const slug = String(node.id).replace(/"/g, '\\"');
        await copyToClipboard('llmwiki references "' + slug + '"');
        alert('Copied CLI command to clipboard:\n\n  llmwiki references "' + slug + '"');
        break;
      }
      default:
        /* mark-stale / archive: disabled placeholder — requires edit mode */
        break;
    }
  });

  // Keyboard shortcuts while menu is visible.
  if (ctxMenu) ctxMenu.addEventListener('keydown', e => {
    if (!ctxNode) return;
    const map = { 'n': 'neighbours', 'c': 'copy-slug', 'Enter': 'open' };
    const action = map[e.key];
    if (action) {
      const btn = ctxMenu.querySelector('button[data-action="' + action + '"]');
      if (btn && !btn.disabled) { e.preventDefault(); btn.click(); }
    }
  });

  // ─── Live search filter ──────────────────────────────────────────────
  const searchInput = document.getElementById('search-input');
  let baseColors = {};
  nodes.forEach(n => { baseColors[n.id] = n.color; });

  function applyFilter(q) {
    q = (q || '').trim().toLowerCase();
    // #9: matches get a dedicated red — base palette colors are too dim
    // against the blue-ish background to read as "found". Resolved per
    // call so a theme flip mid-search picks up the right shade.
    const matchColor = {
      background: cssVar('--g-search-match'),
      border: cssVar('--g-search-match'),
    };
    const update = [];
    nodes.forEach(n => {
      const label = (n.label || '').toString().toLowerCase();
      const dim = q && !label.includes(q) && !String(n.id).toLowerCase().includes(q);
      update.push({
        id: n.id,
        color: dim ? { background: 'rgba(100,100,100,0.15)', border: 'rgba(100,100,100,0.3)' }
                   : (q ? matchColor : baseColors[n.id]),
      });
    });
    nodes.update(update);
  }
  if (searchInput) searchInput.addEventListener('input', e => applyFilter(e.target.value));

  // ─── Cluster toggle ──────────────────────────────────────────────────
  // Groups on `kind` (the wiki folder a node resolves to), not `type`: in
  // topic mode every node's type is literally 'topic', so a type-keyed
  // cluster collapses the whole graph into one dot and hides every edge.
  const nodeKind = n => n.kind || n.type || 'other';
  const clusterKinds = [...new Set(GRAPH.nodes.map(nodeKind))].sort();
  let clusterMode = 'off';
  const clusterBtn = document.getElementById('cluster-toggle');
  const clusterModeEl = document.getElementById('cluster-mode');
  if (clusterBtn && clusterKinds.length < 2) {
    // One kind means one cluster means a single dot — say so rather than
    // offer a control that can only make the graph less useful.
    clusterBtn.disabled = true;
    clusterBtn.title = 'Nothing to cluster: every node is "' +
      kindLabel(clusterKinds[0] || 'other') + '". Clusters appear once the ' +
      'wiki has pages in more than one folder (entities, concepts, …).';
    if (clusterModeEl) clusterModeEl.textContent = 'n/a';
  } else if (clusterBtn) {
    clusterBtn.title = 'Group nodes by kind (' +
      clusterKinds.map(kindLabel).join(' · ') + ')';
    clusterBtn.addEventListener('click', () => {
      clusterMode = clusterMode === 'off' ? 'kind' : 'off';
      if (clusterModeEl) clusterModeEl.textContent = clusterMode;
      if (clusterMode === 'kind') {
        clusterKinds.forEach(k => {
          const size = GRAPH.nodes.filter(n => nodeKind(n) === k).length;
          // vis refuses to wrap a single node (and logs its own error
          // trying). A lone node already reads as itself.
          if (size < 2) return;
          try {
            network.cluster({
              // joinCondition re-runs over what's on the canvas, which now
              // includes clusters from earlier passes. A cluster node only
              // carries the properties we gave it, so without this guard
              // the `kind` fallback sorts every existing cluster into the
              // kind being built and nests them inside it.
              joinCondition: n => !n.isKindCluster && nodeKind(n) === k,
              clusterNodeProperties: {
                id: 'cluster:' + k,
                label: kindLabel(k) + ' (' + size + ')',
                color: { background: kindColor(k), border: kindColor(k) },
                value: size,
                kind: k,
                isKindCluster: true,
              },
            });
          } catch (err) {
            reportGraphError('Could not cluster "' + kindLabel(k) + '"', err);
          }
        });
      } else {
        clusterKinds.forEach(k => {
          const id = 'cluster:' + k;
          try {
            if (network.isCluster(id)) network.openCluster(id);
          } catch (err) {
            reportGraphError('Could not expand "' + kindLabel(k) + '"', err);
          }
        });
      }
      // Clustering and expanding both create nodes at a single point with
      // physics frozen. Re-run the layout so they spread out and the view
      // reframes on what is now on screen.
      restabilize();
    });
  }
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}"""