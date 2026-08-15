---
title: "Entity schema reference (v0.7 · #55)"
type: source
tags: [wiki-add, raw-doc, session-transcript, entity-schema-reference-v0-7-55, model-frontmatter, ai-model-entities, schema-validation]
date: 2026-08-10
source_file: 
project: entity-schema-reference-v0-7-55
model: 
last_updated: 2026-08-11
---
## Summary

Formal specification for AI model entity pages in [[llm-wiki]]. Defines an opt-in frontmatter schema with structured metadata fields (context window, pricing, modalities, benchmarks), validation rules for each field, and the five-stage build pipeline that discovers model entities, validates them, and renders them as an indexed sortable table plus individual detail pages with info cards.

## Key Claims

- AI model entities are opt-in; any page without `entity_kind: ai-model` renders as free-form markdown and is ignored by the model pipeline
- Nested complex data (model specs, pricing, benchmarks) use inline JSON to avoid requiring a full YAML parser in the frontmatter handler
- Benchmark scores must be fractions in [0, 1]; the validator warns on values outside this range but does not block the build
- Known benchmarks (e.g., GPQA Diamond, SWE-bench, MMLU) receive automatic human-readable labels in the index; unknown benchmark keys pass through with titlecased labels
- Pricing includes both per-token costs and an effective date, enabling historical pricing representation

## Key Quotes

> "Nested blocks are written as inline JSON so llmwiki's lightweight frontmatter parser can store them without a full YAML library." — Justification for JSON-encoded nested data instead of native YAML nesting.

> "Warnings are surfaced in a collapsible `<details>` block on the detail page — they don't block the build." — Schema validation is permissive; violations are reported but never prevent rendering.

## Connections

- [[llm-wiki]] — this entity schema enables structured model metadata, the models index, and model detail pages

## Contradictions

None identified.