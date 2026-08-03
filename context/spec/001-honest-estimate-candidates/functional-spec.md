# Functional Specification: Honest candidate backlog on estimate; truthful end-of-synth summary

- **Roadmap Item:** Honest `--estimate` candidate preview (#113)
- **Status:** Approved
- **Author:** implement-feature / product interview
- **GitHub Issue:** https://github.com/AlexanderMakarov/llm-wiki/issues/113

---

## 1. Overview and Rationale (The "Why")

When someone asks the tool for an estimate of what the next synthesize run will do, they currently also see a Candidates total. That total describes the wiki as it exists **right now**, before the run. Synthesize is about to write new source pages and then harvest candidates from them, so whenever there is anything still to synthesize, the printed Candidates number is already out of date. Someone can reasonably read `Candidates: 0` as “this run will produce nothing to review” when the pending sources will in fact change the backlog.

Separately, after a real synthesize finishes, the next step in the usual workflow is reviewing candidates (in an agent session). The CLI should end with a clear “what just happened” summary — including an honest Candidates figure measured after harvest — so the user has a trustworthy hand-off into that review.

Success looks like: estimate never presents Candidates as a forecast of the upcoming run; a completed synthesize prints a short factual summary (how much was done, how long it took, cost/tokens when known, and Candidates as they stand after the run).

---

## 2. Functional Requirements (The "What")

### 2.1 Estimate labels Candidates as pre-run state

- When the user runs synthesize in estimate mode, if Candidates are shown, the line must use the label **Candidates (pre-run state):** (not wording that sounds like a forecast of this run).
- A short clarifying note must make clear that sources still waiting to be synthesized are not yet reflected in that figure.
- Candidates may still appear on every estimate (including when there are pending sources); honesty comes from the label and note, not from hiding the number.
- Any surrounding help or docs text that still calls this figure a “preview” of the next run must be corrected.

**Acceptance Criteria:**

- [ ] Given a vault with at least one source still to synthesize, when the user runs synthesize in estimate mode, then the Candidates line uses the **Candidates (pre-run state):** label (or equivalent approved wording) and does not read as a prediction of what the upcoming run will harvest.
- [ ] Given the same estimate output, when the user reads the Candidates block, then a note is present stating that pending sources are not yet reflected.
- [ ] Given a vault with nothing pending to synthesize, when the user runs estimate, then Candidates may still appear under the same pre-run label (the number happens to match post-run state, but the label stays consistent).

### 2.2 End-of-run summary after a real synthesize

- After a successful real synthesize (not estimate-only), the user must see an end-of-run summary that includes:
  - How many sources were synthesized in this run
  - Wall-clock time for the run
  - Token usage and money spent, **when those figures are known**
  - Candidates using the backlog **after** this run’s harvest (the real current backlog the user would review next)
- If token usage and/or cost are unknown, those lines are omitted; the other summary lines still appear.
- Do not invent a predicted Candidates total before synthesis; only report Candidates measured after the run (or, on estimate, clearly as pre-run state).

**Acceptance Criteria:**

- [ ] Given pending sources, when the user runs a real synthesize and it finishes successfully, then the CLI shows synthesized count for this run, wall-clock duration, and a Candidates figure consistent with the post-run backlog.
- [ ] Given the same vault, when the user compared an estimate’s pre-run Candidates with the post-run summary Candidates and the run wrote new sources that affected harvest, then the two Candidates figures may differ; the post-run figure is the one that matches what review will see.
- [ ] Given a successful synthesize with no known token or cost data, when the summary prints, then token/cost lines are absent and synthesized count, duration, and Candidates remain.
- [ ] Given estimate-only mode, when it finishes, then it does **not** print the full post-run summary as if a synthesize had just completed (estimate stays an estimate; Candidates stay labelled pre-run).

### 2.3 Discoverability hand-off

- The end-of-run summary exists so the last CLI step before agent candidate review still surfaces the backlog honestly.
- Relocating that nudge into unrelated commands (for example build) is not required.

**Acceptance Criteria:**

- [ ] Given a successful real synthesize that leaves a non-empty candidate backlog, when the user reads the end-of-run summary, then they can see the Candidates total without running a separate estimate.

---

## 3. Scope and Boundaries

### In-Scope

- Relabeling and clarifying the Candidates block on synthesize estimate
- Correcting docs/help wording that presents that block as a run forecast or “preview”
- Printing a factual end-of-run summary after a successful real synthesize (counts, duration, optional tokens/cost, post-harvest Candidates)

### Out-of-Scope

- Honest Corpus / Already synthesized units and the Home pipeline widget (#81) — tracked separately; shares a labelling *convention* with this work but is not implemented here
- Redesigning the candidates review UI or agent `/wiki-candidates` workflow
- Predicting which candidates the next synthesize will create without running synthesis
- Adding estimate mode to build or other commands
- Reconciling stale synthesize state rows beyond what is needed to report the figures above
