# Technical Specification: Loop ready issue (herdr)

- **Functional Specification:** `context/spec/303-loop-ready-issue-herdr/functional-spec.md`
- **Status:** Approved
- **Author(s):** 4ellendger

---

## 1. High-Level Technical Approach

Add an **opt-in maintainer-only** Python driver under `scripts/` plus a **non-invocable** thin skill under `.claude/skills/`. The driver shells `gh` and `herdr` via `subprocess` (stdlib only, no LLM). Pure queue/sort/eligibility logic lives in testable functions; I/O adapters are thin wrappers.

Delivery commands (`/implement-feature`, `/fix-bug`) stay unchanged. The driver **reads the skill file and injects** one-ticket instructions into `herdr agent prompt` — agents do not self-select the skill. Advance is decided by **GitHub merge + post-merge CI**, not herdr `done`/`idle` and not a signal from the skill. herdr lifecycle uses **event-driven wait/subscribe**; GitHub advance uses **`--poll-seconds` (default 300)**. No custom notification feature — herdr’s built-in agent hooks suffice.

---

## 2. Proposed Solution & Implementation Plan (The "How")

### 2.1 Naming & placement

| Piece | Path | Role |
|---|---|---|
| Driver CLI | `scripts/loop_ready_issue_herdr.py` | Morning loop: summary → pick → spawn worker → wait → advance |
| Skill (not a command) | `.claude/skills/loop-ready-issue-herdr/SKILL.md` | One-ticket route text; `disable-model-invocation: true` |
| Slash command | **None** | — |
| Maintainer note | `docs/maintainers/LOOP_READY_ISSUE_HERDR.md` + row in `docs/maintainers/README.md` | Opt-in, herdr required, how to run, hard-stop / restore |
| Tests | `tests/test_loop_ready_issue_herdr.py` | Sort/eligibility/summary/advance helpers; mock subprocess |

Not an `llmwiki` subcommand; not shipped in the PyPI wheel; not under `llmwiki/agent_kit/`. Spec directory name: `303-loop-ready-issue-herdr`.

### 2.2 Driver CLI contract

```text
python3 scripts/loop_ready_issue_herdr.py --label <NAME> [options]
```

| Flag | Purpose |
|---|---|
| `--label` (required) | Readiness label name (docs may example `agent-ready`) |
| `--repo` | Optional `owner/name`; default: `gh repo view --json nameWithOwner` from cwd |
| `--agent-kind` | Default `cursor`; allow `claude`, `codex` |
| `--poll-seconds` | Default **300** (5 minutes) — GitHub merge/CI and empty-queue refresh only |
| `--once` | Process at most one ticket then exit |
| `--dry-run` | Print summary + next eligible issue; no herdr spawn |

**Startup (“work for today”):** resolve viewer login (`gh api user`), list open issues with `--label`, print:
- `open_with_label: N`
- `assigned_to_me: M`  
then enter the loop (unless `--dry-run`).

### 2.3 GitHub call budget

Minimize calls; **never** run `blockedBy` on the full open-issue set.

1. **One list call:** open issues with `--label` (include `number`, `title`, `labels`, `assignees`, `url`).
2. **In-process:** compute startup counts; filter `assignee == viewer` → candidates.
3. **`blockedBy` only for candidates** — one batched GraphQL query for those issue numbers (`Issue.blockedBy { nodes { number state } }`).
4. Sort eligible in process: `(0 if important else 1, number)`.

**While waiting on ticket `#N`:** do not re-list the whole queue every tick. Poll **only** merge + post-merge CI for `#N` every `--poll-seconds`. Refresh the queue listing after advance or on empty-queue idle ticks.

**Advance predicate (α):** linked PR for `#N` is **merged** and post-merge required checks on the default branch for that merge commit are **green**. Do **not** advance on “issue closed” alone, herdr `idle`/`done`, or skill/pane signals.

### 2.4 Pure functions (testable)

