---
description: Implements one feature end-to-end — fetches its requirements, runs the AWOS chain, and delivers per the team's flow.
argument-hint: '[feature — ticket ID, link, or file path]'
---

# Implement a Feature End-to-End

Takes one feature — its requirements from a GitHub Issue, plain prompt, local file, or pre-written `context/spec/` directory — and drives it through spec, implementation, verification, local review, PR, and merge until Definition of Done. Decisions live in `context/product/delivery-flow.md`; re-run `/awos:flow` (Cursor: `/awos-flow`) to change them.

## Notifications

Post to the open pull request with `gh pr comment` **only for exceptions** (skip entirely until a PR exists). Do **not** comment for routine open / CI / gates-passed / merged / blocked-waiting — report those in chat to the user.

Comment when:

1. **Implementation divergence** — the delivered approach differs materially from the approved spec/tech (what changed and why)
2. **Major post-implementation issue** — verify failure forcing scope/approach change, or a serious review finding that alters behavior
3. **Parallel / overlapping work** — rebase or review surfaces functional overlap with another change; describe overlap and resolution

## Arguments

`$ARGUMENTS` — a GitHub Issue number or URL, a local requirements file path, or free-text requirements. If empty, resume from the next incomplete item in `context/product/roadmap.md` (first unchecked `- [ ]`, as `/awos:spec` does); if the roadmap is missing or fully complete, ask the user.

## Context Discipline

A flow this long degrades in one context window — judgment is worst exactly where it matters most, at review time. Per §8 of delivery-flow.md:

- Run every isolatable stage in a subagent (a subagent can invoke `/awos:*` commands via the Skill tool; its context is discarded on completion). Subagent reports must be terse — paths, verdicts, counts — never full document content. Exception for local review: the **subagent** still returns only verdict/counts/path after writing `review.md`; the **orchestrator** then Reads that file and prints the full review body in chat for keep/drop (see Step 8).
- After each completed stage, append an entry to `context/spec/{SPEC_NAME}/flow-log.md`: the stage name, what was produced and where (paths, branch, commit), any decisions taken along the way, and which stage comes next. The log is the flow's memory outside the context window — a fresh session (after a restart, a crash, or an unattended hand-off between sessions) resumes by reading this one small file instead of re-deriving state from the whole repo. That is what keeps the window small across a long flow: nothing needs to stay in context once it is in the log. The log is committed with the work (Step 9 stages it alongside the code), so it must never become an uncommittable leftover: **once the change request is opened — or the change is merged — stop writing to the tracked log**, since a commit adding log lines is unwelcome on a change request under review and impossible once it merges, so a late append would strand a change that can never reach it. From that point report late-stage progress to the user and via §9 notifications (exceptions only), and resume the remote stages from remote state (the open/merged change request and the ticket status), which the resume-detection stage already inspects. The close stage leaves a clean working tree and never writes a final entry it cannot commit.
- Never launch a nested headless session (`claude -p`) from this command — permission modes, PATH, and timeouts differ per machine. Unattended chaining belongs to the trigger setup (§6), outside this command.
- Tell every dispatched subagent: tools are functional — do not test them or make exploratory calls; every call needs a purpose. Run each delegated stage on the model tier recorded in §8 — the fast tier for mechanical transport work, the strongest for judgment.

## Self-Improvement Loop

When this run hits a defect in this command or in `context/product/delivery-flow.md` that blocks progress or forces a workaround:

1. **Flow defect** (disproven recorded fact, missing step, or instruction that forces a workaround) — fix the affected stage in this file and/or record a §10 Local Customization in `context/product/delivery-flow.md` in the same run; note the correction in the flow log; include the correction in the same change request while still pre-PR.
2. **Delivery decision change** (anything in §1–§9) — do not rewrite the decision record on your own; stop and tell the flow owner to re-run `/awos:flow`.
3. **Generator / AWOS framework defect** — do not silently patch around it; report it to the user as feedback for the AWOS repo.

Do not widen into unrelated flow refactors.

<!-- awos:flow:stage=fetch-ticket -->

### Step 1: Fetch & Normalize the Ticket

Use the fast model tier. Prefer the `gh` CLI; fall back to GitHub MCP only if `gh` is missing.

- **GitHub Issue** (`N`, `#N`, or `https://github.com/AlexanderMakarov/llm-wiki/issues/N`): `gh issue view N --repo AlexanderMakarov/llm-wiki --json number,title,body,labels,url,state,comments`. Also pull linked issues and follow URLs/attachments referenced in the body/comments (`gh api` / `gh issue view` as needed). If a link is unreachable, list it as unreachable — do not silently skip.
- **Local file:** read the path; normalize title + body.
- **Plain prompt:** treat `$ARGUMENTS` as the requirements text.

