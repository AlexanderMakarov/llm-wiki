---
title: "Deploying to Vercel or Netlify"
type: source
tags: [wiki-add, raw-doc, session-transcript, deploying-to-vercel-or-netlify, static-hosting, build-automation]
date: 2026-08-10
source_file: 
project: deploying-to-vercel-or-netlify
model: 
last_updated: 2026-08-11
---
## Summary

The document provides step-by-step instructions for deploying [[llmwiki]] to [[Vercel]] and [[Netlify]]. Both platforms require Python runtime, session data (either committed or seeded from demo), and configuration of the output directory to `site/`. The guide covers platform-specific setup (including `vercel.json` and `netlify.toml`), Python version management, custom domain configuration, and troubleshooting common build and runtime issues.

## Key Claims

- [[llmwiki]] produces a plain static site under `site/` that any static hosting platform can serve
- Both [[Vercel]] and [[Netlify]] require: Python runtime, session data (committed or seeded with `--vault demo`), and output directory set to `site/`
- The standard build command across both platforms is `pip install markdown && python3 -m llmwiki init && python3 -m llmwiki build --out ./site`
- Session data can be seeded with the `--vault demo` flag if not committed to the repository
- For 1000+ sessions, builds take 30–60 seconds (CPU-bound markdown rendering) and remain within free-tier time limits on both platforms
- HTTPS is automatically provisioned on both [[Vercel]] and [[Netlify]] when adding custom domains

## Key Quotes

> "Both platforms need: 1. A Python runtime to run `llmwiki build` 2. Session data committed to the repo (or seeded from examples) 3. The output directory pointed at `site/`" — distills the three essential deployment requirements into a compact checklist

> "Make sure the build command includes `pip install markdown` (not `pip install -e .`, which requires the repo to be a proper Python package)." — explains why the build uses a non-standard pip pattern and prevents a common failure mode

> "The build is CPU-bound (markdown rendering). For large session stores (1000+ sessions), builds take 30-60 seconds. This is within Vercel's and Netlify's free-tier build time limits." — sets performance expectations and confirms cost viability

## Connections

- [[Vercel]] — static hosting platform with Python 3 runtime support and automatic HTTPS; configured via `vercel.json` at repo root
- [[Netlify]] — alternative static hosting platform with Python 3.8+ support, SPA redirects, and `netlify.toml` configuration for reproducibility
- [[llmwiki]] — the static site generator being deployed; outputs to `site/` directory via markdown rendering

## Contradictions

None identified.