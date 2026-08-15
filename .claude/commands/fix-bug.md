---
description: Fixes one bug end-to-end — diagnoses the root cause, applies a scoped fix with a regression test, re-verifies the touched criteria, and amends the spec when behavior changed.
argument-hint: '[bug — report ID, link, or description]'
---

# Fix a Bug End-to-End

Takes one bug — a GitHub Issue — and drives it through diagnosis, a scoped fix with a regression test, re-verification of the touched acceptance criteria, local review, PR, and merge until Definition of Done. On the way it keeps the owning spec honest: when the fix changes documented behavior, it amends that spec rather than letting it drift. Decisions live in `context/product/delivery-flow.md`; re-run `/awos:flow` (Cursor: `/awos-flow`) to change them.

## Notifications

Post to the open pull request with `gh pr comment` **only for exceptions** (skip entirely until a PR exists). Do **not** comment for routine open / CI / gates-passed / merged / blocked-waiting — report those in chat to the user.

Comment when:

1. **Implementation divergence** — for a divergence classification, or when the fix approach differs materially from the owning spec (what changed and why)
2. **Major post-implementation issue** — verify failure forcing scope/approach change, or a serious review finding that alters behavior
3. **Parallel / overlapping work** — rebase or review surfaces functional overlap with another change; describe overlap and resolution

## Arguments

`$ARGUMENTS` — a GitHub Issue number or URL for the bug, or enough identifying text to find it via `gh`. If empty, ask the user.

## Context Discipline

A flow degrades in one long context window. Per §8 of delivery-flow.md:

- Run every isolatable stage in a subagent (a subagent can invoke `/awos:*` commands via the Skill tool; its context is discarded on completion). Subagent reports must be terse — paths, verdicts, counts — never full diff or log content. Exception for local review: the **subagent** still returns only verdict/counts/path after writing the review file; the **orchestrator** then Reads that file and prints the full review body in chat for keep/drop (see Step 9b).
- After each completed stage, append an entry to `context/spec/{SPEC_NAME}/flow-log.md` (or `context/fix-log-{BUG_ID}.md` when the bug maps to no spec): the stage name, what was produced and where (paths, branch, commit), the classification verdict once known, any decisions taken, and which stage comes next. The log is the flow's memory outside the context window — a fresh session resumes by reading this one small file. It is committed with the work (commit-push stages it alongside the code), so it must never become an uncommittable leftover: **once the change request is opened — or the change is merged — stop writing to the tracked log.** New commits are unwelcome on a change request under review or already merged, so a late append would strand a change that can never reach it. From that point, report late-stage progress (gate results, merge, close-out evidence) to the user and via §9 notifications (exceptions only), and resume the remote stages from remote state — the open/merged change request and the ticket status, which the resume-detection stage already inspects. The close stage leaves a clean working tree and never writes a final entry it cannot commit.
- Never launch a nested headless session (`claude -p`) from this command — permission modes, PATH, and timeouts differ per machine. Unattended chaining belongs to the trigger setup (§6), outside this command.
- Tell every dispatched subagent: tools are functional — do not test them or make exploratory calls; every call needs a purpose. Run each delegated stage on the model tier recorded in §8 — the fast tier for mechanical transport work, the strongest for judgment (diagnosis, classification, review).

This command is an orchestrator. It diagnoses and decides, but the code change goes through a delegated specialist — **do not edit code in the main context**.

## Self-Improvement Loop

When this run hits a defect in this command or in `context/product/delivery-flow.md` that blocks progress or forces a workaround:

1. **Flow defect** (disproven recorded fact, missing step, or instruction that forces a workaround) — fix the affected stage in this file and/or record a §10 Local Customization in `context/product/delivery-flow.md` in the same run; note the correction in the flow log; include the correction in the same change request while still pre-PR.
2. **Delivery decision change** (anything in §1–§9) — do not rewrite the decision record on your own; stop and tell the flow owner to re-run `/awos:flow`.
3. **Generator / AWOS framework defect** — do not silently patch around it; report it to the user as feedback for the AWOS repo.

