# Tasks: Make the product explain itself (#109)

- **Spec:** [`functional-spec.md`](./functional-spec.md) · [`technical-considerations.md`](./technical-considerations.md)
- **Branch chain:** `feat/109-explain-the-product` — three PRs, one per stage. Slices never straddle a stage.

> **Deviation from the tech spec's stage table, taken deliberately:** `pages.yml` is repointed in **Stage A**, not Stage B. Moving the demo without repointing the publish workflow in the same PR would leave the public site broken between two merges. Stage B still owns the workflow *simplification* and the `wiki-checks.yml` repair.

> **Vault rule for every task:** mutating `llmwiki` commands target `--vault .worktree-vault` or a pytest `tmp_path`. Never the operator's live vault. Read-only probes against the live vault are allowed.

> **Gates after every slice:** `ruff check llmwiki tests scripts` and `python3 -m pytest tests/ -q`.

---

## Stage A — PR A: repository shape, page body, page kinds

- [x] **Slice 1: The demo lives in `demo/`, and publication still works**

  - [x] Move the demo into one self-contained tree using `git mv` so history is preserved: `wiki/` → `demo/wiki/`; `examples/demo-sessions/` → `demo/raw/sessions/`; `examples/demo-docs/` → `demo/raw/docs/`; `examples/demo-wiki/sources/` → `demo/wiki/sources/`; `examples/demo-usage/` → `demo/usage/`. Leave `examples/obsidian-templates/`, `examples/scripts/`, `examples/sessions_config.json` and `examples/wiki_dashboard.md` where they are — they are not demo corpus. **[Agent: general-purpose]**
  - [x] Add `demo/site/` to `.gitignore`. The built demo site is a CI artefact, never committed. **[Agent: general-purpose]**
  - [x] Repoint `.github/workflows/pages.yml`: delete the `init` step and the whole `Seed demo corpus` block, replace the build step with `python -m llmwiki build --vault demo --out ./site`. Keep `.nojekyll`, upload and deploy untouched. **[Agent: general-purpose]**
  - [x] Update `.github/workflows/wiki-checks.yml` path filters so they reference `demo/**` instead of `wiki/**` and `examples/**`. Minimal edit only — the full repair is Slice 10. **[Agent: general-purpose]**
  - [x] Grep the repository for references to the moved paths (`examples/demo-`, `specs/`, root `wiki/`) in docs, workflows, scripts and tests, and update them. **[Agent: general-purpose]**
  - [x] Verify: run `python3 -m llmwiki build --vault demo --out /tmp/demo-site-check` and confirm it produces a site with a non-empty home page; run `ruff check llmwiki tests scripts` and `python3 -m pytest tests/ -q`. Delete `/tmp/demo-site-check` when done. **[Agent: general-purpose]**

- [x] **Slice 2: The repository root can no longer be used as a vault**

  - [x] Add a repository marker file at the repo root identifying this checkout as the llmwiki source tree, and a shared helper that detects it. **[Agent: general-purpose]**
  - [x] Make `cmd_init` (`llmwiki/cli.py:192`) and the other vault-resolving entry points refuse to scaffold, synthesise or build into a directory carrying the marker when no `--vault` is given. The error must name `--vault` and point at `demo/`. An installed package has no marker, so real users are unaffected. **[Agent: general-purpose]**
  - [x] Add unit tests: refuses inside a marked directory; proceeds normally without the marker; `--vault` always wins. **[Agent: general-purpose]**
  - [x] Verify: confirm bare `python3 -m llmwiki init` in the worktree root now errors with the guidance message and creates nothing, while `python3 -m llmwiki init --vault .worktree-vault` still succeeds. Run both gates. **[Agent: general-purpose]**

