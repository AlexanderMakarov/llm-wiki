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
- Slices 1–7 done: cursor map, session-tokens store, convert/sync upsert, migrate session-tokens CLI, Analytics+coverage, docs/CHANGELOG/I/O rules; full ruff+pytest green
- Commit 9a05289; PR https://github.com/AlexanderMakarov/llm-wiki/pull/354 ; CI all green; merge blocked on branch policy (needs review) — `--auto` requested if available
- Follow-up fix: `migrate session-tokens` calls `discover_all()` and loads `config.json` so contrib origin re-read runs and frontmatter tags label `cursor_cli` / `codex_cli` / … correctly (was defaulting every session to `claude_code`). Live-vault checks are `--dry-run` / in-memory only (no vault writes).
- Local review Request changes applied: B1 origin skips empty totals; B2 drop raw filter-skip (metrics-without-raw); convert omits empty `token_totals` + never upserts zeros; N1/N2 tests + no synth imports; N3 leave `demo/wiki/archive/` untracked. Cursor dig (forum 168317): `store.db` has no turn usage — shipped `python3 -m llmwiki.cursor_token_events` stop-hook JSONL + `normalize_records` merge by `conversation_id`. Filed #355 (self-heal, assigned) for optional synthetic/no-tool Tokens knob.
- Next: ruff + pytest; push PR #354 when asked.
- Investigation notes saved at `context/spec/328-cursor-cli-token-usage/investigation-notes.md` (prefs, dead sinks, vscdb cutoff = reinstall or IDE update). Hook latency benches: Rust/Go ~1 ms p50, bash ~3 ms, Python module ~42 ms; concurrent O_APPEND 100 writers integrity ok.
- Locked: ship POSIX `/bin/sh` stop handler (not Rust/Go — CI/multi-arch not worth ~2 ms). `--install-hook` writes `~/.cursor/llmwiki-cursor-token-stop.sh` + merges `hooks.json`; Python kept for install/ingest only.
- Review pass 2 keep-all applied: B1 slim public sidecar (no `sessions`); B2-1 Analytics loads `session-tokens.js` + viewer refresh; N2 document full-stdin managed hook; N3 delete `demo/wiki/archive/`; N4 narrow coverage requirement to Analytics Tokens card.

## commit-push
- Applied review-2 keep-all (B1 slim sidecar, B2-1 Analytics live Tokens refresh, N2 full-stdin docs, N3 removed demo/wiki/archive/, N4 Analytics-only coverage title)
- Staged cursor_token_events + investigation-notes; excluded review.md / review-2.md / demo archive
- Issue link keyword: Closes #325 (AC delivered; #355 is separate optional knob)
- Next: push PR #354; watch CI; ask merge confirm
