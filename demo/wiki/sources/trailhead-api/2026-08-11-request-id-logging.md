---
title: "Thread a request id through the log output"
type: source
tags: [session, session-transcript, trailhead-api, gpt, request-id, structured-logging, correlation-id, context-variables, response-headers]
date: 2026-08-11
source_file: raw/sessions/trailhead-api/2026-08-11T21-10-trailhead-api-request-id-logging.md
project: trailhead-api
model: gpt-5-codex
last_updated: 2026-09-08
---
## Summary

The session added end-to-end request correlation for the trailhead API: a request id is created at the edge, held in a Python context variable, and emitted on every log line via the formatter so handlers do not pass it manually. The same id is exposed as a response header so operators can tie a failed call to log lines. Background work keeps the id only when spawned from the active request context; jobs scheduled outside that context get a new id, which matches treating them as separate units of work.

## Key Claims

- A request id is generated at the edge, stored in a context variable, and attached to every log line by the formatter without explicit passing through the call stack.
- The request id is returned as a response header so a specific failed request can be traced directly in logs.
- Background tasks inherit the request id only when spawned from the request context; tasks scheduled outside that context receive a fresh id.

## Key Quotes

> "Added a request id generated at the edge, stored in a context variable, and included by the log formatter on every line. Nothing has to pass it explicitly." — core design: implicit propagation via context + formatter

> "It is also returned as a response header, so a report about a specific failed request can be traced directly." — client-to-log linkage

> "Only if the task is spawned from the request context. Anything scheduled outside it gets a fresh id, which is correct — it is a different unit of work." — scope of correlation for async/background work

## Connections

- [[REST API]] (entity) — HTTP API where request ids are minted at the edge and returned in response headers.
  - fact: Correlation ids are intended for multi-request log traffic on the API surface.
- [[Observability]] (concept) — log correlation and tracing a single request under concurrent load.
  - fact: Request ids address interleaved log lines when traffic is concurrent.
- [[trailhead-api]] (project) — codebase on branch `chore/logging` where this logging change was implemented.
