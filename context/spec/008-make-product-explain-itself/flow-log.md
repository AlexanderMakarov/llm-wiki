# Flow log — 008-make-product-explain-itself (#109)

## fetch-ticket — 2026-08-09

Fetched GitHub Issue #109 "docs: make the product explain itself — rebuild the demo from the real pipeline, settle page kinds, rewrite README" via `gh issue view`. Labels: `docs`, `important`. State: OPEN. No comments, no unreachable links. Body is a 5-section epic (demo rebuild → page body → page kinds → reference docs → README) with a mandated 1→2→3→4→5 ordering.

Cross-ticket note: #109 asks for #107 (link-check hygiene) to land first. #107 is still OPEN — flagged to the user, proceeding anyway; this spec owns only the links in files it changes.

Next: resume-detection.

## resume-detection — 2026-08-09

No existing spec dir for #109, no branch, no PR. Issue OPEN. Fresh start — entry point is workspace.

Next: workspace.

## workspace — 2026-08-09

- Branch: `feat/109-explain-the-product` off `origin/main` (b9817b0)
- Worktree: `.claude/worktrees/feat-109-explain-the-product`
- Throwaway vault: `$WT/.worktree-vault`, worktree `config.json` points at it; `llmwiki init` seeded
- `setup.sh` run with `LLMWIKI_SKIP_AUTOMATION=1` (needed `bash ./setup.sh` — file is not executable)

Next: specs (`/awos:spec`).

## specs — /awos:spec — 2026-08-09

Wrote `functional-spec.md`, Status: **Approved** by the user.

Scope grew well beyond the filed issue during the interview. Decisions taken:

1. **Page body (issue §2)** — stays facts-only. A synthesised description was rejected because nothing in llmwiki produces one; follow-up issue to be filed. (`consolidate-topics` writes *topic* descriptions to a cache, not page bodies — checked.)
2. **Page kinds (issue §3)** — remove `questions` and `comparisons` entirely ("I don't see a profit in them"); keep `syntheses`, documented as agent/human-authored. Removals go to `DECLINED.md`. The site's auto-generated *model* comparison view is a different feature and is untouched.
3. **Demo regeneration (issue §1)** — local maintainer command; output committed; CI never regenerates and never needs an AI model.
4. **Repo layout (new)** — demo becomes one self-contained folder (own raw/wiki/site); root stops being vault-shaped; `docs/videos/` removed; `specs/` relocated under `docs/`. `context/` **stays** (contributor tooling) — user's folder list said otherwise; recorded as an Open Point, user approved via "lgtm".
5. **Change detection (new)** — read from git history. Explicitly **not** mtime, and **not** a content-hash store. User first chose global content hashing, then reversed it: demo vault only, user vaults untouched.
6. **Agent-kit delivery (new)** — ship user-facing skills/commands inside the installable package plus a documented install command. This is the piece that fixes Homebrew.
7. **Delivery staging** — three stages on one branch chain: A = R1/R6/R7, B = R2–R5, C = R8–R10.

Research findings recorded during the interview (do not re-derive):

