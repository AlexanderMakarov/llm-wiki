---
title: "Uptime Monitoring"
type: source
tags: [wiki-add, raw-doc, session-transcript, uptime, github-actions, version-freshness, observability, incident-response]
date: 2026-09-28
source_file: 
project: uptime
model: 
last_updated: 2026-09-29
---
## Summary

This document establishes uptime and freshness monitoring strategies for the [[llmwiki]] demo site, distinguishing between availability (HTTP response codes) and correctness (deployed version matches code). It provides a scheduled [[GitHub Actions]] workflow checking every 6 hours, a post-deploy version verification mechanism via `manifest.json`, guidance on external monitoring services, and incident response procedures.

## Key Claims

- An uptime check (HTTP 200 response) is distinct from a freshness check (deployed version matches source code); a site can pass all HTTP availability checks while serving stale content (illustrated by incident #213).
- `site/manifest.json` contains the build's `__version__`, enabling `scripts/check_live_version.py` to compare deployed against expected versions with distinct exit codes (0: match, 1: mismatch, 2: unreachable, 3: malformed).
- The post-deploy version check in `.github/workflows/pages.yml` is the only automated freshness gate; a failed check indicates stale content deployment, not an HTTP outage.
- [[GitHub Actions]] provides sufficient monitoring (2,000 min/month free tier) for personal projects without external third-party monitoring services.
- Six key endpoints require monitoring: home page (`/`), sitemap (`/sitemap.xml`), AI agent discovery (`/llms.txt`), search index (`/search-index.json`), build metadata (`/manifest.json`), and sample session content.

## Key Quotes

> "An uptime check answers 'is the site up', which is not the same question as 'is the site current'." — Core distinction illustrated by the [[llmwiki]] demo serving a four-release-old build with entirely passing HTTP checks; uptime alone does not guarantee content freshness.

> "A red post-deploy check is not an outage: the site is up, it is just not serving this build yet (or at all)." — Critical incident response clarification: version mismatches require re-deploying or re-tagging, not escalation as HTTP failures.

## Connections

- [[llmwiki]] (entity) — the demo site being monitored for both uptime and version freshness.
  - fact: Scheduled checks every 6 hours verify HTTP 200 on core endpoints and version parity post-deployment.
- [[GitHub Actions]] (entity) — implements the scheduled uptime checks and post-deploy version assertions.
  - fact: `.github/workflows/uptime.yml` runs on a 6-hour cron with optional Slack/Discord webhook notifications on failure.
- [[GitHub Pages]] (entity) — the deployment platform whose post-deploy state is validated by the version check.
  - fact: The version check runs immediately after `actions/deploy-pages` to confirm live site matches the committed build.
- [[Static Site]] (concept) — the class of site being monitored; static endpoints reliably carry version metadata and structured content.
- [[Observability]] (concept) — monitoring framework encompassing both availability (HTTP status) and freshness (version parity) signals.

## Contradictions

- None identified.