- `work_for_today_counts(issues, login, label) → (with_label, assigned_to_me)`
- `candidates_assigned(issues, login, label)` — open ∧ label ∧ assignee (pre-blockedBy)
- `eligible_after_blocked_by(candidates, blocked_by_map)` — drop issues with any open blocker
- `sort_key(issue)` / `pick_next(...)`
- `advance_ready(merge_info, check_runs) → bool` (pure over fetched status shapes)

### 2.5 herdr lifecycle (event/wait, N=1)

Per ticket (serial):

1. `herdr tab create --cwd <repo> --label "issue-N" --no-focus` (capture tab/pane id).
2. `herdr agent start … --kind <kind> --pane <id>`.
3. Read skill file; `herdr agent prompt` with inlined one-ticket instructions for `#N` URL.
4. **herdr side:** block on `herdr agent wait` / socket `events.subscribe`+`events.wait` (not busy-poll). On `blocked`, hold queue (built-in herdr notifications). On `idle`/`done`, do **not** advance — keep waiting / GitHub poll.
5. **GitHub side:** every `--poll-seconds`, check α for `#N`.
6. When α true: `herdr tab close` for that worker → next issue.

Empty eligible queue: sleep `--poll-seconds`, re-fetch list+candidate blockedBy as in §2.3; Ctrl+C exits cleanly.

### 2.6 Early worker disappearance

If the worker tab/agent is gone before α: print a **WARNING** with restore instructions (re-open worker and continue delivery for the URL; re-run driver with `--label` / `--once`; Ctrl+C to stop the loop). Do **not** treat as successful delivery. Keep waiting on GitHub for `#N` per α unless the operator stops the driver.

### 2.7 Thin skill content (driver-injected)

`.claude/skills/loop-ready-issue-herdr/SKILL.md`:

1. Input: issue number or URL (from driver prompt).
2. Inspect labels (`bug` → `/fix-bug`; else `/implement-feature`).
3. Span **one ticket only**. Never list/advance the readiness queue.
4. Do not duplicate delivery-flow gates.
5. Frontmatter: `disable-model-invocation: true` (agents must not self-invoke).

### 2.8 Docs / CHANGELOG

- `docs/maintainers/LOOP_READY_ISSUE_HERDR.md` — morning start, `--label`, assignee rule, α advance, herdr required, hard-stop / restore, empty-queue idle, no extra notifier, `--poll-seconds` default 300.
- Link from `docs/maintainers/README.md`.
- `CHANGELOG.md` under Unreleased (maintainer opt-in).
- Spec artifacts under `context/spec/303-loop-ready-issue-herdr/`.

### 2.9 Non-goals in code

No `llmwiki/` runtime package behavior changes. No slash command. No herdr-notifications plugin. No hardcoded readiness label as the only gate. No LLM-in-the-driver. No GitHub webhooks.

---

## 3. Impact and Risk Analysis

| Risk | Mitigation |
|---|---|
| herdr `idle`/`done` mistaken for ticket done | Advance only via merge + post-merge CI helpers |
| Worker tab closed early | Warning + restore instructions; do not advance as success |
| GraphQL `blockedBy` drift | Batched query on candidates only; warn if unavailable |
| Public label applyable by triage collaborators | Document residual risk; assignee gate required |
| Long CI wait | Intended (α); 5-minute poll; Ctrl+C / `--once` escape |
| Skill not loaded by agent | Driver inlines skill text; `disable-model-invocation: true` |

**Dependencies:** local `gh` auth, `herdr` on PATH, repo checkout cwd, delivery commands already present.

---

## 4. Testing Strategy

- **Unit (required):** `tests/test_loop_ready_issue_herdr.py` loads the script by path; fixtures for counts, assignee+label filter, blockedBy-only-on-candidates eligibility, sort, advance helpers — **no live network**.
- **Mocked I/O (light):** monkeypatch `subprocess` for dry-run selection if cheap.
- **Manual smoke (operator):** `--dry-run --label …` against the real repo; optional one live herdr spawn outside CI.
- **Not in CI:** live herdr session or live GitHub mutation.