Extract and keep: `TICKET_ID` (issue number or `prompt`/`file`), title, description, acceptance hints, link (issue URL or `n/a`).

<!-- /awos:flow:stage -->

<!-- awos:flow:stage=resume-detection -->

### Step 2: Detect the Entry Point

Start with a cheap preflight on the fast model tier (per §8): is this feature **already done**? Check before doing any work — if the GitHub Issue is `closed`, or the owning AWOS spec is already `Completed` (or all its `tasks.md` items are `[x]`), or a merged pull request exists for the same work, report that and stop. Don't re-run the chain over work that is already delivered. Then: if `context/spec/{SPEC_NAME}/flow-log.md` exists, read it first — it names the last completed stage and carries the branch, commit, and change-request state. The log is a convenience, not ground truth: for the spec-generation stages the on-disk artifacts win when they disagree with the log (a manual or partial rerun can leave it stale) — cross-check `context/spec/` and, if they differ, resume from the first missing artifact and repair the log to match before continuing. Past spec generation there is no such artifact to scan, so the log is the only resume signal. Specs may already exist under `context/spec/`: inspect the matching directory and resume from the first missing artifact — skip `/awos:spec` if `functional-spec.md` exists, skip `/awos:tech` if `technical-considerations.md` exists, skip `/awos:tasks` if `tasks.md` exists, and so on.

<!-- /awos:flow:stage -->

<!-- awos:flow:stage=workspace -->

### Step 3: Prepare the Workspace

Verify `context/` is reachable from the repo root (`context/product/architecture.md` readable). Warn on a dirty working tree. Uncommitted AWOS artifacts — `context/product/delivery-flow.md` and this command file, left by `/awos:flow` — are an expected dirty-tree cause; surface them as such rather than treating them as a blocker. No submodules.

Create an isolated worktree + throwaway vault from `origin/main` (do **not** stay on the primary checkout for implementation). Execute the §2 recipe verbatim:

```bash
git fetch origin main
BRANCH="feat/<issue>-<short-slug>"
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

If already inside a matching worktree on `BRANCH`, reuse it and ensure `$WT/.worktree-vault` + worktree `config.json` still point at the throwaway vault (never copy the primary checkout's `config.json`).

Store `BRANCH`, `WT`, `TMP_VAULT`, and `TICKET_ID`. Always invoke `python3 -m llmwiki` from `$WT` — never PATH `llmwiki` (loads primary package/config).

**Vault rules for the rest of the run:** agent-driven mutating `llmwiki` commands target `$TMP_VAULT` only. Read-only probes against the live vault path (from primary `config.json` `vault.default_path`) are allowed (`lint`, `synth --estimate`, status/read helpers). Never write `raw/`, `wiki/`, or `site/` under the live vault from the agent.

<!-- /awos:flow:stage -->

<!-- awos:flow:stage=specs -->

### Step 4: Generate Specs and Tasks

Run the AWOS commands sequentially in the **main context**, passing the normalized ticket + surrounding context bundle:

1. `/awos:spec` — **approval gate:** stop and wait for the user to accept `functional-spec.md` before continuing.
2. `/awos:tech` — **approval gate:** stop and wait for the user to accept `technical-considerations.md` before continuing.
3. `/awos:tasks` — **no document gate** and **no draft Approve ask** under this command (Local Customization / §4). Upstream `/awos:tasks` Step 4 normally presents the slice plan and iterates until the user is satisfied — **suppress that Approve / AskUserQuestion loop here**. Draft the vertical slices, write `tasks.md` immediately, report a short chat summary of slices + agent assignments (informational only — not a blocking approval), then continue. Still ask for the other `/awos:tasks` decisions that are not draft approval (e.g. skip-tests intent when unclear, QA-agent hire choices). If the user objects in chat after seeing the summary, revise and rewrite `tasks.md`. Standalone `/awos:tasks` outside this flow keeps its full draft loop. The task list stays revisable by re-running `/awos:tasks`.

**Author field (#159 / §10):** After `/awos:spec` and `/awos:tech` write (or amend) their documents, ensure **Author** / **Author(s)** is the operator’s human name — never command names, issue ids, “AWOS”, “Auto”, or other agent/tool metadata. Resolve per run: session/host display name when available; else `git config user.name` (use a nickname if that is all git has — do not prompt). Prefer a multi-word display name when one is available. Ticket linkage stays on **Roadmap Item** / the issue line elsewhere in the header.

Store the spec directory name (e.g. `007-tasks-api`) as `SPEC_NAME`.

<!-- /awos:flow:stage -->

<!-- awos:flow:stage=commit-specs -->

### Step 5: Commit Specs

Stage `context/spec/{SPEC_NAME}/` and commit on `BRANCH` with a conventional message referencing the issue when present, e.g. `docs: add spec for #<TICKET_ID> <title>`. Do not push yet.

