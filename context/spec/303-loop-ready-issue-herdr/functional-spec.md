# Functional Specification: Herdr serial ready-issue loop (optional maintainer aid)

- **Roadmap Item:** [Spike: herdr-driven serial ready-issue loop (thin skill + driver tab)](https://github.com/AlexanderMakarov/llm-wiki/issues/296) — AWOS spec `303-loop-ready-issue-herdr`
- **Status:** In Review
- **Author:** 4ellendger

---

## 1. Overview and Rationale (The "Why")

Maintainers who already use herdr to run coding agents still start each GitHub ticket by hand: pick an issue, open a worker, run `/implement-feature` or `/fix-bug`, wait through human gates and CI, then remember to start the next one.

This change adds an **optional** morning loop: start a driver once with a readiness label you choose; see a short “work for today” count; then the driver walks open issues that both carry that label and are **assigned to you**, one at a time in a fresh worker. It holds while a ticket needs a human (herdr’s own agent notifications cover pings — this spike does not add a separate notifier). It starts the next issue only after the current one’s change is **merged** and **post-merge checks on the default branch are green**. Maintainers who never start the driver keep today’s manual flow unchanged.

Success: enqueue by assigning yourself and applying the label you pass to the driver; start once; answer when herdr shows a worker needs you; tickets drain in order without closing worker tabs by hand to unlock the next issue.

---

## 2. Functional Requirements (The "What")

### 2.1 Opt-in only

- Starting the loop is a deliberate morning action in herdr. Ignoring it leaves `/implement-feature` and `/fix-bug` as the only entry points.
  - **Acceptance Criteria:**
    - [x] Given the maintainer never starts the driver, when they work only with the existing delivery commands, then nothing about those commands’ substance or required steps has changed for this spike. *(Evidence: no edits to `.claude/commands/implement-feature.md` / `fix-bug.md` or `context/product/delivery-flow.md` in this change; feature is `scripts/` + skill + maintainer docs only.)*

### 2.2 herdr required for the loop

- The loop runs inside herdr (driver tab + worker tabs). Without herdr, the aid is documented as unavailable — not as a fallback shell-only product.
  - **Acceptance Criteria:**
    - [x] Given herdr is not available, when the maintainer reads the maintainer note for this aid, then it states clearly that herdr is required and that manual `/implement-feature` / `/fix-bug` remain the path. *(Evidence: `docs/maintainers/LOOP_READY_ISSUE_HERDR.md` + acceptance test.)*

### 2.3 Queue membership: parameter label + assignee

- The readiness label is **not hardcoded**. The maintainer passes the label name as a **parameter** when starting the Python driver (example name in docs may still be `agent-ready`; the running value is whatever was passed).
- After the label is provided, the driver **prints a “work for today” summary** before draining:
  - how many **open** issues currently have that label, and
  - how many of those are **assigned to the maintainer running the driver**.
- An issue is **in the automation queue** only when it is **open**, has the **provided label**, and is **assigned to that same maintainer**.
  - **Acceptance Criteria:**
    - [x] Given the maintainer starts the driver with label `L`, when startup finishes its summary, then the output shows the open-issue count for `L` and the subset count assigned to the running maintainer. *(Evidence: live `--dry-run`; unit + acceptance tests.)*
    - [x] Given an open issue with label `L` but not assigned to the running maintainer, when the driver selects work, then that issue is never started. *(Evidence: tests.)*
    - [x] Given an open issue assigned to the running maintainer but without label `L`, when the driver selects work, then that issue is never started. *(Evidence: tests.)*
    - [x] Given an open issue with label `L` and assigned to the running maintainer, when it is eligible under §2.4, then it can be selected in sort order. *(Evidence: tests.)*

### 2.4 Eligibility and sort order

- **Eligible:** open + provided label + assigned to the running maintainer + no open GitHub “blocked by” blockers (all blockers closed, or none).
- **Among eligible:** issues with `important` before those without; then ascending issue number.
  - **Acceptance Criteria:**
    - [x] Given two eligible issues, one with `important` and a higher number, when the driver picks next, then the `important` issue is chosen first. *(Evidence: tests.)*
    - [x] Given two eligible issues without `important`, when the driver picks next, then the lower issue number is chosen first. *(Evidence: tests.)*
    - [x] Given a labeled, assigned issue still blocked by an open blocker issue, when the driver picks next, then that issue is skipped until blockers are closed. *(Evidence: tests.)*

### 2.5 Serial workers (N = 1) and context reset

- At most one ticket agent runs at a time.
- Each ticket runs in a **new worker tab** (fresh interactive agent), not reused mid-queue for “the next issue” without a tab/process boundary.
- The driver owns queue advance; the one-ticket helper never fetches or starts the next GitHub issue.
  - **Acceptance Criteria:**
    - [x] Given a ticket is in progress, when the driver is running, then it does not start a second ticket worker in parallel. *(Evidence: `run_main_loop` serial structure + `--once` acceptance test with single spawn.)*
    - [x] Given ticket A finishes per §2.8, when ticket B starts, then B runs in a new worker tab/process, not by continuing A’s agent session as the next issue. *(Evidence: spawn per pick_next cycle creates a new tab; skill forbids queue advance.)*

### 2.6 Thin one-ticket helper

- The helper accepts one issue (preferred: number/URL from the driver) and routes:
  - `bug` label → `/fix-bug` for that issue
  - otherwise → `/implement-feature` for that issue
- It does not implement delivery logic; gates stay owned by the existing delivery flow.
  - **Acceptance Criteria:**
    - [x] Given a queued issue labeled `bug`, when the helper runs, then the worker is instructed to run the bug-fix delivery command for that issue only. *(Evidence: skill text + spawn prompt inline tests.)*
    - [x] Given a queued issue without `bug`, when the helper runs, then the worker is instructed to run the feature delivery command for that issue only. *(Evidence: skill text + tests.)*
    - [x] Given the helper is running, when the current ticket is unfinished, then the helper does not start another GitHub issue. *(Evidence: skill contract; driver owns queue.)*

### 2.7 Human gates (no extra notifier)

- While a worker needs human input (herdr `blocked` — approval, question, permission), the driver **holds** the queue and does not start the next ticket.
- This spike **does not** add a separate notification integration. Maintainers rely on **herdr’s existing** agent lifecycle hooks/notifications for blocked/done visibility.
- While the worker is actively delivering (including CI watch inside the delivery command), the driver keeps waiting.
- herdr `idle` / `done` alone do **not** mean “start the next issue.”
  - **Acceptance Criteria:**
    - [x] Given the worker is waiting on a human decision and herdr reports blocked, when the driver is running, then no new ticket worker is started. *(Evidence: wait loop advances only on α; blocked ends a wait slice without spawn.)*
    - [x] Given the spike’s deliverables, when reviewing the change, then there is no new custom “send a notification” feature beyond using herdr’s built-in agent status/notifications. *(Evidence: no notification plugin/code; docs state rely on herdr.)*
    - [x] Given the worker shows idle or done mid-ticket, when the current issue is not yet delivered per §2.8, then the driver does not start the next issue. *(Evidence: advance_ready / wait loop tests.)*

### 2.8 Advance rule (Option α) — no manual tab-close to unlock the queue

- The driver starts the **next** eligible issue only when the **current** issue’s delivery is done on GitHub:
  1. A PR that closed that issue is **merged**, and
  2. **Every check run observed on that merge commit** is **completed** with a green conclusion; an **empty** check-run list means **not ready** (CI may still be queuing).
- On advance, the **driver** retires/closes the finished worker tab as needed and opens a fresh worker for the next issue. The maintainer does **not** need to manually close the herdr tab or stop the agent solely to let the queue proceed.
- Closing a worker tab remains a valid **hard stop** for that ticket if the maintainer chooses; the driver must not treat a manual stop as “merged.”
  - **Acceptance Criteria:**
    - [x] Given the current ticket’s PR is not merged, when the worker is idle/done or the maintainer has not closed the tab, then the next eligible issue is not started. *(Evidence: advance_ready false paths + wait loop.)*
    - [ ] Given the PR is merged and every observed post-merge check run on the merge commit is green, when the driver observes that, then it retires the current worker (without requiring the maintainer to close the tab first) and starts the next eligible issue in a new worker. *(Needs operator smoke with a real merged ticket or mocked live herdr session.)*
    - [x] Given the maintainer closes the worker tab before merge, when the driver notices the worker is gone, then it does not treat that as successful delivery and does not auto-advance as if merged. *(Evidence: WARNING contract tests + wait loop keeps polling GitHub.)*

### 2.9 Morning driver

- The maintainer starts a **Python** driver in a dedicated driver tab once (stdlib; talks to GitHub and herdr only — no LLM in the driver), passing the readiness label parameter.
- When the queue is empty, the driver idles until stopped or until new eligible issues appear (documented in the maintainer note).
  - **Acceptance Criteria:**
    - [ ] Given eligible issues exist for the provided label and assignee, when the maintainer starts the driver with that label, then after the “work for today” summary tickets begin draining in §2.4 order without a per-ticket “do the next one” prompt. *(Needs operator smoke with a labeled+assigned issue + herdr.)*
    - [x] Given the queue is empty, when the driver has finished the last eligible issue, then it does not invent work; it idles or exits per the maintainer note without starting issues that fail §2.3. *(Evidence: empty-queue `--once` acceptance test + live dry-run `next: none`.)*

### 2.10 Harnesses

- Cursor is the primary worker agent; Claude and Codex may be offered as optional kinds via the same herdr start path where documented.
  - **Acceptance Criteria:**
    - [x] Given the default setup, when the driver starts a worker, then Cursor is the default agent kind unless the maintainer configured an optional alternative listed in the note. *(Evidence: argparse default `cursor`; docs list `--agent-kind`.)*

---

## 3. Scope and Boundaries

### In-Scope

- Optional herdr driver (Python) + thin one-ticket skill/wrapper
- Queue: **driver label parameter** + **assignee = running maintainer**; startup counts; eligibility via native blocked-by; sort via `important` then issue number
- Advance on merged PR + green post-merge checks; driver-managed worker retirement
- Short maintainer note (opt-in, herdr required, label+assignee gate, pause/hard-stop; rely on herdr’s built-in notifications)
- Small automated check for the sort/eligibility rules
- Pointers so Claude/Codex can discover the thin skill if those harnesses are used

### Out-of-Scope

- Making the loop required for all maintainers
- Merging `/fix-bug` and `/implement-feature` into one mega-command
- Parallel ticket agents or a productized agent board / Kanban
- Hosting interactive agents outside herdr
- Hardcoding a single repository readiness label name in the driver
- Building a new notification channel or herdr-notifications plugin for this spike
- Per-label GitHub ACL or changing who may open issues on the public repo
- Replacing CI/PR watching inside the delivery commands with herdr
- Auto-closing GitHub issues from this loop
- Non-herdr “headless” driver as a supported product path for this spike
