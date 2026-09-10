# Functional Specification: Search Command and Findability Checks

- **Roadmap Item:** Quality gate for wiki retrieval — issue [#197](https://github.com/AlexanderMakarov/llm-wiki/issues/197)
- **Status:** Approved
- **Author:** 4ellendger

---

## 1. Overview and Rationale (The "Why")

### The problem

A vault's whole promise is that what went into it can be got back out. Nothing checks whether that holds.

Two past changes to result ordering shipped on argument alone, with no before-and-after number. A change that quietly halved how much of a vault could be found would pass every check that exists today. The existing automated checks measure how *fast* a vault builds and how *large* it is — never whether anything in it can be found.

There is also no way for a person to search their own vault outside an agent. The search agents use is reachable only through the agent interface; someone at a terminal has no equivalent.

### What we are actually measuring

An early version assumed the thing worth measuring was the ordering logic. Tracing the behaviour showed otherwise: there are only two ordering knobs, and a page's own name outweighs its contents by roughly twenty-five to one. Whether the right page comes back is decided almost entirely by **whether the page exists and what synthesis chose to call it** — by how the vault was *built*, not by how it is searched.

Measurements on two vaults bear this out, and separate three claims of very different strength:

| Claim | Measured | Treatment |
|---|---|---|
| A page is findable by its own name | 203/203 demo, 150/150 sampled live | **Error** — no tolerance |
| Search agrees with a literal scan of the vault | 40/40 terms, zero disagreements | **Error** — no tolerance |
| A page is *first* for its own name | ~94–96% | **Warning** — the rest are vault defects |
| A term in a session survives into a wiki page | **78%** | **Reported number** — never a failure |

That last row is the important one. Synthesis summarises rather than preserves, so nearly a quarter of what is said in a session legitimately never reaches a wiki page. Treating that as a defect would produce a check that fails constantly; treating it as a measured rate makes visible, for the first time, how much knowledge the pipeline drops.

### Desired outcome

Anyone with a vault can:

1. Search it from a terminal, the same way an agent does.
2. Check lists of terms or phrases in bulk — once with what they expect to find, again with what they expect not to.
3. Get an automatic health measurement that checks not only page names but **session content**, and that shows which terms it used.

And the project can catch a regression in the change that caused it.

### How we will know it worked

- Two runs over an unchanged vault produce identical results.
- Every demo page stays findable by its own name, and search never disagrees with a literal scan.
- Terms deliberately planted in demo sessions are found; terms deliberately absent are not.
- Checking a whole vault takes seconds, not minutes.

---

## 2. Functional Requirements (The "What")

### R1 — A search command

A new `search` command searches a vault the way an agent does and prints results as a list — matching pages, best first, in the shape the agent interface already returns. It is not a report and not a table.

Two modes:

- **term** — one word or fragment, matched literally wherever it occurs.
- **phrase** — several words, where pages containing the whole phrase rank above pages containing only some of them.

Both modes accept **bulk input**: a list of terms, or a list of phrases, run one after another with results reported per entry. Someone verifying a vault runs it once with a list they expect to find and again with a list they expect not to — one list per run.

It targets any vault by location, defaults to the configured one, and never modifies what it reads.

- **Acceptance Criteria:**
  - [ ] A single term prints matching pages best-first, or states plainly there were none.
  - [ ] Phrase mode ranks pages containing the whole phrase above pages containing only some of its words.
  - [ ] A supplied list of **terms** runs every entry and reports results per entry, making it obvious which found nothing.
  - [ ] A supplied list of **phrases** does the same, in phrase mode.
  - [ ] Any vault can be searched by naming its location, without editing configuration.
  - [ ] Nothing in the vault is written, appended to, or otherwise changed.
  - [ ] Naming somewhere that is not a vault produces a clear explanation, not an unhandled failure.
  - [ ] Results match what the agent interface returns for the same input.
  - [ ] The existing natural-language graph query command is unchanged.

### R2 — The answer key is derived from the vault

The automatic checks need no prepared data and no supplied lists. Every vault contains its own answer key in three forms:

- **Every page's own name is a lookup with a known answer** — asking for a page by its title must return it.
- **Every cross-reference is an authored answer** — a link naming another page asserts that this name identifies that page. The link text is the lookup; the resolved page is the answer.
- **A literal scan of the vault is an oracle** — whether a string occurs in the vault's files is a fact that can be established without search, and search must agree with it.

Cross-references resolve exactly as the knowledge-graph view resolves them, including alternate names, so the two can never disagree.

- **Acceptance Criteria:**
  - [ ] Checks run against any vault with no prepared data and no supplied lists.
  - [ ] A cross-reference written with an alternate name is credited to the page it resolves to, matching the knowledge-graph view.
  - [ ] Pages in cold storage are excluded, exactly as search excludes them.
  - [ ] Two runs over an unchanged vault produce identical lookups in an identical order.

### R3 — Health checks

Three checks are added to the existing health check. Named exactly:

#### `page_findability` — error

A page with a title is not returned at all when searched for by that title. A page cannot fail to match its own name unless something is genuinely wrong — measured at 203/203 and 150/150 on two vaults.

- **Acceptance Criteria:**
  - [ ] Reported as an error naming the page.
  - [ ] The reason is stated — for example that results were cut short before reaching it — not merely that it failed.
  - [ ] Reports nothing on the demo vault and on a healthy real vault.

#### `title_ambiguity` — warning

A page is not the *first* result for its own title. About one page in twenty; in every case examined the vault was at fault rather than search — a title that is a substring of another page's title, a near-duplicate differing only in capitalisation, or a name so generic it appears everywhere.

- **Acceptance Criteria:**
  - [ ] Reported as a warning against the page.
  - [ ] The message names the page that outranked it, which is the actionable part.

#### `search_consistency` — error

Search must agree with a literal scan of the vault, over both wiki pages **and session content**. The check picks a sample of real terms out of the vault's own raw sessions, generates synthetic terms that do not occur anywhere, establishes by literal scan which of each group is genuinely present, and requires search to return exactly the present ones and none of the absent ones.

This is what extends the measurement beyond page names to what sessions actually said. Measured at 40/40 agreement with zero disagreements, and 5/5 synthetic absences correctly returning nothing.

Alongside the pass/fail result it reports the **share of sampled session terms that survived into a wiki page** — measured at 78%. This is a reported number and never a failure: synthesis summarises rather than preserves, so a term not surviving is normal. It is the first visibility into how much the pipeline drops.

- **Acceptance Criteria:**
  - [ ] A term the literal scan finds, that search does not return, is an error.
  - [ ] A term the literal scan cannot find, that search does return, is an error.
  - [ ] **Every term used is shown to the person running it**, in both groups, so the result can be checked by hand.
  - [ ] The survival share is reported as information and never fails the check.
  - [ ] Sampling is deterministic — the same vault yields the same terms every run.
  - [ ] Session content is covered, not only wiki pages.

All three checks read only, never modify a page, and are individually selectable and skippable like every existing check. Adding them must not disproportionately slow the health check, which already takes about 20 seconds on a large vault.

### R4 — Checking a whole vault takes seconds

Every search reads the whole vault, so checking pages one at a time would take minutes. Measured on a 918-page vault: one search per page title takes **6.4 minutes**; reading the vault once and evaluating every lookup against what was read takes **about 8 seconds**.

Checks must read the vault once per run, not once per lookup — and must reuse the **same scoring behaviour real search uses**, not a reimplementation. A separate copy would drift, and a drifting check is worse than none.

- **Acceptance Criteria:**
  - [ ] Checking a vault of roughly 900 pages completes in seconds.
  - [ ] Results are identical to what ordinary search returns for the same lookups — verified by comparison, not assumed.
  - [ ] Ordinary search behaviour is unchanged by whatever makes this possible.
  - [ ] Adding a way of searching in future does not require the scoring logic to be written twice.

### R5 — Planted and synthetic terms are produced when demo sessions are generated

The demo session generator produces, alongside the sessions themselves, the two term groups the project's own verification needs:

- **Terms and phrases that must be found** — distinctive single words *and* multi-word phrases planted into authored sessions at known positions (the session's name, a user's message, an assistant's reply, reported tool output) across the different agent tools the demo represents. Because the position and agent tool of each is known, survival can be reported broken down both ways. Phrases are included so that both ways of searching are exercised, not only the single-word one, and each phrase is chosen so its individual words also appear separately elsewhere — otherwise finding the phrase would prove nothing about phrase handling.
- **Terms and phrases that must not be found** — synthetic ones confirmed absent from the whole vault by literal scan at generation time.

Both groups are written out when the sessions are generated and kept with the project, so verification never has to scan the vault to rediscover them.

Planted terms must not damage the demo, which is published and read by people evaluating the project: they must read as plausible subject matter rather than visible test scaffolding, and must not resemble the personal identifiers the project forbids from committed files. The generator is deterministic and re-runs when a release is cut, so the same term must land in the same place every time.

- **Acceptance Criteria:**
  - [ ] Each planted term or phrase appears in exactly one position in one session, so a result is unambiguous about where it came from.
  - [ ] Both groups contain single words and multi-word phrases, so both ways of searching are covered.
  - [ ] Each planted phrase has individual words that also occur separately elsewhere in the vault.
  - [ ] Both groups are produced by the generator and kept with the project.
  - [ ] Synthetic absent entries are confirmed absent by literal scan at generation time.
  - [ ] Survival is reported broken down by position and by agent tool, not only as one overall number.
  - [ ] Regenerating the demo sessions produces the same terms in the same places.
  - [ ] A demo transcript reads as plausible subject matter, not visible test scaffolding.
  - [ ] The checks guarding committed files against personal identifiers still pass.

### R6 — The project's own verification, exact and without thresholds

Separate from R3: those are a feature people run on their own vaults; this is the project's protection against shipping a regression. It runs in automation, where nothing can be written or recorded back — so everything it compares against is prepared in advance by R5 and kept with the project.

Verification reads the two prepared term groups and asserts:

- Every term that must be found is found.
- No term that must not be found is returned.
- Every titled demo page is findable by its own name.
- The overall ranking figure matches its recorded value exactly.

Because the demo vault is committed and search is deterministic, these are exact comparisons. No tolerance is used and none is needed. A deliberate change to the demo corpus changes the recorded values, and a person updates them as part of that change.

Where a headline number is useful, the meaningful ones are the share of pages found, the share ranked first, and the mean reciprocal rank. Precision, recall, F1 and nDCG are **not** reported: every derived lookup has exactly one correct answer, so those collapse into "is the answer at rank ≤ k" and would state one fact four times. Where a cutoff is used it is **top-1** and **top-5** — top-5 because that is what the agent interface returns by default. This is a deliberate departure from the metric list in #197, made because the ground truth turned out to be single-answer.

- **Acceptance Criteria:**
  - [ ] Verification runs in the project's normal test run with no extra installation step.
  - [ ] It reads only prepared data and never needs to write or record anything, so it works in automation.
  - [ ] A demo page becoming unfindable by its own name fails it.
  - [ ] A planted term becoming unfindable fails it.
  - [ ] A synthetic absent term starting to return results fails it.
  - [ ] A change in the recorded ranking figure fails it, in either direction.
  - [ ] Recorded values are kept with the project and readable by a person.
  - [ ] Repeated runs on an unchanged project produce identical results and never fail intermittently.

### R7 — Documentation

User-facing documentation describes current behaviour only, with no history of what changed or why.

- **Acceptance Criteria:**
  - [ ] The `search` command is documented: both modes, bulk lists of terms and of phrases, and targeting a vault by location.
  - [ ] Documentation explains the behaviour as a pre-AI-era search engine — score-weighted matching of the literal characters typed, found anywhere including inside longer words, with no meaning-based matching and no spelling correction.
  - [ ] That consequence is stated plainly with an example: a short term matches inside longer words.
  - [ ] Documentation distinguishes `search` from the existing natural-language graph query command.
  - [ ] The three checks are documented by name alongside the existing ones: `page_findability`, `title_ambiguity`, `search_consistency`.
  - [ ] The reported survival share is explained as information rather than a defect.
  - [ ] The existing performance-and-size reference gains a findability section.
  - [ ] Rationale, alternatives and history live in maintainer documentation, not user-facing pages.

---

## 3. Scope and Boundaries

### In-Scope

- A `search` command with term and phrase modes, single and bulk input for both, targeting any vault read-only.
- An answer key derived from page titles, cross-references, and a literal scan of the vault.
- Three named health checks: `page_findability` (error), `title_ambiguity` (warning), `search_consistency` (error).
- Coverage of session content, not only page names, with every term used shown to the person running it.
- Reporting the share of session terms surviving into wiki pages, as information.
- Reading a vault once per run and sharing scoring behaviour with real search.
- Generator-produced term groups — planted and synthetic-absent — kept with the project.
- Exact, threshold-free verification in the project's own test run.
- User documentation for the command and checks; rationale in maintainer documentation.

### Out-of-Scope

- **Changing how results are ordered** — with one narrow exception recorded below. This work only measures and exposes.
- **Failing on knowledge lost in synthesis.** Measured at 78% survival, so loss is normal; it is reported, never a defect.
- **The in-browser search box and anything on the published site.** Nothing is added to generated pages. The browser surface also indexes an almost entirely different corpus — see [#248](https://github.com/AlexanderMakarov/llm-wiki/issues/248) — so one answer key could not describe both.
- **Search speed and the corpus-size limit.** Tracked as [#244](https://github.com/AlexanderMakarov/llm-wiki/issues/244). R4 makes *checking* fast; it does not make search fast.
- **Changing the existing graph query command**, which keeps its behaviour and optional dependency.
- **Precision, recall, F1 and nDCG as reported metrics** — degenerate against single-answer ground truth, as recorded in R6.
- **Tolerances and thresholds.** Deterministic search over a committed vault makes exact assertions possible.
- **Cold-storage lookups.** The demo vault has no cold storage to point at; deferred until it does.
- **Meaning-based search, spelling correction, and stemming.** Separate proposals.
- **The quality of written answers.** This measures which pages are found, not how well anything is summarised.
- All other roadmap items, addressed in their own specifications.

---

### Amendment: one ordering fix is in scope

Ordering changes are excluded above, with a single exception found while designing the implementation.

Phrase-mode results are ordered by score alone. When two pages score *equally*, which comes first is decided by the order the operating system happens to list files in — so the same vault can order results differently on different machines. On the demo vault, 199 of 203 page-name lookups contain a tie somewhere in their results, and one has its top two tied.

Results are therefore ordered by score and then by page location, so equally-scored pages always appear in the same order. This changes nothing about scores and nothing about the relative order of pages that score differently.

It is in scope because the feature cannot otherwise be delivered: [#197](https://github.com/AlexanderMakarov/llm-wiki/issues/197) requires re-running the measurement to be deterministic, and the health check that names which page outranked another cannot give a stable answer while that answer depends on filesystem order.

---

## 4. Open Questions

- **Mode names.** "term" and "phrase" describe the behaviours; the technical design settles what they are called on the command line and how they map to the agent interface's existing modes.
- **Sample size for `search_consistency`.** Large enough to be meaningful, small enough not to slow the health check; settled in technical design against the 20-second budget.