<!-- /awos:flow:stage -->

<!-- awos:flow:stage=implement -->

### Step 6: Implement via Subagents

Run `/awos:implement` in the **main context** (it dispatches coding subagents — do not nest it inside another subagent). It delegates all coding and tracks progress — do not implement tasks in the main context. Wait for all tasks to complete. Prefer specialists from `context/product/hired-agents.md` when markers name them; fall back to `general-purpose` when none match. Tell coding subagents the vault rules from Step 3 (`$TMP_VAULT` for writes; no live-vault mutation).

<!-- /awos:flow:stage -->

<!-- awos:flow:stage=verify -->

### Step 7: Verify

Run `/awos:verify` in the main context when criteria need `AskUserQuestion`; otherwise a subagent may drive evidence collection and return the verdict + gaps. Address gaps before proceeding.

Running automated verify is the flow's job. For CLI/acceptance criteria use `pytest` and `python3 -m llmwiki` against `$TMP_VAULT` when a vault is required — do not mutate the operator's live Obsidian vault. For UI criteria: `python3 -m llmwiki build --vault "$TMP_VAULT"` then Playwright against `$TMP_VAULT/site`, opening the built files as a reader does, rather than handing the user a routine `run` command. Manual confirmation is only for a criterion the agent genuinely cannot render here.

Read-only live-vault probes (`lint`, `synth --estimate`, etc.) are allowed when they help evidence. If verify forces a scope/approach change relative to the approved documents, that is a §9 exception — comment on the PR once one exists (or remember to comment after open).

<!-- /awos:flow:stage -->

<!-- awos:flow:stage=local-review -->

### Step 8: Local Review

