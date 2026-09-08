# Flow log — #227 command surface parity

Bug: https://github.com/AlexanderMakarov/llm-wiki/issues/227
Branch: `fix/227-command-surface-parity` · worktree `.claude/worktrees/fix-227-command-surface-parity`

## fetch-bug

`gh issue view 227` — open, label `bug`, no comments. Five ACs: Cursor parity for the delivery commands; `/awos:flow` reachable-or-corrected for Claude; a recorded decision for `/maintainer` + `/triage-issue`; parity generated or tested; per-surface state in `docs/maintainers/README.md`.

## resume-detection

No prior spec dir, no branch, no PR for #227. Orphan fix → fix-as-spec dir `context/spec/227-command-surface-parity/` (#164).

## diagnose

Three findings, two of which correct the issue's own premise:

1. **Cursor parity gap is real.** Cursor loads commands from `.cursor/commands/` only — `.claude/commands/` is not scanned (<https://cursor.com/docs/agent/chat/commands>). `/fix-bug`, `/implement-feature`, `/maintainer`, `/triage-issue` therefore do not resolve in Cursor.
2. **`/awos:flow` is NOT missing for Claude.** It ships from the `awos@awos-marketplace` plugin (`docs/maintainers/AWOS-CURSOR.md:204`); `.cursor/commands/awos-flow.md` is the generated Layer C artifact from `scripts/sync-awos-plugin-cursor.sh`, committed only because Cursor has no plugin runtime. The defect is **discoverability** — neither the instruction line in the two generated commands nor `docs/maintainers/README.md` names the plugin prerequisite. Forking the 52KB body into `.claude/commands/awos/flow.md` was rejected: it would hand-maintain a plugin-owned command.
3. **No generator covers hand-written commands.** `scripts/sync-awos-cursor-commands.sh` only regenerates `.cursor/commands/awos-*.md` from `.awos/commands/`. `/release` achieved parity by a byte-identical hand copy — the drift mechanism itself.

Supporting facts: Cursor *does* read `.claude/skills/` natively, which is why `/release` works on both surfaces (spec 200 put the body in `.claude/skills/release/SKILL.md`). `.claude/skills/project-maintainer/` is a generic framework phase-gate skill and does **not** duplicate `/maintainer`. Neither delivery command references `/maintainer` or `/triage-issue` (grep over all 495 lines).

## classify

**Conformance** — no pre-existing `functional-spec.md` owns command surfaces, so there is no spec to amend. Recorded: no functional-spec to amend.

One decision-record defect noted for the owner: `delivery-flow.md` §5 records *"do not transition or close GitHub Issues from this flow"* / *"Issues left untouched"*, but the owner states the real intent is that GitHub auto-closes issues via the PR body and the rule exists only to stop agents adding issue comments. That is a §1/§5 delivery-decision change → routed to a separate `/awos:flow` re-run by the flow owner, per the Self-Improvement Loop. Not changed here.

## decisions (flow owner)

- AC #2 → document the plugin prerequisite; do not create `.claude/commands/awos/flow.md`.
- AC #3 → **remove** `/maintainer` and `/triage-issue` rather than mirror them.
- AC #4 → generator **and** structural test (file-level only; no agent invocation).
- Remaining work stays in this one PR; the `/awos:flow` re-run for issue-close mechanics is the owner's separate run.

Next: fix stage.

## fix + regression-test

- `scripts/sync-cursor-commands.sh` — new generator emitting thin `.cursor/commands/<name>.md` wrappers for a declared `COMMANDS=(fix-bug implement-feature)` array. Each wrapper carries the source `description`, a generated-file marker, a pointer naming `.claude/commands/<name>.md` as source of truth, the `.cursor/rules/awos-cursor-runtime.mdc` tool mapping, the strict `AskQuestion` block, and `$ARGUMENTS` passthrough. Idempotent. Wired into `scripts/update-awos.sh` Layer A. `.cursor/commands/release.md` deliberately untouched — it independently loads the shared `.claude/skills/release/SKILL.md`.
- Removed `.claude/commands/maintainer.md` and `.claude/commands/triage-issue.md`; updated `docs/maintainers/{README,TRIAGE,DECLINED}.md`, `docs/reference/{slash-commands,cli}.md`, `CONTRIBUTING.md`, `CHANGELOG.md`, `tests/test_slash_cli_parity.py`, `tests/test_install_agent_kit.py`. `DECLINED.md` keeps its original wording plus a dated retirement note; `demo/**`, released CHANGELOG entries and prior `context/spec/**` logs left as historical records.
- `/awos:flow` prerequisite sentence corrected in both generated commands, recorded as a `delivery-flow.md` §10 Local Customization so a re-run preserves it. §1–§9 untouched.
- `tests/test_command_surface_parity.py` — 13 structural tests (no agent invocation): two-way Claude↔Cursor mapping with reason-carrying `CLAUDE_ONLY` / `CURSOR_ONLY` allowlists, the two legal wrapper shapes (byte-identical or contains its source path), generator-array honesty, generated-file markers, and removed-commands-stay-removed. RED-validated on the mapping, wrapper-shape and removal properties.

## verify-criteria

All five issue ACs evidenced. Cursor CLI discovery confirmed empirically: the installed `cursor-agent` bundle references `.cursor/commands` as its only commands root, alongside `.cursor/skills` / `.claude/skills` / `.codex/skills` / `.agents/skills` for skills — Cursor adopted Claude Code's skills tree, not its commands tree. No global `~/.cursor/commands` entry or `fix-bug` skill existed in any root, so the wrappers are load-bearing.

Gates: `ruff check llmwiki tests scripts` clean; `python3 -m pytest tests/ -q` → 4969 passed, 81 skipped, exit 0. Generator re-run produces no diff.

## local-review

Skipped at the flow owner's direction — the independent review agent was stopped before it wrote `review.md`, and the owner chose to proceed. No review artifact exists for this run.

Next: commit-push, then PR against `main`.
