---
title: "Session: scaffolding-the-rust-blog-engine — 2026-03-12"
type: source
tags: [claude-code, session-transcript, demo, demo-blog-engine, claude, static-site-generation, markdown-parsing, project-scaffolding, pulldown-cmark, frontmatter-parsing]
date: 2026-03-12
source_file: raw/sessions/demo-blog-engine/2026-03-12-scaffolding-the-rust-blog-engine.md
project: demo-blog-engine
model: claude-sonnet-4-6
last_updated: 2026-07-29
---
## Summary

Bootstrapped a minimal static-site generator in Rust, choosing `pulldown-cmark` over `comrak` for markdown parsing due to its smaller footprint and focus on CommonMark compliance. Scaffolded the project with a `Post` struct holding metadata (title, slug, date), implemented TOML frontmatter parsing delimited by `+++`, and integrated the markdown-to-HTML pipeline. Initial test build succeeded.

## Key Claims

- `pulldown-cmark` was chosen over `comrak` because it prioritizes minimal dependencies and fast compile times; if GitHub Flavored Markdown features become necessary, switching to `comrak` remains possible.
- The `Post` struct stores `title`, `slug`, `date`, and `body_html`.
- Markdown frontmatter is delimited by `+++` lines and parsed as TOML using the `toml` crate.
- Clean builds take approximately 14 seconds; incremental rebuilds complete in 0.4 seconds.
- The markdown parser is configured with `Options::ENABLE_STRIKETHROUGH` to support strikethrough syntax.

## Key Quotes

> "Since we want something minimal, I'll start with `pulldown-cmark` and we can switch if we need GFM." — encapsulates the design philosophy: begin with the simplest suitable tool and upgrade only when requirements justify the added complexity.

## Connections

- [[demo-blog-engine]] — the Rust project being scaffolded
- [[pulldown-cmark]] — markdown parser library selected for its minimal footprint
- [[StaticSiteGeneration]] — the problem domain being addressed