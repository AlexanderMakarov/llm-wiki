# Functional Specification: Per-vault quality-check scoping

- **Roadmap Item:** Per-vault lint rule scoping (#150) — let the demo enforce warnings without inheriting rules that do not apply to it.
- **Status:** Completed
- **Author:** 4ellendger

---

## 1. Overview and Rationale (The "Why")

The product ships a small example wiki so newcomers can see a finished result without running anything. That example is published with the project and re-checked automatically on every change, so a broken example never reaches a new user.

Today that automatic check only stops the project on a **serious** problem. Problems graded **worth-a-look** are printed and ignored. That compromise was recorded deliberately, because one worth-a-look check asks *"has this page gone untouched for three months?"* — and the published example is a frozen snapshot, so that question answers itself with the passage of time. Enforcing worth-a-look problems would redden the project on a calendar date rather than on a defect.

Investigating what it would actually take to lift that compromise turned up something larger. The example currently reports **120 broken cross-reference warnings**, and the same shape appears at scale on a real working wiki (**650** on a 717-page vault). None of them are rot. They come from four parts of the product disagreeing about what an unmaterialized cross-reference means:

- The page-writing step names every topic it recognises and cross-references it, because the wiki's own rules say to cross-link everything.
- The topic-collection step only creates a page for a topic **named by three or more pages**. Every topic named once or twice is deliberately left without one.
- The site builder treats those same names as real topics and renders topic pages for them.
- The quality check calls every one of them a **broken link**.

The quality check is the only part that considers them defects, it is worth-a-look severity, and that is the actual reason the example cannot enforce worth-a-look problems. Three components share a threshold; the fourth has never been told about it.

Once the quality check honours the same threshold the topic-collection step uses, the example reports **zero** broken cross-references at stock settings, a real wiki drops from 650 to 256 — and the 256 that remain are genuine: topics named often enough to deserve a page that never got one.

What is left after that on the example is three flagged "conflicting-claims" sections. Two are the check misreading boilerplate. **The third is a real documentation defect**: the installation guide requires Python 3.12 in its header while telling the reader to expect 3.9 or newer, and the project genuinely requires 3.12. The check found a live bug on its first enforced run, which is the clearest possible argument for enforcing it.

Two constraints shape the design:

- **A silenced check must never look like a passing check.** Otherwise this trades a noisy gate for a dishonest one.
- **New checks must arrive switched on.** A list of checks to *keep* would leave every later-added check unenforced with nobody noticing. A list of checks to *skip* does not.

The published example is held to **stock settings throughout** — a good example is representative, so it configures nothing it does not have to. Its only declared opt-out is the calendar-based staleness question, which cannot apply to a frozen snapshot. Refreshing the example more often remains the honest cure for staleness and is tracked separately.

**Success looks like:** the example is checked on every change with worth-a-look problems enforced, at stock settings, with exactly one declared opt-out; every report says out loud what it skipped; and someone who wants the same for their own wiki can find out how from the documentation.

---

## 2. Functional Requirements (The "What")

### R1 — A wiki can declare which quality checks do not apply to it

- **As** someone who keeps a wiki, **I want to** record inside my wiki the checks that are meaningless for it, **so that** I can hold the wiki to every other check without being drowned by findings I have already judged irrelevant.
  - The declaration lives with the wiki, not with the person or the machine. Copying, sharing, or publishing the wiki carries it along.
  - It lists checks to **switch off**. There is no way to make a check louder or quieter — only on or off.
  - Each switched-off check may carry a short written reason.
  - **Acceptance Criteria:**
    - [x] Given a wiki that declares no opt-outs, when quality checks are run, then the results are exactly what they were before this feature existed.
    - [x] Given a wiki that declares the staleness check as not applicable, when quality checks are run, then no staleness findings appear anywhere in the results.
    - [x] Given two wikis where only one declares an opt-out, when each is checked in turn, then the opt-out affects only the wiki that declares it.
    - [x] Given a declaration carrying a written reason, when quality checks are run, then that reason is shown to the person reading the results.

### R2 — A skipped check is never mistaken for a passing check

- **As** anyone reading a quality report, **I want** every skipped check named, **so that** a clean result can never quietly mean "almost nothing was actually checked".
  - **Acceptance Criteria:**
    - [x] Given a wiki that switches off one or more checks, when quality checks are run, then the report names every switched-off check, whether or not problems were found.
    - [x] Given the same wiki, when results are requested in machine-readable form, then the switched-off checks appear there too, alongside the findings.
    - [x] Given a wiki that switches off every available check, when quality checks are run, then the report states plainly that nothing was checked, rather than reporting a clean wiki.

### R3 — A misspelled or retired check name is reported, not silently ignored

- **As** someone editing my wiki's declaration, **I want to** be told when I name a check that does not exist, **so that** a typo cannot leave a check switched on that I believed I had switched off.
  - **Acceptance Criteria:**
    - [x] Given a declaration naming a check that does not exist, when quality checks are run, then the run stops with a message naming the unrecognised entry and listing the valid names.
    - [x] Given that same declaration, when the run stops, then no quality result is reported as clean.

### R4 — The cross-reference check honours the same significance threshold the rest of the product uses

- **As** someone reading a quality report, **I want** a cross-reference to a topic the product deliberately declined to give a page to **not** to be reported as broken, **so that** the report shows failures rather than design decisions, and becomes worth enforcing.
  - The product already has a setting for how many pages must name a topic before it earns one. The cross-reference check honours that same setting, from a single shared definition of the stock value, so the two can never disagree.
  - A cross-reference to a topic that **no** page contributing to the count names at all is always reported. Nothing was ever going to create a page for it, so it was never a decision — it is simply a dangling reference.
  - A cross-reference to a topic named **fewer** times than the threshold is expected and is not reported. That one *was* a decision.
  - A cross-reference to a topic named **at least** as often as the threshold, with no page, **is** reported — that is a genuine gap.
  - The threshold can be stated when running the check, and is otherwise the stock value.
  - **Acceptance Criteria:**
    - [x] Given the published example at stock settings, when quality checks are run, then zero broken cross-references are reported.
    - [x] Given a wiki containing a topic named by at least the threshold number of pages with no page of its own, when quality checks are run, then that cross-reference is reported.
    - [x] Given a wiki containing a cross-reference to a topic that nothing else names, when quality checks are run at **any** threshold including the stock one, then that cross-reference is reported.
    - [x] Given the same wiki, when quality checks are run with the threshold lowered to one, then every unmaterialized cross-reference is reported.
    - [x] Given the threshold is not stated when running the check, when quality checks are run, then the value used matches the one the topic-collection step uses by default, with no second place to change it.

### R5 — The significance threshold is settable wherever topics are collected

- **As** someone running the whole pipeline in one command, **I want** the threshold I chose to be the one that is used, **so that** running the steps together does not silently behave differently from running them separately.
  - **Acceptance Criteria:**
    - [x] Given the full pipeline run with a stated threshold, when it collects topics, then it uses the stated threshold and not the stock value.
    - [x] Given the full pipeline run with no stated threshold, when it collects topics, then it uses the stock value.
    - [x] Given the same wiki and the same threshold, when topics are collected via the full pipeline and via the individual step, then both produce the same result.

### R6 — Quality checks can be told to fail on worth-a-look problems too

- **As** someone gating a change on wiki quality, **I want to** ask for worth-a-look problems to stop the gate as well as serious ones, **so that** they block a change instead of scrolling past in the output.
  - A choice made when running the check. The default is unchanged: only serious problems stop the gate.
  - **Acceptance Criteria:**
    - [x] Given a wiki whose only problems are worth-a-look ones, when checks are run in the default way, then the problems are reported and the gate is not stopped.
    - [x] Given the same wiki, when checks are run with the stricter choice, then the problems are reported and the gate is stopped.
    - [x] Given a wiki with no problems, when checks are run with the stricter choice, then the gate is not stopped.
    - [x] Given a wiki that switches off the only check producing worth-a-look problems, when checks are run with the stricter choice, then the gate is not stopped.

### R7 — The conflicting-claims check stops flagging boilerplate

- **As** someone reading a quality report, **I want** a section that says "nothing to record" to be recognised as such, **so that** enforcing this check does not punish pages that are in fact clean.
  - **Acceptance Criteria:**
    - [x] Given a page whose conflicting-claims section opens by stating nothing was found and then explains why in wording that mentions conflicting with earlier entries, when checks are run, then the page is not flagged.
    - [x] Given a page whose conflicting-claims section states nothing is evident, when checks are run, then the page is not flagged.
    - [x] Given a page that records a real conflict between two claims, when checks are run, then the page is still flagged.

### R8 — The published example passes an enforced gate at stock settings

- **As** a newcomer, **I want** the example wiki to be held to the project's own standards, **so that** my first impression is not an example containing the defects the product exists to catch.
  - The example declares the staleness question as not applicable, with a written reason, and configures nothing else.
  - The automatic check of the example is tightened so worth-a-look problems stop the project.
  - The real documentation defect the check surfaced — the installation guide naming two different minimum Python versions — is corrected so the guide agrees with what the project actually requires.
  - **Acceptance Criteria:**
    - [x] Given the example as it stands after this work, when its automatic quality check runs with worth-a-look problems enforced, then it passes.
    - [x] Given the example, when its automatic check runs, then the output names the staleness check as switched off and gives the recorded reason.
    - [x] Given a change that introduces a cross-reference to a topic named often enough to deserve a page, when the automatic check runs, then it stops the project.
    - [x] Given the example left untouched for more than three months, when the automatic check runs, then it still passes.
    - [x] Given the installation guide, when a reader compares the minimum Python version in its header, its verification step, and what the project requires, then all three agree.

### R9 — An agent asking about wiki quality gets the same answer a person does

- **As** someone who works through an assistant, **I want** the quality report my assistant sees to be the same report I would see myself, **so that** we are not quietly working from two different accounts of the same wiki.
  - Today the assistant-facing route runs its own smaller, stricter set of checks and reports different results for the same wiki. After this work both routes run the same checks, honour the same opt-outs, and produce the same findings.
  - The assistant-facing route's own description of what it checks must match what it actually checks.
  - **Acceptance Criteria:**
    - [x] Given any wiki, when quality is requested through the assistant-facing route and directly, then both report the same findings and the same skipped checks.
    - [x] Given the same unchanged wiki, when quality is checked repeatedly, then the report is identical every time — including the order findings are listed in. Two runs that disagree only about ordering still read as a difference to anyone comparing them, so "the same report" has to mean the same report.
    - [x] Given a wiki that switches a check off, when quality is requested through the assistant-facing route, then that check is skipped there too and named as skipped.
    - [x] Given the assistant-facing route's own description of what it checks, when compared against what it runs, then they agree.
    - [x] Given the change alters what the assistant-facing route returns, when a reader consults the release notes and the upgrade guide, then the change is described there.

### R10 — The feature is documented where someone would look for it

- **As** someone who wants the same for my own wiki, **I want** written instructions, **so that** I do not have to read the product's source code to find out this is possible.
  - The documentation covers where the declaration goes, what it may contain, and how to name a check.
  - It states the risk plainly: switching a check off hides real problems, so it is for checks that cannot apply to a wiki — not for checks that are merely inconvenient.
  - It explains the significance threshold's effect on the cross-reference check, so a reader who lowers the threshold understands why more findings appear.
  - **Acceptance Criteria:**
    - [x] Given the project's documentation, when a reader looks for how to switch a quality check off, then they find instructions including a complete worked example.
    - [x] Given those instructions, when a reader follows them exactly against a fresh wiki, then the named check is switched off and the report says so.
    - [x] Given the documentation, when a reader looks for the caution, then they find a stated warning that switching a check off hides real findings.
    - [x] Given the documentation, when a reader looks for why lowering the significance threshold produces more cross-reference findings, then it is explained.

---

## 3. Scope and Boundaries

### In-Scope

- A written declaration, carried inside a wiki, listing quality checks that do not apply to it, each with an optional reason.
- Skipped checks named in both the human-readable report and the machine-readable results.
- A clear failure when the declaration names a check that does not exist.
- The cross-reference check honouring the topic-significance threshold, from a single shared definition of the stock value, with the threshold statable at run time.
- The threshold reaching the topic-collection step on the full-pipeline path as well as the individual one.
- A run-time option to let worth-a-look problems stop the gate.
- Boilerplate fixes to the conflicting-claims check so "nothing evident" and "nothing found, because…" wording is recognised.
- The published example declaring the staleness check not applicable — and nothing else — plus its automatic check tightened to enforce worth-a-look problems.
- Correcting the minimum-Python-version disagreement in the installation guide that the enforced check surfaced.
- The assistant-facing quality route reporting exactly what the direct route reports, with its description corrected to match, and the change to what it returns announced in the release notes and upgrade guide.
- Documentation covering all of the above, including the caution about hiding real findings.

### Out-of-Scope

- **Changing how loud a check is.** A wiki may switch a check off; it may not re-grade a problem's severity.
- **Switching a check off for part of a wiki.** Opt-out is all-or-nothing per wiki.
- **A machine-wide or per-person opt-out list.** The declaration belongs to the wiki.
- **Changing the staleness check's three-month threshold.**
- **Changing what the published example contains, or how often it is refreshed.** The example is used at stock settings; its refresh cadence is a separate concern.
- **Making an unmaterialized cross-reference readable on the site.** After this work such a reference is correctly no longer a *lint* finding, but a reader clicking it still arrives nowhere. Resolving those against the topic pages the site already builds is worth its own issue and is not attempted here.
- **Clearing the genuine cross-reference gaps this surfaces on a real working wiki** (256 topics named often enough to deserve a page that do not have one). The check will now report them honestly; acting on them is the operator's review work, not this change.
- **Rewriting or unlinking cross-references in already-written pages.** Rejected: replacing a cross-reference with plain text is irreversible without a full re-synthesis, since nothing marks where the reference used to be.
- All other roadmap items, addressed in their own specifications — notably honest `--estimate` candidate preview (#113), broken docs links (#107), the dead comparison surface (#138), one project one page (#126), the candidate-review correctness group (#146, #139, #148, #149), operator privacy and test isolation (#141, #142), the migration inventory group, the self-explanatory product group (#109, #112), and the guided health check (#110).
