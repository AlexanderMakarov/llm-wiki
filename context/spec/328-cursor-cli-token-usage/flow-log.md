# Flow log — 328-cursor-cli-token-usage

## fetch-ticket
- Issue: https://github.com/AlexanderMakarov/llm-wiki/issues/325
- Title: feat(cursor_cli): investigate and capture native token usage
- Labels: enhancement, important, self-heal (no bug → /implement-feature)
- Next: resume-detection / workspace

## resume-detection
- Issue OPEN; no prior owning spec for this work; no merged PR for Cursor CLI token capture
- Next: workspace

## workspace
- BRANCH: feat/325-cursor-cli-token-usage
- WT: .claude/worktrees/feat-325-cursor-cli-token-usage
- TMP_VAULT: WT/.worktree-vault
- Next: specs (/awos:spec)

## specs (functional)
- SPEC_NAME: 328-cursor-cli-token-usage
- Wrote functional-spec.md (In Review) — awaiting user approval gate
- Product direction locked: four-bucket session usage (cache counts); no occupancy substitute
- User revision (pre-approve): (1) user-facing docs for all-agent Tokens calc + usage-vs-billing; (2) Analytics on-hover hint; (3) restore usage on first static build / normal recalculate for historical eligible sessions
- User approved functional-spec (lgtm) → Status Approved
- Next: /awos:tech

## specs (technical)
- Wrote technical-considerations.md (In Review)
- User direction: full usage/ cutover with Cursor (no Cursor-only frontmatter precedent); sync refreshes site sidecar; coverage hover on all Tokens widgets as measured/known (omit zero-measured agents); CONTRIBUTING/maintainers I/O scalability rules
- Revised functional-spec.md → Status In Review again (material expansion)
- User challenge: reject `usage/sessions/<id>.json` (still O(n) opens); care about files/op; prep #322; multi-day → session-day; metrics-without-raw for filtered/don’t-sync
- Rewrote both specs: few aggregates + one ledger; `session-tokens.json` + `session-tokens-daily.json` + `session-tokens-ledger.json`; day = UTC `started`; metrics_only ledger rows
- User pushback (pre-approve): (1) frontmatter still needed for session pages + Cursor backfill path?; (2) prefer one usage file over three (sync/atomicity); (3) expected trade-off ask before precision choice; (4) resumed sessions after days must re-update counters
- Specs stay In Review; do not proceed to tasks until precision + file layout decided with user
- User locked: precision A + last_activity UTC day; single usage/session-tokens.json (totals + days×agent + slim sessions stubs); sync = primary historical backfill; optional named migrate for offline raw-FM seed
- Rewrote functional-spec.md + technical-considerations.md to match
- User: 2nd sync must not full-re-read all sessions just for Tokens no-op → locked fingerprint skip (no body parse / no usage rewrite when all unchanged)
- User: fingerprint skip cannot know “frontmatter never got token_totals” → historical backfill = **named migrate** (reliable); sync = new/changed only
- Specs updated accordingly
- User: Cursor four-bucket parse details were lost in rewrites → **appended** full source table + inclusive→disjoint formula + occupancy reject + Appendix A to technical-considerations.md (preserve rule)
- User dual-approved (lgtm) → functional + technical Status Approved
- Next: /awos:tasks → implement

## tasks
- Wrote tasks.md (slices 1–7)
- Next: /awos:implement

## implement
- Slices 1–6 done: cursor map, session-tokens store, convert/sync upsert, migrate session-tokens CLI, Analytics+coverage, docs/CHANGELOG/I/O rules
- Next: full ruff + pytest; then commit/PR
