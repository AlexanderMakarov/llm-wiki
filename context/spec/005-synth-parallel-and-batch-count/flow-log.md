# Flow log — 005-synth-parallel-and-batch-count (#118)

Memory of the `/implement-feature` run outside the context window. One entry per completed stage. Finalized at the commit-push stage — nothing is appended once the PR is open.

## fetch-ticket

- **Ticket:** GitHub Issue #118 — "synth: print pending file count at start; run page synthesis in parallel" (`enhancement`, `important`, state `OPEN`), https://github.com/AlexanderMakarov/llm-wiki/issues/118
- No comments, no attachments. Related: #113 (merged as PR #119) — this issue is its smoke-feedback follow-up; token/cost reporting stays on #113.
- **Next:** resume-detection.

## resume-detection

- Issue OPEN; no `context/spec/*` directory for #118; no branch matching `118`; only PR referencing 118 is #119 (which is #113's work, merged). Nothing to resume — full chain from workspace.
- **Next:** workspace.

## workspace

- **Branch:** `feat/118-synth-parallel` off `origin/main` @ `be38e40`
- **Worktree:** `.claude/worktrees/feat-118-synth-parallel`
- **Throwaway vault:** `<WT>/.worktree-vault`, worktree `config.json` points at it; `llmwiki init` seeded it. `setup.sh` run with `LLMWIKI_SKIP_AUTOMATION=1` (needed `bash ./setup.sh` — file is not executable in a fresh worktree).
- Primary checkout tree was clean at start.
- **Next:** specs.

## specs — functional spec

- **Artifact:** `context/spec/005-synth-parallel-and-batch-count/functional-spec.md` (`SPEC_NAME=005-synth-parallel-and-batch-count`)
- **Decisions taken with the user (AskUserQuestion):**
  - Default concurrency: **2 pages at a time** (user chose the conservative option over the recommended 4).
  - Override: **both** a per-run CLI option **and** a saved config preference; the CLI option wins.
  - Progress display: **completed/total counter prefixed on each per-page line**.
  - Local (Ollama) synthesizer gets the **same default** as the Claude CLI synthesizer — one number, one mental model.
- Spec carries FR1–FR6 (start-of-run count, parallel execution, override + validation, progress counter, unchanged results/failure semantics, discoverability) with 29 acceptance criteria.
- **Gate:** user approved ("lgtm"), 2026-08-06.
- **Next:** `/awos:tech`.

## specs — technical considerations

- **Artifact:** `context/spec/005-synth-parallel-and-batch-count/technical-considerations.md`
- **Design:** `ThreadPoolExecutor` (stdlib — no new dep) over a **pure** per-source worker `_synthesize_one`; the main thread drains `as_completed` and owns *every* shared mutation (`state` dict, `_save_state`, pending-drop, `summary`, `producers`, stdout). That structurally removes most locking.
- **Findings that drove the design (verified by reading, not assumed):**
  - `state_store.update_state` already serializes with `fcntl.flock` and `_save_state` upserts only passed keys → the state *file* was never the hazard, only the in-memory dict.
  - `ClaudeCLISynthesizer.synthesize_source_page` does `self._run_tokens += …` (read-modify-write) → needs an instance `threading.Lock`, else token/cost totals silently under-report.
  - `OllamaSynthesizer` mutates instance attrs only in `__init__`; `DummySynthesizer` is stateless → both already thread-safe.
  - Two sources in one batch can derive the same target filename → a module-level write lock makes `_build_source_page` (reads target for #351 tag preservation) → stub guard (reads target) → `write_text` atomic. Never held across a backend call.
- **Decisions taken without asking (flagged to the user at the gate):**
  - Config key `synthesis.concurrency` (default 2, ceiling `MAX_SYNTH_CONCURRENCY = 16`). Ceiling exists because the number bounds concurrent `claude -p` **subprocesses**.
  - Validation split: config values tolerant (warn + fall back, matching `resolve_backend`); CLI values strict (exit 2), because a silently-ignored typed flag is worse than a refusal.
  - **No `--synth-concurrency` mirror flag on `all`** — deliberate departure from the `--synth-force` precedent; the saved preference already serves non-interactive runs.
  - Ctrl-C: catch in the drain, `shutdown(wait=False, cancel_futures=True)`, report in-flight count, re-raise — otherwise `__exit__`'s `wait=True` looks like a hang.
  - Multi-part docs now print all their lines together on source completion (one source = one progress unit) instead of per part as written.
- **Known churn:** the `[k/N]` prefix changes every per-page stdout line, so existing `test_synth_*` stdout assertions need updating; ordering assertions must become order-independent.
- **Gate:** user approved ("lgtm"), 2026-08-07.
- **Next:** `/awos:tasks`.

## specs — tasks

- **Artifact:** `context/spec/005-synth-parallel-and-batch-count/tasks.md` — 6 slices, 25 tasks. Draft Approve loop suppressed per delivery-flow §10 (summary reported to chat, non-blocking).
- **Slice ordering rationale:** the risky threading slice lands last among implementation slices, after the setting it needs (Slice 2) and after the backends it calls are proven thread-safe (Slice 3), so Slice 4 never ships a known race. Slice 1 (count line) is independent of everything.
  1. Batch count at start of run (FR1 partial — count + backend)
  2. `synthesis.concurrency` + `--concurrency` + validation/precedence, still sequential (FR3)
  3. Backend thread-safety: `ClaudeCLISynthesizer` usage lock + `BaseSynthesizer` contract (FR5 prerequisite)
  4. Parallel execution: pure `_synthesize_one` worker, executor + `as_completed` drain, write lock, `[k/N]` counter, Ctrl-C handling, start-line concurrency, existing-test sweep (FR2, FR4, FR1 complete)
  5. Docs: `docs/reference/cli.md`, `docs/configuration-reference.md`, `CHANGELOG.md` (FR6)
  6. Feature Testing & Regression (`testing-expert`)
- **Agents:** implementation/verify → `general-purpose` (no Python specialist in this session's roster; the repo's `.claude/rules/contributing.md` auto-loads on `llmwiki/`/`tests/`/`scripts/`/`docs/` edits, so conventions still reach it). QA slice → project-local `testing-expert`. Recorded in the tasks.md Recommendations table.
- **Note on Slice 1 → Slice 4:** `print_synth_run_start` takes an optional `concurrency` arg it does not render until Slice 4, so the intermediate state never prints a number it isn't honoring.
- **Next:** commit specs, then `/awos:implement`.
