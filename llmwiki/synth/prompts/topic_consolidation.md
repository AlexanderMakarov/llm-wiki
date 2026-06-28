You are consolidating a **noisy, auto-extracted topic list** into a clean
*controlled vocabulary* of the significant scopes in a personal knowledge base.

This is a one-time migration pass. The topics below were tagged per-session by a
weaker pass, so they contain spelling variants, near-duplicates, and incidental
noise (one-off tools, commands, files). Your job is to produce the canonical set
a human would actually browse by — projects, products, major systems/services,
people, and organisations — and nothing else.

## Input

Each `<candidate>` is a heuristically-clustered topic with:
- `name` — the most frequent spelling
- `sessions` — how many sessions mention it (higher = more important)
- `aka` — spelling variants already folded in (extend this if you find more)
- `with` — topics it co-occurs with (context for what it is)
- `sample` — a session title that mentions it (more context)

<candidates>
{candidates}
</candidates>

## Your tasks

1. **Merge duplicates.** Fold spelling AND semantic duplicates into ONE canonical
   topic. Pick the clearest canonical `name` (proper casing, no abbreviation
   unless that *is* the common name). List every folded spelling in `aliases`.
2. **Drop noise.** Omit candidates that are not significant scopes — incidental
   shell commands, flags, file names, one-off libraries a reader wouldn't browse
   by. Put their names in `dropped`. Bias toward keeping anything mentioned in
   several sessions; bias toward dropping one-off generic terms.
3. **Describe each kept topic.** Write a `description`: one concrete sentence on
   what it is / what it covers, grounded in the `with` + `sample` context.
4. **Disambiguate confusable pairs.** When two kept topics look similar but are
   genuinely different (e.g. a tool vs. the project that uses it), add a
   `distinct_from` note explaining the difference, so later passes don't merge
   them. Omit when there's nothing confusable.

## Output

Return **ONLY** valid JSON (no prose, no markdown fence), matching:

```json
{
  "topics": [
    {
      "canonical": "kbbuilder",
      "description": "CLI that scrapes and ingests external docs into the wiki.",
      "aliases": ["KBBuilder", "Kbbuilder", "code-kbbuilder"],
      "distinct_from": [
        {"topic": "OpenClaw", "why": "kbbuilder is the ingest CLI; OpenClaw is the autonomous VPS agent platform that uses it."}
      ]
    }
  ],
  "dropped": ["ls", "grep", "tmpfile"]
}
```

Rules:
- `canonical` must be unique. `aliases` may be empty `[]`. `distinct_from` is
  optional (omit or `[]` when nothing is confusable).
- Every input candidate must appear exactly once — either as a `canonical`, an
  `alias` of one, or in `dropped`.
- Descriptions stay to a single sentence.
