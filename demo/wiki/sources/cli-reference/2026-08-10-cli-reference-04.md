---
title: "CLI reference (part 4/8: candidates — approval workflow)"
type: source
tags: [wiki-add, raw-doc, session-transcript, cli-reference, candidates-command, key-facts-synthesis, approval-workflow, synthesis-backend]
date: 2026-08-10
source_file: 
project: cli-reference
model: 
last_updated: 2026-08-11
---
## Summary

This documentation covers the `candidates` command in [[llm-wiki]], which implements an approval workflow for managing new entities and concepts. Key operations are promote (which automatically synthesizes Key Facts using a backend model), merge (combining candidates into target pages), discard, and batch apply. Promotion requires a configured synthesis backend; without one, it fails with KeyFactsBackendError.

## Key Claims

- The `promote` action requires a configured synthesis backend; without one, it exits with KeyFactsBackendError and leaves the candidate pending
- Promotion generates 3–5 attributed Key Facts bullets from evidence in sources named in the candidate's frontmatter (capped at 12 sources, 4 lines each) via the configured `synthesis.backend` model
- The `merge` action combines a candidate into a target page by unioning sources and Connections, recording the candidate's original name under `## Aliases`
- The `apply` command executes multiple candidate actions (promote, merge, discard) in a single batch process via JSON input, enabling programmatic workflows
- The `rewrite-key-facts` command retroactively fixes trusted pages containing outdated machine-assembled regex-based Key Facts from older implementations

## Key Quotes

> "Because those bullets become trusted-layer prose, promote refuses to write them without a model: with `synthesis.backend` unset or `dummy` it exits 2 with `KeyFactsBackendError`"

This shows that Key Facts quality is critical enough to block promotion if no real synthesis backend is configured.

> "`merge` folds a harvest stub into the target by unioning its `sources:` and Connections links and recording the name under `## Aliases`"

This describes the core semantics of combining candidate pages with existing target pages.

## Connections

- [[llm-wiki]] — the tool whose CLI is documented here; candidates command is a core workflow component for managing vault contributors