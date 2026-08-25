# Functional Specification: Honest candidate backlog on estimate; truthful end-of-synth summary

- **Roadmap Item:** Honest `--estimate` candidate preview (#113)
- **Status:** Completed
- **Author:** Alexander Makarov
- **GitHub Issue:** https://github.com/AlexanderMakarov/llm-wiki/issues/113

---

## 1. Overview and Rationale (The "Why")

When someone asks the tool for an estimate of what the next synthesize run will do, they currently also see a Candidates total. That total describes the wiki as it exists **right now**, before the run. Synthesize is about to write new source pages and then harvest candidates from them, so whenever there is anything still to synthesize, the printed Candidates number is already out of date. Someone can reasonably read `Candidates: 0` as “this run will produce nothing to review” when the pending sources will in fact change the backlog.

Separately, after a real synthesize finishes, the next step in the usual workflow is reviewing candidates (in an agent session). The CLI should end with a clear “what just happened” summary (how many sources were written, how long it took, and cost/tokens when known). Candidates stay on the existing harvest report so that line is not duplicated.

Success looks like: estimate never presents Candidates as a forecast of the upcoming run; a completed synthesize prints a short factual summary (how much was done, how long it took, cost/tokens when known) while harvest still reports Candidates once.

---

## 2. Functional Requirements (The "What")

### 2.1 Estimate labels Candidates as pre-run state

- When the user runs synthesize in estimate mode, if Candidates are shown, the line must use the label **Candidates (pre-run state):** (not wording that sounds like a forecast of this run).
- A short clarifying note must make clear that sources still waiting to be synthesized are not yet reflected in that figure.
- Candidates may still appear on every estimate (including when there are pending sources); honesty comes from the label and note, not from hiding the number.
- Any surrounding help or docs text that still calls this figure a “preview” of the next run must be corrected.

**Acceptance Criteria:**

- [x] Given a vault with at least one source still to synthesize, when the user runs synthesize in estimate mode, then the Candidates line uses the **Candidates (pre-run state):** label (or equivalent approved wording) and does not read as a prediction of what the upcoming run will harvest.
- [x] Given the same estimate output, when the user reads the Candidates block, then a note is present stating that pending sources are not yet reflected.
- [x] Given a vault with nothing pending to synthesize, when the user runs estimate, then Candidates may still appear under the same pre-run label (the number happens to match post-run state, but the label stays consistent).

### 2.2 End-of-run summary after a real synthesize

- After a successful real synthesize (not estimate-only), the user must see an end-of-run summary that includes:
  - How many sources were synthesized in this run
  - Wall-clock time for the run
  - Token usage and money spent, **when those figures are known**
- Candidates after a real run are reported by the existing harvest line (stubs written + review command) — the end-of-run summary must **not** print a second Candidates line.
- If token usage and/or cost are unknown, those lines are omitted; the other summary lines still appear.
- Do not invent a predicted Candidates total before synthesis; on estimate, Candidates stay clearly labelled as pre-run state.

**Acceptance Criteria:**

- [x] Given pending sources, when the user runs a real synthesize and it finishes successfully, then the CLI shows synthesized count for this run and wall-clock duration, and harvest reports Candidates (at most once — not also in the end summary).
- [x] Given a successful synthesize with harvest, when the user reads stdout, then Candidates appear on the harvest report and are absent from the end-of-run summary block.
- [x] Given a successful synthesize with no known token or cost data, when the summary prints, then token/cost lines are absent and synthesized count and duration remain.
- [x] Given estimate-only mode, when it finishes, then it does **not** print the full post-run summary as if a synthesize had just completed (estimate stays an estimate; Candidates stay labelled pre-run).

### 2.3 Discoverability hand-off

- The harvest Candidates line (and optional end-of-run count/duration/tokens) is the CLI hand-off before agent candidate review.
- Relocating that nudge into unrelated commands (for example build) is not required.

**Acceptance Criteria:**

- [x] Given a successful real synthesize that writes candidates, when the user reads the CLI output, then they can see the Candidates total from the harvest report without running a separate estimate.

---

## 3. Scope and Boundaries

### In-Scope

- Relabeling and clarifying the Candidates block on synthesize estimate
- Correcting docs/help wording that presents that block as a run forecast or “preview”
- Printing a factual end-of-run summary after a successful real synthesize (counts, duration, optional tokens/cost); Candidates remain on the harvest line only

### Out-of-Scope

- Honest Corpus / Already synthesized units and the Home pipeline widget (#81) — tracked separately; shares a labelling *convention* with this work but is not implemented here
- Redesigning the candidates review UI or agent `/wiki-candidates` workflow
- Predicting which candidates the next synthesize will create without running synthesis
- Adding estimate mode to build or other commands
- Reconciling stale synthesize state rows beyond what is needed to report the figures above
