---
title: "Add backoff to broker reconnection"
type: source
tags: [session, session-transcript, sensor-mesh, claude, mqtt, exponential-backoff, reconnect-jitter, broker-connection, logging, observability]
date: 2026-09-23
source_file: raw/sessions/sensor-mesh/2026-09-03T17-54-sensor-mesh-mqtt-reconnect-backoff.md
project: sensor-mesh
model: claude-opus-5
last_updated: 2026-09-28
---
## Summary

The session addressed a critical MQTT reconnection issue in sensor-mesh where dropped broker connections triggered rapid, undelayed reconnect attempts that flooded logs within seconds. The fix implements exponential backoff with jitter up to a ceiling, condenses logging to summary lines showing current delay, prevents synchronized reconnects across fleet instances, and ensures the service never gives up—instead retrying indefinitely at the ceiling, which better suits background data collectors than supervised restart patterns.

## Key Claims

- When the broker goes down without reconnect delays, logs fill up within seconds from rapid retry attempts.
- The fix adds exponential backoff with jitter up to a configurable ceiling to eliminate aggressive reconnection loops.
- Jitter in the backoff prevents fleet-wide synchronized reconnects (thundering herd problem).
- Summary logging reduces verbosity from one line per failure to one line per reconnect attempt, showing current delay.
- The service never gives up; it continues retrying at the ceiling indefinitely.
- For background collectors, continuous retry is more robust than crashing and requiring supervised restart.

## Key Quotes

> "When the broker goes down the logs fill up in seconds." — establishes severity of the original log spam problem

> "The reconnect had no delay. It now backs off exponentially up to a ceiling, with jitter so a fleet coming back does not reconnect in lockstep." — core technical solution

> "The log line moved to a summary — one line per attempt with the current delay, rather than one per failure." — observability improvement strategy

> "For a background collector, continuing to try is more useful than exiting and needing supervision to restart it." — design philosophy justifying indefinite retry

## Connections

- [[Observability]] (concept) — fix improves monitoring by condensing per-failure logs into summary lines with current delay information
  - fact: One line per reconnect attempt replaces one line per individual failure, reducing log spam while preserving diagnostic data
- [[Time Series]] (entity) — MQTT broker collects time-series sensor data; connection reliability is critical for uninterrupted data pipeline
  - fact: Service design prioritizes uninterrupted background collection over crash-and-restart patterns
- [[Exponential Backoff]] (concept) — retry pattern with jitter implemented to prevent reconnection storms
  - fact: Jitter ensures fleet-wide synchronized reconnects cannot occur (thundering herd mitigation)