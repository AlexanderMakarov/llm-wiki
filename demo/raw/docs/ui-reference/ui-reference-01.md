---
title: "UI reference (part 1/5)"
slug: ui-reference-01
project: ui-reference
type: source
tags: [wiki-add, raw-doc]
date: 2026-08-10
source: "docs/reference/ui.md"
content_sha256: 091e560125d91e049c14221fb0d035f09dac5d63e4986142a6252af727a37d58
---

> Part 1 of 5 of **UI reference**.

---
title: "UI reference"
type: navigation
docs_shell: true
---

# UI reference

Every screen on the compiled site (`llmwiki build` → `site/`), what it shows, and how to reach it. Screens are what `llmwiki serve` exposes on `http://127.0.0.1:8765/`.

---

## Top navigation

Every page in the site carries the same header nav. Keyboard: `⌘K` opens the command palette from any page.

| # | Label | URL | Surfaces |
|---|---|---|---|
| 1 | **Home** | `/index.html` | pipeline State widget (Eligible sources Raw→To synthesize→Synthesized→On disk + Knowledge layer Candidates/Entities/Concepts + collapsible backlog/candidates/commands) + recent raw docs |
| 2 | **Raw** | `/raw.html` | file tree browser of raw documents (wiki-add layer) |
| — | **Candidates** | `/candidates.html` | pending entity/concept review (per-row decision + Apply); batch API under serve, or copy-CLI when static |
| 3 | **Graph** | `/graph.html` | interactive force-directed knowledge graph (vis-network) |
| 4 | **Projects** | `/projects/index.html` | filterable card grid of every project + freshness badge |
| 5 | **Sessions** | `/sessions/index.html` | sortable table of every session, agent badge, project, model, tool-call count |
| 6 | **Analytics** | `/analytics.html` | activity heatmaps, wiki usage, recent activity, project grid |
| 7 | **Models** | `/models/index.html` | structured model-profile cards (provider, pricing, benchmarks) |
| 8 | **Compare** | `/vs/index.html` | auto-generated vs-pages between AI models |
| 9 | **Docs** | `/docs/index.html` | editorial docs hub — tutorials, references, deployment guides |
| 10 | **Prototypes** | `/prototypes/index.html` | review-ready UI states (page-shell, article-anatomy, …) for UX iteration |
| — | **Search** | `⌘K` | fuzzy-match command palette over the whole corpus |
| — | **Theme toggle** | button on the right | light / dark (persists via `localStorage.theme`) |

Mobile: the six middle links collapse into a bottom-nav below 768 px; Search + Theme stay in the top bar.

---

## Home

URL: `/index.html`

Queue-first landing page. Layout:

1. **Pipeline state** — Home-only table mount (`#llmwiki-state-widget`, inlined on `index.html`) with two captioned tables: **Eligible sources** (`Raw → To synthesize → Synthesized (by agent)`; caption notes On disk can exceed Raw for filtered/orphan pages; handled by shell commands — agent chips say `… sessions`; Documents is plain text, not a chip) and **Knowledge layer** (`Candidates → Entities / Concepts`). The first three columns count **eligible sources** (synthesize inputs), not markdown files or wiki pages — a document that fans out into several `wiki/sources/` part-pages still contributes 1 (#81). A fifth **On disk** column counts `.md` files under `wiki/sources/` (excluding `_`-prefixed names): sessions attributed per agent, Documents via `raw/docs/` or `raw-doc` tags, plus a **Stubs** row (On disk only; other columns show "—") and an **Other** row when uncategorized non-stub pages remain. There is no under-table Source pages note. The **Candidates** header and count link to [`/candidates.html`](#candidates). Each eligible-sources cell is a single count; To synthesize adds estimated USD in parentheses when non-zero. **Candidates** counts pending stubs already under `wiki/candidates/` (not the `Candidates (pre-run state):` harvestable figure from `synth --estimate`, which describes current `wiki/sources/` before pending sources land). **Entities** / **Concepts** count trusted pages after promote. The eligible-sources Total row also shows queue **queued** / **in progress** counts and sums On disk. Under the tables, shared **collapse sections** (`llmwiki/render/collapse_section.py`) cover Timeline, not-synthesized sessions/docs, **Candidates to review** (by kind + stale), Commands (runnable `llmwiki …` CLI rows + one-shot `cd <llm-wiki-checkout> && claude|agent|codex "/wiki-candidates"` — Gemini CLI is adapter-scaffold only, so no Home launcher), and estimate warnings.
2. **Recent raw documents** — newest `raw/docs/` entries with title + source meta.

Numbers come from `llmwiki-state.js` (`synth.pipeline` + `synth.pending` + `synth.estimate`), refreshed by `llmwiki sync` / `llmwiki synth --estimate`. Every `llmwiki build` also recounts pending/stale candidates and trusted entity/concept page counts into `synth.pipeline.to_review*` / `trusted_entities` / `trusted_concepts` (cheap disk walk — #84) and copies the sidecar into `site/llmwiki-state.js`. `llmwiki build` still one-shot backfills `synth.pipeline` rows when the state snapshot predates that key (v1.4→v1.5 upgrade — #70). The session-analytics content (heatmap, stats, project grid) lives on [Analytics](#analytics).

---

## Candidates

URL: `/candidates.html`

Review gate for pending stubs under `wiki/candidates/` (#97). Two tables — **Entities (pending)** and **Concepts (pending)** — with Name, Description, and Decision:

| Decision | Effect |
|---|---|
| **Skip** | Leave pending (default) |
| **Promote** | Move into trusted `wiki/entities/` or `wiki/concepts/`; `status: reviewed` |
| **Flip and promote** | Wrong kind → promote into the opposite trusted folder and rewrite `type:` (do not hand-`mv` stubs between candidate folders) |
| **Discard** | Archive under `wiki/archive/candidates/` |
| **Merge with…** | Pick another pending name in the **same table**; merges then archives the source stub (CLI `merge` can also target a trusted same-kind page) |

Set decisions per row, then **Apply**. Under `llmwiki serve` (vault `…/site` beside `…/wiki`), Apply POSTs a **batch** to `/api/candidates`. On a static or `file://` open, Apply shows one pasteable `llmwiki candidates apply --actions '[{…}]'` line (Copy CLI) — same JSON shape as the API. After a successful served Apply the page reloads; run `llmwiki build` for a cold-open Home/Analytics recount. One-off CLI actions and `/wiki-candidates` remain available.

---