Do not widen into unrelated flow refactors.

<!-- awos:flow:stage=fetch-bug -->

### Step 1: Fetch & Normalize the Bug

Use the fast model tier. Prefer `gh`; fall back to GitHub MCP only if `gh` is missing.

Fetch the GitHub Issue (`gh issue view … --json number,title,body,labels,url,state,comments`). Extract and keep: `BUG_ID`, title, reported symptom, reproduction steps if given, affected area, link. Also pull linked issues and referenced URLs/attachments; list unreachable ones explicitly.

<!-- /awos:flow:stage -->

<!-- awos:flow:stage=resume-detection -->

### Step 2: Detect the Entry Point

Start with a cheap preflight on the fast model tier (per §8): is this bug **already fixed**? If the GitHub Issue is `closed`, or a merged change request exists for the same fix, report that and stop rather than re-fixing. Then, if a flow log for this bug exists (`context/spec/{SPEC_NAME}/flow-log.md`, or `context/fix-log-{BUG_ID}.md`), read it first — it names the last completed stage and carries the branch, commit, classification verdict, and change-request state, and is the resume signal for the middle stages that produce no scannable artifact.

<!-- /awos:flow:stage -->

<!-- awos:flow:stage=workspace -->

### Step 3: Prepare the Workspace

Verify `context/` is reachable (`context/product/architecture.md` readable). Warn on a dirty working tree (uncommitted AWOS artifacts left by `/awos:flow` are an expected cause, not a blocker). No submodules.

Create an isolated worktree + throwaway vault from `origin/main`:

```bash
git fetch origin main
BRANCH="fix/<issue>-<short-slug>"
WT_SLUG=$(echo "$BRANCH" | tr '/' '-')
WT=".claude/worktrees/$WT_SLUG"
git worktree add -b "$BRANCH" "$WT" origin/main
cd "$WT"
LLMWIKI_SKIP_AUTOMATION=1 ./setup.sh
TMP_VAULT="$WT/.worktree-vault"
mkdir -p "$TMP_VAULT"
printf '%s\n' "{\"vault\":{\"default_path\":\"$TMP_VAULT\"}}" > config.json
python3 -m llmwiki init --vault "$TMP_VAULT"
```

If already inside a matching worktree on `BRANCH`, reuse it and ensure `$WT/.worktree-vault` + worktree `config.json` still isolate from the live vault (never copy primary `config.json`).

Store `BRANCH`, `WT`, `TMP_VAULT`, and `BUG_ID`. Always `python3 -m llmwiki` from `$WT` — never PATH `llmwiki`. Agent mutating commands → `$TMP_VAULT` only; read-only live-vault probes allowed.

<!-- /awos:flow:stage -->

<!-- awos:flow:stage=diagnose -->

### Step 4: Diagnose

Reproduce the bug and find the root cause. Delegate the investigation to the built-in `Explore` subagent or a debugging specialist via **[Agent: name]** (strongest tier) — the orchestrator does not read the whole codebase or write code itself. Prefer reproducing against `$TMP_VAULT` or synthetic fixtures; read-only live probes are OK. The subagent returns terse: the reproduction, the root-cause location (file/function), and a proposed minimal fix shape. If the bug cannot be reproduced, report that and stop rather than guessing at a fix.

<!-- /awos:flow:stage -->

<!-- awos:flow:stage=classify -->

### Step 5: Classify — Conformance vs. Divergence

This gate decides whether the spec gets amended later, so it runs **before** any fix touches behavior. Locate the owning `context/spec/NNN-*/` for the affected behavior (read its `functional-spec.md`), then classify:

- **Conformance bug** — the code violates a _correct_ spec. The acceptance criteria were right; the code was wrong. → Fix the code and add a regression test; **do not** amend the spec.
- **Divergence** — the spec was wrong or incomplete, or the fix intentionally changes documented behavior. → Fix, add a regression test, and **amend** the owning spec in the `amend-spec` stage. Once a PR exists, post a §9 divergence exception comment.

