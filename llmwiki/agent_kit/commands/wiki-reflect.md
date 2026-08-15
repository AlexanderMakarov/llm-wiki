Run a self-reflection pass over the whole wiki — look for patterns, gaps, and improvement opportunities.

Usage: /wiki-reflect [focus-area]

`$ARGUMENTS` is an optional focus hint: `patterns`, `gaps`, `quality`, `contradictions`, or omit for a general pass.

Unlike `/wiki-lint` (which finds structural issues) or `/wiki-query` (which answers one question), `/wiki-reflect` asks the higher-order question: **what is this wiki trying to say, and what's missing?**

## Steps

1. **Read `wiki/index.md` and `wiki/overview.md`** to get the current synthesis.

2. **Read every page under `wiki/sources/`, `wiki/entities/`, and `wiki/concepts/`** — or a representative sample if there are more than 50 pages.

3. **Look for:**
   - **Recurring themes** that span multiple sources — candidates for new concept pages
   - **Implicit comparisons** where two entities or concepts keep appearing together — candidates for a `wiki/concepts/` page that names the trade-off
   - **Unanswered questions** mentioned in multiple sources — candidates for a `wiki/syntheses/` page once answered
   - **Evolution over time** — how has the user's thinking on a concept changed?
   - **Contradiction clusters** — pages that disagree on the same point
   - **Orphan themes** — interesting ideas mentioned once then never again
   - **Missing entities** — people, tools, or projects mentioned in 3+ sources without their own page

4. **Synthesise a 3-5 paragraph reflection** structured as:
   - **What the wiki knows well** — the most-covered topics, the strongest signal
   - **What the wiki is missing** — gaps that reflection surfaced
   - **Suggested next actions** — new pages, new queries, or new sources to ingest

5. **Ask the user** whether to:
   - Save the reflection as `wiki/syntheses/reflection-<YYYY-MM-DD>.md`
   - Open GitHub issues for any "new page" suggestions
   - Schedule a `/wiki-ingest` of any missing sources the reflection identified

6. **Append to `wiki/log.md`**:
   ```
   ## [YYYY-MM-DD] reflect | <short summary of findings>
   ```

## Focus-area hints

| Hint | What to emphasise |
|---|---|
| `patterns` | Recurring themes, clusters, evolution over time |
| `gaps` | Missing entities/concepts, unanswered questions |
| `quality` | Stale summaries, weak writing, duplicated effort |
| `contradictions` | Disagreements across pages, unresolved claims |
| *(none)* | A general pass — briefly touch each of the above |

## Hard rules

1. **Don't edit pages during reflection.** Reflection is read-only. Any changes are proposed to the user, who approves before you touch the wiki.
2. **Distinguish "the wiki says" from "I think".** Cite specific pages (with `[[wikilinks]]`) when describing what the wiki knows. Flag your own interpretations clearly.
3. **Be specific, not vague.** "The wiki covers Python well" is unhelpful. "The wiki has 14 Python sessions, strong coverage of pytest and argparse, but zero on async or typing" is actionable.
