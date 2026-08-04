<%*
const date = tp.date.now("YYYY-MM-DD");
_%>---
title: "<% await tp.file.title %>"
type: entity
tags: [entity]
sources: []
confidence: 0.5
lifecycle: draft
last_updated: <% date %>
---

# <% await tp.file.title %>

> [!info] Entity page
> Use for people, orgs, tools, products, APIs, and libraries. Ideas belong on a concept page (`type: concept`); codebases belong on a project page (`type: project`).

One-paragraph description of this entity — who/what it is, why it matters.

## Key Facts

- Fact 1
- Fact 2

## Sessions

- [[session-slug]] (YYYY-MM-DD) — what happened

## Connections

- [[RelatedEntity]]
- [[RelatedConcept]]

## Inline Dataview

**Sources citing this entity:**
```dataview
LIST
FROM "sources"
WHERE contains(file.outlinks, this.file.link)
```
