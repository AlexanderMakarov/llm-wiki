# Advance wait redesign — herdr driver + AWOS finish (proposed)

- **Status:** Implemented (branch `feat/296-herdr-advance-wait`; supersedes held PR #381 direction)
- **Motivation:** #355 worker stopped at “merged”; driver could advance on GitHub before the **main checkout** (where herdr runs) was updated or before post-merge CI was meaningful locally. Prior fix attempt (PR #381) duplicated GitHub α polling in the worker and proposed sidecar files — rejected.
- **Author intent:** Driver watches **local then GitHub** in sequence; **AWOS** owns `git pull` on main; driver **does not** audit AWOS correctness — only **reliable stop/start signals** for the worker session. Operator **skip** for stuck tickets.

---

## 0. Scope (two deliverables)

This change is **not** driver-only. Both parts ship together:

| # | Deliverable | Problem it fixes |
|---|-------------|-------------------|
| **A** | **AWOS delivery flow** — `context/product/delivery-flow.md` and generated **`.claude/commands/implement-feature.md`**, **`.claude/commands/fix-bug.md`**, plus herdr-inlined skill | Workers stop at merge / green PR CI while **main checkout is never updated** (`git pull` skipped). #355 hit this directly. |
| **B** | **Herdr driver** — `scripts/loop_ready_issue_herdr.py` wait loop (Phase A → B, Path 2, skip) | Driver could treat GitHub as done **before** main reflects the ticket; needs local-then-gh sequencing. |

Optional helper **`scripts/wait_post_merge_ci.py`** stays under **A** (agent-invoked), not **B**.

**Regeneration:** After editing `delivery-flow.md`, re-run **`/awos-flow`** (or `./scripts/update-awos.sh` / project equivalent) so generated command files match — do not leave only maintainer docs updated while Step 12–13 still say “merged + CI green” with no main pull.

---

## 1. Goals and non-goals

### Goals

1. **Serial loop** still drains one labeled, assigned issue at a time (unchanged queue rules).
2. **Advance** closes the current worker tab and starts the next ticket only when defined **done signals** fire.
3. **Main checkout** (herdr driver cwd) eventually reflects merged work for normal PR deliveries — via **AWOS last step**, not driver `git pull`.
4. **No delivery sidecar files** (no `.herdr/delivery-done.json` or similar “worker said done” artifacts).
5. **Restart-safe:** driver (re)start always begins wait logic at **Phase A** for the in-flight issue.
6. **Operator skip** for tickets stuck in Phase A (irregular / forgotten pull / abandoned).

### Non-goals

- Driver does **not** run `git fetch`, `git pull`, or any network git operation.
- Driver does **not** verify that AWOS executed every stage correctly.
- Driver does **not** replace human gates inside herdr (`blocked`, merge confirm, etc.).
- Not a new `llmwiki` subcommand; maintainer script + AWOS/delivery-flow text only.
- Herdr driver is **only supported** when started from the **main checkout** of the repo (no `--primary-checkout` override unless a later spec adds it).

---

## 2. Repository layout (main vs gate worktree)

| Checkout | Role |
|----------|------|
| **Main checkout** | Where `python3 scripts/loop_ready_issue_herdr.py` runs. herdr worker tabs use `--cwd` = this path (`REPO_ROOT` today). **Phase A** reads git state here only. |
| **Gate worktree `$WT`** | AWOS workspace stage: `.claude/worktrees/<slug>`, branch `feat/…` or `fix/…`, throwaway `.worktree-vault`. **All implementation** happens here per `context/product/delivery-flow.md` §2. |

**AWOS contract (last stages):** After merge (and post-merge CI handling **in the agent path** — see §5), the worker runs **`git pull --ff-only origin main` in the main checkout** (not “switch `$WT` to main”). Typical shape:

```bash
# From anywhere; target main checkout explicitly if the agent shell cwd is $WT:
git -C "$MAIN" fetch origin main    # network — agent/worker, NOT driver
git -C "$MAIN" pull --ff-only origin main
```

Record `$MAIN` at workspace time (path of the checkout that is **not** `$WT` — usually the parent repo / where herdr was started). Herdr-injected prompt may include `MAIN=<path>` for clarity.

**Optional cleanup:** `git worktree remove "$WT"` after merge — not required for driver advance.

---

## 3. Driver wait state machine (per in-flight issue `#N`)

Two phases, **strict order** for **Path 1** (merged closing PR). On **every** adopt/restart for `#N`, start in **Phase A** (no remembered phase across driver processes except what can be inferred from local git + gh on the next ticks).

```
                    ┌──────────────────────┐
                    │  PHASE A (local)     │
                    │  every local_poll    │
                    │  NO network          │
                    └──────────┬───────────┘
                               │ clean (§3.2)
                               ▼
                    ┌──────────────────────┐
                    │  PHASE B (GitHub)    │
                    │  every poll_seconds  │
                    │  gh only             │
                    └──────────┬───────────┘
                               │ advance (§3.3)
                               ▼
                         close tab, next ticket
```

**Parallel escape hatches** (see §3.4, §4):

- **Path 2** (issue closed, no merged closing PR): **no Phase A** — gh-only on 300 s schedule (preserves today’s “CI gate skipped” behavior).
- **Operator skip:** force advance from Phase A (or B) without full normal signals.

### 3.1 Phase A — local only

- **Interval:** `--local-poll-seconds` (default **10**, allowed range **10–30**).
- **Local network:** **none** for git — no `git fetch`, no `git pull`.
- **GitHub during Phase A:** still poll `gh` every `--poll-seconds` only to detect **Path 2** (closed without merged PR) and to print “merged on GitHub; main not updated yet”. Never advance **Path 1** from Phase A.
- **Commands (main checkout only) for local clean:**
  - `git status --porcelain` (and optionally `git branch --show-current` → expect `main`)
  - `git log -n 10 --oneline`
- **No `baseline_head`** — do not compare to ticket-start HEAD; only current local history.

**Clean (all required):**

1. Working tree **clean:** `git status --porcelain` is empty (document any allowed exceptions, e.g. only gitignored noise — default: empty).
2. **Ticket marker in recent history:** `#N` appears in the output of `git log -n 10 --oneline` (match whole issue token, e.g. `#355`, to reduce false positives from `#3550` use word-boundary or `(#355)` / `Closes #355` patterns in implementation).

When **clean**, transition to **Phase B** for this wait episode. Stay in Phase B until advance or operator skip; **do not** revert to Phase A on later local polls (unless driver restarts — then Phase A again from scratch).

**Status line example:** `#355 Phase A: waiting for #355 in git log -n 10 (local only) — next local poll 10s`

### 3.2 Phase B — GitHub only

- **Interval:** existing `--poll-seconds` (default **300**).
- **Only** after Phase A is **clean** (Path 1), or immediately for **Path 2** (§3.4).
- **Calls:** existing merge/CI/issue helpers (`fetch_issue_merge_and_ci_status`, `advance_ready`, `closed_without_merge_reason`, etc.).

**Path 1 advance (merged closing PR):** all of:

- Phase A was clean for this episode (local evidence ticket landed on main checkout).
- GitHub: merged closing PR for `#N` with **`advance_ready(merge_info, check_runs)`** true (post-merge CI α — non-empty check runs, all green conclusions as today).
- Issue **CLOSED** (GitHub auto-close from merge counts).

**Why Phase B alone is insufficient:** GitHub can show merged / closed / green **before** the worker runs `git pull` on main. Phase A ensures local history already mentions `#N` before α is accepted for advance.

**Status line example:** `#355 Phase B: local clean; post-merge CI 5/5 green — waiting 300s` / `#355 Phase B: local clean; CI 3/5 (2 pending) — waiting 300s`

### 3.3 Path 2 — closed without merged closing PR (no Phase A)

When gh status matches **Path 2** (issue CLOSED, no merged PR that closed it):

- **Do not require Phase A** (no code artifacts expected on main).
- Poll GitHub every **300 s**; advance with existing skip-CI reason string; close tab.

This is **not** the same as “stuck in Phase A”; it is the normal automation path for manual close / duplicate / “Relevant to #N” closures.

### 3.4 Operator skip (jump stuck tickets)

**Problem:** Strict Path 1 **A → B** blocks forever if the issue was merged but nobody pulled main (or `#N` never appears in `log -n 10`), or other irregular delivery.

**Command (separate process, same repo):**

```bash
python3 scripts/loop_ready_issue_herdr.py --skip-issue N
```

**Behavior:**

1. Writes a **gitignored** operator request file (e.g. `.herdr/skip-issue` containing ASCII issue number `N` and optional reason line). Add `.herdr/` to root `.gitignore`.
2. Running driver, on each wait tick (Phase A or B), if current worker issue == `N` and skip file present:
   - Print **WARNING** with skip reason (default: `operator skip`).
   - **Force advance:** close worker tab, proceed to next ticket **without** Phase A clean or Phase B α.
   - Remove skip file (one-shot).
3. If skip file names an issue **not** currently in flight, print WARNING and leave file (or clear with message — implementation choice: prefer clear + warn to avoid stale skip hitting wrong ticket later).

**Dry-run:** `--skip-issue N` with `--dry-run` prints what would be written without requiring a running driver.

**Docs:** `docs/maintainers/LOOP_READY_ISSUE_HERDR.md` — when to skip, that it bypasses local+CI gates, recovery if skip was wrong (re-open issue, manual worker).

---

## 4. Restart and mid-AWOS behavior

| Event | Driver action |
|-------|----------------|
| Driver (re)start, open `issue-N` tab | **Adopt** (no new prompt). Wait state = **Phase A**. |
| Phase A clean, then driver restart before advance | **Phase A** again; if log still shows `#N`, reach Phase B again on next clean check. |
| gh Path 2 eligible | **Phase B** (or immediate advance on first qualifying gh poll) without Phase A. |
| gh Path 1 merged, CI pending, Phase A clean | **Phase B** until α or skip. |
| gh Path 1 merged, Phase A not clean | Stay **Phase A** (local poll only) — status explains “merged on GitHub; main checkout not updated yet”. |
| Worker gone (`herdr agent wait`) | Existing gone-warning; **keep** Phase A/B logic unchanged (gone does not advance). |
| Operator `--skip-issue N` | Force advance (§3.4). |

**No persisted driver state file** beyond gitignored skip request. No `baseline_head`.

---

## 5. AWOS / delivery-flow changes (Deliverable A — worker, not driver)

Applies to **`/implement-feature`**, **`/fix-bug`**, and **short variants** that perform delivery. Today Step 12 (“Deliver”) is packaging-only and Step 13 DoD is **“PR merged + post-merge checks green”** with **no mandatory main-checkout sync** — that gap is **in scope to fix**.

### 5.1 `context/product/delivery-flow.md`

- **§2 Git flow / workspace:** After worktree recipe, record **`MAIN`**: absolute path to the **primary** checkout (parent of `$WT` in the usual layout — the tree herdr uses). Agents must not assume `cwd` is `$MAIN` after `cd "$WT"`.
- **§5 Delivery / Definition of Done:** Extend DoD to include **main checkout synced to `origin/main` after merge** (merge commit present on `MAIN` at `HEAD` after pull), in addition to merged PR + post-merge CI green.
- **§5 Post-merge:** Split “watch CI” from “sync main” — CI wait/fix-forward, then **explicit final git block on `$MAIN`** (fetch + pull `--ff-only`), then report.

### 5.2 Generated commands (implement-feature / fix-bug)

Re-run flow generation after §5 edits. Minimum behavioral changes:

1. **Workspace stage:** Set and export `MAIN="$(…)"` (document resolution: e.g. git dir of worktree → main worktree path, or path recorded when driver started herdr).
2. **After merge stage:** Keep post-merge CI watch/fix-forward on `main` (existing prose); add **mandatory** block before Close the loop:
   ```bash
   git -C "$MAIN" fetch origin main
   git -C "$MAIN" pull --ff-only origin main
   git -C "$MAIN" log -1 --oneline
   ```
3. **Close the loop / DoD:** Require evidence: PR URL, merge SHA, post-merge CI result, **`git log -1` on `$MAIN`**. Explicit line: **Stopping after merge or issue CLOSED without pulling `$MAIN` is not Done** (herdr Phase A depends on local history on main).
4. **Short commands:** Any abbreviated implement/fix wrapper must **not** omit the main-pull block (same final stage).

Optional: invoke `python3 scripts/wait_post_merge_ci.py --issue N` before pull (shared α with driver Phase B).

### 5.3 Definition of Done (agent-facing summary)

1. PR merged (per existing merge-confirm gate).
2. Post-merge CI on merge commit **green** (agent waits / fix-forward — **not** driver’s job). Optional: `wait_post_merge_ci.py`.
3. **Last mutating git step on product repo:** `git pull --ff-only origin main` on **`$MAIN`** (main checkout — **was skipped in #355; must be mandatory**).
4. Final chat report including step 3 evidence.

Driver **does not** verify steps 1–3 programmatically — only Phase A/B signals — but **AWOS must require** step 3 so agents actually run it.

### 5.4 Herdr skill (driver-inlined)

- Route `bug` → `/fix-bug`, else `/implement-feature` (unchanged).
- **Finish:** complete the delivery command through its **final stage** (main pull + report). Do not stop at “merged” or issue CLOSED in chat.
- Pass **`MAIN=<path>`** in driver spawn prompt when known (same as `$MAIN` in AWOS).

### 5.5 PR #381 (held)

- **Do not merge** as-is.
- **Salvage:** `wait_post_merge_ci.py` + tests as **optional AWOS helper** only; shared `fetch_check_runs_for_sha` / `advance_ready` in driver module is fine.
- **Drop:** worker+driver dual polling as peer DoD; `.herdr/delivery-done.json`; skill text that treats PR merge as Done; driver `fetch`/`pull`.

---

## 6. CLI parameters (driver)

| Flag | Default | Purpose |
|------|---------|---------|
| `--local-poll-seconds` | `10` | Phase A interval (10–30). |
| `--poll-seconds` | `300` | Phase B gh interval (unchanged default). |
| `--skip-issue N` | — | One-shot operator force advance (§3.4). |
| `--label`, `--repo`, `--once`, `--dry-run`, `--workspace`, `--agent-kind` | (existing) | Unchanged. |

---

## 7. Implementation notes (for `loop_ready_issue_herdr.py`)

1. Replace body of `wait_until_ticket_advanced` with Phase A loop + Phase B loop + skip check + Path 2 branch.
2. Interleave existing `herdr agent wait` during Phase A/B sleeps while worker live (unchanged).
3. Unit tests: Phase A clean detection (log fixture), transition A→B, Path 2 skips A, skip file force advance, restart resets to A (simulate re-enter function).
4. Acceptance: adopt + Phase A status lines; no gh call in Phase A (mock gh assert call count).

---

## 8. Documentation updates (when implemented)

- **`context/product/delivery-flow.md`** — Deliverable **A** (§5.1).
- **`.claude/commands/implement-feature.md`**, **`.claude/commands/fix-bug.md`** — regenerated or edited to match (§5.2).
- **`.claude/skills/loop-ready-issue-herdr/SKILL.md`** — §5.4.
- `context/spec/303-loop-ready-issue-herdr/functional-spec.md` — amend §2.1 (delivery commands **do** gain mandatory finish steps for herdr), §2.8 (advance rule).
- `context/spec/303-loop-ready-issue-herdr/technical-considerations.md` — §2.5 wait loop, remove “do not advance on skill signals” if superseded by Phase A local signal.
- `docs/maintainers/LOOP_READY_ISSUE_HERDR.md` — two-phase wait, skip command, Path 1 vs Path 2, pointer to AWOS main pull.
- `CHANGELOG.md` — edit existing unreleased **#296** bullet **and** note delivery-flow DoD change (user-visible for anyone using `/implement-feature` / `/fix-bug`, not only herdr).

---

## 9. Caveats and discussion record

| Topic | Decision |
|-------|----------|
| Sidecar done files | **Rejected** — local git + gh only. |
| Driver `git fetch` / `git pull` | **Rejected** — worker AWOS only. |
| `git log baseline..origin/main` | **Rejected** — use `git log -n 10` only; no baseline. |
| Driver verifies AWOS | **No** — only stop/start signals. |
| Phase B before Phase A (Path 1) | **Rejected** — gh too early vs pull/CI story. |
| Phase B alone for Path 1 | **Rejected** — use A → B. |
| Closed without merge | **Path 2** — gh 300 s, **no Phase A**. |
| Stuck Path 1 (merged, never pulled) | **`--skip-issue N`**. |
| Herdr only on main checkout | **Assumed** — no extra path checks. |
| Post-merge CI α | **Still Phase B** for Path 1 (keep `advance_ready`). |
| `wait_post_merge_ci.py` | **Optional AWOS helper**, not driver gate. |
| Irregular close with merge but no local pull | Stuck in **Phase A** until pull or **skip**. |
| PR #381 | **Hold / rework** per this spec. |
| Network in “local” Phase A | **Forbidden** — includes `git fetch`. |

---

## 10. Acceptance criteria (new / amended)

### AWOS (Deliverable A)

- [ ] Given a completed delivery run, generated implement/fix commands include **`git -C "$MAIN" pull --ff-only origin main`** after merge and before final report.
- [ ] Given workspace stage, **`MAIN`** is defined (absolute path) and used for the final pull, not `$WT` alone.
- [ ] Given functional spec §2.1, text no longer claims delivery command **substance** is unchanged when herdr finish steps are added.

### Driver (Deliverable B)

- [ ] Given Path 1 and Phase A not clean, driver never advances on α (local polls at `local_poll_seconds`; `gh` may still run on `poll_seconds` for Path 2 / status only).
- [ ] Given Path 1 and Phase A clean, driver calls `gh` at most every `poll_seconds` until α + closed.
- [ ] Given Path 2, driver advances without Phase A when gh matches closed-without-merge.
- [ ] Given `--skip-issue N` while `#N` in flight, driver force-advances on next tick with WARNING.
- [ ] Given driver restart with adopted `issue-N` tab, wait logic starts in Phase A.
- [ ] Given AWOS last stage documented, main checkout pull is **after** merge and **before** chat Done report.
- [ ] No committed `.herdr/` except gitignore entry; skip file gitignored.

---

## 11. Open items (optional follow-ups)

- Tune `#N` regex in `log -n 10` (false positives / `Closes #N` in merge commits only on main).
- Whether Phase B first gh tick waits full 300 s after Phase A clean or runs gh immediately once (current spec: **only 300 s gh polling** — first B tick at next 300 s boundary after entering B).
- `--skip-issue` with reason string for audit in WARNING line.
