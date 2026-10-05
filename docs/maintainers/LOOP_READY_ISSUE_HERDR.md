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

`--dry-run` prints the work-for-today summary and the next eligible issue without spawning herdr. `--once` processes at most one ticket then exits. `--repo` overrides the default (`gh repo view` from cwd).

## Queue membership

An issue enters the automation queue only when it is **open**, carries the **label you passed**, and is **assigned to you** (the `gh api user` login running the driver). Issues with the label but another assignee are ignored; issues assigned to you without the label are ignored.

## Work for today counts

On startup (and in `--dry-run`), the driver prints a one-line queue summary, for example `22 with 'self-heal' label, 1 is assigned on 'AlexanderMakarov'`. Only the assigned subset is eligible for automatic starts. A live run also prints `params:` (`poll-seconds`, `agent-kind`, `mode=loop|once`) and, after each spawn, `{tab} herdr tab opened for #{n} gh issue … at HH:MM:SS`. If a GitHub merge/CI poll fails, the driver retries and leaves the worker agent running — that poll only gates starting the *next* ticket.

## Eligibility and sort order

Among assigned, labeled, open issues, the driver skips any issue that still has an open GitHub “blocked by” blocker. It then picks one ticket at a time: issues with the `important` label before those without, then ascending issue number.

## Serial workers (N = 1)

At most one ticket worker runs at a time. Each ticket gets a **new** herdr worker tab and agent session; the driver does not reuse the previous agent as “the next issue.” The driver owns queue advance — the one-ticket helper never fetches or starts the next GitHub issue.

## Thin skill (driver-inlined)

Routing for a single ticket lives in `.claude/skills/loop-ready-issue-herdr/SKILL.md` with `disable-model-invocation: true` — agents must not self-invoke it. That path is the **repo’s canonical contributor-skill tree** (same place as `/release`), not a Claude-only product surface: Cursor also loads top-level `.claude/skills/` from this checkout, and Codex can mirror from there when you install skills. For this loop the file is mainly a **source blob the Python driver reads and pastes** into `herdr agent prompt`, so the worker (default Cursor, or `--agent-kind claude` / `codex`) receives the one-ticket contract in the prompt and does not need to discover the skill by name. The body routes `bug` → `/fix-bug`, otherwise → `/implement-feature`, for that issue URL only. There is no slash command wrapper.

## Human gates and notifications

While a worker waits on you (herdr `blocked` — approval, question, permission), the driver holds the queue and does not start the next ticket. While the worker is actively delivering (including CI watch inside the delivery command), the driver keeps waiting. herdr `idle` or `done` alone does **not** mean “start the next issue.” This spike does **not** add a custom notifier; rely on **herdr’s built-in** agent status and notifications when a worker needs you.

## Advance rule (merge + post-merge CI)

The driver starts the **next** eligible issue only when the **current** issue is done on GitHub: a PR that **closed** the issue is **merged**, and **every check run GitHub reports on that merge commit** is **completed** with a green conclusion (`success`, `skipped`, or `neutral`). If no check runs exist yet on the merge commit, the driver **does not** advance (workflows may still be queuing). On advance, the driver closes the finished worker tab and opens a fresh one for the next issue — you do not need to close the tab yourself to unlock the queue. Closing a worker tab early is a valid **hard stop** for that ticket; the driver does not treat it as successful delivery and does not auto-advance as if merged.

## Polling interval

GitHub merge/CI checks for the in-flight issue use `--poll-seconds` (default **300**, five minutes) between α polls; herdr `agent wait` may return immediately when the worker is idle, blocked, or done, but the driver still waits the full poll interval before the next GitHub check. Empty-queue re-listing (without `--once`) also sleeps `--poll-seconds` between attempts.

## Trust model

Queue membership is gated on **you** (the `gh` viewer login) **and** the readiness label you pass — the driver only auto-starts issues assigned to you with that label. Issue titles, bodies, and comments are **untrusted** input to the autonomous worker agent (public-tracker prompt-injection surface); the assignee gate limits who can trigger automation but does not sanitize issue text. The driver **never** closes GitHub issues on your behalf. Collaborators with triage rights can still apply your readiness label to issues; treat unexpected labeled tickets as something to fix in GitHub before the driver picks them up.

## Hard stop and restore

If you close the worker tab or the agent disappears before merge + green post-merge CI, the driver prints a **WARNING** with restore steps: continue delivery for that issue URL in a new worker. **Before re-running** `python3 scripts/loop_ready_issue_herdr.py --label <NAME>` (add `--once` for a single ticket), **close the old `issue-N` worker tab** if it is still open — a fresh driver run spawns a **duplicate** worker for the same issue otherwise. Press **Ctrl+C** to stop the driver loop; in-flight workers are left open until you close them. The driver keeps polling GitHub for advance on that issue until α is satisfied or you stop.

## Empty queue

When no eligible issues remain, the driver sleeps `--poll-seconds` and re-lists; it does not invent work. Ctrl+C exits cleanly.

## Default agent kind

`--agent-kind` defaults to **cursor**. Optional values are `claude` and `codex` where your herdr install supports them.

## Related material

- Functional spec: `context/spec/303-loop-ready-issue-herdr/functional-spec.md`
- Roadmap item: [GitHub #296](https://github.com/AlexanderMakarov/llm-wiki/issues/296)
