---
title: "Monthly Project Health Report Template"
type: source
tags: [wiki-add, raw-doc, session-transcript, monthly-report-template, observability, github-metrics, project-health]
date: 2026-10-01
source_file: 
project: monthly-report-template
model: 
last_updated: 2026-10-01
---
## Summary

The session introduces a standardized monthly reporting template for tracking llmwiki's project health metrics across adoption, development activity, and demo site performance. The template automates data collection from GitHub Insights, PyPI stats, and the gh CLI with date-filtered searches, and recommends publishing reports to GitHub Discussions for community transparency.

## Key Claims

- Monthly project health reports should track six adoption metrics: GitHub stars, forks, unique cloners, unique visitors, PyPI monthly downloads, and PyPI installs.
- The `gh` CLI can automate collection of monthly issue and PR metrics using date-filtered searches (e.g., `--search "created:2026-MM-01..2026-MM-31"`).
- PyPI download statistics are accessible via pepy.tech or the pypistats tool (`pypistats overall llmwiki --last-month`).
- New contributors can be extracted from merged PRs by querying with `gh pr list --state merged --json author --jq '.[].author.login' | sort -u`.
- Lighthouse scores should be tracked monthly as a proxy for demo site performance and accessibility compliance.

## Key Quotes

> "Copy this template at the start of each month. Fill in the numbers from GitHub Insights, the issue tracker, and PyPI stats." — defines the monthly cadence and unified data sources for comprehensive health tracking.

> "GitHub Discussions: create a 'Monthly Reports' category for public transparency" — recommends public-facing publication of metrics for community engagement and stakeholder trust.

> "run `npx lighthouse https://alexandermakarov.github.io/llm-wiki/ --output=json`" — specifies tooling for automated performance auditing of the deployed demo site.

## Connections

- `[[llmwiki]]` (entity) — the open-source project whose health metrics are tracked monthly
  - fact: The template captures adoption metrics (stars, forks, cloners, visitors, PyPI), development activity (issues, PRs, contributors), releases, test suite performance, and demo site uptime/performance.

## Contradictions

None identified.