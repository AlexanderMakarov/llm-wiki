---
title: "Uptime Monitoring"
type: source
tags: [wiki-add, raw-doc, session-transcript, uptime, github-actions, version-freshness, deployment-verification, incident-response]
date: 2026-09-07
source_file: raw/docs/uptime/uptime-monitoring.md
project: uptime
model: 
last_updated: 2026-09-07
---
## Summary

This documentation provides a monitoring strategy for the llmwiki demo site that separates uptime checks (HTTP availability) from version freshness verification (whether the live deployment matches the current build). A key motivation is issue #213, in which the demo served a four-release-old build while all HTTP-level checks passed. The solution includes a `scripts/check_live_version.py` script that verifies `manifest.json` after each deployment, with distinct exit codes for different failure modes.

## Key Claims

- Uptime checks (HTTP 200 responses) and version freshness checks are distinct monitoring concerns requiring separate tools
- The llmwiki demo once served a four-release-old build with all uptime checks passing, proving availability does not guarantee correctness (#213)
- `llmwiki build` writes `site/manifest.json` containing `__version__`, enabling post-deployment version verification
- `scripts/check_live_version.py` compares deployed version against repository version or an explicit tag, with exit codes indicating different failure modes (0 = match, 1 = stale, 2 = unreachable, 3 = malformed)
- GitHub Pages workflow `.github/workflows/pages.yml` runs version freshness checks immediately after `actions/deploy-pages`, making version correctness a deployment gate
- A red post-deploy check indicates freshness failure (stale build), not necessarily an HTTP outage

## Key Quotes

> "The llmwiki demo once served a four-release-old build behind entirely green checks: every URL returned 200, and nothing compared what was published with what had been released (#213)."
> — Motivating example for why version freshness checks must complement simple uptime monitoring

> "A red post-deploy check is not an outage: the site is up, it is just not serving this build yet (or at all)."
> — Clarifies incident classification and prevents incorrect outage responses

## Connections

- [[llmwiki]] (project) — the demo site subject to this monitoring strategy
  - fact: Demo hosted at https://pratiyush.github.io/llm-wiki/
  - fact: Requires both HTTP availability and version freshness verification

- [[GitHub Actions]] (tool) — implements scheduled uptime checks and post-deploy verification
  - fact: Uptime workflow runs every 6 hours via cron schedule
  - fact: GitHub Actions provides 2,000 free minutes/month, sufficient for continuous monitoring

- [[GitHub Pages]] (platform) — deployment target being monitored
  - fact: Version check runs immediately after `actions/deploy-pages` to verify live deployment
  - fact: DNS misconfiguration (CNAME records) can trigger false uptime failures

- [[Observability]] (concept) — umbrella for uptime and freshness monitoring
  - fact: Six endpoint categories monitored: home page, sitemap, llms.txt, search-index, manifest, and session content
  - fact: Exit codes enable programmatic discrimination between network, availability, and correctness failures
