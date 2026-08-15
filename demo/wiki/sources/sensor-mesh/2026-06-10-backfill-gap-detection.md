---
title: "Detect and backfill gaps in the sensor stream"
type: source
tags: [session, session-transcript, sensor-mesh, gpt, gap-detection, time-series, data-backfill, interval-declaration]
date: 2026-06-10
source_file: raw/sessions/sensor-mesh/2026-06-10T22-35-sensor-mesh-backfill-gap-detection.md
project: sensor-mesh
model: gpt-5-codex
last_updated: 2026-08-11
---
## Summary

The session addressed a critical observability issue where missing sensor readings were indistinguishable from repeated readings downstream, causing dashboards to draw flat lines through outages instead of indicating data loss. The solution implemented explicit gap detection (recording missing intervals), bounded-window data backfill upon device reconnection, and declared per-device sampling intervals rather than inferring them (inference erroneously adapted to outages, defeating the purpose).

## Key Claims

- Missing readings and repeated readings were previously indistinguishable downstream, causing flat-line visualization of outages
- Gaps are now explicitly recorded so consumers can distinguish missing data from stable readings
- Backfill re-requests only a bounded window when a device reconnects, rejecting requests beyond that to prevent unbounded history pulls
- Expected sampling intervals must be declared per-device, not inferred (inference adapts to outages, making detection impossible)

## Key Quotes

> "A sensor dropped out for an hour and the dashboard drew a flat line through it."

Illustrates the core symptom: silent gaps were visually indistinguishable from stable repeated readings, creating false confidence in data continuity.

> "Inference was the original approach and it adapted to the outage, which is exactly when you need it not to."

Explains why declarative intervals are necessary: an adaptive strategy undermines itself during the very events it should detect.

## Connections

- [[sensor-mesh]] — the project where this feature was implemented
- [[Time Series]] — handling time-series data with gaps and missing values
- [[Observability]] — the dashboard visualization problem that motivated the fix