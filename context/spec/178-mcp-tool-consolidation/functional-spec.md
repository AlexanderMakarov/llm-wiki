# Functional Specification: Consolidate the MCP Tool Surface

- **Roadmap Item:** GitHub issue #196 — reduce MCP tool count and per-request schema cost while preserving every capability
- **Status:** Approved
- **Author:** 4ellendger

---

## 1. Overview and Rationale (The "Why")

Developers connect coding agents (Claude Code, Cursor, Codex, and similar) to llmwiki through the Model Context Protocol. Every time an agent session starts, the full list of available wiki actions is sent to the model — whether or not the session will use them.

Today that list contains twelve separate actions, costing roughly 1,900 tokens of context on every turn before the agent asks a single question. That tax repeats for the entire session and works against ongoing cost-reduction efforts elsewhere in the product.

A second problem is overlap: two different actions both "search the wiki," and several others all "list pages filtered by one attribute." The calling model must guess which action fits, and a wrong guess wastes a round trip with no useful answer.

This change redesigns the action list down to **six** actions with clear verbs. Success means:

- Six actions exposed to the model (down from twelve today)
- Measurably smaller schema payload per request (baseline today: 12 tools, ~7,600 characters / ~1,900 tokens; before/after recorded in the PR body)
- Every behaviour that agents rely on today remains reachable through the consolidated surface — nothing dropped, only regrouped
- Agents can pick the right action without guessing between similarly named search or health options

### Target surface (six actions)

| Action | Role | Absorbs (removed names) |
|---|---|---|
| **Search** | Find, list, and filter wiki content | `wiki_query`, `wiki_list_sources`, `wiki_confidence`, `wiki_lifecycle`, `wiki_category_browse` |
| **Read** | Return one page by exact path | — (stays separate; see §1.1) |
| **Health** | Quality checks plus headline wiki totals | `wiki_lint`, `wiki_dashboard` (totals only) |
| **Sync** | Pull new agent sessions into `raw/` | — |
| **Export** | Return pre-built site artifacts | — |
| **Add** | Ingest a URL, file, or inline content | — |

### 1.1 Why search and read stay separate

A single mega-search tool is possible (path OR term OR mode OR filter in one schema), but **read deserves its own action**:

- **Simplicity** — read is one required parameter (`path`); search carries modes, filters, caps, and output format. Merging them forces mutual-exclusion rules the model must learn.
- **Analytics coupling** — session/doc read heatmaps, top-earning pages, and dead-stock all key off `wiki_read_page` in telemetry today. Folding read into search requires retagging every read signal unless we keep recording a distinct tool name internally anyway.
- **Cost is still low** — six tools is half the current twelve; the big wins come from merging query + list-sources + three filter tools into search, and dropping dashboard.

Search absorbs the *discovery* family (keyword match, natural-language extract, source listing, confidence/lifecycle/tag filters). Read stays the *exact lookup* verb.

---

## 2. Functional Requirements (The "What")

### 2.1 Evidence before consolidation

Before any action is removed or merged, the team must review real usage data from the product's built-in MCP telemetry (per-action call counts and zero-hit rates, as shown on the Analytics page).

- **Acceptance Criteria:**
  - [ ] Per-action call counts and zero-hit rates are collected from MCP telemetry and recorded in the issue or PR before consolidation ships.
  - [ ] Decisions about which actions to fold cite this data (e.g. near-zero usage supports a straightforward merge; active usage requires a clear migration path).

### 2.2 Unified search (find + filter + extract)

Today's separate actions for keyword search, natural-language Q&A, source listing, confidence filtering, lifecycle filtering, and tag browsing become **one search action** with explicit parameters:

- **Match** (default when a search term is given) — find pages by title, path, or body; support kind filter, project filter for sources, optional raw-session inclusion, text or JSON output format.
- **Extract** — natural-language question answered from index, overview, and matching pages (replaces `wiki_query`).
- **Filter** — list pages by confidence range, lifecycle state, or tag (replaces confidence, lifecycle, and category-browse actions). Tag-count listing (all tags with page counts) is a filter mode with no tag value set.
- **List sources** — match mode with `kind=source` and optional project filter (replaces `wiki_list_sources`).