If the bug maps to **no** existing spec (legacy or cross-cutting behavior), do not fabricate one — record "no owning spec" and proceed without amendment. Record the verdict and the owning spec dir (or "none") in the flow log; later stages read it.

<!-- /awos:flow:stage -->

<!-- awos:flow:stage=fix -->

### Step 6: Fix

Delegate the code change to a specialist via **[Agent: name]** (chosen from `context/product/hired-agents.md` / available agents for the affected area) — the orchestrator never edits code itself. Prefer `testing-expert` only for test work; coding uses the best matching specialist or `general-purpose`. Keep the change scope-disciplined: a flat task list targeting the root cause, no vertical slicing, no opportunistic refactors beyond what the fix needs. Pass the subagent the root-cause findings from Step 4, the classification, and vault rules (`$TMP_VAULT` for writes), not a re-derivation.

<!-- /awos:flow:stage -->

<!-- awos:flow:stage=regression-test -->

### Step 7: Regression Test

Add one test that fails on the old code and passes on the fix, capturing the bug so it cannot silently return. Delegate it to `testing-expert` (or the best available testing specialist) via **[Agent: name]**. Honor the `<!-- skip-tests: true -->` marker: if the owning spec's `tasks.md` carries it (the team opted out of generated test suites), skip adding an automated test and note that the regression is covered by the look-and-feel check in the next stage instead.

<!-- /awos:flow:stage -->

<!-- awos:flow:stage=verify-criteria -->

### Step 8: Verify the Touched Criteria

Re-check **only** the acceptance criteria the bug touched, with `/awos:verify`'s evidence discipline — drive the CLI/API/UI for real against `$TMP_VAULT`, and `AskUserQuestion` only when a criterion has no agent-driven render path at all. This is scoped: it does not re-run the whole acceptance set, does not flip the spec's Status, and honors `<!-- skip-tests: true -->` (look-and-feel walk-through only, no test suites). Report the criteria checked and their evidence.

Automated verify is the flow's job on `$TMP_VAULT` (`python3 -m llmwiki build`, Playwright, free serve port). Read-only live probes are allowed. Do not mutate the live vault. Manual `AskUserQuestion` is only for criteria the agent genuinely cannot render here.

**Smoke confirm:** ask the user to confirm the fix works as expected before local review. Include ready-to-paste live-vault commands using worktree code (`cd "$WT" && python3 -m llmwiki … --vault "$LIVE"`); do not run the mutating ones yourself. Skipped confirmation → stop.

<!-- /awos:flow:stage -->

<!-- awos:flow:stage=amend-spec -->

### Step 9: Amend the Spec (on divergence)

Conditional on the Step 5 verdict:

- **Conformance** — nothing to amend; the spec was already correct. Skip to the next stage.
- **Divergence** — invoke `/awos:spec` in update mode for the owning spec, passing the spec directory and a description of the behavior change (e.g. `/awos:spec amend spec NNN: <what changed and why>`). `/awos:spec`'s Mode Detection routes this to its Update Mode, which edits the affected acceptance criteria in place and appends a dated `## Change Log` entry — no new spec index is allocated, and a `Completed` Status is left untouched. Do not duplicate the amendment prose here; the amendment capability lives in core `/awos:spec`. §9 exception comment once a PR exists.

In either case, if the fix revealed that `product-definition.md` or `architecture.md` also drifted, surface the same `/awos:product <…>` / `/awos:architecture <…>` suggestions `/awos:verify` Step 5 emits — as suggestions, never auto-edits.

<!-- /awos:flow:stage -->

<!-- awos:flow:stage=local-review -->

### Step 9b: Local Review

After smoke confirm, run one independent local review (pre-push, `git diff origin/main...HEAD`).

Independence rules:

- Do not add run-time focus areas drawn from what you fixed or suspect.
- Dispatch exactly one independent reviewer on the strongest tier using the coding agent's own most suitable review skill, command, or subagent (do not hardcode a product-specific reviewer name). Pass the fixed prompt below (verbatim).
- That reviewer writes the review file and returns only verdict, counts by severity, and path.
- Then **Read the review file and print its full body in chat** (lead with `Review file: <path>`). Pause for keep/drop; apply accepted findings before push.

