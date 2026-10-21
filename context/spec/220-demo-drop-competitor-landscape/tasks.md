# Tasks: Refresh competitor landscape docs + demo sync

- **Spec:** `context/spec/220-demo-drop-competitor-landscape/`
- **Issue:** #220
- **Tests:** No new test whose only job is to lock prose (approved technical spec). Each slice is verified by reading the page and, for the demo slice, `lint` on `demo/`. The regression slice runs the existing suite.

---

- [x] **Slice 1: Reader sees a current function comparison**

  - [x] Rewrite `docs/competitor-landscape.md` in the worktree. Columns: this project, agentmemory, mem0, TencentDB Agent Memory. Rows in order: Output for agents, Context impact, Output for humans, Agent coverage, KB sources, KB layers, Query features, Automation cadence, Resources usage, Tokens cost, Observability. lucasastorian/llmwiki and the Obsidian plugin stay under the table. Remove Rewind, Pieces, and the manual-notes column. TencentDB agent coverage is the 9 named clients in its install guide, including Claude Code. **[Agent: general-purpose]**
  - [x] In `docs/getting-started.md`, change the sync comment so the path is flat `<vault>/raw/sessions/*.md`, not `<vault>/raw/sessions/<project>/*.md`. Do not edit the later “6 agents” aside. Do not edit `docs/i18n/`. **[Agent: general-purpose]**
  - [x] Add or update one `CHANGELOG.md` `[Unreleased]` bullet: competitor landscape comparison refreshed; getting-started sync path hint is flat. If an Unreleased entry already describes this page, edit that entry instead of adding a second one. **[Agent: general-purpose]**
  - [x] Verify: read `docs/competitor-landscape.md` and confirm the eleven function rows, the four memory-tool columns, the lookalikes under the table, and the absence of Rewind, Pieces, and a manual-notes column. Read the getting-started sync line. **[Agent: general-purpose]**

- [x] **Slice 2: Example vault matches the updated page**

  - [x] In the worktree, merge `synthesis` (and any other non-vault keys) from the primary checkout’s gitignored `config.json` into the worktree `config.json`. Leave `vault.default_path` pointing at `$WT/.worktree-vault`. Do not copy the primary vault path. **[Agent: general-purpose]**
  - [x] From the worktree, run `python3 scripts/refresh_demo.py --dry-run` and confirm the plan is remove-then-add for `docs/competitor-landscape.md`. Then run `python3 scripts/refresh_demo.py` so `demo/` is regenerated for that doc only. Do not hand-edit `demo/raw/`. Do not write the live Obsidian vault. If synth is interrupted, finish with `--resume`. **[Agent: general-purpose]**
  - [x] Verify: `python3 -m llmwiki lint --vault demo` reports no new broken links or orphans from this refresh. Spot-read one regenerated competitor raw part and confirm it describes the new function grid, not Rewind or Pieces. Delete any scratch output from the check. **[Agent: general-purpose]**

- [x] **Slice 3: Feature Testing & Regression**

  > Verifies the whole feature end-to-end against functional-spec.md, run after all implementation slices are complete. No new prose-only test file — the approved technical spec forbids one.
  - [x] Read functional-spec.md acceptance criteria in full. Confirm each criterion against the worktree docs and `demo/` (function grid, under-table notes, stale tools absent, flat sync path, demo lint). Run `python3 -m pytest tests/test_refresh_demo.py -q` and `ruff check llmwiki tests scripts`. Do not add a new test module. **[Agent: testing-expert]**
  - [x] Run `python3 -m pytest tests/ -q`. All must pass. Fix any failures caused by this change before proceeding. **[Agent: testing-expert]**
