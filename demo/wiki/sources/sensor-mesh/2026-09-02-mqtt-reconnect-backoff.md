---
title: "Add backoff to broker reconnection"
type: source
tags: [session, session-transcript, sensor-mesh, claude, mqtt-reconnection, exponential-backoff, jitter, log-aggregation]
date: 2026-09-02
source_file: raw/sessions/sensor-mesh/2026-09-02T17-54-sensor-mesh-mqtt-reconnect-backoff.md
project: sensor-mesh
model: claude-opus-5
last_updated: 2026-09-07
---
## Summary

When a broker dropped, the sensor-mesh collector's reconnect logic entered a tight loop, flooding logs with repeated connection attempts in seconds. Exponential backoff with a ceiling and jitter was implemented to rate-limit reconnection and prevent synchronized reconnection across a distributed fleet. Log output was consolidated into a summary format showing current delay per attempt instead of one line per failure. The retry strategy continues indefinitely at the ceiling rather than exiting, prioritizing continuous operation for a background collector.

## Key Claims

- The original broker reconnection logic had no delay between attempts, causing rapid log flooding when the broker became unavailable.
- Exponential backoff with a ceiling and jitter was implemented to rate-limit reconnection attempts and prevent coordinated reconnection surge when the broker recovers.
- Log aggregation was changed from one line per failure to a single summary line per attempt that includes the current backoff delay.
- The retry mechanism continues indefinitely at the maximum delay rather than exiting and requiring external supervision to restart the collector.

## Key Quotes

> "When the broker goes down the logs fill up in seconds." — illustrates the severity of the unthrottled reconnect loop.

> "It now backs off exponentially up to a ceiling, with jitter so a fleet coming back does not reconnect in lockstep." — describes both the backoff strategy and its benefit for distributed operations.

> "No, it keeps retrying at the ceiling. For a background collector, continuing to try is more useful than exiting and needing supervision to restart it." — justifies the decision to continue retrying indefinitely.

## Connections

- [[Observability]] (concept) — improved logging strategy reduces noise from connection failure storms
  - fact: Log output changed from one line per failed attempt to a summary format with current backoff delay, reducing log volume during broker outages

## Contradictions

(none identified)