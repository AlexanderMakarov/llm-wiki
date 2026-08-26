# Declined ideas

> **Audience:** maintainers and contributors about to re-propose
> something. Check this file before filing an issue — we may have
> already considered and rejected your idea, and the reason is here.

The project has a scope. Not every cool idea fits. This file is the
graveyard where declined ideas rest, with a date and a one-sentence
rationale. If you disagree with a decline, open a new issue and link
to the entry — explain what's changed since the rejection.

## Format

```markdown
## <Date> — <Title>

**Reason:** one-sentence rationale.

**Context (optional):** link to the issue, PR, or discussion. Any
nuance about *when* this might be reconsidered.
```

---

## 2026-04-09 — N-way comparisons on vs-comparison pages

**Reason (historical):** When #58 sketched 2-way side-by-side comparisons, N-way was declined as degenerating into an info table. The whole `/vs/` surface was later removed (#138); this entry stays only as the record of that earlier non-goal.

**Context:** #58 non-goal; superseded by #138.

## 2026-04-09 — Automatic benchmark scraping from provider websites

**Reason:** Scraping is fragile, violates most providers' ToS, and
creates a hidden data pipeline that can silently break. Users add
benchmarks manually for v1. Structured community contributions are
welcome via PR.

**Context:** #55 non-goal. Reconsider if a provider ships an
official machine-readable benchmark API.

## 2026-04-09 — USD cost estimates in token usage cards

