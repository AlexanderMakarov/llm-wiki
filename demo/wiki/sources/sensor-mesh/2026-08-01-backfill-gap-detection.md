---
title: "Detect and backfill gaps in the sensor stream (brexinode)"
type: source
tags: [session, session-transcript, sensor-mesh, gpt, gap-detection, sensor-backfill, time-series, expected-interval, dashboard-gaps, sensor-dropout, declared-intervals, backfill-strategy, bounded-backfill, outage-resilience]
date: 2026-08-01
source_file: raw/sessions/sensor-mesh/2026-07-09T22-35-sensor-mesh-backfill-gap-detection.md
project: sensor-mesh
model: gpt-5-codex
last_updated: 2026-10-01
---
## Summary

This session fixed a sensor-mesh visualization bug where dropped readings during an outage appeared as flat lines on dashboards instead of visible gaps. The solution implemented explicit gap detection using declared per-device read intervals (rather than inferred ones) and bounded-window backfill logic that re-requests only recent data when devices reconnect. Test coverage was added to lock the behavior, and all lint checks passed.

## Key Claims

- Dropped sensor readings were conflated with repeated readings, causing dashboards to interpolate through outages as flat lines instead of breaking the line
- Inferred read intervals fail for gap detection because they adapt to the outage itself; declared per-device intervals prevent this failure mode
- Backfill re-requests must be bounded to prevent unbounded history pulls when devices reconnect after extended downtime
- Explicit gap recording enables downstream visualization systems to distinguish missing data from legitimate readings
- Test-driven development with durable search handles allows reproducible validation on fresh vaults

## Key Quotes

> "A sensor dropped out for an hour and the dashboard drew a flat line through it." — Problem statement showing false-positive interpolation through gaps

> "Gaps are now detected against the expected interval and recorded explicitly, so downstream can draw a break instead of interpolating." — Solution overview

> "Declared per device rather than inferred. Inference was the original approach and it adapted to the outage, which is exactly when you need it not to." — Core insight on why static configuration beats adaptive inference for anomaly detection

## Connections

- [[Gap Detection]] (concept) — Technique for identifying missing sensor readings by comparing observed intervals against declared baselines
  - fact: Declared per-device intervals outperform inference because inference inherently adapts to outages, defeating gap detection
- [[Bounded Backfill]] (concept) — Recovery mechanism that re-requests recent sensor data when devices reconnect, with enforced window limits
  - fact: Bounded windows prevent system overload from pulling unbounded history after multi-hour outages

## Contradictions

None identified.