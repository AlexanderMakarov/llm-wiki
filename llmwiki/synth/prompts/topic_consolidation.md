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

`<fixed_curated_titles>` lists live wiki pages a reviewer already created
(entities, concepts, projects). Treat each `name` as a **fixed canonical** —
do not fold one fixed title into another as an alias, and do not drop a fixed
title as noise. You may still attach non-fixed spelling variants as `aliases`
of a fixed title.

<fixed_curated_titles>
{fixed_curated_titles}
</fixed_curated_titles>

`<keep_distinct>` lists unordered pairs a reviewer marked as different subjects.
Never fold either side into the other (neither as `canonical`/`aliases` of one
topic). Prefer a `distinct_from` note when both stay.

<keep_distinct>
{keep_distinct}
</keep_distinct>

## Your tasks

1. **Merge duplicates.** Fold spelling AND semantic duplicates into ONE canonical
   topic. Pick the clearest canonical `name` (proper casing, no abbreviation
   unless that *is* the common name). List every folded spelling in `aliases`.
   Never merge two `<fixed_curated_titles>` names into one topic, and never merge
   a `<keep_distinct>` pair.
2. **Drop noise.** Omit candidates that are not significant scopes — incidental
   shell commands, flags, file names, one-off libraries a reader wouldn't browse
   by. Put their names in `dropped`. Bias toward keeping anything mentioned in
   several sessions; bias toward dropping one-off generic terms. Never put a
   fixed curated title in `dropped`.
3. **Describe each kept topic.** Write a `description`: one concrete sentence on
   what it is / what it covers, grounded in the `with` + `sample` context.
4. **Disambiguate confusable pairs.** When two kept topics look similar but are
   genuinely different (e.g. a tool vs. the project that uses it), add a
   `distinct_from` note explaining the difference, so later passes don't merge
   them. Omit when there's nothing confusable. Keep-distinct pairs should stay
   as separate topics with `distinct_from` when helpful.
5. **Classify each kept topic.** Set `kind` to `"entity"` (person, company,
   product, tool, library) or `"concept"` (idea, framework, method, decision).
   Pick the best fit; do not invent other values.

## Output

Return **ONLY** valid JSON (no prose, no markdown fence), matching:

```json
{
  "topics": [
    {
      "canonical": "kbbuilder",
      "kind": "entity",
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
- `kind` must be `"entity"` or `"concept"` for every kept topic.
- Every input candidate must appear exactly once — either as a `canonical`, an
  `alias` of one, or in `dropped`.
- Fixed curated titles that appear as candidates must remain as their own
  `canonical` (or an alias only of a non-conflicting spelling of *themselves*,
  never of another fixed title or keep-distinct partner).
- Descriptions stay to a single sentence.

## Session to synthesize

Job 1 has no session body. Follow the Output rules above and return only the JSON object.
