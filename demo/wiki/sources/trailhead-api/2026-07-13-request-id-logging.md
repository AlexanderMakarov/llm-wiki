---
title: "Thread a request id through the log output"
type: source
tags: [session, session-transcript, trailhead-api, gpt, request-id-logging, context-propagation, distributed-tracing, log-correlation]
date: 2026-07-13
source_file: raw/sessions/trailhead-api/2026-07-13T21-10-trailhead-api-request-id-logging.md
project: trailhead-api
model: gpt-5-codex
last_updated: 2026-08-11
---
## Summary

The session addressed log readability in high-traffic [[REST API]]s where concurrent requests interleave log lines indistinguishably. The solution generates a unique request ID at the API edge, stores it in a context variable, and automatically includes it in every log line without requiring explicit parameter passing through the call stack. The ID is also returned as a response header for direct request traceability. A critical design decision: request IDs only propagate to background tasks spawned within the request context; independently scheduled tasks receive fresh IDs, correctly treating them as distinct work units.

## Key Claims

- Concurrent [[REST API]] requests produce interleaved logs with no built-in way to trace individual requests
- Request IDs can be stored in context variables and automatically picked up by the log formatter without explicit parameter passing
- Request IDs returned as response headers enable direct tracing of failed requests to their corresponding log entries
- Request ID propagation to background tasks should be scoped to tasks spawned within the request context; independently scheduled tasks should receive fresh IDs

## Key Quotes

> "I cannot follow a single request through the logs when there is any traffic." — The core problem statement

> "Added a request id generated at the edge, stored in a context variable, and included by the log formatter on every line. Nothing has to pass it explicitly." — The implementation strategy

> "Only if the task is spawned from the request context. Anything scheduled outside it gets a fresh id, which is correct — it is a different unit of work." — Design decision on context propagation boundaries

## Connections

- [[REST API]] — request IDs generated at the API edge and returned in response headers
- [[Observability]] — request correlation is a foundational observability pattern for tracing behavior through concurrent systems
- [[trailhead-api]] — the project being improved
- [[Python]] — implementation language; context propagation strategy is language-specific

## Contradictions

None identified.