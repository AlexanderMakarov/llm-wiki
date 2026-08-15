Lint the llmwiki — find orphans, broken wikilinks, contradictions, and stale pages.

Usage: /wiki-lint

Use Grep and Read to check for:

1. **Orphan pages** — wiki pages with no inbound `[[links]]` from any other page.
   ```
   # For each page in wiki/sources, wiki/entities, wiki/concepts:
   #   grep -rl "[[<slug>]]" wiki/ → if zero matches, orphan
   ```

2. **Broken wikilinks** — `[[Name]]` pointing to a page that does not exist.
   ```
   grep -rohE '\[\[[^]]+\]\]' wiki/ | sort -u
   # then compare against wiki/sources/*.md + wiki/entities/*.md + wiki/concepts/*.md
   ```

3. **Contradictions** — search for `## Contradictions` sections and report them to the user.

4. **Stale summaries** — pages whose `last_updated` is older than the newest source that contributes to them.

5. **Missing entity pages** — entities mentioned in 3+ source pages but lacking their own page.

6. **Data gaps** — questions the wiki can't answer; suggest new sources or queries.

Output a report to the chat, grouped by issue type. At the end, ask the user if they want the report saved to `wiki/lint-report.md`.

Append to `wiki/log.md`: `## [YYYY-MM-DD] lint | <N> issues found`
