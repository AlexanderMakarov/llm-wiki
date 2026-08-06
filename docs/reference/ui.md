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

1. **Pipeline state** — Home-only table mount (`#llmwiki-state-widget`, inlined on `index.html`) with two captioned tables: **Files layer** (`Raw → To synthesize → Synthesized`, handled by shell commands — agent chips say `… sessions`; Documents is plain text, not a chip) and **Knowledge layer** (`Candidates → Entities / Concepts`). The **Candidates** header and count link to [`/candidates.html`](#candidates). Each Files-layer cell is a single count; To synthesize adds estimated USD in parentheses when non-zero. **Candidates** counts pending stubs already under `wiki/candidates/` (not the `Candidates (pre-run state):` harvestable figure from `synth --estimate`, which describes current `wiki/sources/` before pending sources land). **Entities** / **Concepts** count trusted pages after promote. The Files-layer Total row also shows queue **queued** / **in progress** counts. Under the tables, shared **collapse sections** (`llmwiki/render/collapse_section.py`) cover Timeline, not-synthesized sessions/docs, **Candidates to review** (by kind + stale), Commands (runnable `llmwiki …` CLI rows + one-shot `cd <llm-wiki-checkout> && claude|agent|codex "/wiki-candidates"` — Gemini CLI is adapter-scaffold only, so no Home launcher), and estimate warnings.
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

- Hero — display name plus `slug`, `created`, `updated`, main-session and sub-agent counts. The two dates are the earliest and latest `date` across the project's own sessions, recomputed every build: project stubs carry no date of their own, so nothing is hand-maintained, and a project whose sessions all lack a date shows neither.
- Project summary (auto-synthesised from sessions)
- **Connected topics** — the topics this project co-occurs with, immediately above the session tables. Same list shape as on a [topic page](#topic-pages) (topic name · shared-session count), linking to `../topics/<slug>.html`. The whole section is omitted — heading included — when the project's topic node has no connections, or when the vault has too few topics for the topic graph to be used at all.
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
- Click a node → focuses its 1-hop neighbourhood; in topic mode it also opens the side panel, in page mode it opens the node's compiled page in a new tab
- Double-click a node → opens its page in a new tab — the [topic page](#topic-pages), or the project page for a topic that routes to one
- Search input in the top-right → highlights matching nodes, dims the rest
- Orphan highlighting — nodes with zero inbound links get a red border
- Cluster toggle — group nodes by kind (the `wiki/` folder behind each topic)
- Stats overlay (bottom-right) — total pages, edges, orphans, avg connections, top-5 hubs
- Dark / light theme mirrors the main site

**Node colours.** One colour per kind, at equal saturation — a topic no wiki page describes is a normal citizen of the map, not a faded placeholder. The legend renders one swatch per kind actually present in the graph, so a vault with no comparisons advertises no comparison swatch.

| Kind | Colour | |
|---|---|---|
| Sources | violet | `#7c3aed` |
| Entities | blue | `#2563eb` |
| Concepts | green | `#059669` |
| Syntheses | amber | `#d97706` |
| Projects | magenta | `#db2777` |
| Questions | cyan | `#0891b2` |
| Comparisons | brown | `#b45309` |
| Other (no wiki page describes the topic) | lime | `#65a30d` |

Red is deliberately not a kind colour: the map already spends it on two states — the orphan border and a live search match — and a kind sharing it would read as an error.

**Side panel** (topic mode, single click) — topic name, `Sessions`, `Connected topics`, then the same identity facts the topic page carries: `Kind`, `Active`, `Reviewed`. Each of those three rows is omitted when the node lacks the field, so a topic with no backing wiki page shows the counts alone rather than empty rows. `Open page →` follows, then the top connections and the bridging sessions.

**Offline fallback:** if the vis-network CDN can't load, the viewer shows an inline notice instead of a blank screen.

---

## Topic pages

URLs: `/topics/<slug>.html`, `/topics/index.html`

A **topic** is a `[[wikilink]]` target found in `wiki/sources/*.md`, with spelling variants clustered into one canonical name. Topics are therefore *not* wiki pages: a topic exists because sessions cited the name, and a topic page renders whether or not any page under `wiki/` describes it — an un-promoted candidate, or a name a reviewer declined, keeps its page indefinitely. Reach them by double-clicking a node in the [Graph](#graph), from `⌘K` (`type:topic`), from `topics/index.html`, or from the Connected topics list on any other topic or project page.

`/topics/index.html` lists every topic by reach — session count and link count per row.

Two thresholds decide which topics get a page: a topic mentioned by fewer than 2 sessions is dropped from the graph, and a vault yielding fewer than 5 topic nodes falls back to the page graph, in which case `build` writes no topic pages at all.

### Layout

The title, then an **identity line** of ` · `-separated parts in this order — each part dropped entirely when its source is absent, never filled with a placeholder:

`Entity` chip · `Active 2026-01-09 – 2026-07-30` · `Reviewed 2026-08-01` · `7 connected topics` · `12 sessions` · `<slug>`

The kind chip names the singular kind — Entity, Concept, Project, Question, Comparison, Synthesis, Source. Below the identity line:

- **Also tagged as** — the alternative spellings sessions used before clustering merged them under this name.
- **Page content** — the backing wiki page's body (see below). Absent when no page backs the topic or the page records nothing.
- **Connected topics** — topics sharing at least one session, strongest first, each with its shared-session count. Renders `No connected topics.` rather than disappearing.
- **Sessions** — every session mentioning the topic, linked to its compiled session page; a session with no compiled page is listed as text marked `(no page)`.

### Where each fact comes from

This is the distinction to keep straight: **sessions supply reach and activity, the topic's own wiki page supplies kind, review date and content.** Neither substitutes for the other, and neither is invented.

| On the page | Comes from | Present when |
|---|---|---|
| `Active <first> – <last>` | the `date` frontmatter of the sessions that mention the topic — oldest to newest, collapsing to one date when they agree | at least one such session carries a date |
| `N sessions` + the Sessions list | the same set of sessions | always |
| `N connected topics` + the Connected topics list | co-occurrence: two topics share an edge when a session mentions both | always (the count can be `0`) |
| Kind chip | the `wiki/` folder holding the page that backs the topic — `entities/` → Entity, `concepts/` → Concept, and so on. The folder is the only kind signal the schema carries; frontmatter `type` is not consulted | a page's slug or title matches the topic's canonical spelling or one of its aliases |
| `Reviewed <date>` | that page's `last_updated` frontmatter | the page records one |
| Page content | that page's body | the page has a body left after the omissions below |

A topic with no backing page therefore shows no chip, no review date and no content — and one whose page omits `last_updated` shows no review date even while sessions supply activity dates.

### Page content

The topic page is the only browsable surface for entity and concept pages, so it renders their content above the link lists. What survives is everything after the page's own leading `# H1`, minus `## Connections` and `## Sessions` — the topic page renders both of those itself, from the graph, so the page's hand-written versions would only duplicate them.

- **Heading-agnostic.** Nothing is keyed to `## Key Facts`; a renamed, reordered, or newly added section reaches the reader as written, as does introductory prose sitting above the first heading.
- **No empty sections.** A heading with nothing under it is dropped rather than rendered as a bare heading — innermost first, so a `##` whose only child `###` was itself empty goes too.
- **`[[wikilinks]]` resolve.** A target naming a topic links to wherever that topic resolved (its topic page, or the project page a project topic routes to); a target naming a session with a compiled page links to it; anything else degrades to the plain text it wrapped rather than a dead link.

### Project topics route to the project page

A topic backed by a page under `wiki/projects/` links to `/projects/<slug>.html` — the full [project detail page](#project-detail-projectsslughtml) with its heatmap, session cards and charts — rather than to a thin topic page. The rewrite is applied once at build time and every surface honours it: the map's double-click target, the search index entry, Connected topics lists on other topic pages, `topics/index.html`, and `[[wikilinks]]` cited inside page content.

The match itself identifies which project it is, so an alias spelling routes as correctly as the canonical one. The rewrite is skipped when the build wrote no page for that project: `wiki/projects/` is seeded from stubs while `site/projects/` comes from session groups, so a project page with no recorded sessions keeps its ordinary topic page rather than being handed a link that 404s.

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
| `drawer-browse` | faceted project-browse drawer open (by project / lifecycle / cache_tier) |
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

1. **Candidates to review** — pending stubs under `wiki/candidates/` (total + by kind) and stale count (default ≥30d). Heading / pending count link to [`/candidates.html`](#candidates). Zero is intentional signal: synthesize-only vaults still show that the review gate exists and is empty.
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

Topic entries (`type: "topic"`) point at `topics/<slug>.html` — or at `projects/<slug>.html` for a topic that [routes to a project page](#project-topics-route-to-the-project-page); their `body` includes session count plus `also: …` aliases so a query using any non-canonical spelling still hits the right page. The same payloads ship as `.js` sidecars for `file://` (#20).

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
