---
title: "Star History Tracking"
type: source
tags: [wiki-add, raw-doc, session-transcript, star-history, github-stars, adoption-metrics, github-actions, metrics-tracking]
date: 2026-09-28
source_file: 
project: star-history
model: 
last_updated: 2026-09-29
---
## Summary

Documented comprehensive approach to tracking GitHub star growth as a key adoption metric for [[llmwiki]]. Provided ready-to-use code snippets for embedding live star-history.com charts, shields.io badges, and automating monthly snapshots via [[GitHub Actions]]. Established a 50-star threshold for adding charts to README and included a monthly check-in template to correlate star growth with project activity (launches, blog posts, community mentions).

## Key Claims

- Star history charts should only be added to README once a repository reaches 50+ stars (before that, sparse data makes charts meaningless)
- star-history.com provides free chart embedding without authentication required
- GitHub Actions can automate monthly star count snapshots with a simple scheduled workflow triggered on the 1st of each month
- The recommended badge color `7C3AED` matches [[llmwiki]]'s accent purple
- Multi-repository star charts are useful for competitive positioning against related projects (mem0, hivemind)

## Key Quotes

> "Add this section to the README once the repo has 50+ stars (before that the chart is too sparse to be meaningful)."

Establishes a concrete, data-informed threshold for when metrics visualization becomes valuable rather than cluttering early-stage documentation.

## Connections

- [[llmwiki]] (entity) — the project whose star growth is being tracked
  - fact: All examples are configured specifically for AlexanderMakarov/llm-wiki repository
- [[GitHub Actions]] (entity) — used to automate monthly star count snapshots
  - fact: Scheduled workflow on the 1st of each month uses GitHub CLI API to log current star count
- [[Static Site]] (concept) — star charts and badges are embeddable media for README and blog posts
  - fact: Shields.io badges automatically update, providing dynamic content in static site documentation
- [[Observability]] (concept) — star growth as a key metric for measuring adoption velocity
  - fact: Monthly check-in template correlates star deltas with project activity (releases, blog posts, community mentions)