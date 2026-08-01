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
| 1 | **Home** | `/index.html` | pipeline State widget (Files layer Raw→To synthesize→Synthesized + Knowledge layer Candidates/Entities/Concepts + collapsible backlog/candidates/commands) + recent raw docs |
| 2 | **Raw** | `/raw.html` | file tree browser of raw documents (wiki-add layer) |
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

1. **Pipeline state** — Home-only table mount (`#llmwiki-state-widget`, inlined on `index.html`) with two captioned tables: **Files layer** (`Raw → To synthesize → Synthesized`, handled by shell commands — agent chips say `… sessions`; Documents is plain text, not a chip) and **Knowledge layer** (`Candidates → Entities / Concepts`, review via agent Commands). Each Files-layer cell is a single count; To synthesize adds estimated USD in parentheses when non-zero. **Candidates** counts pending stubs already under `wiki/candidates/` (not the harvestable-stub preview from `synth --estimate`). **Entities** / **Concepts** count trusted pages after promote. The Files-layer Total row also shows queue **queued** / **in progress** counts. Under the tables, shared **collapse sections** (`llmwiki/render/collapse_section.py`) cover Timeline, not-synthesized sessions/docs, **Candidates to review** (by kind + stale), Commands (runnable `llmwiki …` CLI rows + one-shot `cd <llm-wiki-checkout> && claude|agent|codex "/wiki-candidates"` — Gemini CLI is adapter-scaffold only, so no Home launcher), and estimate warnings.
2. **Recent raw documents** — newest `raw/docs/` entries with title + source meta.

