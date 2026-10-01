---
title: "Add backoff to broker reconnection"
type: source
tags: [session, session-transcript, sensor-mesh, claude, mqtt, exponential-backoff, reconnect-jitter, broker-connection, logging, observability, mqtt-reconnect, log-suppression]
date: 2026-09-26
source_file: raw/sessions/sensor-mesh/2026-09-03T17-54-sensor-mesh-mqtt-reconnect-backoff.md
project: sensor-mesh
model: claude-opus-5
last_updated: 2026-10-01
---
## Summary

A dropped MQTT broker connection triggered a tight reconnect loop that flooded logs. The assistant implemented exponential backoff with jitter and a ceiling, changed logging to summary format, and configured indefinite retries at maximum backoff. This prioritizes uptime for background data collectors.

## Key Claims

- The original reconnect logic had no delay between attempts, causing log flooding when broker connectivity was lost
- Exponential backoff with jitter and a ceiling was implemented to prevent reconnection storms
- Logging was changed from per-attempt to summary format (one line per attempt with current delay), reducing noise significantly
- The system retries indefinitely at maximum backoff rather than failing, prioritizing availability over graceful shutdown

## Key Quotes

> "When the broker goes down the logs fill up in seconds." — User identifying the problem

> "The reconnect had no delay. It now backs off exponentially up to a ceiling, with jitter so a fleet coming back does not reconnect in lockstep." — Solution summary

> "For a background collector, continuing to try is more useful than exiting and needing supervision to restart it." — Design philosophy for retry behavior

## Connections

- [[Exponential Backoff]] (concept) — retry strategy with jitter and ceiling to prevent reconnection storms
  - fact: Backoff increases exponentially to a maximum delay; jitter desynchronizes fleet reconnections to prevent coordinated reconnect lockstep

## Contradictions

None identified.