- [x] **Slice 3: Dead and misplaced assets removed**

  - [x] `git rm -r docs/videos/` (4 tracked files: `cli-tutorial.gif`, `cli-tutorial.mp4`, `cli-tutorial.tape`, `demo.mp4`). **[Agent: general-purpose]**
  - [x] `git mv specs/` → `docs/maintainers/surfaces/` (10 files) and fix every inbound link to them. **[Agent: general-purpose]**
  - [x] Check whether `scripts/record_demo.py`, `scripts/demo-record.sh` and `scripts/regen_docs_screenshots.py` referenced the deleted videos; update or remove whatever is now dangling. **[Agent: general-purpose]**
  - [x] Verify: grep the repository for `docs/videos` and bare `specs/` references and confirm none remain; run both gates. **[Agent: general-purpose]**

- [x] **Slice 4: Agent instructions stop describing a page shape the pipeline cannot produce**

  - [x] Remove the `One-paragraph description.` line from the "Entity / Concept / Project Page Format" block in `CLAUDE.md`, and the equivalent `One paragraph.` line in `AGENTS.md`. Both currently instruct agents to write an introductory paragraph that no code path produces. **[Agent: general-purpose]**
  - [x] File a follow-up GitHub issue proposing a description-generating synth step (functional-spec R6), and record its number in `functional-spec.md` next to the R6 criterion. **[Agent: general-purpose]**
  - [x] Verify: grep both files to confirm no remaining instruction to write a description paragraph on entity/concept/project pages. **[Agent: general-purpose]**

- [x] **Slice 5: `question` and `comparison` are gone from the vocabulary**

  - [x] **Spike, do this first — it sizes the next slice.** Determine whether `[[wikilink]]` resolution is name-based or path-based, by reading the resolver and proving it with a test that moves a page between folders and asserts inbound links still resolve. Record the finding in `technical-considerations.md` under the corresponding risk row. If resolution turns out to be **path-based**, Slice 6's migration must also rewrite inbound links — say so explicitly in the finding. **[Agent: general-purpose]**
  - [x] Remove `"comparison"` and `"question"` from `PAGE_KINDS` in `llmwiki/schema.py:50-58`. This is the single vocabulary source; `lint/rules/frontmatter_validity.py:19` and the MCP tool schema both follow from it. **[Agent: general-purpose]**
  - [x] Clear the remaining call sites: `topics.py:193-194`, `topics_page.py:44`, `graph.py:44-45,347-372,594`, `render/graph_viewer.py:34-46`, `graphify_bridge.py:409`, `obsidian_output.py:40` (`EXPORTED_DIRS`), `exporters.py:446-447`, `docs_pages.py:645`, `categories.py:50`, `reindex.py:26` (docstring), `lint/rules/duplicate_detection.py`, `mcp/server.py`, `usage.py`. **[Agent: general-purpose]**
  - [x] Delete the tracked `demo/wiki/comparisons/_context.md` (moved from `wiki/` in Slice 1) and any now-empty demo folder for the removed kinds. **[Agent: general-purpose]**
  - [x] **Regression pin:** add a test asserting the auto-generated *model* comparison index still renders — `llmwiki/compare.py` and `build.py:2501-2509` are a different feature that shares the word and must survive. **[Agent: general-purpose]**
  - [x] Add tests: the two removed kinds are rejected by frontmatter validation; every surviving kind is still accepted; the MCP tool schema no longer advertises them; the graph legend and viewer no longer offer them. **[Agent: general-purpose]**
  - [x] Verify: run both gates, plus `python3 -m llmwiki build --vault demo --out /tmp/demo-kinds-check` and confirm the model comparison page is still present in the output. Delete `/tmp/demo-kinds-check` when done. **[Agent: general-purpose]**

