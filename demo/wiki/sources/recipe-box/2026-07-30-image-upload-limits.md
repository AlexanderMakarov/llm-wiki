---
title: "Validate image uploads before they reach storage"
type: source
tags: [session, session-transcript, recipe-box, claude, upload-validation, file-type-detection, stream-processing, configurable-limits]
date: 2026-07-30
source_file: raw/sessions/recipe-box/2026-07-30T19-44-recipe-box-image-upload-limits.md
project: recipe-box
model: claude-opus-5
last_updated: 2026-09-07
---
## Summary

The session addressed a critical data loss issue where video uploads were being written to storage before validation occurred. Upload validation was refactored to happen on the incoming stream: file type is now detected from actual file bytes rather than the declared filename, and file size is enforced during the read operation, rejecting oversized uploads before buffering. The size limit is configurable with an 8MB default, and error messages now include both the limit and detected type.

## Key Claims

- Upload validation was originally running after files were written to storage
- File type validation now inspects actual file bytes instead of relying on filename extensions
- File size validation occurs during the stream read operation, cutting off oversized uploads rather than measuring them after buffering
- The upload size limit is configurable with a default of 8 megabytes
- Error messages now report both the configured size limit and the detected file type for better debugging

## Key Quotes

> "Validation ran after the write. It now happens on the incoming stream" — describes the architectural shift from post-write to stream-based early rejection

> "The cap is enforced during the read, so an attempt to send more is cut off rather than measured after the fact" — explains how oversized uploads are rejected before buffering

## Connections

- [[Recipe Box]] (project) — Web application where image uploads were previously accepted and written to storage without pre-validation
  - fact: A user uploaded a video that was stored before any validation ran, exposing the timing bug
- [[Upload Validation]] (system) — File validation layer now operating on the incoming request stream
  - fact: Type checking moved from filename inspection to byte-level detection for accuracy
  - fact: Size enforcement now happens during read rather than after buffering, preventing resource waste

## Contradictions

None identified.