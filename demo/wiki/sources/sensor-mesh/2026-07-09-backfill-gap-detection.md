---
title: "Detect and backfill gaps in the sensor stream"
type: source
tags: [session, session-transcript, sensor-mesh, gpt, gap-detection, sensor-backfill, time-series, expected-interval, dashboard-gaps]
date: 2026-07-09
source_file: raw/sessions/sensor-mesh/2026-07-09T22-35-sensor-mesh-backfill-gap-detection.md
project: sensor-mesh
model: gpt-5-codex
last_updated: 2026-09-08
---
## Summary

The session fixed a sensor-mesh bug where an hour-long dropout was rendered as a flat line because missing samples were indistinguishable from repeated values. Gaps are now detected against a per-device **declared** expected sampling interval and stored explicitly so dashboards can break the series instead of interpolating. On reconnect, backfill requests only a bounded time window and refuses unbounded historical pulls.

## Key Claims

- Downstream charts treated “no new reading” the same as “same reading again,” which produced misleading flat segments during outages.
- Gap detection compares actual arrival times to the device’s declared expected interval; gaps are recorded as such rather than filled silently.
- Expected interval must be configured per device; inferring interval from recent traffic failed during outages because the stream itself went quiet.
- Backfill runs when a device reconnects, re-requests data for a limited window, and does not attempt unlimited history recovery.

## Key Quotes

> "There was no distinction between a missing reading and a repeated one." — root cause of flat-line dashboard behavior during dropouts

> "Declared per device rather than inferred. Inference was the original approach and it adapted to the outage, which is exactly when you need it not to." — rationale for explicit interval configuration

## Connections

- [[Observability]] (concept) — dashboards and downstream consumers need explicit gap semantics to avoid false “steady” readings during sensor loss.
  - fact: Explicit gap records let visualization break lines instead of interpolating across outages.
- [[Time Series]] (concept) — sampling cadence, missing points, and backfill windows for reconnecting devices.
- sensor-mesh (project) — feat/backfill work on gap detection and bounded backfill for the mesh sensor stream.