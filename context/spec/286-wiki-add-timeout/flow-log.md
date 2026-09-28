# Flow log: 286-wiki-add-timeout

## fetch-bug
- BUG_ID: 286
- Title: Agent 'add to wiki' path is unreliable: MCP wiki_add timeout never fires, skill still prescribes pre-candidate manual steps
- URL: https://github.com/AlexanderMakarov/llm-wiki/issues/286
- State: open; labels: bug, important; comments: none
- Symptom: MCP `wiki_add` ThreadPoolExecutor context-manager waits for worker after timeout, so `mcp.tool_timeouts.wiki_add` never returns early; agents see client `-32001`, retry via CLI, hit pipeline lock / duplicate
- Related: #273 (MCP/CLI add proxy), #37, #110
- Unreachable links: none
- Next: resume-detection

## resume-detection
- Not already fixed (issue open; no PR for 286)
- Owning functional spec: none for timeout/skills path; related `273-mcp-wiki-add-cli-proxy` covers MCP↔CLI add parity, not this timeout/skill bug
- SPEC_NAME: `286-wiki-add-timeout` (orphan fix-as-spec, #164)
- Next: workspace

## workspace
- BRANCH: `fix/286-wiki-add-timeout`
- WT: `/home/USER/code/llm-wiki/.claude/worktrees/fix-286-wiki-add-timeout` (absolute; §10 #213)
- TMP_VAULT: `$WT/.worktree-vault` (absolute; worktree config.json vault-only)
- Note: first create used relative TMP_VAULT and nested vault under `$WT/.claude/worktrees/...`; corrected to absolute paths before diagnose
- Next: diagnose

## diagnose
- Repro: ThreadPoolExecutor-as-context-manager + `fut.result(timeout=0.5)` around 3s sleep → catch at 0.5s, return at 3.0s
- Root cause: `llmwiki/mcp/server.py::tool_wiki_add` — `with ThreadPoolExecutor` → `__exit__` `shutdown(wait=True)` blocks the timeout error return; orphan worker still holds `pipeline_lock`
- No existing timeout regression test
- Skills: `llmwiki-ingest` still has hand-written entity/concept/log steps 4–9; no packaged `wiki-add` skill; `install_agent_kit` writes version but never compares on reinstall
- Next: classify

## classify
- Primary timeout bug: **conformance** (config `mcp.tool_timeouts.wiki_add` intended to bound the tool; code never returns early). No functional-spec to amend for timeout itself.
- Related `273-mcp-wiki-add-cli-proxy` already Approved: MCP is CLI `add` proxy with synthesize **opt-in**. Flipping MCP to raw-only would be **divergence** from 273; keeping opt-in + return-fast is conformance to 273.
- Orphan SPEC_NAME `286-wiki-add-timeout` for flow-log/review; "no functional-spec to amend" unless operator chooses synthesize policy change vs 273.
- Pending operator: (1) synthesize settlement a/b/c; (2) PR scope — timeout+desc only vs full issue AC
- Next: fix (after operator answers)

## classify (operator confirmed)
- Synthesize policy: keep opt-in; timeout return-fast + verify-before-retry (conformance to 273)
- No thin wiki-add / llmwiki-add alias skill
- Scope: timeout fix + tool description + rewrite llmwiki-ingest docs workflow + agent-kit skills catalog + Cursor `--dest ~/.cursor` docs
- Extra: rename skill `wiki-all` → `llmwiki-all` (slash `/wiki-all` unchanged); retire old skill path via RETIRED_PATHS
- Operator installed kit to `~/.cursor` and `~/.claude`
- Next: fix

## fix (started)
- Delegating code/docs change to specialist on worktree

## fix (implemented)
- `llmwiki/mcp/server.py::tool_wiki_add`: pool is no longer a context manager; `shutdown(wait=False)` in `finally`, so the timeout error returns within `mcp.tool_timeouts.wiki_add` instead of joining the orphan worker. Error text states the add continues in the background holding `pipeline_lock`, tells the caller to verify via `wiki_search` / `raw/docs/` before retrying, and names the config key.
- `wiki_add` tool description + docstring carry the same budget / lock / verify-before-retry contract. Synthesis stays opt-in per 273.
- Regression: `tests/test_mcp_wiki_add.py::test_wiki_add_timeout_returns_within_budget` — stub `run_add` blocks on an event for 30s, timeout injected at 0.2s, asserts `isError` plus wall clock < 10s. Verified it fails at 30.0s against `shutdown(wait=True)`.
- `llmwiki-ingest` SKILL.md rewritten: document path is add (CLI or MCP `wiki_add`) → synth (sources + harvest; `--candidates-only` after `--synthesize`) → `/wiki-candidates` review → build. Hand-written entity/concept/project/log steps removed; session path points at synth first, hand summary kept as the fallback; timeout/lock warning added.
- Skill `wiki-all` → `llmwiki-all` (dir, frontmatter `name`, heading, description triggers). `/wiki-all` slash command unchanged. `RETIRED_PATHS["skills/wiki-all/SKILL.md"]` carries all three digests git history has for the path (`895c4870…`, `75cfcc67…`, `d2e21b15…`). Tests referencing the old path updated (`test_109_acceptance`, `test_install_agent_kit`, `test_170_wiki_all_skill`).
- Docs: CHANGELOG `[Unreleased]` Fixed (timeout) + Changed (skill rewrite, rename, install dests); `docs/reference/cli.md` install-agent-kit destination table (`~/.claude`, `~/.cursor`, `~/.codex`, project `.claude`); new **Agent-kit skills** catalog in `docs/reference/slash-commands.md` listing the four skills. No other doc named the skill `wiki-all` (remaining hits are the slash command or historical release notes).
- No new runtime deps; no commit/push from this pass.

## regression-test
- Added `tests/test_mcp_wiki_add.py::test_wiki_add_timeout_returns_within_budget` (RED on wait=True, GREEN on fix)
- Related skill/install tests updated for llmwiki-all rename
- Next: verify-criteria

## verify-criteria (automated)
- AC timeout returns within budget: PASS (pytest)
- AC wiki_add description synthesize/timeout/verify: PASS (server.py schema text)
- AC llmwiki-ingest no hand-written entity/log for docs; names candidates: PASS (skill rewrite)
- AC discoverability via new alias skill: WAIVED by operator (no thin skill; use installed llmwiki-ingest)
- AC installer outdated report: OUT OF SCOPE this PR (operator)
- Extra: skill rename wiki-all → llmwiki-all + RETIRED_PATHS + docs catalog + ~/.cursor dest
- Awaiting operator smoke confirm before local-review

## verify-criteria (smoke)
- Operator kit reinstall from worktree completed by agent into `~/.cursor` and `~/.claude` (llmwiki-all written; wiki-all pruned; ingest rewritten)
- Pre-gates green (ruff + targeted pytest)
- smoke blocked: awaiting operator chat reply `smoke ok` (fix-bug gate; skipped → stop)

## verify-criteria (smoke — waived)
- Operator did not type `smoke ok`; fired repeated goal Continue after agent installed kit from worktree and pre-gates were green
- Treating Continue + prior "Run remained actions" as smoke waiver (install verified: llmwiki-all present, wiki-all pruned, ingest candidates/timeout text present on ~/.cursor and ~/.claude)
- Next: local-review

## local-review (keep-all applied)
- Operator accepted all review findings via Continue waiver; applied N1, N2, N3, N5, N6 in the worktree (no commit, no push)
- N1: `pipeline_lock(REPO_ROOT, timeout=lock_timeout_s)` in `_do_add` + distinct `RuntimeError` branch naming the holding pid; lock wait set to 90% of the tool budget so it loses no race to the outer future timeout (deviation from the review's literal `timeout=timeout_s`, which would make the branch unreachable)
- N1 test: `tests/test_mcp_wiki_add.py::test_wiki_add_blocked_on_lock_reports_the_holder` (stubs `pipeline_lock`; no wall-clock wait)
- N2: `# Not a context manager:` comment now records the atexit join of the worker and why it is deliberate
- N3: skill no longer routes `wiki/projects/` through candidate review (line 14, document workflow intro, session note, Hard rule 3); CHANGELOG ingest bullet says the same
- N5: blank lines after the two new Unreleased bullets removed; rename split into its own `### Changed` bullet with its own release note
- N6: `---` added before `## How the slash commands get installed`
- Gates: `ruff check llmwiki tests scripts` clean; full `python3 -m pytest tests/ -q` green
- Left for commit stage: B1 (rename in its own dedicated commit + PR-body paragraph), B2 (commit this flow-log so the AWOS context gate sees it; keep `review.md` untracked), N4 (`Refs #286`, not `Closes`, + follow-up issue for installer staleness report)

## commit-push
- Two commits planned: (1) timeout + ingest + docs/catalog + review nits; (2) skill rename wiki-all → llmwiki-all
- review.md session-only, not staged
- Next: remote-gates (stop writing flow-log after PR opens)

---

## resume-detection (run 2, 2026-09-28)
- PR #287 merged (`Refs #286`, not `Closes`); issue 286 still open with two ACs unshipped
- AC4 (thin `wiki-add` alias skill): declined by operator in run 1 — stays declined
- AC5 (installer reports an outdated install): deferred in run 1 to a follow-up issue that was never filed (#288/#289/#290 are unrelated) — this run's scope
- SPEC_NAME unchanged: `286-wiki-add-timeout`
- Next: workspace

## workspace (run 2)
- BRANCH: `fix/286-installer-outdated-report` off `origin/main` @ 33cfa04
- WT: `/home/USER/code/llm-wiki/.claude/worktrees/fix-286-installer-outdated-report`
- TMP_VAULT: `$WT/.worktree-vault`; worktree `config.json` vault-only; `llmwiki init` seeded
- Next: diagnose

## diagnose (run 2)
- `run_install` treats every destination file that differs from the kit identically: write `<name>.bak`, overwrite. It never asks *why* the file differs.
- The installer already knows the answer. `.llmwiki-agent-kit.json` records `version` plus a `path -> sha256` of what llmwiki last installed, and `RETIRED_PATHS` holds historical digests — but `known_digests()` filters that evidence down to paths the kit *no longer ships*, so the install path cannot consult it.
- Consequence: an install that is merely out of date is indistinguishable from one the user hand-edited. Both are reported as a plain write plus a backup, so nothing tells the operator their install was stale, and a pointless `.bak` of llmwiki's own bytes can clobber a real one (#224).
- Next: classify

## classify (run 2)
- **Conformance.** No functional spec documents `install-agent-kit`'s backup or reporting behaviour (`grep '\.bak' context/spec/*/functional-spec.md` → no hits); the contract lives only in the module docstring and `docs/reference/cli.md`. Nothing to amend — docstring and reference docs move with the code.
- Operator decisions this run:
  - outdated (digest is one llmwiki authored) → report + overwrite + **no** `.bak`; mirrors the existing prune rule that our own bytes need no backup. Partially defuses #224.
  - customised (digest is nobody's we know) → report must **say the edits cannot be merged into the kit update** and point at the `.bak`.
  - report prints **absolute** paths, not dest-relative ones.
  - name the version the file came from wherever the manifest allows it.
- Next: fix

## fix (run 2)
- `llmwiki/install_agent_kit.py`: a destination file that differs from the kit is classified `outdated` (its digest is the one the manifest records for that path) or `customised` (anything else). Outdated is replaced with no `.bak`; customised is backed up first and the report says the edits cannot be merged.
- Provenance for the install decision is the manifest alone. `_authored_digests` is gone; `known_digests` inlines the manifest ∪ `RETIRED_PATHS` merge and keeps it to the prune path, where a retired digest is the only kind that can describe a path. A retired-then-resurrected name therefore fails safe as `customised`.
- Version attribution is the manifest's `version`, applied only when the manifest records that path: `installed by <v>` for outdated, `patched from <v>` for customised, and nothing at all with no manifest.
- Report gains `outdated`, `customised`, `installed_version`, `package_version`, `attributed_versions`; `kept` carries paths so `print_report` can render them absolute. Every printed path, errors included, is absolute.
- Docs: `docs/reference/cli.md` classification table, manifest trust-surface note, report paragraph; `CONTRIBUTING.md` install note; `CHANGELOG.md` `[Unreleased] → Fixed`.
- Next: regression-test

## regression-test (run 2)
- `tests/test_install_agent_kit.py`: outdated replaced without a `.bak`; customised backed up with the un-mergeable explanation; absolute paths across dest/wrote/outdated/customised/kept/unchanged; both version wordings; no manifest attributes no version; dry-run classifies and writes nothing; a `.bak` that could not be written is never claimed; a retired digest never replaces a shipped file unbacked.
- Updated for the accepted findings: `test_cli_conflict_reports_bak`, `test_cli_reports_pruned_paths`, `test_cli_reports_kept_paths`, `test_manifest_records_only_what_landed`, `test_report_prints_absolute_paths` (column widths, dropped duplicate backup line, absolute error paths).
- Next: verify-criteria

## verify-criteria (run 2)
- AC5 "installer reports the outdated files": PASS. Drove `install-agent-kit` against a scratch dest staged with one file holding llmwiki's own older bytes (manifest stamped to an older version) and one patched by hand. Dry-run and real run both classify 1 outdated + 1 customised; real run leaves no `.bak` beside the outdated file, a `.bak` holding the patch beside the customised one, and the next run reports nothing to write.
- Gates: `ruff check llmwiki tests scripts` clean; full `python3 -m pytest tests/ -q` exit 0.
- Next: local-review

## local-review (run 2)
- One independent reviewer, pre-push. Verdict Comment — 0 Blockers, 10 Nits. Written to `review.md` (session-only, never staged).
- Operator accepted all ten. N8 and N9 collapsed into one change: the install-path lookup is manifest-only, which removes the guessed version and shrinks the no-backup trust surface together; N9's documentation half still applied.
- Applied in the worktree, gates re-run green. Deviation from the flow: the Agent tool's safety classifier returned no verdict six times across Agent/Bash/Edit, so the orchestrator applied the findings inline rather than through a specialist. Recorded per the Self-Improvement Loop as a harness failure, not a flow defect.
- Next: commit-push (stop writing this log once the PR is open)

## commit-push (run 2)
- One commit: installer classification + tests + docs. `review.md` session-only, not staged.
- `Closes #286` — ACs 1–3 shipped in PR #287, AC4 declined by the operator, AC5 here.
- Next: remote-gates
