---
title: "Validate image uploads before they reach storage"
type: source
tags: [session, session-transcript, recipe-box, claude, image-upload-validation, stream-capping, content-type-detection, file-size-limits, upload-middleware]
date: 2026-07-31
source_file: raw/sessions/recipe-box/2026-07-31T19-44-recipe-box-image-upload-limits.md
project: recipe-box
model: claude-opus-5
last_updated: 2026-09-08
---
## Summary

The session fixed recipe-box image uploads that accepted invalid files because checks ran only after storage. Validation now runs on the incoming stream: MIME/type is inferred from file bytes instead of the client filename, and reads are capped so oversize payloads are rejected before buffering. User-facing errors report the configured size limit and the detected type. The maximum upload size is configurable with an eight-megabyte default, enforced during the read so excess data is cut off rather than measured after the fact.

## Key Claims

- Upload validation previously ran after the file was written to storage, so a video could be stored before any rejection.
- Content type is determined from actual bytes on the stream, not from the declared filename or `Content-Type` header alone.
- A configurable read cap (default 8 MB) stops the stream during read; oversize uploads are rejected without fully buffering the body.
- Error responses name both the applicable limit and the detected media type, replacing a generic “upload failed” message.

## Key Quotes

> "Validation ran after the write. It now happens on the incoming stream: type is checked from the actual bytes rather than the declared name, and the read is capped so an oversized file is rejected before it is buffered." — describes the shift from post-write to streaming validation.

> "Configurable, defaulting to eight megabytes. The cap is enforced during the read, so an attempt to send more is cut off rather than measured after the fact." — defines default limit and streaming enforcement semantics.

## Connections

- [[recipe-box]] (project) — web app where recipe image uploads were hardened on branch `feat/uploads`.
  - fact: Oversized and wrong-type uploads (e.g. video) could be stored before validation; fix targets the upload path for images.
- Validation (concept) — fail-fast checks on the request body before persistence.
  - fact: Type and size limits are applied while reading the upload stream, not after write completes.