- [x] **Slice 6: Existing vaults can migrate off the removed kinds**

  - [x] Add a `migrate-page-kinds` subcommand following the existing `migrate-*` convention. For each page with `type: question` or `type: comparison`: rewrite the type to `concept` and relocate it into `wiki/concepts/`, keeping the filename. Delete the two `_context.md` files. Remove the folders once empty. Leave a non-empty folder in place and report it — never delete unrecognised content. Support `--dry-run` and `--vault`, append a `## [YYYY-MM-DD] migrate | page kinds` entry to `wiki/log.md`, and print a per-file report. **[Agent: general-purpose]**
  - [x] If the Slice 5 spike found path-based wikilink resolution, extend the migration to rewrite inbound links to every moved page. If name-based, add a test proving links survive the move unchanged. **[Agent: general-purpose]**
  - [x] Add unit tests covering: retype and relocate; `_context.md` cleanup; empty-folder pruning; non-empty folder left intact and reported; `--dry-run` writes nothing; a vault with none of these pages is a clean no-op. **[Agent: general-purpose]**
  - [x] Append two dated entries to `docs/maintainers/DECLINED.md` — one for open questions, one for comparisons — matching the existing entry format, each with a one-line reason and a `#109` context reference. **[Agent: general-purpose]**
  - [x] Document the migration in `docs/UPGRADING.md` and add a `CHANGELOG.md` entry, so a user whose pages carry a removed type is told which command to run. **[Agent: general-purpose]**
  - [x] Verify: build a temporary vault under `tmp_path` containing one page of each removed kind plus both `_context.md` files, run the migration, and confirm pages are retyped, relocated, links still resolve, folders pruned, and a follow-up `lint` reports no error about invalid types. **[Agent: general-purpose]**

---

## Stage B — PR B: the demo is real, checked, and published

- [x] **Slice 7: Changed documents can be identified from git**

  - [x] Implement the change-selection logic in `scripts/refresh_demo.py` as a pure function taking git's `diff --name-status` and `status --porcelain` output and returning an ordered action plan of `(action, path, slug)`. No file or vault access inside it. **[Agent: general-purpose]**
  - [x] Map git statuses to actions: `A` → add; `M` and `R` → remove-then-add; `D` → remove. Uncommitted working-tree edits from `status` are merged with committed changes from `diff`, de-duplicated by path. **[Agent: general-purpose]**
  - [x] Add unit tests over the pure function: added, modified, deleted, renamed, unchanged, an uncommitted edit, a file both committed and then further edited, and a no-change run producing an empty plan. Assert the remove-then-add ordering explicitly for the modified case. **[Agent: general-purpose]**
  - [x] Verify: run the new tests plus both gates. **[Agent: general-purpose]**

- [x] **Slice 8: One command refreshes the demo**

  - [x] Complete `scripts/refresh_demo.py`: read the base revision from `demo/.demo-source-rev`, collect git output, build the plan, then drive the existing CLI per action — `llmwiki add <path> --vault demo --no-build` and `llmwiki remove <slug> --vault demo --yes`. Then once per run: `synth --vault demo --docs-only` → `build --vault demo --out demo/site` → `lint --vault demo`. Finally write `HEAD` into `demo/.demo-source-rev`. **[Agent: general-purpose]**
  - [x] Add a code comment at the remove-then-add site explaining why the ordering is mandatory: re-adding an ingested document lands a second snapshot under a drifted slug and leaves the original, breaking inbound links. **[Agent: general-purpose]**
  - [x] Add a `llmwiki synth --check` preflight that fails early with an actionable message when no synth backend is reachable, rather than part-way through a run. **[Agent: general-purpose]**
  - [x] Add flags: `--dry-run` (print the plan, touch nothing), `--force` (treat every `docs/` file as changed), `--base <rev>` (override the recorded revision). Print the full lint report at the end of every run — under an errors-only CI gate this is the maintainer's only sight of warning-severity defects. **[Agent: general-purpose]**
  - [x] Document the command in `docs/maintainers/`: what it does, that it requires a working synth backend and a git working copy, that it cannot run from a release archive, and that it is local-only and never runs in CI. **[Agent: general-purpose]**
  - [x] File a follow-up GitHub issue for the product-level gap — llmwiki cannot update an already-ingested document in place (functional-spec R3) — and record its number next to the R3 criterion. **[Agent: general-purpose]**
  - [x] Verify: build a temporary git fixture with a seeded `docs/` tree and a scratch vault, then exercise `--dry-run` for added / modified / deleted / renamed / no-change and confirm the printed plan matches expectations and nothing is written. Delete the fixture afterwards. **[Agent: general-purpose]**

