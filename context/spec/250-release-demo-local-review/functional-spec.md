# Functional Specification: Release-cut local demo review (usage window + site gate)

- **Roadmap Item:** [#240](https://github.com/AlexanderMakarov/llm-wiki/issues/240) — refresh demo vault locally (site + usage + Home stamps) before tagging; CI only deploys
- **Status:** Approved
- **Author:** Aleksandr Makarov

---

## 1. Overview and Rationale (The "Why")

When a maintainer cuts a release, the public demo site is what visitors see after the tag deploys. Today the release checklist already refreshes demo sessions and wiki pages, and Home Pipeline state for the demo can be committed so the live site is not blank. Two gaps remain:

1. **Analytics still looks months old.** Session dates move to “release day,” but the demo’s MCP usage fixture is not regenerated in the same cut, so Analytics still shows an old telemetry window.
2. **Review happens after publish.** Maintainers only notice a broken Home Timeline, stale Analytics window, or wrong session dates after Pages has already shipped. There is no deliberate pause with a **local** demo site link before the tag push.

Success means: a release cut with demo refresh ON regenerates usage for release day, builds a local demo site, shows the maintainer a usable local URL, waits for an explicit OK, and only then allows the commit/tag push. Automation still only builds and deploys what was committed — it never invents sessions, usage, or ops stamps.

Related work already landed and is **not** re-opened here: committed demo Home Pipeline state so Pages is not all-“never” (#254 / #255).

---

## 2. Functional Requirements (The "What")

### FR1 — Usage fixture moves with release day

When demo refresh is ON for a release cut, the maintainer regenerates the demo’s MCP Analytics fixture using the same release-day date used for session regeneration. That regenerated fixture is part of what gets committed with the demo before tagging.

- **Acceptance Criteria:**
  - [ ] Given demo refresh is ON and a release-day date is chosen, when the release checklist is followed through the demo refresh steps, then regenerating demo usage for that same date is an explicit required step (not optional or forgotten).
  - [ ] Given that regeneration ran, when the maintainer inspects the demo Analytics MCP window after a local build, then the activity window ends on (or includes) that release-day date rather than a months-older fixture.
  - [ ] Given the human explicitly opted out of demo refresh for this cut, when the release continues, then usage regeneration is skipped with the same opt-out as sessions/docs (and may stay stale).

### FR2 — Local demo site build is part of the cut

After sessions, docs/wiki refresh, usage regeneration, and any required demo state refresh for Home Pipeline honesty, the maintainer builds the demo site locally to a known output location suitable for browser review.

- **Acceptance Criteria:**
  - [ ] Given demo refresh completed (or the cut is still preparing the demo commit), when the release skill/checklist reaches the review step, then it instructs a local demo site build and names how to open that site.
  - [ ] Given the build succeeded, when the skill reports progress to the human, then it prints a concrete local URL or open instruction (for example a `file://` path or a short serve command) — not only “build then look around.”

### FR3 — Human review gate before tag push

The release skill pauses after showing the local demo site link and before asking to push the version tag. The human reviews Home Timeline stamps, Analytics MCP window, newest session dates, and candidates (and may correct the demo and rebuild) before approving the push.

- **Acceptance Criteria:**
  - [ ] Given demo refresh was ON (not opted out), when the skill reaches the human gate, then it has already printed the local demo site URL/instruction and explicitly waits for human OK that the demo looks right before presenting tag push as ready.
  - [ ] Given the human has not confirmed the local demo review, when the skill would otherwise ask for tag push, then it does not treat the cut as ready to push.
  - [ ] Given demo synth is still incomplete/blocked, when the skill reports status, then it still refuses to present tag push as ready (existing hard-stop behavior remains).

### FR4 — Checklist and skill stay aligned

The maintainer release checklist and the `/release` skill both describe usage regeneration, local build + URL, the review pause, post-harvest case-fold/demo guards before tagging, and that Pages/CI only assert version and build the committed demo — not invent content freshness.

- **Acceptance Criteria:**
  - [ ] Given a maintainer reads the release process doc and the release skill for the same cut, when they compare the demo-refresh and human-gate steps, then both mention usage regeneration next to session regen, local site review with a link, and the pause before push.
  - [ ] Given a maintainer reads the Pages/CI notes in that process, when they look for who is responsible for freshness, then the docs state that CI deploys committed demo content and version-asserts — it does not regenerate sessions, usage, or invent ops stamps.

### FR5 — Post-harvest guards before tagging

After demo harvest/synth for the cut, the release checklist includes re-running the known case-fold / demo path guards so a colliding candidate path cannot slip into the tagged demo.

- **Acceptance Criteria:**
  - [ ] Given demo refresh included harvest/synth, when the checklist reaches pre-tag checks, then it calls out re-running the case-insensitive / demo collision guards before tagging.

### FR6 — CI behavior unchanged (no content invention)

Automated Pages/build jobs continue to build and deploy whatever is already committed under the demo vault. They do not run synthesis and do not invent demo sessions or usage fixtures.

- **Acceptance Criteria:**
  - [ ] Given a tag push triggers Pages, when the workflow runs, then it still only builds/deploys committed demo content (plus existing version assert) and does not add a new step that generates sessions or usage.

---

## 3. Scope and Boundaries

### In-Scope

- Updating the release skill and maintainer release checklist for usage regeneration, local demo build URL, and human review pause before tag push
- Clarifying in those docs that CI/Pages only deploy + version-assert committed demo content
- Calling out post-harvest case-fold / demo guards before tagging
- Tests or doc-acceptance checks that lock the new checklist obligations where the repo already patterns that style
- CHANGELOG / maintainer-facing notes for the workflow change

### Out-of-Scope

- Re-implementing Home Timeline packaging for demo (already done via committed demo state — #254 / #255)
- Changing Pages to invent or seed ops stamps in CI (options B/C from the issue — not chosen; option A already shipped)
- Automating the human’s browser review or auto-approving the gate
- Changing how real (non-demo) vaults treat gitignored state files
- Cutting an actual product version tag as part of this feature PR
- Closing or re-litigating #225’s broader historical docs backlog; this cut only requires refresh completeness for what this release touched
