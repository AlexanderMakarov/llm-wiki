---
title: "Add backoff to broker reconnection"
type: source
tags: [session, session-transcript, sensor-mesh, claude, exponential-backoff, mqtt-reconnect, thundering-herd]
date: 2026-08-05
source_file: raw/sessions/sensor-mesh/2026-08-05T17-54-sensor-mesh-mqtt-reconnect-backoff.md
project: sensor-mesh
model: claude-opus-5
last_updated: 2026-08-11
---
## Summary

When an MQTT broker connection was dropped, the collector would attempt to reconnect immediately in a tight loop, causing logs to fill up within seconds. The session implemented exponential backoff with an upper ceiling and jitter to prevent synchronized reconnection across fleet instances, while consolidating logging from per-failure to per-attempt messages showing the current backoff delay. The collector continues retrying indefinitely at the backoff ceiling rather than failing and requiring external supervision to restart.

## Key Claims

- The original code had no delay between reconnection attempts, causing immediate re-connection loops when the broker was unavailable
- Exponential backoff with a ceiling was implemented to rate-limit reconnection attempts and reduce resource consumption
- Jitter was added to desynchronize reconnection attempts across multiple collector instances and prevent thundering herd effects
- Log output was refactored from per-failure to per-attempt with backoff state visibility to reduce log spam
- The system is designed to retry indefinitely at the backoff ceiling rather than fail-stop, prioritizing availability over bounded recovery

## Key Quotes

> "When the broker goes down the logs fill up in seconds." — Illustrating the severity of the problem caused by immediate reconnection attempts

> "It now backs off exponentially up to a ceiling, with jitter so a fleet coming back does not reconnect in lockstep." — The solution strategy, combining exponential backoff with jitter to handle distributed failure scenarios

> "For a background collector, continuing to try is more useful than exiting and needing supervision to restart it." — Design rationale for retry-forever behavior rather than fail-stop semantics

## Connections

- [[Time Series]] — Sensor-mesh collects time series data; connection resilience ensures uninterrupted collection during broker failures
- [[Observability]] — Session addresses both problem (log spam during failures) and solution (consolidated logging with backoff visibility for diagnostics)