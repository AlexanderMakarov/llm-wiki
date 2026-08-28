# Tasks: Per-vault quality-check scoping (#150)

Spec: [`functional-spec.md`](./functional-spec.md) · [`technical-considerations.md`](./technical-considerations.md)

Every slice leaves the CLI runnable and is verified against a temp vault or the committed `demo/`. **Never** run a mutating command against the operator's live vault; read-only probes are fine.

---

- [x] **Slice 1: Lint stops calling a deliberate design decision a broken link**

  > End state: `python3 -m llmwiki lint --vault demo` reports **0** `link_integrity` findings at stock settings and all 120 again at `--min-refs 1`.

  - [x] Create `llmwiki/thresholds.py` holding `DEFAULT_MIN_REFS = 3` with no llmwiki imports. Re-export it from `llmwiki/candidates_harvest.py` so `cli.py` and `pipeline.py` importers are untouched. A direct `llmwiki.lint` → `candidates_harvest` import would be circular: `candidates_harvest` already imports `_norm_slug` from `llmwiki.lint.rules.link_integrity`. **[Agent: general-purpose]**
  - [x] Extract `count_source_refs(texts_by_rel) -> dict[str, set[str]]` from `harvest_targets` — pure, counts a target **once per page**. Call it from `harvest_targets` with no behaviour change. Do **not** extract resolution: harvest and lint invert each other on `candidates/` and `archive/` on purpose (tech spec §2.3). **[Agent: general-purpose]**
  - [x] Add frozen `LintOptions(min_refs=DEFAULT_MIN_REFS)` in `llmwiki/lint/__init__.py`; declare `options: LintOptions = LintOptions()` as a `LintRule` class attribute; have the runner set `rule.options` before `run`. Do **not** add a `min_refs=` keyword to `rule.run()` — 16 of 17 rules declare `run(self, pages, *, llm_callback=None)` and the runner turns rule exceptions into error-severity issues, so a new kwarg would report 16 errors on a clean vault. **[Agent: general-purpose]**
  - [x] Gate `LinkIntegrity`: count references over pages under `sources/` via `count_source_refs`; report only targets named by **at least** `self.options.min_refs` pages. Resolution logic unchanged. **[Agent: general-purpose]**
  - [x] Add `lint --min-refs N` (default `DEFAULT_MIN_REFS`) and thread it into `LintOptions`. **[Agent: general-purpose]**
  - [x] Unit tests: below-threshold target silent; at-threshold target reported; `--min-refs 1` restores every finding; candidates resolve; archived slugs still read as broken; `count_source_refs` counts once per page; rule and harvester agree on one corpus; **every registered rule runs clean under the new runner** (guards the kwarg trap). **[Agent: general-purpose]**
  - [x] Verify: `python3 -m llmwiki lint --vault demo` → 0 `link_integrity`; `--min-refs 1` → 120; existing harvest tests pass untouched; `ruff check llmwiki tests scripts` clean. Delete any scratch vault copies made during the check. **[Agent: general-purpose]**

- [x] **Slice 2: A vault can switch a check off, and the report always says which**

  > End state: a vault carrying `llmwiki.json` has the named rule skipped, and both the text report and `--json` name it with its reason.

  - [x] Create `llmwiki/vault_settings.py` with `load_vault_settings(root)` (missing file → `{}`) and `disabled_lint_rules(settings)` normalising both accepted shapes — list `["name"]` and object `{"name": "reason"}` — to `dict[str, str]`. Malformed JSON is a hard error, never a silent `{}`: an unparseable settings file must not yield a clean report. **[Agent: general-purpose]**
  - [x] Add `LintOutcome(issues, skipped, ran)` and `run_lint(pages, *, selected, disabled, options) -> LintOutcome` in `llmwiki/lint/__init__.py`. Keep `run_all` as a thin wrapper returning `.issues` so its ~20 existing call sites stay valid. Validate `disabled` names against `REGISTRY`, raising the existing `UnknownRuleError`. **[Agent: general-purpose]**
  - [x] Create `llmwiki/lint/report.py` with `render_text(outcome, total_pages)` and `render_json(outcome, total_pages)`. Skipped rules appear **whether or not** anything was found; when every registered rule is disabled the report states nothing was checked rather than printing a clean summary. **[Agent: general-purpose]**
  - [x] Rewrite `cmd_lint` to resolve settings (`--wiki-dir` → its parent, else `_content_root(args)`), call `run_lint`, and render through the shared reporter. **[Agent: general-purpose]**
  - [x] Tests: both accepted shapes; missing file; malformed JSON → exit 2; unknown rule name → clear failure listing valid names; disabled rule absent from findings and present in text + `--json` `disabled_rules`; all-rules-disabled wording; reason surfaced. **[Agent: general-purpose]**
  - [x] Verify: against a temp vault, disable a rule that fires and confirm it vanishes from findings while being named as skipped in both output modes; then delete the temp vault. **[Agent: general-purpose]**

