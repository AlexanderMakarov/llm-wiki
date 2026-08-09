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
