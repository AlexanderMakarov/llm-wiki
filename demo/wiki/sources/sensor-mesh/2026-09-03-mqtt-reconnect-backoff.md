---
title: "Add backoff to broker reconnection"
type: source
tags: [session, session-transcript, sensor-mesh, claude, mqtt, exponential-backoff, reconnect-jitter, broker-connection, logging]
date: 2026-09-03
source_file: raw/sessions/sensor-mesh/2026-09-03T17-54-sensor-mesh-mqtt-reconnect-backoff.md
project: sensor-mesh
model: claude-opus-5
last_updated: 2026-09-08
---
## Summary

After a broker outage, the MQTT client reconnected with no delay and flooded logs. The session added exponential backoff capped at a maximum interval, plus jitter so many collectors do not reconnect in sync. Logging was reduced to one summary line per attempt showing the current delay. The client does not stop retrying at the ceiling; for a background collector, persistent retries were preferred over exit and external restart.

## Key Claims

- Reconnect without backoff caused log volume to spike within seconds when the broker dropped.
- Reconnect uses exponential backoff up to a ceiling, with jitter to spread reconnect times across a fleet.
- Each reconnect attempt is logged once with the current delay, not on every underlying failure.
- The client never gives up; it keeps retrying at the ceiling delay rather than exiting.

## Key Quotes

> "When the broker goes down the logs fill up in seconds." — Motivation for backoff and quieter logging.

> "No, it keeps retrying at the ceiling. For a background collector, continuing to try is more useful than exiting and needing supervision to restart it." — Explicit product decision against a max-retry give-up.

## Connections

- [[Observability]] (concept) — reconnect logging was tightened to one summary line per attempt with delay, reducing noise during outages.
  - fact: Per-attempt summary logging replaces high-volume per-failure lines during reconnect storms.
- [[Time Series]] (concept) — sensor-mesh collectors depend on steady broker connectivity for time-series ingestion; reconnect policy affects data gaps during broker downtime.
  - fact: Background collectors are expected to survive broker outages without process restart.
