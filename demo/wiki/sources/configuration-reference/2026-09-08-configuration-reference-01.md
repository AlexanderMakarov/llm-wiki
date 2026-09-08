---
title: "Configuration Reference (part 1/8)"
type: source
tags: [wiki-add, raw-doc, session-transcript, configuration-reference]
date: 2026-09-08
source_file: 
project: configuration-reference
model: 
last_updated: 2026-09-08
---
The body you shared is only the opening of **Configuration Reference (part 1/8)**—no conversation transcript—so the page below is synthesized from that stub and the frontmatter (`docs/configuration-reference.md`, `configuration-reference` project).

<!-- suggested-tags: configuration-reference, cli-flags, environment-variables, sessions-config -->

## Summary

This source is part 1 of an eight-part **Configuration Reference** doc ingested into the wiki (`wiki-add`, `raw-doc`). It frames the series as the full reference for **llmwiki** CLI subcommands, flags, environment variables, and configuration options. No specific flags, env keys, or config file shapes appear in this fragment; later parts presumably carry the detail.

## Key Claims

- The Configuration Reference is split into eight parts; this file is explicitly **part 1 of 8**.
- The series scope is **all** CLI subcommands, flags, environment variables, and configuration options for the toolchain.
- The canonical upstream for this chunk is `docs/configuration-reference.md` under the `configuration-reference` project slug.

## Key Quotes

> "Complete reference for all CLI subcommands, flags, environment variables, and configuration options." — Stated scope of the eight-part reference series.

## Connections

- [[llmwiki]] (entity) — The reference documents how to configure and invoke the wiki toolchain from the CLI and config files.
  - fact: Part 1 only declares series scope; operational detail lives in sibling parts and in `docs/reference/*.md` per repo contribution rules.
- [[Adapters]] (concept) — Configuration options typically include adapter enablement and paths (`sessions_config.json`, per CONTRIBUTING/adapter docs).
  - fact: Not enumerated in this fragment; link is thematic for readers browsing configuration topics.
- [[MCP Server]] (concept) — MCP exposure is part of the product surface area usually covered alongside CLI in reference material.
  - fact: No MCP-specific options appear in this part’s body.
