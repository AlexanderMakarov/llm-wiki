# Functional Specification: Show each topic's known kind when synthesizing a source

- **Roadmap Item:** GitHub Issue [#257](https://github.com/AlexanderMakarov/llm-wiki/issues/257) — when synthesis writes a source summary, the model must see whether each already-known name is a person/product or an idea, so Connections labels stay exact and free-form kinds stop filling the paid rewrite backlog. Complements offline kind stamping ([#174](https://github.com/AlexanderMakarov/llm-wiki/issues/174)) and does not replace known-names performance work ([#264](https://github.com/AlexanderMakarov/llm-wiki/issues/264)).
- **Status:** Approved
- **Author:** Alexander Makarov

---

## 1. Overview and Rationale (The "Why")

Source summaries are supposed to name each important person, product, or idea with a short label that is only one of two values: person/product, or idea. Those labels feed later collection of pending names. Today the start-of-run “what names do we already know?” step already classifies many topics that way, and many names already have a page filed under people/products or ideas — but the list shown to each source-summary pass does not carry that classification. The model then invents labels like “(desktop environment)”. Pages with only bad labels look unfinished, stay in the synthesis backlog, and cost another full paid rewrite.

**Desired outcome:** every source-summary pass sees each listed topic’s known kind when the wiki already knows it (from the known-names list, or from where the topic’s page is filed). Prompt rules say the parentheses may only be person/product or idea, and must copy the listed kind when linking a listed topic. Operators who already have summaries that only lack kinds clear that backlog with the existing offline stamp instead of re-paying for a full rewrite. Docs make the difference clear between preparing known names and collecting pending candidate stubs.

**Success is measured by:** a normal synthesis of a topic that already has a known kind produces a Connections bullet using that kind; free-form kind nouns no longer appear as the intended shape; pages that only needed kinds are stamped offline without a language-model rewrite; docs name both harvest-related steps without conflating them.

---

## 2. Functional Requirements (The "What")

### FR1 — Known topics show their kind in the vocabulary for each source pass

- **As an** operator running synthesis, **I want** the existing-topics list given to each source summary to include each topic’s known kind when the wiki already knows it, **so that** the model does not invent a free-form type in parentheses.

Kind resolution order (operator-visible outcome): if the start-of-run known-names list has a kind, use it; else if the topic already has a page under people/products or ideas (including pending review stubs of those kinds), use that filing; else omit kind for that row.

- **Acceptance Criteria:**
  - [ ] Given a topic whose known-names entry already carries person/product or idea, when a source is synthesized with that vocabulary, then that topic’s vocabulary row exposes that kind.
  - [ ] Given a topic with no known-names kind but a page filed under people/products or ideas (or a matching pending stub), when vocabulary is built, then that topic’s row still exposes the matching kind from the filing.
  - [ ] Given a topic with neither a known-names kind nor such a page, when vocabulary is built, then that row may omit kind (name and other hints remain).

### FR2 — Prompt rules forbid free-form kinds and require copying listed kinds

- **As an** operator, **I want** the synthesis instructions to say that Connections parentheses may only be person/product or idea, and that linking a listed topic must reuse that topic’s listed kind, **so that** models stop inventing type nouns.

- **Acceptance Criteria:**
  - [ ] Given the source-summary prompt text after this change, when an operator (or a test) reads the rules and the existing-topics guidance, then it states that parentheses must be exactly the person/product or idea labels (no free-form type nouns).
  - [ ] Given the same prompt text, when a listed topic carries a kind, then the instructions tell the model to copy that kind when linking that topic.

### FR3 — A normal synth on a known-kind topic writes that kind on the Connections bullet

- **As an** operator, **I want** a normal synthesis of a session that links a vocabulary topic with a known kind to emit a Connections bullet using that kind, **so that** the page clears the “needs topic shape” rewrite path without a second paid pass for labels alone.

- **Acceptance Criteria:**
  - [ ] Given a fixture or dummy synthesis where the vocabulary includes a topic with a known kind and the model (or fixture reply) links that topic, when the written source page is inspected, then the Connections bullet for that topic uses that kind — not a free-form parenthetical.

### FR4 — Offline kind stamp remains the cheap path for pages that only lack kinds

- **As an** operator whose backlog is mostly summaries that only lack kinds, **I want** the existing offline topic-kind stamp to remain the recommended way to clear those pages without a full language-model rewrite, **so that** fixing labels alone does not force another paid synth.

This requirement does not invent a new stamp command; it keeps and documents the path shipped for [#174](https://github.com/AlexanderMakarov/llm-wiki/issues/174).

- **Acceptance Criteria:**
  - [ ] Given source pages that only lack usable kinds on Connections and whose targets already have matching wiki filings, when the operator runs the existing topic-kind migration, then those pages gain kinds and are no longer forced through a full language-model rewrite solely for missing kinds.
  - [ ] Given docs touched by this work, when the operator reads the upgrade or CLI guidance for this problem, then they are pointed at that offline stamp for label-only catch-up.

### FR5 — Docs distinguish preparing known names from collecting candidate stubs

- **As an** operator reading product docs, **I want** clear wording that the start-of-run known-names preparation (designed “harvest” of vocabulary) is not the same step as the later offline collection of pending candidate stubs (`synth` harvest / candidates-only), **so that** I do not confuse cost, timing, or what each step writes.

- **Acceptance Criteria:**
  - [ ] Given the CLI reference (and any tutorial line this change updates), when the operator reads the synthesis section, then both steps are named and contrasted in plain language — known-names preparation vs candidates collection — without treating them as one command stage.

---

## 3. Scope and Boundaries

### In-Scope

- Carrying known kind into the per-source vocabulary the model sees (known-names first; else page/pending filing).
- Tightening source-summary prompt rules for Connections kinds.
- Tests that prove vocabulary injection and/or a sample Connections bullet uses the known kind (dummy or prompt-inspection fixture).
- Docs clarifying known-names preparation vs candidates harvest, and pointing label-only catch-up at the existing offline stamp.
- CHANGELOG / upgrade notes as needed for the user-visible prompt and docs change.

### Out-of-Scope

- **[#264](https://github.com/AlexanderMakarov/llm-wiki/issues/264)** — bounding or speeding known-names preparation (candidate cap, incremental reuse, separate timeout, richer timing report). That work changes how/when the known-names list is built; this work changes what each source pass is told about kind. They compose: a capped or timed-out known-names run still benefits from page-filing kind fallback (FR1). Do not implement #264 here.
- Changing how pending candidates are collected or reviewed.
- Replacing or redesigning the offline topic-kind migration (#174 already shipped).
- Changing Key Claims, Key Quotes, or other source-page sections.
- Live-vault mutation as part of automated verify (throwaway vault / fixtures only).

### Compatibility note on #264

[#264](https://github.com/AlexanderMakarov/llm-wiki/issues/264) explicitly lists #257 as related and does not redefine Connections shape. No acceptance criterion in #264 removes kinds from the cache or vocabulary. Implementing #257 first does not block #264; implementing #264 later must keep exposing kind on cached entries so FR1 still holds. If a future #264 design drops kind from reuse, that would be a regression against this spec and must be rejected or amended here first.