**Reason:** Requires a pricing table that's correct at the moment
of rendering, which means either an external API call (bad —
kills offline mode) or a stale hardcoded table (bad — wrong
numbers are worse than no numbers). Will revisit after the v0.7
structured model schema (#55) landed, so cost can be computed
from the same pricing block users already maintain.

**Context:** #66 non-goal. #55 shipped; revisit in v0.10.

## 2026-04-09 — Rollback for append-only changelog entries

**Reason:** Append-only by design. If an entry is wrong, add a
correcting entry rather than deleting the original — preserves the
audit trail. Same rule as the wiki log.

**Context:** #56 non-goal.

## 2026-04-09 — Per-turn tool timelines

**Reason:** Would need turn-level structured data in every session
frontmatter (beyond the per-session aggregates in #63), which is a
5× larger converter output and bloats the search index. The
per-session bar chart from #65 covers the 90% use case.

**Context:** #65 non-goal. Reconsider if users start asking for it.

## 2026-04-09 — Success/failure counts per tool

**Reason:** The raw JSONL has `toolUseResult.isError` on every tool
result block, but wiring it through the converter aggregates
doubles the state-machine complexity. Defer until users ask.

**Context:** #65 non-goal.

## 2026-04-09 — Replicating qmd's hybrid search inside llmwiki

**Reason:** qmd already does hybrid BM25 + vector + LLM rerank.
llmwiki's built-in search is a deliberate "works offline, zero
deps, client-side fuzzy" design. Users who need hybrid search run
`llmwiki export-qmd` and point qmd at the output. Two tools, one
source of truth, no competing stacks.

**Context:** #59 non-goal. Reconsider only if qmd becomes
unmaintained.

## 2026-04-09 — Shipping qmd as a dependency

**Reason:** qmd is TypeScript/Node. llmwiki is stdlib Python plus
`markdown`. Adding a Node runtime as a dep would destroy the
"works on any 3.9+ Python, no other dependencies" promise.

**Context:** #59 non-goal.

## 2026-04-09 — Forcing users to create `_context.md` files

**Reason:** Folder-level context files are an optional navigation
hint. Making them mandatory turns them into busywork for sparse
folders and obscures their value for large ones. The `/wiki-lint`
warning (#60) nags at >10-file folders without a stub, which is
enough social pressure without blocking a build.

**Context:** #60 non-goal.

## 2026-04-09 — Auto-generating `_context.md` via LLM on sync

**Reason:** The whole point of `_context.md` is a human (or LLM
during `/wiki-query`) having a stable, reviewable description of
the folder's purpose. Auto-generating it on sync would make the
file drift every time the converter runs, which defeats the
caching benefit. A separate `/wiki-write-contexts` slash command
that takes user approval is acceptable — just not in the sync
pipeline.

**Context:** #60 follow-up, not a non-goal.

## 2026-04-09 — SEO schema.org markup on vs-comparison pages

**Reason (historical):** Vs-comparison pages were never a clean schema.org article type; half-correct markup was declined under #58. The `/vs/` surface itself was later removed (#138).

**Context:** #58 non-goal; superseded by #138.

## 2026-04-09 — CLAs or DCO sign-off for contributions

**Reason:** llmwiki is MIT. The added bureaucracy deters small
PRs and buys nothing the license doesn't already cover.

**Context:** #62 non-goal.

## 2026-04-09 — Enforcing governance retroactively on old issues

**Reason:** Issues #1–#61 were filed before the governance scaffold
existed. Re-triaging them would churn for no user benefit. New
rules apply to new issues.

**Context:** #62 non-goal.

## 2026-04-09 — Bots for automated triage

**Reason:** Manual triage via `/triage-issue <number>` is enough
for the current queue size (<60 open issues). Automated bots
create labeling noise and false positives. Revisit if the queue
grows past 300.

**Context:** #62 non-goal.

## 2026-08-09 — First-class open questions as a page kind

**Reason:** `type: question` sat in the vocabulary for years without a
single line of product creating one — no scaffold, no synth path, no
promote path — so it bought a graph colour and a legend label and
nothing else; an open question is a `concept` page with an unanswered
heading.

**Context:** #109. `llmwiki migrate-page-kinds` moves any hand-written
question page into `wiki/concepts/`. Reconsider only if question state
tracking (open / answered / stale) becomes a feature someone builds,
which is a lifecycle problem, not a page-kind problem.

## 2026-08-26 — Auto-generated `/vs/` model-comparison surface

**Reason:** `render_vs_section` had no production callers, hard-coded `REPO_ROOT/wiki`, and never emitted `site/vs/` on a real vault. Docs and nav still advertised Compare. Per the fork-residue inventory rule, remove the dead surface rather than wire it.

**Context:** #138. `/models/` (`render_models_section`, ai-model schema) stays. Reconsider only if a real demand for pairwise model diffs appears with a design that takes a vault path and is called from `build_site`.

## 2026-08-09 — Comparison pages as a page kind

**Reason:** A hand-authored `type: comparison` kind duplicated the word "comparison" without sharing machinery with anything else in the product and left readers unsure what it meant. Model diffs were briefly sketched as auto-generated `/vs/` pages from AI-model entity frontmatter; that surface was never wired and was later removed (#138).

**Context:** #109. `llmwiki migrate-page-kinds` moves any hand-written comparison page into `wiki/concepts/`. Reconsider a first-class comparison kind only if a real product need for authored side-by-side pages appears — not as a revival of dead `/vs/` code.

---

*Want to propose something that's on this list? File an issue with
a link to the entry and explain what's changed since the rejection.
Maintainers read proposals with an open mind, but "the idea is
cool" isn't a new argument.*

## 2026-08-16 — Slack / Discord export ingestion

**Reason:** Chat exports are conversation logs without an agent session's structure — no tool calls, no project, no model — so they would land in `raw/` as a shape the converter, the frontmatter contract and every downstream page format were not built for.

**Context:** Carried from the retired `docs/roadmap.md` (`W-L0-01`). Reconsider only if someone wants a chat adapter badly enough to design the frontmatter mapping first.

## 2026-08-16 — TUI browser for the wiki

**Reason:** The generated site is already browsable as plain files and the terminal audience is served by existing tools; a second UI would double the surface that every site feature has to ship into.

**Context:** Carried from the retired `docs/roadmap.md` (`W-L2-01`), which deferred to `raine/claude-history`.

## 2026-08-16 — Real-time collaborative editing

**Reason:** Not a product goal. The wiki is a single-operator artifact compiled from that operator's own sessions; collaboration happens in git, not in the page.

**Context:** Carried from the retired `docs/roadmap.md` (`W-L3-01`).

## 2026-08-16 — Precompiled Go / Rust binary

**Reason:** Python-first policy. A second toolchain would fork the build, the release pipeline and every adapter that reaches into a Python session store.

**Context:** Carried from the retired `docs/roadmap.md` (`W-L4-01`).

## 2026-08-16 — Sentry / telemetry

**Reason:** Privacy rule. The product reads a user's entire session history; shipping anything that phones home is incompatible with that, regardless of what is in the payload.

**Context:** Carried from the retired `docs/roadmap.md` (`W-L7-01`). Local-only usage telemetry (`llmwiki usage`) is the deliberate alternative — it never leaves the machine.

## 2026-08-16 — Supabase / Postgres backend

**Reason:** Stdlib-first rule. A database would make the vault something other than files on disk, which is the property that makes it greppable, diffable and portable.

**Context:** Carried from the retired `docs/roadmap.md` (`W-L7-02`).

## 2026-08-16 — Local HTTP server and server-side search

**Reason:** The server was removed and the site is plain files opened directly from disk, so `llmwiki serve`, the `serve.sh` / `serve.bat` wrappers, and the SQLite FTS5 server-side search fallback all lost the runtime they depended on. Search is the prebuilt client-side index.

**Context:** Carried from the retired `docs/roadmap.md` (`M-L3-15`, `M-L4-04`, `C-L7-02`), which still listed the server as a shipped Must long after it was deleted. Reconsider only together with a decision to reintroduce a runtime.

## 2026-08-26 — Eval framework / `llmwiki eval` subcommand

**Reason:** Never implemented. Docs and roadmaps advertised an eval framework / `llmwiki eval` as shipped since v0.3, and CI once ran a no-op behind `|| true`, so the check reported success while measuring nothing. Structural and wiki quality remains `llmwiki lint` / `/wiki-lint`.

**Context:** #154. Do not reintroduce a scoring CLI unless it is a real subcommand with tests; until then, lint is the quality gate.
