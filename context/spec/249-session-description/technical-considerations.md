# Technical Specification: Session `description:` from assigned names + scored fallback

- **Functional Specification:** [`functional-spec.md`](./functional-spec.md) (#249)
- **Status:** Approved
- **Author(s):** Alexander Makarov

---

## 1. High-Level Technical Approach

Extend the adapter contract with optional **assigned session name** and optional **user-turn format cleanup**. At convert time, prefer assigned name (redacted) for frontmatter `description:`. When absent, **delete** today’s description heuristics and replace with **score every user prompt → sort → take top** (truncate 120). Wire Claude Code + Cursor CLI assigned names. **Lock weights only after an operator eval** on real sessions. No LLM for scoring; no new runtime deps; no synth.

---

## 2. Proposed Solution & Implementation Plan

### Architecture

| Piece | Path / responsibility |
|---|---|
| Adapter hooks | `assigned_session_name(path, records) -> str \| None`; `normalize_user_prompt(text) -> str` (default: identity / shared light cleanup) |
| Claude Code | `customTitle` > `aiTitle`; Claude XML → `/cmd` / `/cmd <args>` lives in **this adapter’s** `normalize_user_prompt` (not a convert-global Claude-only special case) |
| Cursor CLI | store meta `name`; normalize as needed for Cursor shapes (or default) |
| Convert | assigned name wins; else score candidates from user turns after **active adapter** normalize |
| Scoring | new helpers; **remove** soft-ack / continuation / description chrome-skip / first-match selection code |
| Eval | read-only harness → table of proposed `description:` for operator correction |

### Assigned-name precedence (Part A)

Unchanged: adapter assigned name → redact → truncate 120 → emit; skip Part B.

### Format cleanup (all adapters, not Claude-only)

Why not “Claude-only” in convert: other agents have their own envelopes/chrome. Cleanup is an **adapter responsibility**:

- `BaseAdapter.normalize_user_prompt(text) -> str` — default returns stripped text (or shared minimal cleanup).
- Claude Code override: existing control-XML collapse to `/cmd` / `/cmd <args>`.
- Cursor CLI / others: override when a real format need appears; otherwise default.

Convert calls the **active** adapter’s normalize when building candidates. Shared convert must not hardcode Claude XML as the only cleanup path.

### Scored fallback (Part B) — algorithm

**Delete** from the description path: soft-ack / continuation regexes, description-only chrome/dump skip lists, first-match leftover selection. Do not leave them unused.

Candidate = first non-empty line of `adapter.normalize_user_prompt(user_turn_text)`.

#### Type base (largest gaps)

| Type | Detection (structural, no LLM, no “issue-like” regex) | Base |
|---|---|---|
| Slash + **long** args | Line is `/cmd` + remainder whose **arg length** (chars after the command token) is **above** a threshold `ARG_LONG_MIN` | High — same band as prose (session-starting task commands, e.g. `/fix-bug …`) |
| Prose | Not a `/cmd` line | High — same band as slash+long-args |
| Slash + **short** args | `/cmd` + remainder with arg length **≤** `ARG_LONG_MIN` (e.g. `/model opus`, `/theme dark`) | Mid-low — config-like; must lose to later high-band prompts when position gaps are set correctly |
| Bare slash | `/cmd` with no args (`/clear`, `/mcp` with no args) | Lowest — wins **only** if nothing stronger exists |

**Counterexample to “prose always highest”:**  
`['/fix-bug xxxxx', 'merge with `--admin`']` → description **`/fix-bug xxxxx`** (slash+long-args, earlier), not the later short prose correction.

**Invariant still required:**  
`['/clear', '/model opus', '/theme dark', 'Refactor the auth middleware…']` → **prose** wins (high-band later beats early bare/short-arg slashes).

So: prose does **not** automatically beat slash+long-args; position + band decide. Bare slash is last resort.

`ARG_LONG_MIN` is a tunable constant (provisional until eval; document in code). No GitHub URL special-case — long vs short is **character count of args only**.

#### Position (next; stronger than length)

Earlier user-prompt index → higher bonus. Weight so that:

- Early slash+long-args beats later short prose (the `/fix-bug` vs `merge with --admin` case).
- Later high-band prose still beats early bare/short-arg slash stacks (`/clear` / `/model` / `/theme`).

Exact numbers from eval; unit tests lock both invariants.

#### Length (last; weakest)

- Length contribution uses `min(len(candidate), 120)` only — prompts longer than 120 get the **same** length term as a 120-char prompt.
- Range is effectively **0..120**; short prompts are valid (small length term, not rejected).
- **Position (and type) outrank length** — wordy later corrections must not win on verbosity alone.

`score = type_base + position_bonus + length_bonus(min(len, 120))`. Sort desc; tie-break earlier index. Winner → redact → truncate display to 120.

### Operator eval round (required)

Read-only over real Claude + Cursor CLI sessions: show assigned name (if any), top-N candidates with scores, chosen `description:`. Operator corrects weights (`ARG_LONG_MIN`, type gaps, position step) or rules; re-run; freeze when accepted.

### Cursor CLI meta / inventory / specialists

Unchanged from prior draft (persist `name`; inventory other adapters; `general-purpose` + `testing-expert`).

---

## 3. Impact and Risk Analysis

| Risk | Mitigation |
|---|---|
| `ARG_LONG_MIN` mis-bins `/fix-bug` vs `/model` | Eval + both unit invariants |
| Adapter normalize missing → ugly candidates | Claude override required; others default; eval catches |
| Huge first lines | Display truncate 120; length term capped at 120 |

---

## 4. Testing Strategy

- Invariants: `/fix-bug …` then `merge with --admin` → `/fix-bug …`; `/clear`+`/model`+`/theme` then prose → prose; `/mcp`-only → `/mcp`; truncate 120; length&gt;120 same length term as 120.
- Assigned names: Claude + Cursor CLI.
- Eval acceptance recorded in flow-log (not raw session text in git).
