# Independent checklist review — #113 Honest estimate Candidates

- **Branch:** `feat/113-honest-estimate-candidates`
- **Scope reviewed:** `origin/main...HEAD` (spec commit `5546f85`) **plus** all uncommitted working-tree changes (implementation is mostly unstaged)
- **Issue:** https://github.com/AlexanderMakarov/llm-wiki/issues/113
- **Checklist:** `docs/maintainers/REVIEW_CHECKLIST.md` (all applicable sections)
- **Date:** 2026-08-04
- **Verdict:** **request-changes**

## Summary

The change correctly addresses the issue’s Option 3: estimate Candidates are labelled as pre-run wiki state (not a forecast), docs/Home copy stop calling that figure a harvest “preview,” and a real `synth` ends with count/duration (plus tokens/cost when the Claude CLI returns them). Shared helpers in `llmwiki/synth/reporting.py` keep CLI and `all --with-synth` consistent. Targeted and full `pytest` are green; `ruff` on touched Python is green.

Before merge, fix Claude JSON parsing when `--output-format json` is always on: missing/`is_error`/empty-`result` payloads currently fall back to writing the raw JSON (or error text) as a source page. Also align residual functional-spec / tasks wording that still describes post-harvest Candidates inside the end-of-run summary (ACs and code were amended the other way).

---

## Findings

### Blockers

_None under the checklist’s Security / Meta / layer-boundary / red-CI definition._

### Important

1. **Claude JSON parse fallback can write non-page stdout into `wiki/sources/`** (`llmwiki/synth/claude_cli.py`)

   Always appending `--output-format json` is appropriate for usage (and matches how cost docs already measure), but `_parse_claude_print_stdout` treats any dict without a non-empty string `result` as “plain text” and returns the **entire stdout** — including JSON envelopes and `is_error: true` payloads that still carry a `result` string.

   Concrete failure modes (exercised via the helper locally):

   - `{"result": ""}` / missing `result` → full JSON string becomes the page body (returncode 0 path does not raise).
   - `{"is_error": true, "result": "boom"}` → `"boom"` is accepted as a successful page with no `ClaudeCLIError`.

   Pre-#113, stdout was page text only; forcing JSON without validating `is_error` / requiring a usable `result` expands the silent-corruption surface. Fix: if stdout parses as a JSON object, require a non-empty `result` string and treat `is_error` (or absent `result`) as `ClaudeCLIError`; only use the plaintext fallback when the payload is not a JSON object (stubs that ignore `--output-format`). Add regression tests beside `tests/test_synth_claude_cli.py`.

2. **Functional-spec overview / In-Scope still describe end-summary Candidates; Slice 2 task text does too**

   Amended §2.2 ACs (and the implementation) correctly leave Candidates on the harvest line and omit them from `print_synth_run_summary`. But:

   - §1 still says success includes “Candidates as they stand after the run.”
   - §3 In-Scope still says the end-of-run summary includes “post-harvest Candidates.”
   - `tasks.md` Slice 2 title/body still say implement Candidates via `summarize_backlog` after harvest, yet the slice is marked `[x]`.

   That drift will mislead the next reviewer or a cherry-pick. Update overview / In-Scope / Slice 2 wording to match the amended ACs (or reopen the task as amended).

### Nits

3. **`--estimate` argparse help still only mentions the cost report** (`cli.py` ~2168) — fine as a short help line, but it never mentions the Candidates pre-run block that docs now document. Optional one-phrase addition for discoverability.

4. **`take_usage` treats cost `0.0` / token total `0` as unknown** — known zeros are omitted from the summary. Spec allows omitting unknown; strictly known-zero is still “known.” Unlikely in production; soften to `is not None` if you care.

5. **`test_ac_222_end_summary_does_not_duplicate_candidates`** only asserts helper stdout labels in isolation. Real duplication is better locked by `test_synth_prints_post_harvest_run_summary` (already present) — the acceptance test is thin relative to its AC claim.

6. **Slice 2 checkbox text vs smoke amendment** — implementation choice (no second Candidates line) is sound; just don’t leave the checked task describing the discarded design (covered under Important #2).

---

## Checklist application

### Meta

| Item | Result |
|---|---|
| Linked issue | Pass — #113 referenced in CHANGELOG, UPGRADING, specs, tests |
| One concern per PR | Pass — labelling + honest post-run summary + usage plumbing for that summary |
| Conventional-commit title | N/A until PR/commit; only committed change is `docs:` spec; implementation still uncommitted — use `feat:` (not `docs:`) when landing |
| CHANGELOG under Unreleased | Pass — Changed bullet + #90 bullet retuned |
| Tests added/updated | Pass — estimate, run-summary, Claude CLI usage, acceptance |
| CI green | Not evaluated (no PR push in this review); local full `pytest` exit 0; ruff clean on touched files |

### Layer boundaries

| Item | Result |
|---|---|
| Layer-appropriate | Pass — synth reporting/CLI/pipeline + docs + Home Commands copy (L1/L2/L5); no convert/adapters |
| No new runtime deps | Pass — stdlib `json` / `time` only |
| Layer-0 stdlib-only | Pass — untouched |

### Security + privacy

| Item | Result |
|---|---|
| No real session data | Pass — fixtures synthetic |
| Redaction | N/A — converter/redaction untouched |
| XSS in rendered HTML | Pass — `render/js.py` copy uses existing escaped HTML string patterns |
| No network during build | N/A for estimate path; Claude already subprocesses on real synth (JSON flag does not add a new network client) |
| Localhost binding | N/A |
| No telemetry | Pass |

### Code quality

| Item | Result |
|---|---|
| Docstrings on new public helpers | Pass — `reporting.py`, usage helpers |
| Inline comments for “why” | Pass — sparse and relevant |
| Error handling | **Important #1** — JSON envelope / `is_error` handling insufficient once JSON is mandatory |
| Type hints | Pass |
| No dead code | Pass |

### Tests

| Item | Result |
|---|---|
| Happy path + edges | Pass for labelling / omit tokens / estimate skips summary; **gap** on JSON error envelopes (Important #1) |
| Behavior-named tests | Pass |
| Regression annotations | Pass — `@regression` / `#113` commentary |
| tmp_path only | Pass |
| Local pytest | Pass — full `tests/` green this review |

### Docs

| Item | Result |
|---|---|
| README | Pass — flag list only; no misleading “preview” claim found |
| CHANGELOG | Pass |
| reference / cheatsheet / UPGRADING / ui | Pass — preview framing removed |
| Docstrings match | Pass for `summarize_backlog` / estimate comments |
| Spec package consistency | **Important #2** |

### Build + runtime smoke

| Item | Result |
|---|---|
| Full `llmwiki build` on live vault | Not re-run — change is CLI/synth presentation + Claude argv; Home copy string is inert until next build. Build not required to validate estimate labelling. |
| Preview server | N/A for core CLI behaviour |

### DECLINED.md

No conflict — USD-in-token-usage-cards decline is unrelated; this PR reports Claude’s own `total_cost_usd` when present, not Home card pricing.

---

## Severity counts

| Severity | Count |
|---|---|
| Blocker | 0 |
| Important | 2 |
| Nit | 4 |

## Verdict

**request-changes** — land Important #1 (Claude JSON validation) and tidy Important #2 (spec/task wording) before calling the PR ready. Nits optional.