- [x] **Slice 3: Warnings can stop the gate**

  > End state: `lint --fail-on-warnings` exits non-zero on a warning-only vault and zero once the offending rule is disabled.

  - [x] Add `lint --fail-on-warnings` beside the existing `--fail-on-errors`. **[Agent: general-purpose]**
  - [x] Fix the exit-code ordering in `cmd_lint`: it currently returns on `--fail-on-errors` **before** `_apply_default_vault` and the `last_lint_run_at` state update, so a failing lint never records its run. Compute the exit code last so neither flag skips the update. **[Agent: general-purpose]**
  - [x] Tests: warning-only vault → non-zero with the flag, zero without; clean vault → zero with the flag; disabling the offending rule → zero with the flag; a failing lint still records `last_lint_run_at`. **[Agent: general-purpose]**
  - [x] Verify: exercise all four exit-code paths against a temp vault, then delete it. **[Agent: general-purpose]**

- [x] **Slice 4: The threshold reaches the full pipeline**

  > End state: `llmwiki all --min-refs N` harvests at N, matching `synth --min-refs N`.

  - [x] Add `--min-refs N` to the `all` parser — it was only ever defined by `_add_synth_arguments` for `synth` / `synthesize`, so the threshold was unreachable on this path. **[Agent: general-purpose]**
  - [x] Pass the resolved threshold to `run_harvest` in `pipeline.py` instead of the hardcoded `DEFAULT_MIN_REFS`. **[Agent: general-purpose]**
  - [x] Point `_run_lint_step` at `run_lint` + the shared reporter so the pipeline and `lint` cannot drift, and so skipped rules show on this path too. **[Agent: general-purpose]**
  - [x] Tests: `all --min-refs N` reaches `run_harvest`; equals `synth --min-refs N` on the same corpus; default unchanged; pipeline lint output names skipped rules. **[Agent: general-purpose]**
  - [x] Verify: run both paths against a temp vault with a non-default threshold and diff the resulting candidate sets; delete the temp vault. **[Agent: general-purpose]**

- [x] **Slice 5: Conflicting-claims stops flagging boilerplate, and the defect it found gets fixed**

  > End state: the demo's three `contradiction_detection` findings are gone — two because the check got more precise, one because the bug it caught is fixed.

  - [x] Add `evident` to `_NONE_SYNONYMS` and modal hypotheticals `could|would|might|may` to `_NEGATOR_RE` in `llmwiki/lint/rules/contradiction_detection.py`. Both verified against the real demo text during specification. **[Agent: general-purpose]**
  - [x] Fix `docs/tutorials/01-installation.md:26` — `python3 --version # expect 3.9 or newer` contradicts line 10 ("Python 3.12+") and `pyproject.toml:10` `requires-python = ">=3.12"`. Make all three agree. **[Agent: general-purpose]**
  - [x] Update the `## Contradictions` section of `demo/wiki/sources/01-installation/2026-08-10-01-installation.md` to record that the version disagreement no longer exists. `demo/wiki/` is generated but committed, and regenerating it needs a synthesis backend (`scripts/refresh_demo.py` is maintainer-only); this hand-edit is what the next refresh would produce now that the docs agree. Do **not** touch anything under `demo/raw/`. **[Agent: general-purpose]**
  - [x] Tests: the two demo boilerplate strings are treated as filler; a genuine recorded contradiction is still flagged; the regression case `"None in the summary. However, this page contradicts prior guidance…"` stays flagged. **[Agent: general-purpose]**
  - [x] Verify: `python3 -m llmwiki lint --vault demo` reports 0 `contradiction_detection`, and the three Python-version statements agree. **[Agent: general-purpose]**