Read by exact path remains on the separate **Read** action (§2.3).

- **Acceptance Criteria:**
  - [ ] Given an agent needs pages by keyword, when it calls search with a term in match mode, then it receives equivalent results to today's name/text search.
  - [ ] Given an agent needs raw session sources (optionally by project), when it calls search with match mode and kind/project filters, then it receives equivalent information to today's source-listing action.
  - [ ] Given an agent asks a natural-language question, when it calls search in extract mode, then it receives ranked content comparable to today's query action.
  - [ ] Given an agent needs pages filtered by confidence, lifecycle, or tag, when it calls search with the appropriate filter parameters, then it receives equivalent information to today's confidence, lifecycle, or category-browse actions.
  - [ ] Given an agent session starts, when it inspects the available actions, then there is no separate query, list-sources, confidence, lifecycle, or category-browse action.

### 2.3 Read (unchanged role)

The read action returns full content for one wiki or raw page given its path. Behaviour and path-guard rules stay as today; only documentation and client configs may need updating if the registered name changes (technical spec decides whether to keep `wiki_read_page` or shorten to `wiki_read`).

- **Acceptance Criteria:**
  - [ ] Given an agent has an exact page path, when it calls read, then it receives the same content as today's read action.
  - [ ] Read remains a separate action from search (not a search mode).

### 2.4 Health with headline totals (replaces lint + dashboard)

The lint action is **renamed to health** (`wiki_health`) to reflect its expanded role: quality checks *and* headline wiki totals. The dedicated dashboard action is **removed**.

**Health output includes:**

- Everything today's lint action returns (issue summary, `total_pages`, disabled rules, `ran`, etc.)
- A new `totals` (or equivalent) block with simple headline counts — e.g. total wiki pages, source count, pending candidate count. Exact fields are a technical decision; must be cheap to compute on each call.

**Explicitly excluded:** breakdown by page type, lifecycle distribution, and confidence buckets (former dashboard views).

The human-facing `wiki/dashboard.md` page (Obsidian/Dataview template) is unchanged; only the MCP dashboard action goes away.

- **Acceptance Criteria:**
  - [ ] Given an agent calls health, when the report returns, then it includes lint results plus a totals block with headline counts.
  - [ ] Given an agent session starts, when it inspects the available actions, then there is no `wiki_lint` or `wiki_dashboard` action — only `wiki_health`.
  - [ ] Health totals do **not** include per-type, per-lifecycle, or per-confidence-bucket breakdowns.

### 2.5 Unchanged pipeline actions

Three actions stay as separate entries:

| Action | What the agent gets | Typical use |
|---|---|---|
| **Sync** | Pull new agent sessions into `raw/` (dry-run by default; explicit confirm required to write) | Ingest new sessions |
| **Export** | Machine-readable dump from the built site (`llms.txt`, full-text, JSON-LD, sitemap, RSS, manifest, or list). Requires `llmwiki build` first. | Bulk context for another model |
| **Add** | Ingest one URL, file path, or inline markdown into `raw/docs/` | Land a document without the CLI |

- **Acceptance Criteria:**
  - [ ] Sync, export, and add behave as today (aside from documentation updates).
  - [ ] Total exposed action count is exactly six (search, read, health, sync, export, add).

### 2.6 Analytics and telemetry continuity

MCP usage is stored append-only under `<vault>/usage/` and rendered on the Analytics page (`/analytics.html`): per-tool call table, retrieval/write value cards, session/doc read heatmaps, top-earning pages, and dead-stock lists.

**Raw logs stay unchanged** — each JSONL record keeps the tool name that was active at call time. No rewrite of historical `usage/*.jsonl`, `rollup.json`, or `daily.json` files.

**Display and aggregation use a canonical name map** — when building Analytics totals, value cards, and the per-tool table, every retired tool name is folded into its replacement before numbers are shown. Users see **only the six post-consolidation tool names**; historical calls from removed tools count toward the new name.