Review output path: `context/spec/{SPEC_NAME}/review.md` when a spec dir exists, else `context/fix-log-{BUG_ID}-review.md`.

Fixed prompt (replace the path placeholder before dispatch):

```text
Review git diff origin/main...HEAD (branch changes, not an open-PR number).

Load and apply every section of these docs, in this priority order for attention:
1. docs/maintainers/REVIEW_CHECKLIST.md — treat its Blocker vs Nit rule as the severity model (Security + Meta + broken layer boundaries / failing tests or build = Blocker; Code quality / Docs / Build+runtime smoke = Nit unless they trip Meta or Security). Use the checklist's Blocker shortlist.
2. docs/maintainers/ARCHITECTURE.md
3. docs/maintainers/DECLINED.md
4. CONTRIBUTING.md
5. SECURITY.md

Also look for bugs, logic errors, and security issues the checklist does not name.

Write the full review markdown to <REVIEW_PATH> with: Verdict (Approve | Request changes | Comment), counts by severity, findings grouped Blockers then Nits, each finding citing the relevant REVIEW_CHECKLIST section when applicable, and a concrete fix suggestion.

Return only: verdict, counts by severity, and the review file path — never the full review body in your report.
```

Then:

```bash
ruff check llmwiki tests scripts
python3 -m pytest tests/ -q
```

Do not push until keep/drop is done and the static gate is green. Serious findings that alter behavior → §9 exception after PR open.

<!-- /awos:flow:stage -->

<!-- awos:flow:stage=commit-push -->

### Step 10: Commit & Push

Write this stage's flow-log entry **before** staging so the log rides in this commit — this is the flow-log's last committed state (see Context Discipline). Then stage all changed files, excluding `.env`, credentials, secrets, and local vault/config (`config.json`, `.worktree-vault/`). Commit with conventional commits referencing `#<BUG_ID>`; if pre-push ruff rejects, fix and create a new commit (no `--no-verify` unless the user allows). Push `BRANCH` to `origin`.

<!-- /awos:flow:stage -->

<!-- awos:flow:stage=remote-gates -->

### Step 11: Remote Gates

From here the change request is open — **do not append to the tracked flow-log** (Context Discipline). Report routine gate progress in chat only; §9 PR comments only for exceptions.

Before opening the PR: fetch and rebase onto `origin/main`. On conflicts: subagent resolution, re-run local gates, user confirm for non-trivial resolutions, push. Functional overlap → §9 comment after open.

Open the PR with `gh pr create` against `main`. Do **not** post a "PR opened" comment. Wait on required checks with `gh pr checks --watch` (~30m max-wait, then ask in chat). On CI failure: `gha-diagnosis` + log-failed → fix subagent → push → re-watch. Do not PR-comment on CI red/max-wait. Claude-in-CI workflows were removed (#116) — do not wait on a Claude Code Review check; do not poll CODEOWNERS; do not transition the GitHub Issue.

<!-- /awos:flow:stage -->

<!-- awos:flow:stage=merge -->

### Step 12: Merge

Re-check mergeability against current `origin/main`. If dirty: rebase, push, return to Step 11.

When gates are green, ask for explicit merge confirmation in this run. On yes: `gh pr merge`. Skipped/unanswered → do not merge; report ready-to-merge in chat. No "merged"/"gates passed" PR comments.

After merge: watch post-merge Actions on `main` and fix forward if this change broke them.

<!-- /awos:flow:stage -->

<!-- awos:flow:stage=close-ticket -->

### Step 13: Close the Loop

Definition of Done: PR merged and post-merge required checks green. Report evidence in chat: PR URL, merge commit, local-review verdict/counts/paths, classification verdict, and (on divergence) that the owning spec was amended. Do **not** close or transition the GitHub Issue.

Leave a clean working tree: do not write a closing flow-log entry. If any flow-created artifact is still uncommitted, surface it in the report.

<!-- /awos:flow:stage -->

---

<!-- awos:flow:generated date=2026-08-08 version=2.4.3 source=context/product/delivery-flow.md -->
