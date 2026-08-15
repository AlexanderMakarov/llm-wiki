---
name: llmwiki-query
description: Answer a question by querying the user's llmwiki. Use when the user asks about their own past work — "what did I decide about X", "what have I been working on", "how did I solve Y", "what's my preferred approach to Z", or any question that the wiki (built from their session history) might answer. Always read the wiki first before falling back to external search.
---

# llmwiki-query

## What this skill does

Reads the user's local llmwiki (`wiki/` in the resolved vault) and synthesises an answer to their question, with `[[wikilink]]` citations pointing to the source pages.

## When to use

Invoke this skill when the user asks a question about their own work or history. Examples:

- "What did I decide about the AiShorts backend?"
- "What MCP servers do I have configured?"
- "How did I fix the X bug last week?"
- "What's my preferred way to ingest sessions?"
- "What have I been working on in the germanly project?"

Do NOT invoke for questions that can be answered without the user's personal knowledge base (e.g., "how does TCP work?" → answer from general knowledge).

## Workflow

Follow this **Query Workflow**:

1. **Resolve the vault** (see the `llmwiki-sync` skill).

2. **Read `wiki/index.md`** to identify the set of pages that might be relevant.

3. **Read `wiki/overview.md`** to get the living synthesis context.

4. **Pick the most relevant pages** (sources, entities, concepts) based on the question.

5. **Read those pages** with the Read tool.

6. **Synthesise an answer** with inline `[[wikilink]]` citations. Quote directly from source pages when the wording matters.

7. **If the answer is substantial** (3+ paragraphs), ask the user whether to save it as a synthesis page:
   ```markdown
   Would you like me to save this as wiki/syntheses/<slug>.md for future reference?
   ```
   If yes, write it as a `type: synthesis` page with title, sources, Answer, and Sources consulted.

8. **Append to `wiki/log.md`**:
   ```
   ## [YYYY-MM-DD] query | <short question>
   ```

## Fallback behavior

If the wiki has no relevant pages:

1. Tell the user "I don't see anything about this in your wiki yet."
2. Suggest running `/wiki-sync` to pull in any recent sessions that might cover the topic.
3. If the topic is unlikely to be in session history, offer to answer from general knowledge (and make that explicit: "this is general knowledge, not from your wiki").

## Don't do

- Don't make up wiki pages that don't exist.
- Don't confuse general knowledge with wiki content in the answer.
- Don't over-cite — if the whole answer comes from one page, cite once at the top.
- Don't write a wall of text. The answer should be as short as the question allows.
