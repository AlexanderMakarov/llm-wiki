---
title: "UI reference (part 2/6: Candidates)"
slug: ui-reference-02
project: reference-ui
type: source
tags: [wiki-add, raw-doc]
date: 2026-09-08
source: "docs/reference/ui.md"
content_sha256: 7eb6298d7f4ad87999fa2453589b551356412dea6a6e4d19fc218921bf71850b
---

> Part 2 of 6 of **UI reference** — Candidates.

## Candidates

URL: `/candidates.html`

The review gate for pending stubs under `wiki/candidates/` (#97). Two tables — **Entities (pending)** and **Concepts (pending)** — each with **Name** (title, slug and age), **Description**, and **Decision**.

**Decision** is a per-row select offering exactly the actions `llmwiki candidates apply` executes: *Promote*, *Flip and promote*, *Merge into…* and *Discard*. The last two reveal the field that action needs, and both fields are required before the row can be applied. Every row starts at **No decision** and stays there until you choose — deciding is browser state, so nothing runs and nothing is sent.

**Apply** sits in a bar above the tables that stays pinned under the site nav while you scroll, so it is in reach from any row. It assembles the rows you decided — and only those — into the command to run and the JSON batch to pipe into it, shown directly below the bar with **Copy command** and **Copy JSON**:

```bash
llmwiki candidates apply --vault <vault> --actions -
```

*Merge into…* reveals a **filterable dropdown** of every page `merge --into` resolves for that table — the trusted pages under `wiki/<kind>/` first, then the same-table pending stubs. Press the ▾ button or `↓` to browse the whole list without typing, type any part of a name to narrow it (case-insensitive substring), `↑` / `↓` to move, `Enter` to choose, `Esc` to close. The list is the closed set of valid targets: text naming no page is marked as you type, and a row holding one is named on the page instead of going into a batch that would fail at the CLI.

*Discard* reveals a **required reason**. `discard` files that reason beside the archived stub, so a blank one throws the decision away — a row set to *Discard* with no reason is held back the same way an unresolved merge target is.

A row left at **No decision** is absent from the batch and stays pending, so a half-finished review can be applied and resumed. Apply refuses an empty batch; when a decided row is not yet executable it names the row, marks the field and moves focus to it, and emits nothing until you finish it. `llmwiki candidates apply` rebuilds `site/` after a successful batch, so reload the page (or reopen the file) to see the remaining queue. Pass `--no-rebuild` if you are applying several batches and will `llmwiki build` once at the end. One-off CLI actions and `/wiki-candidates` do the same wiki work; only `apply` rebuilds.

| Action | Effect |
|---|---|
| **promote** | Move into trusted `wiki/entities/` or `wiki/concepts/`; `status: reviewed` |
| **flip-promote** | Wrong kind → promote into the opposite trusted folder and rewrite `type:` (do not hand-`mv` stubs between candidate folders) |
| **discard** | Archive under `wiki/archive/candidates/` |
| **merge** | Fold into another page of the same kind, then archive the stub |

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

- Hero — display name plus a `Project` kind chip, `slug`, `created`, `updated`, main-session and sub-agent counts. The chip is the same one a [topic page](#topic-pages) carries, shown here because a project topic routes to this page instead, so the reader sees the kind either way. The two dates are the earliest and latest `date` across the project's own sessions, recomputed every build: project stubs carry no date of their own, so nothing is hand-maintained, and a project whose sessions all lack a date shows neither.
- Project summary (auto-synthesised from sessions)
- **Connected topics** — the topics this project co-occurs with, immediately above the session tables. Same list shape as on a [topic page](#topic-pages) (topic name · shared-session count), and each entry routes exactly as it does everywhere else: `../topics/<slug>.html` normally, `../projects/<slug>.html` for a neighbour that is itself a project. The whole section is omitted — heading included — when the project's topic node has no connections, or when the vault has too few topics for the topic graph to be used at all.
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

## Models

URL: `/models/index.html`

Structured info cards for each AI model (per `llmwiki/schema.py :: ModelProfile`):

- Provider · release date · license
- Context window · max output
- Modalities (text / vision / audio)
- Pricing per 1 M tokens (input, cached_input, cache_write, output)
- Benchmark scores (GPQA Diamond, SWE-bench, MMLU, LiveCodeBench, etc.)

---
