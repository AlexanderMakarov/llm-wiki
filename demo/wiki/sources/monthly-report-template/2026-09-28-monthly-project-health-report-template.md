---
title: "Monthly Project Health Report Template"
type: source
tags: [wiki-add, raw-doc, session-transcript, monthly-report-template, project-metrics, github-insights, github-cli]
date: 2026-09-28
source_file: 
project: monthly-report-template
model: 
last_updated: 2026-09-28
---
## Summary

Established a standardized monthly health report template for [[llmwiki]] that systematically captures adoption metrics (GitHub stars/forks, PyPI downloads, cloner/visitor counts), issue and PR velocity, contributor activity, release information, test coverage, and demo site health. The template includes concrete data-gathering procedures using GitHub Insights, the `gh` CLI with specific search queries, and PyPI stats, with guidance on publishing via GitHub Discussions for public transparency, internal documentation for stakeholders, or blog posts for milestone announcements.

## Key Claims

1. Project health across all major dimensions (adoption, velocity, contributor activity, release cadence, test coverage, site reliability) can be systematically tracked and reported monthly using standardized metrics.
2. GitHub Insights, the `gh` CLI with specific date-range search queries, and PyPI stats are the primary authoritative data sources for gathering monthly metrics.
3. Monthly reports should be published through different channels depending on audience and context: GitHub Discussions for public transparency, internal docs for private stakeholders, and blog posts for quarterly summaries or major milestones.

## Key Quotes

> "Copy this template at the start of each month. Fill in the numbers from GitHub Insights, the issue tracker, and PyPI stats." — Establishes the intended monthly cadence and the three primary data sources.

> "Where to publish: GitHub Discussions (public transparency), Internal doc (if the project has private stakeholders), Blog post (quarterly or on major milestones)" — Shows how report distribution strategy varies by audience and milestone timing.

## Connections

- [[llmwiki]] (entity) — The project being monitored through monthly health reports
  - fact: Monthly reports systematically track adoption metrics, issue/PR velocity, contributor activity, test coverage, and demo site health
- [[Static Site]] (entity) — The deployed demo site whose uptime, Lighthouse scores, page counts, and visitor metrics are included in the health report
  - fact: The template includes a dedicated "Demo site" section tracking uptime %, Lighthouse scores, pages deployed, and unique visitor counts

## Contradictions

None identified.