Numbers come from `llmwiki-state.js` (`synth.pipeline` + `synth.pending` + `synth.estimate`), refreshed by `llmwiki sync` / `llmwiki synth --estimate`. Every `llmwiki build` also recounts pending/stale candidates and trusted entity/concept page counts into `synth.pipeline.to_review*` / `trusted_entities` / `trusted_concepts` (cheap disk walk — #84) and copies the sidecar into `site/llmwiki-state.js`. `llmwiki build` still one-shot backfills `synth.pipeline` rows when the state snapshot predates that key (v1.4→v1.5 upgrade — #70). The session-analytics content (heatmap, stats, project grid) lives on [Analytics](#analytics).

---

## Projects index

URL: `/projects/index.html`

Grid view of every project. Each card shows:

- Project name + slug
- Session count (main + sub-agent)
- Token total for the project
- Freshness badge (days since last session)
- Topic chips (from frontmatter `topics: []`)
- Agent badges (Claude / Codex / Copilot / Cursor / Gemini)

Clicking a card navigates to `/projects/<slug>.html` — the project detail page.

### Project detail (`/projects/<slug>.html`)

- Project summary (auto-synthesised from sessions)
- Sorted session table (date desc)
- Per-project activity heatmap
- Linked entities + concepts that appear across sessions
- Tool-call distribution bar chart

---

## Sessions index

URL: `/sessions/index.html`

Sortable table across every project. Default sort: date desc.

**Columns:** Session · Agent · Project · Date · Cwd · Model · Msgs · Tools.

**Filter bar at top:** Project · Agent · Model · date range · slug substring (Clear resets; selections persist in `sessionStorage` for the tab).

**Activity timeline** above the filter bar — SVG sparkline of sessions/day across the calendar span. Hover, focus, or click a bar to show that day's date and count in the label (native tooltip too).

Clicking a row navigates to `/sessions/<project>/<slug>.html`.

### Session detail (`/sessions/<project>/<slug>.html`)

- **Frontmatter block** — model, date, token counts, tool-call summary
- **Summary** — auto-synthesised 2–4 sentence abstract
- **Key claims** — bullet list
- **Key quotes** — blockquote pulls
- **Conversation** — full transcript, tool outputs collapsible (auto- expand on long blocks)
- **Connections** — `[[wikilinks]]` out to entities, concepts, related sessions
- **Related** — top-3 similarity matches (from heading/body n-gram)
- **Download .md** — nested `sources/<project>/<stem>.md` for AI-agent consumption

---

## Models + Compare

URLs: `/models/index.html`, `/vs/index.html`

**Models:** structured info cards for each AI model (per `llmwiki/schema.py :: ModelProfile`):

- Provider · release date · license
- Context window · max output
- Modalities (text / vision / audio)
- Pricing per 1 M tokens (input, cached_input, cache_write, output)
- Benchmark scores (GPQA Diamond, SWE-bench, MMLU, LiveCodeBench, etc.)

**Compare:** auto-generated pairwise comparison pages (`/vs/claude-sonnet-4-6-vs-gpt-5.html`, etc.). One row per shared field, winner highlighted.

---

## Graph

URL: `/graph.html`

Interactive force-directed knowledge graph. Details in [`reference/reader-api.md`](reader-api.md) under the graph section.

**What works:**

- Pan / zoom (mouse / trackpad)
- Click a node → opens the wiki page in a new tab
- Search input in the top-right → highlights matching nodes, dims the rest
- Orphan highlighting — nodes with zero inbound links get a red border
- Cluster toggle — group nodes by type (sources / entities / concepts / syntheses)
- Stats overlay (bottom-right) — total pages, edges, orphans, avg connections, top-5 hubs
- Dark / light theme mirrors the main site

**Offline fallback:** if the vis-network CDN can't load, the viewer shows an inline notice instead of a blank screen.

---

## Docs hub

URL: `/docs/index.html`

The editorial entry point — you're reading a page compiled from the same pipeline. Covered in detail by [`tutorials/01-installation.md`](../tutorials/01-installation.md) onward. See also [`style-guide.md`](../style-guide.md).

---

## Prototypes hub

URL: `/prototypes/index.html`

Review-ready UI states for UX iteration **before** larger UI changes touch the live templates. Six states:

| Slug | What's shown |
|---|---|
| `page-shell` | layout skeleton — nav + footer + breadcrumb, empty content slot |
| `article-anatomy` | annotated session page with orange callouts on every slot (frontmatter, summary, transcript, connections, related) |
| `drawer-browse` | faceted project-browse drawer open (by project / entity_type / lifecycle / cache_tier) |
| `search-results` | command palette mid-query, 10+ results |
| `empty-search` | no-match state with escape-hatch links |
| `references-rail` | article with sticky right-hand `## Connections` rail |

Every prototype carries a **4 px `#7C3AED` top stripe** and a "Prototype — not a live page" meta block so reviewers never confuse them with real pages.

---

## Recent

URL: `/recent.html`

Newest raw documents first, one row per logical document — chunked docs (`<slug>-01.md` … `<slug>-NN.md` in one folder) collapse into a single row with a part count. Each row shows title, date, and origin source, and links into the Home tree browser.

---

## Analytics

URL: `/analytics.html`

Session analytics plus usage-led wiki value (#52) and the candidates review gate (#84). The page opens with a hero line (main sessions · sub-agent runs · projects) and a row of stat cards — tokens (total + per-session average), best cache hit, heaviest project by tokens, and heaviest project by MCP usage.

Below that, sections appear in this order:

1. **Candidates to review** — pending stubs under `wiki/candidates/` (total + by kind) and stale count (default ≥30d). Zero is intentional signal: synthesize-only vaults still show that the review gate exists and is empty.
2. **Activity** — ~18-month GitHub-style heatmaps: **Agents Activity** (session counts), **Wiki MCP calls**, and — when telemetry carries signal — **Session-page reads** and **Doc-page reads** split from `wiki_read_page` hits.
3. **Recent activity** — last entries from `wiki/log.md` (including producer breakdown lines such as `Processed: 2 Claude · 1 Cursor`).
4. **Projects** — filterable card grid (session counts, date range, topic chips) linking to per-project detail pages.
5. **LLM-Wiki MCP usage** — merged value block and MCP table in one section (MCP telemetry only, not `file://` browsing): retrievals · writes · answer rate · payoff-per-page · distinct attributed projects; optional synthesis cost line; sessions vs documents corpus/read mix; top-earning pages; **Dead stock** as a shared count-badge collapsible listing every unread synthesized source (`collapse_section`); per-tool calls, items returned, and zero-hit rate.

There is no daily bar chart — trends are read from the heatmaps. Durable counts and series are described in [`reference/state-persistence.md`](state-persistence.md).

---

## Command palette (⌘K)

Press `⌘K` (or `Ctrl+K` on Linux/Windows) from any page.

- Fuzzy match over **every** page title + body — including topic pages (`type: topic`) and their alias spellings (#50).
- Top result on Enter navigates.
- Shows facet chips: `Project`, `Entity type`, `Lifecycle`, `Confidence`, `Tags` — click a facet to filter.
- Footer shows the current mode (`flat` / `tree`) from `search-index.json._mode` and the deep-page ratio (see [`reference/cache-tiers.md`](cache-tiers.md) for the tree-mode heuristic).
- Keyboard: `↑ / ↓` navigate, `Enter` open, `Esc` close.
- Filter by type: `type:topic` / `type:session` / `type:project` / `type:docs` / `type:document` / `type:slash` / `type:page`.

---

## Search index + chunks

Two levels:

- `site/search-index.json` — ~7 KB meta index (projects, static pages, documents, docs, slash commands, **topics**) + chunk manifest + facet counts + mode badge.
- `site/search-chunks/<project>.json` — per-project session entries with `title`, `url`, `type`, `project`, `date`, `model`, `body`, `heading_max_depth`, `heading_count_by_depth`.

Topic entries (`type: "topic"`) point at `topics/<slug>.html`; their `body` includes session count plus `also: …` aliases so a query using any non-canonical spelling still hits the canonical topic page. The same payloads ship as `.js` sidecars for `file://` (#20).

The palette lazy-loads chunks as the query narrows. See [`reference/reader-api.md`](reader-api.md) for the stable shape.

---

## AI-consumable exports

Every session page links to a nested markdown copy for agents:

- `sources/<project>/<stem>.md` — raw session markdown (same as the page Download .md button)

Site-level exports AI agents should start with:

| URL | Purpose |
|---|---|
| `/llms.txt` | short index per [llmstxt.org](https://llmstxt.org) |
| `/llms-full.txt` | flattened plain-text dump (capped at 5 MB) |
| `/graph.jsonld` | schema.org JSON-LD entity / concept / source graph |
| `/sitemap.xml` | standard sitemap with `lastmod` |
| `/rss.xml` | RSS 2.0 of newest sessions |
| `/robots.txt` | AI-friendly robots + link to `llms.txt` |
| `/ai-readme.md` | navigation instructions aimed at AI agents |
| `/manifest.json` | SHA-256 hashes for every file + perf-budget check |

---

## Keyboard shortcuts

Press `?` on any page to see the shortcuts modal. Current set:

| Key | Does |
|---|---|
| `⌘K` / `Ctrl+K` | open command palette |
| `/` | focus search filter (on index pages) |
| `g h` | go to home |
| `g p` | go to projects |
| `g s` | go to sessions |
| `j` / `k` | next / previous row (on table views) |
| `?` | show this shortcut modal |
| `Esc` | close modal / palette |

---

## Theming

Site-wide CSS lives in `llmwiki/render/css.py`. All tokens inherit from the brand system — see [`../design/brand-system.md`](../design/brand-system.md).

Theme toggle (top-right): `light` / `dark`, persists via `localStorage.theme`. System preference (`prefers-color-scheme`) is honoured when no override is set.

---

## Accessibility

WCAG 2.1 AA targeted across the whole site. Specifics in [`../accessibility.md`](../accessibility.md). Notable:

- Every image has an `alt` attribute
- Skip-to-content link appears on every page on keyboard focus
- Focus ring uses the accent colour with 2 px outline + 2 px offset
- `prefers-reduced-motion` honoured (all transitions collapse to 0.01 ms)
- Muted text hits ≥ 4.8:1 contrast in light and ≥ 6.9:1 in dark

---

## Related

- **[CLI reference](cli.md)** — every `python3 -m llmwiki …` subcommand.
- **[Slash commands reference](slash-commands.md)** — the `/wiki-*` surface.
- **[Reader API contract](reader-api.md)** — stable shape of every file the build writes.
- **[Reader-first article shell](reader-shell.md)** — opt-in Wikipedia-style layout for individual pages.
