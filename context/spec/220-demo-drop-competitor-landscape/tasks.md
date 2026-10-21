# Tasks: Refresh competitor landscape docs + demo sync

- **Spec:** `context/spec/220-demo-drop-competitor-landscape/`
- **Issue:** #220
- **Tests:** No new test whose only job is to lock prose (approved technical spec). Each slice is verified by reading the page and, for the demo slice, `lint` on `demo/`. The regression slice runs the existing suite.

---

- [ ] **Slice 1: Reader sees a current function comparison**

  - [ ] Rewrite `docs/competitor-landscape.md` in the worktree. Keep our own facts current (11 agents from the README table, Python 3.12+, `markdown` as the only runtime dependency, page kinds without retired comparison/question kinds). Replace the comparison table with the seven function rows and three columns from `technical-considerations.md` (this project, llmwiki (lucasastorian), Karpathy LLM Wiki (Obsidian)). Column heading for the other llmwiki includes the author so the two columns are distinct; cells compare functions. After the table, one short “when to choose which” paragraph for those three. Under that, one functional paragraph and link each for mem0, agentmemory, and TencentDB Agent Memory. Remove Rewind, Limitless, Pieces, and the manual-notes column. One sentence under “when llmwiki is not the right tool” may still cover writing notes by hand when there are few sessions. Do not copy star counts or benchmark claims. **[Agent: general-purpose]**
  - [ ] In `docs/getting-started.md`, change the sync comment so the path is flat `<vault>/raw/sessions/*.md`, not `<vault>/raw/sessions/<project>/*.md`. Do not edit the later “6 agents” aside. Do not edit `docs/i18n/`. **[Agent: general-purpose]**
  - [ ] Add or update one `CHANGELOG.md` `[Unreleased]` bullet: competitor landscape comparison refreshed; getting-started sync path hint is flat. If an Unreleased entry already describes this page, edit that entry instead of adding a second one. **[Agent: general-purpose]**
  - [ ] Verify: read `docs/competitor-landscape.md` and confirm the seven function rows, the three columns, the three under-table paragraphs, and the absence of Rewind, Pieces, and a manual-notes column. Read the getting-started sync line. Delete any scratch notes created for the check. **[Agent: general-purpose]**

- [ ] **Slice 2: Example vault matches the updated page**

  - [ ] In the worktree, merge `synthesis` (and any other non-vault keys) from the primary checkout’s gitignored `config.json` into the worktree `config.json`. Leave `vault.default_path` pointing at `$WT/.worktree-vault`. Do not copy the primary vault path. **[Agent: general-purpose]**
  - [ ] From the worktree, run `python3 scripts/refresh_demo.py --dry-run` and confirm the plan is remove-then-add for `docs/competitor-landscape.md`. Then run `python3 scripts/refresh_demo.py` so `demo/` is regenerated for that doc only. Do not hand-edit `demo/raw/`. Do not write the live Obsidian vault. If synth is interrupted, finish with `--resume`. **[Agent: general-purpose]**
  - [ ] Verify: `python3 -m llmwiki lint --vault demo` reports no new broken links or orphans from this refresh. Spot-read one regenerated competitor raw part and confirm it describes the new function grid, not Rewind or Pieces. Delete any scratch output from the check. **[Agent: general-purpose]**

- [ ] **Slice 3: Feature Testing & Regression**

  > Verifies the whole feature end-to-end against functional-spec.md, run after all implementation slices are complete. No new prose-only test file — the approved technical spec forbids one.
  - [ ] Read functional-spec.md acceptance criteria in full. Confirm each criterion against the worktree docs and `demo/` (function grid, under-table notes, stale tools absent, flat sync path, demo lint). Run `python3 -m pytest tests/test_refresh_demo.py -q` and `ruff check llmwiki tests scripts`. Do not add a new test module. **[Agent: testing-expert]**
  - [ ] Run `python3 -m pytest tests/ -q`. All must pass. Fix any failures caused by this change before proceeding. **[Agent: testing-expert]**
