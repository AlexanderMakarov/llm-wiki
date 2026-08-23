# Review — 009-one-call-per-source-synth (#147 / #145)

**Scope:** `origin/main...HEAD` (spec commit only) plus the uncommitted working tree and untracked `llmwiki/source_topics.py`, `tests/test_147_acceptance.py`, `tests/test_source_topics.py`. Ignored: `config.json`, `.worktree-vault/`.

**Bar:** `docs/maintainers/REVIEW_CHECKLIST.md` (Blocker vs Nit), plus ARCHITECTURE, DECLINED, CONTRIBUTING, SECURITY. Logic bugs not named on the checklist are included when confidence ≥ 80.

**Local tests:** `python3 -m pytest` on the #147 unit/integration files in this worktree passed (e2e `conftest` was not loaded; `pytest_bdd` is absent here).

---

## Verdict

**Request changes**

| Severity | Count |
| --- | ---: |
| Blockers | 3 |
| Nits | 3 |

---

## Blockers

### 1. One concern per PR — product #147 mixed with contributor verify/screenshot overlays

- **Confidence:** 90
- **Where:** `.claude/commands/awos/verify.md`, `.claude/commands/fix-bug.md`, `.claude/commands/implement-feature.md`, `.cursor/commands/awos-verify.md`, `context/product/delivery-flow.md` (and the matching CHANGELOG “Local delivery review” / verify-path bullets if those ride this PR)
- **Guideline:** REVIEW_CHECKLIST **Meta — One concern per PR**; CONTRIBUTING TL;DR #1
- **Why:** The product change is one-call-per-source synth + interrupt harvest (#147 / #145). The same working tree also rewrites maintainer AWOS verify to forbid screenshots and HTTP servers (#109 process overlay). That is a second intent: contributor delivery-flow, not vault synth. The checklist splits mixed PRs.
- **Fix:** Land #147 as `llmwiki/` + tests + user docs + CHANGELOG + this `context/spec/009-…` tree only. Move the verify/screenshot overlays to a separate `chore:` / `docs:` PR (they already have a delivery-flow §10 origin note).

### 2. Job 1 on Claude CLI is steered as “wiki source markdown”, not JSON

- **Confidence:** 91
- **Where:** `llmwiki/topics_consolidate.py` ~164–168 (`prepare_known_names` → `backend.synthesize_source_page`); `llmwiki/synth/claude_cli.py` ~56–60 (`_LEAN_SYSTEM_PROMPT`) and ~298–300 (`stable or _LEAN_SYSTEM_PROMPT`)
- **Guideline:** Not named on the checklist; **logic error** against FR5 / technical spec job 1. Closest checklist: **Tests** (happy path for the real backend is untested) and **Error handling** (failures are swallowed into heuristic vocab).
- **Why:** `topic_consolidation.md` has no `## Session to synthesize`, so `split_prompt_template` yields an empty stable prefix. Claude then uses `_LEAN_SYSTEM_PROMPT`: synthesize **wiki source pages**, output **only markdown**. The user message asks for **ONLY valid JSON**. `parse_and_cache` then fails, `prepare_known_names` warns and returns, and the run continues on heuristic `_inject_vocabulary`. Dummy/spy tests never go through `ClaudeCLISynthesizer`, so CI stays green while the default LLM backend can skip the known-names cache every run.
- **Fix:** Do not reuse the source-page lean system prompt for job 1. Options: (a) a dedicated backend method / system prompt (“return only the JSON object”); (b) put `## Session to synthesize` at the end of `topic_consolidation.md` so the consolidation instructions become the cached `stable` system half; (c) call the provider without `_LEAN_SYSTEM_PROMPT`. Add a test that `ClaudeCLISynthesizer.synthesize_source_page` (or a extracted argv/system-prompt helper) does **not** attach the wiki-page lean prompt when the template is the consolidation prompt.

### 3. Job 1 `kind` never reaches the frozen job-2 vocabulary prefix (FR5)

- **Confidence:** 90
- **Where:** `llmwiki/synth/pipeline.py` `_inject_vocabulary` ~376–388; `llmwiki/synth/prompts/source_page.md` “Existing topics” ~61–75; `llmwiki/topics_consolidate.py` `parse_and_cache` / `load_cache` (kind is stored on topic entries, not mapped into inject)
- **Guideline:** Logic vs FR5 AC2 and technical spec §2.1 (“canonical `name`, `aliases`, `kind`, one-line `description`” injected so every source pass reuses spelling **and** kind). REVIEW_CHECKLIST **Tests — happy path + edge** (no test that job-2 `{vocabulary}` contains `kind=`).
- **Why:** Job 1 persists `kind` on `.llmwiki-topics.json`. `_inject_vocabulary` still emits `<topic name="…" desc="…" with="…"/>` only. `source_page.md` never tells the model to copy `(entity)` / `(concept)` from that list. Graph node `kind` is folder plurals (`entities` / `concepts`), not the source-bullet contract. Harvest then majority-votes kinds the source pass was never asked to reuse.
- **Fix:** When injecting, attach `kind="entity"| "concept"` from the cache topic entry (fallback: map wiki folder `entities`→`entity`, `concepts`→`concept`; omit if unknown). Update the Existing topics rules to prefer that kind on `[[ExactName]] (kind)` bullets. Assert the job-2 prompt prefix contains `kind=` after `prepare_known_names` in `test_llm_synth_runs_prepare_known_names_once_before_pages`.

---

## Nits

### 4. Interrupt harvest always claims success

- **Confidence:** 86
- **Where:** `llmwiki/cli.py` `cmd_synthesize` ~1272–1280
- **Guideline:** REVIEW_CHECKLIST **Code quality — Error handling matches the module**; FR9 (progress and failure reporting)
- **Why:** After `run_harvest`, the CLI prints `Pending names collected from written sources.` even when `rc != 0` (unreadable sources → exit 2). Review counts refresh only on `rc == 0`, so stderr can show a harvest error while stdout says collection succeeded. Then the process still exits 130.
- **Fix:** Print the success line only when `rc == 0`. On failure, print that harvest failed and the exact `llmwiki synth --candidates-only` recovery line; keep exit 130 if that remains the interrupt contract, or return the harvest `rc` when harvest is the failure of record.

### 5. Unreleased CHANGELOG still documents fail-closed harvest classification

- **Confidence:** 88
- **Where:** `CHANGELOG.md` `## [Unreleased]` → Removed → `synth --allow-unclassified` (#102) (“harvest now always fails closed… Configure a reachable backend”)
- **Guideline:** REVIEW_CHECKLIST **Docs** / **Meta — CHANGELOG** (user-visible accuracy); contradicts the new #147 Unreleased bullets
- **Why:** After this change, default harvest ignores the backend and does not refuse on classify. Leaving the #102 paragraph as current Unreleased behaviour will mis-instruct operators who read the file top-down.
- **Fix:** Rewrite that bullet to historical tense (flag removed in #102; harvest classification later removed in #147 / see Changed) or drop the fail-closed sentences now that they are false.

### 6. Stale comments still describe `consolidate-topics` as a user command

- **Confidence:** 82
- **Where:** `llmwiki/synth/pipeline.py` `_inject_vocabulary` docstring ~347–351; `llmwiki/topics.py` ~146–147
- **Guideline:** REVIEW_CHECKLIST **Docs — docstrings match the code**; FR7
- **Why:** Vocabulary still comes from the cache job 1 writes, but comments tell readers to run `llmwiki consolidate-topics`.
- **Fix:** Point at `prepare_known_names` / synth job 1; mention the CLI name only as retired.

---

## Checklist notes (no extra findings)

- **Linked issue / AWOS context / conventional changelog / tests for the product path:** present in the uncommitted tree (`context/spec/009-…`, CHANGELOG #147/#145, new parser + harvest/promote/interrupt tests).
- **Layer boundaries / no new runtime deps / L0 stdlib:** synth + harvest + CLI + Home snapshot; no new packages; `source_topics.py` is a leaf on `wikilinks`.
- **Security + privacy:** no session fixtures with real paths, no new HTML surface, no build-time network, no telemetry, localhost unchanged. Job 1 failure degrades locally (heuristic vocab), it does not exfiltrate.
- **DECLINED.md:** no revived N-way / scraping / qmd / `_context.md` auto-gen.
- **`classify_names` left in `candidates_harvest.py`:** allowed by the technical spec (unused on the default path). Not a blocker.
- **Promote offline / no mention-clip:** matches FR4; spies in `tests/test_candidates.py` lock it.
