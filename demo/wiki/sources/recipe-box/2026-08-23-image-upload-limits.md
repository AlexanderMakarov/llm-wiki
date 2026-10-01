---
title: "Validate image uploads before they reach storage"
type: source
tags: [session, session-transcript, recipe-box, claude, image-upload-validation, stream-capping, content-type-detection, file-size-limits, upload-middleware, stream-processing, mime-type-detection]
date: 2026-08-23
source_file: raw/sessions/recipe-box/2026-07-31T19-44-recipe-box-image-upload-limits.md
project: recipe-box
model: claude-opus-5
last_updated: 2026-10-01
---
## Summary

The session addressed a bug where oversized and mistyped file uploads were accepted and persisted before validation rejected them. The team relocated validation from post-write to stream ingestion: file type is now detected from actual bytes (not declared filename), reads are capped to reject oversized uploads before buffering, and error messages report both the limit and detected type.

## Key Claims

- Previous implementation validated uploads **after** writing them to storage
- Validation now occurs during stream ingestion, before any buffering takes place
- File type detection uses actual file bytes instead of the declared filename
- File read streams are capped with a configurable limit to prevent oversized uploads from being buffered
- Error messages improved to include both the resource limit and the detected type

## Key Quotes

> "Someone uploaded a video and it was stored before anything complained."
— User report of the original problem: validation ran too late

> "Validation ran after the write. It now happens on the incoming stream: type is checked from the actual bytes rather than the declared name, and the read is capped so an oversized file is rejected before it is buffered."
— Summary of the implemented solution

## Connections

- [[Web App]] (entity) — the recipe-box application
  - fact: File uploads now validate during stream ingestion rather than post-write
- [[Validation]] (concept) — checking file type and size constraints on input
  - fact: Type detection uses actual bytes and reads are capped before buffering to prevent resource exhaustion