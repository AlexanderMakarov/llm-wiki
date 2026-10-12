# Flow log — #146 harvest discard reason surface

## fetch-ticket
- Issue: https://github.com/AlexanderMakarov/llm-wiki/issues/146 (OPEN; labels: enhancement, self-heal)
- Title: Harvest re-proposes candidates you already discarded, and never reads the reason you recorded
- Owner re-scope (comment): #282 covered exact-name exclusion + merge-target reads from reason.txt; still open = free-text dismissal reason unused, and no surface when a close name reappears
- Route: no `bug` label → `/implement-feature`
- Next: resume-detection

## resume-detection
- Issue OPEN; no owning functional-spec; no open PR for remaining scope
- Roadmap still unchecked: "Harvest respects a dismissal (#146)"
- Allocated SPEC_NAME=`326-harvest-discard-reason-surface`
- Next: workspace

## workspace
- BRANCH=`feat/146-harvest-discard-reasons` from origin/main 143d000
- WT=`/home/USER/code/llm-wiki/.claude/worktrees/feat-146-harvest-discard-reasons`
- TMP_VAULT=`$WT/.worktree-vault` + worktree config.json (absolute path)
- Next: specs (/awos:spec)

## specs — functional-spec
- Product choices: (1) propose near-matches but mark them; (2) name near-match only, reason for display
- Approved: `context/spec/326-harvest-discard-reason-surface/functional-spec.md`
- Next: `/awos:tech`

## specs — technical-considerations
- Approved (lgtm): dismissals.json SoT; no new reason.txt; dismissal_ledger sole I/O; near-match at list time; mockups + `(discarded without explanation)`
- Next: `/awos:tasks`

## specs — tasks
- Wrote `tasks.md`: 5 slices (ledger → CLI near-match → site → docs → regression)
- Agents: python-pro (impl), generalPurpose (docs), testing-expert unavailable → generalPurpose for Slice 5
- All slices Completed
- Next: verify + smoke confirm

## implement
- BRANCH=`feat/146-harvest-discard-reasons` WT absolute under `.claude/worktrees/`
- Delivered: dismissal_ledger, candidates rewrite, near_match, CLI+site, migrate dismissal-ledger, docs, acceptance tests
- Full gate: ruff clean; pytest tests/ exit 0
- Next: user smoke confirm (live vault — operator runs mutating commands)

## verify
- FR1–FR6 covered by tests/test_harvest_discard_reason_surface_acceptance.py + unit suites
- Live vault: backup + migrate dismissal-ledger + UX polish (multi prior list, name de-dupe, Discard with prior reason); operator smoke OK
- Next: local review

## local-review
- Smoke confirmed by operator
- review.md: Verdict Approve; Blockers 0; Nits 3
- Keep/drop: keep all — applied Nit1 agent-kit wiki-candidates.md; Nit3 JS comment; Nit2 stage untracked at commit
- Next: static gate → commit-push

## commit-push
- Issue link keyword: `Closes #146` — delivers remaining #146 scope (reason surface + near-match UX + dismissals.json rewrite); exact-name exclusion was #282
- Stage: product + tests + docs + context/spec/326 (exclude review.md)
- Next: push → PR → remote gates

## implement — Slice 2
- `list_candidates` → `attach_prior_dismissals`; CLI human line + `--json` prior_dismissal
- Near-match spellings: `FooBar`/`Foobar` fold equal (`norm_page_key`) — used `FooBars`/`Foobar` (ratio 0.9231) and `ApiClients`/`ApiClient` (empty reason)
- Vault verify list mockup green; focused pytest + ruff green; `.worktree-vault` cleaned
- Next: Slice 3 (candidates.html)

## implement — Slice 3
- Site payload + Name-cell Prior dismissal line; `(discarded without explanation)` for empty reason
- Next: Slice 4 (docs)

## implement — Slice 4 (docs / CHANGELOG / UPGRADING / context)
- User-visible delivery for #146: `dismissals.json` ledger (no new `*.reason.txt`), near-match marks on `candidates list` + `candidates.html`, `llmwiki migrate dismissal-ledger`, empty reason → `(discarded without explanation)`
- Docs: `docs/reference/cli.md`, `docs/reference/ui.md`, `CHANGELOG.md` [Unreleased] Added, `docs/UPGRADING.md` Unreleased note
- Product PR context: this flow-log entry + `notes.md` in this spec dir
- Next: Slice 5 (acceptance / regression)