- Two demo surfaces existed: repo-root `wiki/` (23 tracked hand-authored files incl. `entities/ClaudeSonnet4.md`) and `examples/demo-wiki/sources/` (17 pre-synthesized). `pages.yml` runs `init` + copies + `build`, never `synth`.
- `raw/`, `site/`, `tmp/` are **already gitignored/untracked** — local working dirs only, nothing to remove from git. `context/` (57), `specs/` (10), `wiki/` (23), `docs/videos/` (4) are tracked.
- Core adapters are `claude_code` + `codex_cli` only; 10 others are contrib. README wrongly lists Copilot Chat/CLI, Gemini CLI, Obsidian as core and omits `chatgpt` + `opencode`.
- `docs/reference/ui.md` **already has** a `## Topic pages` section (added by #108/PR #128) — issue §4's checkbox for it is already satisfied; verify, don't rewrite.
- CLI capability audit: `add --vault`, `synth --vault/--docs-only/--path`, `build`, `lint --fail-on-errors`, `all --strict` all exist. Missing: a single demo-regen command, and CI lint against the demo.
- **Verified by experiment** (throwaway vault, artifacts cleaned): re-adding an edited doc creates a *second* snapshot (`test-doc` → `test-doc-2`) and keeps the original; re-adding an unchanged doc is correctly skipped by content hash; `remove` cascades correctly; **remove-then-add preserves the slug**. There is no in-place document update. `add` dedups by `content_sha256`, but `synth` staleness is mtime — two different mechanisms, neither implementing "changed".
- `.claude-plugin/plugin.json` + `marketplace.json` exist but are **broken**: `path: "."` + `commands/wiki-init.md` resolves to `./commands/` which does not exist (real: `.claude/commands/`); author/homepage point at upstream `Pratiyush`; declares `python >=3.9` vs actual `>=3.12`; lists 7 of ~15 commands and 3 of ~5 user skills.
- `pyproject.toml:105-109` packages `llmwiki*` only — no skills/commands ship with pip/brew. Confirmed root cause of the incomplete packaged install.

Next: `/awos:tech` (approval gate).

## specs — /awos:tech — 2026-08-09

Wrote `technical-considerations.md`, Status: **Approved** by the user.

Design decisions taken during the interview:

1. **Page-kind removal** — hard cut with a migration (new `migrate-page-kinds` subcommand, following the `migrate-*` convention). Retype `question`/`comparison` → `concept`, relocate into `wiki/concepts/` keeping the filename, delete the two `_context.md`, prune the empty dirs, leave non-empty dirs alone and report.
2. **Demo refresh** — `scripts/refresh_demo.py`, maintainer-only, never shipped. Rejected a CLI subcommand (would ship a repo-only surface to every user — the exact dishonesty this epic removes) and a Makefile (no Makefile exists; the git-selection logic deserves tests).
3. **CI gate** — repair `wiki-checks.yml` rather than replace it.
4. **Installer** — `install-agent-kit --dest PATH`, required flag, no auto-detection, `.bak` on conflicting content.
5. **Lint left untouched** (user directive, late change). `--strict` was dropped; gate is `lint --vault demo --fail-on-errors`.

Assumptions stated and accepted: demo folder is `demo/` at repo root; `demo/site/` stays gitignored (CI builds it); `.claude-plugin/` is deleted.

**Amendment to the approved functional spec:** R4 changed from "zero errors AND zero warnings" to errors-only. Cause: the only rule warning on the demo is `content_freshness` (>90 days since `last_updated`), which on a committed artefact measures elapsed time only and would redden CI on a timer. Excluding one rule needs either a drifting `--rules` allowlist or a lint change; lint is out of scope by user directive. Accepted cost, recorded in the risk table: `link_integrity`, `stub_source_pages` and `duplicate_detection` are warning-severity and will NOT fail CI.

Additional findings this stage (verified, do not re-derive):

- **`init` does NOT scaffold `questions/` or `comparisons/`** — the issue's premise is wrong. Verified against a fresh vault: `cli.py:224` creates only `raw/sessions`, `wiki/{sources,entities,concepts,projects,syntheses}`, `site`, `wiki/hot`. Those folders exist only as the tracked `wiki/comparisons/_context.md` plus code references.
- **`reindex.py:26`** already catalogues non-canonical folders generically, so an existing user vault with those folders keeps working — no migration needed for the *folder*, only for any page carrying the removed `type:`.
- **`schema.PAGE_KINDS` (schema.py:50-58)** is the single vocabulary source feeding `lint/rules/frontmatter_validity.py:19` AND the MCP tool schema — one edit changes both.
- **Removal surface is 14 files**, wider than the issue's 9: adds `topics_page.py:44`, `graphify_bridge.py:409`, `reindex.py:26` (docstring), `schema.py`, `lint/rules/duplicate_detection.py`, `mcp/server.py`, `usage.py`.
- **`wiki-checks.yml` is broken**: triggers on `master` (fork uses `main`, so push never fires), and calls `python -m llmwiki eval` — **not a subcommand** — masked by `|| true`. Verified: `eval` is absent from the CLI choices.
- **Lint rule severities**: 4 error (`frontmatter_completeness`, `frontmatter_validity`, `index_sync`, `provenance_integrity`), 9 warning, 4 info. Current repo `wiki/` lints to exactly 9 issues, all `content_freshness`.
- **Lint is not config-aware** — only `config_schedule.py` mentions lint, for scheduling.
- `scripts/` already mixes `.py` and `.sh` maintenance scripts — precedent for `refresh_demo.py`.
- 219 test files; acceptance convention is `tests/test_<issue>_acceptance.py`.
- No Python/CLI/packaging specialist agent registered (only `testing-expert`) — tech sections drafted without one; gap noted for `/awos:hire`.

**Open risk carried into implementation:** the migration assumes `[[wikilink]]` resolution is name-based, not path-based. NOT yet verified. If path-based, the migration must rewrite inbound links too. Flagged in the risk table with a dedicated test.

Next: `/awos:tasks` (no approval gate under /implement-feature — write, summarise, continue).

## specs — /awos:tasks — 2026-08-09

Wrote `tasks.md`: 74 tasks across 14 slices, grouped into the three PR stages from R11. No approval gate (delivery-flow §10 local customization); summarised in chat as informational.

Authoring decisions:

1. **`pages.yml` repoint moved from Stage B to Stage A** (Slice 1). The tech spec's stage table put it in B, but moving the demo in A while the publish workflow still points at `examples/demo-*` and root `wiki/` would leave the public site broken between two merges. Deviation recorded at the top of `tasks.md`.
2. **Slice 5 leads with the wikilink-resolution spike** and states that a path-based result enlarges Slice 6 (migration must rewrite inbound links). The unknown is scheduled rather than assumed.
3. **Slice 9 is written to refuse a fake.** If `synth --check` finds no backend, the task stops and escalates instead of hand-writing demo pages — hand-authored demo content is the exact defect #109 exists to remove. The worktree currently has the `dummy` backend, so this will block until a real one is configured.
4. Agent assignment: `general-purpose` for all implementation (no Python/CLI/packaging specialist registered), `testing-expert` for Slice 14.

Recommendations table in `tasks.md` records: the general-purpose fallback, the packaging-specialist gap (compensated by a distribution-content test), the Slice 9 backend prerequisite, and the errors-only CI gate leaving three warning-severity rules unenforced.

Next: commit specs, then `/awos:implement`.

## implement — Stage A (Slices 1–6) — 2026-08-09

All six Stage A slices complete. Tests **3958 passed / 48 skipped** (baseline at branch start 3887/48; +71 net new tests). `ruff check llmwiki tests scripts` clean. `llmwiki build --vault demo` exits 0, 136 HTML files.

Dispatched one subagent per slice rather than per task (deviation from `/awos:implement` step 3): slice tasks here are inseparable file-level operations, and splitting a `git mv` from its dependent path updates across two cold agents would leave the repo broken between calls.

Slice outcomes:

1. **Demo → `demo/`** — all moves via `git mv` (history preserved). `tests/fixtures/demo/` moved too: `demo/wiki/sources/demo-alpha|demo-beta` are pre-synthesized pages for exactly those sessions. `examples/demo-wiki/README.md` → `demo/README.md`, rewritten as a demo-vault README. `pages.yml`, `ci.yml`, `agents-e2e.yml` all repointed to `--vault demo`.
2. **Repo-root guard** — `.llmwiki-source-checkout` marker + `llmwiki/source_checkout.py`. Guard sits at the single shared `apply_default_vault` border in `cli.py`, covering the 8 vault-writing subcommands (`init`, `sync`, `synth`, `synthesize`, `add`, `build`, `all`, `watch`). Read-only and in-place commands deliberately unguarded. 19 tests.
3. **Dead assets** — `docs/videos/` removed; `specs/` → `docs/maintainers/surfaces/`. All three demo-recording scripts KEPT (none existed to produce the deleted videos) but two were repaired: they ran bare vault commands that Slice 2's guard now refuses.
4. **Page-shape docs** — description-paragraph line removed from `CLAUDE.md` and `AGENTS.md` templates. Source-page `## Summary` deliberately preserved (it is a real produced field). Follow-up issue **#137** filed.
5. **Kind hard-cut** — `question`/`comparison` removed from `PAGE_KINDS` and all real call sites. 27 tests.
6. **Migration** — `migrate-page-kinds` subcommand, 25 tests. DECLINED.md entries dated 2026-08-09. Follow-up issue **#138** filed.

### Findings that changed the plan

- **SPIKE RESOLVED: wikilink resolution is name-based, not path-based.** `llmwiki/wikilinks.py` parses `[[Target]]` to a bare name; every consumer keys by filename stem. Folder determines only kind and site URL. The migration therefore does NOT rewrite inbound links. Risk row in `technical-considerations.md` updated with the evidence. Proven by `tests/test_page_kinds.py::test_wikilink_resolution_survives_a_move_between_wiki_folders`.
- **`render_vs_section` is dead code** (`llmwiki/build.py:2470`) — zero production callers, only tests. The "Model comparisons" surface the tech spec ordered preserved never renders in any build; proven by an identical 136-file build-output diff before/after Slice 5. It also hardcodes `REPO_ROOT / "wiki" / "entities"`, now nonexistent. Filed as **#138**. The tech spec's "must survive untouched — a test must pin that it still renders" was wrong: reading a function does not establish that anything calls it.
- **3 of the 14 tech-spec call sites were false positives**: `graphify_bridge.py:409` (graphify's `suggest_questions`), `categories.py:50` and `docs_pages.py:645` (already only surviving folders), `lint/rules/duplicate_detection.py` (English word). Editing them blindly would have broken graphify.
- **`.gitignore` had three instances of the unanchored-pattern trap.** `raw/`, `usage/` and the collapsed `/wiki/` all match at any depth unless anchored; unfixed, each would have silently excluded part of `demo/` from git.
- **`llmwiki build --vault demo` mutates tracked `demo/usage/daily.json`** (MCP read reclassification). Idempotent, but CI leaves a dirty checkout after every build — matters if Slice 10 adds a no-diff assertion.
- **VERIFIED: plain `llmwiki lint` exits 0 even with error-severity findings** (probe: 2 errors, exit 0). Only `--fail-on-errors` exits non-zero (exit 1). Slice 10's gate MUST pass that flag or it enforces nothing.
- **`lychee.toml` excludes `wiki/` and `raw/` as bare substrings**, which now also match `demo/wiki/` link targets; `link-check.yml` scans `docs/**` and `examples/**`, neither reaching `demo/**`. Demo link-checking is a hole with two independent causes — Slice 10 / R9.
- Migration deliberately lives in the package, not `scripts/`: `pyproject.toml` packages only `llmwiki*`, so a `scripts/`-based migration cannot run from a pip or Homebrew install — exactly the users it exists for.
- Migration needed one scope addition for R7: `reindex` cannot clear a catalog section whose backing folder was pruned, so the migration unlists those bullets itself. Without it the migrated vault reported 2 `index_sync` errors.
- Pre-existing, left alone: `docs/modes/agent/{index,backend}.md` have a broken `../UPGRADING.md` link (needs one more `../`).

Next: `/awos:verify` scoped to Stage A criteria (R1, R6, R7) — must NOT mark the whole spec Completed.

## verify — Stage A (R1, R6, R7, R11-A) — 2026-08-09

Verdict: **Stage A PASS.** Spec Status deliberately left `Approved`, NOT `Completed` — Stages B (R2–R5) and C (R8–R10) are not implemented. Gates after verification: ruff clean; pytest **3958 passed / 0 failed / 48 skipped**; `build --vault demo` exit 0.

Per-criterion evidence:

- **R1** — `demo/` holds `raw/`, `wiki/`, `usage/`, `README.md`; `demo/site/` ignored (confirmed via `git check-ignore demo/site/index.html`); state files ignored; nothing untracked under `demo/`. Bare `python3 -m llmwiki init` with `config.json` moved aside → **exit 2**, actionable message naming `--vault` and `demo`, and no `raw/`/`wiki/`/`site/` created. `docs/videos/` gone; `specs/` gone, 10 files under `docs/maintainers/surfaces/`. `context/` present. Top-level listing shows `demo/` plainly.
- **R6** — Both agent templates now run `# Name` → `## Key Facts` with no description line. Issue **#137** confirmed OPEN via `gh`.
- **R7** — `PAGE_KINDS == ('source','entity','concept','project','synthesis')`. Only residual references are `migrate_page_kinds.REMOVED_FOLDERS` (required by the migration) and graphify's unrelated `suggest_questions`. Two dated `## 2026-08-09` DECLINED entries present. Migration exercised on a realistic scratch vault (demo copy + a legacy `type: question` page): migrate exit 0, page relocated to `wiki/concepts/` with filename intact, folder pruned, `build` exit 0, `lint --fail-on-errors` exit 0, `link_integrity` clean.
- **R11 Stage A** — R1/R6/R7 delivered together; repo buildable at slice granularity.

### Three gaps found by verification and fixed in-stage

1. **R6 reason was not actually recorded.** The spec deferred the description idea but never stated *why*. Out-of-Scope now records the reason (no step produces one; the prompt mandates bullets with no preamble; a harvested stub is a title plus an empty facts heading) and links #137.
2. **`synthesis` was not honestly described.** Nothing said saved answers are agent/human-authored. `CLAUDE.md` and `AGENTS.md` now state "no pipeline step generates one."
3. **`context/` was not named as contributor tooling.** `CONTRIBUTING.md` said AWOS tooling generally; it now names `context/` explicitly and states it is never shipped and never appears in a user's vault.

### Honest qualification on one criterion

R7's "the site's auto-generated model comparison view still works and is unaffected" is satisfied **only in the sense that nothing regressed**. `render_vs_section` has zero production callers, so the surface never rendered in any build — before or after. Proven by an identical 136-file build-output diff. Filed as **#138**. It must not be reported as a working feature.

### Pre-existing defect confirmed, NOT introduced by Stage A — blocks Slice 10

The demo vault is **not lint-clean and never has been**. Measured against a reconstruction of the `origin/main` demo (its own `wiki/` plus the `examples/demo-*` seeding `pages.yml` performed):

| Rule | origin/main | Stage A |
| --- | --- | --- |
| `index_sync` (error) | 16 | 16 |
| `provenance_integrity` (error) | 4 | **0** |
| `link_integrity` (warning) | 32 | 32 |
| `content_freshness` (warning) | 9 | 9 |

Stage A removed 4 errors and introduced none. CI never caught this because `wiki-checks.yml` runs on a dead `master` trigger and calls a nonexistent `eval` subcommand. **Slice 9 must produce a clean demo before Slice 10 turns the gate on** — the existing task order already reflects this.

Read-only probe of the operator's live vault: no `wiki/questions/`, no `wiki/comparisons/`, zero pages carrying a removed `type:`. The migration is a no-op there.

Next: Step 8 — user smoke confirm, then single independent local review.

## scope change — R12 added (remove the server) — 2026-08-10

User directive during Stage A smoke confirm: cut the HTTP server entirely, static site only. Chosen option: **remove `serve`, move candidate review to the CLI.**

Investigation that shaped it:

- `llmwiki/serve.py` (225 lines) is not only a static file server — it hosts `POST /api/candidates`, the backend for the #97 review UI. `candidates.html` posts batch decisions to it. A naive delete would remove a shipped feature this epic's README rewrite is meant to advertise.
- **The removal is not lossy.** `llmwiki candidates apply --actions JSON` already accepts the identical batch shape; its own help text reads "same shape as POST /api/candidates". The CLI is a complete substitute.
- **The built site is already file-openable by design**: it loads data via `<script src="llmwiki-state.js">` (a `.js`, not a fetched `.json`) and uses no `type="module"` scripts. The only same-origin `fetch` is `candidates.html` → `/api/candidates`, removed by this work. A `highlight.js` CDN tag remains — syntax highlighting alone needs network. Pre-existing, out of scope, recorded not fixed.
- **`serve` was never the idle cost.** It is foreground-only. Probing the operator's machine found 5 live `llmwiki.mcp` processes and one monthly `synthesize` cron entry — those are what persist. User elected to ignore the MCP processes.
- That cron runs `python -m llmwiki synthesize` from the repo root with no `--vault`; it survives Stage A's guard only because the gitignored primary `config.json` sets `vault.default_path`. That config is now load-bearing.

**Placement: R12 leads Stage C, not a new stage.** It edits README, `CLAUDE.md`, `AGENTS.md`, the agent kit, and `docs/**` — exactly the files Stage C already rewrites. A separate stage would edit all of them twice. Ordering it first means the documents written afterwards describe a static-file product. A naming collision with the tech spec's existing "Stage A2" sub-section was resolved by naming the new section **Stage C0**.

Spec updates: `functional-spec.md` gains R12 and an amended R11 staging bullet; `technical-considerations.md` gains a Stage C0 section, an approach line, and a risk row; `tasks.md` gains Slice 11 and renumbers the old 11-14 to 12-15, with cross-references corrected.

**Stage A is unaffected** — it stays as verified, and goes to review and PR as-is.

## scope addition — vendor highlight.js (R12) — 2026-08-10

User directive: load highlight.js from local files, as vis-network already is. Folded into R12 rather than made separate — same requirement (a site that works with nothing running and nothing fetched).

Verified specifics:

- The site pulls **three** files from `cdn.jsdelivr.net`, not one: `highlight.min.js`, `github.min.css`, `github-dark.min.css`, all pinned 11.9.0. After vendoring these, the built site references no `https://` script or stylesheet at all.
- Precedent to copy exactly (#127): `llmwiki/vendor/vis-network.min.js` + `llmwiki/vendor/NOTICE`; constant `VIS_NETWORK_VENDOR` at `graph.py:31`; `shutil.copy2` into the output at `graph.py:681`; relative `<script src>` with an `onerror` offline notice at `graph.py:540`. NOTICE records project / version / license / homepage / source / repository.
- **`pyproject.toml:109` packages `vendor/*.js` only.** Adding CSS without extending that glob would ship the JS and silently drop both themes — visible only to pip/Homebrew users, never in a source checkout. Task added, and the distribution-content test must assert it.
- Degrading to unstyled code blocks is acceptable if highlighting fails; no offline notice needed (unlike the graph, which is unusable without its library).

Also resolved this turn: the operator could not find `demo/site/index.html` because `demo/` exists only on the uncommitted feature branch inside the worktree — the primary checkout is on `main` and has no `demo/`. Build output confirmed present at `<worktree>/demo/site/index.html` (180 files).

## implement — Slice 9 (demo corpus) — 2026-08-10

User directive during smoke confirm: demo sessions are dummy; use real anonymised sessions (OpenClaw, not Gemini); projects are 4 months old and leak `/home/4ellendger`; graph too small with no entities or concepts; demo build must run `synth` via `claude -p` with haiku.

**Privacy position taken and stated.** The live vault holds 1177 sessions: 1098 contain absolute `/home` paths, 142 contain `/mnt` paths, 163 distinct non-public hostnames appear. The `#56` redactor covers usernames and secret-token shapes only — not hostnames, neighbouring project names, or private infrastructure named in prose. The demo is published publicly and irreversibly, so a bulk export was rejected in favour of a **curated, auditable subset**.

**False alarm resolved:** the `/home/4ellendger` the operator saw appears **only** in `demo/site/` (gitignored, rebuilt by CI). Source files carry zero. The `#56` redactor stores `USER` and *restores* the real username at build time for local viewing; CI builds under its own user. `origin/main` has zero occurrences under `wiki`/`examples`.

**`scripts/curate_demo_sessions.py`** (new) — deterministic, re-runnable, auditable:

- Selects by topic keyword score (CLI / site / adapters) so the corpus covers what the product does; prefers top-level sessions over subagent children (111 of 210 llm-wiki candidates were subagents, which read as fragments).
- Scrubs: username literals, `/home`, `/Users`, `/mnt` paths, emails, and every non-public hostname (allowlist of public docs/package hosts). Session ids replaced with a deterministic digest, `cwd` and `source_file` neutralised.
- **Scrubs neighbouring projects automatically** — every project in the source vault not being imported becomes `other-project` — plus `--scrub-term` for private infrastructure a pattern cannot infer.
- Rewrites dates: two historical, the rest inside the last two weeks.
- Names files by dominant topic plus a short digest, because real transcript titles are empty and the original names carried agent/subagent identifiers.
- `--audit` re-scans the written corpus and is run automatically after every write.

**Findings during curation:**

- OpenClaw sessions live in project `openclaw-main`, not `llm-wiki` — so the demo now carries **two** projects and **two** adapters (9 `llm-wiki` claude_code + 3 `openclaw-main` openclaw), which also fixes the "projects all 4 months old" complaint.
- First pass leaked a neighbouring project's name, and reading the context showed several private infrastructure service names alongside it. Generic project scrubbing plus an explicit term list was added; the second pass was clean. The specific literals are deliberately not recorded here — this file is committed.
- The audit's own placeholder `internal.example.com` failed its allowlist anchor (`example\.com` did not match a subdomain). Fixed to `([A-Za-z0-9-]+\.)*example\.com`.

**Verification:** script audit 0 findings; an independent scan over nine identifying literals (the operator's username, vault directory, neighbouring project names and private service names — not reproduced here) returned 0 hits each. Remaining hosts: `internal.example.com` (58), `github.com` (25), `localhost` (3). Remaining absolute paths: `/home/USER` only.

**Synth backend:** worktree `config.json` (gitignored) set to `synthesis.backend = "claude"` — note the accepted value is `claude`, **not** `claude_cli`; the latter silently falls back to dummy with a warning. Model `haiku`, concurrency 4. `synth --check` reports `claude-cli / Available: True`. Estimate: **$0.18** for the 12 new sources.

## implement — Slice 9 (synth + candidate review) — 2026-08-10

Ran the real loop on the demo: `synth` (claude -p, haiku) → candidate review → `build` → `graph` → `lint`.

**Synth:** 16 sources, 224s, 142,646 tokens, **$0.53**. Note the `--estimate` figure was $0.18 because it counted only the 12 new sessions and not the 4 docs — the estimate undercounts a mixed corpus.

**Removed the fabricated content** #109 indicts: 8 hand-authored entity/concept pages (`ClaudeSonnet4.md` opened with exactly the prose paragraph the issue names, and all 8 were about AI models, not llmwiki) plus 12 source pages and 3 project pages for the fictional `demo-alpha/beta/blog-engine/ml-pipeline/todo-api`.

**Candidate review, actually exercised** via `candidates apply --actions -` (the same CLI path that replaces the review UI under R12 — so this doubles as validation of that decision). At `--min-refs 3` only 1 candidate appeared, so harvested at 1 for 11, then: merged `wikilinks` + `ObsidianWikilinks` into `WikiLinks`, discarded `Hetzner` (unrelated project's hosting), promoted the remaining 8. Zero pending afterwards.

**Promoted page shape verified correct** — `# Name` → `## Key Facts` (attributed bullets) → `## Connections`, no prose intro. This is the shape R6 ratifies.

### Results

| | before | after |
| --- | --- | --- |
| graph nodes / edges | 15 / 0 (site), no entities or concepts | **30 / 41** with 6 entities + 2 concepts |
| broken graph edges | 3 | 4 (all from filed defects) |
| lint issues | 73 (16 `index_sync` errors) | **2, both warnings** |
| `lint --fail-on-errors` | exit 1 | **exit 0** |
| projects | 3 fictional, all ~4 months old | 2 real, dates spread across 2 weeks |

### Two product defects the rebuild exposed — filed

- **#139 — merge records aliases nothing reads.** `candidates.py:818-822` writes `## Aliases` on merge; no resolver consults it (`graph.py`, `wikilinks.py`, `link_integrity.py`, `backlinks.py` all clean on grep). Resolution is by filename stem, so **every merge permanently dangles every existing inbound link** — 3 of the demo's 4 broken edges. Also folded in: `candidates_harvest.py:260` writes the evidence count at harvest time and a merge never recomputes it, so `WikiLinks.md` read "Named by 1 source page(s)" directly above a list of 2.
- **#140 — `archive/` treated three different ways.** `reindex` catalogs it into `index.md`; `lint/__init__.py:112` deliberately excludes it; `graph` includes it as valid link targets. Consequence: `index_sync` reports its own catalog entries as dead links at **error** severity on a correct vault, which would fail Slice 10's gate for any user who has ever discarded or merged a candidate. Worked around here by deleting `demo/wiki/archive/` and pruning the index with the existing `_prune_index_links` helper.

### Other findings

- `demo/wiki/overview.md` was hand-authored, dated April, described the old demo and linked three deleted projects (the 3 original broken edges). Rewritten to describe the actual demo honestly — that it is real pipeline output, anonymised, two projects, two adapters, and that no page carries a synthesised description because nothing produces one.
- Remaining 2 lint warnings and 4 broken edges are entirely attributable to #139 and one deliberate discard. Kept rather than papered over: a discarded candidate genuinely leaves its mention dangling, which is real product behaviour.
- `entities/Karpathy Wiki.md` carries a space, against the documented TitleCase convention. `promote` does not normalise the slug. Not yet filed.

## implement — Slice 9 rebuilt on synthetic sessions — 2026-08-10

**Real transcripts abandoned.** Anonymisation failed three times on three different classes, each caught by a different mechanism and none by the purpose-built scrubber:

1. Structural identifiers (paths, hosts, usernames) — caught by the scrubber.
2. Unrelated private subject matter (therapy assessment instruments, another project) — caught by `lint`'s broken-wikilink report, because synth had extracted them as subjects with no page.
3. Personal name, an app name, a channel handle — caught by **the operator**, after both the scrubber and the audit reported clean.

The corpus is public and permanent, so pattern-matching against a space that cannot be enumerated was the wrong bet. User chose authored sessions.

**`scripts/curate_demo_sessions.py` deleted.** Replaced by **`scripts/generate_demo_sessions.py`**: 25 authored transcripts, 7 projects, 4 agents. Deterministic apart from `--today`.

**Three defects in the generator found by operator review, all mine:**

- Emitted an `adapter:` frontmatter field that **nothing reads**. `detect_agent_label` reads `agent:`.
- Gave every session a `claude-*` model — and the model check in `detect_agent_label` runs **before** the source and tag checks, so all 25 sessions rendered as "Claude" regardless of intent. Now Claude 15 / OpenClaw 4 / Cursor 4 / Codex 2, and Codex sessions run a Codex model.
- Dates clustered in one week. Now decay across four months (Apr 2 · May 3 · Jun 3 · Jul 8 · Aug 9), one session at 120 days.

**Docs corpus 4 → 70 documents (119 files after the product's chunking)**, ingested from real `docs/` excluding contributor-only `maintainers/` and the `i18n/` translation.

- First attempt used `--project llm-wiki`, which put every file under one top-level folder. `group_documents` treats a shared top-level folder as **chunks of one document**, so Home's "Recent raw documents" showed a single entry with 119 parts. Re-ingested without `--project`: 70 entries.
- **Filed #141** — `llmwiki add` writes the **absolute** source path into raw frontmatter unredacted, while `sync` redacts the same thing for sessions. 119 files carried the operator's home directory. Invisible in the UI; only a grep finds it. Stripped by hand for the demo.

**Usage fixture regenerated** (`scripts/generate_demo_usage.py`): 82 records over 18 days with realistic misses, so Analytics' zero-hit column reports 23% / 19% / 12% / 14% / 20% instead of 0% everywhere. Reporting tools stay at 0% because they cannot miss. `daily.json` is folded by the product's own `refresh_daily()` rather than maintained separately, so the two cannot drift.

**Spec additions this session:** R12 (remove the server, candidate review moves to the CLI — `candidates apply --actions` already accepts the identical batch shape); R13 (displayed local paths become an explicit `build` input rather than a reversal of import-time redaction, so builds are reproducible). Both land in Stage C, R12 first, because the documents written afterwards must describe the result.

**Synth deliberately not run.** The operator holds that lever — it is the only step that spends money. Corpus is staged and priced at ~$1.57 for 144 sources.

## smoke confirm — passed — 2026-08-11

Operator reviewed the rebuilt demo site and confirmed it. Satisfies the delivery-flow §4 user smoke-confirm gate for the work committed so far (Stage A plus the demo corpus).

Reported and fixed during that review, all mine rather than product defects:

- The generator emitted an `adapter:` frontmatter field that nothing reads; `detect_agent_label` reads `agent:`. Compounded by the model check running before the source and tag checks, so every session rendered as "Claude" despite four adapters being represented.
- Session dates clustered inside one week instead of decaying across four months.
- Docs ingested with `--project` collapsed into a single Home entry, because `group_documents` treats a shared top-level folder under `raw/docs` as chunks of one document.
- The Analytics zero-hit column read 0% for every tool because the telemetry fixture contained no misses.

## sequencing change — docs before synth — 2026-08-11

Operator: no point synthesising the demo now, because the docs it is built from are about to be rewritten. Measured blast radius on the 70-document demo corpus: **19 mention `serve`**, 13 mention the server or its API, 2 mention the removed page kinds. Synthesising now would pay to summarise text that Stage C replaces, then pay again.

Revised order: **Stage C docs and product changes first, then one synth at the end.** This inverts the spec's Stage B → Stage C order for the demo-content step only; the refresh script still belongs to Stage B and is what makes subsequent doc edits cheap.

**Consequence for the PR plan (R11):** the branch now carries Stage A, the Stage B demo corpus, and Stage C work together, so the three-PR split recorded in R11 no longer matches reality. Raised with the operator rather than drifting silently.

## spec change — no served site anywhere — 2026-08-11

Operator directive after reviewing the demo: "No served site at all. Everywhere... it should be removed with all tooling around it. Everything should be checked on static site from now on."

Two defects in the previous specification prompted this.

**1. R12 stated a property without stating its evidence.** It required the site to work as files, but said nothing about how that is verified — so the entire browser suite reached the site over HTTP via `ThreadingHTTPServer` while the server was being removed from the product. Every check passed and none exercised the claim. The operator noticed the browser running against a served page, not the files.

This is the same failure shape as the `eval` / `check-links` workflow tests replaced earlier today: a check whose form implies coverage it does not provide. There the assertion pinned a string rather than a behaviour; here the harness exercised a transport the product no longer uses.

**2. R12 was ambiguous enough to license removing a working feature.** "Reviewing candidates is possible entirely from the command line" was implemented as *the page becomes read-only*, deleting per-row decision controls and Apply. Only executing decisions ever needed a server; deciding is state held in the page. "Calls an endpoint" was collapsed into "needs an endpoint", and a capability was lost that the removal did not require.

Spec changes:

- **R12 rewritten** — no command, no helper, **no endpoint of any kind**, and nothing in the project serves the site for its own purposes either: not the test harness, not a screenshot script, not a workflow, not an editor launch task.
- **R12a added** — the browser tests open the built files. No test starts a server. They walk the surfaces a reader uses and fail on a console error or a failed load. Carries a note explaining why this is a requirement rather than an implementation detail: a file URL is a different origin model, not a slower HTTP one.
- **R12b added** — the review interaction stays in the page; only execution moves to the command line. A row starts with **no decision**, so applying without deciding yields an empty batch rather than promoting everything. Carries a note recording the conflation that caused the regression.
- **Tech spec** gains Stage C0a, tabulating the six places that still serve the site and what each becomes, and recording that Chromium under Playwright does navigate `file://` — an earlier agent's claim that it blocks the scheme was wrong.
- **Slice 11 rewritten** with the fuller scope.

The agent restoring the candidates page was stopped mid-verification so the specification could be corrected first. Its work — `candidates_site.py`, CSS, two test files, docs — is uncommitted in the tree and was not discarded.

## merge target becomes a closed, filterable list — 2026-08-13

Operator: the merge control "presents as a plain text box — I did not recognise it as a chooser at all", and it accepted any string. An `<input list=…>` over a `<datalist>` offers typeahead but looks like free text, and `merge()` resolves a target under `wiki/<kind>/` or a pending peer, so an invented name failed later, after the reviewer had moved on.

The Into field is now a combobox over the same `merge_targets()` list: the ▾ button or `↓` opens it whole, typing narrows it by case-insensitive substring, `↑`/`↓`/`Enter`/`Esc` drive it, and the list is the closed set of valid targets — a value that names no page is flagged as it is typed and never enters a batch. Target names are embedded once per kind as inline JSON rather than repeated per row, so a long backlog does not multiply the page size by the size of the vault.

Same pass, same page: **the discard reason is required**. `discard` writes `<slug>.reason.txt` beside the archived stub, so a blank reason loses the decision rather than merely being untidy. A row set to *Discard* with no reason is held back exactly the way an unresolved merge target is — one mechanism, one message, one marked field, focus moved to it — instead of silently producing a reasonless action or silently vanishing from the batch.

Observed while doing it, and filed separately by the operator rather than fixed here: **nothing reads `.reason.txt`**. Harvest has no memory of what a reviewer rejected, so a discarded candidate is re-proposed on the next run.

## Slice 12 — page-kind reference (R8) — 2026-08-15

Wrote `docs/reference/page-kinds.md`. Provenance for every field taken from the producers: `_build_source_page`, `_stub_text`, `ensure_project_stubs`, `init` seeds, `_auto_archive_log`, `categories.py`, `context_md.py`. No committed demo entity/concept/project/source wiki pages — examples that exist (`overview.md`, `CRITICAL_FACTS.md`, two `_context.md` files, raw sessions/docs) are linked; the rest name the producer rather than inventing a path. `docs/reference/ui.md` Topic pages section left intact except one cross-link. `tasks.md` not edited.

## Operator skip — no full demo synth — 2026-08-15

Operator: do not run `llmwiki synth` against `demo/` for this PR. The review they want is the static site shape (raw docs, sessions, analytics) and the docs shape. A full wiki regeneration (Slice 9) is deferred; untracked partial `demo/wiki/sources|candidates|entities` stay local and are not committed. `demo/.demo-source-rev` is not created.

Mechanism to keep the demo current when `docs/` change, without putting a model in CI:

- `scripts/refresh_demo.py` (local, needs a backend) — Slices 7–8, follow-up in-place update is #151
- pre-push reminder when product markdown under `docs/` (not `docs/maintainers/`) is in the push
- wiki-checks path filter includes `docs/**`; if `demo/.demo-source-rev` is later committed, the job prints `refresh_demo.py --dry-run` (never synth)

Demo site rebuilt locally with `build --vault demo --out demo/site --local-root /home/user` for inspection (119 document pages, 25 sessions, analytics, candidates).

## Operator: commit the partial wiki for GitHub Pages — 2026-08-15

The published demo is `pages.yml` building `--vault demo`. An empty `wiki/sources/` catalog meant Pages had sessions and docs HTML but no synthesized knowledge layer, no promoted topics, and an empty candidates queue.

Committed the existing synth output: 99 source pages, 2 entities, 3 concepts, 10 pending candidates. Reconciled `wiki/index.md`. Rewrote `overview.md` Connections to pages that exist. `lint --vault demo --fail-on-errors` is 0 errors (warnings remain). Full `refresh_demo.py` + `demo/.demo-source-rev` still not done.

## `candidates apply` rebuilds the site by default — 2026-08-15

Operator: after promotion/merge/discard the static candidates page still showed the old queue. `llmwiki candidates apply` now rebuilds `site/` after a successful batch; `--no-rebuild` opts out. One-off `promote` / `merge` / `discard` are unchanged. Spec R12b gained that acceptance criterion.


