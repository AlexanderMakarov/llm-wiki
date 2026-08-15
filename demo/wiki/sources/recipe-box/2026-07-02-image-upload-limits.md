---
title: "Validate image uploads before they reach storage"
type: source
tags: [session, session-transcript, recipe-box, claude, file-upload-validation, stream-processing, content-type-detection, configurable-limits]
date: 2026-07-02
source_file: raw/sessions/recipe-box/2026-07-02T19-44-recipe-box-image-upload-limits.md
project: recipe-box
model: claude-opus-5
last_updated: 2026-08-11
---
## Summary
The session addressed a critical upload validation bug where files were rejected only *after* being written to storage. The fix implements pre-emptive validation on the incoming stream: type checking now inspects actual file bytes rather than the declared filename, and a configurable size cap (default 8MB) is enforced during the read phase to prevent buffering of oversized files. Error messages were improved to report both the size limit and detected content type.

## Key Claims
- Upload validation previously occurred *after* writing to storage, allowing invalid files to be persisted
- Type detection now examines actual file bytes during streaming rather than trusting the uploaded filename
- File size is capped (default 8MB) and enforced during the read phase, rejecting oversized uploads before buffering
- Error messages now include both the violated limit and the detected content type

## Key Quotes
> "Validation ran after the write. It now happens on the incoming stream: type is checked from the actual bytes rather than the declared name, and the read is capped so an oversized file is rejected before it is buffered."

This describes the core fix: shifting from post-write validation to pre-emptive stream-based validation.

> "The cap is enforced during the read, so an attempt to send more is cut off rather than measured after the fact."

Clarifies the critical distinction—size limits prevent buffering, avoiding resource exhaustion and potential denial-of-service vectors.

## Connections
- [[Recipe Box]] — the application whose upload handling was secured
- [[Upload Validation]] — the security-critical feature being improved