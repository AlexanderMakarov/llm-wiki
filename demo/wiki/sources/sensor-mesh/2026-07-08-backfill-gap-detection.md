---
title: "Detect and backfill gaps in the sensor stream"
type: source
tags: [session, session-transcript, sensor-mesh, gpt, gap-detection, sensor-dropout, bounded-backfill]
date: 2026-07-08
source_file: raw/sessions/sensor-mesh/2026-07-08T22-35-sensor-mesh-backfill-gap-detection.md
project: sensor-mesh
model: gpt-5-codex
last_updated: 2026-09-07
---
## Summary

A sensor dropout appeared as a flat line on the dashboard because the system couldn't distinguish missing readings from repeated ones. Gap detection was implemented by comparing readings against device-specific expected intervals and explicitly marking gaps, so downstream systems can render breaks instead of interpolating. Backfill re-requests data in bounded windows on reconnect, and intervals are declared per-device rather than inferred (since inference adapts to outages, defeating detection).

## Key Claims

- Gap detection compares readings against device-specific expected intervals rather than inferring interval patterns from data.
- Interval inference cannot be used because inference algorithms adapt to observed data patterns, including the outage itself.
- Backfill re-requests data only within bounded windows when a device reconnects, refusing unbounded history pulls.
- Explicitly marking gaps allows downstream systems (dashboards) to render breaks instead of interpolating through missing readings.

## Key Quotes

> "There was no distinction between a missing reading and a repeated one." — Captures the core observability gap before the fix.

> "Declared per device rather than inferred. Inference was the original approach and it adapted to the outage, which is exactly when you need it not to." — Explains the critical design decision against algorithmic interval detection.

## Connections

- [[Sensor Mesh]] (project) — the sensor network system that detects and recovers from device dropouts.
  - fact: Sensor dropouts appear as flat lines without explicit gap markers, confusing downstream consumers.
- [[Time Series]] (existing topic) — sensor readings form time-series data where gaps must be explicitly distinguished from repeated values.
  - fact: Explicit gap markers allow downstream systems to treat breaks differently from interpolation.
- [[Observability]] (existing topic) — sensor dropouts are an observability challenge; gap detection ensures visibility into data quality issues.
- [[Gap Detection]] (pattern) — technique for identifying and marking missing values in time-series data using device-specific intervals.
  - fact: Per-device interval declaration enables reliable gap detection without requiring inference.
  - fact: Gaps are recorded explicitly so downstream systems can distinguish them from repeated readings.
- [[Backfill]] (strategy) — mechanism for recovering historical data when a sensor reconnects after a dropout.
  - fact: Bounded windows on backfill prevent unbounded history pulls that could overwhelm the system.
  - fact: Backfill refuses requests beyond the bounded window to maintain resource constraints.

## Contradictions

None identified.