| Retired name | Counts toward |
|---|---|
| `wiki_query` | `wiki_search` |
| `wiki_list_sources` | `wiki_search` |
| `wiki_confidence` | `wiki_search` |
| `wiki_lifecycle` | `wiki_search` |
| `wiki_category_browse` | `wiki_search` |
| `wiki_lint` | `wiki_health` |
| `wiki_dashboard` | `wiki_health` |

Unchanged names (`wiki_search`, `wiki_read_page`, `wiki_sync`, `wiki_export`, `wiki_add`) pass through as-is. If read is renamed (e.g. to `wiki_read`), the map includes `wiki_read_page` → `wiki_read`.

The map lives in one place in code (e.g. `usage.py`) and is applied in aggregation paths (`combined_totals`, `value_summary`, per-tool table renderer, daily bucket rollups used by heatmaps). Read-path classifiers (`page_retrievals`, session/doc read splits) apply the same map so a historical `wiki_read_page` hit still counts as a read after any rename.

- **Acceptance Criteria:**
  - [ ] New MCP calls record the post-consolidation tool names.
  - [ ] Analytics per-tool table lists only the six current tool names — no separate rows for retired tools.
  - [ ] Historical calls logged under retired names contribute to the mapped canonical tool's call count, items returned, and zero-hit rate.
  - [ ] Value cards and read heatmaps use mapped names (subtext reflects the six-tool surface, e.g. "search · read").
  - [ ] `docs/reference/ui.md` describes the six-tool surface; no mention of legacy tool rows in the Analytics table.
  - [ ] No user-facing `llmwiki migrate-*` step for usage files.

### 2.7 Measurement (informational, not enforced by tests)

The PR must record before/after tool count and serialized schema size. **No automated test asserts a maximum tool count or payload ceiling.**

- **Acceptance Criteria:**
  - [ ] PR body records before/after tool count and payload size (baseline: 12 tools, ~7,597 characters).
  - [ ] Existing MCP tests are updated for renamed/merged actions; no new test locks the surface to a fixed tool count or byte limit.

### 2.8 MCP documentation consolidation

Produce one canonical, searchable MCP reference listing all six actions with migration rows for every removed name.

- **Acceptance Criteria:**
  - [ ] A dedicated page under `docs/reference/` documents the full six-action MCP surface.
  - [ ] Each removed action has a "use instead" row (`wiki_query`, `wiki_list_sources`, `wiki_confidence`, `wiki_lifecycle`, `wiki_category_browse`, `wiki_lint`, `wiki_dashboard`, and any others dropped).
  - [ ] The page is linked from at least one other reference doc so site search for "MCP" finds it.
  - [ ] Stale MCP tool lists elsewhere in `docs/` are updated or removed.

### 2.9 Migration guidance for existing integrations

Breaking change for MCP clients on the twelve-action surface.

- **Acceptance Criteria:**
  - [ ] `docs/UPGRADING.md` documents each removed action and its replacement, following the `wiki_entity_search` precedent.
  - [ ] `CHANGELOG.md` and reference docs updated in the same change.
  - [ ] MCP tests cover consolidated surface and migration paths.

---

## 3. Scope and Boundaries

### In-Scope

- Reducing MCP actions from twelve to **six** (search, read, health, sync, export, add)
- Renaming lint → **health** with headline totals; removing dashboard MCP action
- Folding query, list-sources, confidence, lifecycle, category-browse into search
- Telemetry/analytics code updates: canonical tool-name map folds retired names into the six current tools at aggregation/display time (raw logs unchanged)
- Consolidated `docs/reference/` MCP page + Analytics docs touch-up
- Upgrade documentation, changelog, updated MCP tests (no tool-count ceiling tests)

### Out-of-Scope

- Vault usage-file migration scripts (`usage/*.jsonl` data stays as-is)
- Dashboard-style breakdowns (by type, lifecycle, confidence buckets)
- Changing core behaviour beyond what merging requires
- The `llmwiki` CLI surface
- Automated regression guards on tool count or schema payload size
- Gating actions behind per-client configuration
