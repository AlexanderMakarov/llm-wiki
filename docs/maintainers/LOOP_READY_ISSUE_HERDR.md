# Loop ready issue (herdr)

Optional maintainer aid for draining a personal GitHub readiness queue inside herdr: one Python driver tab plus serial worker tabs. It is not an `llmwiki` subcommand, is not shipped in the PyPI wheel, and does not change `/implement-feature` or `/fix-bug` unless you start the loop.

## Opt-in only

Nothing in the delivery commands requires this loop. If you never run the driver, you keep picking issues and opening workers by hand exactly as today.

## herdr required

The loop depends on herdr (driver tab, worker tabs, `herdr agent` lifecycle). Without herdr there is no supported path — use `/implement-feature` and `/fix-bug` manually. This spike does not add a shell-only or headless product mode.

## Morning start

From a git checkout of this repository (repository root as cwd), open a dedicated herdr tab and run:

```bash
python3 scripts/loop_ready_issue_herdr.py --label <NAME>
```

Replace `<NAME>` with the readiness label you use on GitHub (docs and examples may say `agent-ready`; the running value is whatever you pass). Prerequisites: authenticated `gh`, `herdr` on PATH, and the repo checkout the workers should use.

Useful variants:

```bash
python3 scripts/loop_ready_issue_herdr.py --label <NAME> --dry-run
python3 scripts/loop_ready_issue_herdr.py --label <NAME> --once
python3 scripts/loop_ready_issue_herdr.py --label <NAME> --agent-kind claude
python3 scripts/loop_ready_issue_herdr.py --label <NAME> --repo OWNER/NAME
```

`--dry-run` prints the work-for-today summary, the **planned** eligible queue in driver order (`important` then issue number, blockers excluded) with in-progress tickets (an open `issue-N` herdr tab) listed first, oldest tab first, and marked `(in progress, tab open)`, and `next:` (the ticket the driver would resume or start) without spawning herdr. It reads `herdr tab list` read-only; if herdr is missing or errors it prints `in-progress: unknown (herdr unavailable: <reason>)` and falls back to plain queue order, so dry-run never fails because of herdr. `--once` processes at most one ticket then exits. `--repo` overrides the default (`gh repo view` from cwd).

There is no Make wrapper for this script: the repo has no other Makefile surface, and a target that still requires `LABEL=…` is not more convenient than calling `python3 scripts/loop_ready_issue_herdr.py --label …` directly.

## Queue membership

An issue enters the automation queue only when it is **open**, carries the **label you passed**, and is **assigned to you** (the `gh api user` login running the driver). Issues with the label but another assignee are ignored; issues assigned to you without the label are ignored.

## Work for today counts

On startup (and in `--dry-run`), the driver prints a one-line queue summary, for example `22 with 'self-heal' label, 1 is assigned on 'AlexanderMakarov'`. Only the assigned subset is eligible for automatic starts. A live run also prints `params:` (`poll-seconds`, `agent-kind`, `mode=loop|once`) and, after each spawn, `{tab} herdr tab opened for #{n} gh issue … at HH:MM:SS`. While it waits on a ticket, every GitHub poll that does not advance prints one status line, for example `#323 open; no merged PR closes it yet — waiting 300s`, `#323: PR #335 merged; post-merge CI 3/5 green (2 pending) — waiting 300s`, or `… no check runs yet on the merge commit …`, with ` (worker gone)` appended once the worker agent has disappeared. If a GitHub merge/CI poll fails, the driver retries and leaves the worker agent running — that poll only gates starting the *next* ticket.

## Eligibility and sort order

Among assigned, labeled, open issues, the driver skips any issue that still has an open GitHub “blocked by” blocker. It then picks one ticket at a time: issues with the `important` label before those without, then ascending issue number.

## Serial workers (N = 1)

At most one ticket worker runs at a time. Before starting new work, the driver resumes an eligible ticket that already has an open `issue-N` herdr tab (a session restored after a reboot, or a driver restart), even when another issue sorts ahead of it; if several eligible tickets have open tabs, it resumes the one whose tab is oldest (lowest herdr tab `number`, i.e. leftmost in the tab bar; ties by tab id), prints a WARNING naming the others (`WARNING: N eligible issues have an open issue-N tab; resuming #311 first (oldest tab); the others (#256) wait their turn and are adopted later with no new prompt.`), and adopts each in turn later with no new prompt. Tab bar order is start order (new tabs append; herdr restore keeps it), so drag tabs to reprioritize. An `issue-N` tab whose issue is not in the eligible queue (closed, unlabeled, unassigned, or blocked) prints one WARNING per driver run (`issue-N tab open but #N is not in the eligible queue (closed, unlabeled, unassigned, or blocked); close the tab or restore label/assignee.`) and does not hold the queue. Each new ticket gets a **new** herdr worker tab and agent session; the driver does not reuse the previous agent as “the next issue.” The driver owns queue advance — the one-ticket helper never fetches or starts the next GitHub issue.

## Thin skill (driver-inlined)