- [ ] **Slice 9: The demo content is genuine pipeline output about llmwiki**

  > **Deferred 2026-08-15.** Operator chose not to run a full demo `synth` for this PR. The committed `demo/raw/` corpus (product docs + authored sessions) stays; untracked partial `demo/wiki/sources|candidates|entities` are local leftovers and must not be committed. `demo/.demo-source-rev` is not created. Revisit when someone runs `scripts/refresh_demo.py` locally.

  - [x] Curate `demo/raw/docs/` so the demo corpus covers llmwiki's own subject matter — its commands, its static site, and how it reads agent sessions — sourced from the project's real `docs/`. Remove the inherited fictional projects (blog engine, to-do API, ML pipeline) and their pre-synthesized source pages. **[Agent: general-purpose]**
  - [ ] Run `python3 -m llmwiki synth --check` first. **If no backend is reachable, stop and report to the user** — this task needs a real AI backend and must not be faked, stubbed, or hand-written. That is the entire point of the requirement. **[Agent: general-purpose]**
  - [ ] Regenerate the demo by running `scripts/refresh_demo.py`, and commit the produced `demo/raw/` and `demo/wiki/` content together with `demo/.demo-source-rev`. **[Agent: general-purpose]**
  - [ ] Verify: confirm no page under `demo/wiki/entities/`, `demo/wiki/concepts/` or `demo/wiki/projects/` opens with a prose description paragraph, that every knowledge page body is attributed fact bullets, and that each bullet carries a source link. Confirm `llmwiki lint --vault demo --fail-on-errors` exits zero. **[Agent: general-purpose]**

- [x] **Slice 10: CI proves the demo is clean**

  - [x] Repair `.github/workflows/wiki-checks.yml`: change the push trigger from `master` to `main` (it currently never fires); delete the `python -m llmwiki eval` step, which invokes a subcommand that does not exist and is masked by `|| true`; drop the seeding block; run `python -m llmwiki build --vault demo --out demo/site` then `python -m llmwiki lint --vault demo --fail-on-errors`. **[Agent: general-purpose]**
  - [x] Do not add `--strict` and do not modify anything under `llmwiki/lint/`. Errors fail the build; warnings are printed and tolerated. Add a comment in the workflow recording why, so a future reader does not "fix" it: `content_freshness` fires on any committed demo once 90 days pass and would redden CI on a timer. **[Agent: general-purpose]**
  - [x] Add a test pinning the amended R4 boundary: `lint --vault <tmp> --fail-on-errors` exits non-zero on a seeded error and zero on a vault carrying only warnings — so reintroducing `--strict` later is a deliberate act, not an accident. **[Agent: general-purpose]**
  - [x] File a follow-up GitHub issue proposing per-vault lint rule scoping so the demo can enforce warnings once `content_freshness` can be excluded (amended R4), and record its number next to the R4 criterion. **[Agent: general-purpose]**
  - [x] Verify: run both gates, and confirm the built demo site opens and the lint command exits zero against `demo/`. **[Agent: general-purpose]** *(lint against the committed scaffold; a full-wiki lint-clean demo waits on Slice 9)*

---

## Stage C — PR C: static site, then the product explains itself