**Smoke confirm first.** Ask the user to confirm the feature works as expected. Include a ready-to-paste **live vault** command block using worktree code (resolve `LIVE` from the primary checkout's gitignored `config.json` `vault.default_path` — never commit that path). Example shape:

```bash
cd "$WT"
LIVE="<path-from-primary-config.json>"
python3 -m llmwiki lint --vault "$LIVE"
# Mutating checks — you run these:
python3 -m llmwiki build --vault "$LIVE" --out "$LIVE/site"
# then open "$LIVE/site/index.html" in a browser
```

Do **not** execute the mutating live-vault commands yourself. Do not start review until the user confirms. A skipped confirmation means stop and report verified-but-unconfirmed.

The review must stay independent of this conversation's authorship bias:

- Do not add run-time focus areas drawn from what you implemented or suspect — the author framing the review is the bias.
- Dispatch exactly one reviewer subagent with the **fixed** prompt below (verbatim). That subagent writes findings to a file and returns only the verdict, the finding count by severity, and the file path.
- After the subagent returns: **Read the review file and print its full body in chat** (lead with `Review file: <path>` on its own line). Record the path in this stage's flow-log entry.
- Pause for keep/drop. The agent that applies accepted findings reads the review file and the diff fresh — relay the user's keep/drop decisions, not your own summary of the findings.

**Single local review (pre-push, branch diff `origin/main...HEAD`):**

On the strongest tier, dispatch **one** independent reviewer using the coding agent's own most suitable review skill, command, or subagent (do not hardcode a product-specific reviewer name). Pass this fixed prompt verbatim (no author-supplied focus list):

```text
Review git diff origin/main...HEAD (branch changes, not an open-PR number).

Load and apply every section of these docs, in this priority order for attention:
1. docs/maintainers/REVIEW_CHECKLIST.md — treat its Blocker vs Nit rule as the severity model (Security + Meta + broken layer boundaries / failing tests or build = Blocker; Code quality / Docs / Build+runtime smoke = Nit unless they trip Meta or Security). Use the checklist's Blocker shortlist.
2. docs/maintainers/ARCHITECTURE.md
3. docs/maintainers/DECLINED.md
4. CONTRIBUTING.md
5. SECURITY.md

Also look for bugs, logic errors, and security issues the checklist does not name.

Write the full review markdown to context/spec/{SPEC_NAME}/review.md with: Verdict (Approve | Request changes | Comment), counts by severity, findings grouped Blockers then Nits, each finding citing the relevant REVIEW_CHECKLIST section when applicable, and a concrete fix suggestion.

Return only: verdict, counts by severity, and the review file path — never the full review body in your report.
```

Replace `{SPEC_NAME}` with the actual spec directory name before dispatch.

The review file is **session-only (#159):** write it for keep/drop and chat presentation; it must never be staged or committed (see Step 9). `context/.gitignore` ignores `review.md` / `review-*.md`.

Present the printed review for keep/drop. Apply accepted findings before anything is pushed. Then run the static gate:

```bash
ruff check llmwiki tests scripts
python3 -m pytest tests/ -q
```

Do not push until keep/drop is done and the static gate is green. Serious findings that alter delivered behavior → §9 exception PR comment after the PR exists.

<!-- /awos:flow:stage -->

<!-- awos:flow:stage=commit-push -->

### Step 9: Commit & Push

Write this stage's flow-log entry **before** staging so the log rides in this commit — this is the flow-log's last committed state (see Context Discipline). Then stage all changed files, excluding `.env`, credentials, secrets, local vault/config (`config.json`, `.worktree-vault/`), and **all local-review dumps (#159):** `context/**/review.md` and `context/**/review-*.md` (covered by `context/.gitignore`). Prefer path-aware adds (`git add -u` / explicit paths) over a blind `git add context/` so gitignore cannot be bypassed with `-f`. Commit with conventional commits (`feat`/`fix`/`docs`/… per CONTRIBUTING), referencing `#<TICKET_ID>` when an issue exists. If `.githooks/pre-push` is active and rejects the push, fix ruff findings and create a new commit (do not `--no-verify` unless the user explicitly allows it). Push `BRANCH` to `origin`.

<!-- /awos:flow:stage -->

<!-- awos:flow:stage=remote-gates -->

### Step 10: Remote Gates

From here the change request is open — **do not append to the tracked flow-log** (Context Discipline): a commit adding log lines is unwelcome on a change request under review, and impossible once it merges. Report routine gate progress to the user in chat only; resume relies on the remote state, not the log. Post §9 exception comments only when an exception fires.

Before opening the PR: `git fetch origin main` and rebase onto `origin/main`. On conflicts: delegate resolution to a subagent, re-run `ruff` + `pytest`, confirm non-trivial resolutions with the user, then push. If the conflict or competing PR shows **functional overlap**, post a §9 overlap exception comment after the PR is open.

Open the pull request with `gh pr create` against `main` (fill Summary + applicable Pre-merge checklist boxes from `.github/PULL_REQUEST_TEMPLATE.md`). Do **not** post a "PR opened" notification comment.

Then wait on required GitHub Actions with `gh pr checks --watch` (Monitor-style polling, interval ≥30s, timeout ~30 minutes). On failure: use the `gha-diagnosis` skill plus `gh run view <id> --log-failed`, delegate the fix to a subagent, push, re-watch until green — or escalate to the user in chat if the ~30m window expires (ask whether to keep watching or hand off). Do **not** PR-comment on CI red or max-wait. Claude-in-CI workflows were removed (#116); do not wait on a Claude Code Review check. Do **not** poll CODEOWNERS human approval. Ticket state transitions are off — do not comment-close the GitHub Issue from this stage.

<!-- /awos:flow:stage -->

<!-- awos:flow:stage=merge -->

### Step 11: Merge

Re-check mergeability against current `origin/main` (fetch + rebase dry-run / `gh pr view`). If the branch no longer rebases cleanly: sync per §2, push, and return to Step 10 — remote gates run again on the new commit before any merge. Functional overlap surfaced here → §9 exception comment.

When every waited gate is green, show that status and ask the user for explicit merge confirmation in this run. Merge only on yes, via `gh pr merge` (merge commit or squash per repo defaults / user preference if stated). A skipped or unanswered confirmation means do not merge — report ready-to-merge in chat and stop. Do **not** post a "merged" or "gates passed" PR comment.

After merge: watch post-merge Actions on `main`; if they fail because of this change, diagnose (`gha-diagnosis`), fix forward on a follow-up commit or hotfix branch, and re-watch until green.

<!-- /awos:flow:stage -->

<!-- awos:flow:stage=delivery -->

### Step 12: Deliver

No auto-deploy and no `/release` invocation from this flow. Optionally print that a release remains a separate `/release` + tag when the maintainer chooses. Stop here for packaging.

<!-- /awos:flow:stage -->

<!-- awos:flow:stage=close-ticket -->

### Step 13: Close the Loop

Definition of Done: PR merged and post-merge required checks green. Report to the user in chat: PR URL, merge commit, local-review evidence (verdict, finding counts by severity, review file paths, that keep/drop ran), and any try-steps. Do **not** close or transition the GitHub Issue. Do **not** post a closing/merged PR comment unless a §9 exception still needs recording.

Leave a clean working tree: do not write a closing flow-log entry (the log was finalized at commit-push and the change request is now open or merged — a new entry could never be committed into it). If any flow-created artifact is still uncommitted, surface it in the report rather than leaving it behind — an uncommitted leftover after a merged or in-review change request is a bug, not a record.

<!-- /awos:flow:stage -->

---

<!-- awos:flow:generated date=2026-08-25 version=2.4.3 source=context/product/delivery-flow.md -->
