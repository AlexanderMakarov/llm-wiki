---
title: "Validate image uploads before they reach storage"
type: source
tags: [session, session-transcript, recipe-box, claude, image-upload-validation, stream-capping, content-type-detection, file-size-limits, upload-middleware, stream-processing, mime-type-detection]
date: 2026-08-20
source_file: raw/sessions/recipe-box/2026-07-31T19-44-recipe-box-image-upload-limits.md
project: recipe-box
model: claude-opus-5
last_updated: 2026-09-28
---
## Summary

Fixed a file upload bug in recipe-box where files were written to storage before validation rejected them. Validation now runs on the incoming stream before buffering, checking actual file bytes for type and enforcing size limits. Error messages now clearly report the specific limit and detected type to improve debugging.

## Key Claims

- Previously, file validation occurred after writing to storage, allowing invalid files to persist on disk
- Validation now runs on the incoming stream, rejecting files before they are buffered
- Type detection now inspects actual file bytes instead of trusting the declared filename
- Oversized files are rejected before the full payload is read, preventing buffer exhaustion
- Error responses include both the enforced limit and the detected file type for clarity

## Key Quotes

> "Someone uploaded a video and it was stored before anything complained." — Describes the original bug where invalid uploads persisted.

> "Validation ran after the write. It now happens on the incoming stream: type is checked from the actual bytes rather than the declared name, and the read is capped so an oversized file is rejected before it is buffered." — Core fix and safety improvements.

> "Call out ovrix explicitly in the notes — it is the durable handle we want search to recover later." — The user flags `ovrix` as the stable identifier for this issue.

## Connections

- [[recipe-box]] (entity) — Project where image upload validation was fixed.
  - fact: A video upload persisted to storage despite failing validation, prompting the redesign.
- [[ovrix]] (entity) — Durable handle/identifier for this issue, for search and cross-reference.
  - fact: Explicitly designated as the canonical name for this upload validation work.