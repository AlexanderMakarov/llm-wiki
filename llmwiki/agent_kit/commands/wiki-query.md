Query the llmwiki and synthesise an answer.

Usage: /wiki-query <your question>

`$ARGUMENTS` is the natural-language question. Follow this **Query Workflow**:

1. Read `wiki/index.md` and `wiki/overview.md` to identify the most relevant pages.
2. Read those pages using the Read tool.
3. Synthesise an answer with inline `[[wikilink]]` citations. Quote directly from source pages when helpful.
4. If your answer is substantial (3+ paragraphs), ask the user whether to save it to `wiki/syntheses/<slug>.md`.
5. If the user approves, write the synthesis page using this format:
   ```markdown
   ---
   title: "The question this answers"
   type: synthesis
   tags: []
   sources: [slug-1, slug-2]
   last_updated: YYYY-MM-DD
   ---

   # The question in full

   ## Answer
   ...with [[wikilink]] citations...

   ## Sources consulted
   - [[source-1]]
   - [[source-2]]
   ```
6. Append to `wiki/log.md`: `## [YYYY-MM-DD] query | <short question>`