Routing for a single ticket lives in `.claude/skills/loop-ready-issue-herdr/SKILL.md` with `disable-model-invocation: true` — agents must not self-invoke it. That path is the **repo’s canonical contributor-skill tree** (same place as `/release`), not a Claude-only product surface: Cursor also loads top-level `.claude/skills/` from this checkout, and Codex can mirror from there when you install skills. For this loop the file is mainly a **source blob the Python driver reads and pastes** into `herdr agent prompt`, so the worker (default Cursor, or `--agent-kind claude` / `codex`) receives the one-ticket contract in the prompt and does not need to discover the skill by name. The body routes `bug` → `/fix-bug`, otherwise → `/implement-feature`, for that issue URL only. There is no slash command wrapper.

## Human gates and notifications

While a worker waits on you (herdr `blocked` — approval, question, permission), the driver holds the queue and does not start the next ticket. While the worker is actively delivering (including CI watch inside the delivery command), the driver keeps waiting. herdr `idle` or `done` alone does **not** mean “start the next issue.” This spike does **not** add a custom notifier; rely on **herdr’s built-in** agent status and notifications when a worker needs you.

## Advance rule (merge + post-merge CI, or closed)

The driver starts the **next** eligible issue only when the **current** issue is done on GitHub, checked in this order on every poll:

1. **Merged closing PR** — a PR that **closed** the issue is **merged**: the driver advances only when **every check run GitHub reports on that merge commit** is **completed** with a green conclusion (`success`, `skipped`, or `neutral`). If no check runs exist yet on the merge commit, the driver **does not** advance (workflows may still be queuing). GitHub auto-closes the issue on that merge, so a CLOSED issue never skips this CI gate.
2. **Closed without a merged closing PR** — the issue is CLOSED (completed by hand, not planned, duplicate) and no merged PR closes it: the driver advances at once and skips the CI gate, printing e.g. `Advanced #323 (closed: COMPLETED, no merged closing PR; CI gate skipped); worker tab closed.`
3. Otherwise it keeps waiting.

On advance, the driver always closes the finished worker tab (even if the agent already went idle/disappeared — that only stops `herdr agent wait`, not tab cleanup) and opens a fresh one for the next issue — you do not need to close the tab yourself to unlock the queue. If a tab labeled `issue-N` is already open when the driver reaches issue N (a herdr session restored after a reboot, or a driver restart), the driver **adopts** it: it sends no new prompt and just polls GitHub for α, so in-progress delivery is not restarted. Close that tab first if you want a fresh worker. At startup and at the top of every queue cycle the driver lists herdr tabs labeled `issue-N` once — for this sweep and for resume-first selection (if the list fails, selection falls back to queue order and the driver still refuses to spawn a worker it cannot check for a duplicate tab) — asks GitHub for those issues' state in one batched query, and closes each tab whose issue is already CLOSED (`Closed herdr tab issue-N (<tab_id>): #N is closed.`) — leftovers from an earlier run or a ticket closed while the driver was stopped. A tab whose issue GitHub cannot resolve is left alone, and a herdr or GitHub failure in this sweep only prints a WARNING. Closing a worker tab early is a valid **hard stop** for that ticket; the driver does not treat it as successful delivery and does not auto-advance as if merged.

## Polling interval

GitHub merge/CI checks for the in-flight issue use `--poll-seconds` (default **300**, five minutes) between α polls; herdr `agent wait` may return immediately when the worker is idle, blocked, or done, but the driver still waits the full poll interval before the next GitHub check. Empty-queue re-listing (without `--once`) also sleeps `--poll-seconds` between attempts.

## Trust model

Queue membership is gated on **you** (the `gh` viewer login) **and** the readiness label you pass — the driver only auto-starts issues assigned to you with that label. Issue titles, bodies, and comments are **untrusted** input to the autonomous worker agent (public-tracker prompt-injection surface); the assignee gate limits who can trigger automation but does not sanitize issue text. The driver **never** closes GitHub issues on your behalf. Collaborators with triage rights can still apply your readiness label to issues; treat unexpected labeled tickets as something to fix in GitHub before the driver picks them up.

## Hard stop and restore

If you close the worker tab or the agent disappears before merge + green post-merge CI, the driver prints a **WARNING** with restore steps: continue delivery for that issue URL in a new worker. Re-running the driver adopts the open `issue-N` tab instead of spawning a new worker; close it first to start the ticket over. Press **Ctrl+C** to stop the driver loop; in-flight workers are left open until you close them, until advance closes them, or until a later driver run finds their issue CLOSED and closes the tab. The driver keeps polling GitHub for advance on that issue until α is satisfied or you stop.

## Empty queue

When no eligible issues remain, the driver sleeps `--poll-seconds` and re-lists; it does not invent work. Ctrl+C exits cleanly.

## Default agent kind

`--agent-kind` defaults to **cursor**. Optional values are `claude` and `codex` where your herdr install supports them.

## Related material

- Functional spec: `context/spec/303-loop-ready-issue-herdr/functional-spec.md`
- Roadmap item: [GitHub #296](https://github.com/AlexanderMakarov/llm-wiki/issues/296)
