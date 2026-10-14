# Functional Specification: Bound and speed up known-names preparation

- **Roadmap Item:** GitHub Issue [#264](https://github.com/AlexanderMakarov/llm-wiki/issues/264) — every synthesis run starts with one “preparing known names” step that can take a minute or more and sometimes times out; operators need a candidate cap, incremental reuse of unchanged topics, a dedicated timeout for this step, and clear run reporting. Complements per-source kind injection ([#257](https://github.com/AlexanderMakarov/llm-wiki/issues/257)); does not change how pending candidate stubs are collected or reviewed.
- **Status:** Completed
- **Author:** 4ellendger

---

## 1. Overview and Rationale (The "Why")

When an operator runs synthesis, the first paid step asks a language model to describe every candidate topic the wiki already knows about. On a real vault that step already takes about a minute; scheduled runs have hit the ordinary per-page wait limit and fallen back to a weak automatic vocabulary. Larger or older vaults send more candidates, so the wait grows, and every run re-asks for topics whose descriptions have not changed.

**Desired outcome:** the preparing-known-names step stays useful without dominating the run. Operators can limit how many candidates go into the call (highest session reach first). Unchanged topics keep their saved descriptions, aliases, and kind; the model is asked only about new or changed names; a vault with nothing new skips the call entirely. This step has its own wait limit, separate from per-page synthesis, and the run log shows how many candidates were sent, how large the prompt and reply were, how long it took, and token or cost figures when the backend reports them. Optional leaner reply shapes are deferred.

**Success is measured by:** a vault above the cap sends exactly the cap; a second run with no new or changed candidates makes zero known-names calls and still injects the saved vocabulary (including kind where known); a run with a few new names asks only about those and merges without losing untouched entries; the dedicated timeout is configurable independently of the per-page timeout; the run output reports candidate count, sizes, and duration for this step.

---

## 2. Functional Requirements (The "What")

### FR1 — Cap candidates sent to known-names preparation

- **As an** operator with a large wiki, **I want** synthesis to send at most a configurable number of candidate topics to the preparing-known-names step, choosing the ones seen in the most sessions first, **so that** the call stays bounded as the vault grows.

Default cap when unset: **150**. Topics below the cut keep their saved entry when one exists, or fall back to the existing automatic vocabulary path for names with no saved entry.

- **Acceptance Criteria:**
  - [ ] Given a vault with more candidate topics than the configured cap, when the operator runs synthesis with a language-model backend, then the preparing-known-names step sends exactly the cap count, highest session reach first.
  - [ ] Given a topic below the cut that already has a saved known-names entry, when the step finishes, then that entry remains available for vocabulary injection (including kind when present).
  - [ ] Given the operator changes the cap in configuration and re-runs, when the next preparing-known-names step runs, then the new cap is honoured.

### FR2 — Reuse saved known-names entries; call only on delta

- **As an** operator whose topic list is mostly stable, **I want** synthesis to reuse saved descriptions, aliases, and kinds for topics that have not meaningfully changed, and to skip the language-model call when nothing is new, **so that** steady-state vaults pay zero known-names cost.

A candidate is “changed” when its name, aliases, or reach bucket relative to the last saved preparation differs enough that a fresh description is warranted (exact change rule is an implementation detail; the operator-visible rule is: unchanged topics are not re-asked).

- **Acceptance Criteria:**
  - [ ] Given a second synthesis run with no new or changed candidate topics (after a successful first preparation), when the run starts, then it makes zero known-names language-model calls and still injects the saved vocabulary, including kind where known.
  - [ ] Given a run with a few new or changed candidates, when preparing known names runs, then the model is asked only about those (plus any minimal context the prompt needs), and the saved list is updated by merge without losing description, aliases, or kind for untouched names.
  - [ ] Given a first-ever run with an empty saved list, when preparation succeeds, then the full (capped) candidate set is sent and the result becomes the new saved vocabulary.

### FR3 — Dedicated wait limit for known-names preparation

- **As an** operator running scheduled synthesis, **I want** the preparing-known-names step to use its own wait limit, separate from the ordinary per-page synthesis wait, **so that** I can give this longer call enough time without making hung page calls wait longer too.

Default when unset should be generous relative to today’s measured ~1 minute (on the order of several minutes, e.g. 600 seconds, or at least as long as the backend’s per-page timeout when that is higher). On timeout or non-usage-limit failure, behaviour stays: warn clearly and fall back to automatic vocabulary (usage-limit errors still stop the run as today).

- **Acceptance Criteria:**
  - [ ] Given a configured known-names wait limit different from the per-page timeout, when preparing known names runs, then that dedicated limit is what bounds the call — not the per-page timeout alone.
  - [ ] Given the dedicated limit is raised or lowered in configuration, when the next preparation runs, then the new limit is used without changing the per-page timeout for source pages.
  - [ ] Given the call hits the dedicated limit (or another non-usage-limit failure), when the run continues, then the operator sees a clear warning that known-names preparation fell back, and heuristic vocabulary is used as today.

### FR4 — Report size and duration of the known-names step

- **As an** operator watching a synthesis run, **I want** the preparing-known-names progress and summary to show how many candidates were sent, approximate prompt and reply size, duration, and token or cost figures when the backend reports them, **so that** growth of this step is visible before it becomes a surprise timeout.

- **Acceptance Criteria:**
  - [ ] Given a preparation call that runs (not skipped), when the step completes or falls back, then the run output reports candidate count sent, prompt/reply size, and duration for this step.
  - [ ] Given the backend reports token or cost usage for the call, when the step finishes, then those figures appear in the same reporting path; when the backend does not report them, the other fields still appear.
  - [ ] Given the step is skipped because there is no delta, when the run starts, then the output makes that skip visible (zero call / reused saved vocabulary) rather than looking like a silent no-op.

### FR5 — Docs and release notes (including how to choose the cap)

- **As an** operator reading product docs after upgrading, **I want** the new cap, incremental reuse behaviour, dedicated timeout, and reporting described in the configuration/CLI reference and CHANGELOG, **and** clear guidance on how to choose the candidate-cap value, **so that** I can tune the step without reading the issue tracker.

The cap guidance must explain, in plain language:

1. **What the number bounds** — how many candidate topics go into the preparing-known-names call (highest session reach first); it does **not** depend on session or article body length, because that step sends only short topic hints, not page bodies.
2. **Cost and time** — more candidates mean a larger reply and longer wall time on a cold (or large-delta) run; after incremental reuse, a stable vault usually pays zero for this step, so the cap mainly matters on first preparation and when many topics change.
3. **Quality effect** — topics below the cut keep a saved entry when one exists, otherwise the weaker automatic vocabulary; raising the cap improves coverage of lower-reach names at the cost of a slower/more expensive cold call; lowering it shortens that call but leaves more names on cache or heuristics.
4. **When vaults exceed the default (150)** — a well-curated wiki rarely has more than about 150 significant topics that clear the “seen in several sessions” bar. Crossing that usually means either a genuinely large knowledge base or a **quality problem** (too many weak/noisy candidates were accepted into the live vocabulary). In that situation, simply raising the cap without cleaning up tends to make preparation slower while vocabulary quality keeps dropping; operators should prefer reviewing/discarding noise (and relying on incremental reuse) over endlessly increasing the number.

- **Acceptance Criteria:**
  - [ ] Given the configuration reference (and CLI reference where synthesis behaviour is described), when the operator looks up known-names preparation, then the cap key (default 150), dedicated timeout key, and incremental-reuse behaviour are documented.
  - [ ] Given those same docs, when the operator looks for how to choose the cap, then they find the four guidance points above (what it bounds, cost/time, quality effect, and the “large or noisy vault” note about exceeding 150).
  - [ ] Given CHANGELOG for the release that includes this work, when the operator reads Unreleased / the release notes, then the user-visible behaviour change is summarised.

---

## 3. Scope and Boundaries

### In-Scope

- Candidate cap for known-names preparation (default 150; configurable; highest reach first).
- Incremental reuse of saved known-names entries; skip the call when there is no delta; merge on partial delta without losing untouched entries (including kind).
- Dedicated configurable timeout for this step, independent of per-page synthesis timeout; clear fallback warning.
- Run-log reporting of candidates sent, sizes, duration, and tokens/cost when available.
- Tests covering cap ordering, zero-call reuse, merge-on-delta, timeout resolution, and reporting.
- Docs (`docs/reference/cli.md` and/or configuration reference as appropriate) and CHANGELOG, including “how to choose” guidance for the candidate cap (cost/time, quality, and the note that exceeding ~150 usually means a very large or poorly curated vault).

### Out-of-Scope

- **Leaner reply format** (pipe-delimited / compact XML / short keys) — deferred; today’s JSON vocabulary shape remains the wire format for this delivery.
- **Descriptions-only-on-delta as a separate reply-shape change** — covered operationally by FR2 (do not re-ask unchanged topics); no new lean wire format in this delivery.
- Changing how pending candidate stubs are harvested or reviewed after synthesis.
- Redesigning per-source vocabulary injection beyond preserving kind on reuse ([#257](https://github.com/AlexanderMakarov/llm-wiki/issues/257) already shipped).
- Filing a separate timeout-only bug issue (timeout is in-scope here per operator choice for this run).