- [x] **Slice 11: The wiki is a static site — nothing serves it**

  - [x] Delete `llmwiki/serve.py` and its `serve` subcommand wiring in `llmwiki/cli.py`. Delete `serve.sh` and `serve.bat`. **[Agent: general-purpose]**
  - [x] Rework the built candidates page so it reviews without a backend. Keep the review interaction — a row per candidate showing **Name**, **Description** and a **Decision** control covering every action `candidates apply` executes, plus an **Apply** button — because deciding is state held in the page and only executing was ever the server's job. A row starts with **no decision**, so applying without deciding yields an empty batch rather than one that promotes everything. Apply assembles the decided rows into the command plus its `--actions` JSON, naming the vault, placed where a reviewer finds it without scrolling past the tables. **[Agent: general-purpose]**
  - [x] **Remove every remaining thing that serves the site.** `playwright.config.ts` (`baseURL` + `webServer`), `tests/e2e/conftest.py` (`ThreadingHTTPServer`, `_serve_dir`, the `base_url` fixture), the tests that consume it (`test_navigation_404.py`, `test_build_artifacts.py`), `.github/workflows/agents-e2e.yml` (which currently starts `python3 -m http.server`), `.github/workflows/synthetic.yml`, `.claude/launch.json`, and the screenshot scripts `scripts/record_demo.py` and `scripts/regen_docs_screenshots.py`. Leave `llmwiki/synth/ollama.py` and its test alone — that is a model backend, not a served site — and leave the vendored `.cursor/skills/**` tests alone. **[Agent: general-purpose]**
  - [x] **Convert the browser tests to open the built files directly.** Replace the `base_url` fixture with one returning the built site's path, and navigate file URLs. Chromium under Playwright navigates `file://` — an earlier claim that it blocks the scheme is wrong. Any test that depends on server behaviour (directory indexes, same-origin requests) is either reworked or removed with a stated reason. **[Agent: general-purpose]**
  - [x] Add a test that walks the surfaces a reader uses — home, a project, a session, a topic page, search, the graph, candidates — opened as files, failing on a console error or a resource that fails to load. This is the check that would have caught the site being verified over a transport it no longer uses. **[Agent: general-purpose]**
  - [x] Vendor the code-highlighting assets so the site needs no network: pinned `highlight.min.js`, `github.min.css` and `github-dark.min.css` (11.9.0) under `llmwiki/vendor/`, emitted beside the pages that use them and referenced relatively, following the pattern `graph.py` uses for vis-network. Extend `llmwiki/vendor/NOTICE` with a matching entry. **[Agent: general-purpose]**
  - [x] Add `vendor/*.css` to `package-data` in `pyproject.toml` — it lists `vendor/*.js` only, so the themes would ship in a source checkout but be silently missing from a pip or Homebrew install. Assert it in the distribution-content test. **[Agent: general-purpose]**
  - [x] Add a `--local-root` input to `build` that supplies the value shown in place of a stored home directory: resolved from the current run by default, overridden by the flag. Remove `restore_local_path` from the build path along with its dependence on convert-time redaction config, and restrict substitution to the `cwd` field — it currently also rewrites session descriptions, editing arbitrary prose. **[Agent: general-purpose]**
  - [x] Pass an explicit fixed string from the demo build and from `pages.yml`, so published pages never show whoever ran the build. Test that two builds under different environments are identical when the flag is given. **[Agent: general-purpose]**
  - [x] Sweep every instruction telling a reader to start a server to view their wiki — README, `docs/**`, `CLAUDE.md`, `AGENTS.md`, `docs/deploy/*`, the `/wiki-serve` slash command and the `wiki-serve` skill — and replace it with opening the built site. Delete the serve command and skill outright. **[Agent: general-purpose]**
  - [x] Record the removal in `CHANGELOG.md` and `docs/UPGRADING.md`, telling anyone who ran the server what to do instead, and describe the candidates page's behaviour in `docs/reference/ui.md`. **[Agent: general-purpose]**
  - [x] Add tests: `serve` is no longer a subcommand; the built page contains no `fetch`, no `XMLHttpRequest` and no endpoint reference; the Decision controls and Apply exist; a row with no decision is excluded from the batch; the generated batch is valid and shaped as `candidates apply` parses it; the CLI review path still performs promote / discard / merge end to end on a `tmp_path` vault. **[Agent: general-purpose]**
  - [x] Verify: build the demo, open it as files, and confirm every surface works with nothing running. Assert the built site references no `https://` script or stylesheet beyond the accepted web-font link. Delete any temp build afterwards. **[Agent: general-purpose]**

