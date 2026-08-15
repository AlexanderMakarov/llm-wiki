---
name: page-format
load: always
applies_to: "wiki/**/*.md"
---

# Wiki page format (always loaded)

Every file under `wiki/` obeys these rules. They are enforced by `/wiki-lint` and by the CI workflow.

## Frontmatter (required)

```yaml
---
title: "Human-readable title"
type: source | entity | concept | synthesis | comparison | question | archive
tags: [tag1, tag2]
sources: [source-slug-1, source-slug-2]      # only for entity/concept/synthesis
last_updated: YYYY-MM-DD
---
```

Every field is required except `sources` (source pages don't have them).

## Body sections

### Source pages (`wiki/sources/<slug>.md`)

```markdown
## Summary
2–4 sentences.

## Key Claims
- Claim 1
- Claim 2

## Key Quotes
> "Quote here" — context

## Connections
- [[EntityName]] — how they relate
- [[ConceptName]] — how it connects

## Contradictions
- Contradicts [[OtherPage]] on: ...
```

### Entity pages (`wiki/entities/<TitleCase>.md`)

```markdown
# Entity Name

One paragraph of description.

## Key Facts
- Fact 1

## Sessions
- [[session-slug]] (YYYY-MM-DD) — what happened

## Connections
- [[RelatedEntity]]
- [[RelatedConcept]]
```

### Concept pages (`wiki/concepts/<TitleCase>.md`)

Same shape as entity pages but `type: concept` in frontmatter.

### Synthesis pages (`wiki/syntheses/<slug>.md`)

```markdown
# Question This Answers

## Answer
Synthesis of sources with [[wikilink]] citations.

## Sources consulted
- [[source-1]]
- [[source-2]]
```

## Naming conventions

| Page type | Directory | Slug format | Example |
|---|---|---|---|
| Source | `wiki/sources/` | `kebab-case` (matches raw slug) | `clever-munching-parnas.md` |
| Entity | `wiki/entities/` | `TitleCase` | `AndrejKarpathy.md` |
| Concept | `wiki/concepts/` | `TitleCase` | `RetrievalAugmentedGeneration.md` |
| Synthesis | `wiki/syntheses/` | `kebab-case` | `what-did-i-decide-about-quarkus.md` |
| Archive | `wiki/archive/` | same as original | `deprecated-slug.md` |

## Hard rules

1. **Every page has a `## Connections` section** with at least one `[[wikilink]]`.
2. **`[[wikilinks]]` must resolve** — `/wiki-lint` fails on broken links.
3. **Frontmatter `last_updated` must match** the most recent edit (updated automatically on ingest).
4. **Never silently overwrite** — conflicting claims go under `## Contradictions` with both cited.
5. **Slugs are immutable once published.** Rename via archive + redirect, not in place.
