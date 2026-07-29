---
title: "Session: gentle-planning-hopper — 2026-04-03"
type: source
tags: [claude-code, session-transcript, demo, research, demo-beta, claude, static-blog-gen, markdown-parsing, frontmatter, go-cli, minimal-architecture, static-site-gen, go-lang, markdown-html, minimal-design]
date: 2026-04-03
source_file: raw/sessions/demo-beta/2026-04-03-gentle-planning-hopper.md
project: demo-beta
model: claude-opus-4-6
last_updated: 2026-07-29
---
## Summary

The session planned the architecture for **Stilo**, a minimal Go static blog generator designed to fill the gap between tiny generators (120–500 LoC) and massive tools like Hugo/Zola (50k+ LoC). The assistant recommended core libraries—`gomarkdown` for markdown parsing and stdlib's `html/template` for rendering—and drafted a five-file implementation plan with clear directory structure. The project scope locked at markdown-to-HTML-only with frontmatter support, aiming for under-200-line simplicity, and the project name was selected from several options.

## Key Claims

- A minimal Go static blog generator can be built in under 200 lines of code
- The 2026 Go ecosystem has a significant gap: generators are either minimal (120–500 LoC) or massive (Hugo/Zola at 50k+ LoC)
- `github.com/gomarkdown/markdown` is the recommended markdown parser for this use case (actively maintained, no CGO required)
- Stdlib's `html/template` is sufficient for template rendering without external dependencies
- Existing minimal generators in 2026 include `pelle-fk/tinysg` (180 LoC) and `haahnah/minimd` (120 LoC)

## Key Quotes

> "The minimal tier is a huge gap you could fill."

This identifies the market opportunity and positions Stilo's strategic niche: large tools dominate, but minimal, focused alternatives remain underdeveloped.

> "A Go static blog generator with only markdown → HTML can be done in under 200 lines."

This statement anchors the project's feasibility and scope, constraining the feature set to essential transformations only.

## Connections

- [[Stilo]] — the blog generator project being architected and planned in this session
- [[Static Site Generation]] — the product domain and market category where Stilo positions itself