- [x] **Slice 12: A reference explains every page kind and where each field comes from**

  - [x] Write `docs/reference/page-kinds.md` covering every surviving kind — `source`, `entity`, `concept`, `project`, `synthesis`, plus the system kinds `navigation` and `context`. For each: what it is for, and a real example linked into the rebuilt demo. **[Agent: general-purpose]**
  - [x] For every frontmatter field on every kind, give a provenance value of **synth**, **harvest**, **build**, or **human**. Derive these from the code, not from assumption. **[Agent: general-purpose]**
  - [x] List conventionally-absent fields explicitly with the reason, including that `ensure_project_stubs()` (`llmwiki/build.py:340`) writes project stubs with no `last_updated`, so project freshness derives from sessions. **[Agent: general-purpose]**
  - [x] State plainly that saved answers are written by an agent or a person and are never generated automatically. **[Agent: general-purpose]**
  - [x] Verify only — do not rewrite — that `docs/reference/ui.md` already carries a complete `## Topic pages` section from #108 / PR #128. Link the new page from `docs/index.md`. **[Agent: general-purpose]**
  - [x] Verify: confirm every example in the new page resolves to a file that exists in the rebuilt demo, and that every field named in the code appears in the tables. **[Agent: general-purpose]**

- [x] **Slice 13: A packaged install carries the agent commands**

  - [x] Create `llmwiki/agent_kit/{commands,skills}/` and move the user-facing material into it: the `wiki-*.md` slash commands, and the `llmwiki-sync`, `llmwiki-ingest`, `llmwiki-query`, `wiki-all`, `wiki-add` skills. Leave contributor material in `.claude/` — `awos/`, `fix-bug.md`, `implement-feature.md`, `maintainer.md`, `release.md`, `triage-issue.md`, and the `docs-that-work`, `gha-diagnosis`, `modern-python-development`, `project-maintainer`, `pytest-best-practices`, `self-learn` skills. **[Agent: general-purpose]** *(wiki-add was not in this worktree — skipped)*
  - [x] Strip any reference to repository-only paths from the moved user-facing files — they will run from a user's own project. **[Agent: general-purpose]**
  - [x] Extend `package-data` for `llmwiki` in `pyproject.toml:108-109` to include `agent_kit/**/*.md` and any non-markdown skill assets. **[Agent: general-purpose]**
  - [x] Add an `install-agent-kit` subcommand with a **required** `--dest PATH` — no auto-detection. Copy `commands/` and `skills/` beneath the destination, report every path written, write a `.bak` beside any conflicting file whose content differs and report it, treat an identical file as a no-op, and support `--dry-run`. **[Agent: general-purpose]**
  - [x] Delete `.claude-plugin/` (`plugin.json`, `marketplace.json`). It declares `path: "."` with `commands/wiki-init.md`, resolving to a directory that does not exist; names the upstream author; and claims `python >=3.9` against an actual floor of 3.12. It cannot work, so nothing can depend on it. **[Agent: general-purpose]**
  - [x] Add tests: writes to `--dest`; missing `--dest` errors; conflicting file produces a `.bak` and a report; identical file is a no-op; `--dry-run` writes nothing. **[Agent: general-purpose]**
  - [x] **Add the test that actually proves the Homebrew fix:** build a distribution and assert it contains `llmwiki/agent_kit/commands/*.md` and the skill files. Inspecting `pyproject.toml` by eye would not catch a packaging mistake. **[Agent: general-purpose]**
  - [x] Verify: build a distribution, install it into a throwaway virtualenv, run `install-agent-kit --dest <tmp>` from outside the repository, and confirm the commands and skills land. Delete the virtualenv and temporary destination afterwards. **[Agent: general-purpose]**

