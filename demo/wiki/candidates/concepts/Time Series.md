---
title: "Time Series"
type: concept
status: candidate
tags: []
sources: [2026-07-09-backfill-gap-detection, 2026-07-09-backfill-gap-detection, 2026-09-03-mqtt-reconnect-backoff]
last_updated: 2026-09-08
---

# Time Series

sensor readings form time-series data where gaps must be explicitly distinguished from repeated values.

## Key Facts

- Explicit gap markers allow downstream systems to treat breaks differently from interpolation. [[2026-07-09-backfill-gap-detection]]
- Background collectors are expected to survive broker outages without process restart. [[2026-09-03-mqtt-reconnect-backoff]]

## Connections

Named by 3 source page(s), which is the evidence that
justified this candidate:

- [[2026-07-09-backfill-gap-detection]]
- [[2026-07-09-backfill-gap-detection]]
- [[2026-09-03-mqtt-reconnect-backoff]]
