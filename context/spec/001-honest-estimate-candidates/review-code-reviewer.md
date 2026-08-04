# Code review: #113 honest estimate Candidates (`feat/113-honest-estimate-candidates`)

**Scope:** `git diff origin/main...HEAD` plus all uncommitted / untracked working-tree changes (implementation mostly uncommitted).

**Focus:** bugs, logic errors, security issues, CONTRIBUTING violations. Confidence threshold ≥ 80.

**Verdict:** request_changes

| Severity | Count |
|---|---|
| Critical | 1 |
| Important | 2 |
| Advisory (&lt;80, not counted) | — |

---

## Critical

### 1. JSON envelope can be written as a wiki source page (confidence: 95)

**Where:** `llmwiki/synth/claude_cli.py` — `_parse_claude_print_stdout` (approx. lines 161–188) + `synthesize_source_page` always appending `--output-format json` (approx. lines 235–236, 290–299).

**Bug:** This PR forces `claude -p` to emit `--output-format json` on every page call. When stdout is JSON but `result` is missing, null, or empty, the parser falls back to returning the **entire raw JSON string** as “page text”:

```python
if not isinstance(result, str) or not result.strip():
    return text, None, None  # `text` is the full JSON blob
```

`synthesize_source_page` then treats any non-empty string as a successful completion and returns it to the pipeline. That content is written under `wiki/sources/`.

Previously the CLI default was plain text, so a JSON envelope almost never appeared. Requesting JSON by default makes “JSON without a usable `result`” a realistic failure mode (truncated stdout, alternate CLI shape, error payload with empty `result` but exit 0).

**Verified locally:** `_parse_claude_print_stdout('{"is_error":true,"result":"","subtype":"error"}')` returns the whole JSON string (not `""`), so the empty-completion guard later in `synthesize_source_page` does **not** fire.

**Guideline / impact:** Corrupts immutable-ish synthesized sources with billing/session metadata; silent data-quality failure (not a security hole in the sandbox sense, but a serious integrity bug on the primary synth backend).

**Fix:** If stdout parses as a JSON object and was requested as JSON:

1. Require a non-empty string `result` (and preferably `is_error is not True` / `subtype == "success"`).
2. On missing/invalid `result`, raise `ClaudeCLIError` — never return the envelope.
3. Keep plaintext fallback only when the payload does **not** look like parseable JSON (test stubs that ignore `--output-format`).
4. Add a unit test that empty/missing `result` raises and does not return `{`-prefixed garbage.

---

## Important

### 2. Claude JSON `is_error` / failure subtype ignored (confidence: 85)

**Where:** `llmwiki/synth/claude_cli.py` — `_parse_claude_print_stdout` / `synthesize_source_page` (same block as above). Exit-code check only (`returncode != 0`).

**Logic:** Claude Code’s `--output-format json` documents a structured result object (`result`, `usage`, `total_cost_usd`, `is_error`, `subtype`, …). This change starts depending on that shape for tokens/cost, but still accepts any payload with a non-empty `result` string whenever the process exits 0. Failed runs can surface as JSON with `is_error: true` (or non-success `subtype`) while still exiting 0; the assistant message (or error text) would be ingested as a normal source page, and token/cost counters might still accumulate.

**Fix:** After a successful `json.loads` of an object, reject the response when `is_error` is true or `subtype` is present and not `"success"`, raising `ClaudeCLIError` with a short detail from `result`/stderr. Cover with a unit test.

---

### 3. Tech spec still requires post-run `summarize_backlog` Candidates while code deliberately omits them (confidence: 88)

**Where (inconsistent today):**

| Source | Says |
|---|---|
| `llmwiki/synth/reporting.py` `print_synth_run_summary` | Candidates intentionally **not** printed |
| `CHANGELOG.md` / amended functional ACs (§2.2–2.3) | Harvest owns Candidates; end summary does not repeat |
| `technical-considerations.md` §1 high-level | Candidates stay on harvest line only |
| `technical-considerations.md` Component table (“End-of-run summary”) | Still lists post-harvest `summarize_backlog` Candidates |
| Same file Logic § “Real synth path” | Still: “call `summarize_backlog` and print the end-of-run summary” |
| Same file §3 risk + §4 tests | Still refer to dual backlog line / “Candidates consistent with `summarize_backlog`” |
| `functional-spec.md` Overview + §3 In-Scope | Still promise Candidates “as they stand after the run” / “post-harvest Candidates” in the end-of-run summary |

**CONTRIBUTING / logic:** CONTRIBUTING expects user-visible behaviour, docs, and CHANGELOG to align. The product docs (`docs/reference/cli.md`, cheatsheet, UPGRADING, Home copy) match the harvest-only Candidates choice. The **approved tech considerations were only partially amended**, so the PR currently ships contradictory requirements for the same feature. That invites the next agent to “fix” the summary by re-adding a second Candidates line (or, conversely, leaves open whether acceptance was actually met relative to the written tech plan).

**Fix (pick one and finish the amendment):**

- **A (match code):** Finish updating `technical-considerations.md` (component table, algorithm, risks, test strategy) and the functional Overview / In-Scope bullets so nothing still requires `summarize_backlog` in the end summary; or  
- **B (match original tech plan):** Call `summarize_backlog` after harvest and print a clearly labelled post-run backlog line from the helper (accepting a second Candidates-adjacent line with distinct wording).

Do not leave Overview/ACs/tech algorithm disagreeing with `print_synth_run_summary`.

---

## What looks solid (no ≥80 findings)

- Estimate pre-run label + pending-sources note via `print_candidates_pre_run`; estimate path skips end-of-run summary (covered by tests).
- Wall-clock placement after estimate/check early returns; `--sources-only` / `--candidates-only` / failed harvest do not mis-claim a post-harvest summary.
- `all --with-synth` shares `print_synth_run_summary`; usage plumbed only through optional `reset_usage` / `take_usage` (no invented rate-card cost).
- Product docs + CHANGELOG Unreleased bullet updated for #113; no new runtime deps; no personal vault paths / usernames in the changed product surfaces.
- Related pytest subsets for this feature currently pass locally.

---

## Suggested merge gate

Block on **Critical #1** (and ideally **Important #2**) before merge. Resolve **Important #3** in the same PR so the written tech/functional contract matches the code that will ship.
