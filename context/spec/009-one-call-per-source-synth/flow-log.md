# Flow log — 009-one-call-per-source-synth (#147)

Memory of the `/implement-feature` run outside the context window. One entry per completed stage. Finalized at the commit-push stage — nothing is appended once the PR is open.

## fetch-ticket

- **Ticket:** GitHub Issue #147 — "Collapse synthesis to one model call per source: emit topics, kind, facts and description together" (`important`, state `OPEN`), https://github.com/AlexanderMakarov/llm-wiki/issues/147
- No comments. Related issues fetched: #103 (closed — promote Key Facts LLM), #145 (open — interrupt skips harvest + stale Home counts; **in scope**), #146 (open — discard reasons; out of scope), #148 (open — merge-stitched descriptions; out of scope), #149 (open — apply batch order; out of scope), #109 (closed — descriptions arrive here).
- Unreachable links: none.
- **Next:** resume-detection.

## resume-detection

- Issue OPEN; no `context/spec/*` directory for #147; no matching PR; no `feat/147-*` worktree. Nothing to resume — full chain from workspace.
- Primary checkout was `behind 1` with untracked `candidates.png` / `candidates-top.png` (not a blocker).
- **Next:** workspace.

## workspace

- **Branch:** `feat/147-one-call-synth` off `origin/main` @ `0f2b710`
- **Worktree:** `.claude/worktrees/feat-147-one-call-synth`
- **Throwaway vault:** `<WT>/.worktree-vault`, worktree `config.json` points at it; `llmwiki init` seeded it. `setup.sh` needed `chmod +x` (not executable in a fresh worktree). `LLMWIKI_SKIP_AUTOMATION=1 ./setup.sh`; pytest `-q` green.
- **Next:** specs.

## specs — functional spec

- **Artifact:** `context/spec/009-one-call-per-source-synth/functional-spec.md` (`SPEC_NAME=009-one-call-per-source-synth`)
- **Decisions taken with the user:**
  - Existing source summaries: **rewrite on the next synth** so the whole vault matches the new shape; afterwards skip when already up to date.
  - Known-names list: **once per run**, from disk at start. No mid-run waves and no “2 new stubs → rebuild”. Convergence is **Ctrl+C then restart** (or the next run).
  - Description refresh from fact-count threshold: **do not implement**.
  - `consolidate-topics`: **remove from the product** (not a CLI function-call wrapper). Skills must not tell the agent to run a leftover consolidate step.
  - #145 is **in scope** (harvest on interrupt; Home counts recover on the next site rebuild).
- Spec carries FR1–FR10.
- **Gate:** user approved ("approve"), 2026-08-15.
- **Amendment (2026-08-16):** FR5 / honest accounting updated after tech review — job 1 is one LLM ask per run to prepare known-names; not a free disk-only assembly.
- **Next:** `/awos:tech`.

## specs — technical considerations

- **Artifact:** `context/spec/009-one-call-per-source-synth/technical-considerations.md`
- **Design:** two LLM jobs per `synth` run — (1) `prepare_known_names` once at start (classifier + consolidate + “what is this name”), (2) source page per queued raw file with kind/facts/description on Connections bullets. Harvest/promote are parsers + move. Interrupt returns summary + harvest, exit 130; build refreshes stale `on_disk` (#145). `consolidate-topics` CLI retired (library remains for job 1).
- First draft wrongly treated this as adding a `## Topics` block beside Summary/Claims/Quotes/Connections; user corrected (Karpathy ingest + 4→2 prompts). Claims/Quotes left unchanged.
- **Gate:** user approved ("lgtm"), 2026-08-16.
- **Next:** `/awos:tasks`.

## specs — tasks

- **Artifact:** `context/spec/009-one-call-per-source-synth/tasks.md`
- Eight slices: parser → harvest offline → promote offline → job 1 + retire CLI → job 2 + FR2 rewrite → interrupt/#145 → docs → Feature Testing & Regression (`testing-expert`). Implementation tasks: `general-purpose` (no Python specialist hired).
- Draft Approve ask suppressed per delivery-flow Local Customization.
- **Next:** commit-specs.