- [x] **Slice 14: The README is a product page**

  - [x] Rewrite `README.md` in this order: what you get → live demo link → install → the loop (`sync / add → synth → review candidates → build`, with candidate review described as a real human gate) → one merged agent table → configuration pointer → docs index → acknowledgements → license. Target roughly half of today's 364 lines. **[Agent: general-purpose]**
  - [x] Build one agent table with a row per agent and columns *Supplies sessions* / *Reads the wiki* / *Core or contrib*. Ground truth: core is `claude_code` and `codex_cli`; contrib is `chatgpt`, `copilot_chat`, `copilot_cli`, `cursor`, `cursor_cli`, `gemini_cli`, `obsidian`, `opencode`, `openclaw`. Today's README wrongly lists four contrib adapters as core and omits `chatgpt` and `opencode` entirely. **[Agent: general-purpose]**
  - [x] Correct the Python version against `pyproject.toml:10` (`>=3.12`) and the CI matrix (3.12, 3.13). **[Agent: general-purpose]**
  - [x] Remove the fork/lineage paragraph from the top; attribution stays only under Acknowledgements and License. **[Agent: general-purpose]**
  - [x] Move displaced detail into real pages under `docs/`: `Manual queue`, the per-path gitignore table (reduced to one sentence in the README), and the tutorial content that duplicates the quickstart, How it works and CLI reference. Every fact appears once. **[Agent: general-purpose]**
  - [x] Re-scope `CLAUDE.md` and `AGENTS.md` to contributors: state plainly they are for people working on llmwiki itself, and point users at `install-agent-kit`. Note `context/` as contributor tooling in `CONTRIBUTING.md`. **[Agent: general-purpose]**
  - [x] Retarget `homebrew/llmwiki.rb` at `AlexanderMakarov/llm-wiki` with branch `main`, replacing the stale upstream `Pratiyush` URL and `master` reference. **[Agent: general-purpose]**
  - [x] Verify: confirm every link in the README and in changed docs resolves; assert structurally that exactly one agent table exists, the Python version is correct, and no lineage paragraph appears above Acknowledgements. **[Agent: general-purpose]**

- [x] **Slice 15: Feature Testing & Regression**

  > Verifies the whole feature end-to-end against functional-spec.md, run after all implementation slices are complete. Slice 9 wiki regeneration is deferred; acceptance tests cover the committed corpus, packaging, docs and CI shape.
  - [x] Read functional-spec.md acceptance criteria in full. Generate acceptance-level tests that verify the entire feature as a whole — not individual slices. Cover applicable layers (unit for pure logic, integration for service interactions, e2e for user flows) based on the project's testing stack. Write tests with RED validation (must fail before implementation is confirmed done). Annotate each test with `@spec: 008-make-product-explain-itself` and `@regression` if suitable for long-term regression. Place them in `tests/test_109_acceptance.py` per the project's `test_<issue>_acceptance.py` convention. **[Agent: testing-expert]**
  - [x] Run all generated tests. All must pass. Fix any failures before proceeding. **[Agent: testing-expert]**

---

## Criteria not automated

These functional-spec criteria are editorial and are confirmed at the user smoke-confirm step rather than by a test: the README leads with the benefit; no fact is stated twice; a newcomer can tell which folder is the demo from the top-level listing; the demo "reads as" genuine output. Structural README criteria that *are* checkable are asserted in Slice 14.

## Recommendations

| Task/Slice | Issue | Recommendation |
| --- | --- | --- |
| All implementation slices | Assigned to `general-purpose` — no Python/CLI specialist is registered (`context/product/hired-agents.md` lists only `testing-expert`) | Run `/awos:hire` if a Python CLI agent becomes available; the gap is already recorded in the hired-agents report |
| Slice 13 | Packaging and distribution work with no packaging specialist | Same as above; the distribution-content test is the compensating control |
| Slice 9 | Demo regeneration needs a reachable AI synth backend; the worktree is configured with the `dummy` backend | Configure a real backend before this slice, or the task will correctly stop and escalate |
| Slice 10 | Errors-only CI gate leaves `link_integrity`, `stub_source_pages` and `duplicate_detection` unenforced | Accepted by user directive (lint out of scope); follow-up issue [#150](https://github.com/AlexanderMakarov/llm-wiki/issues/150) |
| Slice 11 | Removing `serve` deletes the #97 review UI's backend | Not lossy: `candidates apply --actions` accepts the identical batch shape. The candidates page states the replacement command and emits copy-ready JSON |
