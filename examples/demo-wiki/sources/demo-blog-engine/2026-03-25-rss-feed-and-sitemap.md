---
title: "Session: rss-feed-and-sitemap — 2026-03-25"
type: source
tags: [claude-code, session-transcript, demo, demo-blog-engine, claude, rss-feed, sitemap, rust, static-site, zero-deps, string-templates, xml-escaping]
date: 2026-03-25
source_file: raw/sessions/demo-blog-engine/2026-03-25-rss-feed-and-sitemap.md
project: demo-blog-engine
model: claude-sonnet-4-6
last_updated: 2026-07-29
---
## Summary

The session implemented RSS 2.0 feed and XML sitemap generation for the demo blog engine, using pure string templates rather than external XML libraries. Both feeds are generated as strings in `src/feeds.rs`, escaped via a minimal `xml_escape` helper handling 5 special characters, and written to `public/rss.xml` and `public/sitemap.xml`. The implementation also added feed discovery metadata to the HTML `<head>` of all post pages.

## Key Claims

- RSS 2.0 and XML sitemaps can be generated as plain strings without using an external XML library
- A helper function escaping just 5 XML special characters (`` ` < ` ``, `` ` > ` ``, `` ` & ` ``, `` ` " ` ``, `` ` ' ` ``) is sufficient for valid feed generation
- Feed discoverability requires a `<link rel="alternate" type="application/rss+xml" href="/rss.xml">` tag in the HTML head
- Implementing feeds as string templates rather than using an XML library keeps project dependencies minimal

## Key Quotes

> "Keep dependencies light" — the constraint that drove the decision to generate feeds as strings rather than using an XML library

> "Both return strings which `main.rs` writes to `public/`" — the straightforward architecture: feeds are generated as strings and directly persisted to files

## Connections

- [[DemoBlogEngine]] — the blog engine project being extended with feed support
- [[RSS]] — web feed standard implemented (RSS 2.0 version)
- [[Sitemap]] — XML sitemap format implemented for search engine discoverability