- [x] **Slice 6: An agent gets the same answer a person does**

  > End state: `tool_wiki_lint({})` returns the same payload as `lint --json` for the same vault.

  - [x] Rewrite `tool_wiki_lint` (`llmwiki/mcp/server.py:989`) to call `load_pages` + `run_lint` with the vault's settings and `LintOptions`, returning `render_json(...)`. Delete the private orphan/broken-link implementation — its exact `target in {p.stem}` match (no `_norm_slug`, no anchor stripping) and its wikilink-only orphan test both over-report versus the registry rules. **[Agent: general-purpose]**
  - [x] Add optional `rules` and `min_refs` tool arguments mirroring the CLI flags. No `fail_on_*` — there is no exit code over MCP. **[Agent: general-purpose]**
  - [x] Rewrite the `wiki_lint` entry in the tool schema: it currently advertises "orphan pages, broken wikilinks, contradictions, and stale summaries" while implementing only the first two. Describe what it now actually runs. **[Agent: general-purpose]**
  - [x] Update `tests/test_v02.py:157` and `tests/test_archive_cold_storage.py:272` to the new payload, and add the central parity test: `tool_wiki_lint({})` and `lint --json` agree on the same vault, including `disabled_rules` and threshold handling. An unknown rule name must error rather than return a clean report. **[Agent: general-purpose]**
  - [x] Record the payload change in `CHANGELOG.md` and `docs/UPGRADING.md` — keys `orphans` / `orphan_count` / `broken_links` / `broken_link_count` are replaced by `summary` / `issues` / `disabled_rules` / `total_pages`. This is a deliberate breaking change; keeping both shapes would defeat parity. **[Agent: general-purpose]**
  - [x] Verify: run both routes against the committed demo and a temp vault with an opt-out, and confirm identical payloads. **[Agent: general-purpose]**

- [x] **Slice 7: The demo enforces warnings**

  > End state: CI fails the demo on a warning-severity defect, and passes today.

  - [x] Add committed `demo/llmwiki.json` disabling `content_freshness` only, with a reason recording that a committed snapshot measures elapsed time. **No threshold override** — the demo runs at stock settings so it stays representative. **[Agent: general-purpose]**
  - [x] Update `.github/workflows/wiki-checks.yml` to pass `--fail-on-warnings`, replacing the comment that explains why `--strict` is withheld with one describing the opt-out that now makes enforcement possible. **[Agent: general-purpose]**
  - [x] Verify: `lint --vault demo --fail-on-errors --fail-on-warnings` exits 0; output names `content_freshness` as skipped with its reason; on a **copy** of the demo, seeding an above-threshold unmaterialized target makes it exit non-zero; with the clock moved past 90 days the real demo still passes. Delete the copy afterwards. **[Agent: general-purpose]**

- [x] **Slice 8: Someone can find out how to do this for their own wiki**

  > End state: the documentation describes the settings file, the caution, and the threshold's effect.

  - [x] Add an `llmwiki.json` section to `docs/configuration-reference.md`: location, both accepted shapes, a complete worked example, and a `lint` flag table beside the existing `all` one. State plainly that switching a check off hides real findings — it is for checks that cannot apply to a wiki, not for checks that are merely inconvenient. Explain why lowering the significance threshold produces more cross-reference findings. **[Agent: general-purpose]**
  - [x] Verify: follow the written instructions verbatim against a fresh temp vault and confirm the named check is switched off and reported as skipped; delete the temp vault. If the instructions cannot be followed exactly, fix the docs, not the test. **[Agent: general-purpose]**

- [x] **Slice 9: Feature Testing & Regression**

  > Verifies the whole feature end-to-end against functional-spec.md, run after all implementation slices are complete.
  - [x] Read functional-spec.md acceptance criteria in full. Generate acceptance-level tests that verify the entire feature as a whole — not individual slices. Cover applicable layers (unit for pure logic, integration for service interactions, e2e for user flows) based on the project's testing stack. Write tests with RED validation (must fail before implementation is confirmed done). Annotate each test with `@spec: 150-vault-lint-rule-scoping` and `@regression` if suitable for long-term regression. **[Agent: testing-expert]**
  - [x] Run all generated tests. All must pass. Fix any failures before proceeding. **[Agent: testing-expert]**

---

## Recommendations

| Task/Slice | Issue | Recommendation |
| --- | --- | --- |
| Slices 1–8, all implementation tasks | Assigned to `general-purpose` — `context/product/hired-agents.md` records Python/CLI coverage as "⚠️ Partial — skills installed; no dedicated agent (user declined template-generated agents)" | Optional: author a hand-written `.claude/agents/python-cli-backend.md`, or re-run `/awos:hire` if a suitable registry agent appears |
| Slice 6 (MCP) | `hired-agents.md` records the MCP server surface as "❌ Missing — no MCP-specific skill/agent in registry" | Acceptable here: the slice deletes a private implementation in favour of an existing shared one, so it needs llmwiki knowledge rather than MCP-protocol expertise |
| Slice 9 (QA) | None — `testing-expert` is installed and matches | — |
| Slice 9 (QA) | `hired-agents.md` notes `testing-expert` "expects testing stack declared in `context/product/architecture.md` — architecture currently does not declare pytest/ruff/e2e harness" | Pass the stack explicitly when dispatching: `python3 -m pytest tests/ -q` and `ruff check llmwiki tests scripts` |
| Slice 5 | Demo page hand-edit — `demo/wiki/` is generated, but regeneration needs a synthesis backend and `scripts/refresh_demo.py` is maintainer-only | Accepted and scoped to the one section the docs fix invalidates; `demo/raw/` stays untouched |
