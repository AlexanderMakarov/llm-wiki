---
title: "Detect and backfill gaps in the sensor stream (brexinode)"
type: source
tags: [session, session-transcript, sensor-mesh, gpt, gap-detection, sensor-backfill, time-series, expected-interval, dashboard-gaps, sensor-dropout, declared-intervals, backfill-strategy]
date: 2026-07-29
source_file: raw/sessions/sensor-mesh/2026-07-09T22-35-sensor-mesh-backfill-gap-detection.md
project: sensor-mesh
model: gpt-5-codex
last_updated: 2026-09-28
---
## Summary

This session solved a critical bug in sensor data visualization where device dropouts rendered as flat lines indistinguishable from repeated readings. The solution implements explicit gap detection by comparing readings against declared per-device intervals and marks gaps as distinct markers, enabling downstream systems to render breaks instead of interpolating over outages. Backfill operations were bounded to prevent unbounded history requests on reconnection. A key design decision was declaring intervals per-device rather than inferring them—inference adapts to outages during the exact conditions when stable detection is most critical.

## Key Claims

- Flat-line rendering of dropped readings cannot be distinguished from repeated readings without explicit gap markers
- Inferring expected intervals fails precisely during outages, when reliable detection is most important
- Declaring intervals per-device ensures stable, predictable gap detection independent of outage patterns
- Backfill windows must be bounded to prevent exploitative history requests after device reconnection
- Gap detection implementation passes all tests (4 → 7 → 10 passing) with no new lint warnings

## Key Quotes

> "There was no distinction between a missing reading and a repeated one. Gaps are now detected against the expected interval and recorded explicitly, so downstream can draw a break instead of interpolating."

This captures the core insight: gaps require explicit signaling, not just data absence, to prevent silent misinterpretation downstream.

> "Inference was the original approach and it adapted to the outage, which is exactly when you need it not to."

This reveals the critical flaw in the original approach: adaptive systems fail under the stress conditions where stable behavior is essential.

## Connections

- [[Sensor Mesh]] (entity) — the IoT sensor collection system being improved for outage resilience
  - fact: Explicit gap markers prevent dashboards and consumers from interpolating across device outages
- [[Observability]] (concept) — system visibility requires distinguishing sensor gaps from repeated readings
  - fact: Gap markers make outages queryable and observable rather than silent flat-line artifacts